"""Local-only route checks for asset preservation and owner settings."""
import asyncio
from copy import deepcopy
from pathlib import Path
import os
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017")
os.environ.setdefault("DB_NAME", "kaeldor_isolated_tests")

from game_models import new_player, DEFAULT_CONFIG
from fastapi import HTTPException


@pytest.fixture
def route_world(monkeypatch):
    from mongomock_motor import AsyncMongoMockClient
    import core
    import server
    import routes.economy as economy
    import routes.business as business
    db = AsyncMongoMockClient().kaeldor_isolated_tests
    p = new_player("u", "Tester", "drifter")
    p.update(cash=900.0, bank=0.0)
    cfg = deepcopy(DEFAULT_CONFIG)
    async def state(user):
        return p
    async def config(_db):
        return cfg
    async def noop(*args, **kwargs):
        return None
    for module in (core, server, economy, business):
        monkeypatch.setattr(module, "db", db)
    for module in (economy, business):
        monkeypatch.setattr(module, "get_state", state)
        monkeypatch.setattr(module, "get_config", config)
        monkeypatch.setattr(module, "save_player", noop)
        monkeypatch.setattr(module, "add_event", noop)
    monkeypatch.setattr(economy.social_engine, "ensure_landlord", noop)
    return db, p, cfg


def test_changing_home_cannot_silently_destroy_owned_property(route_world):
    import routes.economy as economy
    db, p, _ = route_world
    async def run():
        await db.housing.insert_one({"id": "new", "name": "New Home", "buy_price": 500, "deposit": 50})
        p["housing"] = {"id": "owned", "owned": True}
        for fn in (economy.rent_house, economy.buy_house):
            with pytest.raises(HTTPException) as error:
                await fn("new", {"id": "u"})
            assert error.value.status_code == 409
            assert p["housing"]["id"] == "owned" and p["cash"] == 900
    asyncio.run(run())


def test_rental_deposit_counts_toward_home_purchase(route_world):
    import routes.economy as economy
    db, p, _ = route_world
    async def run():
        await db.housing.insert_one({"id": "new", "name": "New Home", "buy_price": 1000, "social_status": 0})
        p["housing"] = {"id": "rental", "owned": False, "deposit_paid": 100}
        result = await economy.buy_house("new", {"id": "u"})
        assert result["refunded"] == 100
        assert p["cash"] == p["bank"] == p["debt"] == 0
        assert p["housing"]["owned"] is True
    asyncio.run(run())


def test_sell_business_rejects_orphaning_player_workers(route_world, monkeypatch):
    import routes.business as business
    db, p, _ = route_world
    b = {"id": "b", "name": "Business", "purchase_price": 1000, "level": 1, "reputation": 50}
    async def owned(player, bid):
        return b
    monkeypatch.setattr(business, "_get_owned_business", owned)
    async def run():
        await db.businesses.insert_one(dict(b))
        await db.player_employment.insert_one({"id": "e", "business_id": "b", "status": "active"})
        with pytest.raises(HTTPException) as error:
            await business.sell_business("b", {"id": "u"})
        assert error.value.status_code == 409
        assert await db.businesses.find_one({"id": "b"})
        assert p["cash"] == 900
        await db.player_employment.update_one({"id": "e"}, {"$set": {"status": "fired"}})
        await db.employees.insert_one({"id": "npc", "business_id": "b", "status": "active"})
        await db.business_applications.insert_one({"id": "offer", "business_id": "b", "status": "offered"})
        await business.sell_business("b", {"id": "u"})
        assert (await db.employees.find_one({"id": "npc"}))["status"] == "fired"
        assert (await db.business_applications.find_one({"id": "offer"}))["status"] == "rejected"
    asyncio.run(run())


def test_startup_preserves_existing_owner_password(route_world, monkeypatch):
    import server
    db, _, _ = route_world
    async def noop(*args, **kwargs):
        return None
    for name in ("seed_content", "seed_demo_players", "migrate_hours_based_promotions",
                 "migrate_player_employment_hourly", "migrate_business_supply_chain", "migrate_city_shops",
                 "migrate_job_sectors", "migrate_job_shift_options", "migrate_vehicle_categories", "migrate_job_visibility"):
        monkeypatch.setattr(server, name, noop)
    monkeypatch.setenv("ADMIN_EMAIL", "owner@test.local")
    monkeypatch.setenv("ADMIN_PASSWORD", "bootstrap-default-must-not-replace-custom-password")
    async def run():
        await db.users.insert_one({"email": "owner@test.local", "role": "admin", "password_hash": "custom-hash"})
        await server.startup()
        assert (await db.users.find_one({"email": "owner@test.local"}))["password_hash"] == "custom-hash"
    asyncio.run(run())


@pytest.mark.parametrize("ordinary_account", [False, True])
def test_startup_has_no_default_owner_password_or_silent_promotion(route_world, monkeypatch, ordinary_account):
    import server
    db, _, _ = route_world
    async def noop(*args, **kwargs):
        return None
    for name in ("seed_content", "seed_demo_players", "migrate_hours_based_promotions",
                 "migrate_player_employment_hourly", "migrate_business_supply_chain", "migrate_city_shops",
                 "migrate_job_sectors", "migrate_job_shift_options", "migrate_vehicle_categories", "migrate_job_visibility"):
        monkeypatch.setattr(server, name, noop)
    monkeypatch.setenv("ADMIN_EMAIL", "owner@test.local")
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    async def run():
        if ordinary_account:
            await db.users.insert_one({"email": "owner@test.local", "role": "player", "password_hash": "player-hash"})
            monkeypatch.setenv("ADMIN_PASSWORD", "explicit-bootstrap-password")
        await server.startup()
        account = await db.users.find_one({"email": "owner@test.local"})
        if ordinary_account:
            assert account["role"] == "player" and account["password_hash"] == "player-hash"
        else:
            assert account is None
    asyncio.run(run())
