"""Kaeldor RPG - unified business engine (supply chain + workers).

A business buys named ingredients (recipe), its workers process them into a finished
product, and the product is sold to meet demand. Profit = sales - materials - wages.
NO rent / artificial fixed costs on owned businesses.

Workers are handled by ONE code path: NPC employees (db.employees) and player employees
(db.player_employment) are normalized into the same shape and use the same productivity /
wage / shift math. The only difference is the UI label (NPC name vs player name).

resolve_business() is idempotent on the business's own clock (last_resolved_at) and is the
single writer of the business document, so it can be triggered by the owner OR by any
employed player without double-booking (no clobber-race).
"""
import uuid
import random
from datetime import timedelta

from game_models import clamp, now_utc
import game_models
from game_engine import (add_event, parse_dt, real_seconds, add_notification, game_now,
                         get_config, effectiveness)
import employment


FIRST_NAMES = [
    "Mara", "Dex", "Lena", "Cyrus", "Nadia", "Theo", "Vera", "Rafe", "Iris", "Kai",
    "Sasha", "Bram", "Noor", "Dario", "Petra", "Ezra", "Lila", "Cato", "Maya", "Finn",
    "Zara", "Otto", "Juno", "Milo", "Greta", "Levi", "Anya", "Ravi", "Esme", "Tomas",
]
LAST_NAMES = [
    "Voss", "Kade", "Mercer", "Sato", "Okafor", "Rios", "Halloran", "Nikolai", "Dubois", "Reyes",
    "Cohen", "Ashby", "Varga", "Lindqvist", "Petrov", "Okonkwo", "Bauer", "Costa", "Ferro", "Salim",
]

NPC_EQUIV_HOURS = 8.0  # NPC daily_wage is spread over an 8h equivalent day -> hourly wage


def _gen_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def npc_hourly_wage(e):
    return e.get("wage_per_hour") or round(e.get("daily_wage", 90) / NPC_EQUIV_HOURS, 2)


def worker_productivity(skill_level, reliability, condition):
    """Unified productivity (0.35..1.8) from skill, reliability and a mild condition factor.
    Identical formula for NPCs and players; only the input source differs."""
    fit = clamp(0.55 + (skill_level - 1) / 9 * 0.75, 0.55, 1.3)
    rel = 0.8 + 0.4 * (reliability / 100.0)
    return round(clamp(fit * rel * condition, 0.35, 1.8), 3)


async def get_staffing(db, b):
    doc = await db.staffing_requirements.find_one({"id": b.get("type_id")}, {"_id": 0})
    return (doc or {}).get("requirements", [])


def _distribute_slots(reqs, max_slots):
    """Spread the business's staff slots across its roles so per-role targets sum to max_slots.
    Extra slots unlocked by upgrades go to the roles with the largest base need first."""
    rec = [r.get("recommended", 1) for r in reqs]
    if not rec:
        return rec
    extra = max(0, max_slots - sum(rec))
    order = sorted(range(len(rec)), key=lambda i: -rec[i])
    i = 0
    while extra > 0:
        rec[order[i % len(order)]] += 1
        extra -= 1
        i += 1
    return rec


async def _traits_map(db):
    return {t["id"]: t for t in await db.employee_traits.find({}, {"_id": 0}).to_list(100)}


def _recipe(b):
    return b.get("recipe") or []


def material_cost_per_unit(b):
    override = b.get("material_cost_override")
    if override is not None:
        return round(float(override), 4)
    return round(sum(r.get("qty", 1) * r.get("cost", 0) for r in _recipe(b)), 4)


def unit_price(b):
    return (b.get("product") or {}).get("price", 0)


def marketing_demand_mult(b):
    """Marketing brings more customers: +25% demand per level."""
    return 1 + 0.25 * b.get("marketing_level", 0)


def marketing_price_mult(b):
    """Brand strength lets the business charge a premium: +10% price per level.
    This stays visible even when the business is capacity-bound (already sold out)."""
    return 1 + 0.10 * b.get("marketing_level", 0)


def reputation_mult(b):
    """REPUTATION = market reach. Scales customer DEMAND (min..max, admin-tunable)."""
    lo = game_models.TUNE.get("reputation_mult_min", 0.5)
    hi = game_models.TUNE.get("reputation_mult_max", 1.0)
    return round(lo + (hi - lo) * (b.get("reputation", 50) / 100.0), 4)


def satisfaction_mult(b):
    """SATISFACTION = team morale/efficiency. Scales PRODUCTION output (min..max, admin-tunable)."""
    lo = game_models.TUNE.get("satisfaction_mult_min", 0.85)
    hi = game_models.TUNE.get("satisfaction_mult_max", 1.0)
    return round(lo + (hi - lo) * (b.get("satisfaction", 80) / 100.0), 4)


# ===================== CANONICAL ECONOMY FORMULAS =====================
# Single source of truth — see /app/docs/ECONOMY_LOGIC.md. All wage/production
# math MUST route through these two functions. No alternate wage paths.
def _num(v):
    """Coerce an hour value that may be numeric or an 'HH:MM' string to a float."""
    if isinstance(v, (int, float)):
        return float(v)
    return employment.hhmm_to_float(v)


