"""Iteration 40 — FINAL LOGIC REPAIR: reputation/social/legal wiring into outcomes.

Backend API-level validation of:
  1. Reputation-priced bank loans (interest_daily scales with reputation)
  2. VIP banking via social_status (vip flag + social_standing factor)
  3. Reputation gate on high-tier jobs (store/restaurant/logistics manager)
  4. Loan interest actually charged uses reputation-priced rate
     (validated via /api/bank -> daily_interest_cost)
  5. Underworld crime endpoints still functional; game/state resolves cleanly
     for a player with low legal_reputation without 500 errors
  6. Regression: core economy/game flows still work
"""
import os
import pytest
import requests
from dotenv import dotenv_values

_fe_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or _fe_env.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@kaeldor.com"
ADMIN_PASS = "admin123"
MARA_EMAIL = "mara@kaeldor.com"
DOVAN_EMAIL = "dovan@kaeldor.com"
KIRI_EMAIL = "kiri@kaeldor.com"
DEMO_PASS = "demo123"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


def _login(email, password=DEMO_PASS):
    r = requests.post(f"{API}/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def mara_token():
    return _login(MARA_EMAIL)


@pytest.fixture(scope="module")
def dovan_token():
    return _login(DOVAN_EMAIL)


@pytest.fixture(scope="module")
def kiri_token():
    return _login(KIRI_EMAIL)


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


def _list_players(admin_token):
    r = requests.get(f"{API}/admin/players", headers=_hdr(admin_token), timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    return body.get("players") if isinstance(body, dict) else body


def _get_player(admin_token, pid):
    for p in _list_players(admin_token):
        if p["id"] == pid:
            return p
    return None


def _player_id(email, admin_token):
    """Look up player id via admin listing. Falls back to matching by known name."""
    r = requests.get(f"{API}/admin/players", headers=_hdr(admin_token), timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    players = body.get("players") if isinstance(body, dict) else body
    name_map = {
        MARA_EMAIL: "Mara Vance",
        DOVAN_EMAIL: "Dovan Reyes",
        KIRI_EMAIL: "Kiri Sol",
    }
    target_name = name_map.get(email)
    for p in players:
        if p.get("email") == email or (p.get("user") or {}).get("email") == email:
            return p["id"]
        if target_name and p.get("name") == target_name:
            return p["id"]
    return None


@pytest.fixture(scope="module")
def mara_id(admin_token):
    pid = _player_id(MARA_EMAIL, admin_token)
    assert pid, "mara player id not found"
    return pid


@pytest.fixture(scope="module")
def kiri_id(admin_token):
    pid = _player_id(KIRI_EMAIL, admin_token)
    assert pid, "kiri player id not found"
    return pid


def _admin_set(admin_token, pid, **fields):
    r = requests.put(f"{API}/admin/players/{pid}",
                     headers=_hdr(admin_token), json=fields, timeout=15)
    assert r.status_code == 200, f"admin update failed: {r.status_code} {r.text}"
    return r.json()


# ---------- 1. Reputation-priced bank loan rates (read-only) ----------
class TestReputationLoanPricing:
    def test_bank_returns_interest_daily_field(self, mara_token):
        r = requests.get(f"{API}/bank", headers=_hdr(mara_token), timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "interest_daily" in data, f"missing interest_daily: {list(data.keys())}"
        assert isinstance(data["interest_daily"], (int, float))
        assert 0 < data["interest_daily"] < 0.1  # sane bounds
        # New fields required by spec:
        assert "vip" in data, "credit_profile must expose 'vip' boolean"
        assert isinstance(data["vip"], bool)
        factors = data.get("factors") or {}
        assert "social_standing" in factors, "factors.social_standing missing"


# ---------- 2/3/4/5-state-mutation: all Mara-mutating tests grouped so xdist loadscope
# pins them to a single worker (avoids concurrent state races between tests). ----------
class TestMaraStateWiring:
    MANAGER_IDS = ["store_manager", "restaurant_manager", "logistics_manager"]

    def test_rate_scales_inversely_with_reputation(self, admin_token, mara_token, mara_id):
        orig = _get_player(admin_token, mara_id)
        orig_rep = orig.get("reputation", 50)
        try:
            _admin_set(admin_token, mara_id, reputation=10)
            r_lo = requests.get(f"{API}/bank", headers=_hdr(mara_token), timeout=15).json()
            _admin_set(admin_token, mara_id, reputation=50)
            r_mid = requests.get(f"{API}/bank", headers=_hdr(mara_token), timeout=15).json()
            _admin_set(admin_token, mara_id, reputation=100)
            r_hi = requests.get(f"{API}/bank", headers=_hdr(mara_token), timeout=15).json()

            lo, mid, hi = r_lo["interest_daily"], r_mid["interest_daily"], r_hi["interest_daily"]
            assert lo > mid > hi, f"expected lo>mid>hi, got lo={lo} mid={mid} hi={hi}"
            assert abs(mid - 0.015) < 1e-6, f"neutral rep should be base 0.015, got {mid}"
        finally:
            _admin_set(admin_token, mara_id, reputation=orig_rep)

    def test_high_social_status_flips_vip_and_raises_limit(
            self, admin_token, mara_token, mara_id):
        orig = _get_player(admin_token, mara_id)
        orig_soc = orig.get("social_status", 10)
        # ensure legal is high so credit isn't frozen from stray state
        orig_legal = orig.get("legal_reputation", 100)
        try:
            _admin_set(admin_token, mara_id, legal_reputation=100)
            _admin_set(admin_token, mara_id, social_status=10)
            low = requests.get(f"{API}/bank", headers=_hdr(mara_token), timeout=15).json()
            _admin_set(admin_token, mara_id, social_status=80)
            hi = requests.get(f"{API}/bank", headers=_hdr(mara_token), timeout=15).json()

            assert low["vip"] is False, f"vip should be False at social=10, got {low['vip']}"
            assert hi["vip"] is True, f"vip should be True at social=80, got {hi['vip']}"
            assert hi["credit_limit"] > low["credit_limit"], (
                f"credit_limit should rise with social_status: low={low['credit_limit']} hi={hi['credit_limit']}"
            )
            assert hi["credit_available"] >= low["credit_available"], (
                f"credit_available should not decrease: low={low['credit_available']} hi={hi['credit_available']}"
            )
            low_ss = (low.get("factors") or {}).get("social_standing", 0)
            hi_ss = (hi.get("factors") or {}).get("social_standing", 0)
            assert hi_ss > low_ss, f"factors.social_standing should rise: low={low_ss} hi={hi_ss}"
        finally:
            _admin_set(admin_token, mara_id, social_status=orig_soc, legal_reputation=orig_legal)

    def test_manager_jobs_expose_min_reputation(self, mara_token):
        r = requests.get(f"{API}/jobs", headers=_hdr(mara_token), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        jobs = body.get("jobs") if isinstance(body, dict) else body
        by_id = {j.get("id"): j for j in (jobs or []) if isinstance(j, dict)}
        for mid_job, expected in [("store_manager", 60), ("restaurant_manager", 55),
                                  ("logistics_manager", 60)]:
            assert mid_job in by_id, f"{mid_job} missing from /api/jobs"
            req = (by_id[mid_job].get("requirements") or {})
            assert req.get("min_reputation") == expected, (
                f"{mid_job} min_reputation expected {expected}, got {req.get('min_reputation')}"
            )

    def test_low_reputation_player_blocked_from_manager_apply(
            self, admin_token, mara_token, mara_id):
        orig = _get_player(admin_token, mara_id)
        orig_rep = orig.get("reputation", 50)
        try:
            _admin_set(admin_token, mara_id, reputation=20)  # well below 55/60
            r = requests.post(f"{API}/jobs/store_manager/apply",
                              headers=_hdr(mara_token), json={}, timeout=15)
            # Must be rejected. Requirement chain will surface first failing check.
            assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"
            print(f"low-rep manager apply blocked with: {r.text}")
        finally:
            _admin_set(admin_token, mara_id, reputation=orig_rep)

    def test_loan_flow_shows_daily_interest_cost_matching_rate(
            self, admin_token, mara_token, mara_id):
        orig = _get_player(admin_token, mara_id)
        orig_rep = orig.get("reputation", 50)
        orig_debt = orig.get("debt", 0)
        orig_legal = orig.get("legal_reputation", 100)
        try:
            _admin_set(admin_token, mara_id, debt=0, reputation=70, legal_reputation=100)
            bank_before = requests.get(f"{API}/bank", headers=_hdr(mara_token), timeout=15).json()
            rate_before = bank_before["interest_daily"]
            avail = bank_before.get("credit_available", 0)
            loan_amt = min(200, max(50, int(avail * 0.05)))
            if loan_amt <= 0 or avail < loan_amt:
                pytest.skip("no credit available for mara in this env")
            r = requests.post(f"{API}/bank/loan",
                              headers=_hdr(mara_token),
                              json={"amount": loan_amt}, timeout=15)
            assert r.status_code == 200, f"loan failed: {r.status_code} {r.text}"
            body = r.json()
            assert body.get("ok") is True
            assert body["debt"] >= loan_amt - 0.01

            bank_after = requests.get(f"{API}/bank", headers=_hdr(mara_token), timeout=15).json()
            assert bank_after["debt"] >= loan_amt - 0.01
            expected = round(bank_after["debt"] * bank_after["interest_daily"], 2)
            assert abs(bank_after["daily_interest_cost"] - expected) < 0.05, (
                f"daily_interest_cost {bank_after['daily_interest_cost']} != debt*rate {expected}"
            )
            assert bank_after["interest_daily"] == rate_before

            rp = requests.post(f"{API}/bank/repay",
                               headers=_hdr(mara_token),
                               json={"amount": loan_amt}, timeout=15)
            assert rp.status_code == 200, rp.text
        finally:
            _admin_set(admin_token, mara_id, reputation=orig_rep, debt=orig_debt,
                       legal_reputation=orig_legal)

    def test_game_state_resolves_with_low_legal_reputation(
            self, admin_token, mara_token, mara_id):
        orig = _get_player(admin_token, mara_id)
        orig_legal = orig.get("legal_reputation", 100)
        orig_susp = orig.get("criminal_suspicion", 0)
        try:
            _admin_set(admin_token, mara_id, legal_reputation=10, criminal_suspicion=50)
            for _ in range(3):
                r = requests.get(f"{API}/game/state", headers=_hdr(mara_token), timeout=20)
                assert r.status_code == 200, f"game/state 500 with low legal: {r.status_code} {r.text[:400]}"
                body = r.json()
                assert "player" in body
        finally:
            _admin_set(admin_token, mara_id, legal_reputation=orig_legal,
                       criminal_suspicion=orig_susp)


# ---------- Read-only underworld tests (use Mara + Dovan; no Mara mutation) ----------
class TestUnderworldAccess:
    def test_underworld_status_locked_for_mara(self, mara_token):
        r = requests.get(f"{API}/underworld/status", headers=_hdr(mara_token), timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "access" in data
        assert data["access"] is False, f"mara should be locked: {data}"

    def test_underworld_unlocked_for_dovan(self, dovan_token):
        r = requests.get(f"{API}/underworld/status", headers=_hdr(dovan_token), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("access") is True

    def test_illegal_actions_listed_for_dovan(self, dovan_token):
        r = requests.get(f"{API}/illegal-actions", headers=_hdr(dovan_token), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        actions = body.get("actions") if isinstance(body, dict) else body
        if isinstance(body, dict) and body.get("access") is False:
            pytest.fail("dovan should have access to illegal-actions")
        assert actions is not None
        assert isinstance(actions, list)
        assert len(actions) > 0


# ---------- Regression smoke (read-only) ----------
class TestRegressionSmoke:
    def test_game_state(self, mara_token):
        r = requests.get(f"{API}/game/state", headers=_hdr(mara_token), timeout=15)
        assert r.status_code == 200, r.text

    def test_bank(self, mara_token):
        r = requests.get(f"{API}/bank", headers=_hdr(mara_token), timeout=15)
        assert r.status_code == 200, r.text

    def test_jobs(self, mara_token):
        r = requests.get(f"{API}/jobs", headers=_hdr(mara_token), timeout=15)
        assert r.status_code == 200, r.text

    def test_shop_stores(self, mara_token):
        r = requests.get(f"{API}/shop/stores", headers=_hdr(mara_token), timeout=15)
        assert r.status_code == 200, r.text
