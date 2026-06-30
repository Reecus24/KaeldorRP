from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import uuid
import logging
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from bson import ObjectId
from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from game_models import now_utc, clamp, new_player, BACKGROUNDS, SKILLS, DEFAULT_CONFIG
from game_engine import (
    resolve_player, get_config, add_event, real_seconds, parse_dt,
    charge, add_money, effectiveness, apply_effects, add_skill_xp,
)
from seed_data import seed_content, CONTENT_MAP
import employee_engine

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"

app = FastAPI(title="Kaeldor RPG API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("kaeldor")


# ============================ AUTH ============================
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "type": "access",
               "exp": datetime.now(timezone.utc) + timedelta(days=7)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def set_auth_cookie(response: Response, token: str):
    response.set_cookie(key="access_token", value=token, httponly=True, secure=False,
                        samesite="lax", max_age=604800, path="/")


async def current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["id"] = str(user["_id"])
        user.pop("_id", None)
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def admin_user(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=4)
    name: str = Field(min_length=1)


class LoginBody(BaseModel):
    email: EmailStr
    password: str


@api.post("/auth/register")
async def register(body: RegisterBody, response: Response):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    doc = {"email": email, "password_hash": hash_password(body.password), "name": body.name,
           "role": "player", "created_at": now_utc().isoformat()}
    res = await db.users.insert_one(doc)
    uid = str(res.inserted_id)
    token = create_access_token(uid, email)
    set_auth_cookie(response, token)
    return {"token": token, "user": {"id": uid, "email": email, "name": body.name, "role": "player"}}


@api.post("/auth/login")
async def login(body: LoginBody, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    uid = str(user["_id"])
    token = create_access_token(uid, email)
    set_auth_cookie(response, token)
    return {"token": token, "user": {"id": uid, "email": email, "name": user.get("name"), "role": user.get("role", "player")}}


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    return {"id": user["id"], "email": user["email"], "name": user.get("name"), "role": user.get("role", "player")}


# ============================ HELPERS ============================
def meets_requirements(p, req):
    req = req or {}
    for sk, lvl in (req.get("skills") or {}).items():
        if p["skills"].get(sk, {}).get("level", 1) < lvl:
            return False, f"Requires {sk} level {lvl}"
    for edu in (req.get("education") or []):
        if edu not in p["education"]:
            return False, f"Requires course: {edu}"
    if req.get("min_reputation") and p["reputation"] < req["min_reputation"]:
        return False, f"Requires reputation {req['min_reputation']}"
    if req.get("vehicle"):
        if not p.get("vehicles"):
            return False, "Requires a vehicle"
    return True, ""


def ensure_free(p):
    if p.get("status") == "jail":
        raise HTTPException(status_code=409, detail="You are in jail. Wait it out or post bail.")
    if p.get("status") == "hospital":
        raise HTTPException(status_code=409, detail="You are in hospital recovering.")
    if p.get("current_activity"):
        raise HTTPException(status_code=409, detail="You are already busy with another activity.")


def set_activity(p, kind, name, duration_game_minutes, cfg, payload, blocking=True, sleep_flag=False):
    ts = cfg["time_scale"]
    now = now_utc()
    ends = now + timedelta(seconds=real_seconds(duration_game_minutes, ts))
    p["current_activity"] = {
        "kind": kind, "name": name,
        "started_at": now.isoformat(), "ends_at": ends.isoformat(),
        "blocking": blocking, "sleep_flag": sleep_flag,
        "duration_minutes": duration_game_minutes, "payload": payload,
    }
    p["status"] = "busy"


async def fetch_raw_player(user_id):
    p = await db.players.find_one({"user_id": user_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="No character. Create one first.")
    return p


async def save_player(p):
    await db.players.update_one({"id": p["id"]}, {"$set": p})


async def compute_net_worth(p):
    nw = p["cash"] + p["bank"] - p["debt"]
    for v in p.get("vehicles", []):
        spec = v.get("spec", {})
        nw += spec.get("price", 0) * spec.get("resale", 0.5) * (v.get("condition", 100) / 100.0)
    if p.get("housing", {}).get("owned"):
        hd = await db.housing.find_one({"id": p["housing"]["id"]}, {"_id": 0})
        if hd:
            nw += hd.get("buy_price", 0) * 0.8
    bizs = await db.businesses.find({"player_id": p["id"], "bankrupt": {"$ne": True}}, {"_id": 0}).to_list(100)
    for b in bizs:
        nw += b.get("cash", 0) - b.get("debt", 0) + b.get("purchase_price", 0) * 0.5
    return round(nw, 2)


async def get_state(user):
    p = await fetch_raw_player(user["id"])
    await resolve_player(db, p)
    p["net_worth"] = await compute_net_worth(p)
    await save_player(p)
    return p


def serialize_activity(p):
    act = p.get("current_activity")
    if not act:
        return None
    now = now_utc()
    ends = parse_dt(act["ends_at"])
    started = parse_dt(act["started_at"])
    total = max(1, (ends - started).total_seconds())
    remaining = max(0, (ends - now).total_seconds())
    return {
        "kind": act["kind"], "name": act["name"], "blocking": act.get("blocking", True),
        "started_at": act["started_at"], "ends_at": act["ends_at"],
        "total_seconds": round(total), "remaining_seconds": round(remaining),
        "progress": round(min(1.0, (total - remaining) / total), 3),
    }


def confine_remaining(p):
    out = {}
    for key, label in (("jail_until", "jail"), ("hospital_until", "hospital")):
        dt = parse_dt(p.get(key))
        if dt and dt > now_utc():
            out[label] = round((dt - now_utc()).total_seconds())
    return out


# ============================ GAME STATE ============================
class CharacterBody(BaseModel):
    name: str = Field(min_length=1, max_length=24)
    background: str = "drifter"


@api.get("/backgrounds")
async def list_backgrounds():
    return [{"id": k, **v} for k, v in BACKGROUNDS.items()]


@api.post("/character/create")
async def create_character(body: CharacterBody, user: dict = Depends(current_user)):
    existing = await db.players.find_one({"user_id": user["id"]})
    if existing:
        raise HTTPException(status_code=400, detail="Character already exists")
    p = new_player(user["id"], body.name, body.background)
    await db.players.insert_one({**p})
    await add_event(db, p["id"], f"Welcome to Kaeldor, {body.name}. Your new life begins now.", "system", "info")
    return {"ok": True}


@api.get("/game/state")
async def game_state(user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    return {
        "player": p,
        "activity": serialize_activity(p),
        "confinement": confine_remaining(p),
        "net_worth": p["net_worth"],
        "time_scale": cfg["time_scale"],
        "effectiveness": round(effectiveness(p), 2),
    }


@api.get("/game/events")
async def game_events(limit: int = 60, user: dict = Depends(current_user)):
    p = await fetch_raw_player(user["id"])
    evs = await db.events.find({"player_id": p["id"]}, {"_id": 0}).sort("ts", -1).to_list(limit)
    return evs


@api.post("/game/cancel-activity")
async def cancel_activity(user: dict = Depends(current_user)):
    p = await get_state(user)
    if not p.get("current_activity"):
        raise HTTPException(status_code=400, detail="Nothing to cancel")
    act = p["current_activity"]
    if act["kind"] in ("job", "course"):
        p["stress"] = clamp(p["stress"] + 8)
    p["current_activity"] = None
    p["status"] = "free"
    await add_event(db, p["id"], f"You abandoned '{act['name']}' early.", "system", "warning")
    await save_player(p)
    return {"ok": True}


# ============================ ACTIONS ============================
@api.get("/actions")
async def list_actions(user: dict = Depends(current_user)):
    p = await get_state(user)
    actions = await db.actions.find({}, {"_id": 0}).to_list(200)
    out = []
    for a in actions:
        ok, reason = meets_requirements(p, a.get("requirements"))
        cd = p.get("cooldowns", {}).get(a["id"])
        on_cd = cd and parse_dt(cd) > now_utc()
        out.append({**a, "available": bool(ok and not on_cd),
                    "reason": reason if not ok else ("On cooldown" if on_cd else ""),
                    "cooldown_remaining": round((parse_dt(cd) - now_utc()).total_seconds()) if on_cd else 0})
    return out


@api.post("/actions/{action_id}/start")
async def start_action(action_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    ensure_free(p)
    a = await db.actions.find_one({"id": action_id}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Action not found")
    ok, reason = meets_requirements(p, a.get("requirements"))
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    cd = p.get("cooldowns", {}).get(action_id)
    if cd and parse_dt(cd) > now_utc():
        raise HTTPException(status_code=409, detail="Action on cooldown")
    cfg = await get_config(db)
    if a.get("money_cost", 0) > 0:
        if p["cash"] + p["bank"] < a["money_cost"]:
            raise HTTPException(status_code=400, detail="Not enough money")
        charge(p, a["money_cost"])
    sleep_quality = 1.0
    if a.get("sleep"):
        hd = await db.housing.find_one({"id": p.get("housing", {}).get("id")}, {"_id": 0})
        sleep_quality = (hd or {}).get("sleep_quality", 1.0)
    payload = {
        "name": a["name"], "effects": a.get("effects", {}), "skill_xp": a.get("skill_xp", {}),
        "money_reward": a.get("money_reward", 0), "result_text": a.get("result_text", "Done."),
        "sleep": a.get("sleep", False), "sleep_quality": sleep_quality,
        "repairs_vehicle": a.get("repairs_vehicle", False), "action_id": action_id,
    }
    set_activity(p, "action", a["name"], a["duration_minutes"], cfg, payload,
                 blocking=a.get("blocking", True), sleep_flag=a.get("sleep", False))
    if a.get("cooldown_minutes", 0) > 0:
        ts = cfg["time_scale"]
        p.setdefault("cooldowns", {})[action_id] = (
            now_utc() + timedelta(seconds=real_seconds(a["duration_minutes"] + a["cooldown_minutes"], ts))).isoformat()
    await add_event(db, p["id"], f"Started: {a['name']}.", "action", "info")
    await save_player(p)
    return {"ok": True, "activity": serialize_activity(p)}


# ============================ JOBS ============================
@api.get("/jobs")
async def list_jobs(user: dict = Depends(current_user)):
    p = await get_state(user)
    jobs = await db.jobs.find({}, {"_id": 0}).to_list(200)
    out = []
    for j in jobs:
        ok, reason = meets_requirements(p, j.get("requirements"))
        out.append({**j, "qualified": ok, "reason": reason})
    return sorted(out, key=lambda x: x.get("tier", 1))


@api.get("/jobs/current")
async def current_job(user: dict = Depends(current_user)):
    p = await get_state(user)
    if not p.get("job"):
        return {"job": None}
    jd = await db.jobs.find_one({"id": p["job"]["job_id"]}, {"_id": 0})
    promo = None
    if jd and jd.get("promotion_to"):
        target = await db.jobs.find_one({"id": jd["promotion_to"]}, {"_id": 0})
        req = jd.get("promotion_req", {})
        ok = True
        reasons = []
        if p["job"].get("shifts_worked", 0) < req.get("shifts", 0):
            ok = False
            reasons.append(f"{req.get('shifts')} shifts (you have {p['job'].get('shifts_worked',0)})")
        mok, mreason = meets_requirements(p, {"skills": req.get("skills"), "education": req.get("education"),
                                              "min_reputation": req.get("reputation")})
        if not mok:
            ok = False
            reasons.append(mreason)
        promo = {"target": target, "eligible": ok, "requirements": req, "reasons": reasons}
    return {"job": p["job"], "details": jd, "promotion": promo}


@api.post("/jobs/{job_id}/apply")
async def apply_job(job_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    j = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    ok, reason = meets_requirements(p, j.get("requirements"))
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    if p["legal_reputation"] < 25:
        raise HTTPException(status_code=403, detail="Your criminal record blocks this application.")
    p["job"] = {"job_id": job_id, "title": j["title"], "shifts_worked": 0, "reliability": 50,
                "hired_at": now_utc().isoformat()}
    await add_event(db, p["id"], f"You were hired as a {j['title']}!", "job", "success")
    await save_player(p)
    return {"ok": True}


@api.post("/jobs/quit")
async def quit_job(user: dict = Depends(current_user)):
    p = await get_state(user)
    if not p.get("job"):
        raise HTTPException(status_code=400, detail="You have no job")
    title = p["job"]["title"]
    p["job"] = None
    await add_event(db, p["id"], f"You quit your job as {title}.", "job", "warning")
    await save_player(p)
    return {"ok": True}


class ShiftBody(BaseModel):
    hours: int


@api.post("/jobs/work")
async def work_shift(body: ShiftBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    ensure_free(p)
    if not p.get("job"):
        raise HTTPException(status_code=400, detail="You have no job")
    j = await db.jobs.find_one({"id": p["job"]["job_id"]}, {"_id": 0})
    if not j:
        raise HTTPException(status_code=404, detail="Job no longer exists")
    if body.hours not in j.get("shift_options", [4]):
        raise HTTPException(status_code=400, detail="Invalid shift length")
    if p["energy"] < 10:
        raise HTTPException(status_code=400, detail="Too exhausted to work. Rest first.")
    cfg = await get_config(db)
    payload = {
        "job_id": j["id"], "title": j["title"], "hours": body.hours,
        "hourly_wage": j["hourly_wage"], "fatigue_ph": j["fatigue_per_hour"],
        "stress_ph": j["stress_per_hour"], "energy_ph": j["energy_per_hour"],
        "skill_xp": j.get("skill_xp", {}),
    }
    set_activity(p, "job", f"{j['title']} ({body.hours}h shift)", body.hours * 60, cfg, payload, blocking=True)
    p["status"] = "working"
    await add_event(db, p["id"], f"Clocked in for a {body.hours}h shift as {j['title']}.", "job", "info")
    await save_player(p)
    return {"ok": True, "activity": serialize_activity(p)}


@api.post("/jobs/promote")
async def promote(user: dict = Depends(current_user)):
    p = await get_state(user)
    if not p.get("job"):
        raise HTTPException(status_code=400, detail="You have no job")
    jd = await db.jobs.find_one({"id": p["job"]["job_id"]}, {"_id": 0})
    if not jd or not jd.get("promotion_to"):
        raise HTTPException(status_code=400, detail="No promotion available")
    req = jd.get("promotion_req", {})
    if p["job"].get("shifts_worked", 0) < req.get("shifts", 0):
        raise HTTPException(status_code=400, detail="Not enough shifts worked")
    mok, mreason = meets_requirements(p, {"skills": req.get("skills"), "education": req.get("education"),
                                          "min_reputation": req.get("reputation")})
    if not mok:
        raise HTTPException(status_code=400, detail=mreason)
    target = await db.jobs.find_one({"id": jd["promotion_to"]}, {"_id": 0})
    p["job"] = {"job_id": target["id"], "title": target["title"], "shifts_worked": 0,
                "reliability": 60, "hired_at": now_utc().isoformat()}
    p["reputation"] = clamp(p["reputation"] + 6)
    p["social_status"] = clamp(p["social_status"] + 5)
    await add_event(db, p["id"], f"Promoted to {target['title']}! Bigger paycheck ahead.", "job", "success")
    await save_player(p)
    return {"ok": True}


# ============================ EDUCATION ============================
@api.get("/courses")
async def list_courses(user: dict = Depends(current_user)):
    p = await get_state(user)
    courses = await db.courses.find({}, {"_id": 0}).to_list(200)
    out = []
    for c in courses:
        ok, reason = meets_requirements(p, c.get("requirements"))
        out.append({**c, "completed": c["id"] in p["education"], "qualified": ok, "reason": reason})
    return out


@api.post("/courses/{course_id}/enroll")
async def enroll_course(course_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    ensure_free(p)
    c = await db.courses.find_one({"id": course_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    if course_id in p["education"]:
        raise HTTPException(status_code=400, detail="Already completed")
    ok, reason = meets_requirements(p, c.get("requirements"))
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    if p["cash"] + p["bank"] < c["cost"]:
        raise HTTPException(status_code=400, detail="Not enough money for tuition")
    charge(p, c["cost"])
    cfg = await get_config(db)
    payload = {"course_id": course_id, "title": c["title"], "grants_skills": c.get("grants_skills", {})}
    set_activity(p, "course", f"Studying: {c['title']}", c["duration_minutes"], cfg, payload, blocking=False)
    p["status"] = "studying"
    await add_event(db, p["id"], f"Enrolled in {c['title']}. Study takes time but pays off.", "education", "info")
    await save_player(p)
    return {"ok": True, "activity": serialize_activity(p)}


# ============================ SHOP ============================
@api.get("/shop/items")
async def shop_items(user: dict = Depends(current_user)):
    return await db.items.find({}, {"_id": 0}).to_list(200)


class BuyBody(BaseModel):
    item_id: str
    qty: int = 1


@api.post("/shop/buy")
async def shop_buy(body: BuyBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    it = await db.items.find_one({"id": body.item_id}, {"_id": 0})
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    qty = max(1, body.qty)
    total = it["price"] * qty
    if p["cash"] + p["bank"] < total:
        raise HTTPException(status_code=400, detail="Not enough money")
    charge(p, total)
    cfg = await get_config(db)
    for _ in range(qty):
        eff = dict(it.get("effects", {}))
        skill_eff = {k: v for k, v in eff.items() if k in SKILLS}
        for k in skill_eff:
            eff.pop(k)
            add_skill_xp(p, k, skill_eff[k], cfg)
        apply_effects(p, eff)
    p.setdefault("inventory", {})
    p["inventory"][body.item_id] = p["inventory"].get(body.item_id, 0) + qty
    await add_event(db, p["id"], f"Bought {qty}x {it['name']} for ${total}.", "shop", "info")
    await save_player(p)
    return {"ok": True}


# ============================ BANK ============================
class AmountBody(BaseModel):
    amount: float


@api.get("/bank")
async def bank_info(user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    fin = p["skills"].get("finance", {}).get("level", 1)
    max_loan = round(max(500, (p["bank"] + p["cash"]) * cfg["economy"]["max_loan_multiplier"] + fin * 500))
    return {"cash": p["cash"], "bank": p["bank"], "debt": p["debt"],
            "max_loan": max_loan, "interest_daily": cfg["economy"]["loan_interest_daily"]}


@api.post("/bank/deposit")
async def deposit(body: AmountBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    amt = round(body.amount, 2)
    if amt <= 0 or p["cash"] < amt:
        raise HTTPException(status_code=400, detail="Invalid amount")
    p["cash"] -= amt
    p["bank"] += amt
    await save_player(p)
    return {"ok": True}


@api.post("/bank/withdraw")
async def withdraw(body: AmountBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    amt = round(body.amount, 2)
    if amt <= 0 or p["bank"] < amt:
        raise HTTPException(status_code=400, detail="Invalid amount")
    p["bank"] -= amt
    p["cash"] += amt
    await save_player(p)
    return {"ok": True}


@api.post("/bank/loan")
async def take_loan(body: AmountBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    fin = p["skills"].get("finance", {}).get("level", 1)
    max_loan = max(500, (p["bank"] + p["cash"]) * cfg["economy"]["max_loan_multiplier"] + fin * 500)
    amt = round(body.amount, 2)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")
    if p["debt"] + amt > max_loan:
        raise HTTPException(status_code=400, detail=f"Loan exceeds your limit of ${round(max_loan)}")
    p["bank"] += amt
    p["debt"] += amt
    await add_event(db, p["id"], f"Took a loan of ${amt}. The bank expects it back with interest.", "finance", "warning")
    await save_player(p)
    return {"ok": True}


@api.post("/bank/repay")
async def repay(body: AmountBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    amt = round(body.amount, 2)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")
    amt = min(amt, p["debt"])
    if p["cash"] + p["bank"] < amt:
        raise HTTPException(status_code=400, detail="Not enough money")
    charge(p, amt)
    p["debt"] = round(p["debt"] - amt, 2)
    await add_event(db, p["id"], f"Repaid ${amt} of debt.", "finance", "success")
    await save_player(p)
    return {"ok": True}


# ============================ REAL ESTATE ============================
@api.get("/housing")
async def list_housing(user: dict = Depends(current_user)):
    p = await get_state(user)
    houses = await db.housing.find({}, {"_id": 0}).to_list(100)
    return {"current": p.get("housing"), "listings": sorted(houses, key=lambda x: x.get("tier", 1))}


@api.post("/housing/{house_id}/rent")
async def rent_house(house_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    h = await db.housing.find_one({"id": house_id}, {"_id": 0})
    if not h:
        raise HTTPException(status_code=404, detail="Housing not found")
    if p["cash"] + p["bank"] < h.get("deposit", 0):
        raise HTTPException(status_code=400, detail="Cannot afford the deposit")
    charge(p, h.get("deposit", 0))
    p["housing"] = {"id": house_id, "owned": False, "since": now_utc().isoformat()}
    await add_event(db, p["id"], f"You moved into {h['name']} (renting).", "housing", "success")
    await save_player(p)
    return {"ok": True}


@api.post("/housing/{house_id}/buy")
async def buy_house(house_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    h = await db.housing.find_one({"id": house_id}, {"_id": 0})
    if not h:
        raise HTTPException(status_code=404, detail="Housing not found")
    if h.get("buy_price", 0) <= 0:
        raise HTTPException(status_code=400, detail="This property is not for sale")
    if p["cash"] + p["bank"] < h["buy_price"]:
        raise HTTPException(status_code=400, detail="Cannot afford to buy this property")
    charge(p, h["buy_price"])
    p["housing"] = {"id": house_id, "owned": True, "since": now_utc().isoformat()}
    p["social_status"] = clamp(p["social_status"] + h.get("social_status", 0) * 0.2)
    await add_event(db, p["id"], f"You bought {h['name']}! No more rent.", "housing", "success")
    await save_player(p)
    return {"ok": True}


# ============================ VEHICLES ============================
@api.get("/vehicles")
async def list_vehicles(user: dict = Depends(current_user)):
    p = await get_state(user)
    vehicles = await db.vehicles.find({}, {"_id": 0}).to_list(100)
    return {"owned": p.get("vehicles", []), "listings": sorted(vehicles, key=lambda x: x.get("price", 0))}


@api.post("/vehicles/{vehicle_id}/buy")
async def buy_vehicle(vehicle_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    v = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if p["cash"] + p["bank"] < v["price"]:
        raise HTTPException(status_code=400, detail="Cannot afford this vehicle")
    charge(p, v["price"])
    p.setdefault("vehicles", []).append({
        "instance_id": uuid.uuid4().hex, "type_id": vehicle_id, "name": v["name"],
        "condition": 100, "since": now_utc().isoformat(), "spec": v,
    })
    await add_event(db, p["id"], f"You bought a {v['name']}.", "vehicle", "success")
    await save_player(p)
    return {"ok": True}


@api.post("/vehicles/{instance_id}/sell")
async def sell_vehicle(instance_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    veh = next((x for x in p.get("vehicles", []) if x["instance_id"] == instance_id), None)
    if not veh:
        raise HTTPException(status_code=404, detail="You don't own that vehicle")
    spec = veh.get("spec", {})
    value = round(spec.get("price", 0) * spec.get("resale", 0.5) * (veh.get("condition", 100) / 100.0))
    p["vehicles"] = [x for x in p["vehicles"] if x["instance_id"] != instance_id]
    add_money(p, value)
    await add_event(db, p["id"], f"Sold your {veh['name']} for ${value}.", "vehicle", "info")
    await save_player(p)
    return {"ok": True, "value": value}


# ============================ BUSINESSES ============================
@api.get("/businesses/market")
async def business_market(user: dict = Depends(current_user)):
    p = await get_state(user)
    types = await db.business_types.find({}, {"_id": 0}).to_list(100)
    out = []
    for t in types:
        ok, reason = meets_requirements(p, t.get("requirements"))
        out.append({**t, "qualified": ok, "reason": reason})
    return sorted(out, key=lambda x: x.get("purchase_price", 0))


@api.get("/businesses/owned")
async def owned_businesses(user: dict = Depends(current_user)):
    p = await get_state(user)
    bizs = await db.businesses.find({"player_id": p["id"]}, {"_id": 0}).sort("created_at", 1).to_list(100)
    for b in bizs:
        b["metrics"] = await employee_engine.business_metrics(db, b)
    return bizs


@api.post("/businesses/{type_id}/buy")
async def buy_business(type_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    t = await db.business_types.find_one({"id": type_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Business type not found")
    ok, reason = meets_requirements(p, t.get("requirements"))
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    if p["cash"] + p["bank"] < t["purchase_price"]:
        raise HTTPException(status_code=400, detail="Cannot afford this business")
    charge(p, t["purchase_price"])
    biz = {
        "id": uuid.uuid4().hex, "player_id": p["id"], "type_id": type_id, "name": t["name"],
        "category": t.get("category", ""), "purchase_price": t["purchase_price"],
        "rent_per_day": t.get("rent_per_day", 0), "base_revenue_per_day": t.get("base_revenue_per_day", 0),
        "base_expenses_per_day": t.get("base_expenses_per_day", 0), "max_level": t.get("max_level", 5),
        "level": 1, "marketing_level": 0, "security_level": 0, "reputation": 50.0,
        "cash": 0.0, "debt": 0.0, "revenue_total": 0.0, "last_net_day": 0.0,
        "bankrupt": False, "history": [], "created_at": now_utc().isoformat(),
        "satisfaction": 60.0, "last_applicant_at": now_utc().isoformat(),
        "rev_day": 0.0, "exp_day": 0.0, "wages_day": 0.0, "coverage": 0.35, "morale_avg": 0,
    }
    await db.businesses.insert_one({**biz})
    cfg = await get_config(db)
    reqs = await employee_engine.get_staffing(db, biz)
    for _ in range(3):
        await employee_engine._create_applicant(db, p, cfg, biz, reqs, premium=False)
    await add_event(db, p["id"], f"You acquired a business: {t['name']}! Applicants are waiting to be hired.", "business", "success", biz["id"])
    await save_player(p)
    return {"ok": True}


async def _get_owned_business(p, biz_id):
    b = await db.businesses.find_one({"id": biz_id, "player_id": p["id"]}, {"_id": 0})
    if not b:
        raise HTTPException(status_code=404, detail="Business not found")
    return b


@api.post("/businesses/{biz_id}/upgrade")
async def upgrade_business(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    if b.get("bankrupt"):
        raise HTTPException(status_code=400, detail="This business is bankrupt")
    if b["level"] >= b["max_level"]:
        raise HTTPException(status_code=400, detail="Already at max level")
    cost = round(b["purchase_price"] * 0.4 * b["level"])
    if p["cash"] + p["bank"] < cost:
        raise HTTPException(status_code=400, detail=f"Upgrade costs ${cost}")
    charge(p, cost)
    b["level"] += 1
    b["reputation"] = clamp(b["reputation"] + 4)
    await db.businesses.update_one({"id": biz_id}, {"$set": b})
    await add_event(db, p["id"], f"Upgraded {b['name']} to level {b['level']}.", "business", "success")
    await save_player(p)
    return {"ok": True, "cost": cost}


@api.post("/businesses/{biz_id}/marketing")
async def marketing_business(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    if b.get("bankrupt"):
        raise HTTPException(status_code=400, detail="This business is bankrupt")
    cost = round(b["purchase_price"] * 0.12 * (b.get("marketing_level", 0) + 1))
    if p["cash"] + p["bank"] < cost:
        raise HTTPException(status_code=400, detail=f"Marketing campaign costs ${cost}")
    charge(p, cost)
    b["marketing_level"] = b.get("marketing_level", 0) + 1
    b["reputation"] = clamp(b["reputation"] + 8)
    await db.businesses.update_one({"id": biz_id}, {"$set": b})
    await add_event(db, p["id"], f"Ran a marketing campaign for {b['name']}. Reputation up!", "business", "success")
    await save_player(p)
    return {"ok": True, "cost": cost}


@api.post("/businesses/{biz_id}/collect")
async def collect_business(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    amount = round(b.get("cash", 0), 2)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="No profit to collect")
    b["cash"] = 0.0
    await db.businesses.update_one({"id": biz_id}, {"$set": {"cash": 0.0}})
    add_money(p, amount)
    await add_event(db, p["id"], f"Collected ${amount} profit from {b['name']}.", "business", "success")
    await save_player(p)
    return {"ok": True, "amount": amount}


@api.post("/businesses/{biz_id}/inject")
async def inject_business(biz_id: str, body: AmountBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    amt = round(body.amount, 2)
    if amt <= 0 or p["cash"] + p["bank"] < amt:
        raise HTTPException(status_code=400, detail="Invalid amount")
    charge(p, amt)
    paid = min(amt, b.get("debt", 0))
    b["debt"] = round(b.get("debt", 0) - paid, 2)
    b["cash"] = round(b.get("cash", 0) + (amt - paid), 2)
    if b.get("bankrupt") and b["debt"] <= 0:
        b["bankrupt"] = False
    await db.businesses.update_one({"id": biz_id}, {"$set": b})
    await add_event(db, p["id"], f"Injected ${amt} into {b['name']}.", "business", "info")
    await save_player(p)
    return {"ok": True}


@api.post("/businesses/{biz_id}/sell")
async def sell_business(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    value = round(b["purchase_price"] * 0.5 * b["level"] * (0.6 + 0.4 * b["reputation"] / 100) - b.get("debt", 0) + b.get("cash", 0))
    value = max(0, value)
    await db.businesses.delete_one({"id": biz_id})
    add_money(p, value)
    await add_event(db, p["id"], f"Sold {b['name']} for ${value}.", "business", "info")
    await save_player(p)
    return {"ok": True, "value": value}


# ============================ ILLEGAL / LEGAL ============================
@api.get("/illegal-actions")
async def list_illegal(user: dict = Depends(current_user)):
    p = await get_state(user)
    acts = await db.illegal_actions.find({}, {"_id": 0}).to_list(100)
    out = []
    for a in acts:
        ok, reason = meets_requirements(p, a.get("requirements"))
        out.append({**a, "available": ok, "reason": reason})
    return out


@api.post("/illegal-actions/{action_id}/commit")
async def commit_illegal(action_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    ensure_free(p)
    a = await db.illegal_actions.find_one({"id": action_id}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Action not found")
    ok, reason = meets_requirements(p, a.get("requirements"))
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    cfg = await get_config(db)
    payload = {k: a.get(k) for k in ("name", "reward_min", "reward_max", "suspicion_gain", "police_risk",
                                     "failure_chance", "jail_minutes", "fine_amount", "reputation_impact",
                                     "skill_xp", "lowers_suspicion")}
    set_activity(p, "illegal", a["name"], a["duration_minutes"], cfg, payload, blocking=a.get("blocking", True))
    await add_event(db, p["id"], f"You started something risky: {a['name']}...", "crime", "warning")
    await save_player(p)
    return {"ok": True, "activity": serialize_activity(p)}


@api.get("/legal/record")
async def legal_record(user: dict = Depends(current_user)):
    p = await get_state(user)
    return {"criminal_record": p.get("criminal_record", []),
            "criminal_suspicion": p["criminal_suspicion"],
            "legal_reputation": p["legal_reputation"],
            "times_jailed": p.get("stats_meta", {}).get("times_jailed", 0),
            "crimes_committed": p.get("stats_meta", {}).get("crimes_committed", 0)}


# ============================ JAIL / HOSPITAL ============================
@api.get("/jail/status")
async def jail_status(user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    rem = confine_remaining(p).get("jail", 0)
    bail = round(rem / 60 * cfg["time_scale"] * cfg["economy"]["bail_per_minute"]) if rem else 0
    return {"in_jail": p.get("status") == "jail", "remaining_seconds": rem, "bail_cost": bail}


@api.post("/jail/bail")
async def post_bail(user: dict = Depends(current_user)):
    p = await get_state(user)
    if p.get("status") != "jail":
        raise HTTPException(status_code=400, detail="You are not in jail")
    cfg = await get_config(db)
    rem = confine_remaining(p).get("jail", 0)
    bail = round(rem / 60 * cfg["time_scale"] * cfg["economy"]["bail_per_minute"])
    if p["cash"] + p["bank"] < bail:
        raise HTTPException(status_code=400, detail=f"Bail costs ${bail}, you can't afford it")
    charge(p, bail)
    p["jail_until"] = None
    p["status"] = "free"
    p["criminal_suspicion"] = clamp(p["criminal_suspicion"] + 5)
    await add_event(db, p["id"], f"You posted ${bail} bail and walked free.", "legal", "info")
    await save_player(p)
    return {"ok": True}


@api.get("/hospital/status")
async def hospital_status(user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    return {"in_hospital": p.get("status") == "hospital",
            "remaining_seconds": confine_remaining(p).get("hospital", 0),
            "health": p["health"], "treat_cost": cfg["economy"]["hospital_treat_cost"]}


@api.post("/hospital/treat")
async def hospital_treat(user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    cost = cfg["economy"]["hospital_treat_cost"]
    if p["cash"] + p["bank"] < cost:
        raise HTTPException(status_code=400, detail=f"Treatment costs ${cost}")
    charge(p, cost)
    if p.get("status") == "hospital":
        p["hospital_until"] = None
        p["status"] = "free"
    p["health"] = 100.0
    p["stress"] = clamp(p["stress"] - 10)
    await add_event(db, p["id"], f"You paid ${cost} for treatment. Health restored.", "health", "success")
    await save_player(p)
    return {"ok": True}


# ============================ LEADERBOARD ============================
@api.get("/leaderboard")
async def leaderboard(user: dict = Depends(current_user)):
    players = await db.players.find({}, {"_id": 0, "name": 1, "level": 1, "net_worth": 1,
                                         "reputation": 1, "social_status": 1, "id": 1}).to_list(500)
    players.sort(key=lambda x: x.get("net_worth", 0), reverse=True)
    me_p = await db.players.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    return {"top": players[:50], "my_id": me_p["id"] if me_p else None}


# ============================ CONFIG (public) ============================
@api.get("/config")
async def public_config():
    cfg = await get_config(db)
    return {"time_scale": cfg["time_scale"], "decay": cfg.get("decay", {})}


# ============================ ADMIN ============================
@api.get("/admin/content/{ctype}")
async def admin_list(ctype: str, admin: dict = Depends(admin_user)):
    if ctype not in CONTENT_MAP:
        raise HTTPException(status_code=404, detail="Unknown content type")
    coll = CONTENT_MAP[ctype][0]
    return await db[coll].find({}, {"_id": 0}).to_list(500)


@api.post("/admin/content/{ctype}")
async def admin_create(ctype: str, body: dict, admin: dict = Depends(admin_user)):
    if ctype not in CONTENT_MAP:
        raise HTTPException(status_code=404, detail="Unknown content type")
    coll = CONTENT_MAP[ctype][0]
    if not body.get("id"):
        body["id"] = uuid.uuid4().hex
    body.pop("_id", None)
    await db[coll].update_one({"id": body["id"]}, {"$set": body}, upsert=True)
    return {"ok": True, "id": body["id"]}


@api.put("/admin/content/{ctype}/{item_id}")
async def admin_update(ctype: str, item_id: str, body: dict, admin: dict = Depends(admin_user)):
    if ctype not in CONTENT_MAP:
        raise HTTPException(status_code=404, detail="Unknown content type")
    coll = CONTENT_MAP[ctype][0]
    body.pop("_id", None)
    body["id"] = item_id
    res = await db[coll].update_one({"id": item_id}, {"$set": body})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}


@api.delete("/admin/content/{ctype}/{item_id}")
async def admin_delete(ctype: str, item_id: str, admin: dict = Depends(admin_user)):
    if ctype not in CONTENT_MAP:
        raise HTTPException(status_code=404, detail="Unknown content type")
    coll = CONTENT_MAP[ctype][0]
    await db[coll].delete_one({"id": item_id})
    return {"ok": True}


@api.get("/admin/config")
async def admin_get_config(admin: dict = Depends(admin_user)):
    return await get_config(db)


@api.put("/admin/config")
async def admin_update_config(body: dict, admin: dict = Depends(admin_user)):
    body.pop("_id", None)
    body["id"] = "global"
    await db.config.update_one({"id": "global"}, {"$set": body}, upsert=True)
    return {"ok": True}


@api.get("/admin/players")
async def admin_players(admin: dict = Depends(admin_user)):
    players = await db.players.find({}, {"_id": 0, "name": 1, "level": 1, "cash": 1, "bank": 1,
                                         "debt": 1, "net_worth": 1, "status": 1, "reputation": 1,
                                         "id": 1, "created_at": 1}).to_list(500)
    return players


@api.get("/admin/stats")
async def admin_stats(admin: dict = Depends(admin_user)):
    return {
        "users": await db.users.count_documents({}),
        "players": await db.players.count_documents({}),
        "businesses": await db.businesses.count_documents({}),
        "jobs": await db.jobs.count_documents({}),
        "actions": await db.actions.count_documents({}),
        "courses": await db.courses.count_documents({}),
    }


# ============================ EMPLOYEES ============================
async def _get_employee(p, emp_id):
    emp = await db.employees.find_one({"id": emp_id}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    biz = await db.businesses.find_one({"id": emp["business_id"], "player_id": p["id"]}, {"_id": 0})
    if not biz:
        raise HTTPException(status_code=403, detail="Not your employee")
    return emp, biz


@api.get("/businesses/{biz_id}")
async def business_detail(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    return {"business": b, "metrics": await employee_engine.business_metrics(db, b)}


@api.get("/businesses/{biz_id}/employees")
async def biz_employees(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    emps = await db.employees.find({"business_id": biz_id, "status": {"$in": ["active", "sick"]}}, {"_id": 0}).sort("hire_date", 1).to_list(200)
    return {"employees": emps, "metrics": await employee_engine.business_metrics(db, b)}


@api.get("/businesses/{biz_id}/applicants")
async def biz_applicants(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    await _get_owned_business(p, biz_id)
    return await db.employees.find({"business_id": biz_id, "status": "applicant"}, {"_id": 0}).to_list(50)


@api.get("/businesses/{biz_id}/events")
async def biz_events(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    await _get_owned_business(p, biz_id)
    return await db.events.find({"player_id": p["id"], "business_id": biz_id}, {"_id": 0}).sort("ts", -1).to_list(50)


@api.post("/businesses/{biz_id}/applicants/{emp_id}/hire")
async def hire_applicant(biz_id: str, emp_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    await _get_owned_business(p, biz_id)
    emp = await db.employees.find_one({"id": emp_id, "business_id": biz_id, "status": "applicant"}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Applicant not found")
    await db.employees.update_one({"id": emp_id}, {"$set": {
        "status": "active", "hire_date": now_utc().isoformat(), "last_paid": now_utc().isoformat()}})
    await add_event(db, p["id"], f"You hired {emp['name']} as {emp['role'].replace('_', ' ')}.", "business", "success", biz_id)
    return {"ok": True}


@api.post("/businesses/{biz_id}/applicants/{emp_id}/reject")
async def reject_applicant(biz_id: str, emp_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    await _get_owned_business(p, biz_id)
    await db.employees.delete_one({"id": emp_id, "business_id": biz_id, "status": "applicant"})
    return {"ok": True}


@api.post("/businesses/{biz_id}/recruit")
async def recruit_applicant(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    cfg = await get_config(db)
    cost = cfg.get("employees", {}).get("recruit_cost", 250)
    if p["cash"] + p["bank"] < cost:
        raise HTTPException(status_code=400, detail=f"Recruiting costs ${cost}")
    charge(p, cost)
    await save_player(p)
    reqs = await employee_engine.get_staffing(db, b)
    await employee_engine._create_applicant(db, p, cfg, b, reqs, premium=True)
    await add_event(db, p["id"], f"A strong candidate applied at {b['name']} after recruiting.", "business", "info", biz_id)
    return {"ok": True, "cost": cost}


@api.post("/businesses/employees/{emp_id}/fire")
async def fire_employee(emp_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    emp, biz = await _get_employee(p, emp_id)
    await db.employees.update_one({"id": emp_id}, {"$set": {"status": "fired"}})
    await add_event(db, p["id"], f"You fired {emp['name']}.", "business", "warning", biz["id"])
    return {"ok": True}


@api.post("/businesses/employees/{emp_id}/raise")
async def give_raise(emp_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    emp, biz = await _get_employee(p, emp_id)
    new_wage = round(emp.get("daily_wage", 80) * 1.12, 2)
    await db.employees.update_one({"id": emp_id}, {"$set": {
        "daily_wage": new_wage, "wants_raise": False,
        "morale": clamp(emp.get("morale", 60) + 10), "loyalty": clamp(emp.get("loyalty", 50) + 6)}})
    await add_event(db, p["id"], f"You gave {emp['name']} a raise to ${new_wage}/day.", "business", "success", biz["id"])
    return {"ok": True}


@api.get("/training-options")
async def list_training_options(user: dict = Depends(current_user)):
    return await db.training_options.find({}, {"_id": 0}).to_list(50)


@api.post("/businesses/employees/{emp_id}/train")
async def train_employee(emp_id: str, body: dict, user: dict = Depends(current_user)):
    p = await get_state(user)
    emp, biz = await _get_employee(p, emp_id)
    if emp.get("training"):
        raise HTTPException(status_code=400, detail="Already in training")
    opt = await db.training_options.find_one({"id": body.get("option_id")}, {"_id": 0})
    if not opt:
        raise HTTPException(status_code=404, detail="Training option not found")
    if p["cash"] + p["bank"] < opt["cost"]:
        raise HTTPException(status_code=400, detail="Not enough money for training")
    charge(p, opt["cost"])
    await save_player(p)
    cfg = await get_config(db)
    ends = (now_utc() + timedelta(seconds=real_seconds(opt["duration_minutes"], cfg["time_scale"]))).isoformat()
    tr = {"option_id": opt["id"], "label": opt["label"], "ends_at": ends,
          "skill_gain": opt["skill_gain"], "morale_gain": opt["morale_gain"],
          "loyalty_gain": opt["loyalty_gain"], "fail_chance": opt["fail_chance"]}
    await db.employees.update_one({"id": emp_id}, {"$set": {"training": tr}})
    await add_event(db, p["id"], f"{emp['name']} started training: {opt['label']}.", "business", "info", biz["id"])
    return {"ok": True}


# ============================ STARTUP ============================
app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.players.create_index("user_id", unique=True)
    await db.players.create_index("id", unique=True)
    await db.events.create_index([("player_id", 1), ("ts", -1)])
    await db.businesses.create_index("player_id")
    await seed_content(db)
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@kaeldor.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({"email": admin_email, "password_hash": hash_password(admin_password),
                                   "name": "Game Master", "role": "admin", "created_at": now_utc().isoformat()})
    elif not verify_password(admin_password, existing.get("password_hash", "")):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})
    elif existing.get("role") != "admin":
        await db.users.update_one({"email": admin_email}, {"$set": {"role": "admin"}})
    logger.info("Kaeldor RPG started. Admin: %s", admin_email)


@app.on_event("shutdown")
async def shutdown():
    client.close()
