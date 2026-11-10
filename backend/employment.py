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
from pymongo import ReturnDocument
from game_models import now_utc, clamp
from game_engine import (parse_dt, add_event, add_notification, charge, add_money, ledger_add,
                         game_now, effectiveness, add_skill_xp)


# Default reason strings per outcome factor. Admins override these per-job via reason_strings
# (Job Editor ▸ Applications) or per-application (Admin ▸ Applications). Players never see these
# directly — only the final success_response/failure_response message.
DEFAULT_ACCEPT_REASONS = {
    "skills": "strong relevant skills",
    "education": "solid education",
    "reputation": "a great reputation",
    "work_history": "a strong work history",
    "reference": "a good reference",
    "connections": "the right connections",
    "interview": "a great interview",
}
DEFAULT_REJECT_REASONS = {
    "criminal_record": "your criminal record",
    "suspicion": "you're under watch attention",
    "low_skill": "insufficient skills",
    "reputation": "poor reputation",
    "work_history": "a weak work history",
    "health": "poor health",
    "competition": "a stronger candidate was chosen",
}



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
    cond = (p["health"] + p["energy"] + (100 - p["fatigue"]) + p["mood"]) / 400.0
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


# ----------------------------- business opening hours & shift coverage -----------------------------
def hhmm_to_float(s):
    try:
        h, m = str(s).split(":")
        return int(h) + int(m) / 60.0
    except Exception:
        return 0.0


def float_to_hhmm(f):
    f = max(0.0, min(24.0, float(f)))
    h = int(f)
    m = int(round((f - h) * 60))
    if m == 60:
        h += 1
        m = 0
    return f"{h:02d}:{m:02d}"


def opening_bounds(opening):
    """(open_h, close_h) floats for a business; defaults to 08:00-20:00."""
    if not opening:
        return 8.0, 20.0
    o = hhmm_to_float(opening.get("open", "08:00"))
    c = hhmm_to_float(opening.get("close", "20:00"))
    if c <= o:
        c = 24.0
    return o, c


def open_hours_total(opening):
    o, c = opening_bounds(opening)
    return round(c - o, 4)


def shift_bounds(schedule):
    """(start_h, end_h) floats from a worker schedule dict."""
    if not schedule:
        return 8.0, 16.0
    return float(schedule.get("start", 8)), float(schedule.get("end", 16))


def make_shift(start_h, end_h):
    return {"start": round(float(start_h), 2), "end": round(float(end_h), 2),
            "label": f"{float_to_hhmm(start_h)}-{float_to_hhmm(end_h)}"}


def _merge_intervals(ivals):
    ivals = sorted([iv for iv in ivals if iv[1] > iv[0]])
    out = []
    for s, e in ivals:
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def coverage_intervals(opening, worker_schedules):
    """Merged covered intervals (hour-of-day floats) clipped to the opening window."""
    o, c = opening_bounds(opening)
    ivals = []
    for sch in worker_schedules:
        if not sch:
            continue
        s, e = shift_bounds(sch)
        s = max(o, s)
        e = min(c, e)
        if e > s:
            ivals.append((s, e))
    return _merge_intervals(ivals)


def covered_hours_per_day(opening, worker_schedules):
    """Distinct opening-hours covered by at least one worker (capped at opening length)."""
    return round(sum(e - s for s, e in coverage_intervals(opening, worker_schedules)), 4)


def is_open_now(opening, g_now):
    o, c = opening_bounds(opening)
    h = g_now.hour + g_now.minute / 60.0
    return o <= h < c


