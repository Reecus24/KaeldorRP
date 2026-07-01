"""Kaeldor RPG - social contacts & relationships system.

Per-player NPC contacts live in the `contacts` collection. All time-based
effects (relationship decay, mood drift, random social events, firing/eviction
risk, partner expenses) resolve on offline catch-up via resolve_social().
Content (archetypes, traits, actions, events, gifts) is admin-editable.
"""
import uuid
import random
from datetime import timedelta

from game_models import clamp, now_utc
from game_engine import add_event, parse_dt, real_seconds, charge, add_money, apply_effects, add_notification, ledger_add, ledger_warn, ledger_event
import employee_engine


# ----------------------------- content helpers -----------------------------
async def _archetypes(db):
    return await db.npc_archetypes.find({}, {"_id": 0}).to_list(200)


async def _traits(db):
    return await db.social_traits.find({}, {"_id": 0}).to_list(200)


def derive_status(c):
    """Map a contact's numbers to a status, preserving sticky states."""
    st = c.get("status")
    if st in ("blocked", "ex_partner"):
        return st
    score = c.get("relationship_score", 0)
    if st == "romantic":
        return "ex_partner" if score <= -30 else "romantic"
    if score >= 75:
        return "close"
    if score >= 25:
        return "active"
    if score >= -20:
        return "distant"
    return "angry"


# ----------------------------- contact creation -----------------------------
async def create_contact(db, p, archetype=None, archetype_id=None, name=None, key=None, announce=True):
    arche = archetype
    arcs = None
    if arche is None:
        arcs = await _archetypes(db)
        if archetype_id:
            arche = next((a for a in arcs if a["id"] == archetype_id), None)
        if arche is None and arcs:
            arche = random.choice(arcs)
    if arche is None:
        return None
    traits_all = await _traits(db)
    pool = [t for t in traits_all if t["id"] in arche.get("trait_pool", [])] or traits_all
    n = random.choices([1, 2], weights=[3, 2])[0]
    chosen = [t["id"] for t in random.sample(pool, min(n, len(pool)))] if pool else []
    romance = arche.get("romance_capable", False)
    now = now_utc()
    c = {
        "id": uuid.uuid4().hex,
        "player_id": p["id"],
        "key": key,
        "name": name or employee_engine._gen_name(),
        "age": random.randint(arche.get("age_min", 20), arche.get("age_max", 55)),
        "archetype_id": arche["id"],
        "archetype_label": arche.get("label", ""),
        "relationship_type": arche["relationship_type"],
        "category": arche.get("category", "friend"),
        "relationship_score": float(arche.get("start_score", 10)),
        "trust": float(arche.get("base_trust", 30)),
        "respect": float(arche.get("base_respect", 30)),
        "attraction": float(arche.get("base_attraction", 0)) if romance else 0.0,
        "romance_capable": romance,
        "mood": float(random.randint(55, 80)),
        "traits": chosen,
        "status": "active",
        "decay_rate": float(arche.get("decay_rate", 1.0)),
        "last_interaction_at": now.isoformat(),
        "known_since": now.isoformat(),
        "created_at": now.isoformat(),
        "history": [{"ts": now.isoformat(), "text": arche.get("intro_text", "You met."), "type": "meet"}],
        "cooldowns": {},
        "notes": arche.get("desc", ""),
        "perk": arche.get("perk"),
    }
    c["status"] = derive_status(c)
    await db.contacts.insert_one({**c})
    if announce:
        await add_event(db, p["id"], f"You met {c['name']} — {arche.get('label', c['relationship_type'].replace('_', ' '))}.", "social", "info")
    return c


async def _has_key(db, p, key):
    return await db.contacts.find_one({"player_id": p["id"], "key": key}, {"_id": 0})


async def ensure_job_contacts(db, p, job=None):
    # Socials 3.0: you inherently know your direct manager (boss). Colleagues are met via
    # the "Network at Work" location action, not auto-added.
    if not await _has_key(db, p, "boss"):
        await create_contact(db, p, archetype_id="boss", key="boss", announce=False)


