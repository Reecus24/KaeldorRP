"""Isolated open-world checks; no network, no external AI and no production DB."""
import asyncio
import os
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import pytest

os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:1")
os.environ.setdefault("DB_NAME", "world_tests")
from mongomock_motor import AsyncMongoMockClient
from world_content import WORLD_CONTENT, WORLD_ACTIONS, WORLD_ORIGINS, WORLD_PROFESSIONS, WORLD_NPCS
from game_models import DEFAULT_CONFIG, new_player
import world_engine as w
import game_engine as ge

NOW = datetime(2026, 11, 10, 8, tzinfo=timezone.utc)


def player(uid="u"):
    p = new_player(uid, "Rowan", "drifter")
    p.update(cash=5000, bank=0, net_worth=5000, health=100, hunger=10, last_resolved_at=NOW.isoformat(), created_at=NOW.isoformat())
    w.state(p, DEFAULT_CONFIG)
    return p


@pytest.mark.parametrize("kind", list(WORLD_CONTENT))
def test_owner_definitions_validate(kind):
    for doc in WORLD_CONTENT[kind][1]:
        w.validate_definition(kind, doc)


@pytest.mark.parametrize("patch", [{"difficulty": float("inf")}, {"duration_minutes": -1}, {"energy_cost": 101}, {"skill": "$bad"}, {"outcomes": []}, {"regions": "any"}, {"requirements": {"training": {"smithing": -1}}}])
def test_malformed_actions_rejected(patch):
    with pytest.raises(ValueError):
        w.validate_definition("world_actions", {**WORLD_ACTIONS[0], **patch})


def test_weighted_picker_zero_boundaries_and_skill_improvement():
    p = player()
    a = deepcopy(WORLD_ACTIONS[0])
    base = w.probabilities(p, a, DEFAULT_CONFIG)
    p["skills"][a["skill"]]["level"] = 12
    better = w.probabilities(p, a, DEFAULT_CONFIG)
    assert sum(o["probability"] for o in base) == pytest.approx(1)
    assert sum(o["probability"] for o in better if o["success"]) > sum(o["probability"] for o in base if o["success"])
    rows = [{"weight": 0, "id": "never"}, {"weight": 2, "id": "first"}, {"weight": 1, "id": "second"}]
    assert w.pick(rows, roll=0)[0]["id"] == "first"
    assert w.pick(rows, roll=2/3)[0]["id"] == "second"
    assert w.pick(rows, roll=.99999)[0]["id"] == "second"
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg["world"].update(base_success=0, min_success=0, max_success=0)
    assert all(o["probability"] == 0 for o in w.probabilities(p, a, cfg) if o["success"])


def test_origin_picker_inclusive_ranges_absolute_skills_and_zero_coins(monkeypatch):
    monkeypatch.setattr(w, "RNG", SimpleNamespace(random=lambda: 0, randint=lambda low, high: high))
    origins = deepcopy(WORLD_ORIGINS)
    origins[0].update(coins=[0, 0], age=[18, 18], skills={"shipbuilding": [2, 4]}, stats={"stress": [0, 0]})
    result = w.origin_roll(origins)
    assert result["cash"] == 0 and result["age"] == 18 and result["skills"]["shipbuilding"] == 4
    assert result["stats"]["stress"] == 0
    for o in origins:
        o["weight"] = 0
    with pytest.raises(ValueError):
        w.origin_roll(origins)


def test_professions_require_both_learning_and_skill_and_cycles_fail_closed():
    p = player()
    profs = {d["id"]: deepcopy(d) for d in WORLD_PROFESSIONS}
    req = {"professions": ["shipwright"]}
    p["skills"]["shipbuilding"] = {"level": 4, "xp": 0}
    assert "lessons" in w.requirements_reason(p, req, profs)
    p["world"]["training"]["shipbuilding"] = 10
    assert not w.requirements_reason(p, req, profs)
    profs["shipwright"]["requirements"] = req
    assert "circular" in w.requirements_reason(p, req, profs)
    profs["shipwright"]["active"] = False
    assert "unavailable" in w.requirements_reason(p, req, profs)