def calculate_worker_daily_wage(worker, opening=None):
    """ONLY wage formula: hourly_wage * scheduled_shift_hours. Off-shift / no schedule = $0.
    If `opening` is given, the shift is clipped to the opening window (never paid while closed)."""
    schedule = worker.get("schedule")
    if not schedule:
        return 0.0
    start = _num(schedule.get("start", 0))
    end = _num(schedule.get("end", 0))
    if opening is not None:
        o = _num(opening.get("open", 0))
        c = _num(opening.get("close", 24))
        if c <= o:
            c = 24.0
        start = max(o, start)
        end = min(c, end)
    hours = end - start
    if hours <= 0:
        return 0.0
    rate = worker.get("hourly_wage", worker.get("wage_per_hour", 0)) or 0.0
    return round(rate * hours, 4)


def calculate_total_covered_hours(employees, opening_hours):
    """UNION of all workers' shift durations, clipped to & capped at the opening window.
    Overlapping shifts do NOT double-count (union, not sum) per ECONOMY_LOGIC.md."""
    o = _num(opening_hours.get("open", 8))
    c = _num(opening_hours.get("close", 20))
    if c <= o:
        c = 24.0
    ivals = []
    for emp in employees:
        sch = emp.get("schedule")
        if not sch:
            continue
        s = max(o, _num(sch.get("start", 0)))
        e = min(c, _num(sch.get("end", 0)))
        if e > s:
            ivals.append((s, e))
    ivals.sort()
    total = 0.0
    cur_s = cur_e = None
    for s, e in ivals:
        if cur_e is None:
            cur_s, cur_e = s, e
        elif s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            total += cur_e - cur_s
            cur_s, cur_e = s, e
    if cur_e is not None:
        total += cur_e - cur_s
    return round(min(total, c - o), 4)



def effective_price(b):
    return round(unit_price(b) * marketing_price_mult(b), 4)


def margin_per_unit(b):
    return round(effective_price(b) - material_cost_per_unit(b), 4)


async def gather_workers(db, b, cfg, traits_map=None):
    """Return the unified active-worker list for a business (NPCs + players)."""
    traits_map = traits_map if traits_map is not None else await _traits_map(db)
    workers = []
    npcs = await db.employees.find({"business_id": b["id"], "status": "active"}, {"_id": 0}).to_list(300)
    for e in npcs:
        cond = clamp(game_models.TUNE.get("worker_cond_min", 0.85) + (game_models.TUNE.get("worker_cond_max", 1.05) - game_models.TUNE.get("worker_cond_min", 0.85)) * ((e.get("morale", 60) + e.get("energy", 80)) / 200.0), 0.6, 1.2)
        prod = worker_productivity(e.get("skill", 3), e.get("reliability", 60), cond)
        for t in e.get("traits", []):
            prod *= (1 + traits_map.get(t, {}).get("effects", {}).get("revenue", 0))
        workers.append({
            "kind": "npc", "id": e["id"], "name": e["name"], "role": e.get("role"),
            "wage_per_hour": npc_hourly_wage(e), "schedule": e.get("schedule"),
            "clocked_out_until": None, "productivity": round(clamp(prod, 0.2, 1.9), 3),
            "is_player": False, "emp": e,
        })
    pemps = await db.player_employment.find({"business_id": b["id"], "status": "active"}, {"_id": 0}).to_list(100)
    for e in pemps:
        pl = await db.players.find_one({"id": e["employee_player_id"]}, {"_id": 0})
        if not pl:
            continue
        sk = employment.ROLE_SKILL.get(e.get("role"))
        skill_level = pl["skills"].get(sk, {}).get("level", 1) if sk else employment._avg(employment._top_skills(pl))
        cond = clamp(game_models.TUNE.get("worker_cond_min", 0.85) + (game_models.TUNE.get("worker_cond_max", 1.05) - game_models.TUNE.get("worker_cond_min", 0.85)) * effectiveness(pl), 0.6, 1.2)
        prod = worker_productivity(skill_level, e.get("reliability", 60), cond)
        workers.append({
            "kind": "player", "id": e["id"], "name": e.get("employee_name") or pl["name"], "role": e.get("role"),
            "wage_per_hour": e.get("wage_per_hour") or round(e.get("wage_per_shift", 60) / 4.0, 2),
            "schedule": e.get("schedule") or employment.make_schedule("early"),
            "clocked_out_until": parse_dt(e.get("clocked_out_until")), "productivity": prod,
            "is_player": True, "emp": e, "player_id": pl["id"],
        })
    return workers


def calculate_effective_worker_hours(employees, opening, slots):
    """Worker-hours that drive production: sum of min(concurrent workers, slots) over opening hours.
    1 worker/12h = 12; two 6h split shifts = 12; two concurrent 12h shifts (slots>=2) = 24 (scales)."""
    return employment.effective_worker_hours_per_day(opening, [e.get("schedule") for e in employees], slots)


