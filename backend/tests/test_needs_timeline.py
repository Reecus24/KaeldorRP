"""Offline regressions for needs and activity/confinement deadlines.

All tests use a synthetic clock and an in-memory database. No app startup,
credentials, external service, or live database is needed.
Run from the repository: PYTHONPATH=backend python -m pytest backend/tests/test_needs_timeline.py
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import game_engine as ge
import game_models
import employment
import social_engine


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
NEEDS = ("energy", "fatigue", "hunger", "mood", "stress", "health")


class Collection:
    def __init__(self, document=None):
        self.document = document
        self.rows = []

    async def find_one(self, *args, **kwargs):
        return deepcopy(self.document)

    async def insert_one(self, document):
        self.rows.append(deepcopy(document))

    def find(self, *args, **kwargs):
        return self

    async def to_list(self, *args, **kwargs):
        return deepcopy(self.rows)


class Timeline:
    def __init__(self, monkeypatch, scale):
        self.scale = scale
        self.now = START
        self.config = deepcopy(game_models.DEFAULT_CONFIG)
        self.config["time_scale"] = scale
        self.config.pop("world_start_real", None)
        self.config.pop("world_start_game", None)
        self.db = SimpleNamespace(
            config=Collection(self.config), housing=Collection(),
            events=Collection(), notifications=Collection(), random_events=Collection(),
        )
        monkeypatch.setattr(ge, "now_utc", lambda: self.now)
        monkeypatch.setattr(game_models, "now_utc", lambda: self.now)

        async def noop(*args, **kwargs):
            return None

        for name in ("accrue_recurring", "accrue_businesses", "maybe_police_event"):
            monkeypatch.setattr(ge, name, noop)
        monkeypatch.setattr(social_engine, "resolve_social", noop)
        for name in ("resolve_npc_applications", "resolve_worked_businesses", "sweep_player_earnings"):
            monkeypatch.setattr(employment, name, noop)
        # Random job events and incidental accidents must not obscure time accounting.
        monkeypatch.setattr(ge.random, "random", lambda: 1.0)

    def at(self, game_hours):
        return START + timedelta(seconds=game_hours * 3600 / self.scale)

    def player(self, **updates):
        p = game_models.new_player("offline-test-user", "Test Player", "drifter")
        p.update(housing={}, last_resolved_at=START.isoformat())
        p.update(updates)
        return p

    def resolve(self, p, game_hour):
        self.now = self.at(game_hour)
        return asyncio.run(ge.resolve_player(self.db, p))

    def activity(self, kind, start=0, end=1, payload=None, sleep=False):
        return {
            "kind": kind, "name": kind, "started_at": self.at(start).isoformat(),
            "ends_at": self.at(end).isoformat(), "blocking": True,
            "sleep_flag": sleep, "duration_minutes": (end - start) * 60,
            "payload": payload or {},
        }


@pytest.fixture(params=[1.0, 12.0], ids=["real-time", "12x"])
def timeline(monkeypatch, request):
    return Timeline(monkeypatch, request.param)


def assert_same_needs(a, b):
    for key in NEEDS:
        assert a[key] == pytest.approx(b[key], abs=1e-6), key


def test_existing_hospital_recovery_follows_its_saved_deadline(timeline):
    timeline.config["hospital"]["duration_minutes"] = 120
    p = timeline.player(health=1, status="hospital", hospital_until=timeline.at(6).isoformat())
    timeline.resolve(p, 3)
    assert p["health"] == pytest.approx(30.5)
    assert p["hospital_until"] == timeline.at(6).isoformat()


def test_datetime_parser_keeps_negative_timezone_offset():
    dt = ge.parse_dt("2026-01-01T05:00:00-05:00")
    assert dt.astimezone(timezone.utc).hour == 10


def test_hunger_threshold_only_damages_exposed_interval():
    p = game_models.new_player("u", "Threshold", "drifter")
    p.update(hunger=79, health=50, fatigue=0, stress=0, energy=100)
    cfg = deepcopy(game_models.DEFAULT_CONFIG)
    cfg["decay"].update(hunger=4, energy_awake=0, fatigue_awake=0, stress_relax=0)
    ge.decay_needs(p, 1, cfg, False)
    # First 15 minutes: +0.8 HP/hour. Remaining 45 minutes: -1.4 HP/hour.
    assert p["hunger"] == pytest.approx(83)
    assert p["health"] == pytest.approx(50 + 0.8 * 0.25 - 1.4 * 0.75, abs=1e-7)


def test_needs_independent_of_polling_interval():
    p = game_models.new_player("u", "Thresholds", "drifter")
    p.update(hunger=72, health=80, fatigue=76, stress=88, energy=22, mood=83)
    frequent = deepcopy(p)
    cfg = deepcopy(game_models.DEFAULT_CONFIG)
    ge.decay_needs(p, 8, cfg, False)
    for _ in range(480):
        ge.decay_needs(frequent, 1 / 60, cfg, False)
    assert_same_needs(p, frequent)


def test_owner_tuned_need_thresholds_and_rates_are_used():
    p = game_models.new_player("u", "Tuned needs", "drifter")
    p.update(hunger=49, health=50, fatigue=0, stress=0, energy=100)
    cfg = deepcopy(game_models.DEFAULT_CONFIG)
    cfg["decay"].update(hunger=4, energy_awake=0, fatigue_awake=0, stress_relax=0)
    cfg["needs"].update(hunger_damage_threshold=50, regen_max_hunger=50,
                        hunger_health_loss_per_hour=2, health_regen_per_hour=2.5)
    ge.decay_needs(p, 1, cfg, False)
    assert p["health"] == pytest.approx(50 + 2.5 * 0.25 - 2 * 0.75, abs=1e-7)


def test_zero_need_rates_disable_growth_and_regeneration():
    p = game_models.new_player("u", "Zero rates", "drifter")
    p.update(hunger=79, health=50, fatigue=0, stress=0, energy=100)
    cfg = deepcopy(game_models.DEFAULT_CONFIG)
    cfg["decay"].update(hunger=0, energy_awake=0, fatigue_awake=0, stress_relax=0)
    cfg["needs"]["health_regen_per_hour"] = 0
    ge.decay_needs(p, 24, cfg, False)
    assert p["hunger"] == 79
    assert p["health"] == 50
    assert p["energy"] == 100
    assert p["fatigue"] == 0


def test_meal_applies_before_subsequent_offline_hunger(timeline):
    p = timeline.player(hunger=95, health=100)
    p["current_activity"] = timeline.activity("action", end=8 / 60,
        payload={"name": "Meal", "effects": {"hunger": -45}})
    timeline.resolve(p, 12)
    # Hunger grows for all 12 hours; the meal happens after 8 minutes, before
    # hunger hits the cap. Applying the meal at login incorrectly produces 55.
    assert p["hunger"] == pytest.approx(95 + 12 * 3.2 - 45, abs=1e-7)
    assert p["current_activity"] is None
    assert p["stats_meta"]["actions_done"] == 1
    completed = next(e for e in timeline.db.events.rows if e["message"].startswith("Meal:"))
    assert ge.parse_dt(completed["ts"]) == timeline.at(8 / 60)
    asyncio.run(ge.add_event(timeline.db, p["id"], "Request-time event"))
    assert ge.parse_dt(timeline.db.events.rows[-1]["ts"]) == timeline.at(12)


def test_sleep_only_protects_its_actual_duration(timeline):
    p = timeline.player(energy=20, fatigue=70, hunger=10, health=70, stress=10)
    p["current_activity"] = timeline.activity("action", end=8, sleep=True, payload={
        "name": "Sleep", "sleep": True, "sleep_quality": 1,
        "effects": {"energy": 80, "fatigue": -70, "stress": -20, "hunger": 15, "health": 8},
    })
    timeline.resolve(p, 12)
    assert p["energy"] == pytest.approx(100 - 4 * 2.4)
    assert p["fatigue"] == pytest.approx(4 * 1.8)
    assert p["hunger"] == pytest.approx(10 + 12 * 3.2 + 15)
    assert p["stats_meta"]["actions_done"] == 1


def test_course_welfare_ends_at_graduation(timeline):
    p = timeline.player(hunger=65, fatigue=60, energy=25)
    p["current_activity"] = timeline.activity("course", end=2,
        payload={"course_id": "test-course", "title": "Test course", "grants_skills": {}})
    timeline.resolve(p, 10)
    assert p["hunger"] == pytest.approx(8 * 3.2)
    assert p["energy"] == pytest.approx(100 - 8 * 2.4)
    assert p["fatigue"] == pytest.approx(8 * 1.8)
    assert p["education"] == ["test-course"]
    assert p["stats_meta"]["courses_done"] == 1


@pytest.mark.parametrize("kind", ["meal", "sleep", "course"])
def test_activity_offline_and_frequent_resolution_agree(timeline, kind):
    p = timeline.player(hunger=75, health=65, fatigue=50, energy=40, stress=15)
    if kind == "course":
        act = timeline.activity("course", end=2,
            payload={"course_id": "c", "title": "Course", "grants_skills": {}})
    else:
        sleep = kind == "sleep"
        act = timeline.activity("action", end=2 if sleep else 0.25, sleep=sleep,
            payload={"name": kind, "sleep": sleep, "sleep_quality": 1,
                     "effects": {"energy": 50, "fatigue": -40} if sleep else {"hunger": -45}})
    p["current_activity"] = act
    frequent = deepcopy(p)
    timeline.resolve(p, 5)
    for minute in range(1, 301):
        timeline.resolve(frequent, minute / 60)
    assert_same_needs(p, frequent)
    assert p["stats_meta"] == frequent["stats_meta"]


def test_hospital_protects_needs_and_recovers_during_stay(timeline):
    p = timeline.player(status="hospital", hospital_until=timeline.at(6).isoformat(),
                        health=1, hunger=100, fatigue=100, energy=0, stress=95)
    initial_needs = {k: p[k] for k in NEEDS if k != "health"}
    timeline.resolve(p, 3)
    assert p["status"] == "hospital"
    assert p["health"] == pytest.approx(1 + 59 / 2)
    for key, value in initial_needs.items():
        assert p[key] == pytest.approx(value), key


def test_discharge_decays_only_time_after_hospital(timeline):
    p = timeline.player(status="hospital", hospital_until=timeline.at(6).isoformat(),
                        health=1, hunger=100, fatigue=100, energy=0, stress=0)
    timeline.resolve(p, 7)
    assert p["status"] == "free"
    assert p["hospital_until"] is None
    # Six hours under care restore 60 HP. Only the following idle hour incurs
    # starvation/fatigue damage (1.4 + 0.6 HP), not the whole seven-hour gap.
    assert p["health"] == pytest.approx(58, abs=1e-6)
    assert len([e for e in timeline.db.events.rows if "discharged" in e["message"]]) == 1


def test_hospital_offline_and_frequent_resolution_agree(timeline):
    p = timeline.player(status="hospital", hospital_until=timeline.at(6).isoformat(),
                        health=1, hunger=100, fatigue=100, energy=0, stress=0)
    frequent = deepcopy(p)
    timeline.resolve(p, 7)
    for minute in range(1, 421):
        timeline.resolve(frequent, minute / 60)
    assert_same_needs(p, frequent)
    assert p["status"] == frequent["status"] == "free"


def test_collapse_admission_starts_when_health_reaches_zero(timeline):
    p = timeline.player(hunger=100, health=1.4, fatigue=0, energy=100, stress=0)
    timeline.resolve(p, 2)
    # Starvation reaches 0 HP at hour one; by hour two one hour of the six-hour
    # admission has elapsed. Starting the timer at login would end at hour eight.
    assert p["status"] == "hospital"
    assert ge.parse_dt(p["hospital_until"]) == timeline.at(7)
    assert p["health"] == pytest.approx(1 + 59 / 6, abs=1e-6)


def test_owner_tuned_hospital_duration_and_recovery_target(timeline):
    timeline.config["hospital"] = {
        "duration_minutes": 120, "discharge_health": 80, "admission_health": 1,
    }
    p = timeline.player(hunger=100, health=1.4, fatigue=0, energy=100, stress=0)
    timeline.resolve(p, 1)
    assert p["status"] == "hospital"
    assert ge.parse_dt(p["hospital_until"]) == timeline.at(3)
    timeline.resolve(p, 2)
    assert p["health"] == pytest.approx(40.5, abs=1e-6)
    timeline.resolve(p, 3)
    assert p["status"] == "free"
    assert p["health"] == pytest.approx(80, abs=1e-6)


def test_finished_action_injury_triggers_hospital_immediately(timeline):
    p = timeline.player(health=5, hunger=20)
    p["current_activity"] = timeline.activity("action", end=1,
        payload={"name": "Injury", "effects": {"health": -10}})
    timeline.resolve(p, 1)
    assert p["stats_meta"]["actions_done"] == 1
    assert p["current_activity"] is None
    assert p["status"] == "hospital"
    assert ge.parse_dt(p["hospital_until"]) == timeline.at(7)


def test_finished_work_injury_triggers_hospital_immediately(timeline, monkeypatch):
    p = timeline.player(health=5, hunger=20)
    p["current_activity"] = timeline.activity("job", end=1, payload={
        "hours": 1, "hourly_wage": 10, "title": "Hazardous job", "category": "test",
        "fatigue_ph": 2, "stress_ph": 1, "energy_ph": 3, "skill_xp": {}, "injury_risk": 1,
    })
    monkeypatch.setattr(ge.random, "random", lambda: 0)
    monkeypatch.setattr(ge.random, "uniform", lambda a, b: 10)
    timeline.resolve(p, 1)
    assert p["stats_meta"]["shifts_worked"] == 1
    assert p["current_activity"] is None
    assert p["status"] == "hospital"
    assert ge.parse_dt(p["hospital_until"]) == timeline.at(7)


def test_same_timestamp_does_not_repeat_completion_or_decay(timeline):
    p = timeline.player(hunger=40)
    p["current_activity"] = timeline.activity("action", end=1,
        payload={"name": "Snack", "effects": {"hunger": -18}})
    timeline.resolve(p, 1)
    snapshot = deepcopy(p)
    event_count = len(timeline.db.events.rows)
    timeline.resolve(p, 1)
    assert p == snapshot
    assert len(timeline.db.events.rows) == event_count


def test_registered_shift_offline_and_online_have_same_work_costs(timeline):
    p = timeline.player(hunger=20, health=100, fatigue=0, energy=100, stress=0)
    p["job"] = {"job_id": "job", "reliability": 50}
    p["registered_shift"] = {
        "job_id": "job", "title": "Tester", "shift_name": "morning",
        "start_real": timeline.at(1).isoformat(), "duration_hours": 2,
        "payload": {"hours": 2, "hourly_wage": 10, "title": "Tester", "category": "test",
                    "fatigue_ph": 2, "stress_ph": 1, "energy_ph": 3, "skill_xp": {}},
    }
    frequent = deepcopy(p)
    timeline.resolve(p, 4)
    for minute in range(1, 241):
        timeline.resolve(frequent, minute / 60)
    assert_same_needs(p, frequent)
    # Two idle hours, two working hours: work already supplies explicit penalties.
    assert p["hunger"] == pytest.approx(20 + 2 * 3.2 + 2 * 2.5)
    assert p["energy"] == pytest.approx(100 - 2 * 2.4 - 2 * 3)
    assert p["cash"] == frequent["cash"]
    assert p["stats_meta"]["shifts_worked"] == frequent["stats_meta"]["shifts_worked"] == 1