def test_npc_memory_private_bounded_and_zero_does_not_keep_turns():
    p, other = player(), player("other")
    cfg = deepcopy(DEFAULT_CONFIG); cfg["world"]["memory_turns"] = 2
    for text in ("one", "two", "three"):
        w.remember(p["world"], "mira", text, "Hello", cfg, NOW)
    assert [x["player"] for x in p["world"]["memories"]["mira"]["turns"]] == ["two", "three"]
    assert "three" in w.scripted_reply(p, WORLD_NPCS[0], "remember me", [])
    assert other["world"]["memories"] == {}
    cfg["world"]["memory_turns"] = 0
    w.remember(p["world"], "mira", "four", "Hello", cfg, NOW)
    assert p["world"]["memories"]["mira"]["turns"] == []
    assert p["world"]["memories"]["mira"]["visits"] == 4


@pytest.mark.parametrize("scale", [1, 12])
@pytest.mark.parametrize("roll", [0, .9999])
def test_world_outcomes_offline_equal_polling_and_resolve_once(monkeypatch, scale, roll):
    monkeypatch.setattr(w, "RNG", SimpleNamespace(random=lambda: roll, randint=lambda low, high: low))
    async def run():
        db = AsyncMongoMockClient().world
        cfg = deepcopy(DEFAULT_CONFIG); cfg["time_scale"] = scale
        a = deepcopy(WORLD_ACTIONS[0]); a["duration_minutes"] = 10
        for o in a["outcomes"]:
            o["effects"] = {"health": -100}; o["training"] = {"smithing": 1}
        p = player()
        payload = w.prepare_action(p, a, cfg, NOW)
        end = NOW + timedelta(seconds=ge.real_seconds(10, scale))
        p["current_activity"] = {"kind": "world", "started_at": NOW.isoformat(), "ends_at": end.isoformat(), "payload": payload}
        p["status"] = "busy"
        offline, online = deepcopy(p), deepcopy(p)
        final = NOW + timedelta(seconds=ge.real_seconds(420, scale))
        await ge.advance_player_time(db, offline, cfg, NOW, final)
        cursor = NOW
        for i in range(1, 43):
            step = NOW + timedelta(seconds=ge.real_seconds(i * 10, scale))
            await ge.advance_player_time(db, online, cfg, cursor, step)
            cursor = step
        for key in ("health", "hunger", "energy", "fatigue", "cash", "xp"):
            assert online[key] == pytest.approx(offline[key]), key
        assert online["world"]["reports"] == offline["world"]["reports"]
        assert len(offline["world"]["reports"]) == 1
        assert offline["world"]["training"]["smithing"] == 1
        assert offline["current_activity"] is None
        await ge.advance_player_time(db, offline, cfg, final, final)
        assert len(offline["world"]["reports"]) == 1
    asyncio.run(run())


def test_snapshot_and_supply_costs_and_lesson_location():
    p = player(); cfg = deepcopy(DEFAULT_CONFIG); a = deepcopy(WORLD_ACTIONS[0])
    a.update(supplies={"protein_bar": 2}, money_cost=0, energy_cost=0)
    prepared = w.prepare_action(p, a, cfg, NOW)
    assert p["cash"] == 5000 and p["energy"] == 100 and p["inventory"]["protein_bar"] == 1
    a["outcomes"][0]["coins"] = [999, 999]
    assert prepared["outcome"]["coin_result"] != 999
    lesson = WORLD_ACTIONS[6]
    profs = {x["id"]: x for x in WORLD_PROFESSIONS}
    npcs = {x["id"]: x for x in WORLD_NPCS}
    assert "Travel" in w.action_reason(p, lesson, cfg, profs, npcs, NOW)
    p["world"]["region"] = "cinderforge"
    assert not w.action_reason(p, lesson, cfg, profs, npcs, NOW)
    assert "teacher" in w.action_reason(p, lesson, cfg, profs, {}, NOW)


def test_world_seeds_never_resurrect_owner_deletions_or_rebalance_zero():
    from seed_data import seed_content
    async def run():
        db = AsyncMongoMockClient().world
        await seed_content(db)
        await db.world_actions.update_one({"id": "field_work"}, {"$set": {"energy_cost": 0}})
        await db.world_origins.delete_many({})
        await db.world_regions.delete_one({"id": "moonfen"})
        await seed_content(db)
        assert await db.world_origins.count_documents({}) == 0
        assert await db.world_regions.find_one({"id": "moonfen"}) is None
        assert (await db.world_actions.find_one({"id": "field_work"}))["energy_cost"] == 0
    asyncio.run(run())


def api_fixture(monkeypatch):
    import core, server
    import routes.world as route
    import routes.player as players
    import routes.admin as admin
    db = AsyncMongoMockClient().world
    for module in (core, route, players, admin):
        monkeypatch.setattr(module, "db", db)
    async def raw(user):
        from fastapi import HTTPException
        p = await db.players.find_one({"user_id": user["id"]}, {"_id": 0})
        if not p:
            raise HTTPException(404, "No character")
        return p
    monkeypatch.setattr(route, "get_state", raw)
    monkeypatch.setattr(players, "get_state", raw)
    return db, core, server.app


