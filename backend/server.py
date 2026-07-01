from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

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
    add_notification, ledger_add, game_now, game_day_index,
)
from seed_data import seed_content, CONTENT_MAP, JOBS
import seed_data
import employee_engine
import social_engine
import market_engine
import comms
import employment

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
            return False, f"Requires {sk.replace('_', ' ')} level {lvl}"
    for edu in (req.get("education") or []):
        if edu not in p["education"]:
            return False, f"Requires course: {edu.replace('_', ' ')}"
    if req.get("min_reputation") and p["reputation"] < req["min_reputation"]:
        return False, f"Requires reputation {req['min_reputation']}+"
    if req.get("min_legal_reputation") and p.get("legal_reputation", 100) < req["min_legal_reputation"]:
        return False, f"Requires a clean record (Legal Standing {req['min_legal_reputation']}+)"
    if req.get("min_social_status") and p.get("social_status", 0) < req["min_social_status"]:
        return False, f"Requires social standing {req['min_social_status']}+ — build status via housing, education & connections"
    if req.get("max_suspicion") is not None and p.get("criminal_suspicion", 0) > req["max_suspicion"]:
        return False, f"Lay low — you're under too much police attention (Suspicion must be ≤ {req['max_suspicion']})"
    if req.get("vehicle"):
        if not p.get("vehicles"):
            return False, "Requires a vehicle"
    return True, ""


RAISE_INTERVAL_HOURS = 40


def required_promo_hours(req):
    req = req or {}
    if req.get("hours") is not None:
        return req["hours"]
    if req.get("shifts"):
        return req["shifts"] * 5  # backwards-compat: ~5h average shift
    return 0


async def evaluate_promotion(p, jd):
    """Hours-based promotion eligibility: worked hours + skills/education/reputation/reliability/record/boss."""
    req = (jd or {}).get("promotion_req", {}) or {}
    need_h = required_promo_hours(req)
    have_h = round((p.get("job") or {}).get("hours_worked", 0), 1)
    rel = round((p.get("job") or {}).get("reliability", 50))
    reasons = []
    eligible = True
    if have_h < need_h:
        eligible = False
        reasons.append(f"Work {round(need_h - have_h)} more hours ({round(have_h)}/{need_h}h)")
    mok, mreason = meets_requirements(p, {"skills": req.get("skills"), "education": req.get("education"),
                                          "min_reputation": req.get("reputation")})
    if not mok:
        eligible = False
        reasons.append(mreason)
    min_rel = req.get("min_reliability", 55)
    if rel < min_rel:
        eligible = False
        reasons.append(f"Raise reliability to {min_rel} (currently {rel}) — perform well and work consistently")
    if p.get("legal_reputation", 100) < req.get("min_legal_reputation", 35):
        eligible = False
        reasons.append("Your criminal record is blocking advancement")
    boss = await db.contacts.find_one({"player_id": p["id"], "key": "boss"}, {"_id": 0})
    boss_rel = round(boss.get("relationship_score", 0)) if boss else 0
    if boss_rel < req.get("min_boss_rel", -40):
        eligible = False
        reasons.append("Your manager won't endorse you — improve your relationship first")
    return {"need_hours": need_h, "have_hours": have_h, "hours_met": have_h >= need_h,
            "eligible": eligible, "reasons": reasons, "requirements": req,
            "reliability": rel, "boss_rel": boss_rel}


def decorate_employment(e):
    """Add hourly-wage fallback + hours-based raise eligibility to a player_employment doc."""
    if e.get("wage_per_hour") is None:
        e["wage_per_hour"] = round(e.get("wage_per_shift", 60) / 4.0, 2)
    if not e.get("schedule"):
        e["schedule"] = employment.make_schedule("early")
    worked = e.get("total_hours_worked", 0)
    last = e.get("hours_at_last_raise", 0)
    e["raise_due"] = (worked - last) >= RAISE_INTERVAL_HOURS
    e["hours_to_next_raise"] = max(0, round(RAISE_INTERVAL_HOURS - (worked - last), 1))
    return e


def decorate_employment_live(e, cfg, g_now):
    """decorate_employment + live on-shift status for the employee's own views."""
    de = decorate_employment(e)
    de["on_shift"] = employment.emp_on_shift(e, g_now)
    wb = employment.current_window_bounds(e.get("schedule") or {}, g_now)
    de["window_ends_at_game"] = wb[1].isoformat() if (de["on_shift"] and wb) else None
    return de


def ensure_free(p):
    if p.get("status") == "jail":
        raise HTTPException(status_code=409, detail="You are in jail. Wait it out or post bail.")
    if p.get("status") == "hospital":
        raise HTTPException(status_code=409, detail="You are in hospital recovering.")
    os_shift = p.get("on_shift")
    if os_shift:
        raise HTTPException(status_code=409, detail=f"You're on shift at {os_shift.get('business_name', 'work')}. Clock out early first to do something else.")
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


async def net_worth_parts(p):
    """Transparent net-worth breakdown so the UI can explain where the number comes from."""
    cash = round(p["cash"], 2)
    bank = round(p["bank"], 2)
    debt = round(p["debt"], 2)
    vehicles = 0.0
    for v in p.get("vehicles", []):
        spec = v.get("spec", {})
        vehicles += spec.get("price", 0) * spec.get("resale", 0.5) * (v.get("condition", 100) / 100.0)
    prop = 0.0
    if (p.get("housing") or {}).get("owned"):
        hd = await db.housing.find_one({"id": p["housing"]["id"]}, {"_id": 0})
        if hd:
            prop = hd.get("buy_price", 0) * 0.5
    business = 0.0
    bizs = await db.businesses.find({"player_id": p["id"], "bankrupt": {"$ne": True}}, {"_id": 0}).to_list(100)
    for b in bizs:
        business += b.get("cash", 0) - b.get("debt", 0) + b.get("purchase_price", 0) * 0.5
    investments = await market_engine.portfolio_value(db, p)
    parts = {"cash": cash, "bank": bank, "debt": debt,
             "vehicles": round(vehicles, 2), "property": round(prop, 2), "business": round(business, 2),
             "investments": round(investments, 2)}
    parts["total"] = round(cash + bank - debt + vehicles + prop + business + investments, 2)
    return parts


async def compute_net_worth(p):
    return (await net_worth_parts(p))["total"]


async def estimate_income_per_day(p):
    """Rough steady daily income from a job + profitable businesses (used for creditworthiness)."""
    income = 0.0
    job = p.get("job")
    if job:
        wage = job.get("hourly_wage")
        if wage is None:
            jd = await db.jobs.find_one({"id": job.get("job_id")}, {"_id": 0, "hourly_wage": 1})
            wage = (jd or {}).get("hourly_wage", 0)
        income += (wage or 0) * 6  # ~6 productive hours/day
    bizs = await db.businesses.find({"player_id": p["id"], "bankrupt": {"$ne": True}}, {"_id": 0, "net_day": 1}).to_list(100)
    for b in bizs:
        income += max(0, b.get("net_day", 0))
    return round(income, 2)


async def credit_profile(p, cfg=None):
    """Compute a player's TOTAL credit limit, used credit (debt) and AVAILABLE new credit.

    The limit is derived from net worth, income, finance skill, job stability, reputation and
    record. Because net worth already subtracts debt, taking a loan (bank +amt, debt +amt)
    leaves net worth unchanged -> the limit does NOT grow when borrowing, so loans cannot be
    stacked to exceed the cap.
    """
    cfg = cfg or await get_config(db)
    econ = cfg.get("economy", {})
    interest = econ.get("loan_interest_daily", 0.015)
    nw = await compute_net_worth(p)
    income = await estimate_income_per_day(p)
    fin = p["skills"].get("finance", {}).get("level", 1)
    debt = round(p.get("debt", 0), 2)
    missed = int(p.get("credit_missed", 0))

    base = 500.0
    skill_c = fin * 250.0
    asset_c = max(0.0, nw) * 0.6
    income_c = income * 30 * 0.8
    job = p.get("job")
    job_c = (job.get("reliability", 50) / 100.0) * 500.0 if job else 0.0
    raw = base + skill_c + asset_c + income_c + job_c

    reasons = []
    rep_factor = clamp(0.6 + (p.get("reputation", 50) - 50) / 150.0 + (p.get("legal_reputation", 100) - 50) / 200.0, 0.3, 1.4)
    raw *= rep_factor
    if p.get("reputation", 50) < 45:
        reasons.append("low reputation")
    if not job and income <= 0:
        raw *= 0.6
        reasons.append("no steady income")

    blocked = False
    legal = p.get("legal_reputation", 100)
    if legal < 40:
        raw *= 0.5
        reasons.append("criminal record")
    if legal < 25:
        blocked = True
        reasons.append("serious criminal record — credit frozen")
    if missed > 0:
        raw *= max(0.3, 1 - 0.12 * missed)
        reasons.append(f"{missed} missed payment(s)")

    limit = round(max(0.0, raw))
    if blocked:
        limit = min(limit, int(debt))
    available = round(max(0.0, limit - debt), 2)
    return {
        "cash": round(p["cash"], 2), "bank": round(p["bank"], 2), "debt": debt,
        "interest_daily": interest,
        "credit_limit": limit, "credit_used": debt, "credit_available": available,
        "blocked": blocked, "reasons": reasons,
        "net_worth": nw, "income_per_day": income,
        "daily_interest_cost": round(debt * interest, 2),
        "factors": {"base": round(base), "finance_skill": round(skill_c), "assets": round(asset_c),
                    "income": round(income_c), "job_stability": round(job_c), "reputation_factor": round(rep_factor, 2)},
    }


async def get_state(user):
    p = await fetch_raw_player(user["id"])
    await resolve_player(db, p)
    p["net_worth"] = await compute_net_worth(p)
    p["last_seen"] = now_utc().isoformat()
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
        "net_worth_breakdown": await net_worth_parts(p),
        "time_scale": cfg["time_scale"],
        "effectiveness": round(effectiveness(p), 2),
        "game_time": game_now(cfg).isoformat(),
        "world_start_real": cfg.get("world_start_real"),
        "world_start_game": cfg.get("world_start_game"),
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
    jd = await db.jobs.find_one({"id": p["job"]["job_id"]}, {"_id": 0}) if p.get("job") else None
    npc = None
    if p.get("job"):
        promo = None
        if jd and jd.get("promotion_to"):
            target = await db.jobs.find_one({"id": jd["promotion_to"]}, {"_id": 0})
            ev = await evaluate_promotion(p, jd)
            promo = {"target": target, **ev}
        npc = {"job": p["job"], "details": jd, "promotion": promo}
    pe = await db.player_employment.find({"employee_player_id": p["id"], "status": "active"}, {"_id": 0}).to_list(50)
    cfg = await get_config(db)
    g_now = game_now(cfg, now_utc())
    player_jobs = [decorate_employment_live(e, cfg, g_now) for e in pe]
    return {"npc": npc, "player_jobs": player_jobs,
            "job": p.get("job"), "details": jd, "promotion": (npc or {}).get("promotion") if npc else None}


class ApplyBody(BaseModel):
    message: Optional[str] = None


@api.post("/jobs/{job_id}/apply")
async def apply_job(job_id: str, body: ApplyBody = ApplyBody(), user: dict = Depends(current_user)):
    p = await get_state(user)
    j = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    ok, reason = meets_requirements(p, j.get("requirements"))
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    if p["legal_reputation"] < 25:
        raise HTTPException(status_code=403, detail="Your criminal record blocks this application.")
    existing = await db.applications.find_one({"player_id": p["id"], "job_id": job_id, "status": {"$in": ["pending", "accepted"]}}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="You already have an active application for this job.")
    cfg = await get_config(db)
    delay = employment.application_delay_minutes(j, cfg)
    now = now_utc()
    app = {"id": uuid.uuid4().hex, "player_id": p["id"], "job_id": job_id, "title": j["title"],
           "status": "pending", "submitted_at": now.isoformat(),
           "resolves_at": (now + timedelta(seconds=real_seconds(delay, cfg["time_scale"]))).isoformat(),
           "message": body.message, "wage_offer": None, "reason": None, "resolved": False}
    await db.applications.insert_one({**app})
    await add_event(db, p["id"], f"You applied for {j['title']}. A decision is expected in about {delay} minutes.", "job", "info")
    return {"ok": True, "resolves_in_minutes": delay}


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
        "job_id": j["id"], "title": j["title"], "hours": body.hours, "category": j.get("category"),
        "hourly_wage": p["job"].get("hourly_wage", j["hourly_wage"]), "fatigue_ph": j["fatigue_per_hour"],
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
    ev = await evaluate_promotion(p, jd)
    if not ev["eligible"]:
        raise HTTPException(status_code=400, detail="; ".join(ev["reasons"]) or "Not eligible for promotion yet")
    target = await db.jobs.find_one({"id": jd["promotion_to"]}, {"_id": 0})
    p["job"] = {"job_id": target["id"], "title": target["title"], "shifts_worked": 0, "hours_worked": 0,
                "reliability": 60, "hired_at": now_utc().isoformat()}
    p["reputation"] = clamp(p["reputation"] + 6)
    p["social_status"] = clamp(p["social_status"] + 5)
    await add_event(db, p["id"], f"Promoted to {target['title']}! Bigger paycheck ahead.", "job", "success")
    await save_player(p)
    await social_engine.ensure_job_contacts(db, p, target)
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


@api.get("/shop/stores")
async def shop_stores(user: dict = Depends(current_user)):
    await get_state(user)
    shops = await db.city_shops.find({"active": True}, {"_id": 0}).to_list(100)
    shops.sort(key=lambda s: (s.get("order", 99), s.get("name", "")))
    counts = {}
    for it in await db.items.find({}, {"_id": 0, "store_type": 1}).to_list(300):
        counts[it.get("store_type")] = counts.get(it.get("store_type"), 0) + 1
    btypes = {b["id"]: b["name"] for b in await db.business_types.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(100)}
    for s in shops:
        s["item_count"] = counts.get(s.get("category"), 0)
        s["business_type_name"] = btypes.get(s.get("business_type_id"))
    return shops