async def ensure_landlord(db, p, housing=None):
    if not await _has_key(db, p, "landlord"):
        await create_contact(db, p, archetype_id="landlord", key="landlord", announce=False)


async def ensure_business_contact(db, p, biz_type=None):
    if await db.contacts.count_documents({"player_id": p["id"], "relationship_type": "business_contact"}) == 0:
        await create_contact(db, p, archetype_id="business_contact", announce=False)


async def seed_starter_contacts(db, p):
    starters = ["best_friend", "old_friend", "love_interest", "shady_dealer", "mentor", "sibling"]
    for aid in starters:
        await create_contact(db, p, archetype_id=aid, announce=False)
    await add_event(db, p["id"], "Your social circle takes shape: a few friends, family, a mentor, and some... interesting contacts.", "social", "info")


def _set_crime_buff(p, cfg):
    scfg = cfg.get("social", {})
    hours = scfg.get("shady_buff_hours", 6)
    mult = scfg.get("shady_buff_mult", 0.65)
    p["social_buffs"] = {"crime_risk_mult": mult, "until": (now_utc() + timedelta(hours=hours)).isoformat()}


# ----------------------------- professional perks (Socials 2.0/3.0) -----------------------------
# Networking with a Manager (wage discount) or Wholesaler (material discount) unlocks a PERMANENT,
# player-level business discount once trust & relationship are high enough. Multiple contacts stack
# up to a hard cap.
PERK_STEP_DEFAULT = 0.05
PERK_CAP = 0.20
PERK_TRUST_MIN = 60
PERK_SCORE_MIN = 50


def _grant_perk(p, perk):
    if not perk:
        return None
    ptype = perk.get("type")
    step = perk.get("step", PERK_STEP_DEFAULT)
    perks = p.setdefault("social_perks", {})
    cur = perks.get(ptype, 0.0)
    if cur >= PERK_CAP - 1e-9:
        return None
    perks[ptype] = round(min(PERK_CAP, cur + step), 4)
    return {"type": ptype, "value": perks[ptype], "label": perk.get("label", ptype)}


