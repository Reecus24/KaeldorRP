from core import *  # noqa: F401,F403
import realm_engine as realm


class ExpeditionBody(BaseModel):
    tactic: str = "balanced"


async def current_faction(p):
    f = p.get("faction")
    if not f:
        return None
    definition = await db.factions.find_one({"id": f["id"]}, {"_id": 0})
    return realm.service(p, definition) if definition else {**f, "name": "Disbanded faction", "active": False, "rank_index": 0, "rank": {"name": "Unaffiliated"}, "next_rank": None}


@api.get("/realm")
async def realm_view(user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    faction = await current_faction(p)
    factions = await db.factions.find({"active": {"$ne": False}}, {"_id": 0}).to_list(100)
    stats = await realm.combat_stats(db, p, cfg)
    missions = await db.expeditions.find({"active": {"$ne": False}}, {"_id": 0}).to_list(200)
    for m in missions:
        m["reason"] = realm.mission_reason(p, m, faction)
        m["forecasts"] = {key: realm.forecast(m, stats, t, cfg) for key, t in cfg["realm"]["tactics"].items()}
        m["supply_labels"] = []
        for identifier, qty in m.get("supplies", {}).items():
            item = await db.items.find_one({"id": identifier}, {"name": 1})
            m["supply_labels"].append({"name": item["name"] if item else identifier, "quantity": qty, "owned": p.get("inventory", {}).get(identifier, 0)})
    until = parse_dt(p.get("faction_rejoin_at"))
    for f in factions:
        f["join_reason"] = ("Leave your current oath first." if faction else
            "Your oath cooldown ends at " + until.isoformat() if until and until > now_utc() else
            "Requires legal standing " + str(f["min_legal"]) if p["legal_reputation"] < f["min_legal"] else
            "Not enough coin to join." if p["cash"] + p["bank"] < f["join_cost"] else activity_block_reason(p))
    return {"standing": await realm.standing(db, p), "faction": faction, "factions": factions, "combat": stats,
            "missions": missions, "tactics": cfg["realm"]["tactics"], "reports": p.get("battle_reports", []),
            "rejoin_hours": cfg["realm"]["faction_rejoin_hours"]}


@api.post("/realm/factions/{faction_id}/join")
async def join_faction(faction_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    ensure_free(p)
    if p.get("faction"):
        raise HTTPException(409, "Leave your current oath before swearing another.")
    until = parse_dt(p.get("faction_rejoin_at"))
    if until and until > now_utc():
        raise HTTPException(409, "Your oath cooldown has not ended.")
    f = await db.factions.find_one({"id": faction_id, "active": {"$ne": False}}, {"_id": 0})
    if not f:
        raise HTTPException(404, "This faction is unavailable.")
    if p["legal_reputation"] < f["min_legal"] or p["cash"] + p["bank"] < f["join_cost"]:
        raise HTTPException(409, "You do not meet the oath requirements.")
    charge(p, f["join_cost"])
    ledger_add(p, "expedition_costs", -f["join_cost"])
    p["faction"] = {"id": faction_id, "joined_at": now_utc().isoformat(), "renown": 0, "service_hours": 0}
    await save_player(p)
    return {"ok": True}


@api.post("/realm/factions/leave")
async def leave_faction(user: dict = Depends(current_user)):
    p = await get_state(user)
    ensure_free(p)
    if not p.get("faction"):
        raise HTTPException(409, "You have not sworn an oath.")
    cfg = await get_config(db)
    p["faction"] = None
    p["faction_rejoin_at"] = (now_utc() + timedelta(hours=cfg["realm"]["faction_rejoin_hours"])).isoformat()
    await save_player(p)
    return {"ok": True}


@api.post("/realm/expeditions/{mission_id}/start")
async def start_expedition(mission_id: str, body: ExpeditionBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    m = await db.expeditions.find_one({"id": mission_id, "active": {"$ne": False}}, {"_id": 0})
    if not m:
        raise HTTPException(404, "This expedition is unavailable.")
    if body.tactic not in cfg["realm"]["tactics"]:
        raise HTTPException(422, "Unknown tactic. Refresh your expedition board.")
    reason = realm.mission_reason(p, m, await current_faction(p))
    if reason:
        raise HTTPException(409, reason)
    stats = await realm.combat_stats(db, p, cfg)
    payload = realm.prepare(p, m, body.tactic, cfg, stats)
    set_activity(p, "expedition", m["name"], m["duration_minutes"], cfg, payload)
    await save_player(p)
    return {"ok": True, "activity": serialize_activity(p)}
