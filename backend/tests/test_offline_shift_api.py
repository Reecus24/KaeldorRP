"""Iteration 42 — API-level OFFLINE SHIFT COMPLETION (P0).

Verifies that the segmented offline catch-up in game_engine.resolve_player() correctly
clocks a registered shift in and out on the GAME CLOCK, even when the player is fully
offline for the whole window. Simulates offline by BACKDATING the Mongo player doc
(registered_shift.start_real + last_resolved_at) since time_scale=1.0.

Scenarios covered:
  A) FULL OFFLINE COMPLETION — shift starts + ends inside the offline window -> completes + pays.
  B) MID-SHIFT PERSISTENCE  — offline window ends INSIDE the shift -> shift IN PROGRESS after resolve.
  C) EXHAUSTED-AT-START MISS — energy<10 at start -> correctly MISSED with reliability penalty.
  D) FUTURE SHIFT PENDING   — start_real in the future -> registration intact, no auto-start.
  E) SHIFT REGISTRATION API — POST /jobs/register-shift + /jobs/cancel-shift regression.
  F) CORE-LOOP REGRESSION   — /api/game/state, /api/bank, /api/jobs, /api/businesses/owned = 200
     for demo players (mara/dovan/admin).
"""
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # fallback to frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

SHIFT_EMAIL = "shiftplayer@kaeldor.com"
SHIFT_PW = "demo123"


# ----- fixtures --------------------------------------------------------------

