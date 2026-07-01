from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List

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




def shift_window_open(shift, game_hour):
    """Hard time-gate for a job shift option. min_hour > max_hour = overnight window (wraps midnight)."""
    w = shift.get("start_window") or {}
    lo = int(w.get("min_hour", 0))
    hi = int(w.get("max_hour", 24))
    if lo == hi:
        return True
    if lo < hi:
        return lo <= game_hour < hi
    return game_hour >= lo or game_hour < hi




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




class ApplyBody(BaseModel):
    message: Optional[str] = None




class ShiftBody(BaseModel):
    shift_id: Optional[str] = None
    hours: Optional[int] = None




# ============================ SHOP ============================
SHOP_DEFAULT_CAPACITY = seed_data.SHOP_DEFAULT_CAPACITY




def _default_opening():
    return {"open": "08:00", "close": "20:00"}




def _eff_price(base, discount_pct):
    d = max(0, min(95, int(discount_pct or 0)))
    return max(1, int(round(float(base) * (1 - d / 100.0))))




async def _resolve_shop_stock(shop, cfg):
    """Lazily refresh a shop's stock to per-item capacity at the game-day (00:00) boundary.
    Persists the reset. Returns the (mutated) shop dict."""
    day = game_day_index(cfg, now_utc())
    if shop.get("last_refresh_day") == day:
        return shop
    cat_items = await db.items.find({"store_type": shop.get("category")}, {"_id": 0, "id": 1}).to_list(200)
    cfgmap = shop.get("items_config") or {}
    stock = {}
    for it in cat_items:
        cap = int((cfgmap.get(it["id"]) or {}).get("capacity", SHOP_DEFAULT_CAPACITY))
        stock[it["id"]] = max(0, cap)
    shop["stock"] = stock
    shop["last_refresh_day"] = day
    await db.city_shops.update_one({"id": shop["id"]}, {"$set": {"stock": stock, "last_refresh_day": day}})
    return shop




class BuyBody(BaseModel):
    item_id: str
    qty: int = 1
    store_id: Optional[str] = None




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




# ============================ BANK ============================
class AmountBody(BaseModel):
    amount: float




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




async def _get_owned_business(p, biz_id):
    b = await db.businesses.find_one({"id": biz_id, "player_id": p["id"]}, {"_id": 0})
    if not b:
        raise HTTPException(status_code=404, detail="Business not found")
    return b




class RenameBody(BaseModel):
    name: str




class MaterialsBody(BaseModel):
    units: Optional[float] = None  # product-equivalent units to top up to (defaults to restock target)




class RestockBody(BaseModel):
    auto_restock: Optional[bool] = None
    restock_target: Optional[float] = None




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




class AdminLayoutBody(BaseModel):
    order: Optional[List[str]] = None
    hidden: Optional[List[str]] = None




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




# ============================ EMPLOYEES ============================
async def _get_employee(p, emp_id):
    emp = await db.employees.find_one({"id": emp_id}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    biz = await db.businesses.find_one({"id": emp["business_id"], "player_id": p["id"]}, {"_id": 0})
    if not biz:
        raise HTTPException(status_code=403, detail="Not your employee")
    return emp, biz




class OpeningHoursBody(BaseModel):
    open: str
    close: str




class EmployeeShiftBody(BaseModel):
    start: str
    end: str




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
async def set_employee_shift(biz_id: str, emp_id: str, body: EmployeeShiftBody, user: dict = Depends(current_user)):
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




# ============================ SOCIAL CONTACTS ============================
class InteractBody(BaseModel):
    action_id: str
    gift_id: Optional[str] = None




async def _get_contact(p, cid):
    c = await db.contacts.find_one({"id": cid, "player_id": p["id"]}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    return c




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
    opening_hours: Optional[dict] = None
    items_config: Optional[dict] = None




def _norm_opening(oh):
    if not oh:
        return _default_opening()
    return {"open": str(oh.get("open") or "08:00"), "close": str(oh.get("close") or "20:00")}




def _norm_items_config(cfg):
    out = {}
    for iid, c in (cfg or {}).items():
        c = c or {}
        out[iid] = {"capacity": max(0, int(c.get("capacity", SHOP_DEFAULT_CAPACITY))),
                    "discount_pct": max(0, min(95, int(c.get("discount_pct", 0))))}
    return out




# ---- Admin: Job Sectors management ----
class JobSectorBody(BaseModel):
    name: str
    desc: Optional[str] = ""
    icon: Optional[str] = "Briefcase"
    active: Optional[bool] = True
    order: Optional[int] = 50
    job_ids: Optional[List[str]] = None


class VehicleCategoryBody(BaseModel):
    name: str
    desc: Optional[str] = ""
    icon: Optional[str] = "Car"
    active: Optional[bool] = True
    order: Optional[int] = 50
    vehicle_ids: Optional[List[str]] = None




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




# ============================ NOTIFICATIONS & DAILY SUMMARY ============================
class NotifReadBody(BaseModel):
    ids: Optional[list] = None




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




# ============================ ADMIN: CHAT MODERATION ============================
class MuteBody(BaseModel):
    player_id: str
    minutes: int = 60


__all__ = [n for n in list(globals()) if not n.startswith('__')]
