"""Kaeldor RPG - the real-time resolution engine (offline progress, decay, completions)."""
import uuid
import random
from datetime import datetime, timezone, timedelta
from game_models import now_utc, clamp, SKILLS, empty_ledger
import game_models


def _tax_rate_for(gross):
    """Progressive income-tax rate from admin-tunable brackets [[up_to, rate], ...]."""
    brackets = game_models.TUNE.get("tax_brackets") or [[100, 0.10], [250, 0.15], [None, 0.22]]
    for up_to, rate in brackets:
        if up_to is None or gross < up_to:
            return rate
    return brackets[-1][1]


def effective_loan_rate(p, cfg):
    """REPUTATION-PRICED daily loan interest: a strong reputation earns a lower rate, a poor one
    pays a premium. Reputation 50 (neutral) = the base rate. See docs/ECONOMY_LOGIC.md."""
    base = cfg.get("economy", {}).get("loan_interest_daily", 0.015)
    rep = p.get("reputation", 50)
    factor = clamp(1.0 - (rep - 50) / 125.0, 0.7, 1.4)
    return round(base * factor, 5)


def parse_dt(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(v).replace(tzinfo=timezone.utc) if "+" not in str(v) and "Z" not in str(v) else datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def real_seconds(game_minutes, time_scale):
    # real_minutes = game_minutes / time_scale ; default ts=12 -> 60 game min => 5 real min
    return (game_minutes / max(time_scale, 0.0001)) * 60.0


def game_hours(real_secs, time_scale):
    real_minutes = real_secs / 60.0
    return (real_minutes * time_scale) / 60.0


async def get_config(db):
    cfg = await db.config.find_one({"id": "global"}, {"_id": 0})
    if not cfg:
        from game_models import DEFAULT_CONFIG
        cfg = {**DEFAULT_CONFIG}
    import game_models
    game_models.apply_tuning(cfg)
    cfg["tuning"] = dict(game_models.TUNE)  # return the full effective tuning (defaults merged) for the admin UI
    return cfg


async def add_event(db, player_id, message, etype="info", severity="info", business_id=None):
    doc = {
        "id": __import__("uuid").uuid4().hex,
        "player_id": player_id,
        "ts": now_utc().isoformat(),
        "type": etype,
        "severity": severity,
        "message": message,
    }
    if business_id:
        doc["business_id"] = business_id
    await db.events.insert_one(doc)


async def add_notification(db, player_id, ntype, title, body="", severity="info", link=None):
    doc = {
        "id": uuid.uuid4().hex, "player_id": player_id, "type": ntype,
        "title": title, "body": body, "severity": severity, "read": False,
        "ts": now_utc().isoformat(),
    }
    if link:
        doc["link"] = link
    await db.notifications.insert_one(doc)


# ----------------------------- world clock + daily ledger -----------------------------
def world_anchors(cfg):
    return parse_dt(cfg.get("world_start_real")), parse_dt(cfg.get("world_start_game"))


def game_now(cfg, real_dt=None):
    real_dt = real_dt or now_utc()
    wr, wg = world_anchors(cfg)
    if not wr or not wg:
        return real_dt
    elapsed = (real_dt - wr).total_seconds() * cfg.get("time_scale", 1.0)
    return wg + timedelta(seconds=elapsed)


def game_to_real(cfg, game_dt):
    """Inverse of game_now: the real-world datetime at which the clock reaches `game_dt`."""
    wr, wg = world_anchors(cfg)
    if not wr or not wg:
        return game_dt
    elapsed_game = (game_dt - wg).total_seconds()
    return wr + timedelta(seconds=elapsed_game / max(cfg.get("time_scale", 1.0), 0.0001))


def game_day_index(cfg, real_dt=None):
    g = game_now(cfg, real_dt)
    wg = world_anchors(cfg)[1] or g
    base = wg.replace(hour=0, minute=0, second=0, microsecond=0)
    return int((g - base).total_seconds() // 86400)


def ledger_add(p, bucket, amt):
    L = p.setdefault("day_ledger", empty_ledger())
    L[bucket] = round(L.get(bucket, 0.0) + amt, 2)


def ledger_warn(p, text):
    L = p.setdefault("day_ledger", empty_ledger())
    w = L.setdefault("warnings", [])
    if text not in w:
        w.append(text)
        L["warnings"] = w[-20:]


def ledger_event(p, text):
    L = p.setdefault("day_ledger", empty_ledger())
    e = L.setdefault("rel_events", [])
    e.append(text)
    L["rel_events"] = e[-30:]


async def _flush_daily_summary(db, p, cfg, from_day, to_day, now):
    L = p.get("day_ledger") or empty_ledger()
    income = (L.get("wages_earned", 0) + L.get("business_income", 0) + L.get("crime_income", 0)
              + L.get("social_income", 0) + L.get("savings_interest", 0))
    expense = (L.get("rent", 0) + L.get("bills", 0) + L.get("vehicle_costs", 0)
               + L.get("fines", 0) + L.get("medical", 0) + L.get("living_costs", 0)
               + L.get("taxes", 0) + L.get("loan_interest", 0))
    net = round(income + expense, 2)
    gnow = game_now(cfg, now)
    # Collect the day's significant events for the ledger's Event Log (job/legal/social/finance...).
    since_iso = p.get("last_summary_real_ts")
    since = parse_dt(since_iso) if since_iso else (now - timedelta(hours=max(1, to_day - from_day) * 24 / max(0.01, cfg.get("time_scale", 1.0))))
    ev_rows = await db.events.find(
        {"player_id": p["id"], "ts": {"$gte": since.isoformat()}},
        {"_id": 0, "ts": 1, "type": 1, "severity": 1, "message": 1}).sort("ts", 1).to_list(300)
    significant = [e for e in ev_rows
                   if e.get("severity") in ("success", "warning", "danger")
                   or e.get("type") in ("job", "legal", "crime", "social", "housing", "health", "business", "finance")]
    significant = [e for e in significant if e.get("type") != "system"][-25:]
    doc = {
        "id": uuid.uuid4().hex, "player_id": p["id"],
        "day_index": from_day, "days_covered": to_day - from_day,
        "game_date": (gnow - timedelta(days=1)).date().isoformat(),
        "real_ts": now.isoformat(),
        "ledger": {k: (round(v, 2) if isinstance(v, (int, float)) else v) for k, v in L.items()},
        "income_total": round(income, 2), "expense_total": round(expense, 2), "net_cash": net,
        "cash": round(p["cash"], 2), "bank": round(p["bank"], 2), "debt": round(p["debt"], 2),
        "events": significant,
    }
    await db.daily_summaries.insert_one({**doc})
    if p.get("credit_missed_flag"):
        p["credit_missed"] = min(10, int(p.get("credit_missed", 0)) + 1)
        p["credit_missed_flag"] = False
    elif int(p.get("credit_missed", 0)) > 0:
        p["credit_missed"] = max(0, int(p["credit_missed"]) - 1)  # rebuild creditworthiness on a clean day
    p["day_ledger"] = empty_ledger()
    p["last_summary_real_ts"] = now.isoformat()
    sign = "+" if net >= 0 else ""
    await add_notification(db, p["id"], "daily_summary", "Daily summary ready",
                           f"Net cash for the day: {sign}${round(net)}",
                           "success" if net >= 0 else "warning", "/daily-summary")
    await add_event(db, p["id"], f"A new day begins in Kaeldor. Net cash yesterday: {sign}${round(net)}.", "system", "info")


def effectiveness(p):
    score = 1.0
    score *= 0.5 + 0.5 * (p["energy"] / 100.0)
    score *= 0.6 + 0.4 * (1 - p["fatigue"] / 100.0)
    score *= 0.7 + 0.3 * (p["health"] / 100.0)
    if p["hunger"] > 80:
        score *= 0.8
    if p["stress"] > 80:
        score *= 0.85
    score += p.get("equip_bonus", {}).get("work_effectiveness", 0.0)  # equipped work/fitness gear
    return max(0.3, min(1.25, score))


def charge(p, amount):
    """Deduct money: cash -> bank -> debt. Returns True if fully covered without debt."""
    amount = round(amount, 2)
    if amount <= 0:
        return True
    if p["cash"] >= amount:
        p["cash"] = round(p["cash"] - amount, 2)
        return True
    rem = amount - p["cash"]
    p["cash"] = 0.0
    if p["bank"] >= rem:
        p["bank"] = round(p["bank"] - rem, 2)
        return True
    rem -= p["bank"]
    p["bank"] = 0.0
    p["debt"] = round(p["debt"] + rem, 2)
    return False


def add_money(p, amount):
    p["cash"] = round(p["cash"] + amount, 2)


def add_skill_xp(p, skill, amount, cfg):
    if skill not in p["skills"]:
        p["skills"][skill] = {"level": 1, "xp": 0}
    base = cfg.get("xp", {}).get("skill_per_level", 120)
    sk = p["skills"][skill]
    sk["xp"] += amount
    while sk["xp"] >= base * sk["level"]:
        sk["xp"] -= base * sk["level"]
        sk["level"] += 1
    add_player_xp(p, amount * 0.5, cfg)


def add_player_xp(p, amount, cfg):
    base = cfg.get("xp", {}).get("player_per_level", 250)
    p["xp"] += amount
    leveled = False
    while p["xp"] >= base * p["level"]:
        p["xp"] -= base * p["level"]
        p["level"] += 1
        leveled = True
    return leveled


def apply_effects(p, effects, mult=1.0):
    need_keys = ["energy", "fatigue", "hunger", "mood", "stress", "health"]
    rep_keys = ["reputation", "legal_reputation", "criminal_suspicion", "social_status"]
    for k, v in (effects or {}).items():
        if k in need_keys or k in rep_keys:
            p[k] = clamp(p[k] + v * mult)
        elif k == "cash":
            add_money(p, v * mult)


def decay_needs(p, gh, cfg, resting, studying=False, mood_bonus=0.0):
    d = cfg.get("decay", {})
    eb = p.get("equip_bonus", {})
    p["hunger"] = clamp(p["hunger"] + d.get("hunger", 3.2) * gh)
    if not resting:
        p["energy"] = clamp(p["energy"] - d.get("energy_awake", 2.4) * gh * eb.get("energy_drain_mult", 1.0))
        p["fatigue"] = clamp(p["fatigue"] + d.get("fatigue_awake", 1.8) * gh)
        p["stress"] = clamp(p["stress"] - d.get("stress_relax", 1.2) * gh)
    # derived health/mood pressure
    if p["hunger"] > 80:
        p["health"] = clamp(p["health"] - 1.4 * gh)
        p["mood"] = clamp(p["mood"] - 1.0 * gh)
    if p["fatigue"] > 80:
        p["health"] = clamp(p["health"] - 0.6 * gh)
    if p["stress"] > 80:
        p["health"] = clamp(p["health"] - 0.8 * gh)
        p["mood"] = clamp(p["mood"] - 1.0 * gh)
    if p["energy"] < 15:
        p["stress"] = clamp(p["stress"] + 1.0 * gh)
    # criminal suspicion cools down while not committing crimes (admin-tunable, 0 = never cools)
    if p.get("criminal_suspicion", 0) > 0:
        _susp_decay = float(game_models.TUNE.get("suspicion_decay_per_hour", 1.5))
        p["criminal_suspicion"] = clamp(p["criminal_suspicion"] - _susp_decay * gh)
    # slow passive health regen when reasonably fed/rested/calm (+ equipped fitness gear)
    if p["health"] < 100 and p["hunger"] < 80 and p["fatigue"] < 85 and p["stress"] < 85:
        p["health"] = clamp(p["health"] + (0.8 + eb.get("health_regen", 0.0)) * gh)
    # mood drifts toward a baseline set by HOUSING quality: better homes lift the target mood,
    # a cramped studio drags it down (housing mood_bonus, see PLAYER_STATS_LOGIC.md).
    baseline = clamp(d.get("mood_baseline", 60.0) + float(mood_bonus or 0.0), 0.0, 100.0)
    if p["mood"] < baseline:
        p["mood"] = clamp(p["mood"] + 0.5 * gh, 0.0, baseline)
    elif p["mood"] > baseline + 20:
        p["mood"] = clamp(p["mood"] - 0.3 * gh)
    # equipped-gear passive floors: stat won't fall below the floor while the item is worn
    for stat, key in (("mood", "mood_floor"), ("social_status", "social_status_floor"), ("reputation", "reputation_floor")):
        fl = eb.get(key)
        if fl:
            p[stat] = clamp(max(p.get(stat, 0.0), fl))
    # STUDENT WELFARE: while actively in education (kind == "course"), needs are held at their
    # perfect states as a safety net so long courses can never starve/collapse a player.
    # See docs/PLAYER_STATS_LOGIC.md.
    if studying:
        p["health"] = 100.0
        p["energy"] = 100.0
        p["mood"] = 100.0
        p["hunger"] = 0.0
        p["fatigue"] = 0.0
        p["stress"] = 0.0


def weighted_event(events, scope):
    pool = [e for e in events if e.get("scope") == scope]
    if not pool:
        return None
    total = sum(e.get("weight", 1) for e in pool)
    r = random.uniform(0, total)
    acc = 0
    for e in pool:
        acc += e.get("weight", 1)
        if r <= acc:
            return e
    return pool[-1]


async def complete_activity(db, p, cfg):
    act = p.get("current_activity")
    if not act:
        return
    kind = act.get("kind")
    payload = act.get("payload", {})
    pid = p["id"]
    eff = effectiveness(p)

    if kind == "action":
        effects = dict(payload.get("effects", {}))
        if payload.get("sleep"):
            sq = payload.get("sleep_quality", 1.0)
            if "energy" in effects:
                effects["energy"] = effects["energy"] * sq
            if "fatigue" in effects:
                effects["fatigue"] = effects["fatigue"] * sq
        apply_effects(p, effects)
        for sk, xp in payload.get("skill_xp", {}).items():
            add_skill_xp(p, sk, xp * eff, cfg)
        reward = payload.get("money_reward", 0)
        if reward:
            add_money(p, round(reward * eff, 2))
        if payload.get("repairs_vehicle") and p.get("vehicles"):
            for v in p["vehicles"]:
                v["condition"] = 100
        p["stats_meta"]["actions_done"] = p["stats_meta"].get("actions_done", 0) + 1
        msg = payload.get("result_text", "Action complete.")
        if reward:
            msg += f" (+${round(reward * eff)})"
        await add_event(db, pid, f"{payload.get('name','Action')}: {msg}", "action", "success")

    elif kind == "job":
        hours = payload["hours"]
        pay_mult = float(payload.get("pay_multiplier", 1.0))
        xp_mult = float(payload.get("xp_multiplier", 1.0))
        base_pay = round(payload["hourly_wage"] * hours * eff * pay_mult, 2)
        # REPUTATION + SOCIAL STATUS tip for customer-facing work (see PLAYER_STATS_LOGIC.md)
        tip = 0.0
        if payload.get("category") in ("retail", "food", "logistics", "office", "management", "trade"):
            tip_rate = clamp((p["reputation"] - 50) / 100.0 * 0.15 + (p.get("social_status", 10) - 10) / 100.0 * 0.05
                             + p.get("equip_bonus", {}).get("tip_rate", 0.0), 0.0, 0.25)
            tip = round(base_pay * tip_rate, 2)
        pay = round(base_pay + tip, 2)
        # INCOME TAX withheld on wages (progressive, admin-tunable) — links Economy + Bank + Legal Standing.
        gross = pay
        rate = _tax_rate_for(gross)
        tax = round(gross * rate, 2)
        net_pay = round(gross - tax, 2)
        add_money(p, net_pay)
        ledger_add(p, "wages_earned", net_pay)
        ledger_add(p, "taxes", -tax)
        p["fatigue"] = clamp(p["fatigue"] + payload["fatigue_ph"] * hours)
        p["stress"] = clamp(p["stress"] + payload["stress_ph"] * hours)
        p["energy"] = clamp(p["energy"] - payload["energy_ph"] * hours)
        p["hunger"] = clamp(p["hunger"] + hours * 2.5)
        for sk, xp in payload.get("skill_xp", {}).items():
            add_skill_xp(p, sk, xp * hours * eff * xp_mult, cfg)
        p["reputation"] = clamp(p["reputation"] + 0.5)
        if p.get("job"):
            p["job"]["shifts_worked"] = p["job"].get("shifts_worked", 0) + 1
            p["job"]["hours_worked"] = round(p["job"].get("hours_worked", 0) + hours, 1)
            rel_delta = 2 if eff >= 0.7 else (-3 if eff < 0.5 else 0)
            p["job"]["reliability"] = clamp(p["job"].get("reliability", 50) + rel_delta)
        p["stats_meta"]["shifts_worked"] = p["stats_meta"].get("shifts_worked", 0) + 1
        p["stats_meta"]["total_hours_worked"] = round(p["stats_meta"].get("total_hours_worked", 0) + hours, 1)
        shift_name = payload.get("shift_name") or f"{hours}h"
        await add_event(db, pid, f"Finished {shift_name} shift as {payload.get('title')} (+${net_pay} after ${tax} tax{f', incl. ${tip} tips' if tip > 0 else ''}).", "job", "success")
        # SHIFT INJURY RISK — hazardous/night shifts can hurt you (health + stress); the shift still completes.
        injury_risk = float(payload.get("injury_risk", 0.0))
        if injury_risk > 0 and random.random() < injury_risk:
            dmg = round(random.uniform(6, 16))
            p["health"] = clamp(p["health"] - dmg)
            p["stress"] = clamp(p["stress"] + round(dmg * 0.6))
            await add_event(db, pid, f"Work accident during your {shift_name} shift — you lost {dmg} health.", "job", "danger")
        # random work event
        if eff < game_models.TUNE.get("accident_eff_threshold", 0.55) and random.random() < game_models.TUNE.get("accident_chance", 0.30):
            p["health"] = clamp(p["health"] - 8)
            await add_event(db, pid, "You were exhausted and made costly mistakes at work.", "job", "warning")
        else:
            events = await db.random_events.find({"scope": "job"}, {"_id": 0}).to_list(100)
            ev = weighted_event(events, "job")
            if ev and random.random() < 0.45:
                apply_effects(p, ev.get("effects", {}))
                sev = "warning" if any(v < 0 for v in ev.get("effects", {}).values()) else "info"
                await add_event(db, pid, ev["message"], "job", sev)

    elif kind == "course":
        course_id = payload["course_id"]
        if course_id not in p["education"]:
            p["education"].append(course_id)
        for sk, lvls in payload.get("grants_skills", {}).items():
            if sk not in p["skills"]:
                p["skills"][sk] = {"level": 1, "xp": 0}
            p["skills"][sk]["level"] += lvls
        add_player_xp(p, 200, cfg)
        p["social_status"] = clamp(p["social_status"] + 4)
        p["legal_reputation"] = clamp(p["legal_reputation"] + 2)
        p["stats_meta"]["courses_done"] = p["stats_meta"].get("courses_done", 0) + 1
        await add_event(db, pid, f"Graduated: {payload.get('title')}! New skills unlocked.", "education", "success")

    elif kind == "illegal":
        await _resolve_illegal(db, p, cfg, payload, eff)

    elif kind == "social":
        import social_engine
        await social_engine.complete_social_activity(db, p, cfg, payload, eff, act.get("started_at"))

    p["current_activity"] = None
    p["status"] = "jail" if parse_dt(p.get("jail_until")) and parse_dt(p["jail_until"]) > now_utc() else \
        ("hospital" if parse_dt(p.get("hospital_until")) and parse_dt(p["hospital_until"]) > now_utc() else "free")


async def _resolve_illegal(db, p, cfg, payload, eff):
    pid = p["id"]
    name = payload.get("name", "Illegal job")
    street = p["skills"].get("street_smarts", {}).get("level", 1)
    # higher suspicion & lower street smarts -> easier to get caught
    catch = payload["police_risk"] * (1 + p["criminal_suspicion"] / 150.0) * (1 - min(0.4, street * 0.03))
    catch *= payload.get("risk_mult", 1.0)
    fail = payload["failure_chance"] * (1 - min(0.3, street * 0.025))
    # EFFECTIVENESS → CRIME: being sharp (well-rested/fed/healthy) makes a job less likely to flop,
    # while showing up tired/hungry raises the failure chance. (See docs/PLAYER_STATS_LOGIC.md.)
    fail *= clamp(1.6 - 0.6 * eff, 0.6, 1.6)
    gain_mult = float(game_models.TUNE.get("suspicion_gain_mult", 1.0))
    sg = payload.get("suspicion_gain", 10) * gain_mult
    p["stats_meta"]["crimes_committed"] = p["stats_meta"].get("crimes_committed", 0) + 1
    # crime skill XP scales with effectiveness too — a distracted, botched job teaches you less.
    for sk, xp in payload.get("skill_xp", {}).items():
        add_skill_xp(p, sk, xp * eff, cfg)

    roll = random.random()
    if roll < catch:
        jail_minutes = payload.get("jail_minutes", 720)
        ts = cfg["time_scale"]
        p["jail_until"] = (now_utc() + timedelta(seconds=real_seconds(jail_minutes, ts))).isoformat()
        p["status"] = "jail"
        charge(p, payload.get("fine_amount", 200))
        ledger_add(p, "fines", -payload.get("fine_amount", 200))
        p["criminal_suspicion"] = clamp(p["criminal_suspicion"] + sg + 15)
        p["legal_reputation"] = clamp(p["legal_reputation"] - 15)
        p["reputation"] = clamp(p["reputation"] + payload.get("reputation_impact", -5))
        p["stress"] = clamp(p["stress"] + 25)
        p["criminal_record"].append({
            "type": name, "outcome": "caught", "date": now_utc().isoformat(),
            "fine": payload.get("fine_amount", 0),
        })
        p["stats_meta"]["times_jailed"] = p["stats_meta"].get("times_jailed", 0) + 1
        await add_event(db, pid, f"BUSTED during {name}! Fined ${payload.get('fine_amount',0)} and jailed.", "crime", "danger")
    elif roll < catch + fail:
        p["criminal_suspicion"] = clamp(p["criminal_suspicion"] + sg * 0.5)
        p["stress"] = clamp(p["stress"] + 12)
        await add_event(db, pid, f"{name} failed. You got nothing and your nerves are shot.", "crime", "warning")
    else:
        lo, hi = payload.get("reward_min", 0), payload.get("reward_max", 0)
        reward = round(random.uniform(lo, hi))
        if reward >= 0:
            add_money(p, reward)
        else:
            charge(p, -reward)
        ledger_add(p, "crime_income", reward)
        p["criminal_suspicion"] = clamp(p["criminal_suspicion"] + sg)
        p["reputation"] = clamp(p["reputation"] + payload.get("reputation_impact", 0))
        p["legal_reputation"] = clamp(p["legal_reputation"] - 4)
        if payload.get("lowers_suspicion"):
            p["criminal_suspicion"] = clamp(p["criminal_suspicion"] - payload["lowers_suspicion"])
            await add_event(db, pid, f"{name} succeeded. Your record looks cleaner now.", "crime", "info")
        else:
            verb = "scored" if reward >= 0 else "lost"
            await add_event(db, pid, f"{name} succeeded. You {verb} ${abs(reward)}. Suspicion rising.", "crime", "warning")


def _decay_skills(p, gh):
    """Use-it-or-lose-it: skills above level 2 slowly lose XP when idle. Working/training re-adds XP,
    so actively used skills never degrade. Rate is admin-tunable via TUNE['skill_decay_per_hour'] (0 = off)."""
    rate = float(game_models.TUNE.get("skill_decay_per_hour", 0.35)) * gh
    if rate <= 0:
        return
    for name, sk in (p.get("skills") or {}).items():
        if sk.get("level", 1) <= 2:
            continue
        sk["xp"] = sk.get("xp", 0) - rate
        if sk["xp"] < 0:
            if sk["level"] > 2:
                sk["level"] -= 1
                sk["xp"] = 40  # drop a level, retain partial progress
            else:
                sk["xp"] = 0


async def accrue_recurring(db, p, cfg, gh, housing_doc):
    """Hourly-accruing money flows: utility bills, loan/savings interest, skill & vehicle wear.
    NOTE: fixed RENT and VEHICLE costs (fuel/insurance/maintenance) are NO LONGER charged here —
    they are deducted once per day as a single sum at the 00:00 game-day boundary
    (see _charge_daily_fixed). This keeps continuous flows (interest/bills) hourly while making
    the big fixed costs land at midnight, matching the Daily Summary receipt."""
    if gh <= 0:
        return
    bills = 0.0
    if housing_doc:
        bills += housing_doc.get("bills_per_day", 0) * gh / 24.0
    # VEHICLE condition WEAR is continuous (not a cash cost — the cash cost lands at 00:00). A vehicle
    # whose daily maintenance was PAID at the last midnight wears far slower; an UNPAID one wears fast.
    maint_rate = float(cfg.get("economy", {}).get("vehicle_decay_maintained", 0.05))
    unmaint_rate = float(cfg.get("economy", {}).get("vehicle_decay_unmaintained", 0.6))
    for v in p.get("vehicles", []):
        rate = maint_rate if v.get("maintained", True) else unmaint_rate
        v["condition"] = clamp(v.get("condition", 100) - rate * gh, 0, 100)
    if p["debt"] > 0:
        rate = effective_loan_rate(p, cfg)
        interest = round(p["debt"] * rate * gh / 24.0, 2)
        p["debt"] = round(p["debt"] + interest, 2)
        ledger_add(p, "loan_interest", -interest)
    else:
        # SAVINGS INTEREST: a debt-free bank balance earns modest daily interest (rewards saving).
        srate = cfg.get("economy", {}).get("savings_interest_daily", 0.0008)
        if p.get("bank", 0) > 0 and srate > 0:
            si = round(p["bank"] * srate * gh / 24.0, 2)
            if si > 0:
                p["bank"] = round(p["bank"] + si, 2)
                ledger_add(p, "savings_interest", si)
    _decay_skills(p, gh)
    if bills > 0:
        before_debt = p["debt"]
        charge(p, round(bills, 2))
        ledger_add(p, "bills", -round(bills, 2))
        if p["debt"] > before_debt + 1:
            p["credit_missed_flag"] = True
            ledger_warn(p, "Couldn't fully cover utility bills — slipping into debt.")


async def _charge_daily_fixed(db, p, cfg, days, housing_doc):
    """00:00 GAME-DAY BOUNDARY: charge the day's fixed RENT and VEHICLE costs
    (fuel + insurance + maintenance) as a single daily lump, once per day crossed.
    Replaces the old hourly proration so these land exactly at midnight."""
    if days <= 0:
        return
    rent = 0.0
    if housing_doc and not (p.get("housing") or {}).get("owned"):
        rent = housing_doc.get("rent_per_day", 0) * days
    veh = 0.0
    for v in p.get("vehicles", []):
        vt = v.get("spec", {})
        veh += (vt.get("fuel_per_day", 0) + vt.get("insurance_per_day", 0) + vt.get("maintenance_per_day", 0)) * days
    total = round(rent + veh, 2)
    if total <= 0:
        for v in p.get("vehicles", []):
            v["maintained"] = True  # nothing owed today → treated as maintained
        return
    before_debt = p["debt"]
    charge(p, total)
    # Maintenance outcome: if the daily bill was covered (didn't push into debt), vehicles are
    # "maintained" for the next 24h (slow wear); otherwise they go unmaintained (accelerated wear).
    paid = p["debt"] <= before_debt + 1
    for v in p.get("vehicles", []):
        v["maintained"] = paid
    if rent > 0:
        ledger_add(p, "rent", -round(rent, 2))
    if veh > 0:
        ledger_add(p, "vehicle_costs", -round(veh, 2))
    if not paid:
        p["credit_missed_flag"] = True
        ledger_warn(p, "Your 00:00 rent & vehicle bill pushed you into debt.")
        await add_event(db, p["id"], "Your daily rent & vehicle costs pushed you into debt — vehicles left unmaintained and wearing fast.", "finance", "warning")
    else:
        parts = []
        if rent > 0:
            parts.append(f"rent ${round(rent)}")
        if veh > 0:
            parts.append(f"vehicle ${round(veh)}")
        await add_event(db, p["id"], f"00:00 daily charge: {', '.join(parts)} (${round(total)} total). Vehicles maintained.", "finance", "info")


async def accrue_businesses(db, p, cfg, gh, now):
    import employee_engine
    businesses = await db.businesses.find({"player_id": p["id"]}, {"_id": 0}).to_list(100)
    for b in businesses:
        await employee_engine.resolve_business(db, cfg, now, b)


async def release_confinement(db, p):
    now = now_utc()
    ju = parse_dt(p.get("jail_until"))
    if ju and ju <= now and p.get("status") == "jail":
        p["jail_until"] = None
        p["status"] = "free"
        p["legal_reputation"] = clamp(p["legal_reputation"] + 5)
        await add_event(db, p["id"], "You served your time and walked out of jail.", "legal", "info")
    hu = parse_dt(p.get("hospital_until"))
    if hu and hu <= now and p.get("status") == "hospital":
        p["hospital_until"] = None
        p["status"] = "free"
        p["health"] = clamp(max(p["health"], 60))
        await add_event(db, p["id"], "You were discharged from the hospital.", "health", "info")


async def maybe_autostart_shift(db, p, cfg, now):
    """SHIFT AUTO-START: when the registered shift's start time is reached in the game clock, the
    character automatically begins working. If the player is busy/confined/exhausted at that moment,
    the shift is MISSED (no auto-start) and reliability takes a hit. Registration is always cleared."""
    rs = p.get("registered_shift")
    if not rs:
        return
    start_real = parse_dt(rs.get("start_real"))
    if not start_real or now < start_real:
        return  # not time yet
    name = rs.get("shift_name", "shift")
    title = rs.get("title", "work")
    p["registered_shift"] = None  # consume the registration either way

    # Missed if confined, already busy with another activity, or on player-business shift.
    if p.get("status") in ("jail", "hospital") or p.get("current_activity") or p.get("on_shift"):
        if p.get("job"):
            p["job"]["reliability"] = clamp(p["job"].get("reliability", 50) - 5)
        await add_event(db, p["id"], f"You missed your {name} shift — you were busy when it started.", "job", "warning")
        await add_notification(db, p["id"], "job", "Shift missed", f"You were occupied and missed your {name} shift. Reliability took a hit.", "warning", "/current-job")
        return
    if p.get("energy", 0) < 10:
        if p.get("job"):
            p["job"]["reliability"] = clamp(p["job"].get("reliability", 50) - 4)
        await add_event(db, p["id"], f"You were too exhausted to start your {name} shift.", "job", "warning")
        await add_notification(db, p["id"], "job", "Shift missed", f"You were too exhausted to start your {name} shift.", "warning", "/current-job")
        return
    if not p.get("job") or p["job"].get("job_id") != rs.get("job_id"):
        return  # changed jobs since registering

    hours = int(rs["duration_hours"])
    ends = start_real + timedelta(seconds=real_seconds(hours * 60, cfg["time_scale"]))
    p["current_activity"] = {
        "kind": "job", "name": f"{title} — {name}",
        "started_at": start_real.isoformat(), "ends_at": ends.isoformat(),
        "blocking": True, "sleep_flag": False,
        "duration_minutes": hours * 60, "payload": rs["payload"],
    }
    p["status"] = "working"
    await add_event(db, p["id"], f"Your {name} shift started automatically as {title}.", "job", "info")
    await add_notification(db, p["id"], "job", "Shift started", f"Your {name} shift as {title} just started automatically.", "info", "/current-job")


async def maybe_police_event(db, p, cfg, gh):
    """PROACTIVE POLICING (legal_standing link): a player with a criminal record (legal_standing < 40)
    gets randomly stopped/searched by police. The lower the standing and the higher the suspicion,
    the more frequent and harsher the encounter. Only fires while the player is free (not confined,
    not mid-activity, not on shift). See docs/PLAYER_STATS_LOGIC.md."""
    if gh <= 0 or p.get("status") in ("jail", "hospital"):
        return
    if p.get("current_activity") or p.get("on_shift"):
        return
    legal = p.get("legal_reputation", 100)
    if legal >= 40:
        return
    per_hour = float(game_models.TUNE.get("police_event_per_hour", 0.03)) * ((40 - legal) / 40.0)
    if per_hour <= 0:
        return
    chance = 1 - (1 - min(per_hour, 0.9)) ** min(gh, 24)
    if random.random() > chance:
        return
    susp = p.get("criminal_suspicion", 0)
    p["stress"] = clamp(p["stress"] + 8)
    roll = random.random()
    if susp >= 60 and legal < 20 and roll < 0.35:
        p["jail_until"] = (now_utc() + timedelta(seconds=real_seconds(120, cfg["time_scale"]))).isoformat()
        p["status"] = "jail"
        p["criminal_suspicion"] = clamp(susp + 5)
        p["legal_reputation"] = clamp(legal - 2)
        await add_event(db, p["id"], "Police detained you for questioning — your record made you a target.", "legal", "danger")
        await add_notification(db, p["id"], "legal", "Detained by police", "Your criminal record got you pulled in for questioning.", "danger", "/police-record")
    elif susp >= 40 and roll < 0.5:
        fine = round(50 + susp * 2)
        charge(p, fine)
        ledger_add(p, "fines", -fine)
        p["criminal_suspicion"] = clamp(susp - 8)
        await add_event(db, p["id"], f"Police stopped and searched you — cited you ${fine}.", "legal", "warning")
        await add_notification(db, p["id"], "legal", "Stopped and searched", f"Police searched you and issued a ${fine} citation.", "warning", "/police-record")
    else:
        p["criminal_suspicion"] = clamp(susp - 4)
        await add_event(db, p["id"], "Police stopped you for questioning, then let you off with a warning.", "legal", "info")


async def resolve_player(db, p):
    cfg = await get_config(db)
    ts = cfg["time_scale"]
    now = now_utc()
    last = parse_dt(p.get("last_resolved_at")) or now
    elapsed = max(0.0, (now - last).total_seconds())
    gh = game_hours(elapsed, ts)

    act = p.get("current_activity")
    resting = bool(act and act.get("sleep_flag"))
    studying = bool(act and act.get("kind") == "course")

    await release_confinement(db, p)

    # Load housing early so its mood_bonus feeds the mood baseline in decay_needs (and reuse below).
    if p.get("housing") is None:
        p["housing"] = {}
    hid = (p.get("housing") or {}).get("id")
    housing_doc = await db.housing.find_one({"id": hid}, {"_id": 0}) if hid else None
    housing_mood = housing_doc.get("mood_bonus", 0.0) if housing_doc else 0.0

    if gh > 0:
        decay_needs(p, gh, cfg, resting, studying, mood_bonus=housing_mood)
        # health collapse -> hospital
        if p["health"] <= 0 and p.get("status") not in ("jail", "hospital"):
            p["health"] = 1
            p["current_activity"] = None
            p["hospital_until"] = (now + timedelta(seconds=real_seconds(360, ts))).isoformat()
            p["status"] = "hospital"
            await add_event(db, p["id"], "You collapsed from poor health and were rushed to hospital.", "health", "danger")

    # SHIFT AUTO-START: begin a registered shift the moment its start time is reached.
    await maybe_autostart_shift(db, p, cfg, now)

    act = p.get("current_activity")
    if act and parse_dt(act["ends_at"]) <= now:
        await complete_activity(db, p, cfg)

    # housing already loaded above (housing_doc / housing_mood) for the mood baseline
    if gh > 0:
        await accrue_recurring(db, p, cfg, gh, housing_doc)

    await accrue_businesses(db, p, cfg, gh, now)

    import social_engine
    await social_engine.resolve_social(db, p, cfg, gh, now)

    import employment
    await employment.resolve_npc_applications(db, p, cfg, now)
    await employment.resolve_worked_businesses(db, p, cfg, now)
    await employment.sweep_player_earnings(db, p, cfg, now)

    # PROACTIVE POLICING: a criminal record (legal_standing < 40) invites random police stops.
    await maybe_police_event(db, p, cfg, gh)

    # daily summary + 00:00 fixed-cost deduction at each in-game midnight boundary
    if cfg.get("world_start_real"):
        cur_day = game_day_index(cfg, now)
        last_day = p.get("last_summary_day")
        if last_day is None:
            p["last_summary_day"] = cur_day
        elif cur_day > last_day:
            # Claim the boundary atomically so exactly ONE resolver charges rent/vehicle and
            # writes the summary — concurrent /game/state polls can't double-charge or duplicate it.
            claim = await db.players.update_one(
                {"id": p["id"], "last_summary_day": last_day},
                {"$set": {"last_summary_day": cur_day}})
            p["last_summary_day"] = cur_day
            if claim.modified_count == 1:
                await _charge_daily_fixed(db, p, cfg, cur_day - last_day, housing_doc)
                await _flush_daily_summary(db, p, cfg, last_day, cur_day, now)

    # finalize status
    if p.get("status") not in ("jail", "hospital"):
        if p.get("current_activity"):
            p["status"] = "busy"
        elif p.get("on_shift"):
            p["status"] = "working"
        else:
            p["status"] = "free"
    p["last_resolved_at"] = now.isoformat()
    return p
