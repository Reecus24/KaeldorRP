"""Isolated multiplayer/picker tests. Never connects to a live database."""
import asyncio
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
import pytest
import httpx
from test_world import NOW,player,api_fixture
from game_models import DEFAULT_CONFIG
from world_life_content import DAY_EVENTS,TRAVEL_EVENTS,WEATHER,LIFE_CONFIG
from seed_data import seed_content
import world_life as life
import world_engine as w
import game_engine as ge


def setup(monkeypatch):
    import core,game_models
    import routes.world_life as route
    import routes.social as social
    db,core,app=api_fixture(monkeypatch)
    for module in (route,social):monkeypatch.setattr(module,"db",db)
    for module in (life,w,ge,core,game_models,route):monkeypatch.setattr(module,"now_utc",lambda:NOW)
    monkeypatch.setattr(w,"RNG",SimpleNamespace(random=lambda:0,randint=lambda lo,hi:lo))
    return db,core,app,route


async def users(db,core):
    result=[]
    for name,role in [("A","admin"),("B","player"),("C","player")]:
        email=name+"@test.local";uid=(await db.users.insert_one({"email":email,"role":role})).inserted_id
        p=player(str(uid));p["name"]=name;p["last_seen"]=NOW.isoformat()
        await db.players.insert_one(p)
        result.append((p,{"Authorization":"Bearer "+core.create_access_token(str(uid),email)}))
    return result


def test_shared_day_concurrent_draw_midnight_and_empty_owner_pools(monkeypatch):
    db,_,_,_=setup(monkeypatch)
    async def run():
        await seed_content(db)
        cfg=deepcopy(DEFAULT_CONFIG);cfg.update(world_start_real=NOW.isoformat(),world_start_game=NOW.isoformat(),time_scale=12)
        results=await asyncio.gather(*[life.day_state(db,"millhaven",cfg,NOW) for _ in range(12)])
        assert all(r==results[0] for r in results)
        assert await db.world_days.count_documents({})==2
        previous=deepcopy(results[0])
        await db.world_day_events.delete_many({});await db.world_weather.update_many({},{"$set":{"weight":0}})
        assert await life.day_state(db,"millhaven",cfg,NOW)==previous
        later=NOW+timedelta(hours=2) # 24 game hours later
        new,weather=await life.day_state(db,"millhaven",cfg,later)
        assert new["id"]!=previous[0]["id"] and new["definition"] is None and weather["definition"] is None
        await seed_content(db)
        assert await db.world_day_events.count_documents({})==0
        assert all(r["weight"]==0 for r in await db.world_weather.find({}).to_list(100))
    asyncio.run(run())


def test_two_players_contribute_once_and_each_claims_once(monkeypatch):
    db,core,app,_=setup(monkeypatch)
    async def run():
        await seed_content(db)
        await db.config.update_one({"id":"global"},{"$set":{"world_start_real":NOW.isoformat(),"world_start_game":NOW.isoformat()}})
        actors=await users(db,core)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as c:
            scenes=[]
            for p,auth in actors[:2]:
                r=await c.get("/api/world",headers=auth);assert r.status_code==200,r.text
                scenes.append(r.json()["life"]["daily"])
            assert scenes[0]["id"]==scenes[1]["id"]
            event=scenes[0];body={"event_id":event["id"],"choice_id":event["choices"][0]["id"]}
            p,auth=actors[0]
            responses=await asyncio.gather(*[c.post("/api/world/life/day/choose",json=body,headers=auth) for _ in range(3)])
            assert sorted(r.status_code for r in responses)==[200,409,409]
            first=await db.players.find_one({"id":p["id"]})
            assert first["world"]["daily_visits"]["millhaven"]["status"]=="completed"
            assert first["world"]["daily_visits"]["millhaven"]["contribution"]==1
            assert (await c.post("/api/world/life/day/claim",json={"event_id":event["id"]},headers=auth)).status_code==409
            assert (await c.post("/api/world/life/day/choose",json=body,headers=actors[1][1])).status_code==200
            for p,auth in actors[:2]:
                before=await db.players.find_one({"id":p["id"]})
                rewards=await asyncio.gather(*[c.post("/api/world/life/day/claim",json={"event_id":event["id"]},headers=auth) for _ in range(2)])
                assert sorted(r.status_code for r in rewards)==[200,409]
                after=await db.players.find_one({"id":p["id"]})
                assert after["cash"]-before["cash"]==event["goal"]["reward_coins"]
            assert (await c.post("/api/world/life/day/claim",json={"event_id":event["id"]},headers=actors[2][1])).status_code==409
            assert (await c.post("/api/world/life/day/choose",json={**body,"event_id":"yesterday"},headers=actors[2][1])).status_code==409
            assert (await c.post("/api/admin/world/picker/preview",json={"kind":"world_day_events"},headers=actors[1][1])).status_code==403
            count=await db.world_days.count_documents({})
            assert (await c.post("/api/admin/world/picker/preview",json={"kind":"world_day_events","region":"millhaven"},headers=actors[0][1])).status_code==200
            assert await db.world_days.count_documents({})==count
    asyncio.run(run())


