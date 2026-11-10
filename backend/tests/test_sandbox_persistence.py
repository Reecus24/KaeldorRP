"""Offline regression tests. No real database, credentials or Emergent preview is contacted."""
import asyncio
from copy import deepcopy
from pathlib import Path
import os
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017")
os.environ.setdefault("DB_NAME", "kaeldor_isolated_tests")

from config_schema import merge_config, validate_config, validate_content, flatten_patch
from game_models import DEFAULT_CONFIG, new_player


def test_defaults_are_additive_and_preserve_zero_unknown_fields():
    original = deepcopy(DEFAULT_CONFIG)
    cfg = merge_config(DEFAULT_CONFIG, {"decay": {"hunger": 0}, "future": {"feature": {"rate": 0}}})
    assert cfg["decay"]["hunger"] == 0
    assert cfg["decay"]["energy_awake"] == DEFAULT_CONFIG["decay"]["energy_awake"]
    assert cfg["future"]["feature"]["rate"] == 0
    cfg["tuning"]["tax_brackets"][0][1] = 0
    assert DEFAULT_CONFIG == original
    assert flatten_patch({"future": {"feature": {"rate": 0}}}) == {"future.feature.rate": 0}


@pytest.mark.parametrize("patch", [
    {"time_scale": 0}, {"time_scale": -1}, {"time_scale": True},
    {"decay": None}, {"decay": {"hunger": -2}}, {"decay": {"hunger": "fast"}},
    {"future": {"rate": float("nan")}}, {"future": {"rate": float("inf")}},
    {"tuning": {"accident_chance": 2}},
    {"tuning": {"satisfaction_mult_min": 5, "satisfaction_mult_max": 1}},
    {"tuning": {"tax_brackets": [[100, .1], [50, .2]]}},
    {"tuning": {"tax_brackets": [[None, .1], [500, .2]]}},
    {"tuning": {"tax_brackets": [[100, "high"]]}},
    {"future.bad": 1}, {"future": {"$set": 1}},
    {"hospital": {"admission_health": 0}},
    {"hospital": {"admission_health": 40, "discharge_health": 20}},
    {"xp": {"skill_per_level": 0}}, {"xp": {"player_per_level": -1}},
])
def test_invalid_settings_rejected(patch):
    with pytest.raises(ValueError):
        validate_config(merge_config(DEFAULT_CONFIG, patch), DEFAULT_CONFIG)


def test_zero_rates_and_future_structured_content_remain_editable():
    cfg = merge_config(DEFAULT_CONFIG, {"decay": {"hunger": 0},
        "tuning": {"police_event_per_hour": 0},
        "future": {"enabled": False, "recipe": [{"amount": -1}]}})
    assert validate_config(cfg, DEFAULT_CONFIG) is cfg


@pytest.mark.parametrize("patch", [{"id": "bad.id"}, {"id": "$bad"}, {"id": []},
                                     {"id": "food", "price": -5}, {"id": "act", "duration_minutes": "soon"}])
def test_content_rejects_unsafe_identifiers_and_invalid_costs(patch):
    with pytest.raises(ValueError):
        validate_content(patch)


def test_content_allows_free_items_and_negative_effects():
    assert validate_content({"id": "meal", "price": 0, "effects": {"hunger": -40}, "future": {"buff": True}})


@pytest.fixture
def mock_db(monkeypatch):
    mock_motor = pytest.importorskip("mongomock_motor")
    db = mock_motor.AsyncMongoMockClient().kaeldor_isolated_tests
    import core
    import server
    import routes.admin as admin
    import routes.economy as economy
    for module in (core, server, admin, economy):
        monkeypatch.setattr(module, "db", db)
    return db


def test_admin_partial_edit_preserves_nested_siblings(mock_db, monkeypatch):
    import routes.admin as admin
    async def run():
        stored = merge_config(DEFAULT_CONFIG, {"future": {"feature": {"rate": 5, "cost": 12}}})
        await mock_db.config.insert_one(stored)
        await admin.admin_update_config({"future": {"feature": {"rate": 0}}}, admin={})
        result = await mock_db.config.find_one({"id": "global"})
        assert result["future"]["feature"] == {"rate": 0, "cost": 12}
    asyncio.run(run())


