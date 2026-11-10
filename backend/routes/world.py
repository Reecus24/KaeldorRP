"""Open-world routes; the shared player lease serializes every mutation and poll."""
from core import *  # noqa: F401,F403
from copy import deepcopy
import world_engine as world


class TalkBody(BaseModel):
    message: str = Field(min_length=1, max_length=600)


class WorldActionBody(BaseModel):
    narrative: str = Field(default="", max_length=1000)
    founding_id: Optional[str] = None


class IntentReviewBody(BaseModel):
    approved: bool
    note: str = Field(default="", max_length=1000)
    definition: Optional[dict] = None


class FoundBody(BaseModel):
    charter_id: str
    name: str = Field(min_length=2, max_length=60)
    description: str = Field(default="", max_length=1000)


class FoundEditBody(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    description: str = Field(default="", max_length=1000)
    open_membership: bool = True


async def catalog(kind):
    return await db[kind].find({"active": {"$ne": False}}, {"_id": 0}).to_list(500)


async def world_player(user):
    p = await get_state(user)
    cfg = await get_config(db)
    w = world.state(p, cfg)
    # Deleted/disabled regions need an escape path; do not strand old saves.
    if not await db.world_regions.find_one({"id": w["region"], "active": {"$ne": False}}):
        regions = await catalog("world_regions")
        preferred = next((r for r in regions if r["id"] == cfg["world"]["start_region"]), None)
        w["region"] = (preferred or (regions[0] if regions else {"id": None}))["id"]
    return p, cfg, w


async def foundings():
    # Founded entities live atomically with their founder's funds in one document.
    owners = await db.players.find({"world.foundings.0": {"$exists": True}}, {"_id": 0, "id": 1, "name": 1, "world.foundings": 1}).to_list(1000)
    return [{**f, "founder_id": owner["id"], "founder_name": owner["name"]} for owner in owners for f in owner.get("world", {}).get("foundings", [])]


@api.get("/world/creation")
async def creation_rules(user: dict = Depends(current_user)):
    cfg = await get_config(db)
    return {"random": cfg["world"]["random_creation"], "origins": await catalog("world_origins")}


@api.get("/world/skills")
async def skill_definitions(user: dict = Depends(current_user)):
    return await catalog("world_skills")


@api.get("/admin/world/templates")
async def world_templates(admin: dict = Depends(admin_user)):
    return {kind: deepcopy(definitions[1][0]) for kind, definitions in world.WORLD_CONTENT.items()}


@api.get("/admin/players/{player_id}/world")
async def inspect_world_character(player_id: str, admin: dict = Depends(admin_user)):
    p = await db.players.find_one({"id": player_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Character not found.")
    cfg = await get_config(db)
    w = world.state(p, cfg)
    return {"region": w["region"], "profession": w["profession"], "skills": p["skills"], "training": w["training"], "memories": w["memories"]}


@api.put("/admin/players/{player_id}/world")
async def edit_world_character(player_id: str, body: dict, admin: dict = Depends(admin_user)):
    p = await db.players.find_one({"id": player_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Character not found.")
    cfg = await get_config(db)
    from config_schema import validate_json
    try:
        validate_json(body)
        if set(body) - {"region", "profession", "skills", "training", "memories"}:
            raise ValueError("Use the region, profession, skills, training and memories fields.")
        if "region" in body:
            world.identifier(body["region"])
            if not await db.world_regions.find_one({"id": body["region"], "active": {"$ne": False}}):
                raise ValueError("Choose an active region ID.")
        if body.get("profession") is not None:
            world.identifier(body["profession"])
            if not await db.world_professions.find_one({"id": body["profession"], "active": {"$ne": False}}):
                raise ValueError("Choose an active profession ID or null.")
        if "skills" in body:
            for key, value in world.mapping(body["skills"], "skills").items():
                world.identifier(key); world.mapping(value, "skill")
                world.number(value.get("level"), "level", 1, 10000, True)
                world.number(value.get("xp"), "xp", 0, cfg["xp"]["skill_per_level"] * value["level"])
                if value["xp"] >= cfg["xp"]["skill_per_level"] * value["level"]:
                    raise ValueError("Skill XP must be below the next level threshold.")
        if "training" in body:
            world.numeric_map(body["training"], "training", 0, 100000, True)
        if "memories" in body:
            for key, m in world.mapping(body["memories"], "memories").items():
                world.identifier(key); world.mapping(m, "memory")
                world.number(m.get("visits", 0), "visits", 0, 1e9, True)
                if not isinstance(m.get("turns", []), list) or len(m.get("turns", [])) > cfg["world"]["memory_turns"]:
                    raise ValueError("Memory turns must be a list within the configured memory limit.")
                for turn in m.get("turns", []):
                    world.mapping(turn, "turn")
                    for field in ("player", "npc", "at"):
                        if not isinstance(turn.get(field), str) or len(turn[field]) > 4000:
                            raise ValueError("Each memory turn needs player, npc and at text fields.")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    # Settle elapsed activity before applying deliberate Owner overrides.
    await resolve_player(db, p)
    w = world.state(p, cfg)
    for key in ("region", "profession", "training", "memories"):
        if key in body:
            w[key] = deepcopy(body[key])
    if "skills" in body:
        p.setdefault("skills", {}).update(deepcopy(body["skills"]))
    await save_player(p)
    return {"ok": True}


@api.get("/world")
async def world_view(user: dict = Depends(current_user)):
    p, cfg, w = await world_player(user)
    regions, professions, npcs = await catalog("world_regions"), await catalog("world_professions"), await catalog("world_npcs")
    profmap, npcmap = {v["id"]: v for v in professions}, {v["id"]: v for v in npcs}
    for prof in professions:
        prof["reason"] = world.requirements_reason(p, prof.get("requirements", {}), profmap)
    actions = []
    all_actions = await catalog("world_actions")
    all_actions += [{**i["definition"], "intent_id": i["id"], "narrative": i["text"]} for i in w["intents"] if i["status"] == "approved"]
    for a in all_actions:
        if not a["regions"] or w["region"] in a["regions"]:
            a["reason"] = world.action_reason(p, a, cfg, profmap, npcmap)
            a["outcomes"] = world.probabilities(p, a, cfg)
            actions.append(a)
    for npc in npcs:
        npc["region"] = world.npc_region(npc, cfg)
        npc["known"] = npc["id"] in w["memories"]
    for region in regions:
        region["reason"] = world.requirements_reason(p, region.get("requirements", {}), profmap)
        for edge in region["connections"]:
            edge["real_seconds"] = real_seconds(edge["minutes"], cfg["time_scale"])
    groups = await foundings()
    for f in groups:
        f["member"] = f["founder_id"] == p["id"] or f["id"] in w["memberships"]
        f["owned"] = f["founder_id"] == p["id"]
        f["commissions"] = []
        if f["member"] and f["region"] == w["region"]:
            for a in all_actions:
                if a.get("workshop_kind") == f["kind"]:
                    local = {**deepcopy(a), "regions": [f["region"]]}
                    local["reason"] = world.action_reason(p, local, cfg, profmap, npcmap)
                    local["outcomes"] = world.probabilities(p, local, cfg)
                    f["commissions"].append(local)
    charters = await catalog("world_charters")
    for charter in charters:
        charter["reason"] = founding_reason(p, cfg, charter, profmap)
    nearby = await db.players.find({"world.region": w["region"], "id": {"$ne": p["id"]}}, {"_id": 0, "id": 1, "name": 1, "world.profession": 1, "world.region": 1}).to_list(100)
    await save_player(p)
    from npc_dialogue import availability
    return {"world": w, "regions": regions, "npcs": npcs, "actions": actions, "professions": professions,
            "skills": await catalog("world_skills"), "charters": charters, "foundings": groups, "nearby_players": nearby,
            "blocked": world.busy_reason(p), "ai": availability(cfg), "time_scale": cfg["time_scale"], "max_foundings": cfg["world"]["max_foundings"]}


@api.post("/world/travel/{region_id}")
async def travel(region_id: str, user: dict = Depends(current_user)):
    p, cfg, w = await world_player(user)
    reason = world.busy_reason(p)
    if reason:
        raise HTTPException(409, reason)
    source = await db.world_regions.find_one({"id": w["region"]})
    target = await db.world_regions.find_one({"id": region_id, "active": {"$ne": False}})
    edge = next((e for e in (source or {}).get("connections", []) if e["to"] == region_id), None)
    if not edge or not target:
        raise HTTPException(409, "There is no open route from your current location.")
    profs = {x["id"]: x for x in await catalog("world_professions")}
    reason = world.requirements_reason(p, target.get("requirements", {}), profs)
    if reason:
        raise HTTPException(409, reason)
    set_activity(p, "world", "Travel to " + target["name"], edge["minutes"], cfg, {"travel_to": region_id, "name": target["name"]})
    await save_player(p)
    return {"ok": True, "activity": serialize_activity(p)}


@api.post("/world/actions/{action_id}/start")
async def world_action(action_id: str, body: WorldActionBody = WorldActionBody(), user: dict = Depends(current_user)):
    p, cfg, w = await world_player(user)
    a = await db.world_actions.find_one({"id": action_id, "active": {"$ne": False}}, {"_id": 0})
    intent = next((i for i in w["intents"] if i["id"] == action_id and i["status"] == "approved"), None)
    if intent:
        a = deepcopy(intent["definition"])
    if not a:
        raise HTTPException(404, "This action is no longer available.")
    professions = {x["id"]: x for x in await catalog("world_professions")}
    npcs = {x["id"]: x for x in await catalog("world_npcs")}
    if body.founding_id:
        f = next((x for x in await foundings() if x["id"] == body.founding_id), None)
        if not f or f["region"] != w["region"] or (f["founder_id"] != p["id"] and f["id"] not in w["memberships"]) or a.get("workshop_kind") != f["kind"]:
            raise HTTPException(409, "This workshop commission is not available to you here.")
        a["regions"] = [f["region"]]
    reason = world.action_reason(p, a, cfg, professions, npcs)
    if reason:
        raise HTTPException(409, reason)
    payload = world.prepare_action(p, a, cfg)
    payload.update(narrative=intent["text"] if intent else body.narrative.strip(), founding_id=body.founding_id)
    if intent:
        payload["intent_id"] = intent["id"]
        intent["status"] = "started"
    set_activity(p, "world", a["name"], a["duration_minutes"], cfg, payload)
    await save_player(p)
    return {"ok": True, "activity": serialize_activity(p)}


@api.post("/world/intents")
async def propose_action(body: TalkBody, user: dict = Depends(current_user)):
    p, cfg, w = await world_player(user)
    if not body.message.strip():
        raise HTTPException(422, "Describe what you want to do.")
    if sum(i["status"] in ("pending", "approved") for i in w["intents"]) >= cfg["world"]["max_pending_intents"]:
        raise HTTPException(409, "Finish your open proposals before creating more.")
    active = [i for i in w["intents"] if i["status"] in ("pending", "approved", "started")]
    history = [i for i in w["intents"] if i["status"] not in ("pending", "approved", "started")][-cfg["world"]["report_limit"]:]
    intent = {"id": "intent_" + uuid.uuid4().hex, "text": body.message.strip(), "region": w["region"], "status": "pending", "at": now_utc().isoformat()}
    w["intents"] = history + active + [intent]
    await save_player(p)
    return {"ok": True, "intent": intent}


@api.get("/admin/world/intents")
async def pending_intents(admin: dict = Depends(admin_user)):
    players = await db.players.find({"world.intents.status": "pending"}, {"_id": 0, "id": 1, "name": 1, "skills": 1, "world.intents": 1}).to_list(500)
    from world_content import WORLD_ACTIONS
    return {"requests": [{**i, "player_id": p["id"], "player_name": p["name"], "skills": p.get("skills", {})} for p in players for i in p.get("world", {}).get("intents", []) if i["status"] == "pending"], "template": deepcopy(WORLD_ACTIONS[0])}


@api.put("/admin/players/{player_id}/world-intents/{intent_id}")
async def adjudicate_intent(player_id: str, intent_id: str, body: IntentReviewBody, admin: dict = Depends(admin_user)):
    p = await db.players.find_one({"id": player_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Character not found.")
    cfg = await get_config(db)
    w = world.state(p, cfg)
    intent = next((i for i in w["intents"] if i["id"] == intent_id), None)
    if not intent or intent["status"] != "pending":
        raise HTTPException(409, "This proposal has already been reviewed.")
    if body.approved:
        definition = {**(body.definition or {}), "id": intent_id, "regions": [intent["region"]], "active": True}
        try:
            from config_schema import validate_json
            validate_json(definition)
            world.validate_definition("world_actions", definition)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        intent["definition"] = definition
    intent.update(status="approved" if body.approved else "declined", note=body.note, reviewed_at=now_utc().isoformat())
    await save_player(p)
    return {"ok": True}


@api.post("/world/professions/{profession_id}")
async def choose_profession(profession_id: str, user: dict = Depends(current_user)):
    p, cfg, w = await world_player(user)
    profs = {x["id"]: x for x in await catalog("world_professions")}
    prof = profs.get(profession_id)
    if not prof:
        raise HTTPException(404, "Unknown profession.")
    reason = world.requirements_reason(p, prof.get("requirements", {}), profs)
    if reason:
        raise HTTPException(409, reason)
    w["profession"] = profession_id
    await save_player(p)
    return {"ok": True}


async def local_npc(p, cfg, npc_id):
    npc = await db.world_npcs.find_one({"id": npc_id, "active": {"$ne": False}}, {"_id": 0})
    if not npc:
        raise HTTPException(404, "This person is unavailable.")
    if world.busy_reason(p):
        raise HTTPException(409, world.busy_reason(p))
    if world.npc_region(npc, cfg) != p["world"]["region"]:
        raise HTTPException(409, "Travel to this NPC's current location first.")
    return npc


async def npc_offers(npc_id, w):
    quests = await db.world_quests.find({"npc_id": npc_id, "active": {"$ne": False}}, {"_id": 0}).to_list(100)
    return [q for q in quests if q["id"] not in w["quests"]]


@api.get("/world/npcs/{npc_id}")
async def npc_view(npc_id: str, user: dict = Depends(current_user)):
    p, cfg, w = await world_player(user)
    npc = await local_npc(p, cfg, npc_id)
    return {"npc": npc, "memory": w["memories"].get(npc_id, {}), "offers": await npc_offers(npc_id, w),
            "quests": [q for q in w["quests"].values() if q["definition"]["npc_id"] == npc_id]}


@api.post("/world/npcs/{npc_id}/talk")
async def talk(npc_id: str, body: TalkBody, user: dict = Depends(current_user)):
    p, cfg, w = await world_player(user)
    npc = await local_npc(p, cfg, npc_id)
    last = parse_dt(w.get("last_dialogue_at"))
    if last and (now_utc() - last).total_seconds() < cfg["world"]["dialogue_cooldown_seconds"]:
        raise HTTPException(429, "Give them a moment to answer before speaking again.")
    offers = await npc_offers(npc_id, w)
    from npc_dialogue import reply
    text, mode = await reply(db, p, npc, body.message.strip(), offers, cfg)
    world.remember(w, npc_id, body.message.strip(), text, cfg)
    w["last_dialogue_at"] = now_utc().isoformat()
    await save_player(p)
    return {"reply": text, "mode": mode, "memory": w["memories"][npc_id], "offers": offers}


@api.post("/world/quests/{quest_id}/accept")
async def accept_quest(quest_id: str, user: dict = Depends(current_user)):
    p, cfg, w = await world_player(user)
    q = await db.world_quests.find_one({"id": quest_id, "active": {"$ne": False}}, {"_id": 0})
    if not q:
        raise HTTPException(404, "This offer is unavailable.")
    await local_npc(p, cfg, q["npc_id"])
    profs = {x["id"]: x for x in await catalog("world_professions")}
    reason = world.requirements_reason(p, q.get("requirements", {}), profs)
    if reason:
        raise HTTPException(409, reason)
    if quest_id in w["quests"]:
        raise HTTPException(409, "You already accepted this quest.")
    if sum(v["status"] == "active" for v in w["quests"].values()) >= cfg["world"]["max_active_quests"]:
        raise HTTPException(409, "Your quest journal is full.")
    w["quests"][quest_id] = {"definition": q, "status": "active", "progress": 0, "accepted_at": now_utc().isoformat()}
    await save_player(p)
    return {"ok": True}


@api.post("/world/quests/{quest_id}/claim")
async def claim_quest(quest_id: str, user: dict = Depends(current_user)):
    p, cfg, w = await world_player(user)
    q = w["quests"].get(quest_id)
    if not q or q["status"] != "active" or q["progress"] < q["definition"]["target"]:
        raise HTTPException(409, "This quest is not ready to turn in.")
    await local_npc(p, cfg, q["definition"]["npc_id"])
    add_money(p, q["definition"]["reward_coins"])
    ledger_add(p, "expedition_income", q["definition"]["reward_coins"])
    q.update(status="claimed", claimed_at=now_utc().isoformat())
    await save_player(p)
    return {"ok": True}


def founding_reason(p, cfg, charter, profs):
    w = world.state(p, cfg)
    reason = world.busy_reason(p) or world.requirements_reason(p, charter.get("requirements", {}), profs)
    if reason:
        return reason
    if len(w["foundings"]) >= cfg["world"]["max_foundings"]:
        return "Your founding limit has been reached."
    if charter["regions"] and w["region"] not in charter["regions"]:
        return "This charter needs a different location."
    if p["cash"] + p["bank"] < charter["cost"]:
        return "Not enough coin to establish this charter."
    return ""


@api.post("/world/foundings")
async def found(body: FoundBody, user: dict = Depends(current_user)):
    p, cfg, w = await world_player(user)
    charter = await db.world_charters.find_one({"id": body.charter_id, "active": {"$ne": False}}, {"_id": 0})
    if not charter:
        raise HTTPException(404, "This charter is unavailable.")
    profs = {x["id"]: x for x in await catalog("world_professions")}
    reason = founding_reason(p, cfg, charter, profs)
    if reason:
        raise HTTPException(409, reason)
    if not body.name.strip() or any(f["name"].casefold() == body.name.strip().casefold() for f in w["foundings"]):
        raise HTTPException(409, "Choose a distinct name for your founding.")
    charge(p, charter["cost"]); ledger_add(p, "expedition_costs", -charter["cost"])
    f = {"id": uuid.uuid4().hex, "charter_id": charter["id"], "kind": charter["kind"], "name": body.name.strip(), "description": body.description.strip(), "region": w["region"], "open_membership": True, "created_at": now_utc().isoformat()}
    w["foundings"].append(f)
    await save_player(p)
    return {"ok": True, "founding": f}


@api.put("/world/foundings/{founding_id}")
async def edit_founding(founding_id: str, body: FoundEditBody, user: dict = Depends(current_user)):
    p, cfg, w = await world_player(user)
    f = next((x for x in w["foundings"] if x["id"] == founding_id), None)
    if not f:
        raise HTTPException(403, "Only the founder can change this charter.")
    if not body.name.strip():
        raise HTTPException(422, "Enter a name.")
    f.update(name=body.name.strip(), description=body.description.strip(), open_membership=body.open_membership)
    await save_player(p)
    return {"ok": True}


@api.post("/world/foundings/{founding_id}/join")
async def join_founding(founding_id: str, user: dict = Depends(current_user)):
    p, cfg, w = await world_player(user)
    f = next((x for x in await foundings() if x["id"] == founding_id), None)
    if not f or not f["open_membership"]:
        raise HTTPException(409, "This group is not accepting members.")
    if f["founder_id"] == p["id"] or founding_id in w["memberships"]:
        raise HTTPException(409, "You already belong to this group.")
    w["memberships"].append(founding_id)
    await save_player(p)
    return {"ok": True}


@api.post("/world/foundings/{founding_id}/leave")
async def leave_founding(founding_id: str, user: dict = Depends(current_user)):
    p, cfg, w = await world_player(user)
    if founding_id not in w["memberships"]:
        raise HTTPException(409, "You are not a member, or you are the founder.")
    w["memberships"].remove(founding_id)
    await save_player(p)
    return {"ok": True}


@api.get("/world/foundings/{founding_id}/members")
async def founding_members(founding_id: str, user: dict = Depends(current_user)):
    f = next((x for x in await foundings() if x["id"] == founding_id), None)
    if not f:
        raise HTTPException(404, "Founding not found.")
    return await db.players.find({"$or": [{"id": f["founder_id"]}, {"world.memberships": founding_id}]}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