@api.get("/shop/stores/{store_id}/items")
async def shop_store_items(store_id: str, user: dict = Depends(current_user)):
    await get_state(user)
    shop = await db.city_shops.find_one({"id": store_id, "active": True}, {"_id": 0})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    items = await db.items.find({"store_type": shop.get("category")}, {"_id": 0}).to_list(200)
    items.sort(key=lambda x: x["name"])
    return {"shop": shop, "items": items}


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
    p.setdefault("inventory", {})
    p["inventory"][body.item_id] = p["inventory"].get(body.item_id, 0) + qty
    await add_event(db, p["id"], f"Bought {qty}x {it['name']} for ${total} — added to your inventory.", "shop", "info")
    await save_player(p)
    return {"ok": True}


@api.get("/inventory")
async def get_inventory(user: dict = Depends(current_user)):
    p = await get_state(user)
    inv = p.get("inventory") or {}
    equipment = p.get("equipment") or {}
    equipped_ids = {v for v in equipment.values() if v}
    items = await db.items.find({"id": {"$in": list(inv.keys())}}, {"_id": 0}).to_list(200) if inv else []
    by_id = {it["id"]: it for it in items}
    out = []
    for iid, qty in inv.items():
        it = by_id.get(iid)
        if not it or qty <= 0:
            continue
        out.append({**it, "qty": qty,
                    "usable": it.get("category") == "consumable",
                    "equippable": bool(it.get("slot")),
                    "equipped": iid in equipped_ids})
    return sorted(out, key=lambda x: x["name"])


EQUIP_SLOTS = {
    "outfit": {"label": "Outfit"},
    "accessory": {"label": "Accessory"},
    "phone": {"label": "Phone"},
    "computer": {"label": "Computer"},
    "work_gear": {"label": "Work / Fitness Gear"},
}


async def _recompute_equip_bonus(p):
    """Aggregate passive bonuses from all equipped items: floors take max, *_mult multiply, rest sum."""
    equipment = p.get("equipment") or {}
    ids = [iid for iid in equipment.values() if iid]
    bonus = {}
    if ids:
        items = await db.items.find({"id": {"$in": ids}}, {"_id": 0}).to_list(50)
        for it in items:
            for k, v in (it.get("equip") or {}).items():
                if k.endswith("_floor"):
                    bonus[k] = max(bonus.get(k, 0), v)
                elif k.endswith("_mult"):
                    bonus[k] = round(bonus.get(k, 1.0) * v, 4)
                else:
                    bonus[k] = round(bonus.get(k, 0) + v, 4)
    p["equip_bonus"] = bonus
    return bonus


@api.get("/equipment")
async def get_equipment(user: dict = Depends(current_user)):
    p = await get_state(user)
    eq = p.get("equipment") or {}
    ids = [i for i in eq.values() if i]
    items = await db.items.find({"id": {"$in": ids}}, {"_id": 0}).to_list(50) if ids else []
    by_id = {it["id"]: it for it in items}
    slots = [{"slot": sid, "label": meta["label"], "item": by_id.get(eq.get(sid))}
             for sid, meta in EQUIP_SLOTS.items()]
    return {"slots": slots, "bonuses": p.get("equip_bonus") or {}}