# ----------------------------- offline resolution -----------------------------
async def resolve_social(db, p, cfg, gh, now):
    scfg = cfg.get("social", {})

    # Socials 3.0: NO auto-seeded circle. Players start with an empty circle and must
    # MEET people via location actions (bar / gym / work) before they can interact.
    if not p.get("social_seeded"):
        p["social_seeded"] = True

    contacts = await db.contacts.find({"player_id": p["id"]}, {"_id": 0}).to_list(400)
    if not contacts:
        return

    traits_map = {t["id"]: t for t in await _traits(db)}
    decay_per_day = scfg.get("decay_per_day", 3.0)
    close_mult = scfg.get("close_decay_mult", 0.4)
    angry_worsen = scfg.get("angry_worsen_per_day", 1.5)
    grace_h = scfg.get("decay_grace_hours", 8)

    changed = []
    pos_weight = neg_weight = 0.0
    partner_count = 0

    for c in contacts:
        dirty = False
        st = c.get("status")
        if st == "blocked":
            continue
        last = parse_dt(c.get("last_interaction_at")) or now
        idle_h = (now - last).total_seconds() / 3600.0
        score = c.get("relationship_score", 0)

        if gh > 0 and idle_h > grace_h:
            tmult = 1.0
            for t in c.get("traits", []):
                tmult *= (1 + traits_map.get(t, {}).get("effects", {}).get("decay_mult", 0))
            tmult = max(0.2, tmult)
            rate = decay_per_day * c.get("decay_rate", 1.0) * tmult * gh / 24.0
            if st == "angry" or score <= -20:
                c["relationship_score"] = clamp(score - angry_worsen * c.get("decay_rate", 1.0) * gh / 24.0, -100, 100)
                dirty = True
            elif score > 0:
                if score >= 75:
                    rate *= close_mult
                c["relationship_score"] = clamp(score - min(rate, score), -100, 100)
                c["trust"] = clamp(c.get("trust", 30) - rate * 0.3)
                dirty = True
            if c.get("romance_capable") and c.get("attraction", 0) > 0:
                c["attraction"] = clamp(c.get("attraction", 0) - rate * 0.4)
                dirty = True

        if gh > 0:
            newmood = clamp(c.get("mood", 60) + (62 - c.get("mood", 60)) * min(1, 0.05 * gh))
            if abs(newmood - c.get("mood", 60)) > 0.01:
                c["mood"] = newmood
                dirty = True

        newst = derive_status(c)
        if newst != c.get("status"):
            c["status"] = newst
            dirty = True

        score = c.get("relationship_score", 0)
        w = 2.0 if c.get("status") in ("close", "romantic") else 1.0
        if score >= 40:
            pos_weight += (score - 40) / 60.0 * w
        if score <= -20 or c.get("status") == "angry":
            neg_weight += (abs(min(score, -20)) - 20) / 80.0 * w + 0.3
        if c.get("status") == "romantic":
            partner_count += 1

        if dirty:
            changed.append(c)

    # aggregate mood / stress effect on the player
    if gh > 0:
        net = clamp(pos_weight - neg_weight, -4, 4)
        p["mood"] = clamp(p["mood"] + net * scfg.get("mood_factor", 0.35) * gh)
        p["stress"] = clamp(p["stress"] - net * scfg.get("stress_factor", 0.25) * gh)
        pcost = scfg.get("partner_cost_per_day", 25) * partner_count * gh / 24.0
        if pcost > 0:
            charge(p, round(pcost, 2))
            ledger_add(p, "living_costs", -round(pcost, 2))

    # angry-boss firing risk
    if gh > 0 and p.get("job"):
        boss = await db.contacts.find_one({"player_id": p["id"], "key": "boss"}, {"_id": 0})
        if boss and (boss.get("status") == "angry" or boss.get("relationship_score", 0) <= -45):
            if random.random() < scfg.get("fire_risk_per_day", 0.15) * gh / 24.0:
                title = p["job"]["title"]
                p["job"] = None
                await add_event(db, p["id"], f"Your boss {boss['name']} had enough — you were FIRED from your {title} job.", "job", "danger")
                await add_notification(db, p["id"], "job", "You were fired", f"{boss['name']} fired you from your {title} job.", "danger", "/jobs")
                ledger_warn(p, f"Fired from your {title} job by an angry boss.")

    # angry-landlord eviction warning
    if gh > 0 and p.get("housing", {}).get("id") and not p.get("housing", {}).get("owned"):
        ll = await db.contacts.find_one({"player_id": p["id"], "key": "landlord"}, {"_id": 0})
        if ll and (ll.get("status") == "angry" or ll.get("relationship_score", 0) <= -45):
            if random.random() < scfg.get("evict_warn_per_day", 0.25) * gh / 24.0:
                await add_event(db, p["id"], f"Your landlord {ll['name']} is threatening eviction. Smooth things over before it's too late.", "housing", "warning")
                await add_notification(db, p["id"], "housing", "Eviction warning", f"{ll['name']} is threatening to evict you.", "warning", "/social")
                ledger_warn(p, "Landlord threatened eviction.")

    # random social event
    if gh > 0:
        chance = min(0.5, scfg.get("event_chance_per_day", 4.0) * gh / 24.0)
        if random.random() < chance:
            await _roll_social_event(db, p, cfg, contacts, changed)

    for c in {x["id"]: x for x in changed}.values():
        await db.contacts.update_one({"id": c["id"]}, {"$set": c})