def test_api_world_two_players_quest_replay_free_action_and_owner_boundary(monkeypatch):
    import httpx
    from seed_data import seed_content
    db, core, app = api_fixture(monkeypatch)
    async def run():
        await seed_content(db)
        users = []
        for name, role in (("owner", "admin"), ("friend", "player")):
            uid = (await db.users.insert_one({"email": name+"@test.local", "role": role})).inserted_id
            p = player(str(uid)); p["name"] = name
            await db.players.insert_one(p)
            users.append((p, {"Authorization": "Bearer " + core.create_access_token(str(uid),name+"@test.local")}))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            owner, friend = users
            c.headers.update(friend[1])
            assert (await c.get("/api/world")).status_code == 200
            assert (await c.get("/api/admin/world/intents")).status_code == 403
            assert (await c.post("/api/world/travel/moonfen")).status_code == 409
            assert (await c.get("/api/world/npcs/brann")).status_code == 409
            assert (await c.post("/api/world/npcs/mira/talk", json={"message":"My sister is called Ada."})).json()["mode"] == "scripted"
            assert (await c.post("/api/world/quests/bread_for_winter/accept")).status_code == 200
            assert (await c.post("/api/world/quests/bread_for_winter/accept")).status_code == 409
            assert (await c.post("/api/world/quests/bread_for_winter/claim")).status_code == 409
            await db.players.update_one({"id":friend[0]["id"]},{"$set":{"world.quests.bread_for_winter.progress":2}})
            claims = await asyncio.gather(*[c.post("/api/world/quests/bread_for_winter/claim") for _ in range(4)])
            assert sorted(x.status_code for x in claims) == [200,409,409,409]
            proposal = (await c.post("/api/world/intents",json={"message":"I repair a farmer's broken cart."})).json()["intent"]
            path=f"/api/admin/players/{friend[0]['id']}/world-intents/{proposal['id']}"
            assert (await c.put(path,json={"approved":False})).status_code == 403
            c.headers.update(owner[1])
            assert (await c.get("/api/world/npcs/mira")).json()["memory"] == {}
            pending=(await c.get("/api/admin/world/intents")).json()
            assert len(pending["requests"])==1
            rule=deepcopy(WORLD_ACTIONS[0]);rule.update(money_cost=0,energy_cost=4)
            assert (await c.put(path,json={"approved":True,"definition":rule})).status_code == 200
            assert (await c.put(path,json={"approved":True,"definition":rule})).status_code == 409
            c.headers.update(friend[1])
            responses=await asyncio.gather(*[c.post(f"/api/world/actions/{proposal['id']}/start",json={}) for _ in range(4)])
            assert sorted(x.status_code for x in responses)==[200,404,404,404]
            saved=await db.players.find_one({"id":friend[0]["id"]})
            assert saved["energy"]==96
            assert saved["current_activity"]["payload"]["narrative"]==proposal["text"]
            public=(await c.get("/api/game/state")).json()
            assert public["player"]["current_activity"]["payload"]=={}
            assert public["player"]["cash"]==5030
    asyncio.run(run())


def test_random_creation_cannot_reroll_or_bypass_and_starting_profession_requires_qualification(monkeypatch):
    import httpx
    from seed_data import seed_content
    db, core, app=api_fixture(monkeypatch)
    async def run():
        await seed_content(db)
        await db.world_origins.delete_many({})
        origin=deepcopy(WORLD_ORIGINS[0]);origin.update(coins=[0,0],skills={"sales":[3,3]},professions=[{"id":"merchant","weight":1},{"id":"shipwright","weight":100}])
        await db.world_origins.insert_one(origin)
        uid=(await db.users.insert_one({"email":"new@test.local","role":"player"})).inserted_id
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test",headers={"Authorization":"Bearer "+core.create_access_token(str(uid),"new@test.local")}) as c:
            assert (await c.post("/api/character/create",json={"name":"New","background":"drifter"})).status_code==400
            responses=await asyncio.gather(*[c.post("/api/character/create",json={"name":"New","background":"random"}) for _ in range(3)])
            assert sorted(x.status_code for x in responses)==[200,400,400]
        saved=await db.players.find_one({"user_id":str(uid)})
        assert saved["cash"]==0 and saved["skills"]["sales"]["level"]==3
        assert saved["world"]["profession"]=="merchant"
        assert await db.players.count_documents({"user_id":str(uid)})==1
    asyncio.run(run())