@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(api, email, pw):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text}"
    tok = r.json()["token"]
    return tok, {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def shift_auth(api):
    tok, hdrs = _login(api, SHIFT_EMAIL, SHIFT_PW)
    return hdrs


@pytest.fixture(scope="module")
def shift_player(mongo, api, shift_auth):
    """Return the shiftplayer's mongo player doc id (p['id'])."""
    r = api.get(f"{BASE_URL}/api/game/state", headers=shift_auth, timeout=15)
    assert r.status_code == 200, r.text
    pid = r.json()["player"]["id"]
    return pid


# Snapshot original DB state so we can restore after each test that mutates.
def _snapshot(mongo, pid):
    return mongo.players.find_one({"id": pid})


def _restore(mongo, snap):
    mongo.players.replace_one({"id": snap["id"]}, snap)


def _register_early_shift(api, headers):
    """Register the Early Shift (5h) for the cleaner. Returns (shift_id, shift_dict)."""
    r = api.get(f"{BASE_URL}/api/jobs", headers=headers, timeout=15)
    assert r.status_code == 200
    jobs = r.json()
    if isinstance(jobs, dict):
        jobs = jobs.get("jobs") or jobs.get("items") or []
    cleaner = next(j for j in jobs if j.get("id") == "cleaner")
    shifts = [s for s in cleaner.get("shift_options", []) if isinstance(s, dict)]
    # Prefer the fixed Early 08:00 5h shift, otherwise the first 5h shift.
    early = next((s for s in shifts if s.get("id") == "early" or s.get("start_hour") == 8 and s.get("duration_hours") == 5), shifts[0])
    r = api.post(f"{BASE_URL}/api/jobs/register-shift", headers=headers, json={"shift_id": early["id"]}, timeout=15)
    assert r.status_code == 200, f"register-shift -> {r.status_code} {r.text}"
    body = r.json()
    assert body.get("ok") is True
    assert "registered_shift" in body
    assert "starts_in_seconds" in body
    return early


def _backdate(mongo, pid, start_ago_h, offline_h, energy=None, status=None, current_activity=None):
    """Move registered_shift.start_real to `start_ago_h` hours ago (negative = future) and
    last_resolved_at to `offline_h` hours ago. Optionally patch energy/status/current_activity."""
    now = datetime.now(timezone.utc)
    start_real = now - timedelta(hours=start_ago_h)
    last_resolved = now - timedelta(hours=offline_h)
    p = mongo.players.find_one({"id": pid})
    rs = dict(p.get("registered_shift") or {})
    assert rs, "player has no registered_shift to backdate"
    rs["start_real"] = start_real.isoformat()
    rs["registered_at"] = last_resolved.isoformat()
    upd = {
        "registered_shift": rs,
        "last_resolved_at": last_resolved.isoformat(),
    }
    if energy is not None:
        upd["energy"] = float(energy)
    if status is not None:
        upd["status"] = status
    if current_activity is not None:
        upd["current_activity"] = current_activity
    # Reset shifts_worked counter on the job so we can assert +=1 cleanly.
    job = dict(p.get("job") or {})
    job["shifts_worked"] = 0
    job["reliability"] = 60
    upd["job"] = job
    mongo.players.update_one({"id": pid}, {"$set": upd})


# ----- Scenario A — FULL OFFLINE COMPLETION ---------------------------------

class TestOfflineShiftCompletion:
    def test_A_full_offline_completes_and_pays(self, api, mongo, shift_auth, shift_player):
        pid = shift_player
        # Clear any lingering registered_shift / current_activity first.
        mongo.players.update_one({"id": pid}, {"$set": {"registered_shift": None, "current_activity": None,
                                                        "status": "idle", "energy": 90.0}})
        _register_early_shift(api, shift_auth)
        snap = _snapshot(mongo, pid)
        cash0 = snap["cash"]
        try:
            _backdate(mongo, pid, start_ago_h=8, offline_h=9, energy=60)
            # Trigger the resolve.
            r = api.get(f"{BASE_URL}/api/game/state", headers=shift_auth, timeout=20)
            assert r.status_code == 200, r.text
            body = r.json()
            p = body["player"]
            assert p["job"]["shifts_worked"] == 1, f"expected shifts_worked==1, got {p['job']['shifts_worked']}"
            assert p["cash"] > cash0, f"cash should increase after paid shift ({p['cash']} vs {cash0})"
            assert p.get("registered_shift") in (None, {}), f"registered_shift should be cleared: {p.get('registered_shift')}"
            assert p.get("current_activity") in (None, {}), f"current_activity should be cleared after completion: {p.get('current_activity')}"
            # There should be a 'Finished ... shift' event.
            re = api.get(f"{BASE_URL}/api/game/events?limit=20", headers=shift_auth, timeout=15)
            assert re.status_code == 200
            evs = re.json()
            assert any("Finished" in (e.get("message") or "") and "shift" in (e.get("message") or "").lower() for e in evs), \
                f"expected a 'Finished ... shift' event; got: {[e.get('message') for e in evs][:5]}"
        finally:
            _restore(mongo, snap)

    # ----- Scenario B — MID-SHIFT PERSISTENCE ------------------------------

    def test_B_mid_shift_in_progress(self, api, mongo, shift_auth, shift_player):
        pid = shift_player
        mongo.players.update_one({"id": pid}, {"$set": {"registered_shift": None, "current_activity": None,
                                                        "status": "idle", "energy": 90.0}})
        _register_early_shift(api, shift_auth)
        snap = _snapshot(mongo, pid)
        try:
            # Shift started 2h ago, offline for 3h — shift is 5h so still IN PROGRESS.
            _backdate(mongo, pid, start_ago_h=2, offline_h=3, energy=80)
            r = api.get(f"{BASE_URL}/api/game/state", headers=shift_auth, timeout=20)
            assert r.status_code == 200
            p = r.json()["player"]
            act = p.get("current_activity") or {}
            assert act.get("kind") == "job", f"expected in-progress 'job' activity, got {act}"
            assert p["job"]["shifts_worked"] == 0, "shift should NOT be marked complete yet"
            assert p.get("registered_shift") in (None, {}), "registration should be consumed"
        finally:
            _restore(mongo, snap)

    # ----- Scenario C — EXHAUSTED-AT-START MISS ----------------------------

    def test_C_exhausted_at_start_is_missed(self, api, mongo, shift_auth, shift_player):
        pid = shift_player
        mongo.players.update_one({"id": pid}, {"$set": {"registered_shift": None, "current_activity": None,
                                                        "status": "idle", "energy": 90.0}})
        _register_early_shift(api, shift_auth)
        snap = _snapshot(mongo, pid)
        try:
            # Started 30min ago, offline 36min, energy=8 -> too tired at start -> miss + reliability hit.
            _backdate(mongo, pid, start_ago_h=0.5, offline_h=0.6, energy=8)
            r = api.get(f"{BASE_URL}/api/game/state", headers=shift_auth, timeout=20)
            assert r.status_code == 200
            p = r.json()["player"]
            assert p["job"]["shifts_worked"] == 0, "exhausted -> shift missed"
            assert p["job"]["reliability"] < 60, f"reliability should drop from 60, got {p['job']['reliability']}"
            assert p.get("registered_shift") in (None, {}), "registration is consumed on miss"
        finally:
            _restore(mongo, snap)

    # ----- Scenario D — FUTURE SHIFT PENDING -------------------------------

    def test_D_future_shift_stays_pending(self, api, mongo, shift_auth, shift_player):
        pid = shift_player
        mongo.players.update_one({"id": pid}, {"$set": {"registered_shift": None, "current_activity": None,
                                                        "status": "idle", "energy": 90.0}})
        _register_early_shift(api, shift_auth)
        snap = _snapshot(mongo, pid)
        try:
            # start_real is 2h in the future.
            _backdate(mongo, pid, start_ago_h=-2, offline_h=0.1, energy=80)
            r = api.get(f"{BASE_URL}/api/game/state", headers=shift_auth, timeout=20)
            assert r.status_code == 200
            p = r.json()["player"]
            assert p["job"]["shifts_worked"] == 0
            assert p.get("registered_shift"), "future shift must stay registered"
            assert p.get("current_activity") in (None, {}), "must not have auto-started"
        finally:
            _restore(mongo, snap)


# ----- Scenario E — SHIFT REGISTRATION API regression -----------------------

class TestShiftRegistrationApi:
    def test_register_then_cancel(self, api, mongo, shift_auth, shift_player):
        pid = shift_player
        # Clean state.
        mongo.players.update_one({"id": pid}, {"$set": {"registered_shift": None, "current_activity": None,
                                                        "status": "idle", "energy": 90.0}})
        early = _register_early_shift(api, shift_auth)
        # Cannot register a second shift while one is pending.
        r2 = api.post(f"{BASE_URL}/api/jobs/register-shift", headers=shift_auth,
                      json={"shift_id": early["id"]}, timeout=15)
        assert r2.status_code == 409, f"double-register should 409, got {r2.status_code} {r2.text}"
        # Cancel works.
        rc = api.post(f"{BASE_URL}/api/jobs/cancel-shift", headers=shift_auth, timeout=15)
        assert rc.status_code == 200 and rc.json().get("ok") is True
        # Cancel again -> 400 (nothing to cancel).
        rc2 = api.post(f"{BASE_URL}/api/jobs/cancel-shift", headers=shift_auth, timeout=15)
        assert rc2.status_code == 400

    def test_invalid_shift_id_400(self, api, mongo, shift_auth, shift_player):
        pid = shift_player
        mongo.players.update_one({"id": pid}, {"$set": {"registered_shift": None}})
        r = api.post(f"{BASE_URL}/api/jobs/register-shift", headers=shift_auth,
                     json={"shift_id": "NOT_A_REAL_SHIFT"}, timeout=15)
        assert r.status_code == 400

    def test_jailed_cannot_register(self, api, mongo, shift_auth, shift_player):
        pid = shift_player
        snap = _snapshot(mongo, pid)
        try:
            mongo.players.update_one({"id": pid}, {"$set": {
                "registered_shift": None,
                "status": "jail",
                "jail_until": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            }})
            # find a valid shift id first
            r_jobs = api.get(f"{BASE_URL}/api/jobs", headers=shift_auth, timeout=15)
            jl = r_jobs.json()
            if isinstance(jl, dict):
                jl = jl.get("jobs") or jl.get("items") or []
            cleaner = next(j for j in jl if j.get("id") == "cleaner")
            shift = [s for s in cleaner["shift_options"] if isinstance(s, dict)][0]
            r = api.post(f"{BASE_URL}/api/jobs/register-shift", headers=shift_auth,
                         json={"shift_id": shift["id"]}, timeout=15)
            assert r.status_code == 409, f"jailed player must not register: {r.status_code} {r.text}"
        finally:
            _restore(mongo, snap)


# ----- Scenario F — CORE-LOOP REGRESSION ------------------------------------

class TestCoreLoopRegression:
    @pytest.mark.parametrize("email,pw", [
        ("shiftplayer@kaeldor.com", "demo123"),
        ("mara@kaeldor.com", "demo123"),
        ("dovan@kaeldor.com", "demo123"),
    ])
    def test_core_endpoints_ok(self, api, email, pw):
        _, hdrs = _login(api, email, pw)
        for path in ("/api/game/state", "/api/bank", "/api/jobs", "/api/businesses/owned"):
            r = api.get(f"{BASE_URL}{path}", headers=hdrs, timeout=15)
            assert r.status_code == 200, f"{email} GET {path} -> {r.status_code} {r.text[:200]}"
