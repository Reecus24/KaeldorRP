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
from game_engine import parse_dt, add_event, add_notification, charge, add_money, ledger_add


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


async def complete_player_shift(db, p, cfg, payload, eff):
    emp = await db.player_employment.find_one({"id": payload.get("employment_id")}, {"_id": 0})
    if not emp or emp.get("status") != "active":
        await add_event(db, p["id"], "Your shift ended, but you're no longer employed there.", "job", "warning")
        return
    biz = await db.businesses.find_one({"id": emp["business_id"]}, {"_id": 0})
    hours = payload.get("hours", 4)
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
    p["fatigue"] = clamp(p["fatigue"] + payload.get("fatigue", 5) * hours)
    p["energy"] = clamp(p["energy"] - payload.get("energy", 4) * hours)
    p["stress"] = clamp(p["stress"] + 2 * hours)

    output_mult = e.get("player_output_multiplier", 1.8)
    revenue = round(wph * hours * output_mult * productivity, 2)
    net = round(revenue - wage, 2)

    emp["total_hours_worked"] = emp.get("total_hours_worked", 0) + hours
    emp["total_wages_earned"] = round(emp.get("total_wages_earned", 0) + wage, 2)
    emp["total_value_added"] = round(emp.get("total_value_added", 0) + revenue, 2)
    emp["last_paid_at"] = now_utc().isoformat()
    emp["reliability"] = clamp(emp.get("reliability", 60) + (3 if perf >= 0.8 else -2))
    emp["performance"] = round(clamp(emp.get("performance", 60) * 0.7 + productivity * 100 * 0.3, 0, 100), 1)
    emp["last_shift"] = {"hours": hours, "wage": wage, "revenue": revenue, "net": net,
                         "productivity": productivity, "perf": perf, "role_fit": fit,
                         "at": now_utc().isoformat()}
    await db.player_employment.update_one({"id": emp["id"]}, {"$set": emp})

    if biz and not biz.get("bankrupt"):
        biz["cash"] = round(biz.get("cash", 0) + net, 2)
        if biz["cash"] < 0:
            biz["debt"] = round(biz.get("debt", 0) - biz["cash"], 2)
            biz["cash"] = 0.0
        biz["satisfaction"] = clamp(biz.get("satisfaction", 60) + (productivity - 1.0) * 4)
        biz["reputation"] = clamp(biz.get("reputation", 50) + (1 if productivity >= 1 else -0.5))
        biz["revenue_total"] = round(biz.get("revenue_total", 0) + max(revenue, 0), 2)
        hist = biz.get("history", [])
        hist.append({"ts": now_utc().isoformat(), "kind": "shift", "amount": net, "rev": revenue, "wage": wage,
                     "label": f"{p['name']} — {hours}h {role} shift", "cash": biz["cash"], "debt": biz.get("debt", 0)})
        biz["history"] = hist[-60:]
        await db.businesses.update_one({"id": biz["id"]}, {"$set": {
            "cash": biz["cash"], "debt": biz.get("debt", 0), "satisfaction": biz["satisfaction"],
            "reputation": biz["reputation"], "revenue_total": biz["revenue_total"], "history": biz["history"]}})
        sign = "+" if net >= 0 else ""
        await add_notification(db, emp["owner_id"], "business", f"{p['name']} worked a {hours}h shift",
                               f"+${revenue} revenue − ${wage} wage = net {sign}${net} at {biz['name']} (productivity {int(productivity*100)}%).",
                               "success" if net >= 0 else "warning", f"/businesses/{biz['id']}")

    quality = "great" if productivity >= 1.1 else "solid" if productivity >= 0.8 else "rough"
    await add_event(db, p["id"], f"You finished a {hours}h shift at {emp['business_name']} as {role} — a {quality} one. Earned ${wage}.", "job", "success" if productivity >= 0.8 else "info")
