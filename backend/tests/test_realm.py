"""Fantasy migration, Owner controls, faction progression and timed combat; isolated DB only."""
import asyncio
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest

os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:1")
os.environ.setdefault("DB_NAME", "realm_tests")
from mongomock_motor import AsyncMongoMockClient
from game_models import DEFAULT_CONFIG, new_player
from realm_content import FACTIONS, EXPEDITIONS, REALM_RANKS, COMBAT_ITEMS
import realm_engine as re
import game_engine as ge

NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)

def player():
    p = new_player("u", "Rowan", "drifter")
    p.update(created_at=NOW.isoformat(), health=100, hunger=10, cash=100, bank=0)
    return p

@pytest.mark.parametrize("kind,docs", [("factions", FACTIONS), ("expeditions", EXPEDITIONS), ("realm_ranks", REALM_RANKS)])
def test_defaults_validate(kind, docs):
    for d in docs:
        re.validate_definition(kind, d)

@pytest.mark.parametrize("patch", [{"gold": -1}, {"energy_cost": float("nan")}, {"faction_id": "$bad"}, {"supplies": {"protein_bar": 0.5}}, {"min_rank": 0.5}, {"duration_minutes": "fast"}])
def test_invalid_expeditons_rejected(patch):
    with pytest.raises(ValueError):
        re.validate_definition("expeditions", {**EXPEDITIONS[0], **patch})

def test_rank_requires_earned_service_and_real_days():
    p = player()
    p["faction"] = {"id": "crown", "joined_at": NOW.isoformat(), "renown": 1500, "service_hours": 180}
    assert re.service(p, FACTIONS[0], NOW)["rank_index"] == 0
    assert re.service(p, FACTIONS[0], NOW + timedelta(days=7))["rank_index"] == 1
    assert re.service(p, FACTIONS[0], NOW + timedelta(days=90))["rank_index"] == 4
    p["faction"]["service_hours"] = 0
    assert re.service(p, FACTIONS[0], NOW + timedelta(days=90))["rank_index"] == 0


def test_owner_validation_rejects_broken_shapes_without_breaking_story_lists():
    from config_schema import validate_content, validate_config
    validate_content({"id": "story", "requirements": [{"metric": "funds", "target": 20}]})
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg["realm"]["future"] = {"name": "A future expansion"}
    validate_config(cfg, DEFAULT_CONFIG)
    cfg["realm"]["tactics"]["new"] = None
    with pytest.raises(ValueError):
        validate_config(cfg, DEFAULT_CONFIG)
    f = {**FACTIONS[0], "ranks": ["broken"]}
    with pytest.raises(ValueError):
        re.validate_definition("factions", f)

def test_equipped_owned_gear_and_zero_owner_stats():
    async def run():
        db = AsyncMongoMockClient().realm
        await db.items.insert_many(deepcopy(COMBAT_ITEMS))
        p = player()
        p["inventory"] = {"rustic_spear": 1, "mail_hauberk": 1}
        p["equipment"] = {"weapon": "rustic_spear", "armor": "mail_hauberk", "outfit": "rustic_spear"}
        stats = await re.combat_stats(db, p, DEFAULT_CONFIG)
        assert stats == {"power": 18, "armor": 6, "gear": ["Ashwood Spear", "Riveted Mail"]}
        await db.items.update_one({"id": "rustic_spear"}, {"$set": {"combat_power": 0}})
        p["inventory"]["mail_hauberk"] = 0
        changed = await re.combat_stats(db, p, DEFAULT_CONFIG)
        assert changed["power"] == 10 and changed["armor"] == 0
    asyncio.run(run())

