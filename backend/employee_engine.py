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


async def _traits_map(db):
    return {t["id"]: t for t in await db.employee_traits.find({}, {"_id": 0}).to_list(100)}


def _recipe(b):
    return b.get("recipe") or []


def material_cost_per_unit(b):
    return round(sum(r.get("qty", 1) * r.get("cost", 0) for r in _recipe(b)), 4)


def unit_price(b):
    return (b.get("product") or {}).get("price", 0)


def margin_per_unit(b):
    return round(unit_price(b) - material_cost_per_unit(b), 4)


async def gather_workers(db, b, cfg, traits_map=None):
    """Return the unified active-worker list for a business (NPCs + players)."""
    traits_map = traits_map if traits_map is not None else await _traits_map(db)
    workers = []
    npcs = await db.employees.find({"business_id": b["id"], "status": "active"}, {"_id": 0}).to_list(300)
    for e in npcs:
        cond = clamp(0.85 + 0.15 * ((e.get("morale", 60) + e.get("energy", 80)) / 200.0), 0.85, 1.05)
        prod = worker_productivity(e.get("skill", 3), e.get("reliability", 60), cond)
        for t in e.get("traits", []):
            prod *= (1 + traits_map.get(t, {}).get("effects", {}).get("revenue", 0))
        workers.append({
            "kind": "npc", "id": e["id"], "name": e["name"], "role": e.get("role"),
            "wage_per_hour": npc_hourly_wage(e), "schedule": e.get("schedule") or employment.make_schedule("early"),
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
        cond = clamp(0.85 + 0.15 * effectiveness(pl), 0.85, 1.05)
        prod = worker_productivity(skill_level, e.get("reliability", 60), cond)
        workers.append({
            "kind": "player", "id": e["id"], "name": e.get("employee_name") or pl["name"], "role": e.get("role"),
            "wage_per_hour": e.get("wage_per_hour") or round(e.get("wage_per_shift", 60) / 4.0, 2),
            "schedule": e.get("schedule") or employment.make_schedule("early"),
            "clocked_out_until": parse_dt(e.get("clocked_out_until")), "productivity": prod,
            "is_player": True, "emp": e, "player_id": pl["id"],
        })
    return workers


def _day_rates(b, workers):
    """Steady-state per-day P&L forecast (transparent; independent of tick size)."""
    pph = b.get("production_per_worker_hour", 0)
    mkt = 1 + 0.06 * b.get("marketing_level", 0)
    rep = 0.5 + 0.5 * (b.get("reputation", 50) / 100.0)
    lvl = 1 + 0.6 * (b.get("level", 1) - 1)
    demand_day = b.get("daily_demand", 0) * mkt * rep * lvl
    prod_hours_day = sum(w["productivity"] * employment.schedule_hours_per_day(w["schedule"]) for w in workers)
    capacity_day = pph * prod_hours_day
    sold_day = min(capacity_day, demand_day)
    mc = material_cost_per_unit(b)
    price = unit_price(b)
    rev_day = round(sold_day * price, 2)
    material_day = round(sold_day * mc, 2)
    wages_day = round(sum(w["wage_per_hour"] * employment.schedule_hours_per_day(w["schedule"]) for w in workers), 2)
    net_day = round(rev_day - material_day - wages_day, 2)
    return {
        "demand_day": round(demand_day, 1), "capacity_day": round(capacity_day, 1),
        "produced_day": round(sold_day, 1), "sold_day": round(sold_day, 1),
        "rev_day": rev_day, "material_day": material_day,
        "wages_day": wages_day, "net_day": net_day,
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

    npc_by_role, npc_active_by_role = {}, {}
    for e in npcs:
        r = e.get("role")
        npc_by_role[r] = npc_by_role.get(r, 0) + 1
        if employment.emp_on_shift({**e, "status": "active"}, g_now):
            npc_active_by_role[r] = npc_active_by_role.get(r, 0) + 1
    p_by_role, p_active_by_role = {}, {}
    for pe in pemps:
        r = pe.get("role")
        p_by_role[r] = p_by_role.get(r, 0) + 1
        if employment.emp_on_shift(pe, g_now):
            p_active_by_role[r] = p_active_by_role.get(r, 0) + 1

    staffing, active_ratios = [], []
    for r in reqs:
        rec = r.get("recommended", 1)
        assigned = npc_by_role.get(r["role"], 0) + p_by_role.get(r["role"], 0)
        active = npc_active_by_role.get(r["role"], 0) + p_active_by_role.get(r["role"], 0)
        if active > 0:
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

    base_slots = max(1, sum(r.get("recommended", 1) for r in reqs))
    max_slots = base_slots + (b.get("level", 1) - 1)
    staff_count = len(npcs) + len(sick) + len(pemps)

    allp = npcs + sick
    morale_avg = round(sum(e.get("morale", 60) for e in allp) / len(allp)) if allp else 0
    materials = b.get("materials") or {}
    mat_view = [{"id": r["id"], "name": r["name"], "qty": r.get("qty", 1), "cost": r.get("cost", 0),
                 "stock": round(materials.get(r["id"], 0), 1)} for r in _recipe(b)]
    return {
        "staffing": staffing, "coverage": coverage, "active_coverage": coverage,
        "base_slots": base_slots, "max_staff_slots": max_slots, "staff_count": staff_count,
        "slots_free": max(0, max_slots - staff_count),
        "employee_count": len(npcs), "sick_count": len(sick), "applicant_count": applicants,
        "player_employee_count": len(pemps),
        "morale_avg": morale_avg, "satisfaction": round(b.get("satisfaction", 60)),
        # supply-chain P&L (per-day forecast)
        "rev_day": round(b.get("rev_day", 0), 2), "material_day": round(b.get("material_day", 0), 2),
        "wage_per_day": round(b.get("wages_day", 0), 2),
        "exp_day": round(b.get("material_day", 0) + b.get("wages_day", 0), 2),
        "net_day": round(b.get("net_day", 0), 2),
        "demand_day": round(b.get("demand_day", 0), 1), "produced_day": round(b.get("produced_day", 0), 1),
        "sold_day": round(b.get("sold_day", 0), 1),
        "product": b.get("product") or {}, "recipe": _recipe(b),
        "material_cost_per_unit": material_cost_per_unit(b), "margin_per_unit": margin_per_unit(b),
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


async def _roll_event(db, b, active, has_manager, traits_map, changed):
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
    elif kind == "raise_request" and active:
        e = random.choice(active)
        e["wants_raise"] = True
        changed.append(e)
        name = e["name"]
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
    if random.random() < min(0.5, 0.04 * gh + 0.015):
        await _roll_event(db, b, active, has_manager, traits_map, changed)
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

    # --- actual cash flow for the elapsed window ---
    material_spend = 0.0
    revenue = 0.0
    wages = 0.0
    produced = 0.0
    sold = 0.0
    player_bookings = []  # (emp, wage, hours, productivity)
    if gh > 0:
        labor_hours = 0.0
        for w in workers:
            hrs = employment.active_hours_in_range(w["schedule"], g_last, g_now, w["clocked_out_until"])
            if hrs <= 0.0001:
                continue
            labor_hours += hrs * w["productivity"]
            wg = round(w["wage_per_hour"] * hrs, 2)
            wages += wg
            if w["is_player"]:
                player_bookings.append((w["emp"], wg, hrs, w["productivity"]))
        capacity = b.get("production_per_worker_hour", 0) * labor_hours
        # restock enough materials to cover this window's production (+buffer), auto if enabled
        if b.get("auto_restock", True) and capacity > 0:
            material_spend += _auto_restock(b, capacity, None)
        produced = _producible(b, capacity)
        if produced > 0:
            _consume(b, produced)
            b["products"] = round(b.get("products", 0) + produced, 3)
        # sell to demand
        mkt = 1 + 0.06 * b.get("marketing_level", 0)
        rep = 0.5 + 0.5 * (b.get("reputation", 50) / 100.0)
        lvl = 1 + 0.6 * (b.get("level", 1) - 1)
        demand_units = b.get("daily_demand", 0) * mkt * rep * lvl * gh / 24.0
        sold = min(b.get("products", 0), demand_units)
        if sold > 0:
            b["products"] = round(b.get("products", 0) - sold, 3)
            revenue = round(sold * unit_price(b), 2)
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
    rates = _day_rates(b, workers)
    b.update({k: rates[k] for k in ("demand_day", "capacity_day", "produced_day", "sold_day",
                                    "rev_day", "material_day", "wages_day", "net_day")})
    b["exp_day"] = round(rates["material_day"] + rates["wages_day"], 2)

    # satisfaction + reputation drift from how well demand is met
    fill = rates["sold_day"] / rates["demand_day"] if rates["demand_day"] > 0 else 1.0
    avg_prod = (sum(w["productivity"] for w in workers) / len(workers)) if workers else 0.6
    sat_target = clamp(45 + 40 * fill + (avg_prod - 0.8) * 30)
    if gh > 0:
        b["satisfaction"] = clamp(b["satisfaction"] + (sat_target - b["satisfaction"]) * min(1, 0.05 * gh))
        b["reputation"] = clamp(b.get("reputation", 50) + (b["satisfaction"] - b.get("reputation", 50)) * min(1, 0.03 * gh))
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