def _day_rates(b, workers, upgrade_penalty=1.0, slots=1):
    """Steady-state per-day P&L forecast (transparent; independent of tick size).
    Production scales with EFFECTIVE worker-hours = concurrent workers (capped at slots) x hours."""
    pph = b.get("production_per_worker_hour", 0)
    mkt = marketing_demand_mult(b)
    rep = reputation_mult(b)
    lvl = 1 + 0.6 * (b.get("level", 1) - 1)
    opening = b.get("opening_hours")
    # canonical coverage + wage formulas (see /app/docs/ECONOMY_LOGIC.md)
    covered_hours = calculate_total_covered_hours(workers, opening)   # union, for coverage% display
    worker_hours = calculate_effective_worker_hours(workers, opening, slots)  # drives production
    open_hours = employment.open_hours_total(opening)
    demand_day = b.get("daily_demand", 0) * mkt * rep * lvl
    capacity_day = pph * worker_hours * satisfaction_mult(b) * lvl
    sold_day = min(capacity_day, demand_day)
    mc = material_cost_per_unit(b)
    eprice = effective_price(b)
    rev_day = round(sold_day * eprice * upgrade_penalty, 2)
    material_day = round(sold_day * mc, 2)
    wages_day = round(sum(calculate_worker_daily_wage(w, opening) for w in workers), 2)
    net_day = round(rev_day - material_day - wages_day, 2)
    return {
        "demand_day": round(demand_day, 1), "capacity_day": round(capacity_day, 1),
        "produced_day": round(sold_day, 1), "sold_day": round(sold_day, 1),
        "rev_day": rev_day, "material_day": material_day,
        "wages_day": wages_day, "net_day": net_day, "effective_price": eprice,
        "covered_hours": covered_hours, "worker_hours": worker_hours, "open_hours": open_hours,
    }


def _auto_restock(b, need_units, material_spend_out):
    """Buy ingredients from business cash up to target buffer (and at least enough for need_units)."""
    target = max(b.get("restock_target", b.get("daily_demand", 0)) or 0, need_units)
    materials = b.get("materials") or {}
    spent = 0.0
    for r in _recipe(b):
        rid, qty, cost = r["id"], r.get("qty", 1), r.get("cost", 0)
        want = target * qty
        have = materials.get(rid, 0)
        if have >= want or cost <= 0:
            continue
        short = want - have
        afford = b.get("cash", 0) - spent
        buy = short if afford >= short * cost else max(0.0, afford / cost)
        if buy <= 0:
            continue
        materials[rid] = round(have + buy, 3)
        spent += buy * cost
    b["materials"] = materials
    b["cash"] = round(b.get("cash", 0) - spent, 2)
    return round(spent, 2)


def _producible(b, capacity):
    """Units producible now, bounded by capacity and available materials."""
    materials = b.get("materials") or {}
    limit = capacity
    for r in _recipe(b):
        qty = r.get("qty", 1)
        if qty > 0:
            limit = min(limit, materials.get(r["id"], 0) / qty)
    return max(0.0, limit)


def _consume(b, units):
    materials = b.get("materials") or {}
    for r in _recipe(b):
        materials[r["id"]] = round(max(0.0, materials.get(r["id"], 0) - units * r.get("qty", 1)), 3)
    b["materials"] = materials