@pytest.mark.parametrize("scale", [1, 12])
@pytest.mark.parametrize("won", [True, False])
def test_expedition_once_offline_equals_polling_including_hospital(scale, won):
    async def run():
        cfg = deepcopy(DEFAULT_CONFIG)
        cfg["time_scale"] = scale
        cfg["hospital"]["duration_minutes"] = 60
        db = AsyncMongoMockClient().realm
        p = player()
        p["faction"] = {"id": "crown", "joined_at": NOW.isoformat(), "renown": 0, "service_hours": 0}
        mission = {**EXPEDITIONS[2], "win_damage": 110, "loss_damage": 120, "supplies": {"protein_bar": 1}}
        snapshot = re.prepare(p, mission, "balanced", cfg, {"power": 10, "armor": 0}, NOW, SimpleNamespace(random=lambda: 0 if won else 1))
        end = NOW + timedelta(seconds=ge.real_seconds(mission["duration_minutes"], scale))
        p["current_activity"] = {"kind": "expedition", "started_at": NOW.isoformat(), "ends_at": end.isoformat(), "payload": snapshot}
        p["status"] = "busy"
        offline, online = deepcopy(p), deepcopy(p)
        final = NOW + timedelta(seconds=ge.real_seconds(180, scale))
        await ge.advance_player_time(db, offline, cfg, NOW, final)
        cursor = NOW
        for i in range(1, 37):
            tick = NOW + timedelta(seconds=ge.real_seconds(i * 5, scale))
            await ge.advance_player_time(db, online, cfg, cursor, tick)
            cursor = tick
        for key in ("health", "hunger", "energy", "fatigue", "stress", "cash", "xp"):
            assert online[key] == pytest.approx(offline[key]), key
        assert len(offline["battle_reports"]) == 1
        assert offline["current_activity"] is None
        assert offline["status"] == "free"
        assert offline["faction"]["service_hours"] == 1
        assert offline["faction"]["renown"] == (12 if won else 0)
        assert offline["inventory"]["protein_bar"] == 2
        await ge.advance_player_time(db, offline, cfg, final, final)
        assert len(offline["battle_reports"]) == 1
    asyncio.run(run())

def test_departure_snapshots_owner_rules_and_cancel_keeps_cooldown():
    p = player()
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg["realm"]["tactics"]["balanced"]["reward_multiplier"] = 0
    cfg["realm"]["tactics"]["balanced"]["damage_multiplier"] = 0
    mission = deepcopy(EXPEDITIONS[0])
    prepared = re.prepare(p, mission, "balanced", cfg, {"power": 10, "armor": 0}, NOW, SimpleNamespace(random=lambda: 0))
    mission["gold"] = 9999
    cfg["realm"]["tactics"]["balanced"]["reward_multiplier"] = 10
    assert prepared["gold"] == 0 and prepared["damage"] == 0
    assert prepared["mission"]["gold"] == 2
    assert "Restocking" in re.mission_reason(p, mission, None, NOW)

def test_disabled_faction_and_missing_supplies_block():
    p = player()
    m = deepcopy(EXPEDITIONS[3])
    f = {"id": "crown", "rank_index": 1, "active": False}
    assert "not currently" in re.mission_reason(p, m, f, NOW)
    f["active"] = True
    p["inventory"] = {}
    assert "supplies" in re.mission_reason(p, m, f, NOW)
    p["registered_shift"] = {"start_real": NOW.isoformat()}
    assert "reserved" in re.mission_reason(p, m, f, NOW)

def test_theme_migration_preserves_owner_edits_and_deletions():
    from seed_data import seed_content, LEGACY_DEFAULTS, CONTENT_MAP
    async def run():
        db = AsyncMongoMockClient().migration
        await db.config.insert_one(deepcopy(DEFAULT_CONFIG))
        custom = deepcopy(LEGACY_DEFAULTS["jobs"][0])
        custom.update(hourly_wage=0, shift_options=[], description="Owner's custom field work")
        await db.jobs.insert_one(custom)
        await db.items.insert_one(deepcopy(LEGACY_DEFAULTS["items"][0]))
        await seed_content(db)
        job = await db.jobs.find_one({"id": "cleaner"})
        assert job["title"] == "Farmhand" and job["hourly_wage"] == 0
        assert job["shift_options"] == [] and job["description"] == "Owner's custom field work"
        assert await db.jobs.count_documents({}) == 1
        assert await db.housing.count_documents({}) == 0
        assert (await db.items.find_one({"id": "energy_drink"}))["name"] == "Emberroot Tonic"
        await db.factions.delete_many({})
        await db.items.delete_one({"id": "rustic_spear"})
        await seed_content(db)
        assert await db.factions.count_documents({}) == 0
        assert await db.items.find_one({"id": "rustic_spear"}) is None
        assert await db.realm_backups.count_documents({}) > 0
    asyncio.run(run())