@api.post("/inventory/{item_id}/equip")
async def equip_item(item_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    inv = p.get("inventory") or {}
    if inv.get(item_id, 0) <= 0:
        raise HTTPException(status_code=400, detail="You don't own that item")
    it = await db.items.find_one({"id": item_id}, {"_id": 0})
    if not it or not it.get("slot"):
        raise HTTPException(status_code=400, detail="That item can't be equipped")
    p.setdefault("equipment", {})[it["slot"]] = item_id
    await _recompute_equip_bonus(p)
    await add_event(db, p["id"], f"You equipped {it['name']}.", "shop", "info")
    await save_player(p)
    return {"ok": True, "equipped": True, "slot": it["slot"]}


@api.post("/equipment/{slot}/unequip")
async def unequip_slot(slot: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    eq = p.get("equipment") or {}
    iid = eq.pop(slot, None)
    if iid:
        p["equipment"] = eq
        await _recompute_equip_bonus(p)
        it = await db.items.find_one({"id": iid}, {"_id": 0})
        await add_event(db, p["id"], f"You unequipped {(it or {}).get('name', 'an item')}.", "shop", "info")
        await save_player(p)
    return {"ok": True}


@api.post("/inventory/{item_id}/use")
async def use_item(item_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    inv = p.setdefault("inventory", {})
    if inv.get(item_id, 0) <= 0:
        raise HTTPException(status_code=400, detail="You don't have that item")
    it = await db.items.find_one({"id": item_id}, {"_id": 0})
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    if it.get("category") != "consumable":
        raise HTTPException(status_code=400, detail="This item is equipment — equip it instead of using it.")
    cfg = await get_config(db)
    eff = dict(it.get("effects", {}))
    skill_eff = {k: v for k, v in eff.items() if k in SKILLS}
    for k in skill_eff:
        eff.pop(k)
        add_skill_xp(p, k, skill_eff[k], cfg)
    apply_effects(p, eff)
    inv[item_id] = inv.get(item_id, 0) - 1
    if inv[item_id] <= 0:
        inv.pop(item_id, None)
    await add_event(db, p["id"], f"You used {it['name']}.", "shop", "success")
    await save_player(p)
    return {"ok": True}


# ============================ BANK ============================
class AmountBody(BaseModel):
    amount: float


@api.get("/bank")
async def bank_info(user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    prof = await credit_profile(p, cfg)
    prof["max_loan"] = prof["credit_limit"]  # backwards-compat alias
    return prof


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
    prof = await credit_profile(p, cfg)
    amt = round(body.amount, 2)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")
    if prof["blocked"]:
        raise HTTPException(status_code=403, detail=f"Credit denied: {', '.join(prof['reasons']) or 'you are not eligible right now'}.")
    if amt > prof["credit_available"]:
        raise HTTPException(status_code=400,
                            detail=f"You can borrow up to ${round(prof['credit_available'])} more "
                                   f"(total limit ${prof['credit_limit']}, already used ${round(prof['debt'])}).")
    p["bank"] = round(p["bank"] + amt, 2)
    p["debt"] = round(p["debt"] + amt, 2)
    rate_pct = round(prof["interest_daily"] * 100, 2)
    await add_event(db, p["id"], f"Took a ${round(amt)} loan. Total debt now ${round(p['debt'])} at {rate_pct}%/day interest.", "finance", "warning")
    await add_notification(db, p["id"], "finance", "Loan approved",
                           f"${round(amt)} added to your bank. Total debt ${round(p['debt'])} ({rate_pct}%/day).", "info", "/bank")
    await save_player(p)
    new_prof = await credit_profile(p, cfg)
    return {"ok": True, "debt": p["debt"], "credit_limit": new_prof["credit_limit"],
            "credit_available": new_prof["credit_available"]}


@api.post("/bank/repay")
async def repay(body: AmountBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    amt = round(body.amount, 2)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")
    amt = min(amt, p["debt"])
    if amt <= 0:
        raise HTTPException(status_code=400, detail="You have no debt to repay")
    if p["cash"] + p["bank"] < amt:
        raise HTTPException(status_code=400, detail="Not enough money")
    charge(p, amt)
    p["debt"] = round(p["debt"] - amt, 2)
    if p["debt"] <= 0:
        p["debt"] = 0.0
        p["credit_missed"] = 0  # cleared the slate — restore creditworthiness
    await add_event(db, p["id"], f"Repaid ${round(amt)} of debt. Remaining debt ${round(p['debt'])}.", "finance", "success")
    await add_notification(db, p["id"], "finance", "Debt repaid", f"Repaid ${round(amt)}. Remaining debt ${round(p['debt'])}.", "success", "/bank")
    await save_player(p)
    return {"ok": True, "debt": p["debt"]}


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
    cur = p.get("housing") or {}
    if cur.get("id") == house_id and not cur.get("owned"):
        raise HTTPException(status_code=400, detail="You already rent this place")
    deposit = h.get("deposit", 0)
    refund = round(cur.get("deposit_paid", 0), 2) if (cur and not cur.get("owned")) else 0.0
    if p["cash"] + p["bank"] + refund < deposit:
        raise HTTPException(status_code=400, detail="Cannot afford the deposit")
    if refund > 0:
        add_money(p, refund)
        await add_event(db, p["id"], f"Deposit refunded from your old place: +${round(refund)}.", "housing", "success")
    charge(p, deposit)
    p["housing"] = {"id": house_id, "owned": False, "since": now_utc().isoformat(), "deposit_paid": deposit}
    await add_event(db, p["id"], f"You moved into {h['name']} (renting). Deposit ${round(deposit)} paid.", "housing", "success")
    await save_player(p)
    await social_engine.ensure_landlord(db, p, h)
    return {"ok": True, "refunded": refund}


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
    cur = p.get("housing") or {}
    refund = round(cur.get("deposit_paid", 0), 2) if (cur and not cur.get("owned")) else 0.0
    if refund > 0:
        add_money(p, refund)
        await add_event(db, p["id"], f"Deposit refunded from your old rental: +${round(refund)}.", "housing", "success")
    p["housing"] = {"id": house_id, "owned": True, "since": now_utc().isoformat()}
    p["social_status"] = clamp(p["social_status"] + h.get("social_status", 0) * 0.2)
    await add_event(db, p["id"], f"You bought {h['name']}! No more rent.", "housing", "success")
    await save_player(p)
    return {"ok": True, "refunded": refund}


@api.post("/housing/move-out")
async def move_out(user: dict = Depends(current_user)):
    p = await get_state(user)
    cur = p.get("housing") or {}
    if not cur.get("id"):
        raise HTTPException(status_code=400, detail="You have no home to move out of")
    if cur.get("owned"):
        raise HTTPException(status_code=400, detail="You own this property — sell it instead")
    refund = round(cur.get("deposit_paid", 0), 2)
    if refund > 0:
        add_money(p, refund)
        await add_event(db, p["id"], f"You moved out. Deposit refunded: +${round(refund)}.", "housing", "success")
    else:
        await add_event(db, p["id"], "You moved out and are between homes.", "housing", "info")
    p["housing"] = {}
    await save_player(p)
    return {"ok": True, "refunded": refund}


@api.post("/housing/sell")
async def sell_property(user: dict = Depends(current_user)):
    p = await get_state(user)
    cur = p.get("housing") or {}
    if not cur.get("owned"):
        raise HTTPException(status_code=400, detail="You don't own a property to sell")
    h = await db.housing.find_one({"id": cur["id"]}, {"_id": 0})
    if not h:
        raise HTTPException(status_code=404, detail="Property not found")
    value = round(h.get("buy_price", 0) * 0.6)
    add_money(p, value)
    p["housing"] = {}
    await add_event(db, p["id"], f"You sold {h['name']} for ${value} (60% of purchase price).", "housing", "success")
    await save_player(p)
    return {"ok": True, "value": value}


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
def _estimate_market_pnl(t, reqs, roles):
    """Level-1 P&L estimate for an UNOWNED business: ONE NPC worker covering the FULL
    opening-hours window (coverage-based production), at a representative reputation."""
    recipe = t.get("recipe") or []
    mc = round(sum(r.get("qty", 1) * r.get("cost", 0) for r in recipe), 2)
    price = (t.get("product") or {}).get("price", 0) or 0
    pph = t.get("production_per_worker_hour", 0) or 0
    open_hours = employment.open_hours_total(t.get("opening_hours"))
    SAT = 0.9775  # representative team morale (satisfaction ~85)
    capacity = pph * open_hours * SAT  # one worker covering the whole opening window
    demand = (t.get("daily_demand", 0) or 0) * 0.85  # rep ~70, no marketing, level 1
    sold = min(capacity, demand)
    if reqs:
        rd = roles.get(reqs[0]["role"], {})
        hourly = ((rd.get("wage_min", 80) + rd.get("wage_max", 120)) / 2.0) / 8.0
    else:
        hourly = 12.0
    wages = round(open_hours * hourly, 2)
    rev = round(sold * price, 2)
    material = round(sold * mc, 2)
    return {
        "product": t.get("product") or {}, "material_cost_per_unit": mc, "margin_per_unit": round(price - mc, 2),
        "sold_day": round(sold, 1), "demand_day": round(demand, 1),
        "revenue_day": rev, "material_day": material, "wage_day": wages,
        "profit_day": round(rev - material - wages, 2),
        "open_hours": open_hours, "opening_hours": t.get("opening_hours") or {"open": "08:00", "close": "20:00"},
        "staff_needed": [{"role": r["role"], "recommended": r.get("recommended", 1)} for r in reqs],
    }


@api.get("/businesses/market")
async def business_market(user: dict = Depends(current_user)):
    p = await get_state(user)
    types = await db.business_types.find({}, {"_id": 0}).to_list(100)
    staffing = {s["id"]: s.get("requirements", []) for s in await db.staffing_requirements.find({}, {"_id": 0}).to_list(100)}
    roles = {r["id"]: r for r in await db.employee_roles.find({}, {"_id": 0}).to_list(100)}
    out = []
    for t in types:
        ok, reason = meets_requirements(p, t.get("requirements"))
        out.append({**t, "qualified": ok, "reason": reason,
                    "estimate": _estimate_market_pnl(t, staffing.get(t["id"], []), roles)})
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
    now = now_utc()
    recipe = t.get("recipe") or []
    restock_target = t.get("daily_demand", 0)
    materials = {r["id"]: round(restock_target * r.get("qty", 1), 3) for r in recipe}  # starting inventory
    biz = {
        "id": uuid.uuid4().hex, "player_id": p["id"], "type_id": type_id, "name": t["name"],
        "category": t.get("category", ""), "purchase_price": t["purchase_price"],
        "max_level": t.get("max_level", 5), "level": 1, "marketing_level": 0, "reputation": 50.0,
        "opening_hours": t.get("opening_hours") or {"open": "08:00", "close": "20:00"},
        # supply chain
        "product": t.get("product") or {}, "recipe": recipe,
        "production_per_worker_hour": t.get("production_per_worker_hour", 0),
        "daily_demand": t.get("daily_demand", 0), "materials": materials, "products": 0.0,
        "restock_target": restock_target, "auto_restock": True,
        "cash": 0.0, "debt": 0.0, "revenue_total": 0.0,
        "rev_day": 0.0, "material_day": 0.0, "wages_day": 0.0, "net_day": 0.0, "exp_day": 0.0,
        "demand_day": 0.0, "produced_day": 0.0, "sold_day": 0.0,
        "bankrupt": False, "history": [], "created_at": now.isoformat(), "last_resolved_at": now.isoformat(),
        "satisfaction": 80.0, "last_applicant_at": now.isoformat(), "morale_avg": 0, "hiring_open": False,
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
    if b.get("activity"):
        raise HTTPException(status_code=400, detail=f"A {b['activity']['type']} is already in progress here")
    cost = round(b["purchase_price"] * 0.4 * b["level"])
    if p["cash"] + p["bank"] < cost:
        raise HTTPException(status_code=400, detail=f"Upgrade costs ${cost}")
    charge(p, cost)
    cfg = await get_config(db)
    now = now_utc()
    dur_days = int((cfg.get("tuning") or {}).get("upgrade_days", 7))
    ends = now + timedelta(seconds=real_seconds(dur_days * 1440, cfg["time_scale"]))
    activity = {"type": "upgrade", "started_at": now.isoformat(), "ends_at": ends.isoformat(),
                "duration_days": dur_days, "completed": False}
    await db.businesses.update_one({"id": biz_id}, {"$set": {"activity": activity}})
    await add_event(db, p["id"], f"Started upgrading {b['name']} (~{dur_days} in-game days). Income is cut 50% during construction; +1 level & staff slot when it's done.", "business", "info", biz_id)
    await save_player(p)
    return {"ok": True, "cost": cost, "activity": activity}


@api.post("/businesses/{biz_id}/marketing")
async def marketing_business(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    if b.get("bankrupt"):
        raise HTTPException(status_code=400, detail="This business is bankrupt")
    if b.get("activity"):
        raise HTTPException(status_code=400, detail=f"A {b['activity']['type']} is already in progress here")
    cost = round(b["purchase_price"] * 0.12 * (b.get("marketing_level", 0) + 1))
    if p["cash"] + p["bank"] < cost:
        raise HTTPException(status_code=400, detail=f"Marketing campaign costs ${cost}")
    charge(p, cost)
    cfg = await get_config(db)
    now = now_utc()
    dur_days = int((cfg.get("tuning") or {}).get("marketing_days", 3))
    ends = now + timedelta(seconds=real_seconds(dur_days * 1440, cfg["time_scale"]))
    activity = {"type": "marketing", "started_at": now.isoformat(), "ends_at": ends.isoformat(),
                "duration_days": dur_days, "completed": False}
    await db.businesses.update_one({"id": biz_id}, {"$set": {"activity": activity}})
    await add_event(db, p["id"], f"Launched a marketing campaign for {b['name']} (~{dur_days} in-game days to roll out). The demand & price boost applies when it completes.", "business", "info", biz_id)
    await save_player(p)
    return {"ok": True, "cost": cost, "activity": activity}


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


class RenameBody(BaseModel):
    name: str


class MaterialsBody(BaseModel):
    units: Optional[float] = None  # product-equivalent units to top up to (defaults to restock target)


class RestockBody(BaseModel):
    auto_restock: Optional[bool] = None
    restock_target: Optional[float] = None


@api.post("/businesses/{biz_id}/rename")
async def rename_business(biz_id: str, body: RenameBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    await _get_owned_business(p, biz_id)
    name = (body.name or "").strip()
    if not (2 <= len(name) <= 40):
        raise HTTPException(status_code=400, detail="Name must be 2–40 characters")
    await db.businesses.update_one({"id": biz_id}, {"$set": {"name": name}})
    await db.player_employment.update_many({"business_id": biz_id}, {"$set": {"business_name": name}})
    await db.business_applications.update_many({"business_id": biz_id}, {"$set": {"business_name": name}})
    return {"ok": True, "name": name}


@api.post("/businesses/{biz_id}/restock-settings")
async def restock_settings(biz_id: str, body: RestockBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    await _get_owned_business(p, biz_id)
    upd = {}
    if body.auto_restock is not None:
        upd["auto_restock"] = bool(body.auto_restock)
    if body.restock_target is not None:
        upd["restock_target"] = max(0.0, round(body.restock_target, 1))
    if upd:
        await db.businesses.update_one({"id": biz_id}, {"$set": upd})
    return {"ok": True, **upd}


@api.post("/businesses/{biz_id}/buy-materials")
async def buy_materials(biz_id: str, body: MaterialsBody, user: dict = Depends(current_user)):
    """Top up ingredient stock to `units` product-equivalents. Paid from business cash;
    if the business is short, the owner's wallet covers the rest."""
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    recipe = b.get("recipe") or []
    if not recipe:
        raise HTTPException(status_code=400, detail="This business has no supply chain")
    target = body.units if body.units is not None else b.get("restock_target", b.get("daily_demand", 0))
    target = max(0.0, round(target, 1))
    materials = b.get("materials") or {}
    cost = 0.0
    new_mats = dict(materials)
    for r in recipe:
        want = target * r.get("qty", 1)
        have = materials.get(r["id"], 0)
        if want > have:
            cost += (want - have) * r.get("cost", 0)
            new_mats[r["id"]] = round(want, 3)
    cost = round(cost, 2)
    if cost <= 0:
        return {"ok": True, "cost": 0, "detail": "Already stocked to target"}
    biz_cash = round(b.get("cash", 0), 2)
    from_biz = min(biz_cash, cost)
    from_owner = round(cost - from_biz, 2)
    if from_owner > 0 and (p["cash"] + p["bank"]) < from_owner:
        raise HTTPException(status_code=400, detail=f"Need ${cost} to restock (business has ${biz_cash}); you can't cover the rest")
    if from_owner > 0:
        charge(p, from_owner)
        await save_player(p)
    await db.businesses.update_one({"id": biz_id}, {"$set": {"materials": new_mats, "cash": round(biz_cash - from_biz, 2)}})
    await add_event(db, p["id"], f"Restocked materials at {b['name']} for ${cost}.", "business", "info", biz_id)
    return {"ok": True, "cost": cost, "from_business": from_biz, "from_owner": from_owner}


# ============================ ILLEGAL / LEGAL ============================
UW_MIN_SCORE = 40
UW_MIN_TRUST = 30


async def underworld_access(p):
    """Underworld is gated behind knowing & being trusted by a criminal contact (Socials 3.0)."""
    trusted = await db.contacts.find_one(
        {"player_id": p["id"], "relationship_type": "shady_contact",
         "relationship_score": {"$gte": UW_MIN_SCORE}, "trust": {"$gte": UW_MIN_TRUST}},
        {"_id": 0, "name": 1})
    if trusted:
        return True, None, trusted["name"]
    any_shady = await db.contacts.find_one(
        {"player_id": p["id"], "relationship_type": "shady_contact"}, {"_id": 0, "name": 1})
    if any_shady:
        return (False, f"You know {any_shady['name']}, but they don't trust you enough yet. "
                       f"Meet up and build the bond to Trust {UW_MIN_TRUST}+ and Relationship {UW_MIN_SCORE}+.", None)
    return (False, "You have no way in. Meet a Shady Contact first — Social ▸ Meet People ▸ Prowl the Backstreets.", None)


def _effective_crime_risk(p, a, risk_mult=1.0):
    """Mirror game_engine._resolve_illegal so the UI shows the true, live odds."""
    street = p.get("skills", {}).get("street_smarts", {}).get("level", 1)
    susp = p.get("criminal_suspicion", 0)
    bust = a.get("police_risk", 0) * (1 + susp / 150.0) * (1 - min(0.4, street * 0.03)) * risk_mult
    fail = a.get("failure_chance", 0) * (1 - min(0.3, street * 0.025))
    bust = max(0.0, min(0.95, bust))
    fail = max(0.0, min(0.95 - bust, fail))
    return round(bust, 3), round(fail, 3)


@api.get("/underworld/status")
async def underworld_status(user: dict = Depends(current_user)):
    p = await get_state(user)
    access, reason, contact = await underworld_access(p)
    return {"access": access, "reason": reason, "contact": contact,
            "criminal_suspicion": p.get("criminal_suspicion", 0),
            "min_score": UW_MIN_SCORE, "min_trust": UW_MIN_TRUST}


@api.get("/illegal-actions")
async def list_illegal(user: dict = Depends(current_user)):
    p = await get_state(user)
    access, reason, _ = await underworld_access(p)
    if not access:
        return {"access": False, "reason": reason, "actions": []}
    buff = p.get("social_buffs", {})
    until = parse_dt(buff.get("until")) if buff.get("until") else None
    risk_mult = buff["crime_risk_mult"] if (buff.get("crime_risk_mult") and until and until > now_utc()) else 1.0
    acts = await db.illegal_actions.find({}, {"_id": 0}).to_list(100)
    out = []
    for a in acts:
        ok, rsn = meets_requirements(p, a.get("requirements"))
        bust, fail = _effective_crime_risk(p, a, risk_mult)
        out.append({**a, "available": ok, "reason": rsn, "bust_risk": bust, "fail_chance": fail})
    return {"access": True, "reason": None, "actions": out}


@api.post("/illegal-actions/{action_id}/commit")
async def commit_illegal(action_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    ensure_free(p)
    access, reason, _ = await underworld_access(p)
    if not access:
        raise HTTPException(status_code=403, detail=reason)
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
    buff = p.get("social_buffs", {})
    until = parse_dt(buff.get("until")) if buff.get("until") else None
    if buff.get("crime_risk_mult") and until and until > now_utc():
        payload["risk_mult"] = buff["crime_risk_mult"]
    set_activity(p, "illegal", a["name"], a["duration_minutes"], cfg, payload, blocking=a.get("blocking", True))
    await add_event(db, p["id"], f"You started something risky: {a['name']}...", "crime", "warning")
    await save_player(p)
    return {"ok": True, "activity": serialize_activity(p)}


# ---------------- FINANCIAL MARKETS: stocks (open) + crypto (Underworld-gated) ----------------
class TradeBody(BaseModel):
    asset_id: str
    qty: float


async def _do_trade(p, asset_id, qty, side):
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")
    asset = await db.market_assets.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset["kind"] == "crypto":
        access, reason, _ = await underworld_access(p)
        if not access:
            raise HTTPException(status_code=403, detail=reason)
    price = float(asset["price"])
    port = p.setdefault("portfolio", {})
    h = port.get(asset_id, {"qty": 0.0, "avg_cost": price})
    if side == "buy":
        cost = round(price * qty, 2)
        if p["cash"] < cost:
            raise HTTPException(status_code=400, detail=f"Not enough cash (need ${cost:,.2f})")
        new_qty = h["qty"] + qty
        h["avg_cost"] = round((h["qty"] * h.get("avg_cost", price) + qty * price) / new_qty, 6)
        h["qty"] = new_qty
        charge(p, cost)
        port[asset_id] = h
        await add_event(db, p["id"], f"Bought {qty:g} {asset['symbol']} @ ${price:,.2f} (${cost:,.2f}).", "bank", "info")
    else:
        if h["qty"] < qty - 1e-9:
            raise HTTPException(status_code=400, detail=f"You only hold {h['qty']:g} {asset['symbol']}")
        proceeds = round(price * qty, 2)
        h["qty"] = round(h["qty"] - qty, 8)
        add_money(p, proceeds)
        if h["qty"] <= 1e-9:
            port.pop(asset_id, None)
        else:
            port[asset_id] = h
        await add_event(db, p["id"], f"Sold {qty:g} {asset['symbol']} @ ${price:,.2f} (+${proceeds:,.2f}).", "bank", "success")
    p["net_worth"] = await compute_net_worth(p)
    await save_player(p)
    return {"ok": True, "price": price}


@api.get("/market/stocks")
async def market_stocks(user: dict = Depends(current_user)):
    await get_state(user)
    cfg = await get_config(db)
    return await market_engine.get_market(db, cfg, "stock")


@api.get("/market/crypto")
async def market_crypto(user: dict = Depends(current_user)):
    p = await get_state(user)
    access, reason, _ = await underworld_access(p)
    if not access:
        return {"access": False, "reason": reason, "assets": []}
    cfg = await get_config(db)
    return {"access": True, "reason": None, "assets": await market_engine.get_market(db, cfg, "crypto")}


@api.get("/market/portfolio")
async def market_portfolio(user: dict = Depends(current_user)):
    p = await get_state(user)
    return await market_engine.portfolio_view(db, p)


@api.post("/market/buy")
async def market_buy(body: TradeBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    return await _do_trade(p, body.asset_id, body.qty, "buy")


@api.post("/market/sell")
async def market_sell(body: TradeBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    return await _do_trade(p, body.asset_id, body.qty, "sell")


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
    ledger_add(p, "fines", -bail)
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
    ledger_add(p, "medical", -cost)
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
    return {"time_scale": cfg["time_scale"], "decay": cfg.get("decay", {}),
            "game_time": game_now(cfg).isoformat(),
            "world_start_real": cfg.get("world_start_real"),
            "world_start_game": cfg.get("world_start_game")}


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
                                         "legal_reputation": 1, "criminal_suspicion": 1, "social_status": 1,
                                         "health": 1, "energy": 1, "skills": 1,
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


# ---------------- ADMIN SANDBOX: business economy tuning ----------------
class BizEconomyBody(BaseModel):
    price: float | None = None
    material_cost: float | None = None
    daily_demand: float | None = None
    production_per_worker_hour: float | None = None
    base_hourly_wage: float | None = None
    opening_open: str | None = None
    opening_close: str | None = None
    apply_existing: bool = True


@api.get("/admin/business-economy")
async def admin_business_economy(admin: dict = Depends(admin_user)):
    out = []
    for t in await db.business_types.find({}, {"_id": 0}).to_list(100):
        out.append({
            "id": t["id"], "name": t.get("name"),
            "price": (t.get("product") or {}).get("price", 0),
            "material_cost": t.get("material_cost_override", round(sum(r.get("qty", 1) * r.get("cost", 0) for r in (t.get("recipe") or [])), 2)),
            "daily_demand": t.get("daily_demand", 0),
            "production_per_worker_hour": t.get("production_per_worker_hour", 0),
            "base_hourly_wage": t.get("base_hourly_wage"),
            "opening_hours": t.get("opening_hours") or {"open": "08:00", "close": "20:00"},
        })
    return out


@api.put("/admin/business-economy/{type_id}")
async def admin_update_business_economy(type_id: str, body: BizEconomyBody, admin: dict = Depends(admin_user)):
    t = await db.business_types.find_one({"id": type_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Unknown business type")
    tset, bset = {}, {}
    if body.price is not None:
        prod = t.get("product") or {}
        prod["price"] = round(body.price, 2)
        tset["product"] = prod
        bset["product"] = prod
    if body.material_cost is not None:
        tset["material_cost_override"] = round(body.material_cost, 2)
        bset["material_cost_override"] = round(body.material_cost, 2)
    if body.daily_demand is not None:
        tset["daily_demand"] = round(body.daily_demand, 2)
        bset["daily_demand"] = round(body.daily_demand, 2)
    if body.production_per_worker_hour is not None:
        tset["production_per_worker_hour"] = round(body.production_per_worker_hour, 3)
        bset["production_per_worker_hour"] = round(body.production_per_worker_hour, 3)
    if body.base_hourly_wage is not None:
        tset["base_hourly_wage"] = round(body.base_hourly_wage, 2)
        bset["base_hourly_wage"] = round(body.base_hourly_wage, 2)
    if body.opening_open and body.opening_close:
        o = employment.hhmm_to_float(body.opening_open)
        c = 24.0 if body.opening_close == "24:00" else employment.hhmm_to_float(body.opening_close)
        if not (0 <= o < c <= 24):
            raise HTTPException(status_code=400, detail="Opening must be before closing (00:00–24:00).")
        oh = {"open": employment.float_to_hhmm(o), "close": ("24:00" if c >= 24 else employment.float_to_hhmm(c))}
        tset["opening_hours"] = oh
        bset["opening_hours"] = oh
    if tset:
        await db.business_types.update_one({"id": type_id}, {"$set": tset})
    if bset and body.apply_existing:
        await db.businesses.update_many({"type_id": type_id}, {"$set": bset})
    return {"ok": True, "applied_to_existing": bool(bset and body.apply_existing)}


# ---------------- ADMIN SANDBOX: player management ----------------
class AdminPlayerBody(BaseModel):
    cash: float | None = None
    bank: float | None = None
    debt: float | None = None
    reputation: float | None = None
    legal_reputation: float | None = None
    criminal_suspicion: float | None = None
    social_status: float | None = None
    health: float | None = None
    energy: float | None = None
    skills: dict | None = None  # {skill_id: level}


@api.put("/admin/players/{player_id}")
async def admin_update_player(player_id: str, body: AdminPlayerBody, admin: dict = Depends(admin_user)):
    p = await db.players.find_one({"id": player_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Player not found")
    upd = {}
    for f in ["cash", "bank", "debt"]:
        v = getattr(body, f)
        if v is not None:
            upd[f] = round(float(v), 2)
    for f in ["reputation", "legal_reputation", "criminal_suspicion", "social_status", "health", "energy"]:
        v = getattr(body, f)
        if v is not None:
            upd[f] = clamp(float(v))
    if body.skills:
        skills = p.get("skills") or {}
        for sid, lvl in body.skills.items():
            if sid in skills:
                skills[sid]["level"] = max(1, int(lvl))
                skills[sid]["xp"] = 0
        upd["skills"] = skills
    if upd:
        await db.players.update_one({"id": player_id}, {"$set": upd})
    return {"ok": True, "updated": list(upd.keys())}


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
    pp = b.get("purchase_price", 1)
    lvl = b.get("level", 1)
    mkt = b.get("marketing_level", 0)
    rep = b.get("reputation", 50)
    can_upgrade = lvl < b.get("max_level", 1)
    activity = b.get("activity")
    costs = {
        "upgrade_cost": round(pp * 0.4 * lvl) if can_upgrade else None,
        "upgrade_from_level": lvl, "upgrade_to_level": lvl + 1 if can_upgrade else lvl,
        "upgrade_adds_slot": can_upgrade, "upgrade_reputation_gain": 4, "can_upgrade": can_upgrade,
        "upgrade_duration_days": 7,
        "marketing_cost": round(pp * 0.12 * (mkt + 1)),
        "marketing_level": mkt, "marketing_next_level": mkt + 1,
        "marketing_demand_boost_pct": 25, "marketing_price_boost_pct": 12, "marketing_reputation_gain": 8,
        "marketing_duration_days": 3,
        "activity_in_progress": bool(activity), "activity": activity,
        "sell_value": max(0, round(pp * 0.5 * lvl * (0.6 + 0.4 * rep / 100) - b.get("debt", 0) + b.get("cash", 0))),
    }
    return {"business": b, "metrics": await employee_engine.business_metrics(db, b), "costs": costs}


class OpeningHoursBody(BaseModel):
    open: str
    close: str


class ShiftBody(BaseModel):
    start: str
    end: str


@api.get("/businesses/{biz_id}/employees")
async def biz_employees(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    cfg = await get_config(db)
    tmap = {t["id"]: t for t in await db.employee_traits.find({}, {"_id": 0}).to_list(100)}
    emps = await db.employees.find({"business_id": biz_id, "status": {"$in": ["active", "sick"]}}, {"_id": 0}).sort("hire_date", 1).to_list(200)
    opening = b.get("opening_hours")
    for e in emps:
        e["projection"] = employment.npc_employee_projection(e, cfg, tmap, b)
        sh = e.get("schedule")
        e["hourly_wage"] = employee_engine.npc_hourly_wage(e)
        if sh:
            s_h, e_h = employment.shift_bounds(sh)
            e["shift_start"] = employment.float_to_hhmm(s_h)
            e["shift_end"] = employment.float_to_hhmm(e_h)
        else:
            e["shift_start"] = None
            e["shift_end"] = None
        e["shift_hours"] = employment.worker_shift_hours(sh, opening)
    return {"employees": emps, "metrics": await employee_engine.business_metrics(db, b)}


@api.patch("/businesses/{biz_id}/opening-hours")
async def set_opening_hours(biz_id: str, body: OpeningHoursBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    o = employment.hhmm_to_float(body.open)
    c = employment.hhmm_to_float(body.close)
    if body.close == "24:00":
        c = 24.0
    if not (0 <= o < c <= 24):
        raise HTTPException(status_code=400, detail="Opening time must be before closing time (00:00–24:00).")
    opening = {"open": employment.float_to_hhmm(o), "close": ("24:00" if c >= 24 else employment.float_to_hhmm(c))}
    await db.businesses.update_one({"id": biz_id}, {"$set": {"opening_hours": opening}})
    # clamp any worker shifts that now fall outside the new opening window (skip unscheduled)
    for e in await db.employees.find({"business_id": biz_id, "status": {"$in": ["active", "sick"]}}, {"_id": 0, "id": 1, "schedule": 1}).to_list(300):
        if not e.get("schedule"):
            continue
        s, e2 = employment.shift_bounds(e.get("schedule"))
        ns, ne = max(o, s), min(c, e2)
        if ne <= ns:
            ns, ne = o, c
        await db.employees.update_one({"id": e["id"]}, {"$set": {"schedule": employment.make_shift(ns, ne)}})
    return {"ok": True, "opening_hours": opening}


@api.patch("/businesses/{biz_id}/employees/{emp_id}/shift")
async def set_employee_shift(biz_id: str, emp_id: str, body: ShiftBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    emp = await db.employees.find_one({"id": emp_id, "business_id": biz_id, "status": {"$in": ["active", "sick"]}}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    o, c = employment.opening_bounds(b.get("opening_hours"))
    s = employment.hhmm_to_float(body.start)
    e = 24.0 if body.end == "24:00" else employment.hhmm_to_float(body.end)
    if e <= s:
        raise HTTPException(status_code=400, detail="Shift start must be before shift end.")
    if s < o - 1e-6 or e > c + 1e-6:
        raise HTTPException(status_code=400, detail=f"Shift must be within opening hours ({employment.float_to_hhmm(o)}–{employment.float_to_hhmm(c)}).")
    proposed = employment.make_shift(s, e)
    # concurrency limit: no more than `concurrent_slots` workers active in the same hour
    reqs = await employee_engine.get_staffing(db, b)
    concurrent_slots = max(1, sum(r.get("recommended", 1) for r in reqs)) + (b.get("level", 1) - 1)
    others = []
    for o_e in await db.employees.find({"business_id": biz_id, "status": {"$in": ["active", "sick"]}, "id": {"$ne": emp_id}}, {"_id": 0, "name": 1, "schedule": 1}).to_list(300):
        others.append((o_e["name"], o_e.get("schedule")))
    for pe in await db.player_employment.find({"business_id": biz_id, "status": "active"}, {"_id": 0, "employee_name": 1, "schedule": 1}).to_list(100):
        others.append((pe.get("employee_name") or "A player employee", pe.get("schedule")))
    peak = employment.peak_concurrent([sch for _, sch in others] + [proposed])
    if peak > concurrent_slots:
        clash = employment.find_overlapping(proposed, others) or "another worker"
        raise HTTPException(status_code=400, detail=f"Shift overlaps with {clash} — only {concurrent_slots} worker(s) can be active at the same time. Upgrade to add a slot, or pick non-overlapping hours.")
    await db.employees.update_one({"id": emp_id}, {"$set": {"schedule": proposed}})
    return {"ok": True, "schedule": proposed}


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
    b = await _get_owned_business(p, biz_id)
    m = await employee_engine.business_metrics(db, b)
    if m["staff_count"] >= m["max_hire_slots"]:
        raise HTTPException(status_code=400, detail=f"Staff limit reached ({m['staff_count']}/{m['max_hire_slots']}). You can hire up to {m['max_hire_slots']} workers to cover shifts.")
    sched_key = (emp.get("schedule") or {}).get("preset") or "early"
    wph = b.get("base_hourly_wage") or emp.get("wage_per_hour") or round(emp.get("daily_wage", 90) / 8.0, 2)
    # default shift: cover the largest currently-uncovered slice of opening hours
    existing = await db.employees.find({"business_id": biz_id, "status": "active"}, {"_id": 0, "schedule": 1}).to_list(300)
    pe_existing = await db.player_employment.find({"business_id": biz_id, "status": "active"}, {"_id": 0, "schedule": 1}).to_list(100)
    scheds = [x.get("schedule") for x in existing + pe_existing]
    shift = employment.first_uncovered_shift(b.get("opening_hours"), scheds)
    await db.employees.update_one({"id": emp_id}, {"$set": {
        "status": "active", "hire_date": now_utc().isoformat(), "last_paid": now_utc().isoformat(),
        "wage_per_hour": wph, "schedule": shift}})
    if shift:
        await add_event(db, p["id"], f"You hired {emp['name']} as {emp['role'].replace('_', ' ')} ({shift['label']}).", "business", "success", biz_id)
    else:
        await add_event(db, p["id"], f"You hired {emp['name']} as {emp['role'].replace('_', ' ')}. Opening hours are already covered — assign a shift in the Schedule tab (they cost $0 until scheduled).", "business", "info", biz_id)
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
        "daily_wage": new_wage, "wage_per_hour": round(new_wage / 8.0, 2), "wants_raise": False,
        "morale": clamp(emp.get("morale", 60) + 10), "loyalty": clamp(emp.get("loyalty", 50) + 6)}})
    await add_event(db, p["id"], f"You gave {emp['name']} a raise to ${round(new_wage / 8.0, 2)}/hr.", "business", "success", biz["id"])
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


# ============================ SOCIAL CONTACTS ============================
class InteractBody(BaseModel):
    action_id: str
    gift_id: Optional[str] = None


async def _get_contact(p, cid):
    c = await db.contacts.find_one({"id": cid, "player_id": p["id"]}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    return c


@api.get("/social/contacts")
async def social_contacts(user: dict = Depends(current_user)):
    p = await get_state(user)
    cs = await db.contacts.find({"player_id": p["id"]}, {"_id": 0}).sort("known_since", 1).to_list(400)
    views = [social_engine.contact_view(c) for c in cs]
    return {"contacts": views, "summary": social_engine.social_summary(views)}


@api.get("/social/gifts")
async def social_gifts(user: dict = Depends(current_user)):
    return await db.gift_types.find({}, {"_id": 0}).to_list(50)


@api.get("/social/discover-actions")
async def social_discover_actions(user: dict = Depends(current_user)):
    p = await get_state(user)
    acts = await db.relationship_actions.find({"untargeted": True}, {"_id": 0}).to_list(50)
    out = []
    for a in acts:
        cd = p.get("cooldowns", {}).get("social_" + a["id"])
        on_cd = cd and parse_dt(cd) > now_utc()
        out.append({**a, "available": not on_cd,
                    "cooldown_remaining": round((parse_dt(cd) - now_utc()).total_seconds()) if on_cd else 0})
    return out


@api.get("/social/contacts/{cid}")
async def social_contact_detail(cid: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    c = await _get_contact(p, cid)
    cfg = await get_config(db)
    return {
        "contact": social_engine.contact_view(c),
        "history": list(reversed(c.get("history", [])))[:40],
        "actions": await social_engine.actions_for_contact(db, p, c, cfg),
        "opportunities": social_engine.contact_opportunities(c),
        "warnings": social_engine.contact_warnings(c),
    }


@api.post("/social/contacts/{cid}/interact")
async def social_interact(cid: str, body: InteractBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    c = await _get_contact(p, cid)
    a = await db.relationship_actions.find_one({"id": body.action_id}, {"_id": 0})
    if not a or a.get("untargeted"):
        raise HTTPException(status_code=404, detail="Action not found")
    cfg = await get_config(db)
    ok, reason = social_engine.validate_action(p, c, a)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    gift = None
    if a.get("kind") == "give_gift":
        if not body.gift_id:
            raise HTTPException(status_code=400, detail="Choose a gift first")
        gift = await db.gift_types.find_one({"id": body.gift_id}, {"_id": 0})
        if not gift:
            raise HTTPException(status_code=404, detail="Gift not found")
    cd = c.get("cooldowns", {}).get(a["id"])
    if cd and parse_dt(cd) > now_utc():
        raise HTTPException(status_code=409, detail="That interaction is on cooldown")
    if gift is not None:
        if p["cash"] + p["bank"] < gift["cost"]:
            raise HTTPException(status_code=400, detail="You can't afford that gift")
        charge(p, gift["cost"])
        ledger_add(p, "living_costs", -gift["cost"])
    elif a.get("money_cost", 0) > 0:
        if p["cash"] + p["bank"] < a["money_cost"]:
            raise HTTPException(status_code=400, detail="Not enough money")
        charge(p, a["money_cost"])
        ledger_add(p, "living_costs", -a["money_cost"])

    if a.get("timing") == "activity":
        ensure_free(p)
        payload = {"action_id": a["id"], "contact_id": cid, "name": a["label"]}
        if gift:
            payload["gift"] = gift
        set_activity(p, "social", f"{a['label']} · {c['name']}", a["duration_minutes"], cfg, payload, blocking=a.get("blocking", True))
        await add_event(db, p["id"], f"You're spending time with {c['name']}: {a['label']}.", "social", "info")
        await save_player(p)
        return {"ok": True, "started": True, "activity": serialize_activity(p)}

    res = await social_engine.interact_now(db, p, cfg, c, a, gift)
    await save_player(p)
    return {"ok": True, **res}


@api.post("/social/discover/{action_id}")
async def social_discover(action_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    a = await db.relationship_actions.find_one({"id": action_id, "untargeted": True}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Action not found")
    ensure_free(p)
    cfg = await get_config(db)
    cdkey = "social_" + a["id"]
    cd = p.get("cooldowns", {}).get(cdkey)
    if cd and parse_dt(cd) > now_utc():
        raise HTTPException(status_code=409, detail="On cooldown")
    if a.get("money_cost", 0) > 0:
        if p["cash"] + p["bank"] < a["money_cost"]:
            raise HTTPException(status_code=400, detail="Not enough money")
        charge(p, a["money_cost"])
        ledger_add(p, "living_costs", -a["money_cost"])
    payload = {"action_id": a["id"], "name": a["label"]}
    set_activity(p, "social", a["label"], a["duration_minutes"], cfg, payload, blocking=a.get("blocking", True))
    cdm = a.get("cooldown_minutes", 0)
    if cdm > 0:
        p.setdefault("cooldowns", {})[cdkey] = (
            now_utc() + timedelta(seconds=real_seconds(a["duration_minutes"] + cdm, cfg["time_scale"]))).isoformat()
    await add_event(db, p["id"], f"You head out: {a['label']}.", "social", "info")
    await save_player(p)
    return {"ok": True, "activity": serialize_activity(p)}


# ---------------- DYNAMIC SOCIAL LOCATIONS & ENCOUNTERS (Socials 3.0) ----------------
async def _archetype_label_map():
    arch = await db.npc_archetypes.find(
        {}, {"_id": 0, "id": 1, "label": 1, "category": 1, "tags": 1,
             "social_status": 1, "legal_standing": 1, "wealth": 1}).to_list(200)
    return {a["id"]: a for a in arch}


def _loc_encounters(loc, amap):
    """Attach archetype labels + normalized meeting probabilities (manual + filtered) for transparency."""
    pool = social_engine.location_pool(loc, list(amap.values()))
    total = sum(max(0.0, n.get("weight", 0)) for n in pool) or 1.0
    out = []
    for n in pool:
        a = amap.get(n["archetype_id"], {})
        out.append({"archetype_id": n["archetype_id"], "label": a.get("label", n["archetype_id"]),
                    "weight": n.get("weight", 0), "source": n.get("source", "manual"),
                    "tags": a.get("tags", []),
                    "chance": round(max(0.0, n.get("weight", 0)) / total, 4)})
    out.sort(key=lambda x: x["chance"], reverse=True)
    return out


@api.get("/social/locations")
async def social_locations(user: dict = Depends(current_user)):
    p = await get_state(user)
    amap = await _archetype_label_map()
    locs = await db.locations.find({"active": True}, {"_id": 0}).to_list(100)
    locs.sort(key=lambda x: (x.get("order", 99), x.get("name", "")))
    out = []
    for loc in locs:
        cd = p.get("cooldowns", {}).get("loc_" + loc["id"])
        on_cd = cd and parse_dt(cd) > now_utc()
        blocked_reason = None
        if loc.get("requires_job") and not p.get("job"):
            blocked_reason = "Requires a job"
        elif on_cd:
            blocked_reason = "On cooldown"
        elif loc.get("money_cost", 0) > p["cash"] + p["bank"]:
            blocked_reason = "Can't afford"
        out.append({
            "id": loc["id"], "name": loc["name"], "category": loc.get("category"),
            "desc": loc.get("desc", ""), "icon": loc.get("icon", "MapPin"),
            "money_cost": loc.get("money_cost", 0), "duration_minutes": loc.get("duration_minutes", 60),
            "requires_job": loc.get("requires_job", False), "encounters": _loc_encounters(loc, amap),
            "available": blocked_reason is None, "reason": blocked_reason,
            "cooldown_remaining": round((parse_dt(cd) - now_utc()).total_seconds()) if on_cd else 0,
        })
    return out


@api.post("/social/visit/{location_id}")
async def social_visit(location_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    loc = await db.locations.find_one({"id": location_id, "active": True}, {"_id": 0})
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    ensure_free(p)
    if loc.get("requires_job") and not p.get("job"):
        raise HTTPException(status_code=400, detail="You need a job to go there.")
    cfg = await get_config(db)
    cdkey = "loc_" + loc["id"]
    cd = p.get("cooldowns", {}).get(cdkey)
    if cd and parse_dt(cd) > now_utc():
        raise HTTPException(status_code=409, detail="You were just there — give it some time.")
    cost = loc.get("money_cost", 0)
    if cost > 0:
        if p["cash"] + p["bank"] < cost:
            raise HTTPException(status_code=400, detail="Not enough money")
        charge(p, cost)
        ledger_add(p, "living_costs", -cost)
    payload = {"location_id": loc["id"], "name": loc["name"]}
    set_activity(p, "social", f"Visit {loc['name']}", loc.get("duration_minutes", 60), cfg, payload, blocking=True)
    cdm = loc.get("cooldown_minutes", 0)
    if cdm > 0:
        p.setdefault("cooldowns", {})[cdkey] = (
            now_utc() + timedelta(seconds=real_seconds(loc.get("duration_minutes", 60) + cdm, cfg["time_scale"]))).isoformat()
    await add_event(db, p["id"], f"You head out to {loc['name']}.", "social", "info")
    await save_player(p)
    return {"ok": True, "activity": serialize_activity(p)}


# ---- Admin: locations & encounters management ----
class LocationBody(BaseModel):
    name: str
    category: Optional[str] = "other"
    desc: Optional[str] = ""
    icon: Optional[str] = "MapPin"
    money_cost: Optional[float] = 0
    duration_minutes: Optional[int] = 60
    cooldown_minutes: Optional[int] = 120
    requires_job: Optional[bool] = False
    suspicion_gain: Optional[float] = 0
    success_base: Optional[float] = 0.72
    charisma_factor: Optional[float] = 0.3
    active: Optional[bool] = True
    order: Optional[int] = 50
    npcs: Optional[list] = None
    include_filtered: Optional[bool] = False
    category_whitelist: Optional[list] = None
    min_attrs: Optional[dict] = None
    max_attrs: Optional[dict] = None
    filter_weight: Optional[float] = 1.0


@api.get("/admin/locations")
async def admin_locations(admin: dict = Depends(admin_user)):
    amap = await _archetype_label_map()
    locs = await db.locations.find({}, {"_id": 0}).to_list(200)
    locs.sort(key=lambda x: (x.get("order", 99), x.get("name", "")))
    for loc in locs:
        loc["encounters"] = _loc_encounters(loc, amap)
    return {"locations": locs,
            "archetypes": sorted(amap.values(), key=lambda a: a.get("label", "")),
            "tag_options": seed_data.ARCHETYPE_TAG_OPTIONS,
            "attr_options": ["social_status", "legal_standing", "wealth"]}


def _clean_npcs(npcs):
    out = []
    for n in (npcs or []):
        aid = (n or {}).get("archetype_id")
        if not aid:
            continue
        try:
            w = max(0.0, float(n.get("weight", 1)))
        except (TypeError, ValueError):
            w = 1.0
        out.append({"archetype_id": aid, "weight": round(w, 4)})
    return out


def _clean_attrs(attrs):
    out = {}
    for k, v in (attrs or {}).items():
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            continue
    return out


@api.post("/admin/locations")
async def admin_create_location(body: LocationBody, admin: dict = Depends(admin_user)):
    loc = body.model_dump()
    loc["id"] = uuid.uuid4().hex
    loc["npcs"] = _clean_npcs(loc.get("npcs"))
    loc["category_whitelist"] = [t for t in (loc.get("category_whitelist") or []) if t]
    loc["min_attrs"] = _clean_attrs(loc.get("min_attrs"))
    loc["max_attrs"] = _clean_attrs(loc.get("max_attrs"))
    await db.locations.insert_one({**loc})
    return {"ok": True, "id": loc["id"]}


@api.put("/admin/locations/{location_id}")
async def admin_update_location(location_id: str, body: LocationBody, admin: dict = Depends(admin_user)):
    upd = body.model_dump()
    upd["npcs"] = _clean_npcs(upd.get("npcs"))
    upd["category_whitelist"] = [t for t in (upd.get("category_whitelist") or []) if t]
    upd["min_attrs"] = _clean_attrs(upd.get("min_attrs"))
    upd["max_attrs"] = _clean_attrs(upd.get("max_attrs"))
    await db.locations.update_one({"id": location_id}, {"$set": upd})
    return {"ok": True}


@api.delete("/admin/locations/{location_id}")
async def admin_delete_location(location_id: str, admin: dict = Depends(admin_user)):
    await db.locations.delete_one({"id": location_id})
    return {"ok": True}


# ---- Admin: City Shops management ----
class CityShopBody(BaseModel):
    name: str
    category: str = "grocery"
    desc: Optional[str] = ""
    icon: Optional[str] = "Store"
    business_type_id: Optional[str] = None
    location_id: Optional[str] = None
    active: Optional[bool] = True
    order: Optional[int] = 50


@api.get("/admin/city-shops")
async def admin_city_shops(admin: dict = Depends(admin_user)):
    shops = await db.city_shops.find({}, {"_id": 0}).to_list(200)
    shops.sort(key=lambda s: (s.get("order", 99), s.get("name", "")))
    counts = {}
    for it in await db.items.find({}, {"_id": 0, "store_type": 1}).to_list(300):
        counts[it.get("store_type")] = counts.get(it.get("store_type"), 0) + 1
    btypes = await db.business_types.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(100)
    locs = await db.locations.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(200)
    bmap = {b["id"]: b["name"] for b in btypes}
    for s in shops:
        s["item_count"] = counts.get(s.get("category"), 0)
        s["business_type_name"] = bmap.get(s.get("business_type_id"))
    return {"shops": shops, "category_options": seed_data.ITEM_CATEGORY_OPTIONS,
            "business_types": btypes, "locations": locs}


@api.post("/admin/city-shops")
async def admin_create_city_shop(body: CityShopBody, admin: dict = Depends(admin_user)):
    shop = body.model_dump()
    shop["id"] = uuid.uuid4().hex
    await db.city_shops.insert_one({**shop})
    return {"ok": True, "id": shop["id"]}


@api.put("/admin/city-shops/{shop_id}")
async def admin_update_city_shop(shop_id: str, body: CityShopBody, admin: dict = Depends(admin_user)):
    await db.city_shops.update_one({"id": shop_id}, {"$set": body.model_dump()})
    return {"ok": True}


@api.delete("/admin/city-shops/{shop_id}")
async def admin_delete_city_shop(shop_id: str, admin: dict = Depends(admin_user)):
    await db.city_shops.delete_one({"id": shop_id})
    return {"ok": True}



@api.post("/social/contacts/{cid}/block")
async def social_block(cid: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    c = await _get_contact(p, cid)
    if c.get("status") == "blocked":
        new_status = social_engine.derive_status({**c, "status": "active"})
        verb = "unblocked"
    else:
        new_status = "blocked"
        verb = "blocked"
    await db.contacts.update_one({"id": cid}, {"$set": {"status": new_status}})
    await add_event(db, p["id"], f"You {verb} {c['name']}.", "social", "warning" if verb == "blocked" else "info")
    return {"ok": True, "status": new_status}


# ============================ EMPLOYMENT: APPLICATIONS & PLAYER HIRING ============================
class MarketApplyBody(BaseModel):
    role: Optional[str] = None
    message: Optional[str] = None


class OfferBody(BaseModel):
    wage_per_hour: float
    role: Optional[str] = None
    schedule: Optional[str] = None


class BackupBody(BaseModel):
    role: str
    enabled: bool


class TrainingOfferBody(BaseModel):
    option_id: str
    skill: Optional[str] = None


class ProposeScheduleBody(BaseModel):
    schedule: str


class WageBody(BaseModel):
    wage_per_hour: float


async def _staffing_roles(b):
    reqs = await employee_engine.get_staffing(db, b)
    roles_doc = {r["id"]: r for r in await db.employee_roles.find({}, {"_id": 0}).to_list(100)}
    out = []
    for r in reqs:
        rd = roles_doc.get(r["role"], {})
        sp = employment.SHIFT_PRESETS["early"]
        out.append({"role": r["role"], "label": rd.get("label", r["role"].replace("_", " ").title()),
                    "desc": rd.get("desc", ""), "recommended": r.get("recommended", 1),
                    "suggested_wage": None, "schedule_preset": "early",
                    "schedule_label": sp["label"], "schedule_start": sp["start"], "schedule_end": sp["end"],
                    "open": True})
    return out


@api.get("/shift-presets")
async def shift_presets(user: dict = Depends(current_user)):
    return [{"preset": k, "label": v["label"], "start": v["start"], "end": v["end"]}
            for k, v in employment.SHIFT_PRESETS.items()]


# --- NPC applications (applicant) ---
@api.get("/jobs/applications")
async def my_applications(user: dict = Depends(current_user)):
    p = await get_state(user)
    apps = await db.applications.find({"player_id": p["id"]}, {"_id": 0}).sort("submitted_at", -1).to_list(60)
    for a in apps:
        if a["status"] == "pending":
            ra = parse_dt(a.get("resolves_at"))
            a["resolves_in"] = max(0, round((ra - now_utc()).total_seconds())) if ra else 0
    return apps


@api.post("/jobs/applications/{app_id}/accept")
async def accept_offer(app_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    a = await db.applications.find_one({"id": app_id, "player_id": p["id"]}, {"_id": 0})
    if not a or a["status"] != "accepted":
        raise HTTPException(status_code=400, detail="No active offer to accept")
    j = await db.jobs.find_one({"id": a["job_id"]}, {"_id": 0})
    if not j:
        raise HTTPException(status_code=404, detail="Job no longer exists")
    p["job"] = {"job_id": a["job_id"], "title": j["title"], "shifts_worked": 0, "hours_worked": 0, "reliability": 55,
                "hired_at": now_utc().isoformat(), "hourly_wage": a.get("wage_offer") or j["hourly_wage"]}
    await db.applications.update_one({"id": app_id}, {"$set": {"status": "hired"}})
    await db.applications.update_many({"player_id": p["id"], "status": {"$in": ["pending", "accepted"]}, "id": {"$ne": app_id}},
                                      {"$set": {"status": "withdrawn"}})
    await add_event(db, p["id"], f"You accepted the offer — now a {j['title']} at ${p['job']['hourly_wage']}/h.", "job", "success")
    await save_player(p)
    await social_engine.ensure_job_contacts(db, p, j)
    return {"ok": True}


@api.post("/jobs/applications/{app_id}/withdraw")
async def withdraw_application(app_id: str, user: dict = Depends(current_user)):
    p = await fetch_raw_player(user["id"])
    a = await db.applications.find_one({"id": app_id, "player_id": p["id"]}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Application not found")
    if a["status"] not in ("pending", "accepted"):
        raise HTTPException(status_code=400, detail="This application can't be withdrawn")
    await db.applications.update_one({"id": app_id}, {"$set": {"status": "withdrawn"}})
    return {"ok": True}


# --- Player job market (applicant) ---
@api.get("/jobs/market")
async def job_market(user: dict = Depends(current_user)):
    me = await db.players.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    cfg = await get_config(db)
    base = cfg.get("employment", {}).get("player_base_hourly_wage", 14)
    bizs = await db.businesses.find({"hiring_open": True, "bankrupt": {"$ne": True}}, {"_id": 0}).to_list(200)
    out = []
    for b in bizs:
        if me and b["player_id"] == me["id"]:
            continue
        owner = await db.players.find_one({"id": b["player_id"]}, {"_id": 0, "name": 1})
        t = await db.business_types.find_one({"id": b["type_id"]}, {"_id": 0, "name": 1, "category": 1})
        app = await db.business_applications.find_one(
            {"business_id": b["id"], "applicant_id": me["id"], "status": {"$in": ["pending", "offered"]}}, {"_id": 0}) if me else None
        emp = await db.player_employment.find_one(
            {"business_id": b["id"], "employee_player_id": me["id"], "status": "active"}, {"_id": 0}) if me else None
        out.append({"business_id": b["id"], "name": b["name"], "owner_name": owner["name"] if owner else "?",
                    "type": t["name"] if t else "", "category": t["category"] if t else "",
                    "reputation": round(b.get("reputation", 50)), "base_hourly_wage": base,
                    "roles": await _staffing_roles(b),
                    "my_status": "employed" if emp else (app["status"] if app else None)})
    return out


@api.post("/jobs/market/{business_id}/apply")
async def apply_to_business(business_id: str, body: MarketApplyBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await db.businesses.find_one({"id": business_id}, {"_id": 0})
    if not b or b.get("bankrupt") or not b.get("hiring_open"):
        raise HTTPException(status_code=400, detail="This business isn't hiring")
    if b["player_id"] == p["id"]:
        raise HTTPException(status_code=400, detail="You can't apply to your own business")
    if await db.business_applications.find_one({"business_id": business_id, "applicant_id": p["id"], "status": {"$in": ["pending", "offered"]}}, {"_id": 0}):
        raise HTTPException(status_code=409, detail="You already have an active application here")
    if await db.player_employment.find_one({"business_id": business_id, "employee_player_id": p["id"], "status": "active"}, {"_id": 0}):
        raise HTTPException(status_code=409, detail="You already work here")
    cfg = await get_config(db)
    reqs = await employee_engine.get_staffing(db, b)
    role_ids = [r["role"] for r in reqs]
    role = body.role if body.role in role_ids else (role_ids[0] if role_ids else "staff")
    snap = employment.applicant_snapshot(p, cfg, role, reqs)
    app = {"id": uuid.uuid4().hex, "business_id": business_id, "business_name": b["name"], "owner_id": b["player_id"],
           "applicant_id": p["id"], "applicant_name": p["name"], "role": role,
           "message": body.message, "status": "pending", "submitted_at": now_utc().isoformat(),
           "stats": snap, "recommended_wage": snap["recommended_wage"], "wage_offer": None}
    await db.business_applications.insert_one({**app})
    await add_notification(db, b["player_id"], "business", "New job applicant", f"{p['name']} applied to {b['name']} as {role.replace('_', ' ')}.", "info", f"/businesses/{business_id}")
    await add_event(db, p["id"], f"You applied to work at {b['name']} as {role.replace('_', ' ')}.", "job", "info")
    return {"ok": True}


@api.get("/jobs/employment")
async def my_employment(user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    g_now = game_now(cfg, now_utc())
    emps = await db.player_employment.find({"employee_player_id": p["id"], "status": "active"}, {"_id": 0}).to_list(50)
    apps = await db.business_applications.find({"applicant_id": p["id"], "status": {"$in": ["pending", "offered", "rejected"]}}, {"_id": 0}).sort("submitted_at", -1).to_list(50)
    return {"employments": [decorate_employment_live(e, cfg, g_now) for e in emps], "applications": apps}


@api.post("/jobs/employment/applications/{app_id}/accept")
async def accept_business_offer(app_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    a = await db.business_applications.find_one({"id": app_id, "applicant_id": p["id"]}, {"_id": 0})
    if not a or a["status"] != "offered":
        raise HTTPException(status_code=400, detail="No offer to accept")
    b = await db.businesses.find_one({"id": a["business_id"]}, {"_id": 0})
    if not b or b.get("bankrupt"):
        raise HTTPException(status_code=400, detail="That business is unavailable")
    emp = {"id": uuid.uuid4().hex, "business_id": a["business_id"], "business_name": a["business_name"],
           "owner_id": a["owner_id"], "employee_player_id": p["id"], "employee_name": p["name"],
           "role": a.get("role", "staff"), "wage_per_hour": a["wage_offer"], "status": "active",
           "schedule": a.get("schedule") or employment.make_schedule("early"), "clocked_out_until": None,
           "hired_at": now_utc().isoformat(), "reliability": 60, "performance": 60,
           "total_hours_worked": 0, "total_wages_earned": 0.0, "total_value_added": 0.0,
           "hours_at_last_raise": 0, "last_paid_at": None, "today": None, "last_impact": None}
    await db.player_employment.insert_one({**emp})
    await db.business_applications.update_one({"id": app_id}, {"$set": {"status": "accepted"}})
    sched = emp["schedule"]
    await add_notification(db, a["owner_id"], "business", "Offer accepted", f"{p['name']} accepted your offer at {a['business_name']}.", "success", f"/businesses/{a['business_id']}")
    await add_event(db, p["id"], f"You're now working at {a['business_name']} as {a.get('role', 'staff')} (${a['wage_offer']}/h, {sched['label']} {sched['start']:02d}:00–{sched['end']:02d}:00).", "job", "success")
    return {"ok": True}


@api.post("/jobs/employment/applications/{app_id}/decline")
async def decline_business_offer(app_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    a = await db.business_applications.find_one({"id": app_id, "applicant_id": p["id"]}, {"_id": 0})
    if not a or a["status"] not in ("offered", "pending"):
        raise HTTPException(status_code=400, detail="Nothing to decline")
    was_offer = a["status"] == "offered"
    await db.business_applications.update_one({"id": app_id}, {"$set": {"status": "declined" if was_offer else "withdrawn"}})
    if was_offer:
        await add_notification(db, a["owner_id"], "business", "Offer declined", f"{p['name']} declined your offer at {a['business_name']}.", "warning", f"/businesses/{a['business_id']}")
        await add_event(db, p["id"], f"You declined the offer from {a['business_name']}.", "job", "info")
    return {"ok": True}


@api.post("/jobs/employment/applications/{app_id}/withdraw")
async def withdraw_business_application(app_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    a = await db.business_applications.find_one({"id": app_id, "applicant_id": p["id"]}, {"_id": 0})
    if not a or a["status"] not in ("pending", "offered"):
        raise HTTPException(status_code=400, detail="Nothing to withdraw")
    await db.business_applications.update_one({"id": app_id}, {"$set": {"status": "withdrawn"}})
    await add_notification(db, a["owner_id"], "business", "Applicant withdrew",
                           f"{p['name']} withdrew their application at {a['business_name']}.", "info", f"/businesses/{a['business_id']}")
    await add_event(db, p["id"], f"You withdrew your application at {a['business_name']}.", "job", "info")
    return {"ok": True}


@api.post("/jobs/employment/{emp_id}/clock-out")
async def clock_out_player_shift(emp_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    emp = await db.player_employment.find_one({"id": emp_id, "employee_player_id": p["id"], "status": "active"}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="You don't work there")
    cfg = await get_config(db)
    res = await employment.clock_out_early(db, p, cfg, emp)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("detail", "You're not on a scheduled shift right now."))
    await save_player(p)
    return res


@api.post("/jobs/employment/{emp_id}/training/{action}")
async def respond_training(emp_id: str, action: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    emp = await db.player_employment.find_one({"id": emp_id, "employee_player_id": p["id"], "status": "active"}, {"_id": 0})
    if not emp or not emp.get("training_offer"):
        raise HTTPException(status_code=404, detail="No training offer pending")
    offer = emp["training_offer"]
    owner = await db.players.find_one({"id": emp["owner_id"]}, {"_id": 0})
    if action == "accept":
        cfg = await get_config(db)
        add_skill_xp(p, offer["skill"], offer.get("skill_gain", 2) * 50, cfg)
        await save_player(p)
        await db.player_employment.update_one({"id": emp_id}, {"$set": {
            "training_offer": None, "performance": clamp(emp.get("performance", 60) + 4),
            "reliability": clamp(emp.get("reliability", 60) + 3)}})
        await add_event(db, p["id"], f"You completed training paid by {emp['business_name']}: {offer['label']} (+{offer.get('skill_gain', 2)} {offer['skill']}).", "job", "success")
        if owner:
            await add_notification(db, owner["id"], "business", "Training completed",
                                   f"{p['name']} completed {offer['label']} at {emp['business_name']}.", "success", f"/businesses/{emp['business_id']}")
            await add_event(db, owner["id"], f"{p['name']} completed training: {offer['label']}.", "business", "success", emp["business_id"])
        return {"ok": True}
    else:
        # refund the owner's escrowed cost
        if owner:
            add_money(owner, offer.get("cost", 0))
            await db.players.update_one({"id": owner["id"]}, {"$set": {"cash": owner["cash"]}})
            await add_notification(db, owner["id"], "business", "Training declined",
                                   f"{p['name']} declined {offer['label']}; ${offer.get('cost', 0)} refunded.", "warning", f"/businesses/{emp['business_id']}")
        await db.player_employment.update_one({"id": emp_id}, {"$set": {"training_offer": None}})
        await add_event(db, p["id"], f"You declined the training offer from {emp['business_name']}.", "job", "info")
        return {"ok": True}


@api.post("/jobs/employment/{emp_id}/schedule/{action}")
async def respond_schedule(emp_id: str, action: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    emp = await db.player_employment.find_one({"id": emp_id, "employee_player_id": p["id"], "status": "active"}, {"_id": 0})
    if not emp or not emp.get("pending_schedule"):
        raise HTTPException(status_code=404, detail="No schedule change pending")
    ps = emp["pending_schedule"]
    sched = {"preset": ps["preset"], "label": ps["label"], "start": ps["start"], "end": ps["end"]}
    owner_id = emp["owner_id"]
    if action == "accept":
        await db.player_employment.update_one({"id": emp_id}, {"$set": {
            "schedule": sched, "pending_schedule": None, "clocked_out_until": None}})
        await add_event(db, p["id"], f"You accepted the new schedule at {emp['business_name']}: {sched['label']}.", "job", "success")
        await add_notification(db, owner_id, "business", "Schedule change accepted",
                               f"{p['name']} accepted the {sched['label']} schedule at {emp['business_name']}.", "success", f"/businesses/{emp['business_id']}")
    else:
        await db.player_employment.update_one({"id": emp_id}, {"$set": {"pending_schedule": None}})
        await add_event(db, p["id"], f"You declined the proposed schedule change at {emp['business_name']}.", "job", "info")
        await add_notification(db, owner_id, "business", "Schedule change declined",
                               f"{p['name']} declined the {sched['label']} schedule at {emp['business_name']}.", "warning", f"/businesses/{emp['business_id']}")
    return {"ok": True}


@api.post("/jobs/employment/{emp_id}/quit")
async def quit_player_job(emp_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    emp = await db.player_employment.find_one({"id": emp_id, "employee_player_id": p["id"], "status": "active"}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employment not found")
    await db.player_employment.update_one({"id": emp_id}, {"$set": {"status": "quit"}})
    p["reputation"] = clamp(p["reputation"] - 2)
    await add_notification(db, emp["owner_id"], "business", "Employee quit", f"{p['name']} quit at {emp['business_name']}.", "warning", f"/businesses/{emp['business_id']}")
    await add_event(db, p["id"], f"You quit your job at {emp['business_name']}.", "job", "warning")
    await save_player(p)
    return {"ok": True}


# --- Player hiring (business owner) ---
@api.get("/businesses/{biz_id}/player-applications")
async def biz_player_applications(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    cfg = await get_config(db)
    reqs = await employee_engine.get_staffing(db, b)
    roles = [r["role"] for r in reqs]
    apps = await db.business_applications.find({"business_id": biz_id, "status": {"$in": ["pending", "offered"]}}, {"_id": 0}).sort("submitted_at", -1).to_list(100)
    for a in apps:
        ap = await db.players.find_one({"id": a["applicant_id"]}, {"_id": 0})
        if ap:
            r2 = roles + ([a["role"]] if a.get("role") and a["role"] not in roles else [])
            a["projection"] = employment.applicant_projection(ap, cfg, r2, b)
    return apps


@api.post("/businesses/{biz_id}/player-applications/{app_id}/offer")
async def offer_player(biz_id: str, app_id: str, body: OfferBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    a = await db.business_applications.find_one({"id": app_id, "business_id": biz_id}, {"_id": 0})
    if not a or a["status"] not in ("pending", "offered"):
        raise HTTPException(status_code=400, detail="Application not open")
    reqs = await employee_engine.get_staffing(db, b)
    role_ids = [r["role"] for r in reqs]
    role = body.role or a.get("role", "staff")
    matches = role in role_ids
    wage = round(max(1.0, body.wage_per_hour), 2)
    prev = a.get("wage_offer")
    was_offered = a["status"] == "offered"
    schedule = employment.make_schedule(body.schedule or (a.get("schedule") or {}).get("preset") or "early")
    await db.business_applications.update_one({"id": app_id}, {"$set": {"status": "offered", "wage_offer": wage, "role": role, "role_matches_staffing": matches, "schedule": schedule}})
    rl = role.replace("_", " ")
    if was_offered and prev:
        direction = "increased to" if wage >= prev else "lowered to"
        await add_notification(db, a["applicant_id"], "job", "Offer updated", f"{b['name']}: wage {direction} ${wage}/h, previously ${prev}/h (as {rl}, {schedule['label']}).", "info", "/job-market")
    else:
        await add_notification(db, a["applicant_id"], "job", "Job offer!", f"{b['name']} offered you ${wage}/h as {rl} ({schedule['label']}).", "success", "/job-market")
    return {"ok": True, "role_matches_staffing": matches}


@api.post("/businesses/{biz_id}/player-applications/{app_id}/reject")
async def reject_player(biz_id: str, app_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    a = await db.business_applications.find_one({"id": app_id, "business_id": biz_id}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Application not found")
    await db.business_applications.update_one({"id": app_id}, {"$set": {"status": "rejected"}})
    await add_notification(db, a["applicant_id"], "job", "Application declined", f"{b['name']} declined your application.", "warning", "/job-market")
    return {"ok": True}


@api.get("/businesses/{biz_id}/player-employees")
async def biz_player_employees(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    cfg = await get_config(db)
    g_now = game_now(cfg, now_utc())
    emps = await db.player_employment.find({"business_id": biz_id, "status": "active"}, {"_id": 0}).to_list(100)
    out = []
    for e in emps:
        e["projection"] = await employment.player_employee_projection(db, cfg, e, b)
        out.append(decorate_employment_live(e, cfg, g_now))
    return out


@api.post("/businesses/{biz_id}/player-employees/{emp_id}/fire")
async def fire_player(biz_id: str, emp_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    emp = await db.player_employment.find_one({"id": emp_id, "business_id": biz_id, "status": "active"}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    await db.player_employment.update_one({"id": emp_id}, {"$set": {"status": "fired"}})
    await add_notification(db, emp["employee_player_id"], "job", "You were let go", f"{b['name']} ended your employment.", "danger", "/job-market")
    await add_event(db, emp["employee_player_id"], f"You were let go from {b['name']}.", "job", "warning")
    return {"ok": True}


@api.post("/businesses/{biz_id}/player-employees/{emp_id}/raise")
async def raise_player(biz_id: str, emp_id: str, body: WageBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    emp = await db.player_employment.find_one({"id": emp_id, "business_id": biz_id, "status": "active"}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    wage = round(max(1.0, body.wage_per_hour), 2)
    prev = emp.get("wage_per_hour") or round(emp.get("wage_per_shift", 60) / 4.0, 2)
    await db.player_employment.update_one({"id": emp_id}, {"$set": {"wage_per_hour": wage, "hours_at_last_raise": emp.get("total_hours_worked", 0), "reliability": clamp(emp.get("reliability", 60) + 5)}})
    await add_notification(db, emp["employee_player_id"], "job", "Pay rise!", f"{b['name']} raised your wage to ${wage}/h, previously ${prev}/h.", "success", "/job-market")
    return {"ok": True}


@api.post("/businesses/{biz_id}/toggle-hiring")
async def toggle_hiring(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    newv = not b.get("hiring_open", False)
    await db.businesses.update_one({"id": biz_id}, {"$set": {"hiring_open": newv}})
    return {"ok": True, "hiring_open": newv}


@api.post("/businesses/{biz_id}/backup")
async def toggle_backup(biz_id: str, body: BackupBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    backup = dict(b.get("backup_roles") or {})
    if body.enabled:
        backup[body.role] = True
    else:
        backup.pop(body.role, None)
    await db.businesses.update_one({"id": biz_id}, {"$set": {"backup_roles": backup}})
    return {"ok": True, "backup_roles": backup}


# ---- Phase 2: internal training for player employees (owner offers -> player accepts/declines) ----
@api.post("/businesses/{biz_id}/player-employees/{emp_id}/offer-training")
async def offer_player_training(biz_id: str, emp_id: str, body: TrainingOfferBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    emp = await db.player_employment.find_one({"id": emp_id, "business_id": biz_id, "status": "active"}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    if emp.get("training_offer"):
        raise HTTPException(status_code=400, detail="A training offer is already pending for this employee")
    opt = await db.training_options.find_one({"id": body.option_id}, {"_id": 0})
    if not opt:
        raise HTTPException(status_code=404, detail="Training option not found")
    if p["cash"] + p["bank"] < opt["cost"]:
        raise HTTPException(status_code=400, detail=f"You can't cover the ${opt['cost']} training cost")
    charge(p, opt["cost"])  # escrow: owner pays now, refunded if declined/expired
    await save_player(p)
    skill = body.skill or employment.ROLE_SKILL.get(emp.get("role")) or "fitness"
    offer = {"option_id": opt["id"], "label": opt["label"], "cost": opt["cost"],
             "skill": skill, "skill_gain": opt["skill_gain"], "desc": opt.get("desc", ""),
             "offered_at": now_utc().isoformat()}
    await db.player_employment.update_one({"id": emp_id}, {"$set": {"training_offer": offer}})
    await add_notification(db, emp["employee_player_id"], "job", "Training offer",
                           f"{b['name']} offered you training: {opt['label']} (+{opt['skill_gain']} {skill}). Accept or decline in Player Jobs.",
                           "info", "/job-market")
    await add_event(db, p["id"], f"You offered {emp['employee_name']} training: {opt['label']} (${opt['cost']} reserved).", "business", "info", biz_id)
    return {"ok": True}


# ---- P2: propose a schedule change (player must accept) ----
@api.post("/businesses/{biz_id}/player-employees/{emp_id}/propose-schedule")
async def propose_schedule(biz_id: str, emp_id: str, body: ProposeScheduleBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    emp = await db.player_employment.find_one({"id": emp_id, "business_id": biz_id, "status": "active"}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    sched = employment.make_schedule(body.schedule)
    if (emp.get("schedule") or {}).get("preset") == sched["preset"]:
        raise HTTPException(status_code=400, detail="That's already their current schedule")
    await db.player_employment.update_one({"id": emp_id}, {"$set": {"pending_schedule": {**sched, "proposed_at": now_utc().isoformat()}}})
    await add_notification(db, emp["employee_player_id"], "job", "Schedule change proposed",
                           f"{b['name']} proposed a new schedule: {sched['label']} {sched['start']:02d}:00–{sched['end']:02d}:00. Accept or decline in Player Jobs.",
                           "info", "/job-market")
    return {"ok": True}


# ============================ NOTIFICATIONS & DAILY SUMMARY ============================
class NotifReadBody(BaseModel):
    ids: Optional[list] = None


@api.get("/notifications")
async def list_notifications(limit: int = 40, user: dict = Depends(current_user)):
    p = await fetch_raw_player(user["id"])
    items = await db.notifications.find({"player_id": p["id"]}, {"_id": 0}).sort("ts", -1).to_list(limit)
    unread = await db.notifications.count_documents({"player_id": p["id"], "read": False})
    return {"items": items, "unread_count": unread}


@api.post("/notifications/read")
async def mark_notifications_read(body: NotifReadBody, user: dict = Depends(current_user)):
    p = await fetch_raw_player(user["id"])
    q = {"player_id": p["id"], "read": False}
    if body.ids is not None:
        q["id"] = {"$in": body.ids}
    await db.notifications.update_many(q, {"$set": {"read": True}})
    return {"ok": True}


@api.get("/daily-summaries")
async def daily_summaries(limit: int = 30, user: dict = Depends(current_user)):
    p = await get_state(user)
    items = await db.daily_summaries.find({"player_id": p["id"]}, {"_id": 0}).sort("real_ts", -1).to_list(limit)
    return items


# ============================ PRESENCE & WORLD CHAT ============================
class ChatBody(BaseModel):
    message: str


class SendMessageBody(BaseModel):
    channel: str
    to_player_id: str
    subject: Optional[str] = None
    body: str
    thread_id: Optional[str] = None


class PlayerIdBody(BaseModel):
    player_id: str


@api.get("/players/online")
async def players_online(user: dict = Depends(current_user)):
    cfg = await get_config(db)
    window = cfg.get("comms", {}).get("online_window_minutes", 3)
    cutoff = (now_utc() - timedelta(minutes=window)).isoformat()
    players = await db.players.find({"last_seen": {"$gte": cutoff}}, {"_id": 0, "id": 1, "name": 1, "last_seen": 1}).to_list(200)
    return {"online": players, "count": len(players)}


@api.get("/players/directory")
async def players_directory(user: dict = Depends(current_user)):
    me = await db.players.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    cfg = await get_config(db)
    players = await db.players.find({}, {"_id": 0, "id": 1, "name": 1, "last_seen": 1, "level": 1, "reputation": 1}).to_list(500)
    out = [{"id": p["id"], "name": p["name"], "level": p.get("level", 1),
            "online": comms.is_online(p, cfg)} for p in players if not me or p["id"] != me["id"]]
    out.sort(key=lambda x: (not x["online"], x["name"].lower()))
    return out


@api.get("/chat/world")
async def chat_world(limit: int = 60, user: dict = Depends(current_user)):
    msgs = await db.world_chat.find({"deleted": {"$ne": True}}, {"_id": 0}).sort("ts", -1).to_list(limit)
    msgs.reverse()
    cfg = await get_config(db)
    window = cfg.get("comms", {}).get("online_window_minutes", 3)
    cutoff = (now_utc() - timedelta(minutes=window)).isoformat()
    online = await db.players.count_documents({"last_seen": {"$gte": cutoff}})
    return {"messages": msgs, "online_count": online}


@api.post("/chat/world")
async def chat_world_send(body: ChatBody, user: dict = Depends(current_user)):
    p = await fetch_raw_player(user["id"])
    cfg = await get_config(db)
    ccfg = cfg.get("comms", {})
    muted = parse_dt(p.get("chat_muted_until"))
    if muted and muted > now_utc():
        raise HTTPException(status_code=403, detail="You are muted in World Chat.")
    text = (body.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message is empty")
    text = text[: ccfg.get("chat_max_length", 280)]
    last = parse_dt(p.get("last_chat_at"))
    cd = ccfg.get("chat_cooldown_seconds", 4)
    if last and (now_utc() - last).total_seconds() < cd:
        raise HTTPException(status_code=429, detail=f"Slow down — wait {cd}s between messages.")
    doc = {"id": uuid.uuid4().hex, "player_id": p["id"], "name": p["name"],
           "message": comms.clean_text(text), "ts": now_utc().isoformat(), "deleted": False}
    await db.world_chat.insert_one({**doc})
    await db.players.update_one({"id": p["id"]}, {"$set": {"last_chat_at": now_utc().isoformat()}})
    doc.pop("_id", None)
    return {"ok": True, "message": doc}


# ============================ PLAYER MESSAGING ============================
@api.get("/messages/threads")
async def message_threads(channel: str = "all", user: dict = Depends(current_user)):
    me = await fetch_raw_player(user["id"])
    q = {"$or": [{"from_player_id": me["id"]}, {"to_player_id": me["id"]}], "deleted_by": {"$ne": me["id"]}}
    msgs = await db.messages.find(q, {"_id": 0}).sort("ts", 1).to_list(3000)
    threads = {}
    for m in msgs:
        if channel != "all" and m["channel"] != channel:
            continue
        tid = m["thread_id"]
        from_me = m["from_player_id"] == me["id"]
        t = threads.setdefault(tid, {"thread_id": tid, "channel": m["channel"],
                                     "other_id": m["to_player_id"] if from_me else m["from_player_id"],
                                     "other_name": m["to_name"] if from_me else m["from_name"],
                                     "subject": m.get("subject"), "unread": 0})
        t["last_body"] = m["body"]
        t["last_ts"] = m["ts"]
        t["last_from_me"] = from_me
        if m.get("subject"):
            t["subject"] = m["subject"]
        if m["to_player_id"] == me["id"] and not m.get("read"):
            t["unread"] += 1
    return sorted(threads.values(), key=lambda x: x.get("last_ts", ""), reverse=True)


@api.get("/messages/unread")
async def messages_unread(user: dict = Depends(current_user)):
    me = await fetch_raw_player(user["id"])
    count = await db.messages.count_documents({"to_player_id": me["id"], "read": {"$ne": True}, "deleted_by": {"$ne": me["id"]}})
    return {"count": count}


@api.get("/messages/thread/{thread_id}")
async def message_thread(thread_id: str, user: dict = Depends(current_user)):
    me = await fetch_raw_player(user["id"])
    msgs = await db.messages.find({"thread_id": thread_id,
                                   "$or": [{"from_player_id": me["id"]}, {"to_player_id": me["id"]}],
                                   "deleted_by": {"$ne": me["id"]}}, {"_id": 0}).sort("ts", 1).to_list(500)
    await db.messages.update_many({"thread_id": thread_id, "to_player_id": me["id"], "read": {"$ne": True}}, {"$set": {"read": True}})
    return {"messages": msgs}


@api.post("/messages/send")
async def send_message(body: SendMessageBody, user: dict = Depends(current_user)):
    me = await fetch_raw_player(user["id"])
    cfg = await get_config(db)
    if body.channel not in ("sms", "email"):
        raise HTTPException(status_code=400, detail="Invalid channel")
    if not comms.has_device(me, body.channel):
        need = "a Laptop" if body.channel == "email" else "a Smartphone"
        raise HTTPException(status_code=403, detail=f"You need {need} to use this. Buy one in the Shop.")
    text = (body.body or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message is empty")
    text = text[: cfg.get("comms", {}).get("message_max_length", 2000)]
    recipient = await db.players.find_one({"id": body.to_player_id}, {"_id": 0})
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    if recipient["id"] == me["id"]:
        raise HTTPException(status_code=400, detail="You can't message yourself")
    if me["id"] in (recipient.get("msg_blocked") or []):
        raise HTTPException(status_code=403, detail="This player has blocked your messages")
    if body.channel == "sms":
        tid = comms.sms_thread_id(me["id"], recipient["id"])
        subject = None
    else:
        tid = body.thread_id or uuid.uuid4().hex
        subject = (body.subject or "(no subject)").strip()[:120]
    doc = {"id": uuid.uuid4().hex, "channel": body.channel, "thread_id": tid,
           "from_player_id": me["id"], "from_name": me["name"],
           "to_player_id": recipient["id"], "to_name": recipient["name"],
           "subject": subject, "body": comms.clean_text(text),
           "ts": now_utc().isoformat(), "read": False, "deleted_by": []}
    await db.messages.insert_one({**doc})
    label = "email" if body.channel == "email" else "SMS"
    await add_notification(db, recipient["id"], "message", f"New {label} from {me['name']}",
                           (subject + " — " if subject else "") + text[:80], "info", "/messages")
    doc.pop("_id", None)
    return {"ok": True, "thread_id": tid, "message": doc}


@api.post("/messages/block")
async def block_player(body: PlayerIdBody, user: dict = Depends(current_user)):
    me = await fetch_raw_player(user["id"])
    blocked = set(me.get("msg_blocked") or [])
    if body.player_id in blocked:
        blocked.discard(body.player_id)
        verb = "unblocked"
    else:
        blocked.add(body.player_id)
        verb = "blocked"
    await db.players.update_one({"id": me["id"]}, {"$set": {"msg_blocked": list(blocked)}})
    return {"ok": True, "status": verb}


@api.post("/messages/{message_id}/report")
async def report_message(message_id: str, user: dict = Depends(current_user)):
    me = await fetch_raw_player(user["id"])
    await db.message_reports.insert_one({"id": uuid.uuid4().hex, "message_id": message_id,
                                         "reporter_id": me["id"], "ts": now_utc().isoformat()})
    return {"ok": True}


# ============================ ADMIN: CHAT MODERATION ============================
class MuteBody(BaseModel):
    player_id: str
    minutes: int = 60


@api.get("/admin/chat")
async def admin_chat(limit: int = 100, admin: dict = Depends(admin_user)):
    return await db.world_chat.find({}, {"_id": 0}).sort("ts", -1).to_list(limit)


@api.delete("/admin/chat/{message_id}")
async def admin_delete_chat(message_id: str, admin: dict = Depends(admin_user)):
    await db.world_chat.update_one({"id": message_id}, {"$set": {"deleted": True}})
    return {"ok": True}


@api.post("/admin/chat/mute")
async def admin_mute(body: MuteBody, admin: dict = Depends(admin_user)):
    until = (now_utc() + timedelta(minutes=min(max(1, body.minutes), 525600))).isoformat()
    res = await db.players.update_one({"id": body.player_id}, {"$set": {"chat_muted_until": until}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Player not found")
    return {"ok": True, "muted_until": until}


@api.post("/admin/chat/unmute")
async def admin_unmute(body: PlayerIdBody, admin: dict = Depends(admin_user)):
    await db.players.update_one({"id": body.player_id}, {"$set": {"chat_muted_until": None}})
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


async def seed_demo_players():
    """Idempotently create ~3 identifiable demo players for multiplayer testing."""
    demos = [
        {"email": "mara@kaeldor.com", "name": "Mara Vance", "bg": "worker",
         "cash": 800, "bank": 1500, "devices": ["smartphone", "laptop"], "rep": 60, "job": "cashier"},
        {"email": "dovan@kaeldor.com", "name": "Dovan Reyes", "bg": "hustler",
         "cash": 1200, "bank": 4000, "devices": ["smartphone", "laptop"], "rep": 55, "business": "kiosk"},
        {"email": "kiri@kaeldor.com", "name": "Kiri Sol", "bg": "graduate",
         "cash": 500, "bank": 900, "devices": ["smartphone"], "rep": 75, "job": "sales_assistant"},
    ]
    for d in demos:
        user = await db.users.find_one({"email": d["email"]})
        if user:
            uid = str(user["_id"])
        else:
            res = await db.users.insert_one({"email": d["email"], "password_hash": hash_password("demo123"),
                                             "name": d["name"], "role": "player", "demo": True,
                                             "created_at": now_utc().isoformat()})
            uid = str(res.inserted_id)
        if await db.players.find_one({"user_id": uid}):
            continue
        p = new_player(uid, d["name"], d["bg"])
        p["cash"] = d["cash"]
        p["bank"] = d["bank"]
        p["reputation"] = d["rep"]
        p["last_seen"] = now_utc().isoformat()
        p["inventory"] = {dev: 1 for dev in d["devices"]}
        if d.get("job"):
            j = await db.jobs.find_one({"id": d["job"]}, {"_id": 0})
            if j:
                p["job"] = {"job_id": j["id"], "title": j["title"], "shifts_worked": 12, "hours_worked": 60,
                            "reliability": 70, "hired_at": now_utc().isoformat()}
        await db.players.insert_one({**p})
        if d.get("business"):
            t = await db.business_types.find_one({"id": d["business"]}, {"_id": 0})
            if t:
                recipe = t.get("recipe") or []
                target = t.get("daily_demand", 0)
                now = now_utc()
                biz = {
                    "id": uuid.uuid4().hex, "player_id": p["id"], "type_id": t["id"], "name": f"{d['name'].split()[0]}'s {t['name']}",
                    "category": t.get("category", ""), "purchase_price": t["purchase_price"],
                    "max_level": t.get("max_level", 5), "level": 1, "marketing_level": 0, "reputation": 55.0,
                    "product": t.get("product") or {}, "recipe": recipe,
                    "production_per_worker_hour": t.get("production_per_worker_hour", 0),
                    "daily_demand": target, "materials": {r["id"]: round(target * r.get("qty", 1), 3) for r in recipe},
                    "products": 0.0, "restock_target": target, "auto_restock": True,
                    "cash": 200.0, "debt": 0.0, "revenue_total": 0.0,
                    "rev_day": 0.0, "material_day": 0.0, "wages_day": 0.0, "net_day": 0.0, "exp_day": 0.0,
                    "demand_day": 0.0, "produced_day": 0.0, "sold_day": 0.0,
                    "bankrupt": False, "history": [], "created_at": now.isoformat(), "last_resolved_at": now.isoformat(),
                    "satisfaction": 80.0, "last_applicant_at": now.isoformat(), "morale_avg": 0, "hiring_open": True,
                }
                await db.businesses.insert_one({**biz})
    logger.info("Demo players seeded (mara/dovan/kiri @kaeldor.com / demo123)")


async def migrate_hours_based_promotions():
    """Convert legacy shift-count promotion requirements + player job progress to hour-based."""
    seed_jobs = {x["id"]: x for x in CONTENT_MAP["jobs"][1]}
    async for j in db.jobs.find({"promotion_req.shifts": {"$exists": True}}, {"_id": 0, "id": 1, "promotion_req": 1}):
        sj = seed_jobs.get(j["id"])
        if sj:
            new_req = sj.get("promotion_req", {})
        else:
            old = j.get("promotion_req") or {}
            new_req = {k: v for k, v in old.items() if k != "shifts"}
            new_req["hours"] = old.get("shifts", 0) * 5
        await db.jobs.update_one({"id": j["id"]}, {"$set": {"promotion_req": new_req}})
    async for pl in db.players.find({"job": {"$ne": None}, "job.hours_worked": {"$exists": False}}, {"_id": 0, "id": 1, "job": 1}):
        job = pl.get("job") or {}
        if job:
            await db.players.update_one({"id": pl["id"]}, {"$set": {"job.hours_worked": round(job.get("shifts_worked", 0) * 5, 1)}})
    await db.player_employment.update_many({"hours_at_last_raise": {"$exists": False}}, {"$set": {"hours_at_last_raise": 0}})


async def migrate_player_employment_hourly():
    """Convert player employment + open business offers from per-shift to per-hour wages."""
    async for e in db.player_employment.find({"wage_per_hour": {"$exists": False}}, {"_id": 0, "id": 1, "wage_per_shift": 1}):
        wph = round(e.get("wage_per_shift", 60) / 4.0, 2)
        await db.player_employment.update_one({"id": e["id"]}, {"$set": {"wage_per_hour": wph, "total_value_added": 0.0}})
    async for a in db.business_applications.find({"status": "offered", "wage_offer": {"$ne": None}, "wage_hourly_migrated": {"$ne": True}}, {"_id": 0, "id": 1, "wage_offer": 1}):
        await db.business_applications.update_one({"id": a["id"]}, {"$set": {"wage_offer": round(a["wage_offer"] / 4.0, 2), "wage_hourly_migrated": True}})
    async for e in db.player_employment.find({"schedule": {"$exists": False}}, {"_id": 0, "id": 1}):
        await db.player_employment.update_one({"id": e["id"]}, {"$set": {
            "schedule": employment.make_schedule("early"), "clocked_out_until": None}})
    # tag legacy finance-history entries so the UI can label them Forecast vs Booking
    async for b in db.businesses.find({"history": {"$exists": True, "$ne": []}}, {"_id": 0, "id": 1, "history": 1}):
        hist = b.get("history") or []
        changed = False
        for h in hist:
            if "kind" not in h:
                h["kind"] = "accrual"
                changed = True
        if changed:
            await db.businesses.update_one({"id": b["id"]}, {"$set": {"history": hist}})


async def migrate_business_supply_chain():
    """Migrate business_types + existing businesses to the supply-chain model, and give NPC
    employees a schedule + hourly wage so they run through the same worker logic as players."""
    seed_types = {t["id"]: t for t in CONTENT_MAP["business_types"][1]}
    for tid, t in seed_types.items():
        await db.business_types.update_one({"id": tid}, {"$set": {
            "product": t.get("product"), "recipe": t.get("recipe"),
            "production_per_worker_hour": t.get("production_per_worker_hour"),
            "daily_demand": t.get("daily_demand"),
            "opening_hours": t.get("opening_hours") or {"open": "08:00", "close": "20:00"}},
            "$unset": {"rent_per_day": "", "base_revenue_per_day": "", "base_expenses_per_day": ""}})
    # Refresh the economic definition on ALL existing businesses from seed so re-balances take effect
    # (runtime state — cash/level/reputation/materials/products — is preserved).
    for tid, t in seed_types.items():
        await db.businesses.update_many({"type_id": tid}, {"$set": {
            "product": t.get("product") or {}, "recipe": t.get("recipe") or [],
            "production_per_worker_hour": t.get("production_per_worker_hour", 0),
            "daily_demand": t.get("daily_demand", 0),
            "opening_hours": t.get("opening_hours") or {"open": "08:00", "close": "20:00"}}})
    # Lift existing businesses' starting satisfaction so a well-run shop reaches its profit target
    await db.businesses.update_many({"satisfaction": {"$lt": 80}}, {"$set": {"satisfaction": 80.0}})
    now_iso = now_utc().isoformat()
    async for b in db.businesses.find({"recipe": {"$exists": False}}, {"_id": 0}):
        t = seed_types.get(b.get("type_id")) or {}
        recipe = t.get("recipe") or []
        target = t.get("daily_demand", 0)
        await db.businesses.update_one({"id": b["id"]}, {"$set": {
            "product": t.get("product") or {}, "recipe": recipe,
            "production_per_worker_hour": t.get("production_per_worker_hour", 0),
            "daily_demand": target, "restock_target": target, "auto_restock": True,
            "materials": {r["id"]: round(target * r.get("qty", 1), 3) for r in recipe},
            "products": 0.0, "last_resolved_at": now_iso, "bankrupt": False},
            "$unset": {"rent_per_day": "", "base_revenue_per_day": "", "base_expenses_per_day": "",
                       "coverage": "", "backup_roles": "", "backup_wage_day": "", "last_net_day": ""}})
    async for e in db.employees.find({"status": {"$in": ["active", "sick"]}, "schedule": {"$exists": False}}, {"_id": 0, "id": 1, "daily_wage": 1}):
        await db.employees.update_one({"id": e["id"]}, {"$set": {
            "schedule": employment.make_schedule("early"), "wage_per_hour": round(e.get("daily_wage", 90) / 8.0, 2)}})
    # One-time: re-slot existing NPC shifts into non-overlapping blocks across each business's opening hours
    async for b in db.businesses.find({"opening_shift_migrated": {"$ne": True}}, {"_id": 0, "id": 1, "opening_hours": 1}):
        o_h, c_h = employment.opening_bounds(b.get("opening_hours"))
        npcs = await db.employees.find({"business_id": b["id"], "status": {"$in": ["active", "sick"]}}, {"_id": 0, "id": 1}).sort("hire_date", 1).to_list(300)
        n = len(npcs)
        if n:
            block = (c_h - o_h) / n
            for i, e in enumerate(npcs):
                s = o_h + i * block
                e2 = c_h if i == n - 1 else o_h + (i + 1) * block
                await db.employees.update_one({"id": e["id"]}, {"$set": {"schedule": employment.make_shift(s, e2)}})
        await db.businesses.update_one({"id": b["id"]}, {"$set": {"opening_shift_migrated": True}})
    # Sync job requirements from seed (so Legal Standing / Social Status gates apply to existing DBs)
    for jd in JOBS:
        await db.jobs.update_one({"id": jd["id"]}, {"$set": {"requirements": jd.get("requirements", {})}})
    # One-time: hard-sync the world clock to German local time (Europe/Berlin) at 1:1 real-time pace.
    cfg_doc = await db.config.find_one({"id": "global"})
    if cfg_doc and not cfg_doc.get("time_synced_de"):
        try:
            from zoneinfo import ZoneInfo
            offset = datetime.now(ZoneInfo("Europe/Berlin")).utcoffset() or timedelta(hours=2)
        except Exception:
            offset = timedelta(hours=2)
        now = now_utc()
        await db.config.update_one({"id": "global"}, {"$set": {
            "time_scale": 1.0,
            "world_start_real": now.isoformat(),
            "world_start_game": (now + offset).isoformat(),
            "time_synced_de": True,
        }})


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.players.create_index("user_id", unique=True)
    await db.players.create_index("id", unique=True)
    await db.events.create_index([("player_id", 1), ("ts", -1)])
    await db.businesses.create_index("player_id")
    await db.notifications.create_index([("player_id", 1), ("ts", -1)])
    await db.world_chat.create_index([("ts", -1)])
    await db.messages.create_index([("thread_id", 1), ("ts", 1)])
    await db.messages.create_index([("to_player_id", 1), ("read", 1)])
    await db.players.create_index("last_seen")
    await db.applications.create_index([("player_id", 1), ("status", 1)])
    await db.business_applications.create_index([("business_id", 1), ("status", 1)])
    await db.player_employment.create_index([("employee_player_id", 1), ("status", 1)])
    await seed_content(db)
    await migrate_hours_based_promotions()
    await migrate_player_employment_hourly()
    await migrate_business_supply_chain()
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
    await seed_demo_players()
    logger.info("Kaeldor RPG started. Admin: %s", admin_email)


@app.on_event("shutdown")
async def shutdown():
    client.close()
