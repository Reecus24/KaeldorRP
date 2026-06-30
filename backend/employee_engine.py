"""Kaeldor RPG - NPC employee system: applicant generation, staffing,
morale/wages/sick/quit/theft/training resolution, and employee-driven business P&L.
All time-based effects resolve on offline catch-up via resolve_business()."""
import uuid
import random
from datetime import timedelta

from game_models import clamp, now_utc
from game_engine import add_event, parse_dt, real_seconds, ledger_add, add_notification


FIRST_NAMES = [
    "Mara", "Dex", "Lena", "Cyrus", "Nadia", "Theo", "Vera", "Rafe", "Iris", "Kai",
    "Sasha", "Bram", "Noor", "Dario", "Petra", "Ezra", "Lila", "Cato", "Maya", "Finn",
    "Zara", "Otto", "Juno", "Milo", "Greta", "Levi", "Anya", "Ravi", "Esme", "Tomas",
]
LAST_NAMES = [
    "Voss", "Kade", "Mercer", "Sato", "Okafor", "Rios", "Halloran", "Nikolai", "Dubois", "Reyes",
    "Cohen", "Ashby", "Варga", "Lindqvist", "Petrov", "Okonkwo", "Bauer", "Costa", "Ferro", "Salim",
]


def _gen_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


async def get_staffing(db, b):
    doc = await db.staffing_requirements.find_one({"id": b.get("type_id")}, {"_id": 0})
    return (doc or {}).get("requirements", [])


async def _traits_map(db):
    return {t["id"]: t for t in await db.employee_traits.find({}, {"_id": 0}).to_list(100)}


async def business_metrics(db, b):
    """Read-only staffing/financial snapshot used by API responses."""
    reqs = await get_staffing(db, b)
    actives = await db.employees.find({"business_id": b["id"], "status": "active"}, {"_id": 0}).to_list(300)
    sick = await db.employees.find({"business_id": b["id"], "status": "sick"}, {"_id": 0}).to_list(300)
    applicants = await db.employees.count_documents({"business_id": b["id"], "status": "applicant"})
    by_role = {}
    for e in actives:
        by_role[e["role"]] = by_role.get(e["role"], 0) + 1
    staffing, ratios, missing = [], [], 0
    for r in reqs:
        rec = r.get("recommended", 1)
        have = by_role.get(r["role"], 0)
        staffing.append({"role": r["role"], "have": have, "recommended": rec})
        ratios.append(min(1, have / rec) if rec else 1)
        if have == 0 and rec > 0:
            missing += 1
    coverage = sum(ratios) / len(ratios) if ratios else 1.0
    allp = actives + sick
    morale_avg = round(sum(e.get("morale", 60) for e in allp) / len(allp)) if allp else 0
    wage_day = round(sum(e.get("daily_wage", 0) for e in allp), 2)
    risk = clamp((b.get("debt", 0) / max(1, b.get("purchase_price", 1) * 0.85)) * 100)
    return {
        "staffing": staffing, "coverage": round(coverage, 2), "missing_roles": missing,
        "employee_count": len(actives), "sick_count": len(sick), "applicant_count": applicants,
        "morale_avg": morale_avg, "wage_per_day": wage_day,
        "satisfaction": round(b.get("satisfaction", 60)),
        "rev_day": round(b.get("rev_day", b.get("base_revenue_per_day", 0)), 2),
        "exp_day": round(b.get("exp_day", 0), 2),
        "net_day": round(b.get("last_net_day", 0), 2),
        "bankruptcy_risk": round(risk),
    }


async def _create_applicant(db, p, cfg, b, reqs, premium=False):
    roles_doc = {r["id"]: r for r in await db.employee_roles.find({}, {"_id": 0}).to_list(100)}
    traits_all = await db.employee_traits.find({}, {"_id": 0}).to_list(100)
    pool = [r["role"] for r in reqs] or ["cashier"]
    if b.get("level", 1) >= 3 and "manager" in roles_doc and random.random() < 0.18:
        pool = pool + ["manager"]
    role = random.choice(pool)
    rd = roles_doc.get(role, {"wage_min": 80, "wage_max": 120})
    if premium:
        skill = random.randint(5, 9)
    else:
        skill = random.choices([1, 2, 3, 4, 5, 6, 7], weights=[3, 4, 5, 4, 3, 2, 1])[0]
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
        "daily_wage": wage, "skill": skill,
        "reliability": random.randint(60, 95) if premium else random.randint(35, 85),
        "morale": random.randint(65, 85), "energy": random.randint(80, 100),
        "loyalty": random.randint(35, 60), "experience": 0.0, "traits": chosen,
        "status": "applicant", "wants_raise": False, "training": None, "sick_until": None,
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
        await add_event(db, p["id"], f"{made} new applicant(s) available at {b['name']}.", "business", "info", b["id"])
    elif not b.get("last_applicant_at"):
        b["last_applicant_at"] = now.isoformat()