def test_chat_locality_private_access_mode_blocking_and_travel_presence(monkeypatch):
    db,core,app,_=setup(monkeypatch)
    async def run():
        await seed_content(db)
        await db.config.update_one({"id":"global"},{"$set":{"world_life.chat_cooldown_seconds":0}})
        actors=await users(db,core)
        a,b,c=actors
        await db.players.update_one({"id":c[0]["id"]},{"$set":{"world.region":"ironwood"}})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
            async def send(auth,**kw):return await client.post("/api/world/chat",json={"message":"The mill is safe","channel":"local","mode":"emote",**kw},headers=auth)
            assert (await send(a[1])).status_code==200
            local=(await client.get("/api/world/chat",headers=b[1])).json()["messages"]
            assert len(local)==1 and local[0]["mode"]=="emote"
            assert not (await client.get("/api/world/chat?channel=local",headers=c[1])).json()["messages"]
            assert (await send(a[1],channel="whisper",peer=b[0]["id"],message="Private plan")).status_code==200
            private=(await client.get("/api/world/chat",params={"channel":"whisper","peer":a[0]["id"]},headers=b[1])).json()["messages"]
            assert private[0]["message"]=="Private plan"
            stolen=(await client.get("/api/world/chat",params={"channel":"whisper","peer":a[0]["id"]},headers=c[1])).json()["messages"]
            assert stolen==[]
            assert (await client.get("/api/messages/thread/"+private[0]["thread_id"],headers=c[1])).json()["messages"]==[]
            await db.players.update_one({"id":b[0]["id"]},{"$set":{"msg_blocked":[a[0]["id"]]}})
            assert (await send(a[1],channel="whisper",peer=b[0]["id"])).status_code==403
            assert (await send(a[1],message=" ")).status_code==422
            await db.players.update_one({"id":a[0]["id"]},{"$set":{"current_activity":{"kind":"world","ends_at":(NOW+timedelta(minutes=2)).isoformat(),"payload":{"travel_to":"ironwood","travel_from":"millhaven","outcome":{"secret":1}}}}})
            assert (await send(a[1])).status_code==409
            state=(await client.get("/api/world",headers=b[1])).json()
            other=next(p for p in state["presence"] if p["id"]==a[0]["id"])
            assert other["travel"]["to"]=="ironwood" and other["region"]=="millhaven"
            assert "secret" not in str(other) and "cash" not in other
            assert (await send(a[1],channel="world")).status_code==200
    asyncio.run(run())


@pytest.mark.parametrize("scale",[1,12])
def test_travel_snapshot_weather_zero_and_offline_equivalence(monkeypatch,scale):
    db,_,_,_=setup(monkeypatch)
    async def run():
        await seed_content(db)
        cfg=deepcopy(DEFAULT_CONFIG);cfg.update(time_scale=scale,world_start_game=NOW.isoformat(),world_start_real=NOW.isoformat());cfg["world_life"]["travel_event_chance"]=1
        await db.world_weather.delete_many({});sky=deepcopy(WEATHER[0]);sky["travel_multiplier"]=2;await db.world_weather.insert_one(sky)
        await db.world_travel_events.delete_many({});enc=deepcopy(TRAVEL_EVENTS[0]);enc["delay_minutes"]=3;await db.world_travel_events.insert_one(enc)
        p=player();payload,duration=await life.prepare_travel(db,p,{"id":"ironwood","name":"Ironwood"},5,cfg,NOW)
        assert duration==13
        await db.world_travel_events.update_one({"id":enc["id"]},{"$set":{"description":"Changed after departure"}})
        end=NOW+timedelta(seconds=ge.real_seconds(duration,scale));p["current_activity"]={"kind":"world","started_at":NOW.isoformat(),"ends_at":end.isoformat(),"payload":payload};p["status"]="busy"
        online,offline=deepcopy(p),deepcopy(p)
        await ge.advance_player_time(db,offline,cfg,NOW,end)
        cursor=NOW
        for n in range(1,14):
            step=NOW+timedelta(seconds=ge.real_seconds(n,scale));await ge.advance_player_time(db,online,cfg,cursor,step);cursor=step
        assert online["world"]["pending_encounter"]==offline["world"]["pending_encounter"]
        assert online["world"]["travel_log"]==offline["world"]["travel_log"]
        assert offline["world"]["pending_encounter"]["definition"]["description"]==enc["description"]
        for key in ("energy","hunger","health","fatigue"):assert online[key]==pytest.approx(offline[key])
        await ge.advance_player_time(db,offline,cfg,end,end)
        assert len(offline["world"]["travel_log"])==1
        cfg["world_life"]["travel_event_chance"]=0
        quiet,zero=await life.prepare_travel(db,player(),{"id":"ironwood","name":"Ironwood"},0,cfg,NOW)
        assert zero==0 and quiet["encounter"] is None
        cfg["world_life"]["travel_event_chance"]=1
        instant,zero=await life.prepare_travel(db,player(),{"id":"ironwood","name":"Ironwood"},0,cfg,NOW)
        assert instant["encounter"] is not None and zero==0
    asyncio.run(run())