def test_duplicate_create_and_invalid_config_do_not_destroy_owner_data(mock_db):
    import routes.admin as admin
    from fastapi import HTTPException
    async def run():
        await mock_db.actions.insert_one({"id": "custom", "name": "Owner activity", "duration_minutes": 30})
        with pytest.raises(HTTPException) as error:
            await admin.admin_create("actions", {"id": "custom", "name": "Overwritten"}, admin={})
        assert error.value.status_code == 409
        assert (await mock_db.actions.find_one({"id": "custom"}))["name"] == "Owner activity"
        await mock_db.config.insert_one(deepcopy(DEFAULT_CONFIG))
        with pytest.raises(HTTPException) as error:
            await admin.admin_update_config({"time_scale": 0}, admin={})
        assert error.value.status_code == 422
        assert (await mock_db.config.find_one({"id": "global"}))["time_scale"] == DEFAULT_CONFIG["time_scale"]
    asyncio.run(run())


def test_restart_keeps_owner_business_job_and_clock_edits(mock_db):
    import server
    from seed_data import CONTENT_MAP
    async def run():
        definition = deepcopy(CONTENT_MAP["business_types"][1][0])
        definition.update(product={"id": "custom_product", "price": 123}, recipe=[], daily_demand=0,
                          production_per_worker_hour=0, opening_hours={"open": "11:00", "close": "13:00"})
        await mock_db.business_types.insert_one(deepcopy(definition))
        business = {"id": "owned", "type_id": definition["id"], "product": {"price": 456},
                    "recipe": [], "daily_demand": 0, "production_per_worker_hour": 0,
                    "opening_hours": {"open": "15:00", "close": "16:00"},
                    "satisfaction": 12, "materials": {}, "products": 0, "cash": 77}
        await mock_db.businesses.insert_one(deepcopy(business))
        job_id = CONTENT_MAP["jobs"][1][0]["id"]
        await mock_db.jobs.insert_one({"id": job_id, "requirements": {}, "shift_options": []})
        schedule = {"start": 12, "end": 13}
        await mock_db.employees.insert_one({"id": "worker", "business_id": "owned", "status": "active", "schedule": schedule})
        await mock_db.config.insert_one({"id": "global", "time_scale": 12,
            "world_start_real": "2026-01-01T00:00:00+00:00", "world_start_game": "2030-01-01T00:00:00+00:00"})
        for _ in range(2):
            await server.migrate_business_supply_chain()
            await server.migrate_job_shift_options()
        result = await mock_db.businesses.find_one({"id": "owned"})
        assert {key: result[key] for key in business} == business
        saved_definition = await mock_db.business_types.find_one({"id": definition["id"]})
        assert {key: saved_definition[key] for key in definition} == definition
        job = await mock_db.jobs.find_one({"id": job_id})
        assert job["requirements"] == {} and job["shift_options"] == []
        assert (await mock_db.employees.find_one({"id": "worker"}))["schedule"] == schedule
        cfg = await mock_db.config.find_one({"id": "global"})
        assert cfg["time_scale"] == 12 and cfg["world_start_game"].startswith("2030-")
    asyncio.run(run())


def test_legacy_business_backfills_from_owner_definition_not_seed(mock_db):
    import server
    async def run():
        await mock_db.business_types.insert_one({"id": "custom", "product": {"price": 99},
            "recipe": [], "daily_demand": 3, "production_per_worker_hour": 7})
        await mock_db.businesses.insert_one({"id": "legacy", "type_id": "custom", "cash": 42})
        await server.migrate_business_supply_chain()
        b = await mock_db.businesses.find_one({"id": "legacy"})
        assert b["product"]["price"] == 99 and b["daily_demand"] == 3 and b["cash"] == 42
        assert b["recipe"] == []
    asyncio.run(run())


def test_promotion_migration_retains_custom_gates(mock_db):
    import server
    from seed_data import CONTENT_MAP
    async def run():
        job_id = CONTENT_MAP["jobs"][1][0]["id"]
        await mock_db.jobs.insert_one({"id": job_id, "promotion_req": {"shifts": 8, "min_reputation": 91}})
        await server.migrate_hours_based_promotions()
        req = (await mock_db.jobs.find_one({"id": job_id}))["promotion_req"]
        assert req == {"hours": 40, "min_reputation": 91}
    asyncio.run(run())


