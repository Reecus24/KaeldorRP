"""Data-driven progression. Claim markers and rewards share one player save.
Accepted definitions are snapshots; template changes cannot invalidate a run.
Routes run under the existing authenticated player-operation lease.
"""
from copy import deepcopy
from datetime import timedelta
import math
import re
from game_models import SKILLS, clamp
from game_engine import parse_dt, now_utc, charge, add_money, add_player_xp, add_skill_xp, ledger_add
from config_schema import validate_content

COLLECTIONS = {"journey_goals", "story_arcs", "city_events"}
METRICS = {"funds", "bank", "shifts", "actions", "courses", "businesses", "business_revenue",
           "contacts", "level", "reputation", "stories_completed"}
STATS = {"reputation", "legal_reputation", "social_status", "criminal_suspicion"}


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise ValueError("Use IDs of 1–80 letters, numbers, underscores or hyphens.")


def _number(value, minimum=0, maximum=1_000_000):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"Expected a finite number between {minimum} and {maximum}.")


def _requirements(reqs):
    if not isinstance(reqs, list) or len(reqs) > 20:
        raise ValueError("Requirements must be a list with at most 20 entries.")
    for r in reqs:
        if not isinstance(r, dict):
            raise ValueError("Each requirement must be an object.")
        metric = r.get("metric", "")
        if not isinstance(metric, str):
            raise ValueError("A requirement metric must be text.")
        if metric not in METRICS:
            if not isinstance(metric, str) or not metric.startswith(("skill:", "item:")):
                raise ValueError(f"Unknown progress metric: {metric}")
            _id(metric.split(":", 1)[1])
            if metric.startswith("skill:") and metric.split(":", 1)[1] not in SKILLS:
                raise ValueError("Unknown skill.")
        _number(r.get("target"))
        if "label" in r and not isinstance(r["label"], str):
            raise ValueError("Requirement labels must be text.")
        if not isinstance(r.get("since_start", False), bool):
            raise ValueError("since_start must be true or false.")
        if r.get("since_start") and metric not in {"shifts", "actions", "courses", "stories_completed"}:
            raise ValueError("Relative progress supports shifts, actions, courses and stories_completed.")
        if not isinstance(r.get("href", "/journey"), str) or r.get("href", "/journey").startswith("//") or not re.fullmatch(r"/[a-zA-Z0-9_/#-]*", r.get("href", "/journey")):
            raise ValueError("Requirement links must be local game paths.")


def _rewards(rewards):
    if not isinstance(rewards, dict):
        raise ValueError("Rewards must be an object.")
    for k, v in rewards.items():
        if k in STATS:
            _number(v, -100, 100)
        elif k in {"cash", "xp"}:
            _number(v)
        elif k in {"skills", "items"}:
            if not isinstance(v, dict):
                raise ValueError(f"{k} must be an object.")
            for name, amount in v.items():
                _id(name)
                _number(amount)
                if k == "skills" and name not in SKILLS:
                    raise ValueError("Unknown reward skill.")
                if k == "items" and int(amount) != amount:
                    raise ValueError("Item quantities must be whole numbers.")
        else:
            raise ValueError(f"Unsupported reward: {k}")