async def _roll_social_event(db, p, cfg, contacts, changed):
    templates = await db.social_events.find({}, {"_id": 0}).to_list(200)
    if not templates:
        return
    types_present = {c["relationship_type"] for c in contacts if c.get("status") != "blocked"}
    pool = [t for t in templates if t.get("relationship_type") in (None, "any") or t.get("relationship_type") in types_present]
    if not pool:
        return
    total = sum(t.get("weight", 1) for t in pool)
    r = random.uniform(0, total)
    acc = 0
    tpl = pool[-1]
    for t in pool:
        acc += t.get("weight", 1)
        if r <= acc:
            tpl = t
            break
    rt = tpl.get("relationship_type")
    cands = [c for c in contacts if c.get("status") != "blocked" and (rt in (None, "any") or c["relationship_type"] == rt)]
    target = random.choice(cands) if cands else None
    ef = tpl.get("effects", {})
    now = now_utc()
    if target:
        for k in ("relationship_score", "trust", "respect", "attraction"):
            if k in ef:
                lo = -100 if k == "relationship_score" else 0
                target[k] = clamp(target.get(k, 0) + ef[k], lo, 100)
        if ef.get("interact"):
            target["last_interaction_at"] = now.isoformat()
        target["status"] = derive_status(target)
        msg_t = tpl.get("message", "").replace("{name}", target["name"])
        target.setdefault("history", []).append({"ts": now.isoformat(), "text": msg_t, "type": "event"})
        target["history"] = target["history"][-40:]
        changed.append(target)
    pe = tpl.get("player_effects", {})
    if pe:
        apply_effects(p, pe)
        if "cash" in pe:
            ledger_add(p, "social_income", pe["cash"])
    msg = tpl.get("message", "Something happened in your social life.").replace("{name}", target["name"] if target else "Someone")
    ledger_event(p, msg)
    await add_event(db, p["id"], msg, "social", tpl.get("severity", "info"))


# ----------------------------- interaction resolution -----------------------------
def validate_action(p, c, a):
    rt = c.get("relationship_type")
    applies = a.get("applies_to", "all")
    if applies != "all" and rt not in applies:
        return False, "Not available for this contact"
    if a.get("romance_only") and not c.get("romance_capable"):
        return False, "Only for romantic interests"
    if c.get("status") == "blocked":
        return False, "This contact is blocked"
    req = a.get("requires", {})
    if c.get("relationship_score", 0) < req.get("min_score", -100):
        return False, f"Needs relationship {req['min_score']}+"
    if c.get("trust", 0) < req.get("min_trust", 0):
        return False, f"Needs trust {req['min_trust']}+"
    if req.get("status_in") and c.get("status") not in req["status_in"]:
        return False, "Not available right now"
    return True, ""


