"""Shared daily snapshots and private encounter choices on the authoritative clock."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import uuid
from pymongo.errors import DuplicateKeyError
import world_engine as w
from game_models import now_utc
from game_engine import game_now, game_to_real, game_day_index, parse_dt


def validate_settings(s):
    w.mapping(s, "world_life")
    if not isinstance(s.get("daily_events_enabled"), bool):
        raise ValueError("daily_events_enabled: expected true or false")
    for key,lo,hi,whole in [("travel_event_chance",0,1,False),("chat_max_length",1,4000,True),("chat_history_limit",1,200,True),("chat_cooldown_seconds",0,3600,False),("status_max_length",0,300,True),("presence_minutes",0,60,False)]:
        w.number(s.get(key),key,lo,hi,whole)
    if not isinstance(s.get("phases"),list) or len(s["phases"])>24:
        raise ValueError("phases: use a list of up to 24 time-of-day descriptions")
    for phase in s["phases"]:
        w.mapping(phase,"phase")
        for key in ("name","description"):
            if not isinstance(phase.get(key),str) or len(phase[key])>1000:
                raise ValueError("Phase name/description must be text up to 1000 characters")
        w.number(phase.get("from_hour"),"from_hour",0,23)
        w.number(phase.get("to_hour"),"to_hour",1,24)
        if phase["from_hour"]>=phase["to_hour"]:
            raise ValueError("Phase start must be before its end; split overnight phases at midnight")


def validate_definition(kind,d):
    w.number(d.get("weight"),"weight",0,1e6)
    if kind=="world_weather":
        w.number(d.get("travel_multiplier"),"travel_multiplier",0,10)
        return
    w.ids(d.get("regions"),"regions")
    if kind=="world_day_events":
        goal=w.mapping(d.get("goal"),"goal")
        if not isinstance(goal.get("name"),str) or len(goal["name"])>120:
            raise ValueError("Goal name must be text up to 120 characters")
        w.number(goal.get("target"),"goal target",0,100000,True)
        w.number(goal.get("reward_coins"),"goal reward",0,1e6,True)
    else:
        w.number(d.get("delay_minutes"),"delay_minutes",0,10080)
    if not isinstance(d.get("choices"),list) or not 1<=len(d["choices"])<=12:
        raise ValueError("Use 1–12 choices for each encounter")
    seen=set()
    for choice in d["choices"]:
        w.validate_definition("world_actions",choice)
        if choice["id"] in seen: raise ValueError("Choice IDs must be unique")
        seen.add(choice["id"])
        for outcome in choice["outcomes"]:
            w.number(outcome.get("contribution",0),"contribution",0,1000,True)


async def candidates(db,kind,region=None):
    rows=await db[kind].find({"active":{"$ne":False}}, {"_id":0}).to_list(1000)
    return [r for r in rows if r.get("weight",0)>0 and (not r.get("regions") or region in r["regions"])]


def draw(rows):
    if not rows: return None,None,[]
    chosen,roll=w.pick(rows)
    total=sum(r["weight"] for r in rows)
    return deepcopy(chosen),roll,[{"name":r["name"],"probability":r["weight"]/total} for r in rows]


async def snapshot(db,key,kind,cfg,region=None,at=None):
    existing=await db.world_days.find_one({"_id":key})
    if existing:return existing
    rows=await candidates(db,kind,region) if kind!="world_day_events" or cfg["world_life"]["daily_events_enabled"] else []
    event,roll,chances=draw(rows)
    doc={"_id":key,"id":key,"date":game_now(cfg,at).date().isoformat(),"region":region,"definition":event,"roll":roll,"chances":chances}
    try: await db.world_days.insert_one(deepcopy(doc))
    except DuplicateKeyError: pass
    return await db.world_days.find_one({"_id":key})


async def day_state(db,region,cfg,at=None):
    date=game_now(cfg,at).date().isoformat()
    weather=await snapshot(db,"weather_"+date,"world_weather",cfg,at=at)
    key="day_"+sha256((date+":"+str(region)).encode()).hexdigest()[:32]
    event=await snapshot(db,key,"world_day_events",cfg,region,at) if region else None
    return event,weather


def choice_view(p,definition,cfg,profs,npcs):
    choices=[]
    for choice in definition.get("choices",[]):
        if choice.get("active") is False:continue
        c=deepcopy(choice)
        c["reason"]=w.action_reason(p,c,cfg,profs,npcs)
        c["outcomes"]=w.probabilities(p,c,cfg)
        choices.append(c)
    return choices


async def goal_state(db,instance,p):
    goal=(instance.get("definition") or {}).get("goal",{})
    region=instance["region"]
    records=await db.players.find({f"world.daily_visits.{region}.event_id":instance["id"]},{"_id":0,"name":1,f"world.daily_visits.{region}":1}).to_list(1000)
    contributors=[{"name":r["name"],"amount":r["world"]["daily_visits"][region].get("contribution",0)} for r in records]
    total=sum(x["amount"] for x in contributors)
    mine=p.get("world",{}).get("daily_visits",{}).get(region,{})
    return {**goal,"progress":total,"contributors":[x for x in contributors if x["amount"]>0],
            "claimed":mine.get("event_id")==instance["id"] and mine.get("goal_claimed",False),
            "can_claim":goal.get("target",0)>0 and total>=goal["target"] and mine.get("event_id")==instance["id"] and mine.get("contribution",0)>0 and not mine.get("goal_claimed",False)}


async def scene(db,p,cfg,profs,npcs,at=None):
    at=at or now_utc(); clock=game_now(cfg,at); state=w.state(p,cfg)
    instance,weather=await day_state(db,state["region"],cfg,at)
    hour=clock.hour+clock.minute/60+clock.second/3600
    phase=next((v for v in cfg["world_life"]["phases"] if v["from_hour"]<=hour<v["to_hour"]),None)
    midnight=clock.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)
    daily=None
    if instance and instance["definition"]:
        mine=state.get("daily_visits",{}).get(state["region"],{})
        daily={"id":instance["id"],"date":instance["date"],**deepcopy(instance["definition"])}
        daily["id"]=instance["id"]
        daily.update(choices=choice_view(p,instance["definition"],cfg,profs,npcs),picker_roll=instance["roll"],picker_chances=instance["chances"],
                     mine=mine if mine.get("event_id")==instance["id"] else None,goal=await goal_state(db,instance,p))
    encounter=deepcopy(state.get("pending_encounter"))
    if encounter:encounter["choices"]=choice_view(p,encounter["definition"],cfg,profs,npcs)
    return {"day":game_day_index(cfg,at)+1,"date":clock.date().isoformat(),"clock":clock.strftime("%H:%M"),"phase":phase,
            "next_day_at":game_to_real(cfg,midnight).isoformat(),"weather":weather["definition"],"daily":daily,"encounter":encounter,
            "status_max_length":cfg["world_life"]["status_max_length"]}


async def prepare_travel(db,p,target,minutes,cfg,at=None):
    state=w.state(p,cfg)
    _,weather=await day_state(db,state["region"],cfg,at)
    sky=weather["definition"]
    chance=cfg["world_life"]["travel_event_chance"]
    event,roll,chances=(None,None,[])
    if chance>0 and w.RNG.random()<chance:
        event,roll,chances=draw(await candidates(db,"world_travel_events",target["id"]))
    base=minutes*(sky["travel_multiplier"] if sky else 1)
    delay=event["delay_minutes"] if event and minutes>0 else 0
    payload={"travel_to":target["id"],"travel_from":state["region"],"name":target["name"],"id":uuid.uuid4().hex,
             "weather":sky["name"] if sky else None,"base_minutes":minutes,"travel_minutes":base+delay,
             "encounter":event,"encounter_roll":roll,"encounter_chances":chances}
    return payload,base+delay


def finish_travel(p,cfg,payload,at):
    state=w.state(p,cfg)
    trip={"id":payload.get("id",at.isoformat()),"from":payload.get("travel_from"),"to":payload["travel_to"],"name":payload["name"],"at":at.isoformat(),
          "weather":payload.get("weather"),"minutes":payload.get("travel_minutes"),"event_name":(payload.get("encounter") or {}).get("name")}
    log=state.setdefault("travel_log",[])
    if not any(t["id"]==trip["id"] for t in log):state["travel_log"]=(log+[trip])[-cfg["world"]["report_limit"]:]
    if payload.get("encounter"):
        state["pending_encounter"]={"id":trip["id"],"definition":deepcopy(payload["encounter"]),"arrived_at":at.isoformat(),"region":payload["travel_to"],"picker_roll":payload["encounter_roll"],"picker_chances":payload["encounter_chances"]}


def finish_choice(p,cfg,payload,report):
    context=payload.get("life_event")
    if not context:return
    report["event_kind"]=context["kind"]
    if context["kind"]=="day":
        mine=w.state(p,cfg).setdefault("daily_visits",{}).get(context["region"])
        if mine and mine["event_id"]==context["id"]:
            mine.update(status="completed",result=report["result"],contribution=payload["outcome"].get("contribution",0))


def public_presence(p,cfg,at=None):
    at=at or now_utc();state=p.get("world",{});act=p.get("current_activity") or {};payload=act.get("payload") or {}
    last=parse_dt(p.get("last_seen"));end=parse_dt(act.get("ends_at"))
    traveling=act.get("kind")=="world" and bool(payload.get("travel_to"))
    # Do not resolve another player's state without their lease. Explicitly show
    # arrival pending a refresh rather than assert an uncommitted destination.
    trip={"to":payload["travel_to"],"from":payload.get("travel_from",state.get("region")),"ends_at":act["ends_at"],"arrival_pending":end<=at} if traveling and end else None
    return {"id":p["id"],"name":p["name"],"region":state.get("region"),"profession":state.get("profession"),"status":state.get("rp_status",""),
            "online":bool(last and 0<cfg["world_life"]["presence_minutes"] and (at-last).total_seconds()<=cfg["world_life"]["presence_minutes"]*60),"last_seen":p.get("last_seen"),"travel":trip}
