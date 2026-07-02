"""
Iteration 36 — Shift Registration API + Admin Job Applications tuning API tests.

Covers:
  * POST /api/jobs/register-shift  (early/late/full/night)  — success + validation
  * POST /api/jobs/cancel-shift    — success + 400 when nothing registered
  * GET  /api/game/state           — registered_shift is set/cleared
  * GET  /api/jobs/current         — shift_options exposes the 4 standard shifts
  * GET/PUT /api/admin/job-applications — hiring tuning CRUD + validation
  * 403 sanity: player token on /api/admin/*
"""
import os
import pytest
import requests
from pathlib import Path

def _load_frontend_env():
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set (frontend/.env)"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@kaeldor.com"
ADMIN_PASS = "admin123"
PLAYER_EMAIL = "shiftplayer@kaeldor.com"   # Cleaner NPC job holder (per /app/memory/test_credentials.md)
PLAYER_PASS = "demo123"

CASHIER_DEFAULTS = {
    "acceptance_base_chance": 0.5,
    "skill_weight": 1.0,
    "success_response": "Your application for {title} was accepted — the offer is ${wage}/h. Accept it to start working.",
    "failure_response": "Your application for {title} was rejected: {reason}.",
}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def player_headers():
    tok = _login(PLAYER_EMAIL, PLAYER_PASS)
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_headers():
    tok = _login(ADMIN_EMAIL, ADMIN_PASS)
    return {"Authorization": f"Bearer {tok}"}


def _reset_shift_for(headers):
    requests.post(f"{API}/jobs/cancel-shift", headers=headers, timeout=15)


