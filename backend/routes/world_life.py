from core import *  # noqa: F401,F403
from copy import deepcopy
from typing import Literal
from routes.world import world_player, catalog
import world_engine as world
import world_life as life
import comms


class EncounterChoice(BaseModel):
    event_id: str
    choice_id: str


class RPStatus(BaseModel):
    text: str = Field(max_length=300)


class RPChat(BaseModel):
    channel: Literal["local","world","whisper"] = "local"
    mode: Literal["say","emote","ooc"] = "say"
    peer: Optional[str] = None
    message: str = Field(min_length=1,max_length=4000)


@api.put("/world/status")
async def rp_status(body: RPStatus,user:dict=Depends(current_user)):
    p,cfg,state=await world_player(user)
    if len(body.text.strip())>cfg["world_life"]["status_max_length"]:
        raise HTTPException(422,"Your scene status is too long for the Owner's limit.")
    state["rp_status"]=body.text.strip()
    await save_player(p)
    return {"ok":True}


@api.post("/world/life/{kind}/choose")
async def choose_encounter(kind:str,body:EncounterChoice,user:dict=Depends(current_user)):
    p,cfg,state=await world_player(user)
    if kind=="day":
        instance,_=await life.day_state(db,state["region"],cfg)
        if not instance or instance["id"]!=body.event_id or not instance["definition"]:
            raise HTTPException(409,"A new day has begun, or this event is no longer here. Refresh the scene.")
        old=state.setdefault("daily_visits",{}).get(state["region"],{})
        if old.get("event_id")==body.event_id:raise HTTPException(409,"You already made your choice for this event.")
    elif kind=="road":
        instance=state.get("pending_encounter")
        if not instance or instance["id"]!=body.event_id:raise HTTPException(409,"This road encounter has already been settled.")
    else:raise HTTPException(404,"Unknown encounter type.")
    definition=instance["definition"]
    choice=next((c for c in definition["choices"] if c["id"]==body.choice_id and c.get("active") is not False),None)
    if not choice:raise HTTPException(404,"This approach is unavailable.")
    profs={r["id"]:r for r in await catalog("world_professions")};npcs={r["id"]:r for r in await catalog("world_npcs")}
    reason=world.action_reason(p,choice,cfg,profs,npcs)
    if reason:raise HTTPException(409,reason)
    payload=world.prepare_action(p,choice,cfg)
    payload.update(name=definition["name"]+" · "+choice["name"],narrative=definition["description"],life_event={"kind":kind,"id":body.event_id,"region":state["region"]})
    if kind=="day":state["daily_visits"][state["region"]]={"event_id":body.event_id,"status":"started","choice":choice["name"],"contribution":0,"goal_claimed":False}
    else:state["pending_encounter"]=None
    set_activity(p,"world",payload["name"],choice["duration_minutes"],cfg,payload)
    # Immediate choices go through the same chronological injury/recovery engine.
    if choice["duration_minutes"]==0:await resolve_player(db,p)
    await save_player(p)
    return {"ok":True}


@api.post("/world/life/road/leave")
async def leave_encounter(user:dict=Depends(current_user)):
    p,cfg,state=await world_player(user)
    if not state.get("pending_encounter"):raise HTTPException(409,"There is no encounter to leave.")
    name=state["pending_encounter"]["definition"]["name"]
    state["pending_encounter"]=None
    await add_event(db,p["id"],name+": you chose to leave it behind.","world","info")
    await save_player(p)
    return {"ok":True}


@api.post("/world/life/day/claim")
async def claim_village_goal(body:dict,user:dict=Depends(current_user)):
    p,cfg,state=await world_player(user)
    instance,_=await life.day_state(db,state["region"],cfg)
    if not instance or instance["id"]!=body.get("event_id"):raise HTTPException(409,"Return to today's village event.")
    goal=await life.goal_state(db,instance,p)
    if not goal["can_claim"]:raise HTTPException(409,"Contribute to the completed goal before claiming, once per person.")
    state["daily_visits"][state["region"]]["goal_claimed"]=True
    add_money(p,goal["reward_coins"]);ledger_add(p,"expedition_income",goal["reward_coins"])
    await add_event(db,p["id"],goal["name"]+": the village thanks you both.","world","success")
    await save_player(p)
    return {"ok":True}


