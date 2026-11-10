import asyncio
from copy import deepcopy
import pytest
from business_comfort import operations, restock_quote, material_multiplier
from employee_engine import _auto_restock, _day_rates
from game_models import DEFAULT_CONFIG


def business():
    return {"id": "b", "cash": 1000, "debt": 20, "daily_demand": 100, "restock_target": 100,
            "recipe": [{"id": "a", "name": "A", "qty": 1, "cost": 2}, {"id": "b", "name": "B", "qty": 1, "cost": 3}],
            "materials": {}}


def test_reserve_is_same_amount_for_display_and_collect():
    b = business()
    m = {"material_day": 100, "wage_per_day": 80, "sold_day": 20, "staff_count": 2,
         "coverage_hours_pct": 100, "materials": [{"stock": 60, "qty": 1}]}
    op = operations(b, m, DEFAULT_CONFIG)
    assert op["reserve"] == 200 and op["safe_to_collect"] == 800
    assert op["stock_days"] == 3
    b["reserve_days"] = 0
    assert operations(b, m, DEFAULT_CONFIG)["safe_to_collect"] == 980
    b["cash"] = 5
    assert operations(b, m, DEFAULT_CONFIG)["safe_to_collect"] == 0


def test_nondefault_owner_reserve_and_warning_values():
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg["business_comfort"].update(default_reserve_days=2.5, stock_warning_days=0)
    m = {"wage_per_day": 20, "material_day": 20, "sold_day": 10, "staff_count": 1, "coverage_hours_pct": 100}
    op = operations(business(), m, cfg)
    assert op["reserve"] == 120
    assert not any(a["title"] == "Check your supplies" for a in op["alerts"])


def test_quote_applies_discount_and_splits_wallet_sources():
    b = business()
    b["cash"] = 10
    b["materials"] = {"a": 5}
    q = restock_quote(b, 10, material_multiplier({"social_perks": {"material_discount": 0.2}}))
    assert q["cost"] == 32 and q["from_business"] == 10 and q["from_owner"] == 22
    assert q["materials"] == {"a": 10, "b": 10}
    assert restock_quote(b, 0)["cost"] == 0


def test_auto_restock_balances_recipe_and_preserves_wages():
    b = business()
    b["cash"] = 60
    spent = _auto_restock(b, 100, None, cash_floor=10)
    assert spent == pytest.approx(50, abs=0.01)
    assert b["cash"] >= 10
    assert b["materials"]["a"] == pytest.approx(10, abs=0.001)
    assert b["materials"]["b"] == pytest.approx(10, abs=0.001)


def test_free_materials_and_zero_stock_target_are_supported():
    b = business()
    b.update(cash=0, restock_target=0)
    b["recipe"][0]["cost"] = b["recipe"][1]["cost"] = 0
    assert _auto_restock(b, 5, None) == 0
    assert b["materials"] == {"a": 5, "b": 5}
    b["materials"] = {}
    _auto_restock(b, 0, None)
    assert b["materials"] == {}


def test_social_wage_discount_never_reduces_player_employee_forecast():
    # The forecast uses the same contracted hourly rate as the actual player payroll.
    worker = {"wage_per_hour": 10, "schedule": {"start": 8, "end": 16}, "is_player": True}
    b = {"opening_hours": {"open": "08:00", "close": "20:00"}, "production_per_worker_hour": 0}
    baseline = _day_rates(b, [worker], wage_mult=1)["wages_day"]
    assert baseline == 80
    assert _day_rates(b, [worker], wage_mult=0.8)["wages_day"] == baseline


def test_owner_and_employee_operations_cannot_overwrite_each_others_business_cash():
    from mongomock_motor import AsyncMongoMockClient
    from player_lock import business_operations
    async def run():
        db = AsyncMongoMockClient().locks
        await db.players.insert_many([{"id": "p1", "user_id": "u1"}, {"id": "p2", "user_id": "u2"}])
        await db.businesses.insert_one({"id": "shop", "player_id": "p1", "cash": 0})
        await db.player_employment.insert_one({"business_id": "shop", "employee_player_id": "p2", "status": "active"})
        async def mutate(uid):
            async with business_operations(db, uid):
                b = await db.businesses.find_one({"id": "shop"})
                await asyncio.sleep(0.02)
                await db.businesses.update_one({"id": "shop"}, {"$set": {"cash": b["cash"] + 1}})
        await asyncio.gather(mutate("u1"), mutate("u2"))
        assert (await db.businesses.find_one({"id": "shop"}))["cash"] == 2
        assert await db.player_operation_locks.count_documents({}) == 0
    asyncio.run(run())


def test_finished_stock_buffer_prevents_continued_overproduction(monkeypatch):
    from datetime import datetime, timezone, timedelta
    from mongomock_motor import AsyncMongoMockClient
    import employee_engine as ee
    async def run():
        db = AsyncMongoMockClient().production
        now = datetime(2050, 1, 1, 12, tzinfo=timezone.utc)
        cfg = deepcopy(DEFAULT_CONFIG)
        cfg.update(world_start_real=now.isoformat(), world_start_game=now.isoformat())
        cfg["business_comfort"]["finished_stock_days"] = 0
        b = business()
        b.update(player_id="p", name="Shop", type_id="kiosk", level=1, max_level=5,
                 product={"price": 10},
                 products=1000, daily_demand=100, satisfaction=100, reputation=100,
                 production_per_worker_hour=100, opening_hours={"open": "08:00", "close": "20:00"},
                 last_resolved_at=(now - timedelta(hours=1)).isoformat())
        async def workers(*args):
            return [{"schedule": {"start": 8, "end": 20}, "wage_per_hour": 0,
                     "clocked_out_until": None, "productivity": 1, "is_player": False}]
        async def noop(*args, **kwargs):
            pass
        monkeypatch.setattr(ee, "gather_workers", workers)
        monkeypatch.setattr(ee, "_npc_lifecycle", noop)
        await db.businesses.insert_one(deepcopy(b))
        await ee.resolve_business(db, cfg, now, b)
        assert not b["materials"]
        assert b["products"] < 1000
        assert b["history"][-1]["produced"] == 0
    asyncio.run(run())
