"""Kaeldor RPG - employment: stat-based NPC job applications + player-owned business hiring.

NPC applications: apply -> resolves after a real-time delay -> accepted (with a
stat-based wage offer) or rejected (with a reason). Accepting an offer starts the job.

Player employment: players apply to other players' businesses; owners send wage
offers; accepted players work real-time shifts that pay wages and boost the business.
All time-based resolution is offline-safe (driven from resolve_player).
"""
import uuid
import random
from datetime import timedelta
from game_models import now_utc, clamp
from game_engine import (parse_dt, add_event, add_notification, charge, add_money, ledger_add,
                         game_now, effectiveness, add_skill_xp)


# ----------------------------- shared stat helpers -----------------------------
def _relevant_skills(job):
    return list((job.get("skill_xp") or {}).keys()) or ["fitness"]


def _avg(vals):
    return sum(vals) / len(vals) if vals else 0


def _top_skills(p, n=3):
    lvls = sorted((s.get("level", 1) for s in p["skills"].values()), reverse=True)
    return lvls[:n]


def shift_performance(p):
    """0.3..1.5 multiplier from a player's skills + condition."""
    avg = _avg(_top_skills(p))  # 1..10
    base = 0.5 + (avg - 1) / 9 * 0.6
    cond = (p["health"] + p["energy"] + (100 - p["fatigue"]) + p["mood"] + p["hygiene"]) / 500.0
    return round(clamp(base * (0.6 + 0.6 * cond), 0.3, 1.5), 2)


# maps a business staffing role -> the player skill that makes someone good at it
ROLE_SKILL = {
    "cashier": "sales", "cook": "cooking", "server": "charisma", "delivery_driver": "driving",
    "cleaner": "fitness", "mechanic": "crafting", "salesperson": "sales", "manager": "management",
    "security": "fitness", "warehouse_worker": "fitness", "customer_support": "charisma",
    "accountant": "finance", "trainer": "fitness", "animal_care": "fitness",
}


def role_fit(p, role):
    """0.55..1.3 — how well a player's relevant skill fits a business role."""
    sk = ROLE_SKILL.get(role)
    lvl = p["skills"].get(sk, {}).get("level", 1) if sk else _avg(_top_skills(p))
    return round(clamp(0.55 + (lvl - 1) / 9 * 0.75, 0.55, 1.3), 2)


# ----------------------------- scheduled working hours -----------------------------
SHIFT_PRESETS = {
    "early":   {"label": "Early Shift", "start": 8,  "end": 16},
    "late":    {"label": "Late Shift",  "start": 14, "end": 22},
    "night":   {"label": "Night Shift", "start": 22, "end": 6},
    "morning": {"label": "Part-Time Morning", "start": 8, "end": 12},
    "evening": {"label": "Part-Time Evening", "start": 18, "end": 22},
}
DEFAULT_SHIFT = "early"


def make_schedule(preset):
    key = preset if preset in SHIFT_PRESETS else DEFAULT_SHIFT
    pr = SHIFT_PRESETS[key]
    return {"preset": key, "label": pr["label"], "start": pr["start"], "end": pr["end"]}


def _hours_in_window(start_h, end_h, g):
    h = g.hour + g.minute / 60.0
    if end_h > start_h:
        return start_h <= h < end_h
    return h >= start_h or h < end_h  # wraps past midnight


def current_window_bounds(schedule, g):
    """(window_start, window_end) datetimes for the shift window containing game-time g, else None."""
    start_h, end_h = schedule.get("start", 8), schedule.get("end", 16)
    day0 = g.replace(hour=0, minute=0, second=0, microsecond=0)
    for off in (-1, 0):
        d = day0 + timedelta(days=off)
        ws = d + timedelta(hours=start_h)
        we = d + timedelta(hours=end_h if end_h > start_h else end_h + 24)
        if ws <= g < we:
            return ws, we
    return None


def emp_on_shift(emp, g_now):
    """True if a player employee is inside their scheduled hours right now (and hasn't clocked out)."""
    if emp.get("status") != "active":
        return False
    sch = emp.get("schedule")
    if not sch:
        return False
    if not _hours_in_window(sch.get("start", 8), sch.get("end", 16), g_now):
        return False
    co = parse_dt(emp.get("clocked_out_until"))
    if co and g_now < co:
        return False
    return True


