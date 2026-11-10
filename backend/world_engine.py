"""Server-owned exploration, learned qualifications and auditable weighted dice."""
from copy import deepcopy
from datetime import timedelta
import math
import random
import re
import uuid

from game_models import now_utc, clamp
from game_engine import parse_dt, real_seconds, add_money, charge, ledger_add, add_skill_xp, apply_effects, add_event, game_now
from world_content import WORLD_CONTENT, WORLD_CONFIG

COLLECTIONS = set(WORLD_CONTENT)
RNG = random.SystemRandom()


def number(value, label, low=0, high=1e9, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high or (integer and int(value) != value):
        raise ValueError(f"{label}: expected {'a whole number' if integer else 'a finite number'} from {low} to {high}")


def identifier(value, label="ID"):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", value):
        raise ValueError(f"{label}: use 1–80 letters, numbers, underscores or hyphens")


def mapping(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label}: expected an object")
    return value


def ids(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label}: expected a list of IDs")
    for x in value:
        identifier(x, label)


def numeric_map(value, label, low=0, high=1e9, integer=False):
    for key, val in mapping(value, label).items():
        identifier(key, label)
        number(val, label + "." + key, low, high, integer)


def interval(value, label, low=0, high=1e6):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(label + ": expected [minimum, maximum]")
    for x in value:
        number(x, label, low, high, True)
    if value[0] > value[1]:
        raise ValueError(label + ": minimum cannot exceed maximum")


def validate_requirements(req):
    mapping(req, "requirements")
    numeric_map(req.get("skills", {}), "skills", 1, 10000, True)
    numeric_map(req.get("training", {}), "training", 0, 100000, True)
    ids(req.get("professions", []), "professions")


def validate_definition(kind, d):
    mapping(d, kind)
    identifier(d.get("id"))
    if not isinstance(d.get("name"), str) or not d["name"].strip() or len(d["name"]) > 120:
        raise ValueError("name: enter a name up to 120 characters")
    if "active" in d and not isinstance(d["active"], bool):
        raise ValueError("active: expected true or false")
    for key in ("description", "role", "biome"):
        if key in d and (not isinstance(d[key], str) or len(d[key]) > 4000):
            raise ValueError(key + ": expected text up to 4000 characters")
    validate_requirements(d.get("requirements", {}))
    if kind == "world_regions":
        for key in ("x", "y"):
            number(d.get(key), key, 0, 100)
        if not isinstance(d.get("connections"), list):
            raise ValueError("connections: expected [{to, minutes}]")
        for c in d["connections"]:
            mapping(c, "connection"); identifier(c.get("to")); number(c.get("minutes"), "minutes", 0, 10080)
    elif kind == "world_actions":
        ids(d.get("regions"), "regions"); identifier(d.get("skill"))
        for key, high in (("difficulty", 10000), ("duration_minutes", 10080), ("energy_cost", 100), ("money_cost", 1e9), ("cooldown_minutes", 10080)):
            number(d.get(key), key, 0, high)
        numeric_map(d.get("supplies", {}), "supplies", integer=True)
        if d.get("teacher_id"):
            identifier(d["teacher_id"])
        if d.get("workshop_kind"):
            identifier(d["workshop_kind"])
        outcomes = d.get("outcomes")
        if not isinstance(outcomes, list) or not outcomes or len(outcomes) > 50:
            raise ValueError("outcomes: use 1–50 weighted outcomes")
        seen = set()
        for o in outcomes:
            mapping(o, "outcome"); identifier(o.get("id"))
            if o["id"] in seen:
                raise ValueError("outcome IDs must be unique")
            seen.add(o["id"])
            if not isinstance(o.get("success"), bool) or not isinstance(o.get("name"), str):
                raise ValueError("Each outcome needs a name and a success boolean")
            number(o.get("weight"), "weight"); interval(o.get("coins"), "coins")
            number(o.get("xp"), "xp", 0, 1e6)
            numeric_map(o.get("items", {}), "items", integer=True)
            numeric_map(o.get("training", {}), "training", integer=True)
            numeric_map(o.get("effects", {}), "effects", -100, 100)
            if set(o.get("effects", {})) - {"energy", "fatigue", "hunger", "mood", "stress", "health", "reputation", "legal_reputation", "criminal_suspicion", "social_status"}:
                raise ValueError("effects: use need, reputation or suspicion fields; coin, items and training have their own fields")
        if sum(o["weight"] for o in outcomes) <= 0:
            raise ValueError("At least one outcome must have positive weight")
    elif kind == "world_npcs":
        identifier(d.get("home_region"))
        for k in ("personality", "goal", "greeting"):
            if not isinstance(d.get(k), str) or len(d[k]) > 4000:
                raise ValueError(k + ": expected text up to 4000 characters")
        if not isinstance(d.get("schedule", []), list):
            raise ValueError("schedule: expected a list")
        for s in d.get("schedule", []):
            mapping(s, "schedule"); identifier(s.get("region"))
            number(s.get("from_hour"), "from_hour", 0, 23); number(s.get("to_hour"), "to_hour", 0, 24)
    elif kind == "world_quests":
        identifier(d.get("npc_id")); identifier(d.get("action_id"))
        number(d.get("target"), "target", 1, 100000, True); number(d.get("reward_coins"), "reward_coins")
        if not isinstance(d.get("success_only"), bool):
            raise ValueError("success_only: expected true or false")
    elif kind == "world_charters":
        identifier(d.get("kind")); number(d.get("cost"), "cost"); ids(d.get("regions"), "regions")
    elif kind == "world_origins":
        number(d.get("weight"), "weight"); interval(d.get("coins"), "coins"); interval(d.get("age"), "age", 1, 1000)
        for key, value in mapping(d.get("skills"), "skills").items():
            identifier(key); interval(value, "skills." + key, 1, 10000)
        numeric_map(d.get("inventory", {}), "inventory", integer=True)
        numeric_map(d.get("training", {}), "training", integer=True)
        for key, value in mapping(d.get("stats", {}), "stats").items():
            if key not in ("energy", "health", "hunger", "fatigue", "mood", "stress"):
                raise ValueError("Unknown starting need: " + key)
            interval(value, "stats." + key, 0, 100)
        if not isinstance(d.get("professions", []), list):
            raise ValueError("professions: expected weighted [{id, weight}] choices")
        for choice in d.get("professions", []):
            mapping(choice, "profession"); identifier(choice.get("id")); number(choice.get("weight"), "weight")


def validate_settings(s):
    mapping(s, "world")
    identifier(s.get("start_region"))
    for key in ("random_creation",):
        if not isinstance(s.get(key), bool):
            raise ValueError("world." + key + ": expected true or false")
    for key in ("base_success", "chance_per_skill", "min_success", "max_success"):
        number(s.get(key), "world." + key, 0, 1)
    if s["min_success"] > s["max_success"]:
        raise ValueError("world.min_success cannot exceed max_success")
    for key, lo, hi in (("report_limit", 1, 500), ("memory_turns", 0, 100), ("max_active_quests", 0, 50), ("max_foundings", 0, 50), ("max_pending_intents", 0, 50), ("dialogue_cooldown_seconds", 0, 3600)):
        number(s.get(key), "world." + key, lo, hi, True)


def state(p, cfg):
    w = p.setdefault("world", {})
    for key, default in {"region": cfg["world"]["start_region"], "visited": [], "training": {}, "quests": {}, "reports": [], "memories": {}, "foundings": [], "memberships": [], "profession": None, "intents": []}.items():
        w.setdefault(key, deepcopy(default))
    return w


def requirements_reason(p, req, professions, seen=None):
    w = p.get("world", {})
    for skill, level in req.get("skills", {}).items():
        if p.get("skills", {}).get(skill, {}).get("level", 1) < level:
            return f"Requires {skill.replace('_', ' ')} level {level}."
    for key, count in req.get("training", {}).items():
        current = w.get("training", {}).get(key, 0)
        if current < count:
            return f"Requires {count} successful {key.replace('_', ' ')} lessons ({current}/{count})."
    seen = set(seen or [])
    for key in req.get("professions", []):
        profession = professions.get(key)
        if key in seen:
            return "The Owner needs to repair a circular qualification requirement."
        if not profession or profession.get("active") is False:
            return "A required qualification is currently unavailable."
        reason = requirements_reason(p, profession.get("requirements", {}), professions, seen | {key})
        if reason:
            return profession["name"] + ": " + reason
    return ""


def probabilities(p, action, cfg):
    s = cfg["world"]
    level = p.get("skills", {}).get(action["skill"], {}).get("level", 1)
    chance = clamp(s["base_success"] + (level - action["difficulty"]) * s["chance_per_skill"], s["min_success"], s["max_success"])
    sums = {side: sum(o["weight"] for o in action["outcomes"] if o["success"] == side) for side in (True, False)}
    if not sums[True]:
        chance = 0
    if not sums[False]:
        chance = 1
    return [{**deepcopy(o), "probability": ((chance if o["success"] else 1 - chance) * o["weight"] / sums[o["success"]]) if sums[o["success"]] else 0} for o in action["outcomes"]]


def pick(rows, field="weight", roll=None):
    total = sum(row[field] for row in rows)
    if total <= 0:
        raise ValueError("The Owner has disabled every possible result.")
    roll = RNG.random() if roll is None else roll
    target, cumulative = roll * total, 0
    eligible = [r for r in rows if r[field] > 0]
    for row in eligible:
        cumulative += row[field]
        if target < cumulative:
            return row, roll
    return eligible[-1], roll


def origin_roll(origins):
    bg, roll = pick([x for x in origins if x.get("active") is not False])
    return {"id": bg["id"], "name": bg["name"], "description": bg.get("description", ""), "roll": roll,
            "cash": RNG.randint(*bg["coins"]), "age": RNG.randint(*bg["age"]),
            "skills": {key: RNG.randint(*limits) for key, limits in bg["skills"].items()},
            "inventory": deepcopy(bg.get("inventory", {})), "stats": {key: RNG.randint(*limits) for key, limits in bg.get("stats", {}).items()},
            "training": deepcopy(bg.get("training", {})), "professions": deepcopy(bg.get("professions", []))}


def npc_region(npc, cfg, at=None):
    hour = game_now(cfg, at).hour
    for s in npc.get("schedule", []):
        start, end = s["from_hour"], s["to_hour"]
        if (start <= hour < end) if start < end else (hour >= start or hour < end):
            return s["region"]
    return npc["home_region"]


def busy_reason(p):
    if p.get("status") in ("hospital", "jail"):
        return "You must finish recovery or detention first."
    if p.get("current_activity") or p.get("on_shift") or p.get("registered_shift"):
        return "Finish or cancel your current activity or reserved shift first."
    return ""


def action_reason(p, a, cfg, professions, npcs, at=None):
    reason = busy_reason(p) or requirements_reason(p, a.get("requirements", {}), professions)
    if reason:
        return reason
    w = state(p, cfg)
    if a["regions"] and w["region"] not in a["regions"]:
        return "Travel to a place that offers this action."
    if a.get("teacher_id"):
        teacher = npcs.get(a["teacher_id"])
        if not teacher or teacher.get("active") is False or npc_region(teacher, cfg, at) != w["region"]:
            return "Your teacher is not here at the moment."
    until = parse_dt(p.get("cooldowns", {}).get("world_" + a["id"]))
    if until and until > (at or now_utc()):
        return "Available again at " + until.isoformat()
    if p["energy"] < a["energy_cost"]:
        return "Not enough energy."
    if p["cash"] + p["bank"] < a["money_cost"]:
        return "Not enough coin."
    if any(p.get("inventory", {}).get(key, 0) < quantity for key, quantity in a.get("supplies", {}).items()):
        return "Missing required supplies."
    return ""


def prepare_action(p, a, cfg, at=None):
    at = at or now_utc()
    rows = probabilities(p, a, cfg)
    outcome, roll = pick(rows, "probability")
    outcome = deepcopy(outcome)
    outcome["coin_result"] = RNG.randint(*outcome["coins"])
    charge(p, a["money_cost"]); ledger_add(p, "expedition_costs", -a["money_cost"])
    p["energy"] = clamp(p["energy"] - a["energy_cost"])
    for key, quantity in a.get("supplies", {}).items():
        p["inventory"][key] -= quantity
    p.setdefault("cooldowns", {})["world_" + a["id"]] = (at + timedelta(seconds=real_seconds(a["duration_minutes"] + a["cooldown_minutes"], cfg["time_scale"]))).isoformat()
    return {"id": uuid.uuid4().hex, "action_id": a["id"], "name": a["name"], "skill": a["skill"], "outcome": outcome,
            "roll": roll, "chances": [{"name": o["name"], "probability": o["probability"]} for o in rows], "region": state(p, cfg)["region"]}


async def complete(db, p, cfg, payload, at):
    w = state(p, cfg)
    if payload.get("travel_to"):
        w["region"] = payload["travel_to"]
        if w["region"] not in w["visited"]:
            w["visited"].append(w["region"])
        await add_event(db, p["id"], "Arrived at " + payload["name"] + ".", "world", "info")
        return
    if any(r["id"] == payload["id"] for r in w["reports"]):
        return
    o = payload["outcome"]
    add_money(p, o["coin_result"]); ledger_add(p, "expedition_income", o["coin_result"])
    add_skill_xp(p, payload["skill"], o["xp"], cfg); apply_effects(p, o.get("effects", {}))
    for key, quantity in o.get("items", {}).items():
        p.setdefault("inventory", {})[key] = p["inventory"].get(key, 0) + quantity
    for key, count in o.get("training", {}).items():
        w["training"][key] = w["training"].get(key, 0) + count
    for q in w["quests"].values():
        if q["status"] == "active" and q["definition"]["action_id"] == payload["action_id"] and (o["success"] or not q["definition"]["success_only"]):
            q["progress"] = min(q["definition"]["target"], q["progress"] + 1)
    report = {"id": payload["id"], "name": payload["name"], "action_id": payload["action_id"], "result": o["name"], "success": o["success"], "coins": o["coin_result"], "xp": o["xp"], "skill": payload["skill"], "roll": payload["roll"], "chances": payload["chances"], "at": at.isoformat(), "training": o.get("training", {}), "effects": o.get("effects", {}), "narrative": payload.get("narrative", ""), "founding_id": payload.get("founding_id")}
    for intent in w["intents"]:
        if intent["id"] == payload.get("intent_id"):
            intent["status"] = "completed"
    w["reports"] = (w["reports"] + [report])[-cfg["world"]["report_limit"]:]
    p.setdefault("stats_meta", {})["actions_done"] = p["stats_meta"].get("actions_done", 0) + 1
    await add_event(db, p["id"], f"{payload['name']}: {o['name']} · ¤ {o['coin_result']} · {o['xp']} XP", "world", "success" if o["success"] else "warning")


def remember(w, npc_id, player_text, reply, cfg, at=None):
    memory = w["memories"].setdefault(npc_id, {"turns": [], "met_at": (at or now_utc()).isoformat(), "visits": 0})
    memory["visits"] += 1
    memory["last_at"] = (at or now_utc()).isoformat()
    limit = cfg["world"]["memory_turns"]
    turns = memory["turns"] + [{"player": player_text, "npc": reply, "at": memory["last_at"]}]
    memory["turns"] = turns[-limit:] if limit else []
    return memory


def scripted_reply(p, npc, text, offers):
    w = p["world"]
    memory = w["memories"].get(npc["id"], {})
    finished = [q["definition"]["name"] for q in w["quests"].values() if q["definition"]["npc_id"] == npc["id"] and q["status"] == "claimed"]
    intro = f"Good to see you again, {p['name']}. " if memory.get("visits") else npc["greeting"] + " "
    if finished:
        intro += "I remember your help with " + ", ".join(finished) + ". "
    lower = text.lower()
    if any(word in lower for word in ("remember", "erinner", "gesagt", "last time")) and memory.get("turns"):
        return intro + "When we last spoke, you told me: “" + memory["turns"][-1]["player"] + "”"
    if offers:
        return intro + "There is work to be done: " + offers[0]["name"] + ". " + offers[0].get("description", "")
    return intro + npc["goal"] + " The local noticeboard shows the work and training available here."
