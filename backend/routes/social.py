from core import *  # noqa: F401,F403




# ============================ LEADERBOARD ============================
@api.get("/leaderboard")
async def leaderboard(user: dict = Depends(current_user)):
    players = await db.players.find({}, {"_id": 0, "name": 1, "level": 1, "net_worth": 1,
                                         "reputation": 1, "social_status": 1, "id": 1}).to_list(500)
    players.sort(key=lambda x: x.get("net_worth", 0), reverse=True)
    me_p = await db.players.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    return {"top": players[:50], "my_id": me_p["id"] if me_p else None}




@api.get("/social/contacts")
async def social_contacts(user: dict = Depends(current_user)):
    p = await get_state(user)
    cs = await db.contacts.find({"player_id": p["id"]}, {"_id": 0}).sort("known_since", 1).to_list(400)
    views = [social_engine.contact_view(c) for c in cs]
    return {"contacts": views, "summary": social_engine.social_summary(views)}




@api.get("/social/gifts")
async def social_gifts(user: dict = Depends(current_user)):
    return await db.gift_types.find({}, {"_id": 0}).to_list(50)




@api.get("/social/discover-actions")
async def social_discover_actions(user: dict = Depends(current_user)):
    p = await get_state(user)
    acts = await db.relationship_actions.find({"untargeted": True}, {"_id": 0}).to_list(50)
    out = []
    for a in acts:
        cd = p.get("cooldowns", {}).get("social_" + a["id"])
        on_cd = cd and parse_dt(cd) > now_utc()
        out.append({**a, "available": not on_cd,
                    "cooldown_remaining": round((parse_dt(cd) - now_utc()).total_seconds()) if on_cd else 0})
    return out