def active_hours_in_range(schedule, g_start, g_end, clocked_out_until=None):
    """Game-hours within [g_start, g_end] that fall inside the recurring daily shift window."""
    if g_end <= g_start:
        return 0.0
    start_h, end_h = schedule.get("start", 8), schedule.get("end", 16)
    span = 0.0
    day = (g_start - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_day = (g_end + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    while day <= end_day:
        ws = day + timedelta(hours=start_h)
        we = day + timedelta(hours=end_h if end_h > start_h else end_h + 24)
        lo, hi = max(ws, g_start), min(we, g_end)
        if clocked_out_until and clocked_out_until > lo:
            lo = clocked_out_until
        if hi > lo:
            span += (hi - lo).total_seconds() / 3600.0
        day += timedelta(days=1)
    return round(span, 4)


# ----------------------------- NPC job applications -----------------------------
def application_delay_minutes(job, cfg):
    e = cfg.get("employment", {})
    return e.get("npc_app_base_minutes", 10) + (job.get("tier", 1) - 1) * e.get("npc_app_tier_minutes", 12)


def evaluate_application(p, job, cfg, boss_rel=0, mentor_rel=0):
    e = cfg.get("employment", {})
    base = job["hourly_wage"]
    skills = _relevant_skills(job)
    skill_lvl = _avg([p["skills"].get(s, {}).get("level", 1) for s in skills])
    skill_bonus = clamp((skill_lvl - 2) * 0.05, -0.1, 0.4)
    edu_bonus = min(0.25, 0.06 * len(p.get("education", [])))
    rep_bonus = (p["reputation"] - 50) / 250.0
    reliability = (p.get("job") or {}).get("reliability", 50)
    rel_bonus = (reliability - 50) / 400.0
    ref_bonus = max(0.0, max(boss_rel, mentor_rel) / 100.0) * 0.15
    crime_pen = (50 - p["legal_reputation"]) / 200.0 if p["legal_reputation"] < 50 else 0.0
    health_pen = (50 - p["health"]) / 300.0 if p["health"] < 50 else 0.0

    mult = clamp(1 + skill_bonus + edu_bonus + rep_bonus + rel_bonus + ref_bonus - crime_pen - health_pen,
                 e.get("wage_min_mult", 0.7), e.get("wage_max_mult", 1.85))
    wage = round(base * mult, 2)

    score = max(0.03, min(0.97, 0.5 + skill_bonus + edu_bonus + rep_bonus * 1.5 + rel_bonus * 2 + ref_bonus * 2 - crime_pen * 2 - health_pen))
    accepted = random.random() < score

    reason = None
    if not accepted:
        factors = []
        if crime_pen > 0.05:
            factors.append(("your criminal record", crime_pen * 2))
        if skill_lvl < 3:
            factors.append((f"low {skills[0]} skill", 0.35))
        if p["reputation"] < 45:
            factors.append(("poor reputation", (45 - p["reputation"]) / 50))
        if reliability < 45:
            factors.append(("a weak work history", (45 - reliability) / 50))
        if p["health"] < 45:
            factors.append(("poor health", health_pen * 3))
        if not factors:
            factors.append(("a stronger candidate was chosen", 0.2))
        reason = max(factors, key=lambda x: x[1])[0]
    return {"wage": wage, "accepted": accepted, "reason": reason, "mult": round(mult, 2)}


async def resolve_npc_applications(db, p, cfg, now):
    pending = await db.applications.find({"player_id": p["id"], "status": "pending"}, {"_id": 0}).to_list(50)
    for a in pending:
        ra = parse_dt(a.get("resolves_at"))
        if not ra or ra > now:
            continue
        job = await db.jobs.find_one({"id": a["job_id"]}, {"_id": 0})
        if not job:
            await db.applications.update_one({"id": a["id"]}, {"$set": {"status": "expired"}})
            continue
        boss = await db.contacts.find_one({"player_id": p["id"], "key": "boss"}, {"_id": 0})
        mentor = await db.contacts.find_one({"player_id": p["id"], "relationship_type": "mentor"}, {"_id": 0})
        ev = evaluate_application(p, job, cfg, boss.get("relationship_score", 0) if boss else 0,
                                  mentor.get("relationship_score", 0) if mentor else 0)
        if ev["accepted"]:
            upd = {"status": "accepted", "wage_offer": ev["wage"], "reason": "Offer extended", "resolved": True,
                   "offer_expires_at": (now + timedelta(hours=cfg.get("employment", {}).get("offer_expiry_hours", 24))).isoformat()}
            await add_event(db, p["id"], f"Your application for {job['title']} was ACCEPTED — offer ${ev['wage']}/h.", "job", "success")
            await add_notification(db, p["id"], "job", "Application accepted", f"{job['title']} — ${ev['wage']}/h. Accept the offer to start working.", "success", "/jobs")
        else:
            upd = {"status": "rejected", "reason": ev["reason"], "resolved": True}
            await add_event(db, p["id"], f"Your application for {job['title']} was rejected: {ev['reason']}.", "job", "warning")
            await add_notification(db, p["id"], "job", "Application rejected", f"{job['title']}: {ev['reason']}.", "warning", "/jobs")
        await db.applications.update_one({"id": a["id"]}, {"$set": upd})

    accepted = await db.applications.find({"player_id": p["id"], "status": "accepted"}, {"_id": 0}).to_list(50)
    for a in accepted:
        oe = parse_dt(a.get("offer_expires_at"))
        if oe and oe < now:
            await db.applications.update_one({"id": a["id"]}, {"$set": {"status": "expired"}})
            await add_notification(db, p["id"], "job", "Offer expired", f"The {a['title']} offer expired.", "warning", "/jobs")


# ----------------------------- player-owned business hiring -----------------------------
def recommend_wage(applicant, cfg, role=None):
    """Recommended HOURLY wage for a player applicant (hourly is the source of truth)."""
    e = cfg.get("employment", {})
    base = e.get("player_base_hourly_wage", 14)
    avg = _avg(_top_skills(applicant))
    fit_lvl = 0
    if role and ROLE_SKILL.get(role):
        fit_lvl = applicant["skills"].get(ROLE_SKILL[role], {}).get("level", 1)
    skill_level = max(avg, fit_lvl)
    mult = clamp(0.8 + (skill_level - 2) * 0.05 + (applicant.get("reputation", 50) - 50) / 300.0, 0.7, 1.7)
    return round(base * mult, 2)


def applicant_snapshot(p, cfg, role=None, reqs=None):
    top = sorted(p["skills"].items(), key=lambda kv: kv[1].get("level", 1), reverse=True)[:3]
    fit = round(role_fit(p, role), 2) if role else None
    fit_skill = ROLE_SKILL.get(role) if role else None
    fit_label = "great fit" if (fit and fit >= 1.05) else ("good fit" if (fit and fit >= 0.85) else ("weak fit" if fit else None))
    meets = True
    if reqs:
        req_roles = {r["role"] for r in reqs}
        meets = (role in req_roles) if role else False
    return {
        "name": p["name"], "level": p.get("level", 1), "reputation": round(p.get("reputation", 50)),
        "legal_reputation": round(p.get("legal_reputation", 100)),
        "criminal_warning": p.get("legal_reputation", 100) < 50,
        "top_skills": [{"skill": k, "level": v.get("level", 1)} for k, v in top],
        "education_count": len(p.get("education", [])),
        "role_fit": fit, "fit_skill": fit_skill, "fit_label": fit_label, "role_matches_staffing": meets,
        "recommended_wage": recommend_wage(p, cfg, role),
    }


# ----------------------------- contribution projection ($/h) -----------------------------
def worker_productivity(perf, fit, reliability, trait_mult=1.0):
    """Unified productivity multiplier (same basis as live auto-work accrual)."""
    return round(clamp(perf * fit * (0.8 + 0.4 * reliability / 100) * trait_mult, 0.2, 1.9), 2)


def projection_at(hourly_wage, productivity, output_mult):
    rev = round(hourly_wage * output_mult * productivity, 2)
    return {"productivity": productivity, "wage_per_hour": round(hourly_wage, 2),
            "rev_per_hour": rev, "net_per_hour": round(rev - hourly_wage, 2)}


def player_perf(p):
    """Condition + skill performance factor for a player (mirrors auto-work)."""
    return round(shift_performance(p) * effectiveness(p), 2)


def applicant_projection(p, cfg, roles, reliability=60):
    """Per-role productivity map for a player applicant; frontend computes $ live with the wage."""
    perf = player_perf(p)
    by_role = {r: worker_productivity(perf, role_fit(p, r), reliability) for r in roles}
    by_role["_default"] = worker_productivity(perf, role_fit(p, None), reliability)
    return {"output_multiplier": cfg.get("employment", {}).get("player_output_multiplier", 1.8),
            "hire_reliability": reliability, "perf": perf, "by_role": by_role}


async def player_employee_projection(db, cfg, emp):
    """$/h estimate for an active player employee at current condition + wage + role."""
    p = await db.players.find_one({"id": emp["employee_player_id"]}, {"_id": 0})
    if not p:
        return None
    prod = worker_productivity(player_perf(p), role_fit(p, emp.get("role")), emp.get("reliability", 60))
    wph = emp.get("wage_per_hour") or round(emp.get("wage_per_shift", 60) / 4.0, 2)
    out = projection_at(wph, prod, cfg.get("employment", {}).get("player_output_multiplier", 1.8))
    out["estimated"] = True
    return out


def npc_employee_projection(emp, cfg, traits_map):
    """Unified $/h estimate for an NPC employee (comparable to players, clearly an estimate)."""
    skill = emp.get("skill", 3)
    base = 0.5 + (skill - 1) / 9 * 0.6
    cond = (emp.get("morale", 60) + emp.get("energy", 80) + emp.get("reliability", 60)) / 300.0
    perf = round(clamp(base * (0.6 + 0.6 * cond), 0.3, 1.5), 2)
    fit = round(clamp(0.55 + (skill - 1) / 9 * 0.75, 0.55, 1.3), 2)
    tmult = 1.0
    for t in emp.get("traits", []):
        tmult *= (1 + traits_map.get(t, {}).get("effects", {}).get("revenue", 0))
    tmult = max(0.7, min(1.4, tmult))
    prod = worker_productivity(perf, fit, emp.get("reliability", 60), tmult)
    equiv = cfg.get("employment", {}).get("npc_equiv_hours", 8)
    hourly = round(emp.get("daily_wage", 90) / equiv, 2)
    out = projection_at(hourly, prod, cfg.get("employment", {}).get("player_output_multiplier", 1.8))
    out["estimated"] = True
    out["equiv_hours"] = equiv
    return out


async def accrue_player_employment(db, p, cfg, gh, now):
    """Continuous, offline-safe auto-work for player employees on scheduled shifts.

    During scheduled hours the player automatically works: wages accrue to the player and
    revenue (net of wage) accrues to the employing business. Sets p['on_shift'] for activity gating.
    """
    emps = await db.player_employment.find({"employee_player_id": p["id"], "status": "active"}, {"_id": 0}).to_list(50)
    g_now = game_now(cfg, now)
    last = parse_dt(p.get("last_resolved_at")) or now
    g_last = game_now(cfg, last)
    eff = effectiveness(p)
    on_shift = None
    busy = bool(p.get("current_activity"))
    for emp in emps:
        sch = emp.get("schedule")
        if not sch:
            continue
        if emp_on_shift(emp, g_now):
            wb = current_window_bounds(sch, g_now)
            on_shift = {"employment_id": emp["id"], "business_id": emp["business_id"],
                        "business_name": emp.get("business_name"), "role": emp.get("role"),
                        "schedule": sch, "ends_at_game": wb[1].isoformat() if wb else None}
        if busy:
            continue  # cannot auto-work while in a blocking activity -> role left uncovered
        hired = parse_dt(emp.get("hired_at"))
        g_hired = game_now(cfg, hired) if hired else g_last
        a_start = max(g_last, g_hired)
        co = parse_dt(emp.get("clocked_out_until"))
        hours = active_hours_in_range(sch, a_start, g_now, co)
        if hours > 0.001:
            await _accrue_one(db, p, cfg, emp, hours, eff, now)
    p["on_shift"] = on_shift


async def _accrue_one(db, p, cfg, emp, hours, eff, now):
    biz = await db.businesses.find_one({"id": emp["business_id"]}, {"_id": 0})
    e = cfg.get("employment", {})
    wph = emp.get("wage_per_hour") or round(emp.get("wage_per_shift", 60) / 4.0, 2)
    wage = round(wph * hours, 2)
    role = emp.get("role")
    perf = round(shift_performance(p) * eff, 2)
    fit = role_fit(p, role)
    rel = emp.get("reliability", 60)
    productivity = round(clamp(perf * fit * (0.8 + 0.4 * rel / 100), 0.2, 1.9), 2)

    add_money(p, wage)
    ledger_add(p, "wages_earned", wage)
    p["fatigue"] = clamp(p["fatigue"] + 1.4 * hours)
    p["energy"] = clamp(p["energy"] - 1.1 * hours)
    p["stress"] = clamp(p["stress"] + 0.8 * hours)
    p["hygiene"] = clamp(p["hygiene"] - 0.8 * hours)
    sk = ROLE_SKILL.get(role)
    if sk:
        add_skill_xp(p, sk, 3.0 * hours * eff, cfg)

    output_mult = e.get("player_output_multiplier", 1.8)
    revenue = round(wph * hours * output_mult * productivity, 2)
    net = round(revenue - wage, 2)

    emp["total_hours_worked"] = round(emp.get("total_hours_worked", 0) + hours, 2)
    emp["total_wages_earned"] = round(emp.get("total_wages_earned", 0) + wage, 2)
    emp["total_value_added"] = round(emp.get("total_value_added", 0) + revenue, 2)
    emp["last_paid_at"] = now.isoformat()
    emp["reliability"] = clamp(emp.get("reliability", 60) + (0.05 if perf >= 0.8 else -0.05) * hours)
    emp["performance"] = round(clamp(emp.get("performance", 60) * 0.9 + productivity * 100 * 0.1, 0, 100), 1)
    gd = game_now(cfg, now).date().isoformat()
    today = emp.get("today") or {}
    if today.get("date") != gd:
        today = {"date": gd, "hours": 0.0, "wage": 0.0, "revenue": 0.0, "net": 0.0}
    today["hours"] = round(today["hours"] + hours, 2)
    today["wage"] = round(today["wage"] + wage, 2)
    today["revenue"] = round(today["revenue"] + revenue, 2)
    today["net"] = round(today["net"] + net, 2)
    emp["today"] = today
    emp["last_impact"] = {"hours": round(hours, 2), "wage": wage, "revenue": revenue, "net": net,
                          "productivity": productivity, "at": now.isoformat()}
    await db.player_employment.update_one({"id": emp["id"]}, {"$set": {
        "total_hours_worked": emp["total_hours_worked"], "total_wages_earned": emp["total_wages_earned"],
        "total_value_added": emp["total_value_added"], "last_paid_at": emp["last_paid_at"],
        "reliability": emp["reliability"], "performance": emp["performance"],
        "today": emp["today"], "last_impact": emp["last_impact"]}})

    if biz and not biz.get("bankrupt"):
        new_cash = round(biz.get("cash", 0) + net, 2)
        debt = biz.get("debt", 0)
        if new_cash < 0:
            debt = round(debt - new_cash, 2)
            new_cash = 0.0
        sat = clamp(biz.get("satisfaction", 60) + (productivity - 1.0) * 1.0)
        rep = clamp(biz.get("reputation", 50) + (0.1 if productivity >= 1 else -0.05))
        rev_total = round(biz.get("revenue_total", 0) + max(revenue, 0), 2)
        hist = biz.get("history", [])
        hist.append({"ts": now.isoformat(), "kind": "shift", "amount": net, "rev": revenue, "wage": wage,
                     "label": f"{p['name']} — {round(hours, 1)}h {role}", "cash": new_cash, "debt": debt})
        await db.businesses.update_one({"id": biz["id"]}, {"$set": {
            "cash": new_cash, "debt": debt, "satisfaction": sat, "reputation": rep,
            "revenue_total": rev_total, "history": hist[-60:]}})


async def clock_out_early(db, p, cfg, emp):
    """Player leaves before their shift window ends: prorated pay only, reliability -10, role uncovered."""
    now = now_utc()
    g_now = game_now(cfg, now)
    sch = emp.get("schedule")
    if not sch or not emp_on_shift(emp, g_now):
        return {"ok": False, "detail": "You're not currently on a scheduled shift."}
    wb = current_window_bounds(sch, g_now)
    we = wb[1] if wb else g_now
    await db.player_employment.update_one({"id": emp["id"]}, {"$set": {
        "clocked_out_until": we.isoformat(), "reliability": clamp(emp.get("reliability", 60) - 10)}})
    p["on_shift"] = None
    bname = emp.get("business_name", "the business")
    role_lbl = (emp.get("role") or "").replace("_", " ")
    await add_event(db, p["id"], f"You clocked out early from {bname}. You forfeit the rest of today's pay and your reliability dropped.", "job", "warning")
    await add_notification(db, emp["owner_id"], "business", "Employee clocked out early",
                           f"{p['name']} left their {sch.get('label', 'shift')} early at {bname} — the {role_lbl} role is now uncovered.",
                           "warning", f"/businesses/{emp['business_id']}")
    biz = await db.businesses.find_one({"id": emp["business_id"]}, {"_id": 0})
    if biz:
        hist = biz.get("history", [])
        hist.append({"ts": now.isoformat(), "kind": "shift", "amount": 0.0, "rev": 0.0, "wage": 0.0,
                     "label": f"{p['name']} clocked out early — {role_lbl} uncovered",
                     "cash": biz.get("cash", 0), "debt": biz.get("debt", 0)})
        await db.businesses.update_one({"id": biz["id"]}, {"$set": {"history": hist[-60:]}})
        await add_event(db, emp["owner_id"], f"{p['name']} clocked out early at {bname}; {role_lbl} role uncovered until their next shift.", "business", "warning", emp["business_id"])
    return {"ok": True, "until": we.isoformat()}
