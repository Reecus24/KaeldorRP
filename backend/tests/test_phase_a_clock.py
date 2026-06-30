"""Phase A tests: world clock, notifications, daily summary flush, no double-billing."""
import os
import time
import uuid
import pytest
import requests
from dotenv import load_dotenv
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@kaeldor.com"
ADMIN_PASSWORD = "admin123"


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def throwaway_player():
    """Register a fresh throwaway player + create character."""
    email = f"TEST_clock_{uuid.uuid4().hex[:8]}@kaeldor.com"
    pw = "pass1234"
    r = requests.post(f"{BASE_URL}/api/auth/register",
                      json={"email": email, "password": pw, "name": "ClockTester"}, timeout=15)
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    rc = requests.post(f"{BASE_URL}/api/character/create",
                       json={"name": "Tick", "background": "drifter"},
                       headers=_auth_headers(token), timeout=15)
    assert rc.status_code == 200, rc.text
    return {"email": email, "token": token}


def _reset_time_scale(admin_token):
    requests.put(f"{BASE_URL}/api/admin/config", json={"time_scale": 1.0},
                 headers=_auth_headers(admin_token), timeout=15)


# ---------------------- world clock fields ----------------------
class TestPublicConfigClock:
    def test_config_exposes_clock_fields(self):
        r = requests.get(f"{BASE_URL}/api/config", timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("time_scale", "game_time", "world_start_real", "world_start_game"):
            assert k in d and d[k] is not None, f"missing {k}: {d}"
        assert d["time_scale"] == 1.0, f"time_scale should default to 1.0 - found {d['time_scale']}"

    def test_game_time_advances(self):
        r1 = requests.get(f"{BASE_URL}/api/config", timeout=15).json()
        time.sleep(2.5)
        r2 = requests.get(f"{BASE_URL}/api/config", timeout=15).json()
        assert r2["game_time"] > r1["game_time"], f"game_time didn't advance: {r1['game_time']} vs {r2['game_time']}"


class TestGameStateClock:
    def test_game_state_exposes_clock(self, throwaway_player):
        r = requests.get(f"{BASE_URL}/api/game/state",
                         headers=_auth_headers(throwaway_player["token"]), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("game_time", "world_start_real", "world_start_game", "time_scale"):
            assert k in d and d[k] is not None, f"missing {k}"


# ---------------------- notifications API ----------------------
class TestNotifications:
    def test_notifications_shape(self, throwaway_player):
        r = requests.get(f"{BASE_URL}/api/notifications",
                         headers=_auth_headers(throwaway_player["token"]), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d and isinstance(d["items"], list)
        assert "unread_count" in d and isinstance(d["unread_count"], int)

    def test_mark_all_read(self, throwaway_player):
        r = requests.post(f"{BASE_URL}/api/notifications/read", json={"ids": None},
                          headers=_auth_headers(throwaway_player["token"]), timeout=15)
        assert r.status_code == 200
        d = requests.get(f"{BASE_URL}/api/notifications",
                         headers=_auth_headers(throwaway_player["token"]), timeout=15).json()
        assert d["unread_count"] == 0


# ---------------------- daily summary endpoint ----------------------
class TestDailySummariesEndpoint:
    def test_daily_summaries_returns_list(self, throwaway_player):
        r = requests.get(f"{BASE_URL}/api/daily-summaries",
                         headers=_auth_headers(throwaway_player["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)


# ---------------------- FAST-FORWARD: flush + no double-billing ----------------------
class TestDailySummaryFlushNoDoubleBilling:
    def test_flush_and_economy_consistency(self, admin_token, throwaway_player):
        token = throwaway_player["token"]
        try:
            # baseline state (force resolve)
            s0 = requests.get(f"{BASE_URL}/api/game/state",
                              headers=_auth_headers(token), timeout=15).json()
            p0 = s0["player"]
            cash0, bank0, debt0 = p0["cash"], p0["bank"], p0["debt"]
            money0 = cash0 + bank0 - debt0

            # baseline summaries
            sums_before = requests.get(f"{BASE_URL}/api/daily-summaries",
                                       headers=_auth_headers(token), timeout=15).json()
            count_before = len(sums_before)

            # fast-forward
            rr = requests.put(f"{BASE_URL}/api/admin/config", json={"time_scale": 4000},
                              headers=_auth_headers(admin_token), timeout=15)
            assert rr.status_code == 200

            # let real time pass to cross >1 in-game day at ts=4000 (~22 real seconds per day)
            time.sleep(35)

            # trigger resolution twice
            requests.get(f"{BASE_URL}/api/game/state",
                         headers=_auth_headers(token), timeout=15)
            time.sleep(1.0)
            s1 = requests.get(f"{BASE_URL}/api/game/state",
                              headers=_auth_headers(token), timeout=15).json()
            p1 = s1["player"]
            cash1, bank1, debt1 = p1["cash"], p1["bank"], p1["debt"]
            money1 = cash1 + bank1 - debt1

            # check summary doc + notification
            sums_after = requests.get(f"{BASE_URL}/api/daily-summaries",
                                      headers=_auth_headers(token), timeout=15).json()
            assert len(sums_after) > count_before, (
                f"No daily_summary doc created after fast-forward "
                f"(before={count_before}, after={len(sums_after)})")

            latest = sums_after[0]
            # required fields
            for k in ("day_index", "days_covered", "game_date", "income_total",
                      "expense_total", "net_cash", "ledger", "cash", "bank", "debt"):
                assert k in latest, f"missing {k} in summary"

            notifs = requests.get(f"{BASE_URL}/api/notifications",
                                  headers=_auth_headers(token), timeout=15).json()
            types = [n.get("type") for n in notifs["items"]]
            assert "daily_summary" in types, f"daily_summary notification missing - types: {types}"

            # CRITICAL: no double-billing — summary net_cash should match
            # (money1 - money0) within tolerance. The summary REPORTS what was already deducted.
            actual_delta = round(money1 - money0, 2)
            reported_net = latest["net_cash"]

            # since fast-forward may have created multiple summaries covering distinct days,
            # sum all summaries newly created
            new_count = len(sums_after) - count_before
            reported_total = sum(s["net_cash"] for s in sums_after[:new_count])

            diff = abs(reported_total - actual_delta)
            # allow some slack for partial-day ledger that hasn't been flushed yet (carry-over)
            tolerance = max(50.0, abs(actual_delta) * 0.30)
            assert diff <= tolerance, (
                f"DOUBLE-BILLING SUSPECTED: actual money delta ${actual_delta} vs "
                f"summed reported net_cash ${reported_total} (diff ${diff}, tol ${tolerance}). "
                f"New summaries: {new_count}. Latest ledger buckets: {latest['ledger']}")

            # ledger should split costs into rent/bills/vehicle/etc
            ledger = latest["ledger"]
            assert "rent" in ledger and "bills" in ledger and "vehicle_costs" in ledger

            # offline progress regression: needs decayed
            assert p1["hunger"] >= p0["hunger"] - 0.01, "hunger should not have decreased over fast-forward"
        finally:
            _reset_time_scale(admin_token)

    def test_time_scale_reset_after(self, admin_token):
        # make sure we left time_scale at 1.0
        cfg = requests.get(f"{BASE_URL}/api/admin/config",
                           headers=_auth_headers(admin_token), timeout=15).json()
        assert cfg["time_scale"] == 1.0, f"time_scale not reset: {cfg['time_scale']}"