@api.get("/social/contacts/{cid}")
async def social_contact_detail(cid: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    c = await _get_contact(p, cid)
    cfg = await get_config(db)
    return {
        "contact": social_engine.contact_view(c),
        "history": list(reversed(c.get("history", [])))[:40],
        "actions": await social_engine.actions_for_contact(db, p, c, cfg),
        "opportunities": social_engine.contact_opportunities(c),
        "warnings": social_engine.contact_warnings(c),
    }




@api.post("/social/contacts/{cid}/interact")
async def social_interact(cid: str, body: InteractBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    c = await _get_contact(p, cid)
    a = await db.relationship_actions.find_one({"id": body.action_id}, {"_id": 0})
    if not a or a.get("untargeted"):
        raise HTTPException(status_code=404, detail="Action not found")
    cfg = await get_config(db)
    ok, reason = social_engine.validate_action(p, c, a)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    gift = None
    if a.get("kind") == "give_gift":
        if not body.gift_id:
            raise HTTPException(status_code=400, detail="Choose a gift first")
        gift = await db.gift_types.find_one({"id": body.gift_id}, {"_id": 0})
        if not gift:
            raise HTTPException(status_code=404, detail="Gift not found")
    cd = c.get("cooldowns", {}).get(a["id"])
    if cd and parse_dt(cd) > now_utc():
        raise HTTPException(status_code=409, detail="That interaction is on cooldown")
    if gift is not None:
        if p["cash"] + p["bank"] < gift["cost"]:
            raise HTTPException(status_code=400, detail="You can't afford that gift")
        charge(p, gift["cost"])
        ledger_add(p, "living_costs", -gift["cost"])
    elif a.get("money_cost", 0) > 0:
        if p["cash"] + p["bank"] < a["money_cost"]:
            raise HTTPException(status_code=400, detail="Not enough money")
        charge(p, a["money_cost"])
        ledger_add(p, "living_costs", -a["money_cost"])

    if a.get("timing") == "activity":
        ensure_free(p)
        payload = {"action_id": a["id"], "contact_id": cid, "name": a["label"]}
        if gift:
            payload["gift"] = gift
        set_activity(p, "social", f"{a['label']} · {c['name']}", a["duration_minutes"], cfg, payload, blocking=a.get("blocking", True))
        await add_event(db, p["id"], f"You're spending time with {c['name']}: {a['label']}.", "social", "info")
        await save_player(p)
        return {"ok": True, "started": True, "activity": serialize_activity(p)}

    res = await social_engine.interact_now(db, p, cfg, c, a, gift)
    await save_player(p)
    return {"ok": True, **res}




@api.post("/social/discover/{action_id}")
async def social_discover(action_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    a = await db.relationship_actions.find_one({"id": action_id, "untargeted": True}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Action not found")
    ensure_free(p)
    cfg = await get_config(db)
    cdkey = "social_" + a["id"]
    cd = p.get("cooldowns", {}).get(cdkey)
    if cd and parse_dt(cd) > now_utc():
        raise HTTPException(status_code=409, detail="On cooldown")
    if a.get("money_cost", 0) > 0:
        if p["cash"] + p["bank"] < a["money_cost"]:
            raise HTTPException(status_code=400, detail="Not enough money")
        charge(p, a["money_cost"])
        ledger_add(p, "living_costs", -a["money_cost"])
    payload = {"action_id": a["id"], "name": a["label"]}
    set_activity(p, "social", a["label"], a["duration_minutes"], cfg, payload, blocking=a.get("blocking", True))
    cdm = a.get("cooldown_minutes", 0)
    if cdm > 0:
        p.setdefault("cooldowns", {})[cdkey] = (
            now_utc() + timedelta(seconds=real_seconds(a["duration_minutes"] + cdm, cfg["time_scale"]))).isoformat()
    await add_event(db, p["id"], f"You head out: {a['label']}.", "social", "info")
    await save_player(p)
    return {"ok": True, "activity": serialize_activity(p)}




@api.get("/social/locations")
async def social_locations(user: dict = Depends(current_user)):
    p = await get_state(user)
    amap = await _archetype_label_map()
    locs = await db.locations.find({"active": True}, {"_id": 0}).to_list(100)
    locs.sort(key=lambda x: (x.get("order", 99), x.get("name", "")))
    out = []
    for loc in locs:
        cd = p.get("cooldowns", {}).get("loc_" + loc["id"])
        on_cd = cd and parse_dt(cd) > now_utc()
        blocked_reason = None
        if loc.get("requires_job") and not p.get("job"):
            blocked_reason = "Requires a job"
        elif on_cd:
            blocked_reason = "On cooldown"
        elif loc.get("money_cost", 0) > p["cash"] + p["bank"]:
            blocked_reason = "Can't afford"
        out.append({
            "id": loc["id"], "name": loc["name"], "category": loc.get("category"),
            "desc": loc.get("desc", ""), "icon": loc.get("icon", "MapPin"),
            "money_cost": loc.get("money_cost", 0), "duration_minutes": loc.get("duration_minutes", 60),
            "requires_job": loc.get("requires_job", False), "encounters": _loc_encounters(loc, amap),
            "available": blocked_reason is None, "reason": blocked_reason,
            "cooldown_remaining": round((parse_dt(cd) - now_utc()).total_seconds()) if on_cd else 0,
        })
    return out




@api.post("/social/visit/{location_id}")
async def social_visit(location_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    loc = await db.locations.find_one({"id": location_id, "active": True}, {"_id": 0})
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    ensure_free(p)
    if loc.get("requires_job") and not p.get("job"):
        raise HTTPException(status_code=400, detail="You need a job to go there.")
    cfg = await get_config(db)
    cdkey = "loc_" + loc["id"]
    cd = p.get("cooldowns", {}).get(cdkey)
    if cd and parse_dt(cd) > now_utc():
        raise HTTPException(status_code=409, detail="You were just there — give it some time.")
    cost = loc.get("money_cost", 0)
    if cost > 0:
        if p["cash"] + p["bank"] < cost:
            raise HTTPException(status_code=400, detail="Not enough money")
        charge(p, cost)
        ledger_add(p, "living_costs", -cost)
    payload = {"location_id": loc["id"], "name": loc["name"]}
    set_activity(p, "social", f"Visit {loc['name']}", loc.get("duration_minutes", 60), cfg, payload, blocking=True)
    cdm = loc.get("cooldown_minutes", 0)
    if cdm > 0:
        p.setdefault("cooldowns", {})[cdkey] = (
            now_utc() + timedelta(seconds=real_seconds(loc.get("duration_minutes", 60) + cdm, cfg["time_scale"]))).isoformat()
    await add_event(db, p["id"], f"You head out to {loc['name']}.", "social", "info")
    await save_player(p)
    return {"ok": True, "activity": serialize_activity(p)}







@api.post("/social/contacts/{cid}/block")
async def social_block(cid: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    c = await _get_contact(p, cid)
    if c.get("status") == "blocked":
        new_status = social_engine.derive_status({**c, "status": "active"})
        verb = "unblocked"
    else:
        new_status = "blocked"
        verb = "blocked"
    await db.contacts.update_one({"id": cid}, {"$set": {"status": new_status}})
    await add_event(db, p["id"], f"You {verb} {c['name']}.", "social", "warning" if verb == "blocked" else "info")
    return {"ok": True, "status": new_status}




@api.get("/notifications")
async def list_notifications(limit: int = 40, user: dict = Depends(current_user)):
    p = await fetch_raw_player(user["id"])
    items = await db.notifications.find({"player_id": p["id"]}, {"_id": 0}).sort("ts", -1).to_list(limit)
    unread = await db.notifications.count_documents({"player_id": p["id"], "read": False})
    return {"items": items, "unread_count": unread}




@api.post("/notifications/read")
async def mark_notifications_read(body: NotifReadBody, user: dict = Depends(current_user)):
    p = await fetch_raw_player(user["id"])
    q = {"player_id": p["id"], "read": False}
    if body.ids is not None:
        q["id"] = {"$in": body.ids}
    await db.notifications.update_many(q, {"$set": {"read": True}})
    return {"ok": True}




@api.get("/players/online")
async def players_online(user: dict = Depends(current_user)):
    cfg = await get_config(db)
    window = cfg.get("comms", {}).get("online_window_minutes", 3)
    cutoff = (now_utc() - timedelta(minutes=window)).isoformat()
    players = await db.players.find({"last_seen": {"$gte": cutoff}}, {"_id": 0, "id": 1, "name": 1, "last_seen": 1}).to_list(200)
    return {"online": players, "count": len(players)}




@api.get("/players/directory")
async def players_directory(user: dict = Depends(current_user)):
    me = await db.players.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    cfg = await get_config(db)
    players = await db.players.find({}, {"_id": 0, "id": 1, "name": 1, "last_seen": 1, "level": 1, "reputation": 1}).to_list(500)
    out = [{"id": p["id"], "name": p["name"], "level": p.get("level", 1),
            "online": comms.is_online(p, cfg)} for p in players if not me or p["id"] != me["id"]]
    out.sort(key=lambda x: (not x["online"], x["name"].lower()))
    return out




@api.get("/chat/world")
async def chat_world(limit: int = 60, user: dict = Depends(current_user)):
    msgs = await db.world_chat.find({"deleted": {"$ne": True}}, {"_id": 0}).sort("ts", -1).to_list(limit)
    msgs.reverse()
    cfg = await get_config(db)
    window = cfg.get("comms", {}).get("online_window_minutes", 3)
    cutoff = (now_utc() - timedelta(minutes=window)).isoformat()
    online = await db.players.count_documents({"last_seen": {"$gte": cutoff}})
    return {"messages": msgs, "online_count": online}




@api.post("/chat/world")
async def chat_world_send(body: ChatBody, user: dict = Depends(current_user)):
    p = await fetch_raw_player(user["id"])
    cfg = await get_config(db)
    ccfg = cfg.get("comms", {})
    muted = parse_dt(p.get("chat_muted_until"))
    if muted and muted > now_utc():
        raise HTTPException(status_code=403, detail="You are muted in World Chat.")
    text = (body.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message is empty")
    text = text[: ccfg.get("chat_max_length", 280)]
    last = parse_dt(p.get("last_chat_at"))
    cd = ccfg.get("chat_cooldown_seconds", 4)
    if last and (now_utc() - last).total_seconds() < cd:
        raise HTTPException(status_code=429, detail=f"Slow down — wait {cd}s between messages.")
    doc = {"id": uuid.uuid4().hex, "player_id": p["id"], "name": p["name"],
           "message": comms.clean_text(text), "ts": now_utc().isoformat(), "deleted": False}
    await db.world_chat.insert_one({**doc})
    await db.players.update_one({"id": p["id"]}, {"$set": {"last_chat_at": now_utc().isoformat()}})
    doc.pop("_id", None)
    return {"ok": True, "message": doc}




# ============================ PLAYER MESSAGING ============================
@api.get("/messages/threads")
async def message_threads(channel: str = "all", user: dict = Depends(current_user)):
    me = await fetch_raw_player(user["id"])
    q = {"$or": [{"from_player_id": me["id"]}, {"to_player_id": me["id"]}], "deleted_by": {"$ne": me["id"]}}
    msgs = await db.messages.find(q, {"_id": 0}).sort("ts", 1).to_list(3000)
    threads = {}
    for m in msgs:
        if channel != "all" and m["channel"] != channel:
            continue
        tid = m["thread_id"]
        from_me = m["from_player_id"] == me["id"]
        t = threads.setdefault(tid, {"thread_id": tid, "channel": m["channel"],
                                     "other_id": m["to_player_id"] if from_me else m["from_player_id"],
                                     "other_name": m["to_name"] if from_me else m["from_name"],
                                     "subject": m.get("subject"), "unread": 0})
        t["last_body"] = m["body"]
        t["last_ts"] = m["ts"]
        t["last_from_me"] = from_me
        if m.get("subject"):
            t["subject"] = m["subject"]
        if m["to_player_id"] == me["id"] and not m.get("read"):
            t["unread"] += 1
    return sorted(threads.values(), key=lambda x: x.get("last_ts", ""), reverse=True)




@api.get("/messages/unread")
async def messages_unread(user: dict = Depends(current_user)):
    me = await fetch_raw_player(user["id"])
    count = await db.messages.count_documents({"to_player_id": me["id"], "read": {"$ne": True}, "deleted_by": {"$ne": me["id"]}})
    return {"count": count}




@api.get("/messages/thread/{thread_id}")
async def message_thread(thread_id: str, user: dict = Depends(current_user)):
    me = await fetch_raw_player(user["id"])
    msgs = await db.messages.find({"thread_id": thread_id,
                                   "$or": [{"from_player_id": me["id"]}, {"to_player_id": me["id"]}],
                                   "deleted_by": {"$ne": me["id"]}}, {"_id": 0}).sort("ts", 1).to_list(500)
    await db.messages.update_many({"thread_id": thread_id, "to_player_id": me["id"], "read": {"$ne": True}}, {"$set": {"read": True}})
    return {"messages": msgs}




@api.post("/messages/send")
async def send_message(body: SendMessageBody, user: dict = Depends(current_user)):
    me = await fetch_raw_player(user["id"])
    cfg = await get_config(db)
    if body.channel not in ("sms", "email"):
        raise HTTPException(status_code=400, detail="Invalid channel")
    if not comms.has_device(me, body.channel):
        need = "a Laptop" if body.channel == "email" else "a Smartphone"
        raise HTTPException(status_code=403, detail=f"You need {need} to use this. Buy one in the Shop.")
    text = (body.body or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message is empty")
    text = text[: cfg.get("comms", {}).get("message_max_length", 2000)]
    recipient = await db.players.find_one({"id": body.to_player_id}, {"_id": 0})
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    if recipient["id"] == me["id"]:
        raise HTTPException(status_code=400, detail="You can't message yourself")
    if me["id"] in (recipient.get("msg_blocked") or []):
        raise HTTPException(status_code=403, detail="This player has blocked your messages")
    if body.channel == "sms":
        tid = comms.sms_thread_id(me["id"], recipient["id"])
        subject = None
    else:
        tid = body.thread_id or uuid.uuid4().hex
        subject = (body.subject or "(no subject)").strip()[:120]
    doc = {"id": uuid.uuid4().hex, "channel": body.channel, "thread_id": tid,
           "from_player_id": me["id"], "from_name": me["name"],
           "to_player_id": recipient["id"], "to_name": recipient["name"],
           "subject": subject, "body": comms.clean_text(text),
           "ts": now_utc().isoformat(), "read": False, "deleted_by": []}
    await db.messages.insert_one({**doc})
    label = "email" if body.channel == "email" else "SMS"
    await add_notification(db, recipient["id"], "message", f"New {label} from {me['name']}",
                           (subject + " — " if subject else "") + text[:80], "info", "/messages")
    doc.pop("_id", None)
    return {"ok": True, "thread_id": tid, "message": doc}




@api.post("/messages/block")
async def block_player(body: PlayerIdBody, user: dict = Depends(current_user)):
    me = await fetch_raw_player(user["id"])
    blocked = set(me.get("msg_blocked") or [])
    if body.player_id in blocked:
        blocked.discard(body.player_id)
        verb = "unblocked"
    else:
        blocked.add(body.player_id)
        verb = "blocked"
    await db.players.update_one({"id": me["id"]}, {"$set": {"msg_blocked": list(blocked)}})
    return {"ok": True, "status": verb}




@api.post("/messages/{message_id}/report")
async def report_message(message_id: str, user: dict = Depends(current_user)):
    me = await fetch_raw_player(user["id"])
    await db.message_reports.insert_one({"id": uuid.uuid4().hex, "message_id": message_id,
                                         "reporter_id": me["id"], "ts": now_utc().isoformat()})
    return {"ok": True}
