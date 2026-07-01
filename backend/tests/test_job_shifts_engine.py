"""
Backend tests for the UNIVERSAL SHIFT & RISK ENGINE (iteration 33).

Covers:
- GET  /api/admin/job-shifts       (admin, rich shift schema in response)
- PUT  /api/admin/job-shifts/{job} (admin, validation + persistence + restore)
- POST /api/jobs/work              (window-gated shift_id path)
- POST /api/jobs/work              (legacy hours path, no window enforcement)
- Guard scripts (economy + markets)
"""
import os
import subprocess
import time
import pytest
import requests
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://grind-nation.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@kaeldor.com"
ADMIN_PASS  = "admin123"
SHIFT_EMAIL = "shiftplayer@kaeldor.com"
SHIFT_PASS  = "demo123"


# -------------------------- fixtures --------------------------
def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, f"no token in login response for {email}: {r.text[:200]}"
    return tok

@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)

@pytest.fixture(scope="session")
def shift_token():
    return _login(SHIFT_EMAIL, SHIFT_PASS)

@pytest.fixture(scope="session")
def game_hour():
    r = requests.get(f"{API}/config", timeout=30)
    assert r.status_code == 200, f"/config failed: {r.status_code}"
    gt = r.json().get("game_time")
    assert gt, "config missing game_time"
    # accept trailing Z
    h = datetime.fromisoformat(gt.replace("Z", "+00:00")).hour
    return h


def _window_open(shift, h):
    w = shift.get("start_window") or {}
    lo = int(w.get("min_hour", 0)); hi = int(w.get("max_hour", 24))
    if lo == hi: return True
    if lo < hi: return lo <= h < hi
    return h >= lo or h < hi