def validate_definition(kind, doc):
    validate_content(doc)
    _id(doc.get("id"))
    if not isinstance(doc.get("name"), str) or not doc["name"].strip():
        raise ValueError("A name is required.")
    for flag in ("active", "event_only"):
        if flag in doc and not isinstance(doc[flag], bool):
            raise ValueError(f"{flag} must be true or false.")
    def text_fields(obj):
        for key in ("name", "description", "contact", "title", "text", "label", "outcome", "detail"):
            if key in obj and (not isinstance(obj[key], str) or len(obj[key]) > 8000):
                raise ValueError(f"{key} must be text of at most 8,000 characters.")
    text_fields(doc)
    if kind == "city_events":
        for field in ("offset_hours", "duration_hours", "repeat_hours"):
            _number(doc.get(field), 0, 87600)
        if doc["duration_hours"] <= 0 or doc["repeat_hours"] < doc["duration_hours"]:
            raise ValueError("Event duration must be positive and no greater than its repeat interval (real hours).")
        if not isinstance(doc.get("arc_ids"), list) or not doc["arc_ids"]:
            raise ValueError("An event needs at least one story ID in arc_ids.")
        for aid in doc["arc_ids"]:
            _id(aid)
        return doc
    _requirements(doc.get("requirements", []))
    entries = doc.get("milestones" if kind == "journey_goals" else "nodes")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 60:
        raise ValueError("Provide between 1 and 60 milestones or story nodes.")
    ids = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Milestones and story nodes must be objects.")
        _id(entry.get("id"))
        if entry["id"] in ids:
            raise ValueError("Milestone/node IDs must be unique.")
        ids.add(entry["id"])
        text_fields(entry)
        if kind == "journey_goals":
            if not isinstance(entry.get("name"), str) or not entry["name"].strip():
                raise ValueError("Each milestone needs a name.")
            _requirements(entry.get("requirements", []))
            _rewards(entry.get("rewards", {}))
        else:
            choices = entry.get("choices")
            if not isinstance(choices, list) or not 1 <= len(choices) <= 12:
                raise ValueError("Each story node needs 1–12 choices.")
            cids = set()
            for c in choices:
                if not isinstance(c, dict):
                    raise ValueError("Each choice must be an object.")
                _id(c.get("id"))
                if c["id"] in cids:
                    raise ValueError("Choice IDs must be unique within a node.")
                cids.add(c["id"])
                text_fields(c)
                if c.get("next") is not None:
                    _id(c["next"])
                _number(c.get("cost", 0))
                _requirements(c.get("requirements", []))
                _rewards(c.get("rewards", {}))
                _rewards({"items": c.get("consume_items", {})})
                if not isinstance(c.get("label"), str) or not c["label"].strip():
                    raise ValueError("Each choice needs a label.")
    if kind == "story_arcs":
        _id(doc.get("start"))
        if doc.get("start") not in ids:
            raise ValueError("Story start must refer to an existing node.")
        graph = {e["id"]: [c.get("next") for c in e["choices"] if c.get("next") is not None] for e in entries}
        if any(n not in ids for edges in graph.values() for n in edges):
            raise ValueError("Every next value must refer to a node, or be null to finish.")
        visiting, visited = set(), set()
        def visit(n):
            if n in visiting:
                raise ValueError("Story paths cannot loop: repeated reward claims would be possible.")
            if n in visited:
                return
            visiting.add(n)
            for nxt in graph[n]:
                visit(nxt)
            visiting.remove(n)
            visited.add(n)
        for n in graph:
            visit(n)
    return doc


def journal(p):
    return p.setdefault("journal", {"focus": None, "goals": {}, "stories": {}})


async def metrics(db, p):
    businesses = await db.businesses.find({"player_id": p["id"]}, {"_id": 0, "revenue_total": 1}).to_list(100)
    meta = p.get("stats_meta", {})
    m = {"funds": p.get("cash", 0) + p.get("bank", 0), "bank": p.get("bank", 0),
         "shifts": meta.get("shifts_worked", 0), "actions": meta.get("actions_done", 0),
         "courses": meta.get("courses_done", 0), "businesses": len(businesses),
         "business_revenue": sum(b.get("revenue_total", 0) for b in businesses),
         "contacts": await db.contacts.count_documents({"player_id": p["id"]}),
         "level": p.get("level", 1), "reputation": p.get("reputation", 0),
         "stories_completed": sum(r.get("completed", False) for r in journal(p)["stories"].values())}
    m.update({"skill:" + k: v.get("level", 1) for k, v in p.get("skills", {}).items()})
    m.update({"item:" + k: v for k, v in p.get("inventory", {}).items()})
    return m


def progress(requirements, current, baseline=None):
    out = []
    for r in requirements:
        value = current.get(r["metric"], 0)
        if r.get("since_start"):
            value = max(0, value - (baseline or {}).get(r["metric"], 0))
        out.append({**r, "current": round(value, 2), "met": value >= r["target"]})
    return out


def reward(p, values, cfg):
    add_money(p, values.get("cash", 0))
    ledger_add(p, "story_income", values.get("cash", 0))
    add_player_xp(p, values.get("xp", 0), cfg)
    for stat in STATS:
        if stat in values:
            p[stat] = clamp(p.get(stat, 0) + values[stat])
    for skill, xp in values.get("skills", {}).items():
        add_skill_xp(p, skill, xp, cfg)
    for item, qty in values.get("items", {}).items():
        inv = p.setdefault("inventory", {})
        inv[item] = inv.get(item, 0) + qty


def city_window(template, cfg, now):
    anchor = parse_dt(cfg.get("world_start_real")) or now
    first = anchor + timedelta(hours=template["offset_hours"])
    elapsed = (now - first).total_seconds()
    interval = template["repeat_hours"] * 3600
    cycle = max(0, math.floor(elapsed / interval))
    start = first + timedelta(seconds=cycle * interval)
    end = start + timedelta(hours=template["duration_hours"])
    active = start <= now < end
    if now >= end:
        start += timedelta(seconds=interval)
        end += timedelta(seconds=interval)
        cycle += 1
    return {**template, "is_live": active, "cycle": cycle, "starts_at": start.isoformat(), "ends_at": end.isoformat(),
            "remaining_seconds": max(0, math.ceil(((end if active else start) - now).total_seconds()))}


async def city_events(db, cfg, now=None):
    if not cfg.get("journey", {}).get("city_events_enabled", True):
        return []
    rows = await db.city_events.find({"active": {"$ne": False}}, {"_id": 0}).to_list(100)
    return sorted([city_window(t, cfg, now or now_utc()) for t in rows], key=lambda r: (not r["is_live"], r["starts_at"]))


