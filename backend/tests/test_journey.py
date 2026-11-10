"""No live services: authored content, persistence, branching and reward replay guards."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import os
import pytest

os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:1")
os.environ.setdefault("DB_NAME", "journey_tests")

from game_models import new_player, DEFAULT_CONFIG
from journey_content import JOURNEY_GOALS, STORY_ARCS, CITY_EVENTS
import journey_engine as je
from fastapi import HTTPException


@pytest.mark.parametrize("kind,docs", [("journey_goals", JOURNEY_GOALS), ("story_arcs", STORY_ARCS), ("city_events", CITY_EVENTS)])
def test_all_seed_content_is_valid(kind, docs):
    for doc in docs:
        je.validate_definition(kind, doc)


@pytest.mark.parametrize("mutation", [
    lambda d: d["nodes"][0]["choices"][0].update(next="missing"),
    lambda d: d["nodes"][0]["choices"][0].update(next="hello"),
    lambda d: d["nodes"][0]["choices"][0].update(cost=-1),
    lambda d: d["nodes"][0]["choices"][0].update(rewards={"xp": float("inf")}),
    lambda d: d["nodes"][0]["choices"][0].update(rewards={"items": {"sandwich": 0.5}}),
    lambda d: d["nodes"][0]["choices"][0].update(rewards={"skills": {"imaginary": 3}}),
    lambda d: d["nodes"][0]["choices"][0].update(requirements=[{"metric": "cash;delete", "target": 1}]),
    lambda d: d["nodes"][0]["choices"][0].update(requirements=[{"metric": "actions", "target": 1, "href": "//evil.test"}]),
])
def test_rejects_invalid_authoring(mutation):
    d = deepcopy(STORY_ARCS[0])
    mutation(d)
    with pytest.raises(ValueError):
        je.validate_definition("story_arcs", d)


def test_city_schedule_exact_boundaries_independent_of_polling():
    now = datetime(2050, 1, 1, tzinfo=timezone.utc)
    cfg = {**DEFAULT_CONFIG, "world_start_real": now.isoformat()}
    e = CITY_EVENTS[0]
    assert je.city_window(e, cfg, now)["is_live"]
    assert je.city_window(e, cfg, now + timedelta(hours=24) - timedelta(microseconds=1))["is_live"]
    assert not je.city_window(e, cfg, now + timedelta(hours=24))["is_live"]
    next_cycle = je.city_window(e, cfg, now + timedelta(hours=72))
    assert next_cycle["is_live"] and next_cycle["cycle"] == 1
    assert je.run_id("s", next_cycle) != je.run_id("s", je.city_window(e, cfg, now))
    assert not je.city_window(e, cfg, now - timedelta(seconds=1))["is_live"]


@pytest.fixture
def world(monkeypatch):
    from mongomock_motor import AsyncMongoMockClient
    import routes.journey as route
    db = AsyncMongoMockClient().journey
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg["world_start_real"] = je.now_utc().isoformat()
    p = new_player("u", "Player", "drifter")
    p.update(cash=1000, bank=0)
    async def state(user):
        return await db.players.find_one({"user_id": "u"}, {"_id": 0})
    async def save(player):
        await db.players.replace_one({"id": player["id"]}, deepcopy(player))
    async def config(_):
        return deepcopy(cfg)
    async def noop(*args, **kwargs):
        pass
    for key, value in {"db": db, "get_state": state, "save_player": save, "get_config": config, "add_event": noop}.items():
        monkeypatch.setattr(route, key, value)
    async def seed():
        await db.players.insert_one(deepcopy(p))
        for kind, docs in [("journey_goals", JOURNEY_GOALS), ("story_arcs", STORY_ARCS), ("city_events", CITY_EVENTS)]:
            await db[kind].insert_many(deepcopy(docs))
    asyncio.run(seed())
    return route, db, cfg


def test_goal_switch_and_replay_preserve_progress(world):
    route, db, _ = world
    async def run():
        await route.track_goal("entrepreneur", {})
        await route.claim_milestone("entrepreneur", "runway", {})
        p = await route.get_state({})
        xp = p["xp"]
        await route.track_goal("professional", {})
        await route.track_goal("entrepreneur", {})
        with pytest.raises(HTTPException) as exc:
            await route.claim_milestone("entrepreneur", "runway", {})
        assert exc.value.status_code == 409
        assert (await route.get_state({}))["xp"] == xp
        assert (await route.journey_view({}))["focus"] == "entrepreneur"
        await db.journey_goals.delete_many({})
        assert (await route.journey_view({}))["goals"]
    asyncio.run(run())


def test_branching_snapshot_survives_owner_edits_and_rejects_double_choice(world):
    route, db, _ = world
    async def choose(node, choice):
        return await route.story_choice("first_delivery", route.StoryChoiceBody(node_id=node, choice_id=choice), {})
    async def run():
        await route.start_story("first_delivery", route.StoryStartBody(), {})
        await db.story_arcs.delete_many({})
        await choose("hello", "organise")
        assert (await route.get_state({}))["cash"] == 980
        with pytest.raises(HTTPException):
            await choose("hello", "organise")
        await choose("partner", "hire")
        await choose("promise", "honest")
        result = await choose("finish", "capital")
        assert result["completed"]
        assert (await route.get_state({}))["cash"] == 1075
        with pytest.raises(HTTPException):
            await choose("finish", "capital")
        view = await route.journey_view({})
        assert view["stories"][0]["completed"]
        assert len(view["stories"][0]["history"]) == 4
    asyncio.run(run())


def test_relative_progress_only_counts_new_actions(world):
    route, db, _ = world
    async def run():
        await db.players.update_one({"user_id": "u"}, {"$set": {"stats_meta.actions_done": 40}})
        await route.start_story("first_delivery", route.StoryStartBody(), {})
        await route.story_choice("first_delivery", route.StoryChoiceBody(node_id="hello", choice_id="hands"), {})
        body = route.StoryChoiceBody(node_id="prove", choice_id="done")
        with pytest.raises(HTTPException):
            await route.story_choice("first_delivery", body, {})
        await db.players.update_one({"user_id": "u"}, {"$inc": {"stats_meta.actions_done": 1}})
        await route.story_choice("first_delivery", body, {})
        assert (await route.journey_view({}))["stories"][0]["node"]["id"] == "route"
    asyncio.run(run())


def test_city_offer_acceptance_limit_and_no_expiry_after_start(world, monkeypatch):
    route, db, cfg = world
    async def run():
        cfg["journey"]["max_active_stories"] = 1
        rid = (await route.start_story("street_festival_order", route.StoryStartBody(event_id="street_festival"), {}))["run_id"]
        with pytest.raises(HTTPException):
            await route.start_story("first_delivery", route.StoryStartBody(), {})
        future = je.now_utc() + timedelta(days=10)
        monkeypatch.setattr(je, "now_utc", lambda: future)
        await db.city_events.delete_many({})
        result = await route.story_choice(rid, route.StoryChoiceBody(node_id="plan", choice_id="help"), {})
        assert result["ok"]
    asyncio.run(run())


def test_event_only_story_cannot_be_started_without_live_event(world):
    route, db, cfg = world
    async def run():
        for event_id in (None, "wrong", "trade_fair"):
            with pytest.raises(HTTPException):
                await route.start_story("trade_fair_order", route.StoryStartBody(event_id=event_id), {})
        cfg["journey"]["city_events_enabled"] = False
        assert not (await route.journey_view({}))["city_events"]
    asyncio.run(run())


def test_owner_empty_collection_and_zero_reward_survive_seed():
    from mongomock_motor import AsyncMongoMockClient
    from seed_data import seed_content
    async def run():
        db = AsyncMongoMockClient().seed
        await seed_content(db)
        await db.city_events.delete_many({})
        await db.journey_goals.update_one({"id": "entrepreneur"}, {"$set": {"milestones.0.rewards.xp": 0}})
        await seed_content(db)
        assert await db.city_events.count_documents({}) == 0
        assert (await db.journey_goals.find_one({"id": "entrepreneur"}))["milestones"][0]["rewards"]["xp"] == 0
    asyncio.run(run())


def test_hospital_blocks_choice_but_does_not_remove_story(world):
    route, db, _ = world
    async def run():
        await route.start_story("first_delivery", route.StoryStartBody(), {})
        await db.players.update_one({"user_id": "u"}, {"$set": {"status": "hospital"}})
        view = await route.journey_view({})
        assert not view["stories"][0]["node"]["choices"][0]["available"]
        with pytest.raises(HTTPException):
            await route.story_choice("first_delivery", route.StoryChoiceBody(node_id="hello", choice_id="organise"), {})
        assert (await route.get_state({}))["cash"] == 1000
    asyncio.run(run())


def test_authenticated_parallel_choice_claims_are_serialized(world, monkeypatch):
    import core
    import server
    import httpx
    route, db, _ = world
    monkeypatch.setattr(core, "db", db)
    async def run():
        uid = (await db.users.insert_one({"email": "parallel@example.com", "role": "player"})).inserted_id
        token = core.create_access_token(str(uid), "parallel@example.com")
        await route.start_story("first_delivery", route.StoryStartBody(), {})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test",
                                    headers={"Authorization": "Bearer " + token}) as client:
            responses = await asyncio.gather(*[client.post("/api/journey/stories/first_delivery/choose",
                json={"node_id": "hello", "choice_id": "organise"}) for _ in range(8)])
        assert sorted(r.status_code for r in responses) == [200] + [409] * 7
        p = await route.get_state({})
        assert p["cash"] == 980
        assert len(p["journal"]["stories"]["first_delivery"]["history"]) == 1
    asyncio.run(run())