# -------------------------- admin GET --------------------------
class TestAdminJobShiftsGet:
    def test_get_job_shifts_schema(self, admin_token):
        r = requests.get(f"{API}/admin/job-shifts",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "jobs" in data and isinstance(data["jobs"], list) and data["jobs"], "no jobs"
        # find cleaner
        cleaner = next((j for j in data["jobs"] if j.get("id") == "cleaner"), None)
        assert cleaner is not None, "cleaner job missing"
        opts = cleaner.get("shift_options")
        assert isinstance(opts, list) and len(opts) >= 3
        for s in opts:
            assert isinstance(s, dict)
            for k in ("id", "name", "duration_hours", "start_window",
                      "injury_risk", "pay_multiplier", "xp_multiplier"):
                assert k in s, f"cleaner shift missing '{k}': {s}"
            assert isinstance(s["start_window"], dict)
            assert "min_hour" in s["start_window"] and "max_hour" in s["start_window"]

    def test_get_requires_admin(self, shift_token):
        r = requests.get(f"{API}/admin/job-shifts",
                         headers={"Authorization": f"Bearer {shift_token}"}, timeout=30)
        assert r.status_code in (401, 403), f"expected 401/403 for non-admin, got {r.status_code}"


# -------------------------- admin PUT validation + persistence --------------------------
CLEANER_ORIGINAL = [
    {"id": "morning", "name": "Morning Clean",  "duration_hours": 4,
     "start_window": {"min_hour": 5,  "max_hour": 11}, "injury_risk": 0.03,
     "pay_multiplier": 1.0, "xp_multiplier": 1.0},
    {"id": "day",     "name": "Day Shift",      "duration_hours": 6,
     "start_window": {"min_hour": 6,  "max_hour": 16}, "injury_risk": 0.05,
     "pay_multiplier": 1.0, "xp_multiplier": 1.0},
    {"id": "night",   "name": "Night Sanitation","duration_hours": 6,
     "start_window": {"min_hour": 21, "max_hour": 3},  "injury_risk": 0.13,
     "pay_multiplier": 1.40, "xp_multiplier": 1.15},
]


class TestAdminJobShiftsPut:
    def _hdr(self, tok):
        return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

    def test_empty_list_rejected(self, admin_token):
        r = requests.put(f"{API}/admin/job-shifts/cleaner",
                         headers=self._hdr(admin_token), json={"shift_options": []}, timeout=30)
        assert r.status_code == 400, f"expected 400 for empty list, got {r.status_code} {r.text}"

    def test_duplicate_id_rejected(self, admin_token):
        payload = {"shift_options": [
            {"id": "dup", "name": "A", "duration_hours": 4, "start_window": {"min_hour": 5, "max_hour": 11},
             "injury_risk": 0.01, "pay_multiplier": 1.0, "xp_multiplier": 1.0},
            {"id": "dup", "name": "B", "duration_hours": 6, "start_window": {"min_hour": 6, "max_hour": 16},
             "injury_risk": 0.02, "pay_multiplier": 1.0, "xp_multiplier": 1.0},
        ]}
        r = requests.put(f"{API}/admin/job-shifts/cleaner",
                         headers=self._hdr(admin_token), json=payload, timeout=30)
        assert r.status_code == 400, f"expected 400 duplicate id, got {r.status_code} {r.text}"

    def test_bad_duration_rejected(self, admin_token):
        payload = {"shift_options": [
            {"id": "bad", "name": "Bad", "duration_hours": 20,  # >16
             "start_window": {"min_hour": 5, "max_hour": 11},
             "injury_risk": 0.01, "pay_multiplier": 1.0, "xp_multiplier": 1.0},
        ]}
        r = requests.put(f"{API}/admin/job-shifts/cleaner",
                         headers=self._hdr(admin_token), json=payload, timeout=30)
        assert r.status_code == 400, f"expected 400 bad duration, got {r.status_code}"

    def test_bad_window_hour_rejected(self, admin_token):
        payload = {"shift_options": [
            {"id": "bad", "name": "Bad", "duration_hours": 4,
             "start_window": {"min_hour": 5, "max_hour": 30},  # >24
             "injury_risk": 0.01, "pay_multiplier": 1.0, "xp_multiplier": 1.0},
        ]}
        r = requests.put(f"{API}/admin/job-shifts/cleaner",
                         headers=self._hdr(admin_token), json=payload, timeout=30)
        assert r.status_code == 400, f"expected 400 bad window, got {r.status_code}"

    def test_valid_save_and_restore_cleaner(self, admin_token):
        # 1) fetch current cleaner shifts to preserve
        r0 = requests.get(f"{API}/admin/job-shifts",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r0.status_code == 200
        original = next(j for j in r0.json()["jobs"] if j["id"] == "cleaner")["shift_options"]

        # 2) save an alt payload
        alt = [{"id": "tempshift", "name": "TEST Shift", "duration_hours": 3,
                "start_window": {"min_hour": 8, "max_hour": 12},
                "injury_risk": 0.07, "pay_multiplier": 1.25, "xp_multiplier": 1.05}]
        r = requests.put(f"{API}/admin/job-shifts/cleaner",
                         headers=self._hdr(admin_token), json={"shift_options": alt}, timeout=30)
        assert r.status_code == 200, r.text
        cleaned = r.json().get("shift_options")
        assert isinstance(cleaned, list) and len(cleaned) == 1
        assert cleaned[0]["id"] == "tempshift"
        assert cleaned[0]["duration_hours"] == 3
        assert cleaned[0]["start_window"]["min_hour"] == 8
        assert cleaned[0]["start_window"]["max_hour"] == 12

        # 3) verify persistence via GET
        r2 = requests.get(f"{API}/admin/job-shifts",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        cleaner2 = next(j for j in r2.json()["jobs"] if j["id"] == "cleaner")
        assert cleaner2["shift_options"][0]["id"] == "tempshift"

        # 4) RESTORE original (or fallback constants)
        restore = original if isinstance(original, list) and original and isinstance(original[0], dict) else CLEANER_ORIGINAL
        r3 = requests.put(f"{API}/admin/job-shifts/cleaner",
                          headers=self._hdr(admin_token), json={"shift_options": restore}, timeout=30)
        assert r3.status_code == 200, r3.text
        # sanity: post-restore has >=3 shifts including 'night'
        r4 = requests.get(f"{API}/admin/job-shifts",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        cleaner3 = next(j for j in r4.json()["jobs"] if j["id"] == "cleaner")
        ids = [s["id"] for s in cleaner3["shift_options"]]
        assert "night" in ids, f"restore lost 'night' shift: {ids}"


# -------------------------- player POST /jobs/work --------------------------
class TestPlayerWorkShift:
    def _free_player(self, tok):
        """Ensure shiftplayer isn't busy — cancel any current activity if present."""
        st = requests.get(f"{API}/game/state",
                          headers={"Authorization": f"Bearer {tok}"}, timeout=30).json()
        act = st.get("activity") or {}
        if act.get("kind"):
            requests.post(f"{API}/game/cancel-activity",
                          headers={"Authorization": f"Bearer {tok}"}, timeout=30)
            st2 = requests.get(f"{API}/game/state",
                               headers={"Authorization": f"Bearer {tok}"}, timeout=30).json()
            return not (st2.get("activity") or {}).get("kind")
        return True

    def test_invalid_shift_id_returns_400(self, shift_token):
        if not self._free_player(shift_token):
            pytest.skip("shiftplayer is busy on an activity — cannot test start flow")
        r = requests.post(f"{API}/jobs/work",
                          headers={"Authorization": f"Bearer {shift_token}", "Content-Type": "application/json"},
                          json={"shift_id": "does-not-exist-zzz"}, timeout=30)
        assert r.status_code == 400, f"expected 400 for invalid shift_id, got {r.status_code} {r.text}"
        assert "Invalid shift option" in r.text

    def test_closed_window_returns_400(self, shift_token, admin_token, game_hour):
        """Find a cleaner shift whose window is CLOSED for the current game hour and try to start it."""
        if not self._free_player(shift_token):
            pytest.skip("shiftplayer is busy — skipping closed-window test")

        r = requests.get(f"{API}/admin/job-shifts",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        cleaner = next(j for j in r.json()["jobs"] if j["id"] == "cleaner")
        closed = [s for s in cleaner["shift_options"] if not _window_open(s, game_hour)]
        if not closed:
            pytest.skip(f"no closed cleaner shift at game hour {game_hour} — cannot verify 400 path")
        s = closed[0]
        r2 = requests.post(f"{API}/jobs/work",
                           headers={"Authorization": f"Bearer {shift_token}", "Content-Type": "application/json"},
                           json={"shift_id": s["id"]}, timeout=30)
        assert r2.status_code == 400, f"expected 400 (closed), got {r2.status_code} {r2.text}"
        body = r2.text
        assert "can only start between" in body or "between" in body, f"unexpected message: {body}"

    def test_open_window_starts_shift(self, shift_token, admin_token, game_hour):
        if not self._free_player(shift_token):
            pytest.skip("shiftplayer is busy — skipping open-window test")

        r = requests.get(f"{API}/admin/job-shifts",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        cleaner = next(j for j in r.json()["jobs"] if j["id"] == "cleaner")
        opens = [s for s in cleaner["shift_options"] if _window_open(s, game_hour)]
        if not opens:
            pytest.skip(f"no open cleaner shift at game hour {game_hour}")
        s = opens[0]
        r2 = requests.post(f"{API}/jobs/work",
                           headers={"Authorization": f"Bearer {shift_token}", "Content-Type": "application/json"},
                           json={"shift_id": s["id"]}, timeout=30)
        assert r2.status_code == 200, f"expected 200 open-window start, got {r2.status_code} {r2.text}"
        # verify activity exists
        st = requests.get(f"{API}/game/state",
                          headers={"Authorization": f"Bearer {shift_token}"}, timeout=30).json()
        act = st.get("activity") or {}
        assert act.get("kind") == "job", f"activity not started: {act}"

    def test_legacy_hours_path_no_window(self, shift_token, admin_token):
        """Legacy body {hours: N} matches by duration_hours and skips window enforcement."""
        # cancel any lingering activity from prior test
        st = requests.get(f"{API}/game/state",
                          headers={"Authorization": f"Bearer {shift_token}"}, timeout=30).json()
        if (st.get("activity") or {}).get("kind"):
            requests.post(f"{API}/game/cancel-activity",
                          headers={"Authorization": f"Bearer {shift_token}"}, timeout=30)

        # invalid hours
        r_bad = requests.post(f"{API}/jobs/work",
                              headers={"Authorization": f"Bearer {shift_token}", "Content-Type": "application/json"},
                              json={"hours": 99}, timeout=30)
        assert r_bad.status_code == 400, f"expected 400 for bad hours, got {r_bad.status_code} {r_bad.text}"

        # find a valid duration
        r = requests.get(f"{API}/admin/job-shifts",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        cleaner = next(j for j in r.json()["jobs"] if j["id"] == "cleaner")
        durations = sorted({s["duration_hours"] for s in cleaner["shift_options"]})
        r_ok = requests.post(f"{API}/jobs/work",
                             headers={"Authorization": f"Bearer {shift_token}", "Content-Type": "application/json"},
                             json={"hours": durations[0]}, timeout=30)
        assert r_ok.status_code == 200, f"expected 200 legacy hours, got {r_ok.status_code} {r_ok.text}"


# -------------------------- guard scripts --------------------------
class TestGuardScripts:
    @pytest.mark.parametrize("script", ["/app/tests/verify_economy.py", "/app/tests/verify_markets.py"])
    def test_guard(self, script):
        if not os.path.exists(script):
            pytest.skip(f"{script} not present")
        res = subprocess.run(["python3", script], capture_output=True, text=True, timeout=180)
        combined = (res.stdout or "") + (res.stderr or "")
        assert res.returncode == 0, f"guard exit={res.returncode}:\n{combined[-1500:]}"
        assert "PASSED" in combined, f"guard missing PASSED:\n{combined[-1500:]}"