async def _apply_interaction(db, p, cfg, c, a, gift, eff=1.0):
    traits_map = {t["id"]: t for t in await _traits(db)}
    succ = a.get("success", {})
    chance = succ.get("base", 0.8)
    chance += succ.get("score_factor", 0) * (c.get("relationship_score", 0) / 100.0)
    chance += succ.get("trust_factor", 0) * (c.get("trust", 0) / 100.0)
    chance += succ.get("charisma_factor", 0) * (p["skills"].get("charisma", {}).get("level", 1) / 10.0)
    for t in c.get("traits", []):
        chance += traits_map.get(t, {}).get("effects", {}).get("success_mod", 0)
    chance += (p.get("reputation", 50) - 50) / 500.0
    chance += p.get("equip_bonus", {}).get("social_success", 0.0)  # equipped outfit/accessory
    chance = max(0.05, min(0.98, chance)) * (0.85 + 0.15 * eff)
    success = random.random() < chance
    block = a.get("on_success" if success else "on_fail", {}) or {}
    kind = a.get("kind")

    c["relationship_score"] = clamp(c.get("relationship_score", 0) + block.get("relationship_score", 0), -100, 100)
    c["trust"] = clamp(c.get("trust", 0) + block.get("trust", 0))
    c["respect"] = clamp(c.get("respect", 0) + block.get("respect", 0))
    if c.get("romance_capable"):
        c["attraction"] = clamp(c.get("attraction", 0) + block.get("attraction", 0))
    c["mood"] = clamp(c.get("mood", 60) + block.get("c_mood", 0))

    extra = {}
    if kind == "give_gift" and gift and success:
        g = gift.get("on_give", gift)
        c["relationship_score"] = clamp(c["relationship_score"] + g.get("relationship_score", 0), -100, 100)
        c["trust"] = clamp(c["trust"] + g.get("trust", 0))
        c["respect"] = clamp(c["respect"] + g.get("respect", 0))
        if c.get("romance_capable"):
            c["attraction"] = clamp(c["attraction"] + g.get("attraction", 0))
        c["mood"] = clamp(c["mood"] + g.get("c_mood", 0))

    pmap = {"p_mood": "mood", "p_stress": "stress", "p_energy": "energy",
            "p_reputation": "reputation", "p_social_status": "social_status", "p_suspicion": "criminal_suspicion"}
    for bk, pk in pmap.items():
        if bk in block:
            p[pk] = clamp(p[pk] + block[bk])

    if success:
        if kind == "ask_loan":
            # A personal loan is REAL money you must pay back — added to your debt.
            borrowed = round(40 + c.get("trust", 0) * 3)
            extra["cash"] = borrowed
            extra["loan"] = borrowed
            add_money(p, borrowed)
            p["debt"] = round(p.get("debt", 0) + borrowed, 2)
        elif kind == "ask_favor":
            # A favor is help/information, NOT repeatable free cash. Small, non-monetary benefit.
            p["stress"] = clamp(p["stress"] - 5)
            extra["favor"] = True
            if c.get("relationship_type") in ("boss", "coworker", "mentor") and p.get("job"):
                p["job"]["reliability"] = clamp(p["job"].get("reliability", 50) + 4)
                extra["favor_note"] = "put in a good word for you at work"
            else:
                extra["favor_note"] = "helped you sort something out"
        elif kind == "ask_reference" and p.get("job"):
            p["job"]["reliability"] = clamp(p["job"].get("reliability", 50) + 10)
        elif kind == "meet_shady":
            _set_crime_buff(p, cfg)
        elif kind == "network_pro":
            if (c.get("perk") and not c.get("perk_granted")
                    and c.get("trust", 0) >= PERK_TRUST_MIN
                    and c.get("relationship_score", 0) >= PERK_SCORE_MIN):
                granted = _grant_perk(p, c["perk"])
                if granted:
                    c["perk_granted"] = True
                    extra["perk"] = granted
        elif kind == "invite_date" and c.get("romance_capable"):
            if c.get("attraction", 0) >= 65 and c.get("relationship_score", 0) >= 55 and c.get("status") != "romantic":
                c["status"] = "romantic"
                extra["became_romantic"] = True

    name = c["name"]
    msg = (a.get("success_text", "It went well.") if success else a.get("fail_text", "It didn't go well.")).replace("{name}", name)
    if extra.get("loan"):
        msg += f" (+${extra['loan']} borrowed — added to your debt to repay)"
    elif extra.get("cash"):
        msg += f" (+${extra['cash']})"
    if extra.get("favor_note"):
        msg += f" — {name} {extra['favor_note']}."
    if extra.get("became_romantic"):
        msg = f"You and {name} are officially together now! " + msg
    if extra.get("perk"):
        pk = extra["perk"]
        pct = round(pk["value"] * 100)
        msg += f" 🎉 Unlocked: {pk['label']} now {pct}% (permanent, applies to all your businesses)."
    return msg, ("success" if success else "warning")


async def interact_now(db, p, cfg, c, a, gift):
    msg, sev = await _apply_interaction(db, p, cfg, c, a, gift, 1.0)
    now = now_utc()
    c["last_interaction_at"] = now.isoformat()
    cdm = a.get("cooldown_minutes", 0)
    if cdm > 0:
        c.setdefault("cooldowns", {})[a["id"]] = (now + timedelta(seconds=real_seconds(cdm, cfg["time_scale"]))).isoformat()
    c["status"] = derive_status(c)
    c.setdefault("history", []).append({"ts": now.isoformat(), "text": msg, "type": "interaction"})
    c["history"] = c["history"][-40:]
    await db.contacts.update_one({"id": c["id"]}, {"$set": c})
    await add_event(db, p["id"], f"{c['name']}: {msg}", "social", sev)
    return {"message": msg, "severity": sev}