async def business_metrics(db, b):
    """Read-only staffing + supply-chain P&L snapshot used by API responses."""
    cfg = await get_config(db)
    g_now = game_now(cfg, now_utc())
    reqs = await get_staffing(db, b)
    npcs = await db.employees.find({"business_id": b["id"], "status": "active"}, {"_id": 0}).to_list(300)
    sick = await db.employees.find({"business_id": b["id"], "status": "sick"}, {"_id": 0}).to_list(300)
    applicants = await db.employees.count_documents({"business_id": b["id"], "status": "applicant"})
    pemps = await db.player_employment.find({"business_id": b["id"], "status": "active"}, {"_id": 0}).to_list(100)

    opening = b.get("opening_hours")
    open_now = employment.is_open_now(opening, g_now)
    npc_by_role, npc_active_by_role = {}, {}
    for e in npcs:
        r = e.get("role")
        npc_by_role[r] = npc_by_role.get(r, 0) + 1
        if employment.on_shift_now(e.get("schedule"), opening, g_now):
            npc_active_by_role[r] = npc_active_by_role.get(r, 0) + 1
    p_by_role, p_active_by_role = {}, {}
    for pe in pemps:
        r = pe.get("role")
        p_by_role[r] = p_by_role.get(r, 0) + 1
        if employment.on_shift_now(pe.get("schedule"), opening, g_now, parse_dt(pe.get("clocked_out_until"))):
            p_active_by_role[r] = p_active_by_role.get(r, 0) + 1

    base_slots = max(1, sum(r.get("recommended", 1) for r in reqs))
    max_slots = base_slots + (b.get("level", 1) - 1)
    scaled_rec = _distribute_slots(reqs, max_slots)
    staffing, active_ratios = [], []
    for idx, r in enumerate(reqs):
        rec = scaled_rec[idx]
        assigned = npc_by_role.get(r["role"], 0) + p_by_role.get(r["role"], 0)
        active = npc_active_by_role.get(r["role"], 0) + p_active_by_role.get(r["role"], 0)
        if not open_now:
            status = "Closed"
        elif active > 0:
            status = "Working now"
        elif assigned > 0:
            status = "Off shift"
        else:
            status = "Unfilled"
        staffing.append({
            "role": r["role"], "recommended": rec,
            "npc_have": npc_by_role.get(r["role"], 0), "player_have": p_by_role.get(r["role"], 0),
            "assigned": assigned, "active_working": active, "status": status,
        })
        active_ratios.append(min(1, active / rec) if rec else 1)
    coverage = round(sum(active_ratios) / len(active_ratios), 2) if active_ratios else 1.0
    staff_count = len(npcs) + len(sick) + len(pemps)

    # unified shift roster (NPCs + player employees) for the Schedule tab
    all_scheds = [e.get("schedule") for e in npcs] + [pe.get("schedule") for pe in pemps]
    covered_hours = employment.covered_hours_per_day(opening, all_scheds)
    open_hours = employment.open_hours_total(opening)
    o_h, c_h = employment.opening_bounds(opening)
    roster = []
    for e in npcs:
        sh = e.get("schedule")
        scheduled = bool(sh)
        s_h, e_h = employment.shift_bounds(sh) if scheduled else (None, None)
        roster.append({
            "id": e["id"], "kind": "npc", "name": e["name"], "role": e.get("role"),
            "scheduled": scheduled,
            "shift_start": employment.float_to_hhmm(s_h) if scheduled else None,
            "shift_end": employment.float_to_hhmm(e_h) if scheduled else None,
            "hourly_wage": npc_hourly_wage(e), "shift_hours": employment.worker_shift_hours(sh, opening),
            "on_shift": employment.on_shift_now(sh, opening, g_now),
        })
    for pe in pemps:
        sh = pe.get("schedule")
        scheduled = bool(sh)
        s_h, e_h = employment.shift_bounds(sh) if scheduled else (None, None)
        roster.append({
            "id": pe["id"], "kind": "player", "name": pe.get("employee_name") or "Player", "role": pe.get("role"),
            "scheduled": scheduled,
            "shift_start": employment.float_to_hhmm(s_h) if scheduled else None,
            "shift_end": employment.float_to_hhmm(e_h) if scheduled else None,
            "hourly_wage": pe.get("wage_per_hour") or round(pe.get("wage_per_shift", 60) / 4.0, 2),
            "shift_hours": employment.worker_shift_hours(sh, opening),
            "on_shift": employment.on_shift_now(sh, opening, g_now, parse_dt(pe.get("clocked_out_until"))),
        })
    daily_wage_total = round(sum(w["hourly_wage"] * w["shift_hours"] for w in roster), 2)

    allp = npcs + sick
    morale_avg = round(sum(e.get("morale", 60) for e in allp) / len(allp)) if allp else 0
    materials = b.get("materials") or {}
    mat_view = [{"id": r["id"], "name": r["name"], "qty": r.get("qty", 1), "cost": r.get("cost", 0),
                 "stock": round(materials.get(r["id"], 0), 1)} for r in _recipe(b)]
    return {
        "staffing": staffing, "coverage": coverage, "active_coverage": coverage,
        "base_slots": base_slots, "max_staff_slots": max_slots, "staff_count": staff_count,
        "concurrent_slots": max_slots,
        "max_hire_slots": base_slots * 3 + max(0, b.get("level", 1) - 1),
        "slots_free": max(0, (base_slots * 3 + max(0, b.get("level", 1) - 1)) - staff_count),
        "employee_count": len(npcs), "sick_count": len(sick), "applicant_count": applicants,
        "player_employee_count": len(pemps),
        # opening hours + shift coverage
        "opening_hours": {"open": employment.float_to_hhmm(o_h), "close": employment.float_to_hhmm(c_h)},
        "is_open_now": open_now, "open_hours": open_hours, "covered_hours": covered_hours,
        "coverage_hours_pct": round(min(1.0, covered_hours / open_hours) * 100) if open_hours else 100,
        "roster": roster, "daily_wage_total": daily_wage_total,
        "morale_avg": morale_avg, "satisfaction": round(b.get("satisfaction", 60)),
        # supply-chain P&L (per-day forecast)
        "rev_day": round(b.get("rev_day", 0), 2), "material_day": round(b.get("material_day", 0), 2),
        "wage_per_day": round(b.get("wages_day", 0), 2),
        "exp_day": round(b.get("material_day", 0) + b.get("wages_day", 0), 2),
        "net_day": round(b.get("net_day", 0), 2),
        "demand_day": round(b.get("demand_day", 0), 1), "produced_day": round(b.get("produced_day", 0), 1),
        "sold_day": round(b.get("sold_day", 0), 1), "capacity_day": round(b.get("capacity_day", 0), 1),
        "reputation": round(b.get("reputation", 50)),
        "reputation_demand_mult": reputation_mult(b), "satisfaction_production_mult": satisfaction_mult(b),
        "product": b.get("product") or {}, "recipe": _recipe(b),
        "material_cost_per_unit": material_cost_per_unit(b), "margin_per_unit": margin_per_unit(b),
        "effective_price": effective_price(b), "base_price": unit_price(b),
        "marketing_level": b.get("marketing_level", 0),
        "marketing_demand_pct": round((marketing_demand_mult(b) - 1) * 100),
        "marketing_price_pct": round((marketing_price_mult(b) - 1) * 100),
        "products_in_stock": round(b.get("products", 0), 1), "materials": mat_view,
        "auto_restock": b.get("auto_restock", True), "restock_target": b.get("restock_target", b.get("daily_demand", 0)),
    }


