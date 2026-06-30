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
def recommend_wage(applicant, cfg):
    e = cfg.get("employment", {})
    base = e.get("player_base_shift_wage", 60)
    avg = _avg(_top_skills(applicant))
    mult = clamp(0.8 + (avg - 2) * 0.06 + (applicant.get("reputation", 50) - 50) / 300.0, 0.7, 1.7)
    return round(base * mult, 2)


def applicant_snapshot(p, cfg):
    return {
        "name": p["name"], "level": p.get("level", 1), "reputation": round(p.get("reputation", 50)),
        "legal_reputation": round(p.get("legal_reputation", 100)),
        "criminal_warning": p.get("legal_reputation", 100) < 50,
        "top_skills": sorted(p["skills"].items(), key=lambda kv: kv[1].get("level", 1), reverse=True)[:3]
                      and [{"skill": k, "level": v.get("level", 1)} for k, v in sorted(p["skills"].items(), key=lambda kv: kv[1].get("level", 1), reverse=True)[:3]],
        "education_count": len(p.get("education", [])),
        "recommended_wage": recommend_wage(p, cfg),
    }


async def complete_player_shift(db, p, cfg, payload, eff):
    emp = await db.player_employment.find_one({"id": payload.get("employment_id")}, {"_id": 0})
    if not emp or emp.get("status") != "active":
        await add_event(db, p["id"], "Your shift ended, but you're no longer employed there.", "job", "warning")
        return
    biz = await db.businesses.find_one({"id": emp["business_id"]}, {"_id": 0})
    hours = payload.get("hours", 4)
    perf = round(shift_performance(p) * eff, 2)
    wage = round(emp["wage_per_shift"] * (0.7 + 0.3 * perf), 2)  # under-performing earns a bit less

    add_money(p, wage)
    ledger_add(p, "wages_earned", wage)
    p["fatigue"] = clamp(p["fatigue"] + payload.get("fatigue", 5) * hours)
    p["energy"] = clamp(p["energy"] - payload.get("energy", 4) * hours)
    p["stress"] = clamp(p["stress"] + 2 * hours)
    for s in (payload.get("skills") or ["fitness"]):
        # small xp handled by caller via add_skill_xp not available here; light mood bump instead
        pass

    rel_delta = 4 if perf >= 0.9 else (-3 if perf < 0.6 else 1)
    emp["total_hours_worked"] = emp.get("total_hours_worked", 0) + hours
    emp["total_wages_earned"] = round(emp.get("total_wages_earned", 0) + wage, 2)
    emp["last_paid_at"] = now_utc().isoformat()
    emp["reliability"] = clamp(emp.get("reliability", 60) + (3 if perf >= 0.8 else -2))
    emp["performance"] = round(clamp((emp.get("performance", 60) * 0.7 + perf * 100 * 0.3), 0, 100), 1)
    await db.player_employment.update_one({"id": emp["id"]}, {"$set": emp})

    if biz and not biz.get("bankrupt"):
        e = cfg.get("employment", {})
        contribution = round(e.get("player_shift_contribution", 90) * perf * (hours / 4.0), 2)
        biz["cash"] = round(biz.get("cash", 0) + contribution - wage, 2)
        biz["satisfaction"] = clamp(biz.get("satisfaction", 60) + 2 * perf)
        biz["reputation"] = clamp(biz.get("reputation", 50) + 1 * perf)
        biz["revenue_total"] = round(biz.get("revenue_total", 0) + contribution, 2)
        await db.businesses.update_one({"id": biz["id"]}, {"$set": {
            "cash": biz["cash"], "satisfaction": biz["satisfaction"], "reputation": biz["reputation"], "revenue_total": biz["revenue_total"]}})
        await add_notification(db, emp["owner_id"], "business",
                               f"{p['name']} finished a shift", f"+${contribution} value at {biz['name']} (perf {int(perf*100)}%). Wage ${wage} paid.",
                               "success" if perf >= 0.8 else "info", f"/businesses/{biz['id']}")

    quality = "great" if perf >= 1.0 else "solid" if perf >= 0.75 else "rough"
    await add_event(db, p["id"], f"You finished a {hours}h shift at {emp['business_name']} — a {quality} one. Earned ${wage}.", "job", "success" if perf >= 0.75 else "info")