async def complete_social_activity(db, p, cfg, payload, eff):
    loc_id = payload.get("location_id")
    if loc_id:
        loc = await db.locations.find_one({"id": loc_id}, {"_id": 0})
        if loc:
            await _visit_location(db, p, cfg, loc, eff)
        return
    aid = payload.get("action_id")
    a = await db.relationship_actions.find_one({"id": aid}, {"_id": 0})
    if not a:
        return
    if a.get("untargeted"):
        return
    c = await db.contacts.find_one({"id": payload.get("contact_id"), "player_id": p["id"]}, {"_id": 0})
    if not c:
        return
    msg, sev = await _apply_interaction(db, p, cfg, c, a, payload.get("gift"), eff)
    now = now_utc()
    c["last_interaction_at"] = now.isoformat()
    cdm = a.get("cooldown_minutes", 0)
    if cdm > 0:
        c.setdefault("cooldowns", {})[a["id"]] = (now + timedelta(seconds=real_seconds(cdm, cfg["time_scale"]))).isoformat()
    c["status"] = derive_status(c)
    c.setdefault("history", []).append({"ts": now.isoformat(), "text": msg, "type": "interaction"})
    c["history"] = c["history"][-40:]
    await db.contacts.update_one({"id": c["id"]}, {"$set": c})
    await add_event(db, p["id"], f"{c['name']}: {msg}", "social", sev)


def _discover_success(p, a, eff):
    succ = a.get("success", {})
    chance = succ.get("base", 0.8) + succ.get("charisma_factor", 0) * (p["skills"].get("charisma", {}).get("level", 1) / 10.0)
    return random.random() < min(0.97, chance) * (0.85 + 0.15 * eff)


async def _do_meet_at(db, p, cfg, a, eff, archetype_ids, weights, place_label):
    """Roleplay meeting: at a venue you have a CHANCE to meet a specific kind of NPC.
    New contacts are added to your circle only through these location actions."""
    if archetype_ids and _discover_success(p, a, eff):
        aid = random.choices(archetype_ids, weights=weights)[0]
        c = await create_contact(db, p, archetype_id=aid, announce=False)
        p["mood"] = clamp(p["mood"] + 5)
        p["social_status"] = clamp(p["social_status"] + 1)
        if c:
            label = c.get("archetype_label") or c["relationship_type"].replace("_", " ")
            note = ""
            if c.get("perk"):
                note = " Build the relationship (Talk Business) to unlock a permanent business perk."
            await add_event(db, p["id"], f"At {place_label} you met {c['name']} — {label}.{note}", "social", "success")
    else:
        p["stress"] = clamp(p["stress"] + 4)
        p["mood"] = clamp(p["mood"] + 1)
        await add_event(db, p["id"], f"You spent time at {place_label} but didn't click with anyone new.", "social", "info")


async def _visit_location(db, p, cfg, loc, eff):
    """Resolve a Socials 3.0 location visit using the location's DB-defined encounter weights."""
    if loc.get("suspicion_gain"):
        p["criminal_suspicion"] = clamp(p.get("criminal_suspicion", 0) + loc["suspicion_gain"])
    npcs = [n for n in (loc.get("npcs") or []) if n.get("archetype_id") and n.get("weight", 0) > 0]
    ids = [n["archetype_id"] for n in npcs]
    weights = [n["weight"] for n in npcs]
    a = {"success": {"base": loc.get("success_base", 0.72), "charisma_factor": loc.get("charisma_factor", 0.3)}}
    await _do_meet_at(db, p, cfg, a, eff, ids, weights, loc.get("name", "the venue"))


