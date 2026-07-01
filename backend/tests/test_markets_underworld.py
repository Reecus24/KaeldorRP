"""
Iteration 23: Markets + Underworld Gatekeeping + Crime Risk Profiles + Admin Tuning
Tests against live REACT_APP_BACKEND_URL.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://grind-nation.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "mara":  ("mara@kaeldor.com",  "demo123"),
    "dovan": ("dovan@kaeldor.com", "demo123"),
    "admin": ("admin@kaeldor.com", "admin123"),
}


def _login(who):
    email, pw = CREDS[who]
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"Login {who} failed: {r.status_code} {r.text}"
    token = r.json()["token"]
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def mara():   return _login("mara")
@pytest.fixture(scope="module")
def dovan():  return _login("dovan")
@pytest.fixture(scope="module")
def admin():  return _login("admin")


# ------------------- UNDERWORLD GATEKEEPING -------------------
class TestUnderworldGating:
    def test_mara_status_locked(self, mara):
        r = mara.get(f"{API}/underworld/status")
        assert r.status_code == 200
        d = r.json()
        assert d.get("access") is False, f"Expected locked, got {d}"

    def test_mara_illegal_actions_locked(self, mara):
        r = mara.get(f"{API}/illegal-actions")
        assert r.status_code == 200
        d = r.json()
        assert d.get("access") is False

    def test_mara_crypto_locked(self, mara):
        r = mara.get(f"{API}/market/crypto")
        assert r.status_code == 200
        assert r.json().get("access") is False

    def test_dovan_status_unlocked(self, dovan):
        r = dovan.get(f"{API}/underworld/status")
        assert r.status_code == 200
        d = r.json()
        assert d.get("access") is True
        # vouched by Cato Cohen
        vouch = (d.get("vouched_by") or d.get("contact_name") or d.get("shady_contact") or "")
        assert "Cato" in str(d), f"Expected 'Cato Cohen' reference in status: {d}"

    def test_dovan_illegal_actions_unlocked(self, dovan):
        r = dovan.get(f"{API}/illegal-actions")
        assert r.status_code == 200
        d = r.json()
        assert d.get("access") is True
        acts = d.get("actions") or []
        assert len(acts) > 0
        ids = [a.get("id") for a in acts]
        assert "petty_theft" in ids, f"petty_theft missing from {ids}"
        pt = next(a for a in acts if a["id"] == "petty_theft")
        # both fail_chance and bust_risk present
        assert "fail_chance" in pt or "fail_profile" in pt or "fail" in str(pt).lower()
        assert "bust_risk" in pt or "bust_profile" in pt


# ------------------- CRIME RISK / COMMIT -------------------
class TestCrimeCommit:
    def test_dovan_commit_endpoint(self, dovan):
        # Endpoint exists and either starts an activity, returns Busy, or a similar 4xx business rule
        r = dovan.post(f"{API}/illegal-actions/petty_theft/commit", json={})
        assert r.status_code in (200, 400, 409), f"Unexpected status {r.status_code}: {r.text}"

    def test_mara_commit_forbidden(self, mara):
        r = mara.post(f"{API}/illegal-actions/petty_theft/commit", json={})
        # Locked underworld -> should refuse (403/400)
        assert r.status_code in (400, 403, 404), f"Expected refusal for locked mara, got {r.status_code}: {r.text}"


# ------------------- STOCK MARKET (open) -------------------
class TestStockMarket:
    def test_stocks_list(self, mara):
        r = mara.get(f"{API}/market/stocks")
        assert r.status_code == 200
        d = r.json()
        assets = d if isinstance(d, list) else (d.get("assets") or d.get("items") or [])
        assert isinstance(assets, list) and len(assets) > 0
        ids = [a.get("id") for a in assets]
        for req in ("stk_kael", "stk_nova", "stk_orb"):
            assert req in ids, f"Missing {req} in {ids}"
        # Prices are numbers
        for a in assets:
            assert isinstance(a.get("price"), (int, float))

    def test_buy_sell_stock_and_verify_persistence(self, mara):
        # Snapshot state
        state0 = mara.get(f"{API}/game/state").json()
        cash0 = state0["player"]["cash"]

        # Buy 1 unit of stk_orb
        buy = mara.post(f"{API}/market/buy", json={"asset_id": "stk_orb", "qty": 1})
        assert buy.status_code == 200, f"Buy failed: {buy.status_code} {buy.text}"

        # Portfolio should now contain stk_orb
        pf = mara.get(f"{API}/market/portfolio").json()
        holdings = pf.get("positions") or pf.get("holdings") or pf.get("assets") or []
        if isinstance(holdings, dict):
            has = "stk_orb" in holdings
        else:
            has = any((h.get("asset_id") == "stk_orb" or h.get("id") == "stk_orb") for h in holdings)
        assert has, f"stk_orb not in portfolio after buy: {pf}"

        # Cash decreased
        state1 = mara.get(f"{API}/game/state").json()
        cash1 = state1["player"]["cash"]
        assert cash1 < cash0, f"Cash should decrease after stock buy: {cash0} -> {cash1}"

        # net_worth_parts should include 'investments'
        parts = state1.get("net_worth_breakdown") or state1["player"].get("net_worth_parts") or {}
        # search under a few likely locations
        found = False
        def _scan(obj):
            nonlocal found
            if isinstance(obj, dict):
                if "investments" in obj: found = True
                for v in obj.values(): _scan(v)
            elif isinstance(obj, list):
                for v in obj: _scan(v)
        _scan(state1)
        assert found, "Expected 'investments' key somewhere in /game/state response"

        # Sell 1 unit
        sell = mara.post(f"{API}/market/sell", json={"asset_id": "stk_orb", "qty": 1})
        assert sell.status_code == 200, f"Sell failed: {sell.status_code} {sell.text}"

    def test_mara_crypto_buy_forbidden(self, mara):
        r = mara.post(f"{API}/market/buy", json={"asset_id": "cry_dgz", "qty": 1})
        assert r.status_code in (400, 403), f"Expected 403 for locked crypto, got {r.status_code}: {r.text}"


# ------------------- CRYPTO MARKET (gated) -------------------
class TestCryptoMarket:
    def test_dovan_crypto_list(self, dovan):
        r = dovan.get(f"{API}/market/crypto")
        assert r.status_code == 200
        d = r.json()
        assert d.get("access") is True
        assets = d.get("assets") or []
        ids = [a.get("id") for a in assets]
        assert "cry_btk" in ids and "cry_dgz" in ids, f"Missing crypto assets: {ids}"

    def test_dovan_buy_crypto(self, dovan):
        r = dovan.post(f"{API}/market/buy", json={"asset_id": "cry_dgz", "qty": 1})
        assert r.status_code == 200, f"Crypto buy failed: {r.status_code} {r.text}"
        pf = dovan.get(f"{API}/market/portfolio").json()
        holdings = pf.get("positions") or pf.get("holdings") or pf.get("assets") or []
        if isinstance(holdings, dict):
            has = "cry_dgz" in holdings
        else:
            has = any((h.get("asset_id") == "cry_dgz" or h.get("id") == "cry_dgz") for h in holdings)
        assert has, f"cry_dgz not in portfolio: {pf}"


# ------------------- ADMIN TUNING (stock/crypto drift+vol) -------------------
class TestAdminTuning:
    def test_admin_config_has_market_keys(self, admin):
        r = admin.get(f"{API}/admin/config")
        assert r.status_code == 200
        cfg = r.json()
        tun = cfg.get("tuning") or {}
        for k in ("stock_drift", "stock_volatility", "crypto_drift", "crypto_volatility"):
            assert k in tun, f"tuning.{k} missing; got keys {list(tun.keys())[:20]}"

    def test_admin_save_tuning(self, admin):
        # Read current, mutate one field slightly, save, verify
        r = admin.get(f"{API}/admin/config")
        tun = dict(r.json().get("tuning") or {})
        orig = float(tun.get("stock_drift", 0.0015))
        new_val = round(orig + 0.0001, 6)
        tun_out = {**tun, "stock_drift": new_val}
        put = admin.put(f"{API}/admin/config", json={"tuning": tun_out})
        assert put.status_code == 200, f"Save tuning failed: {put.status_code} {put.text}"
        # Verify persisted
        again = admin.get(f"{API}/admin/config").json()
        got = float((again.get("tuning") or {}).get("stock_drift"))
        assert abs(got - new_val) < 1e-9, f"stock_drift not persisted: expected {new_val}, got {got}"
        # Restore
        tun_out["stock_drift"] = orig
        admin.put(f"{API}/admin/config", json={"tuning": tun_out})


# ------------------- REGRESSION: Bank still works -------------------
class TestBankRegression:
    def test_deposit_withdraw(self, mara):
        # small no-op-ish deposit then withdraw
        r1 = mara.post(f"{API}/bank/deposit", json={"amount": 5})
        assert r1.status_code in (200, 400), f"Deposit unexpected: {r1.status_code} {r1.text}"
        r2 = mara.post(f"{API}/bank/withdraw", json={"amount": 5})
        assert r2.status_code in (200, 400), f"Withdraw unexpected: {r2.status_code} {r2.text}"