async def _create_applicant(db, p, cfg, b, reqs, premium=False):
    roles_doc = {r["id"]: r for r in await db.employee_roles.find({}, {"_id": 0}).to_list(100)}
    traits_all = await db.employee_traits.find({}, {"_id": 0}).to_list(100)
    pool = [r["role"] for r in reqs] or ["cashier"]
    if b.get("level", 1) >= 3 and "manager" in roles_doc and random.random() < 0.18:
        pool = pool + ["manager"]
    role = random.choice(pool)
    rd = roles_doc.get(role, {"wage_min": 80, "wage_max": 120})
    skill = random.randint(5, 9) if premium else random.choices([1, 2, 3, 4, 5, 6, 7], weights=[3, 4, 5, 4, 3, 2, 1])[0]
    n = 1 if premium else random.choices([0, 1, 2], weights=[3, 4, 3])[0]
    chosen = []
    if traits_all:
        if premium:
            good = [t for t in traits_all if t["effects"].get("revenue", 0) > 0 or t["effects"].get("satisfaction", 0) > 0]
            chosen = [random.choice(good or traits_all)["id"]]
        elif n:
            chosen = [t["id"] for t in random.sample(traits_all, min(n, len(traits_all)))]
    wmult = 1.0
    for t in chosen:
        wmult *= next((x["effects"].get("wage_mult", 1.0) for x in traits_all if x["id"] == t), 1.0)
    wage = round(random.uniform(rd.get("wage_min", 80), rd.get("wage_max", 120)) * wmult * (0.9 + 0.04 * skill))
    emp = {
        "id": uuid.uuid4().hex, "business_id": b["id"], "player_id": p["id"],
        "name": _gen_name(), "age": random.randint(18, 58), "role": role,
        "daily_wage": wage, "wage_per_hour": round(wage / NPC_EQUIV_HOURS, 2), "skill": skill,
        "reliability": random.randint(60, 95) if premium else random.randint(35, 85),
        "morale": random.randint(65, 85), "energy": random.randint(80, 100),
        "loyalty": random.randint(35, 60), "experience": 0.0, "traits": chosen,
        "status": "applicant", "wants_raise": False, "training": None, "sick_until": None,
        "schedule": employment.make_schedule("early"),
        "hire_date": None, "last_paid": None, "created_at": now_utc().isoformat(),
    }
    await db.employees.insert_one(emp)
    return emp


async def _generate_applicants(db, p, cfg, now, b, reqs, current_count):
    ecfg = cfg.get("employees", {})
    interval = ecfg.get("applicant_interval_hours", 6) * 3600
    maxa = ecfg.get("max_applicants", 6)
    last = parse_dt(b.get("last_applicant_at")) or parse_dt(b.get("created_at")) or now
    made = 0
    while current_count + made < maxa and (now - last).total_seconds() >= interval and made < 5:
        await _create_applicant(db, p, cfg, b, reqs, premium=False)
        last = last + timedelta(seconds=interval)
        made += 1
    if made > 0:
        b["last_applicant_at"] = last.isoformat()
        await add_event(db, b["player_id"], f"{made} new applicant(s) available at {b['name']}.", "business", "info", b["id"])
    elif not b.get("last_applicant_at"):
        b["last_applicant_at"] = now.isoformat()