def covered_hours_in_range(opening, worker_schedules, g_start, g_end):
    """Game-hours in [g_start,g_end] covered by >=1 worker within the opening window."""
    if g_end <= g_start:
        return 0.0
    merged = coverage_intervals(opening, worker_schedules)
    if not merged:
        return 0.0
    total = 0.0
    day = g_start.replace(hour=0, minute=0, second=0, microsecond=0)
    end_day = g_end.replace(hour=0, minute=0, second=0, microsecond=0)
    guard = 0
    while day <= end_day and guard < 4000:
        for s, e in merged:
            ws = day + timedelta(hours=s)
            we = day + timedelta(hours=e)
            lo = max(ws, g_start)
            hi = min(we, g_end)
            if hi > lo:
                total += (hi - lo).total_seconds() / 3600.0
        day += timedelta(days=1)
        guard += 1
    return round(total, 4)


def concurrency_segments(opening, worker_schedules):
    """Break the opening window into segments with a constant number of on-shift workers.
    Returns list of (start_h, end_h, concurrency)."""
    o, c = opening_bounds(opening)
    clipped = []
    pts = {o, c}
    for sch in worker_schedules:
        if not sch:
            continue
        s, e = shift_bounds(sch)
        s = max(o, s)
        e = min(c, e)
        if e > s:
            clipped.append((s, e))
            pts.add(s)
            pts.add(e)
    pts = sorted(pts)
    segs = []
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        if b <= a:
            continue
        mid = (a + b) / 2.0
        conc = sum(1 for (s, e) in clipped if s <= mid < e)
        segs.append((a, b, conc))
    return segs


def effective_worker_hours_per_day(opening, worker_schedules, slots):
    """Sum over the opening window of min(active workers, slots) — i.e. concurrent workers
    (capped at slots) scale production. 1 worker over 12h = 12; 2 concurrent over 12h (slots>=2) = 24."""
    slots = max(1, int(slots))
    return round(sum((b - a) * min(conc, slots) for a, b, conc in concurrency_segments(opening, worker_schedules)), 4)


def effective_worker_hours_in_range(opening, worker_schedules, slots, g_start, g_end):
    """Worker-hours (min(concurrency, slots)) accrued within [g_start,g_end]."""
    if g_end <= g_start:
        return 0.0
    slots = max(1, int(slots))
    segs = concurrency_segments(opening, worker_schedules)
    if not segs:
        return 0.0
    total = 0.0
    day = g_start.replace(hour=0, minute=0, second=0, microsecond=0)
    end_day = g_end.replace(hour=0, minute=0, second=0, microsecond=0)
    guard = 0
    while day <= end_day and guard < 4000:
        for a, b, conc in segs:
            ws = day + timedelta(hours=a)
            we = day + timedelta(hours=b)
            lo = max(ws, g_start)
            hi = min(we, g_end)
            if hi > lo:
                total += (hi - lo).total_seconds() / 3600.0 * min(conc, slots)
        day += timedelta(days=1)
        guard += 1
    return round(total, 4)



def worker_shift_hours(schedule, opening):
    """A worker's paid shift length per day, clipped to the opening window. 0 if unscheduled."""
    if not schedule:
        return 0.0
    o, c = opening_bounds(opening)
    s, e = shift_bounds(schedule)
    s = max(o, s)
    e = min(c, e)
    return round(max(0.0, e - s), 4)


def worker_hours_in_range(schedule, opening, g_start, g_end, clocked_out_until=None):
    """A single worker's paid hours in [g_start,g_end], clipped to the opening window. 0 if unscheduled."""
    if not schedule:
        return 0.0
    o, c = opening_bounds(opening)
    s, e = shift_bounds(schedule)
    s = max(o, s)
    e = min(c, e)
    if e <= s:
        return 0.0
    return active_hours_in_range({"start": s, "end": e}, g_start, g_end, clocked_out_until)


def first_uncovered_shift(opening, worker_schedules):
    """Largest 0-coverage gap within opening; None if the window is already fully covered."""
    o, c = opening_bounds(opening)
    merged = coverage_intervals(opening, worker_schedules)
    if not merged:
        return make_shift(o, c)
    gaps = []
    cursor = o
    for s, e in merged:
        if s > cursor:
            gaps.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < c:
        gaps.append((cursor, c))
    if not gaps:
        return None  # already fully covered — do NOT overlap (would waste wages)
    best = max(gaps, key=lambda g: g[1] - g[0])
    return make_shift(best[0], best[1])