@pytest.mark.parametrize("patch",[{"travel_event_chance":-1},{"chat_max_length":0},{"presence_minutes":float("inf")},{"phases":[{"name":"bad","description":"","from_hour":20,"to_hour":5}]}])
def test_invalid_life_settings_rejected(patch):
    with pytest.raises(ValueError):life.validate_settings({**deepcopy(LIFE_CONFIG),**patch})


def test_zero_picker_weight_goal_and_weather_remain_valid():
    for kind,template in [("world_day_events",DAY_EVENTS[0]),("world_travel_events",TRAVEL_EVENTS[0]),("world_weather",WEATHER[0])]:
        d=deepcopy(template);d["weight"]=0
        if "goal" in d:d["goal"].update(target=0,reward_coins=0)
        if "travel_multiplier" in d:d["travel_multiplier"]=0
        w.validate_definition(kind,d)
    assert life.draw([])==(None,None,[])


def test_fractional_owner_phase_boundaries_and_empty_phases(monkeypatch):
    db,_,_,_=setup(monkeypatch)
    async def run():
        await seed_content(db)
        cfg=deepcopy(DEFAULT_CONFIG);cfg.update(world_start_real=NOW.isoformat(),world_start_game=NOW.isoformat())
        cfg["world_life"]["phases"]=[{"name":"Early bells","description":"An Owner-written dawn.","from_hour":8.5,"to_hour":9.5}]
        before=await life.scene(db,player(),cfg,{}, {},NOW+timedelta(minutes=29))
        during=await life.scene(db,player(),cfg,{}, {},NOW+timedelta(minutes=30))
        assert before["phase"] is None and during["phase"]["name"]=="Early bells"
        cfg["world_life"]["phases"]=[]
        assert (await life.scene(db,player(),cfg,{}, {},NOW+timedelta(minutes=31)))["phase"] is None
    asyncio.run(run())


def test_road_response_is_single_use_and_daily_cancellation_cannot_reroll(monkeypatch):
    db,core,app,_=setup(monkeypatch)
    async def run():
        await seed_content(db)
        actors=await users(db,core);p,auth=actors[0]
        await db.players.update_one({"id":p["id"]},{"$set":{"world.pending_encounter":{"id":"road_one","definition":deepcopy(TRAVEL_EVENTS[0]),"region":"millhaven"}}})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as c:
            assert (await c.post("/api/world/travel/greenfields",headers=auth)).status_code==409
            choices=await asyncio.gather(*[c.post("/api/world/life/road/choose",headers=auth,json={"event_id":"road_one","choice_id":"fix"}) for _ in range(2)])
            assert sorted(r.status_code for r in choices)==[200,409]
            final=await db.players.find_one({"id":p["id"]})
            assert final["world"]["pending_encounter"] is None
            assert len(final["world"]["reports"])==1
            await db.world_day_events.delete_many({})
            long=deepcopy(DAY_EVENTS[0]);long["choices"][0]["duration_minutes"]=10
            await db.world_day_events.insert_one(long)
            daily=(await c.get("/api/world",headers=auth)).json()["life"]["daily"]
            body={"event_id":daily["id"],"choice_id":daily["choices"][0]["id"]}
            assert (await c.post("/api/world/life/day/choose",headers=auth,json=body)).status_code==200
            assert (await c.post("/api/game/cancel-activity",headers=auth)).status_code==200
            after=await db.players.find_one({"id":p["id"]})
            assert after["world"]["daily_visits"]["millhaven"]["status"]=="cancelled"
            assert (await c.post("/api/world/life/day/choose",headers=auth,json=body)).status_code==409
    asyncio.run(run())