async def _roll_event(db, p, b, active, has_manager, traits_map, changed):
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
    elif kind == "customer_favorite" and active:
        e = random.choice(active)
        if "customer_favorite" not in e.get("traits", []):
            e.setdefault("traits", []).append("customer_favorite")
        e["morale"] = clamp(e.get("morale", 60) + 6)
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
    await add_event(db, p["id"], f"[{b['name']}] {msg}", "business", tpl.get("severity", "info"), b["id"])


async def resolve_business(db, p, cfg, gh, now, b):
    bid = b["id"]
    ts = cfg["time_scale"]
    b.setdefault("satisfaction", 60.0)
    b.setdefault("history", [])
    staff = await db.employees.find({"business_id": bid, "status": {"$in": ["active", "sick"]}}, {"_id": 0}).to_list(300)
    applicant_count = await db.employees.count_documents({"business_id": bid, "status": "applicant"})
    reqs = await get_staffing(db, b)
    traits_map = await _traits_map(db)
    changed = []

    # training completion + sick recovery (absolute time, runs even when gh==0)
    for e in staff:
        tr = e.get("training")
        if tr and parse_dt(tr["ends_at"]) <= now:
            fail = random.random() < tr.get("fail_chance", 0.15)
            e["skill"] = min(10, round(e.get("skill", 3) + tr.get("skill_gain", 2) * (0.3 if fail else 1.0), 1))
            e["morale"] = clamp(e.get("morale", 60) + tr.get("morale_gain", 5))
            e["loyalty"] = clamp(e.get("loyalty", 50) + tr.get("loyalty_gain", 3))
            e["training"] = None
            tail = "with little progress" if fail else "and improved"
            await add_event(db, p["id"], f"{e['name']} finished training ({tr.get('label','course')}) {tail}.", "business", "info", bid)
            changed.append(e)
        if e.get("status") == "sick" and e.get("sick_until") and parse_dt(e["sick_until"]) <= now:
            e["status"] = "active"
            e["sick_until"] = None
            await add_event(db, p["id"], f"{e['name']} recovered and is back at work.", "business", "info", bid)
            changed.append(e)

    active = [e for e in staff if e.get("status") == "active"]
    sicklist = [e for e in staff if e.get("status") == "sick"]
    has_manager = any(e["role"] == "manager" for e in active)

    by_role = {}
    for e in active:
        by_role[e["role"]] = by_role.get(e["role"], 0) + 1
    ratios, missing = [], 0
    for r in reqs:
        rec = r.get("recommended", 1)
        have = by_role.get(r["role"], 0)
        ratios.append(min(1, have / rec) if rec else 1)
        if have == 0 and rec > 0:
            missing += 1
    avg_ratio = sum(ratios) / len(ratios) if ratios else 1.0
    final_staff = max(0.35, avg_ratio) * (0.85 ** missing)

    if active:
        quality = sum(clamp(0.25 + 0.6 * (e.get("skill", 3) / 10) + 0.15 * (e.get("morale", 60) / 100), 0.2, 1.2) for e in active) / len(active)
    else:
        quality = 0.6
    rev_tmult, sat_delta = 1.0, 0.0
    for e in active:
        for t in e.get("traits", []):
            td = traits_map.get(t, {}).get("effects", {})
            rev_tmult *= (1 + td.get("revenue", 0))
            sat_delta += td.get("satisfaction", 0)
    rev_tmult = max(0.6, min(1.6, rev_tmult))
    manager_mult = 1.08 if has_manager else 1.0

    level = b.get("level", 1)
    mkt = 1 + 0.06 * b.get("marketing_level", 0)
    rep_factor = 0.55 + 0.45 * (b.get("reputation", 50) / 100)
    staff_mult = (0.5 + 0.5 * final_staff) * (0.7 + 0.3 * quality) * rev_tmult * manager_mult

    sat_target = clamp(40 + 45 * final_staff + 0.15 * (quality * 100 - 70) + sat_delta + (5 if has_manager else 0) + 2 * level)
    b["satisfaction"] = clamp(b["satisfaction"] + (sat_target - b["satisfaction"]) * min(1, 0.05 * max(gh, 0)))
    sat_factor = 0.7 + 0.3 * (b["satisfaction"] / 100)

    wages_day = round(sum(e.get("daily_wage", 0) for e in (active + sicklist)), 2)
    rev_day = b.get("base_revenue_per_day", 0) * (1 + 0.35 * (level - 1)) * mkt * rep_factor * staff_mult * sat_factor
    exp_day = b.get("base_expenses_per_day", 0) * (1 + 0.2 * (level - 1)) + b.get("rent_per_day", 0) + wages_day
    net_day = rev_day - exp_day
    b["rev_day"] = round(rev_day, 2)
    b["exp_day"] = round(exp_day, 2)
    b["wages_day"] = wages_day
    b["last_net_day"] = round(net_day, 2)
    b["coverage"] = round(final_staff, 2)
    allp = active + sicklist
    b["morale_avg"] = round(sum(e.get("morale", 60) for e in allp) / len(allp)) if allp else 0

    unpaid = False
    if gh > 0 and not b.get("bankrupt"):
        delta = net_day * gh / 24.0
        b["cash"] = round(b.get("cash", 0) + delta, 2)
        ledger_add(p, "business_pnl", round(delta, 2))
        ledger_add(p, "employee_wages", -round(wages_day * gh / 24.0, 2))
        b["revenue_total"] = round(b.get("revenue_total", 0) + max(rev_day, 0) * gh / 24.0, 2)
        if b["cash"] < 0:
            b["debt"] = round(b.get("debt", 0) - b["cash"], 2)
            b["cash"] = 0.0
            if wages_day > 0:
                unpaid = True
        b["reputation"] = clamp(b.get("reputation", 50) + (b["satisfaction"] - b.get("reputation", 50)) * min(1, 0.03 * gh))
        hist = b.get("history", [])
        if not hist or (now - parse_dt(hist[-1]["ts"])).total_seconds() > 120:
            hist.append({"ts": now.isoformat(), "net": round(net_day, 2), "rev": round(rev_day, 2),
                         "exp": round(exp_day, 2), "cash": b["cash"], "debt": b.get("debt", 0)})
            b["history"] = hist[-40:]

    if gh > 0 and not b.get("bankrupt"):
        for e in list(active):
            tmap = [traits_map.get(t, {}).get("effects", {}) for t in e.get("traits", [])]
            morale_drift = sum(td.get("morale_drift", 0) for td in tmap)
            target = (50 + (10 if not unpaid else -22) + (8 if (has_manager and e["role"] != "manager") else 0)
                      + (8 if net_day > 0 else -6)
                      + (5 if final_staff > 0.9 else (-8 if final_staff < 0.6 else 0))
                      + morale_drift * 5 + (e.get("loyalty", 50) - 50) * 0.08)
            cur = e.get("morale", 60)
            e["morale"] = clamp(cur + (target - cur) * min(1, 0.04 * gh))
            etarget = 90 if final_staff > 0.8 else 55
            e["energy"] = clamp(e.get("energy", 80) + (etarget - e.get("energy", 80)) * min(1, 0.05 * gh))
            learn = max((traits_map.get(t, {}).get("effects", {}).get("learning", 1.0) for t in e.get("traits", [])), default=1.0)
            e["experience"] = e.get("experience", 0) + gh * learn * (0.8 + e["energy"] / 250)
            thr = 80 * e.get("skill", 3)
            if e["experience"] >= thr and e.get("skill", 3) < 10:
                e["skill"] = round(e.get("skill", 3) + 1, 1)
                e["experience"] -= thr
                await add_event(db, p["id"], f"{e['name']} got better at the job (skill {e['skill']}).", "business", "info", bid)
            theft_rate = sum(td.get("theft", 0) for td in tmap) + (0.003 if e["morale"] < 30 else 0)
            if theft_rate > 0 and random.random() < theft_rate * gh:
                amt = round(random.uniform(20, 80) + b.get("base_revenue_per_day", 0) * 0.05)
                b["cash"] = round(max(0, b.get("cash", 0) - amt), 2)
                await add_event(db, p["id"], f"{e['name']} stole ${amt} from {b['name']}!", "business", "danger", bid)
            sick_rate = 0.0015 + sum(td.get("sick", 0) for td in tmap) + (0.004 if e["morale"] < 35 else 0) + (0.004 if e["energy"] < 30 else 0)
            if random.random() < sick_rate * gh:
                e["status"] = "sick"
                e["sick_until"] = (now + timedelta(seconds=real_seconds(random.randint(480, 1440), ts))).isoformat()
                await add_event(db, p["id"], f"{e['name']} called in sick.", "business", "warning", bid)
                active.remove(e)
                changed.append(e)
                continue
            quit_rate = (0.0015 + sum(td.get("quit", 0) for td in tmap) + (0.01 if e["morale"] < 30 else 0)
                         + (0.012 if unpaid else 0) + (0.005 if e.get("loyalty", 50) < 30 else 0))
            if random.random() < quit_rate * gh:
                e["status"] = "quit"
                await add_event(db, p["id"], f"{e['name']} quit {b['name']}.", "business", "warning", bid)
                active.remove(e)
                changed.append(e)
                continue
            changed.append(e)
        if unpaid:
            await add_event(db, p["id"], f"You couldn't cover wages at {b['name']} — staff morale is dropping.", "business", "danger", bid)
        if random.random() < min(0.5, 0.04 * gh + 0.015):
            await _roll_event(db, p, b, active, has_manager, traits_map, changed)

    await _generate_applicants(db, p, cfg, now, b, reqs, applicant_count)

    if b.get("debt", 0) > b.get("purchase_price", 1) * 0.85 and not b.get("bankrupt"):
        b["bankrupt"] = True
        await add_event(db, p["id"], f"Your business '{b['name']}' went BANKRUPT under crushing debt.", "business", "danger", bid)
        await add_notification(db, p["id"], "business", "Business bankrupt", f"'{b['name']}' has gone bankrupt under its debt.", "danger", f"/businesses/{bid}")

    seen = {}
    for e in changed:
        seen[e["id"]] = e
    for e in seen.values():
        await db.employees.update_one({"id": e["id"]}, {"$set": e})
    await db.businesses.update_one({"id": bid}, {"$set": b})