def peak_concurrent(schedules):
    """Max number of shifts overlapping at any instant (touching shifts do not overlap)."""
    events = []
    for sch in schedules:
        if not sch:
            continue
        s, e = shift_bounds(sch)
        if e > s:
            events.append((s, 1))
            events.append((e, -1))
    events.sort(key=lambda x: (x[0], x[1]))
    cur = peak = 0
    for _, d in events:
        cur += d
        peak = max(peak, cur)
    return peak


def find_overlapping(proposed, named_schedules):
    """Return the name of a worker whose shift intersects `proposed`, else None."""
    if not proposed:
        return None
    ps, pe = shift_bounds(proposed)
    for name, sch in named_schedules:
        if not sch:
            continue
        s, e = shift_bounds(sch)
        if s < pe and ps < e:
            return name
    return None


def on_shift_now(schedule, opening, g_now, clocked_out_until=None):
    """True if the worker's shift covers the current game hour and the business is open."""
    if not schedule:
        return False
    if not is_open_now(opening, g_now):
        return False
    o, c = opening_bounds(opening)
    s, e = shift_bounds(schedule)
    s = max(o, s)
    e = min(c, e)
    h = g_now.hour + g_now.minute / 60.0
    if not (s <= h < e):
        return False
    if clocked_out_until and g_now < clocked_out_until:
        return False
    return True



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
    susp_pen = p.get("criminal_suspicion", 0) / 400.0  # employers run background checks
    status_bonus = max(0.0, (p.get("social_status", 10) - 10) / 300.0)  # connections open doors
    health_pen = (50 - p["health"]) / 300.0 if p["health"] < 50 else 0.0

    mult = clamp(1 + skill_bonus + edu_bonus + rep_bonus + rel_bonus + ref_bonus + status_bonus - crime_pen - health_pen,
                 e.get("wage_min_mult", 0.7), e.get("wage_max_mult", 1.85))
    wage = round(base * mult, 2)

    # Admin-tunable hiring difficulty (per job, stored in the DB).
    base_chance = float(job.get("acceptance_base_chance", 0.5))
    skill_weight = float(job.get("skill_weight", 1.0))
    score = max(0.03, min(0.97, base_chance + skill_bonus * skill_weight + edu_bonus + rep_bonus * 1.5
                          + rel_bonus * 2 + ref_bonus * 2 + status_bonus - crime_pen * 2 - susp_pen * 2 - health_pen))
    accepted = random.random() < score

    # Determine the dominant outcome factor (a KEY); the display string is resolved from the job's
    # admin-editable reason_strings (falling back to defaults). Admins can override per application later.
    rmap = job.get("reason_strings") or {}
    if accepted:
        pos = []
        if skill_lvl >= 4:
            pos.append(("skills", skill_bonus + 0.2))
        if len(p.get("education", [])) >= 2:
            pos.append(("education", edu_bonus + 0.1))
        if p["reputation"] >= 65:
            pos.append(("reputation", rep_bonus + 0.1))
        if reliability >= 65:
            pos.append(("work_history", rel_bonus + 0.1))
        if ref_bonus > 0.05:
            pos.append(("reference", ref_bonus + 0.1))
        if p.get("social_status", 10) >= 40:
            pos.append(("connections", status_bonus + 0.05))
        if not pos:
            pos.append(("interview", 0.1))
        reason_key = max(pos, key=lambda x: x[1])[0]
        reason = (rmap.get("accept") or {}).get(reason_key) or DEFAULT_ACCEPT_REASONS[reason_key]
    else:
        factors = []
        if crime_pen > 0.05:
            factors.append(("criminal_record", crime_pen * 2))
        if susp_pen > 0.05:
            factors.append(("suspicion", susp_pen * 2))
        if skill_lvl < 3:
            factors.append(("low_skill", 0.35))
        if p["reputation"] < 45:
            factors.append(("reputation", (45 - p["reputation"]) / 50))
        if reliability < 45:
            factors.append(("work_history", (45 - reliability) / 50))
        if p["health"] < 45:
            factors.append(("health", health_pen * 3))
        if not factors:
            factors.append(("competition", 0.2))
        reason_key = max(factors, key=lambda x: x[1])[0]
        reason = (rmap.get("reject") or {}).get(reason_key) or DEFAULT_REJECT_REASONS[reason_key]
    return {"wage": wage, "accepted": accepted, "reason": reason, "reason_key": reason_key,
            "mult": round(mult, 2), "score": round(score, 3)}


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
            msg = (job.get("success_response") or "Your application for {title} was accepted — offer ¤ {wage}/h.").format(
                title=job["title"], wage=ev["wage"], reason=ev["reason"])
            upd = {"status": "accepted", "wage_offer": ev["wage"], "reason": ev["reason"], "resolved": True,
                   "outcome_message": msg,
                   "offer_expires_at": (now + timedelta(hours=cfg.get("employment", {}).get("offer_expiry_hours", 24))).isoformat()}
            await add_event(db, p["id"], msg, "job", "success")
            await add_notification(db, p["id"], "job", "Application accepted", f"{job['title']} — ¤ {ev['wage']}/h. Accept the offer to start working.", "success", "/jobs")
        else:
            msg = (job.get("failure_response") or "Your application for {title} was rejected: {reason}.").format(
                title=job["title"], wage=ev["wage"], reason=ev["reason"])
            upd = {"status": "rejected", "reason": ev["reason"], "resolved": True, "outcome_message": msg}
            await add_event(db, p["id"], msg, "job", "warning")
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
def schedule_hours_per_day(sched):
    s, e = sched.get("start", 8), sched.get("end", 16)
    return (e - s) if e > s else (e + 24 - s)