async def _roll_event(db, b, active, has_manager, traits_map, changed, g_now=None):
    templates = await db.employee_events.find({}, {"_id": 0}).to_list(100)
    if not templates:
        return
    total = sum(t.get("weight", 1) for t in templates)
    r = random.uniform(0, total)
    acc = 0
    tpl = templates[-1]
    for t in templates:
        acc += t.get("weight", 1)
        if r <= acc:
            tpl = t
            break
    kind = tpl.get("kind")
    if kind == "manager_save" and not has_manager:
        return
    # Wage-raise requests are rate-limited: at most once per 7 in-game days per NPC.
    if kind == "raise_request":
        if not active:
            return
        e = random.choice(active)
        base = parse_dt(e.get("last_raise_request")) or parse_dt(e.get("hire_date"))
        cooldown_days = game_models.TUNE.get("raise_cooldown_days", 7)
        if g_now and base and (g_now - base) < timedelta(days=cooldown_days):
            return  # still on cooldown — no event, no spam
        e["wants_raise"] = True
        e["last_raise_request"] = (g_now or now_utc()).isoformat()
        changed.append(e)
        msg = tpl.get("message", "").replace("{name}", e["name"])
        await add_event(db, b["player_id"], f"[{b['name']}] {msg}", "business", tpl.get("severity", "info"), b["id"])
        return
    ef = tpl.get("effects", {})
    if "reputation" in ef:
        b["reputation"] = clamp(b.get("reputation", 50) + ef["reputation"])
    if "satisfaction" in ef:
        b["satisfaction"] = clamp(b.get("satisfaction", 60) + ef["satisfaction"])
    if "cash" in ef:
        b["cash"] = round(max(0, b.get("cash", 0) + ef["cash"]), 2)
    name = ""
    if kind == "staff_conflict" and active:
        for e in random.sample(active, min(2, len(active))):
            e["morale"] = clamp(e.get("morale", 60) - 8)
            changed.append(e)
    elif kind == "exp_boost" and active:
        e = random.choice(active)
        e["skill"] = min(10, round(e.get("skill", 3) + 1, 1))
        changed.append(e)
        name = e["name"]
    elif kind == "accident" and active:
        e = random.choice(active)
        e["morale"] = clamp(e.get("morale", 60) - 10)
        changed.append(e)
        name = e["name"]
    elif active:
        name = random.choice(active)["name"]
    msg = tpl.get("message", "").replace("{name}", name or "A staff member")
    await add_event(db, b["player_id"], f"[{b['name']}] {msg}", "business", tpl.get("severity", "info"), b["id"])


async def _npc_lifecycle(db, b, cfg, gh, now, traits_map, net_positive):
    """NPC morale / skill / quit / sick / theft / training / events (players unaffected here)."""
    bid = b["id"]
    ts = cfg["time_scale"]
    staff = await db.employees.find({"business_id": bid, "status": {"$in": ["active", "sick"]}}, {"_id": 0}).to_list(300)
    changed = []
    for e in staff:
        tr = e.get("training")
        if tr and parse_dt(tr["ends_at"]) <= now:
            fail = random.random() < tr.get("fail_chance", 0.15)
            e["skill"] = min(10, round(e.get("skill", 3) + tr.get("skill_gain", 2) * (0.3 if fail else 1.0), 1))
            e["morale"] = clamp(e.get("morale", 60) + tr.get("morale_gain", 5))
            e["loyalty"] = clamp(e.get("loyalty", 50) + tr.get("loyalty_gain", 3))
            e["training"] = None
            tail = "with little progress" if fail else "and improved"
            await add_event(db, b["player_id"], f"{e['name']} finished training ({tr.get('label','course')}) {tail}.", "business", "info", bid)
            changed.append(e)
        if e.get("status") == "sick" and e.get("sick_until") and parse_dt(e["sick_until"]) <= now:
            e["status"] = "active"
            e["sick_until"] = None
            await add_event(db, b["player_id"], f"{e['name']} recovered and is back at work.", "business", "info", bid)
            changed.append(e)
    active = [e for e in staff if e.get("status") == "active"]
    has_manager = any(e.get("role") == "manager" for e in active)
    if gh <= 0:
        for e in changed:
            await db.employees.update_one({"id": e["id"]}, {"$set": e})
        return
    for e in list(active):
        tmap = [traits_map.get(t, {}).get("effects", {}) for t in e.get("traits", [])]
        morale_drift = sum(td.get("morale_drift", 0) for td in tmap)
        target = (55 + (8 if net_positive else -6) + (8 if (has_manager and e["role"] != "manager") else 0)
                  + morale_drift * 5 + (e.get("loyalty", 50) - 50) * 0.08)
        cur = e.get("morale", 60)
        e["morale"] = clamp(cur + (target - cur) * min(1, 0.04 * gh))
        e["energy"] = clamp(e.get("energy", 80) + (85 - e.get("energy", 80)) * min(1, 0.05 * gh))
        learn = max((traits_map.get(t, {}).get("effects", {}).get("learning", 1.0) for t in e.get("traits", [])), default=1.0)
        e["experience"] = e.get("experience", 0) + gh * learn * (0.8 + e["energy"] / 250)
        thr = 80 * e.get("skill", 3)
        if e["experience"] >= thr and e.get("skill", 3) < 10:
            e["skill"] = round(e.get("skill", 3) + 1, 1)
            e["experience"] -= thr
            await add_event(db, b["player_id"], f"{e['name']} got better at the job (skill {e['skill']}).", "business", "info", bid)
        theft_rate = sum(td.get("theft", 0) for td in tmap) + (0.003 if e["morale"] < 30 else 0)
        if theft_rate > 0 and random.random() < theft_rate * gh:
            amt = round(random.uniform(20, 80) + unit_price(b) * 2)
            b["cash"] = round(max(0, b.get("cash", 0) - amt), 2)
            await add_event(db, b["player_id"], f"{e['name']} stole ${amt} from {b['name']}!", "business", "danger", bid)
        sick_rate = 0.0015 + sum(td.get("sick", 0) for td in tmap) + (0.004 if e["morale"] < 35 else 0)
        if random.random() < sick_rate * gh:
            e["status"] = "sick"
            e["sick_until"] = (now + timedelta(seconds=real_seconds(random.randint(480, 1440), ts))).isoformat()
            await add_event(db, b["player_id"], f"{e['name']} called in sick.", "business", "warning", bid)
            changed.append(e)
            active.remove(e)
            continue
        quit_rate = (0.0012 + sum(td.get("quit", 0) for td in tmap) + (0.01 if e["morale"] < 30 else 0)
                     + (0.005 if e.get("loyalty", 50) < 30 else 0))
        if random.random() < quit_rate * gh:
            e["status"] = "quit"
            await add_event(db, b["player_id"], f"{e['name']} quit {b['name']}.", "business", "warning", bid)
            changed.append(e)
            active.remove(e)
            continue
        changed.append(e)
    if random.random() < min(0.4, 0.05 * gh):
        await _roll_event(db, b, active, has_manager, traits_map, changed, g_now=game_now(cfg, now))
    seen = {e["id"]: e for e in changed}
    for e in seen.values():
        await db.employees.update_one({"id": e["id"]}, {"$set": e})


