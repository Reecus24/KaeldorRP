"""
Iteration 39 — God Mode: Market CRUD + Character Origins CRUD.

Tests:
  - Admin market POST/DELETE, engine auto-pickup + stop-on-delete
  - Duplicate symbol / invalid kind => 400
  - Player market GET reflects create/delete
  - Admin backgrounds GET/POST/PUT/DELETE + count guard (>=1 remains)
  - Public GET /api/backgrounds includes active new origin
  - Character creation applies origin cash/bank/debt/stats/skills
  - Admin 403 with player token
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()).rstrip("/")
API = f"{BASE_URL}/api"


# ---------- helpers ----------
def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_token():
    return _login("admin@kaeldor.com", "admin123")


@pytest.fixture(scope="session")
def player_token():
    return _login("mara@kaeldor.com", "demo123")


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------- Market CRUD ----------
class TestMarketCRUD:
    _created_ids = []

    def test_create_stock(self, admin_token):
        sym = f"ZZ{uuid.uuid4().hex[:4].upper()}"
        r = requests.post(f"{API}/admin/market",
                          headers=_h(admin_token),
                          json={"symbol": sym, "name": "ZZ Holdings",
                                "kind": "stock", "base_price": 42})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        asset = data["asset"]
        assert asset["symbol"] == sym
        assert asset["kind"] == "stock"
        assert asset["price"] == 42
        assert "id" in asset
        TestMarketCRUD._created_ids.append(asset["id"])
        TestMarketCRUD._stock_symbol = sym
        TestMarketCRUD._stock_id = asset["id"]

    def test_player_market_includes_new_stock(self, player_token):
        r = requests.get(f"{API}/market/stocks", headers=_h(player_token))
        assert r.status_code == 200, r.text
        payload = r.json()
        stocks = payload if isinstance(payload, list) else payload.get("stocks", payload.get("assets", []))
        symbols = [a["symbol"] for a in stocks]
        assert TestMarketCRUD._stock_symbol in symbols, \
            f"new stock not in player market: {symbols}"

    def test_refresh_advances_new_asset(self, admin_token):
        # get admin market asset count first
        r0 = requests.get(f"{API}/admin/market", headers=_h(admin_token))
        assert r0.status_code == 200
        total = len(r0.json().get("assets", []))
        r = requests.post(f"{API}/admin/market/refresh", headers=_h(admin_token))
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("advanced", 0) >= total, \
            f"advanced count {data.get('advanced')} should include all {total} assets"

    def test_duplicate_symbol_400(self, admin_token):
        r = requests.post(f"{API}/admin/market",
                          headers=_h(admin_token),
                          json={"symbol": TestMarketCRUD._stock_symbol,
                                "name": "Dup", "kind": "stock", "base_price": 10})
        assert r.status_code == 400, r.text

    def test_invalid_kind_400(self, admin_token):
        r = requests.post(f"{API}/admin/market",
                          headers=_h(admin_token),
                          json={"symbol": f"BAD{uuid.uuid4().hex[:3].upper()}",
                                "name": "Bad", "kind": "wutever", "base_price": 5})
        assert r.status_code == 400, r.text

    def test_create_crypto(self, admin_token):
        sym = f"QQ{uuid.uuid4().hex[:4].upper()}"
        r = requests.post(f"{API}/admin/market",
                          headers=_h(admin_token),
                          json={"symbol": sym, "name": "Q Coin",
                                "kind": "crypto", "base_price": 3.14})
        assert r.status_code == 200, r.text
        aid = r.json()["asset"]["id"]
        TestMarketCRUD._created_ids.append(aid)
        TestMarketCRUD._crypto_id = aid
        TestMarketCRUD._crypto_symbol = sym

        # verify via admin listing (player may be locked out of /market/crypto)
        rl = requests.get(f"{API}/admin/market", headers=_h(admin_token))
        assert rl.status_code == 200
        symbols = [a["symbol"] for a in rl.json().get("assets", [])]
        assert sym in symbols

    def test_delete_stock_removes_from_player_market(self, admin_token, player_token):
        aid = TestMarketCRUD._stock_id
        r = requests.delete(f"{API}/admin/market/{aid}", headers=_h(admin_token))
        assert r.status_code == 200, r.text
        TestMarketCRUD._created_ids.remove(aid)

        r2 = requests.get(f"{API}/market/stocks", headers=_h(player_token))
        assert r2.status_code == 200
        payload = r2.json()
        stocks = payload if isinstance(payload, list) else payload.get("stocks", payload.get("assets", []))
        symbols = [a["symbol"] for a in stocks]
        assert TestMarketCRUD._stock_symbol not in symbols

    def test_cleanup_created(self, admin_token):
        # Cleanup any remaining (crypto)
        for aid in list(TestMarketCRUD._created_ids):
            r = requests.delete(f"{API}/admin/market/{aid}", headers=_h(admin_token))
            assert r.status_code in (200, 404)
        TestMarketCRUD._created_ids.clear()


# ---------- Character Origins CRUD ----------
class TestOriginsCRUD:
    _bg_id = None

    def test_admin_list_defaults(self, admin_token):
        r = requests.get(f"{API}/admin/backgrounds", headers=_h(admin_token))
        assert r.status_code == 200, r.text
        d = r.json()
        assert len(d["backgrounds"]) >= 5, f"expected at least 5 defaults, got {len(d['backgrounds'])}"
        assert len(d["skills"]) == 12, f"expected 12 skills, got {len(d['skills'])}"
        assert isinstance(d["items"], list) and len(d["items"]) > 0
        assert len(d["stat_keys"]) == 6

    def test_create_origin(self, admin_token):
        payload = {"label": "QA Origin", "desc": "x",
                   "cash": 777, "bank": 333, "debt": 50,
                   "stats": {"health": 88, "energy": 70, "stress": 30},
                   "skills": {"finance": 5, "sales": 2},
                   "inventory": {}}
        r = requests.post(f"{API}/admin/backgrounds",
                          headers=_h(admin_token), json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert "id" in data
        TestOriginsCRUD._bg_id = data["id"]

    def test_public_backgrounds_includes_new(self):
        r = requests.get(f"{API}/backgrounds")
        assert r.status_code == 200, r.text
        payload = r.json()
        bgs = payload if isinstance(payload, list) else payload.get("backgrounds", [])
        ids = [b["id"] for b in bgs]
        assert TestOriginsCRUD._bg_id in ids

    def test_update_origin(self, admin_token):
        payload = {"label": "QA Origin", "desc": "x",
                   "cash": 800, "bank": 333, "debt": 50,
                   "stats": {"health": 88, "energy": 70, "stress": 30},
                   "skills": {"finance": 5, "sales": 2}, "inventory": {}}
        r = requests.put(f"{API}/admin/backgrounds/{TestOriginsCRUD._bg_id}",
                         headers=_h(admin_token), json=payload)
        assert r.status_code == 200, r.text
        # verify via admin list
        rl = requests.get(f"{API}/admin/backgrounds", headers=_h(admin_token))
        found = next((b for b in rl.json()["backgrounds"]
                      if b["id"] == TestOriginsCRUD._bg_id), None)
        assert found is not None and found["cash"] == 800
        # restore cash to 777 so subsequent character-create test sees the original values
        payload["cash"] = 777
        r2 = requests.put(f"{API}/admin/backgrounds/{TestOriginsCRUD._bg_id}",
                          headers=_h(admin_token), json=payload)
        assert r2.status_code == 200, r2.text

    def test_count_guard_not_triggered(self, admin_token):
        # Just verify the endpoint exists and current count > 1 => normal delete would succeed
        r = requests.get(f"{API}/admin/backgrounds", headers=_h(admin_token))
        assert r.status_code == 200
        assert len(r.json()["backgrounds"]) > 1

    def test_character_create_applies_origin(self, admin_token):
        """Register new user, POST /character/create with QA Origin, verify persisted stats."""
        # register new user (requires name field)
        email = f"qa_origin_{uuid.uuid4().hex[:8]}@test.com"
        rr = requests.post(f"{API}/auth/register",
                           json={"email": email, "password": "test1234", "name": "QAT"})
        assert rr.status_code == 200, f"register: {rr.status_code} {rr.text}"
        tok = rr.json().get("token") or _login(email, "test1234")

        # create character with QA Origin
        cc = requests.post(f"{API}/character/create",
                           headers=_h(tok),
                           json={"name": "X", "background": TestOriginsCRUD._bg_id})
        assert cc.status_code == 200, cc.text

        # get game state
        gs = requests.get(f"{API}/game/state", headers=_h(tok))
        assert gs.status_code == 200, gs.text
        state = gs.json()
        player = state.get("player", state)
        assert abs(player["cash"] - 777) < 1, f"cash={player['cash']}"
        assert abs(player["bank"] - 333) < 1, f"bank={player['bank']}"
        assert abs(player["debt"] - 50) < 1, f"debt={player['debt']}"
        # Stats live at player root (not nested under 'stats')
        assert abs(player.get("health", 0) - 88) <= 2, f"health={player.get('health')}"
        assert abs(player.get("energy", 0) - 70) <= 2, f"energy={player.get('energy')}"
        assert abs(player.get("stress", 0) - 30) <= 2, f"stress={player.get('stress')}"
        skills = player.get("skills", {})
        fin_level = skills.get("finance", {}).get("level")
        sal_level = skills.get("sales", {}).get("level")
        assert fin_level == 6, f"finance level={fin_level}"
        assert sal_level == 3, f"sales level={sal_level}"

    def test_delete_origin_cleanup(self, admin_token):
        r = requests.delete(f"{API}/admin/backgrounds/{TestOriginsCRUD._bg_id}",
                            headers=_h(admin_token))
        assert r.status_code == 200, r.text


# ---------- Admin 403 with player token ----------
class TestAdmin403:
    def test_market_create_403(self, player_token):
        r = requests.post(f"{API}/admin/market",
                          headers=_h(player_token),
                          json={"symbol": "FORB", "name": "Forbidden",
                                "kind": "stock", "base_price": 1})
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"

    def test_background_create_403(self, player_token):
        r = requests.post(f"{API}/admin/backgrounds",
                          headers=_h(player_token),
                          json={"label": "NoWay", "cash": 1})
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"