@api.post("/admin/world/picker/preview")
async def preview_picker(body:dict,admin:dict=Depends(admin_user)):
    if body.get("kind") not in ("world_day_events","world_travel_events","world_weather"):raise HTTPException(422,"Choose a world picker.")
    selected,roll,chances=life.draw(await life.candidates(db,body["kind"],body.get("region")))
    return {"selected":selected["name"] if selected else None,"roll":roll,"chances":chances}


@api.get("/admin/world/life/snapshots")
async def inspect_day_snapshots(admin:dict=Depends(admin_user)):
    return await db.world_days.find({},{"_id":0}).sort("date",-1).to_list(1000)


async def chat_context(channel,peer,user):
    if channel not in ("local","world","whisper"):raise HTTPException(422,"Choose local, world or whisper.")
    p,cfg,state=await world_player(user)
    if channel=="whisper":
        recipient=await db.players.find_one({"id":peer},{"_id":0,"id":1,"name":1,"msg_blocked":1})
        if not recipient or peer==p["id"]:raise HTTPException(404,"Choose another character.")
        tid="whisper:"+":".join(sorted([p["id"],peer]))
        return p,cfg,db.messages,{"thread_id":tid,"$or":[{"from_player_id":p["id"]},{"to_player_id":p["id"]}],"deleted_by":{"$ne":p["id"]}},recipient
    if channel=="world":return p,cfg,db.world_chat,{"deleted":{"$ne":True}},None
    if not state["region"] or (p.get("current_activity") or {}).get("payload",{}).get("travel_to"):
        raise HTTPException(409,"Local conversation is available after you arrive at a location.")
    return p,cfg,db.world_local_chat,{"region":state["region"],"deleted":{"$ne":True}},None


@api.get("/world/chat")
async def rp_chat_read(channel:str="local",peer:Optional[str]=None,user:dict=Depends(current_user)):
    p,cfg,collection,query,recipient=await chat_context(channel,peer,user)
    messages=await collection.find(query,{"_id":0}).sort("ts",-1).to_list(cfg["world_life"]["chat_history_limit"])
    messages.reverse()
    if channel=="whisper":
        await collection.update_many({**query,"to_player_id":p["id"]},{"$set":{"read":True}})
        messages=[{**m,"player_id":m["from_player_id"],"name":m["from_name"],"message":m["body"]} for m in messages]
    return {"messages":messages,"region":p["world"]["region"],"max_length":cfg["world_life"]["chat_max_length"]}


@api.post("/world/chat")
async def rp_chat_send(body:RPChat,user:dict=Depends(current_user)):
    p,cfg,collection,query,recipient=await chat_context(body.channel,body.peer,user)
    text=body.message.strip();settings=cfg["world_life"]
    if not text or len(text)>settings["chat_max_length"]:raise HTTPException(422,"Enter a message within the configured length limit.")
    muted=parse_dt(p.get("chat_muted_until"))
    if muted and muted>now_utc():raise HTTPException(403,"Your chat is temporarily muted.")
    last=parse_dt(p.get("last_chat_at"))
    if last and (now_utc()-last).total_seconds()<settings["chat_cooldown_seconds"]:raise HTTPException(429,"Give the conversation a moment before sending again.")
    if recipient and (p["id"] in recipient.get("msg_blocked",[]) or recipient["id"] in p.get("msg_blocked",[])):
        raise HTTPException(403,"Messages between these characters are blocked.")
    stamp=now_utc().isoformat();doc={"id":uuid.uuid4().hex,"player_id":p["id"],"name":p["name"],"message":comms.clean_text(text),"mode":body.mode,"ts":stamp,"deleted":False}
    if body.channel=="local":doc["region"]=p["world"]["region"]
    if recipient:
        doc.update(channel="whisper",thread_id=query["thread_id"],from_player_id=p["id"],from_name=p["name"],to_player_id=recipient["id"],to_name=recipient["name"],body=doc["message"],subject="Whisper",read=False,deleted_by=[])
    await collection.insert_one(deepcopy(doc))
    p["last_chat_at"]=stamp;await save_player(p)
    return {"ok":True}