def choice_view(p, choice, current, baseline):
    checks = progress(choice.get("requirements", []), current, baseline)
    reasons = [r.get("label", r["metric"]) for r in checks if not r["met"]]
    if p.get("status") in {"hospital", "jail"}:
        reasons.append("Continue after you are released. Your story will wait.")
    if current["funds"] < choice.get("cost", 0):
        reasons.append("Need $" + f"{choice['cost']:g} available.")
    for item, qty in choice.get("consume_items", {}).items():
        if p.get("inventory", {}).get(item, 0) < qty:
            reasons.append(f"Need {qty} × {item.replace('_', ' ')}.")
    return {**choice, "progress": checks, "available": not reasons, "reasons": reasons}


def run_id(story_id, event=None):
    return f"{story_id}__{event['id']}__{event['cycle']}" if event else story_id


async def view(db, p, cfg):
    j = journal(p)
    current = await metrics(db, p)
    defs = await db.journey_goals.find({"active": {"$ne": False}}, {"_id": 0}).to_list(100)
    goals = []
    by_id = {d["id"]: d for d in defs}
    by_id.update({gid: run["definition"] for gid, run in j["goals"].items()})
    for gid, d in by_id.items():
        run = j["goals"].get(gid)
        index = run["index"] if run else 0
        milestones = []
        for i, step in enumerate(d["milestones"]):
            checks = progress(step.get("requirements", []), current, (run or {}).get("baseline"))
            milestones.append({**step, "progress": checks, "claimed": i < index,
                               "ready": bool(run) and i == index and all(r["met"] for r in checks)})
        goals.append({**d, "milestones": milestones, "tracked": bool(run), "focused": j["focus"] == gid,
                      "completed": index == len(milestones)})
    stories = []
    for rid, run in j["stories"].items():
        d = run["definition"]
        node = next((n for n in d["nodes"] if n["id"] == run.get("node")), None)
        stories.append({"id": rid, "template_id": d["id"], "name": d["name"], "contact": d.get("contact"),
                        "completed": run.get("completed", False), "history": run.get("history", []),
                        "node": {**node, "choices": [choice_view(p, c, current, run["baseline"]) for c in node["choices"]]} if node else None})
    occasions = await city_events(db, cfg)
    arcs = await db.story_arcs.find({"active": {"$ne": False}}, {"_id": 0}).to_list(200)
    active_count = sum(not s["completed"] for s in stories)
    limit = cfg.get("journey", {}).get("max_active_stories", 3)
    offers = []
    for d in arcs:
        contexts = [e for e in occasions if e["is_live"] and d["id"] in e["arc_ids"]] if d.get("event_only") else [None]
        for event in contexts:
            rid = run_id(d["id"], event)
            if rid in j["stories"]:
                continue
            checks = progress(d.get("requirements", []), current)
            reasons = [r.get("label", r["metric"]) for r in checks if not r["met"]]
            if active_count >= limit:
                reasons.append(f"Finish an active story first ({limit:g} at a time).")
            offers.append({"id": d["id"], "run_id": rid, "name": d["name"], "description": d.get("description", ""),
                           "contact": d.get("contact"), "event_id": event["id"] if event else None,
                           "event_name": event["name"] if event else None, "progress": checks,
                           "available": not reasons, "reasons": reasons})
    return {"focus": j["focus"], "goals": goals, "stories": stories, "offers": offers, "city_events": occasions,
            "max_active_stories": limit}


def choose(p, rid, node_id, choice_id, current, cfg):
    run = journal(p)["stories"].get(rid)
    if not run or run.get("completed") or run.get("node") != node_id:
        raise ValueError("This chapter has already changed. Refresh your journal.")
    node = next(n for n in run["definition"]["nodes"] if n["id"] == node_id)
    c = next((c for c in node["choices"] if c["id"] == choice_id), None)
    if c is None:
        raise ValueError("Unknown choice.")
    check = choice_view(p, c, current, run["baseline"])
    if not check["available"]:
        raise ValueError(" ".join(check["reasons"]))
    charge(p, c.get("cost", 0))
    ledger_add(p, "story_costs", -c.get("cost", 0))
    for item, qty in c.get("consume_items", {}).items():
        p["inventory"][item] -= qty
    reward(p, c.get("rewards", {}), cfg)
    run.setdefault("history", []).append({"node": node_id, "title": node.get("title"), "choice": c["label"],
                                        "outcome": c.get("outcome", ""), "at": now_utc().isoformat()})
    run["node"] = c.get("next")
    run["completed"] = c.get("next") is None
    run["baseline"] = deepcopy(current)
    return {"ok": True, "outcome": c.get("outcome", ""), "completed": run["completed"]}