# ============================================================================
# Shift registration / cancel
# ============================================================================
class TestShiftRegistration:
    @pytest.fixture(autouse=True)
    def _clean(self, player_headers):
        _reset_shift_for(player_headers)
        yield
        _reset_shift_for(player_headers)

    def test_register_shift_early_ok(self, player_headers):
        r = requests.post(f"{API}/jobs/register-shift", json={"shift_id": "early"}, headers=player_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        rs = data["registered_shift"]
        assert rs["shift_id"] == "early"
        assert rs["start_hour"] == 8
        assert rs["duration_hours"] == 5
        assert isinstance(rs["start_real"], str) and len(rs["start_real"]) > 0
        assert "payload" in rs and rs["payload"]["job_id"] == "cleaner"
        assert "starts_in_seconds" in data and data["starts_in_seconds"] >= 0

        # Verify persistence via /api/game/state
        gs = requests.get(f"{API}/game/state", headers=player_headers, timeout=15).json()
        assert gs["player"].get("registered_shift") is not None
        assert gs["player"]["registered_shift"]["shift_id"] == "early"

    def test_duplicate_registration_returns_409(self, player_headers):
        r1 = requests.post(f"{API}/jobs/register-shift", json={"shift_id": "early"}, headers=player_headers, timeout=15)
        assert r1.status_code == 200, r1.text
        r2 = requests.post(f"{API}/jobs/register-shift", json={"shift_id": "late"}, headers=player_headers, timeout=15)
        assert r2.status_code == 409, f"expected 409, got {r2.status_code} {r2.text}"

    def test_cancel_ok_then_400(self, player_headers):
        requests.post(f"{API}/jobs/register-shift", json={"shift_id": "early"}, headers=player_headers, timeout=15)
        r = requests.post(f"{API}/jobs/cancel-shift", headers=player_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        # /api/game/state should show registered_shift is falsy
        gs = requests.get(f"{API}/game/state", headers=player_headers, timeout=15).json()
        assert not gs["player"].get("registered_shift")

        # Calling again with nothing registered -> 400
        r2 = requests.post(f"{API}/jobs/cancel-shift", headers=player_headers, timeout=15)
        assert r2.status_code == 400, r2.text

    def test_invalid_shift_id_returns_400(self, player_headers):
        r = requests.post(f"{API}/jobs/register-shift", json={"shift_id": "doesnotexist"}, headers=player_headers, timeout=15)
        assert r.status_code == 400, r.text


# ============================================================================
# 4 standard shifts exposed on the job
# ============================================================================
class TestStandardShiftOptions:
    def test_current_job_exposes_4_standard_shifts(self, player_headers):
        r = requests.get(f"{API}/jobs/current", headers=player_headers, timeout=15)
        assert r.status_code == 200, r.text
        details = r.json().get("details") or {}
        shifts = details.get("shift_options") or []
        by_id = {s["id"]: s for s in shifts if isinstance(s, dict)}
        for sid in ("early", "late", "full", "night"):
            assert sid in by_id, f"missing shift id '{sid}' in {list(by_id)}"

        assert by_id["early"]["start_hour"] == 8 and by_id["early"]["duration_hours"] == 5
        assert by_id["late"]["start_hour"] == 13 and by_id["late"]["duration_hours"] == 5
        assert by_id["full"]["start_hour"] == 8 and by_id["full"]["duration_hours"] == 10
        # cleaner has night
        assert by_id["night"]["start_hour"] == 22 and by_id["night"]["duration_hours"] == 10


# ============================================================================
# Admin hiring tuning
# ============================================================================
class TestAdminJobApplications:
    def test_list_job_applications(self, admin_headers):
        r = requests.get(f"{API}/admin/job-applications", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        jobs = data.get("jobs") if isinstance(data, dict) else data
        assert isinstance(jobs, list) and len(jobs) > 0
        for j in jobs:
            for field in ("id", "acceptance_base_chance", "skill_weight", "success_response", "failure_response"):
                assert field in j, f"job {j.get('id')} missing '{field}'"
        assert any(j["id"] == "cashier" for j in jobs)

    def _fetch_cashier(self, admin_headers):
        r = requests.get(f"{API}/admin/job-applications", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        jobs = data.get("jobs") if isinstance(data, dict) else data
        return next(j for j in jobs if j["id"] == "cashier")

    def test_update_cashier_and_persist_then_reset(self, admin_headers):
        payload = {
            "acceptance_base_chance": 0.8,
            "skill_weight": 1.2,
            "success_response": "Hired at {title} for ${wage}/h.",
            "failure_response": "{title} rejected you: {reason}.",
        }
        r = requests.put(f"{API}/admin/job-applications/cashier", json=payload, headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text

        cashier = self._fetch_cashier(admin_headers)
        assert abs(cashier["acceptance_base_chance"] - 0.8) < 1e-6
        assert abs(cashier["skill_weight"] - 1.2) < 1e-6
        assert cashier["success_response"] == payload["success_response"]
        assert cashier["failure_response"] == payload["failure_response"]

        # RESET to defaults
        r3 = requests.put(f"{API}/admin/job-applications/cashier", json=CASHIER_DEFAULTS, headers=admin_headers, timeout=15)
        assert r3.status_code == 200, r3.text
        cashier2 = self._fetch_cashier(admin_headers)
        assert abs(cashier2["acceptance_base_chance"] - 0.5) < 1e-6
        assert abs(cashier2["skill_weight"] - 1.0) < 1e-6
        assert cashier2["success_response"] == CASHIER_DEFAULTS["success_response"]
        assert cashier2["failure_response"] == CASHIER_DEFAULTS["failure_response"]

    def test_validation_out_of_range_base_returns_400(self, admin_headers):
        r = requests.put(
            f"{API}/admin/job-applications/cashier",
            json={"acceptance_base_chance": 5, "skill_weight": 1.0,
                  "success_response": "ok {title} {wage}", "failure_response": "no {title} {reason}"},
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"

    def test_validation_empty_success_returns_400(self, admin_headers):
        r = requests.put(
            f"{API}/admin/job-applications/cashier",
            json={"acceptance_base_chance": 0.5, "skill_weight": 1.0,
                  "success_response": "", "failure_response": "no {title} {reason}"},
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"

    def test_player_token_forbidden_403(self, player_headers):
        r = requests.get(f"{API}/admin/job-applications", headers=player_headers, timeout=15)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"