async def resolve_business(db, cfg, now, b):
    """Idempotent, business-clock-gated supply-chain resolver. SINGLE writer of the business doc.
    Buys materials -> workers produce -> product sold to demand -> wages paid. Profit = sales - materials - wages."""
    bid = b["id"]
    ts = cfg["time_scale"]
    b.setdefault("satisfaction", 60.0)
    b.setdefault("history", [])
    b.setdefault("materials", {})
    b.setdefault("products", 0.0)
    last = parse_dt(b.get("last_resolved_at")) or now
    gh = max(0.0, (now - last).total_seconds()) * ts / 3600.0
    g_last = game_now(cfg, last)
    g_now = game_now(cfg, now)
    traits_map = await _traits_map(db)
    reqs = await get_staffing(db, b)

    workers = await gather_workers(db, b, cfg, traits_map)
    slots = max(1, sum(r.get("recommended", 1) for r in reqs)) + (b.get("level", 1) - 1)  # concurrent capacity

    # --- business activity timers (upgrade / marketing campaign) ---
    upgrade_active = False
    act = b.get("activity")
    if act and not act.get("completed"):
        ends = parse_dt(act.get("ends_at"))
        if ends and now >= ends:
            t = act.get("type")
            if t == "upgrade" and b.get("level", 1) < b.get("max_level", 1):
                b["level"] = b.get("level", 1) + 1
                b["reputation"] = clamp(b.get("reputation", 50) + 4)
                await add_event(db, b["player_id"], f"Upgrade complete — {b['name']} is now level {b['level']} (+1 staff slot).", "business", "success", bid)
                await add_notification(db, b["player_id"], "business", "Upgrade complete", f"{b['name']} reached level {b['level']}. A new staff slot is unlocked.", "success", f"/businesses/{bid}")
            elif t == "marketing":
                b["marketing_level"] = b.get("marketing_level", 0) + 1
                b["reputation"] = clamp(b.get("reputation", 50) + 8)
                await add_event(db, b["player_id"], f"Marketing campaign live — {b['name']} demand & pricing boosted (marketing L{b['marketing_level']}).", "business", "success", bid)
                await add_notification(db, b["player_id"], "business", "Marketing campaign live", f"{b['name']}'s campaign rolled out. Revenue is up.", "success", f"/businesses/{bid}")
            b["activity"] = None
        elif act.get("type") == "upgrade":
            upgrade_active = True

    # --- actual cash flow for the elapsed window ---
    material_spend = 0.0
    revenue = 0.0
    wages = 0.0
    produced = 0.0
    sold = 0.0
    player_bookings = []  # (emp, wage, hours, productivity)
    if gh > 0:
        opening = b.get("opening_hours")
        scheds = [w["schedule"] for w in workers]
        covered = employment.effective_worker_hours_in_range(opening, scheds, slots, g_last, g_now)
        lvl_mult = 1 + 0.6 * (b.get("level", 1) - 1)
        for w in workers:
            whrs = employment.worker_hours_in_range(w["schedule"], opening, g_last, g_now, w["clocked_out_until"])
            if whrs <= 0.0001:
                continue
            wg = round(w["wage_per_hour"] * whrs, 2)
            wages += wg
            if w["is_player"]:
                player_bookings.append((w["emp"], wg, whrs, w["productivity"]))
        capacity = b.get("production_per_worker_hour", 0) * covered * satisfaction_mult(b) * lvl_mult
        # restock enough materials to cover this window's production (+buffer), auto if enabled
        if b.get("auto_restock", True) and capacity > 0:
            material_spend += _auto_restock(b, capacity, None)
        produced = _producible(b, capacity)
        if produced > 0:
            _consume(b, produced)
            b["products"] = round(b.get("products", 0) + produced, 3)
        # sell to demand
        mkt = marketing_demand_mult(b)
        rep = reputation_mult(b)
        lvl = 1 + 0.6 * (b.get("level", 1) - 1)
        demand_units = b.get("daily_demand", 0) * mkt * rep * lvl * gh / 24.0
        sold = min(b.get("products", 0), demand_units)
        if sold > 0:
            b["products"] = round(b.get("products", 0) - sold, 3)
            revenue = round(sold * effective_price(b) * (0.5 if upgrade_active else 1.0), 2)
            b["cash"] = round(b.get("cash", 0) + revenue, 2)
        # pay wages from business cash; shortfall becomes business debt (no bankruptcy)
        if wages > 0:
            if b.get("cash", 0) >= wages:
                b["cash"] = round(b.get("cash", 0) - wages, 2)
            else:
                short = wages - b.get("cash", 0)
                b["cash"] = 0.0
                b["debt"] = round(b.get("debt", 0) + short, 2)
        # credit player workers (idempotent per business window)
        for emp, wg, hrs, prod in player_bookings:
            gd = g_now.date().isoformat()
            today = emp.get("today") or {}
            if today.get("date") != gd:
                today = {"date": gd, "hours": 0.0, "wage": 0.0, "revenue": 0.0, "net": 0.0}
            u = round(b.get("production_per_worker_hour", 0) * prod * hrs, 2)
            rev_share = round(u * margin_per_unit(b), 2)
            today["hours"] = round(today["hours"] + hrs, 2)
            today["wage"] = round(today["wage"] + wg, 2)
            today["revenue"] = round(today["revenue"] + max(rev_share, 0), 2)
            today["net"] = round(today["net"] + rev_share, 2)
            await db.player_employment.update_one({"id": emp["id"]}, {
                "$inc": {"earnings_pending": wg, "personal_hours_pending": hrs,
                         "total_hours_worked": hrs, "total_wages_earned": wg,
                         "total_value_added": max(rev_share, 0)},
                "$set": {"today": today, "last_paid_at": now.isoformat(),
                         "last_impact": {"hours": round(hrs, 2), "wage": wg, "revenue": max(rev_share, 0),
                                         "net": rev_share, "productivity": prod, "at": now.isoformat()}}})

    # --- steady-state per-day forecast for the UI ---
    rates = _day_rates(b, workers, upgrade_penalty=0.5 if upgrade_active else 1.0, slots=slots)
    b.update({k: rates[k] for k in ("demand_day", "capacity_day", "produced_day", "sold_day",
                                    "rev_day", "material_day", "wages_day", "net_day")})
    b["exp_day"] = round(rates["material_day"] + rates["wages_day"], 2)

    # satisfaction + reputation drift from how well demand is met
    # SATISFACTION = team morale/efficiency: driven by opening-hour COVERAGE and worker quality (drives production)
    open_h = rates.get("open_hours", 0) or 0
    hour_coverage = min(1.0, (rates.get("covered_hours", 0) / open_h)) if open_h else 1.0
    avg_prod = (sum(w["productivity"] for w in workers) / len(workers)) if workers else 0.5
    sat_target = clamp(35 + 35 * hour_coverage + 40 * avg_prod)
    # REPUTATION = market reach: grows while you keep shelves stocked, fades on stock-outs (drives demand)
    met_demand = rates["sold_day"] >= rates["demand_day"] - 0.5
    in_stock = 1.0 if (b.get("products", 0) > 0.5 or met_demand) else 0.4
    rep_target = clamp(40 + 45 * in_stock)
    if gh > 0:
        b["satisfaction"] = clamp(b["satisfaction"] + (sat_target - b["satisfaction"]) * min(1, 0.05 * gh))
        b["reputation"] = clamp(b.get("reputation", 50) + (rep_target - b.get("reputation", 50)) * min(1, 0.015 * gh))
        if revenue or wages or material_spend:
            b["revenue_total"] = round(b.get("revenue_total", 0) + max(revenue, 0), 2)
            hist = b.get("history", [])
            net_window = round(revenue - material_spend - wages, 2)
            if not hist or (now - parse_dt(hist[-1]["ts"])).total_seconds() > 120:
                hist.append({"ts": now.isoformat(), "kind": "accrual", "amount": net_window,
                             "net": rates["net_day"], "rev": rates["rev_day"],
                             "material": rates["material_day"], "wages": rates["wages_day"],
                             "sold": round(sold, 1), "produced": round(produced, 1),
                             "cash": b["cash"], "debt": b.get("debt", 0)})
                b["history"] = hist[-60:]

    npcs_all = await db.employees.find({"business_id": bid, "status": {"$in": ["active", "sick"]}}, {"_id": 0}).to_list(300)
    b["morale_avg"] = round(sum(e.get("morale", 60) for e in npcs_all) / len(npcs_all)) if npcs_all else 0

    applicant_count = await db.employees.count_documents({"business_id": bid, "status": "applicant"})
    owner = await db.players.find_one({"id": b["player_id"]}, {"_id": 0, "id": 1})
    if owner:
        await _generate_applicants(db, {"id": b["player_id"], "name": ""}, cfg, now, b, reqs, applicant_count)
    await _npc_lifecycle(db, b, cfg, gh, now, traits_map, net_positive=rates["net_day"] >= 0)

    b["last_resolved_at"] = now.isoformat()
    await db.businesses.update_one({"id": bid}, {"$set": b})