# ----------------------------- serialization for the API -----------------------------
def contact_view(c):
    now = now_utc()
    last = parse_dt(c.get("last_interaction_at")) or now
    idle = (now - last).total_seconds()
    return {
        "id": c["id"], "name": c["name"], "age": c.get("age"),
        "archetype_id": c.get("archetype_id"), "archetype_label": c.get("archetype_label"),
        "relationship_type": c.get("relationship_type"), "category": c.get("category"),
        "relationship_score": round(c.get("relationship_score", 0)),
        "trust": round(c.get("trust", 0)), "respect": round(c.get("respect", 0)),
        "attraction": round(c.get("attraction", 0)), "romance_capable": c.get("romance_capable", False),
        "mood": round(c.get("mood", 60)), "traits": c.get("traits", []),
        "status": c.get("status"), "key": c.get("key"),
        "last_interaction_seconds": round(idle),
        "known_since": c.get("known_since"), "notes": c.get("notes", ""),
        "decaying": idle > 3 * 86400,
        "perk": c.get("perk"), "perk_granted": c.get("perk_granted", False),
    }


async def actions_for_contact(db, p, c, cfg):
    acts = await db.relationship_actions.find({"untargeted": {"$ne": True}}, {"_id": 0}).to_list(200)
    out = []
    for a in acts:
        ok, reason = validate_action(p, c, a)
        cd = c.get("cooldowns", {}).get(a["id"])
        on_cd = cd and parse_dt(cd) > now_utc()
        applies = a.get("applies_to", "all")
        if applies != "all" and c.get("relationship_type") not in applies:
            continue
        if a.get("romance_only") and not c.get("romance_capable"):
            continue
        out.append({**a, "available": bool(ok and not on_cd),
                    "reason": reason if not ok else ("On cooldown" if on_cd else ""),
                    "cooldown_remaining": round((parse_dt(cd) - now_utc()).total_seconds()) if on_cd else 0})
    return out


def contact_opportunities(c):
    out = []
    rt = c.get("relationship_type")
    s = c.get("relationship_score", 0)
    t = c.get("trust", 0)
    if c.get("perk"):
        if c.get("perk_granted"):
            out.append(f"Perk unlocked: {c['perk'].get('label', 'business perk')} (+{round(c['perk'].get('step', 0.05)*100)}%, permanent).")
        else:
            out.append(f"Talk Business to reach Trust {PERK_TRUST_MIN}+ and Relationship {PERK_SCORE_MIN}+ — unlocks a permanent {c['perk'].get('label', 'business perk')}.")
    if rt in ("boss", "coworker", "mentor") and s >= 50:
        out.append("Will give you a strong job reference (boosts reputation & reliability).")
    if rt == "boss" and s >= 40:
        out.append("A friendly boss means smoother promotions and fewer bad shifts.")
    if rt == "landlord" and s >= 45:
        out.append("Flexible on rent and likely to return your deposit in full.")
    if rt == "shady_contact" and t >= 40:
        out.append("Can lower your heat — reduces police risk on your next crime.")
    if c.get("status") == "romantic":
        out.append("Romantic partner — boosts your mood and life stability (but costs money).")
    if not out:
        out.append("Build this relationship to unlock opportunities.")
    return out


def contact_warnings(c):
    out = []
    st = c.get("status")
    rt = c.get("relationship_type")
    s = c.get("relationship_score", 0)
    if st == "angry":
        out.append("Relationship damaged — apologize before it causes real problems.")
    last = parse_dt(c.get("last_interaction_at"))
    if last:
        idle_days = (now_utc() - last).total_seconds() / 86400.0
        if idle_days > 3:
            out.append(f"You haven't connected in {int(idle_days)} days — the bond is fading.")
    if rt == "boss" and s <= -30:
        out.append("Your boss is fed up — you risk being fired.")
    if rt == "landlord" and s <= -30:
        out.append("Your landlord is upset — you risk eviction.")
    if st == "ex_partner":
        out.append("This is an ex-partner. Things ended.")
    return out


def social_summary(views):
    n = len(views)
    return {
        "total": n,
        "close": sum(1 for v in views if v["status"] == "close"),
        "romantic": sum(1 for v in views if v["status"] == "romantic"),
        "angry": sum(1 for v in views if v["status"] == "angry"),
        "avg_score": round(sum(v["relationship_score"] for v in views) / n) if n else 0,
    }