def test_last_shop_item_cannot_be_sold_twice(mock_db, monkeypatch):
    import routes.economy as economy
    from core import BuyBody
    from fastapi import HTTPException
    saved = []
    async def state(user):
        p = new_player(user["id"], user["id"], "drifter")
        p["cash"] = 100
        return p
    async def config(_db):
        return deepcopy(DEFAULT_CONFIG)
    async def noop(*args, **kwargs):
        return None
    async def save(p):
        saved.append(deepcopy(p))
    monkeypatch.setattr(economy, "get_state", state)
    monkeypatch.setattr(economy, "get_config", config)
    monkeypatch.setattr(economy, "_resolve_shop_stock", noop)
    monkeypatch.setattr(economy, "add_event", noop)
    monkeypatch.setattr(economy, "save_player", save)
    async def run():
        await mock_db.items.insert_one({"id": "food", "name": "Food", "price": 5, "store_type": "grocery"})
        await mock_db.city_shops.insert_one({"id": "shop", "name": "Shop", "active": True,
            "category": "grocery", "item_ids": ["food"], "stock": {"food": 1},
            "opening_hours": {"open": "00:00", "close": "24:00"}})
        results = await asyncio.gather(
            economy.shop_buy(BuyBody(item_id="food", store_id="shop"), {"id": "one"}),
            economy.shop_buy(BuyBody(item_id="food", store_id="shop"), {"id": "two"}), return_exceptions=True)
        assert sum(isinstance(r, dict) and r.get("ok") for r in results) == 1
        assert sum(isinstance(r, HTTPException) for r in results) == 1
        assert (await mock_db.city_shops.find_one({"id": "shop"}))["stock"]["food"] == 0
        assert len(saved) == 1 and saved[0]["cash"] == 95
        with pytest.raises(HTTPException) as error:
            await economy.shop_buy(BuyBody(item_id="food", store_id="nonexistent"), {"id": "one"})
        assert error.value.status_code == 404
    asyncio.run(run())


def test_owner_edits_apply_after_old_offline_progress(mock_db, monkeypatch):
    import routes.admin as admin
    from core import AdminPlayerBody
    old = "2026-01-01T00:00:00+00:00"
    edited_at = "2026-01-02T00:00:00+00:00"
    seen = []
    async def resolve(_db, p):
        seen.append(p["hunger"])
        p.update(hunger=100, cash=101, last_resolved_at=edited_at)
        return p
    async def net_worth(p):
        return p["cash"] + p["bank"] - p["debt"]
    monkeypatch.setattr(admin, "resolve_player", resolve)
    monkeypatch.setattr(admin, "compute_net_worth", net_worth)
    async def run():
        p = new_player("u", "Owner Test", "drifter")
        p.update(hunger=90, last_resolved_at=old)
        await mock_db.players.insert_one(dict(p))
        await admin.admin_update_player(p["id"], AdminPlayerBody(hunger=0), admin={})
        saved = await mock_db.players.find_one({"id": p["id"]})
        assert seen == [90]  # old needs are resolved before the override
        assert saved["hunger"] == 0 and saved["last_resolved_at"] == edited_at
        assert saved["cash"] == 101  # unrelated earned progress also survives the edit
    asyncio.run(run())


def test_losing_stock_refresh_updates_callers_snapshot_without_restocking(mock_db, monkeypatch):
    import core
    monkeypatch.setattr(core, "game_day_index", lambda cfg, *args: 3)
    async def run():
        old = {"id": "shop", "category": "food", "item_ids": ["meal"],
               "stock": {"meal": 5}, "last_refresh_day": 2}
        await mock_db.items.insert_one({"id": "meal", "name": "Meal", "store_type": "food"})
        # Another player already refreshed day 3 and bought the last item.
        await mock_db.city_shops.insert_one({**old, "stock": {"meal": 0}, "last_refresh_day": 3})
        await core._resolve_shop_stock(old, deepcopy(DEFAULT_CONFIG))
        assert old["stock"]["meal"] == 0 and old["last_refresh_day"] == 3
        assert (await mock_db.city_shops.find_one({"id": "shop"}))["stock"]["meal"] == 0
    asyncio.run(run())
