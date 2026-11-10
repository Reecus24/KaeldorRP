"""Persisted expedition snapshots, long-term service and Owner-authored factions."""
from copy import deepcopy
from datetime import timedelta
from math import isfinite
import random
import re
from game_models import now_utc, clamp, DEFAULT_CONFIG
from game_engine import parse_dt, real_seconds, add_money, add_player_xp, add_skill_xp, ledger_add, add_event

COLLECTIONS = {"realm_ranks", "factions", "expeditions"}

def number(value, name, minimum=0, maximum=1e9, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not minimum <= value <= maximum or (integer and value != int(value)):
        raise ValueError(name + ": invalid number or outside the allowed range")

def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", value):
        raise ValueError("Use an ID of 1–80 letters, digits, underscores or hyphens")

def validate_definition(kind, d):
    from config_schema import validate_json
    validate_json(d)
    safe_id(d.get("id"))
    if not isinstance(d.get("name"), str) or not d["name"].strip():
        raise ValueError("A name is required")
    if "active" in d and not isinstance(d["active"], bool):
        raise ValueError("active must be true or false")
    if kind == "realm_ranks":
        for key in ("min_days", "min_level", "min_deeds"):
            number(d.get(key), key)
    elif kind == "factions":
        number(d.get("join_cost"), "join_cost")
        number(d.get("min_legal"), "min_legal", maximum=100)
        ranks = d.get("ranks")
        if not isinstance(ranks, list) or not 1 <= len(ranks) <= 30:
            raise ValueError("A faction needs 1–30 ranks")
        prior = {"renown": 0, "service_hours": 0, "days": 0}
        for index, rank in enumerate(ranks):
            if not isinstance(rank, dict):
                raise ValueError("Each faction rank must be an object")
            if not isinstance(rank.get("name"), str) or not rank["name"].strip():
                raise ValueError("Every rank needs a name")
            for key in prior:
                number(rank.get(key), key, minimum=prior[key])
                if index == 0 and rank[key] != 0:
                    raise ValueError("The entry rank must require zero renown, hours and days")
                prior[key] = rank[key]
    elif kind == "expeditions":
        for key in ("duration_minutes", "enemy_power", "gold", "renown", "xp", "win_damage", "loss_damage", "energy_cost", "fatigue_cost", "min_health", "cooldown_minutes", "suspicion", "min_rank"):
            number(d.get(key), key, maximum=100 if key in {"min_health", "energy_cost", "fatigue_cost", "suspicion"} else 1e9, integer=key == "min_rank")
        number(d.get("legal_change", 0), "legal_change", minimum=-100, maximum=100)
        if d.get("faction_id") is not None:
            safe_id(d["faction_id"])
        if not isinstance(d.get("supplies", {}), dict):
            raise ValueError("supplies must map item IDs to whole quantities")
        for key, value in d.get("supplies", {}).items():
            safe_id(key)
            number(value, "supplies." + key, integer=True)

def validate_settings(settings):
    for key in DEFAULT_CONFIG["realm"]:
        value = settings[key]
        if key != "tactics":
            number(value, "realm." + key)
    for key in ("min_win_chance", "max_win_chance", "base_win_chance", "defeat_xp_fraction"):
        number(settings[key], key, maximum=1)
    if settings["min_win_chance"] > settings["max_win_chance"]:
        raise ValueError("Minimum victory chance cannot exceed maximum")
    tactics = settings["tactics"]
    if not isinstance(tactics, dict) or not 1 <= len(tactics) <= 12:
        raise ValueError("Define 1–12 combat tactics")
    for key, t in tactics.items():
        safe_id(key)
        if not isinstance(t, dict):
            raise ValueError("Each tactic must be an object")
        if not isinstance(t.get("name"), str) or not t["name"].strip():
            raise ValueError("Every tactic needs a name")
        number(t.get("chance_bonus"), "chance_bonus", -1, 1)
        for field in ("damage_multiplier", "reward_multiplier"):
            number(t.get(field), field, maximum=10)

def age_days(p, now=None):
    return max(0, ((now or now_utc()) - (parse_dt(p.get("created_at")) or (now or now_utc()))).total_seconds() / 86400)

def service(p, definition, now=None):
    f = p.get("faction") or {}
    days = max(0, ((now or now_utc()) - (parse_dt(f.get("joined_at")) or (now or now_utc()))).total_seconds() / 86400)
    rank = 0
    for i, r in enumerate(definition["ranks"]):
        if days >= r["days"] and f.get("renown", 0) >= r["renown"] and f.get("service_hours", 0) >= r["service_hours"]:
            rank = i
    return {**f, "days": round(days, 2), "rank_index": rank, "rank": definition["ranks"][rank],
            "next_rank": definition["ranks"][rank + 1] if rank + 1 < len(definition["ranks"]) else None,
            "name": definition["name"], "active": definition.get("active", True)}

async def standing(db, p, now=None):
    ranks = await db.realm_ranks.find({"active": {"$ne": False}}, {"_id": 0}).to_list(100)
    ranks.sort(key=lambda r: (r["min_days"], r["min_level"], r["min_deeds"]))
    days = age_days(p, now)
    meta = p.get("stats_meta", {})
    deeds = sum(meta.get(k, 0) for k in ("actions_done", "shifts_worked", "courses_done", "expeditions_done"))
    current = {"id": "unranked", "name": "Wanderer", "description": "Make your own way in the March."}
    next_rank = None
    for rank in ranks:
        if days >= rank["min_days"] and p["level"] >= rank["min_level"] and deeds >= rank["min_deeds"]:
            current = rank
        elif next_rank is None:
            next_rank = rank
    return {"current": current, "next": next_rank, "days": round(days, 2), "deeds": deeds, "level": p["level"]}

async def combat_stats(db, p, cfg):
    s = cfg["realm"]
    power = s["base_power"] + p["level"] * s["power_per_level"]
    power += p["skills"].get("fitness", {}).get("level", 1) * s["power_per_fitness"]
    power += p["skills"].get("street_smarts", {}).get("level", 1) * s["power_per_street_skill"]
    armor = 0
    gear = []
    for slot, identifier in (p.get("equipment") or {}).items():
        if (p.get("inventory") or {}).get(identifier, 0) <= 0:
            continue
        item = await db.items.find_one({"id": identifier}, {"_id": 0})
        if item and item.get("slot") == slot:
            power += item.get("combat_power", 0)
            armor += item.get("combat_armor", 0)
            gear.append(item["name"])
    return {"power": round(power, 2), "armor": round(armor, 2), "gear": gear}

def forecast(m, stats, tactic, cfg):
    s = cfg["realm"]
    chance = clamp(s["base_win_chance"] + (stats["power"] - m["enemy_power"]) * s["chance_per_power"] + tactic["chance_bonus"], s["min_win_chance"], s["max_win_chance"])
    return {"chance": chance, "gold": round(m["gold"] * tactic["reward_multiplier"], 2),
            "win_damage": round(max(0, m["win_damage"] * tactic["damage_multiplier"] - stats["armor"]), 2),
            "loss_damage": round(max(0, m["loss_damage"] * tactic["damage_multiplier"] - stats["armor"]), 2)}

def mission_reason(p, mission, faction, now=None):
    now = now or now_utc()
    if p.get("status") in {"hospital", "jail"}:
        return "Recover or finish your sentence before departing."
    if p.get("current_activity") or p.get("on_shift") or p.get("registered_shift"):
        return "Finish your activity or cancel your reserved work shift first."
    if mission.get("faction_id"):
        if not faction or faction.get("id") != mission["faction_id"]:
            return "Join this faction to accept its orders."
        if not faction.get("active", True):
            return "This faction is not currently issuing orders."
        if faction["rank_index"] < mission["min_rank"]:
            return "Earn a higher faction rank to accept these orders."
    if p["health"] < mission["min_health"]:
        return "Requires at least " + str(mission["min_health"]) + " health."
    if p["energy"] < mission["energy_cost"]:
        return "Rest before departing; you need " + str(mission["energy_cost"]) + " energy."
    until = parse_dt(p.get("cooldowns", {}).get("expedition_" + mission["id"]))
    if until and until > now:
        return "Restocking this expedition. Available in " + str(int((until - now).total_seconds() / 60) + 1) + " real min."
    for item, quantity in mission.get("supplies", {}).items():
        if p.get("inventory", {}).get(item, 0) < quantity:
            return "Gather the listed supplies before departing."
    return ""

def prepare(p, mission, tactic_id, cfg, stats, now=None, rng=None):
    now = now or now_utc()
    rng = rng or random.SystemRandom()
    tactic = cfg["realm"]["tactics"][tactic_id]
    f = forecast(mission, stats, tactic, cfg)
    won = rng.random() < f["chance"]
    for item, quantity in mission.get("supplies", {}).items():
        p["inventory"][item] = p["inventory"].get(item, 0) - quantity
    p["energy"] = clamp(p["energy"] - mission["energy_cost"])
    p["fatigue"] = clamp(p["fatigue"] + mission["fatigue_cost"])
    p.setdefault("cooldowns", {})["expedition_" + mission["id"]] = (now + timedelta(seconds=real_seconds(mission["duration_minutes"] + mission["cooldown_minutes"], cfg["time_scale"]))).isoformat()
    return {"mission": deepcopy(mission), "tactic": tactic["name"], "won": won,
            "gold": f["gold"] if won else 0, "damage": f["win_damage"] if won else f["loss_damage"],
            "xp": mission["xp"] if won else mission["xp"] * cfg["realm"]["defeat_xp_fraction"]}

async def complete(db, p, cfg, payload, at):
    mission = payload["mission"]
    p["health"] = clamp(p["health"] - payload["damage"])
    add_money(p, payload["gold"])
    ledger_add(p, "expedition_income", payload["gold"])
    add_player_xp(p, payload["xp"], cfg)
    p["criminal_suspicion"] = clamp(p["criminal_suspicion"] + mission["suspicion"])
    p["legal_reputation"] = clamp(p["legal_reputation"] + mission["legal_change"])
    p.setdefault("stats_meta", {})["expeditions_done"] = p.get("stats_meta", {}).get("expeditions_done", 0) + 1
    faction = p.get("faction")
    if faction and faction["id"] == mission.get("faction_id"):
        faction["service_hours"] += mission["duration_minutes"] / 60
        faction["renown"] += mission["renown"] if payload["won"] else 0
    report = {"name": mission["name"], "won": payload["won"], "gold": payload["gold"], "damage": payload["damage"], "xp": payload["xp"],
              "renown": mission["renown"] if payload["won"] else 0, "tactic": payload["tactic"], "at": at.isoformat()}
    p["battle_reports"] = [report] + p.get("battle_reports", [])[:19]
    await add_event(db, p["id"], mission["name"] + (": victory." if payload["won"] else ": forced to retreat.") + " Lost " + str(payload["damage"]) + " health; earned " + str(payload["gold"]) + " coins.", "expedition", "success" if payload["won"] else "warning")
