"""Pure API guard/model checks, with Mongo replaced before importing core."""
import asyncio
from datetime import datetime, timedelta, timezone
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mongomock_motor import AsyncMongoMockClient
from pydantic import ValidationError

import game_engine
from game_models import new_player


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def core(monkeypatch):
    import motor.motor_asyncio
    monkeypatch.setenv("MONGO_URL", "mongodb://127.0.0.1:1/isolated-test")
    monkeypatch.setenv("DB_NAME", "isolated_test")
    monkeypatch.setattr(motor.motor_asyncio, "AsyncIOMotorClient", AsyncMongoMockClient)
    return importlib.import_module("core")


@pytest.mark.parametrize("change,expected", [
    ({"status": "hospital"}, "infirmary"),
    ({"status": "jail"}, "dungeon"),
    ({"on_shift": {"business_name": "Store"}}, "shift"),
    ({"current_activity": {"kind": "action"}}, "busy"),
    ({"cash": 2, "bank": 2}, "money"),
    ({"cooldowns": {"meal": (NOW + timedelta(seconds=1)).isoformat()}}, "cooldown"),
])
def test_unavailable_actions_report_server_block_reason(core, change, expected):
    p = new_player("u", "Test", "drifter")
    p.update(change)
    assert expected in core.action_unavailable_reason(p, {"id": "meal", "money_cost": 5}, now=NOW).lower()


def test_cooldown_boundary_and_combined_cash_bank_are_available(core):
    p = new_player("u", "Test", "drifter")
    p.update(cash=2, bank=3, cooldowns={"meal": NOW.isoformat()})
    assert core.action_unavailable_reason(p, {"id": "meal", "money_cost": 5}, now=NOW) == ""


def test_unmet_requirement_is_not_advertised_as_available(core):
    p = new_player("u", "Test", "drifter")
    action = {"id": "workout", "requirements": {"skills": {"fitness": 99}}}
    assert core.action_unavailable_reason(p, action, now=NOW)


@pytest.mark.parametrize("model,field", [
    ("AmountBody", "amount"), ("TradeBody", "qty"),
    ("AdminPlayerBody", "health"), ("WageBody", "wage_per_hour"),
])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_values_are_rejected_before_gameplay_writes(core, model, field, value):
    body = {field: value}
    if model == "TradeBody":
        body["asset_id"] = "test-stock"
    with pytest.raises(ValidationError) as error:
        getattr(core, model)(**body)
    assert any(e["loc"] == (field,) for e in error.value.errors())


@pytest.mark.parametrize("value", [0, -1])
def test_money_movements_require_positive_amount(core, value):
    with pytest.raises(ValidationError):
        core.AmountBody(amount=value)


@pytest.mark.parametrize("value", [-1, 101])
def test_owner_hunger_editor_rejects_out_of_range_values(core, value):
    with pytest.raises(ValidationError):
        core.AdminPlayerBody(hunger=value)


def test_partial_persisted_config_keeps_new_defaults_and_valid_zero():
    db = SimpleNamespace(config=SimpleNamespace(find_one=AsyncMock(return_value={
        "id": "global", "time_scale": 12,
        "needs": {"health_regen_per_hour": 0}, "hospital": {"duration_minutes": 120},
    })))
    config = asyncio.run(game_engine.get_config(db))
    assert config["needs"]["health_regen_per_hour"] == 0
    assert config["needs"]["hunger_damage_threshold"] == 80
    assert config["hospital"]["duration_minutes"] == 120
    assert config["hospital"]["discharge_health"] == 60