def test_new_realm_has_one_peasant_origin_and_all_equipment_in_shop():
    from seed_data import seed_content
    async def run():
        db = AsyncMongoMockClient().fresh
        await seed_content(db)
        origins = await db.character_backgrounds.find({"active": True}).to_list(100)
        assert len(origins) == 1 and origins[0]["label"] == "Unemployed Peasant"
        p = new_player("u", "P", origins[0]["id"], origins[0])
        assert p["job"] is None and p["cash"] == 80 and p["bank"] == 0
        assert all(s["level"] == 1 for s in p["skills"].values())
        shop = await db.city_shops.find_one({"id": "shop_hardware"})
        assert {i["id"] for i in COMBAT_ITEMS} <= set(shop["items_config"])
    asyncio.run(run())


def test_legacy_startup_helpers_do_not_restore_deleted_catalogues(monkeypatch):
    import server
    from seed_data import seed_content
    db = AsyncMongoMockClient().empty_catalogues
    monkeypatch.setattr(server, "db", db)
    async def run():
        await seed_content(db)
        await db.job_sectors.delete_many({})
        await db.vehicle_categories.delete_many({})
        await seed_content(db)
        await server.migrate_job_sectors()
        await server.migrate_vehicle_categories()
        assert await db.job_sectors.count_documents({}) == 0
        assert await db.vehicle_categories.count_documents({}) == 0
    asyncio.run(run())


def test_character_creation_requires_an_active_owner_origin(monkeypatch):
    import core
    import routes.player as route
    from seed_data import seed_content
    from fastapi import HTTPException
    db = AsyncMongoMockClient().character_creation
    monkeypatch.setattr(route, "db", db)
    async def run():
        await seed_content(db)
        with pytest.raises(HTTPException) as blocked:
            await route.create_character(core.CharacterBody(name="Test Peasant", background="graduate"), {"id": "test-character"})
        assert blocked.value.status_code == 400
        assert await db.players.count_documents({}) == 0
        await route.create_character(core.CharacterBody(name="Test Peasant", background="drifter"), {"id": "test-character"})
        p = await db.players.find_one({"user_id": "test-character"})
        assert p["cash"] == 80 and p["bank"] == 0 and p["job"] is None
        assert p["inventory"] == {"protein_bar": 3}
        await db.character_backgrounds.update_many({}, {"$set": {"active": False}})
        assert await route.list_backgrounds() == []
    asyncio.run(run())

def test_authenticated_concurrent_departures_cannot_double_spend(monkeypatch):
    import httpx
    import core
    import server
    import routes.realm as route
    db = AsyncMongoMockClient().requests
    for module in (core, route):
        monkeypatch.setattr(module, "db", db)
    async def state(user):
        return await db.players.find_one({"user_id": user["id"]}, {"_id": 0})
    monkeypatch.setattr(route, "get_state", state)
    async def run():
        uid = (await db.users.insert_one({"email": "test@realm.local", "role": "player"})).inserted_id
        p = player()
        p["user_id"] = str(uid)
        await db.players.insert_one(p)
        await db.expeditions.insert_one(deepcopy(EXPEDITIONS[0]))
        await db.config.insert_one(deepcopy(DEFAULT_CONFIG))
        token = core.create_access_token(str(uid), "test@realm.local")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test", headers={"Authorization": "Bearer " + token}) as client:
            responses = await asyncio.gather(*[client.post("/api/realm/expeditions/yard_drill/start", json={"tactic": "balanced"}) for _ in range(6)])
        assert sorted(r.status_code for r in responses) == [200] + [409] * 5
        updated = await db.players.find_one({"user_id": str(uid)})
        assert updated["energy"] == 92
        assert updated["current_activity"]["kind"] == "expedition"
    asyncio.run(run())