def _productivity(skill_level, reliability, cond):
    """Unified productivity (mirrors employee_engine.worker_productivity)."""
    fit = clamp(0.55 + (skill_level - 1) / 9 * 0.75, 0.55, 1.3)
    rel = 0.8 + 0.4 * (reliability / 100.0)
    return round(clamp(fit * rel * cond, 0.35, 1.8), 3)


def _biz_supply(b):
    recipe = b.get("recipe") or []
    mc = sum(r.get("qty", 1) * r.get("cost", 0) for r in recipe)
    price = (b.get("product") or {}).get("price", 0)
    return b.get("production_per_worker_hour", 0), round(price - mc, 4)


def _player_skill_for_role(p, role):
    sk = ROLE_SKILL.get(role)
    return p["skills"].get(sk, {}).get("level", 1) if sk else _avg(_top_skills(p))


def applicant_projection(p, cfg, roles, b, reliability=60):
    """Per-role productivity map + this business's units/hr and $ margin; FE computes net live."""
    pph, margin = _biz_supply(b)
    cond = clamp(0.85 + 0.15 * effectiveness(p), 0.85, 1.05)
    by_role = {r: _productivity(_player_skill_for_role(p, r), reliability, cond) for r in roles}
    by_role["_default"] = _productivity(_avg(_top_skills(p)), reliability, cond)
    return {"units_per_hour": pph, "margin_per_unit": margin, "hire_reliability": reliability, "by_role": by_role}