def test_founding_is_shared_but_editing_and_commissions_are_authorized(monkeypatch):
    import httpx
    from seed_data import seed_content
    db, core, app=api_fixture(monkeypatch)
    async def run():
        await seed_content(db)
        members=[]
        for name in ("Smith","Friend"):
            uid=(await db.users.insert_one({"email":name+"@test.local","role":"player"})).inserted_id
            p=player(str(uid));p["skills"]["crafting"]["level"]=4;p["world"]["training"]["smithing"]=8
            await db.players.insert_one(p)
            members.append((p,{"Authorization":"Bearer "+core.create_access_token(str(uid),name+"@test.local")}))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as c:
            c.headers.update(members[0][1])
            result=await c.post("/api/world/foundings",json={"charter_id":"smithy","name":"Ash & Iron","description":"Friends at the forge"})
            assert result.status_code==200,result.text
            fid=result.json()["founding"]["id"]
            c.headers.update(members[1][1])
            assert (await c.post("/api/world/actions/forge_blade/start",json={"founding_id":fid})).status_code==409
            assert (await c.post(f"/api/world/foundings/{fid}/join")).status_code==200
            assert (await c.put(f"/api/world/foundings/{fid}",json={"name":"Stolen","description":""})).status_code==403
            assert (await c.post("/api/world/actions/forge_blade/start",json={"founding_id":fid})).status_code==200
            assert len((await c.get(f"/api/world/foundings/{fid}/members")).json())==2
            founder=await db.players.find_one({"id":members[0][0]["id"]})
            assert founder["cash"]==4350
    asyncio.run(run())


def test_travel_completion_and_owner_character_edits_preserve_other_progress(monkeypatch):
    import routes.world as route
    from seed_data import seed_content
    from fastapi import HTTPException
    db, core, app = api_fixture(monkeypatch)
    async def settled(db, p):
        return p
    monkeypatch.setattr(route, "resolve_player", settled)
    async def run():
        await seed_content(db)
        p = player()
        p["world"]["foundings"] = [{"id":"old", "name":"Old fellowship"}]
        await w.complete(db, p, DEFAULT_CONFIG, {"travel_to":"reedharbour", "name":"Reedharbour"}, NOW)
        assert p["world"]["region"] == "reedharbour" and "reedharbour" in p["world"]["visited"]
        w.remember(p["world"], "elin", "I was a carpenter.", "Tell me more.", DEFAULT_CONFIG, NOW)
        await db.players.insert_one(p)
        await route.edit_world_character(p["id"], {"region":"millhaven", "training":{"smithing":0}, "memories":{}, "skills":{"shipbuilding":{"level":4,"xp":0}}}, {"role":"admin"})
        updated = await db.players.find_one({"id":p["id"]})
        assert updated["cash"] == p["cash"]
        assert updated["world"]["foundings"] == p["world"]["foundings"]
        assert updated["world"]["memories"] == {} and updated["world"]["training"] == {"smithing":0}
        assert updated["skills"]["shipbuilding"]["level"] == 4 and "fitness" in updated["skills"]
        with pytest.raises(HTTPException) as blocked:
            await route.edit_world_character(p["id"], {"skills":{"shipbuilding":{"level":4,"xp":float("nan")}}}, {"role":"admin"})
        assert blocked.value.status_code == 422
        npc = deepcopy(WORLD_NPCS[0]);npc["schedule"]=[{"from_hour":22,"to_hour":6,"region":"moonfen"}]
        cfg=deepcopy(DEFAULT_CONFIG);cfg["world_start_real"]=NOW.isoformat();cfg["world_start_game"]=NOW.isoformat()
        assert w.npc_region(npc,cfg,NOW.replace(hour=23))=="moonfen"
        assert w.npc_region(npc,cfg,NOW.replace(hour=8))=="millhaven"
    asyncio.run(run())


def test_owner_zero_limits_and_world_validation():
    from config_schema import validate_config
    cfg=deepcopy(DEFAULT_CONFIG)
    cfg["world"].update(max_pending_intents=0,max_foundings=0,max_active_quests=0,memory_turns=0,dialogue_cooldown_seconds=0,base_success=0,min_success=0,max_success=0)
    validate_config(cfg, DEFAULT_CONFIG)
    cfg["world"]["min_success"]=.8
    with pytest.raises(ValueError):
        validate_config(cfg, DEFAULT_CONFIG)