async def player_employee_projection(db, cfg, emp, b):
    p = await db.players.find_one({"id": emp["employee_player_id"]}, {"_id": 0})
    if not p:
        return None
    pph, margin = _biz_supply(b)
    cond = clamp(0.85 + 0.15 * effectiveness(p), 0.85, 1.05)
    prod = _productivity(_player_skill_for_role(p, emp.get("role")), emp.get("reliability", 60), cond)
    wph = emp.get("wage_per_hour") or round(emp.get("wage_per_shift", 60) / 4.0, 2)
    rev = round(pph * prod * margin, 2)
    return {"units_per_hour": pph, "margin_per_unit": margin, "productivity": prod,
            "rev_per_hour": rev, "wage_per_hour": wph, "net_per_hour": round(rev - wph, 2), "estimated": True}


def npc_employee_projection(emp, cfg, traits_map, b):
    pph, margin = _biz_supply(b)
    cond = clamp(0.85 + 0.15 * ((emp.get("morale", 60) + emp.get("energy", 80)) / 200.0), 0.85, 1.05)
    prod = _productivity(emp.get("skill", 3), emp.get("reliability", 60), cond)
    for t in emp.get("traits", []):
        prod *= (1 + traits_map.get(t, {}).get("effects", {}).get("revenue", 0))
    prod = round(clamp(prod, 0.2, 1.9), 3)
    wph = emp.get("wage_per_hour") or round(emp.get("daily_wage", 90) / 8.0, 2)
    rev = round(pph * prod * margin, 2)
    return {"units_per_hour": pph, "margin_per_unit": margin, "productivity": prod,
            "rev_per_hour": rev, "wage_per_hour": wph, "net_per_hour": round(rev - wph, 2), "estimated": True}


async def resolve_worked_businesses(db, p, cfg, now):
    """Trigger the (idempotent, business-clock-gated) resolver for every business this player
    works at, so wages/output book promptly. Safe to call from the employee's own resolve."""
    import employee_engine
    bids = await db.player_employment.distinct("business_id", {"employee_player_id": p["id"], "status": "active"})
    for bid in bids:
        b = await db.businesses.find_one({"id": bid}, {"_id": 0})
        if b:
            await employee_engine.resolve_business(db, cfg, now, b)


async def sweep_player_earnings(db, p, cfg, now):
    """Pay out wages the businesses accrued to this player's employment records (atomic drain,
    so it never double-pays or races the business resolver) and apply the shift's personal toll."""
    g_now = game_now(cfg, now)
    on_shift = None
    emps = await db.player_employment.find({"employee_player_id": p["id"], "status": "active"}, {"_id": 0}).to_list(50)
    for emp in emps:
        drained = await db.player_employment.find_one_and_update(
            {"id": emp["id"]},
            {"$set": {"earnings_pending": 0.0, "personal_hours_pending": 0.0}},
            projection={"_id": 0, "earnings_pending": 1, "personal_hours_pending": 1},
            return_document=ReturnDocument.BEFORE)
        pend_cash = round((drained or {}).get("earnings_pending", 0) or 0, 2)
        pend_hours = (drained or {}).get("personal_hours_pending", 0) or 0
        if pend_cash > 0:
            add_money(p, pend_cash)
            ledger_add(p, "wages_earned", pend_cash)
        if pend_hours > 0:
            p["fatigue"] = clamp(p["fatigue"] + 1.4 * pend_hours)
            p["energy"] = clamp(p["energy"] - 1.1 * pend_hours)
            p["stress"] = clamp(p["stress"] + 0.8 * pend_hours)
            sk = ROLE_SKILL.get(emp.get("role"))
            if sk:
                add_skill_xp(p, sk, 3.0 * pend_hours * effectiveness(p), cfg)
        if emp_on_shift(emp, g_now):
            wb = current_window_bounds(emp.get("schedule") or {}, g_now)
            on_shift = {"employment_id": emp["id"], "business_id": emp["business_id"],
                        "business_name": emp.get("business_name"), "role": emp.get("role"),
                        "schedule": emp.get("schedule"), "ends_at_game": wb[1].isoformat() if wb else None}
    p["on_shift"] = on_shift


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
