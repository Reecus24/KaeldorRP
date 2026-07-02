"""
Iteration 37 tests — Admin City Shops item management + player shop reflection.

Covers:
- GET /api/admin/city-shops returns shops[].items and all_items
- POST /api/admin/city-shops/{shop_id}/items adds an item (200)
- Adding the same item again returns 400
- DELETE /api/admin/city-shops/{shop_id}/items/{item_id} returns 200 and removes it
- Add to non-existent shop -> 404; add non-existent item -> 404
- Player GET /api/shop/stores/{shop_id}/items reflects the change
- Admin endpoints return 403 for a player token
"""

import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@kaeldor.com"
ADMIN_PASS = "admin123"
PLAYER_EMAIL = "mara@kaeldor.com"
PLAYER_PASS = "demo123"

SHOP_ID = "shop_grocery"
ITEM_ID = "first_aid_kit"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def player_session():
    return _login(PLAYER_EMAIL, PLAYER_PASS)


@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_session):
    """Ensure shop_grocery does NOT contain first_aid_kit before and after."""
    admin_session.delete(f"{API}/admin/city-shops/{SHOP_ID}/items/{ITEM_ID}")
    yield
    admin_session.delete(f"{API}/admin/city-shops/{SHOP_ID}/items/{ITEM_ID}")


# ---------------- Admin City Shops GET ----------------
class TestAdminCityShopsGet:
    def test_list_shops_has_items_and_all_items(self, admin_session):
        r = admin_session.get(f"{API}/admin/city-shops")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "all_items" in data, "expected top-level all_items"
        assert isinstance(data["all_items"], list) and len(data["all_items"]) > 0
        shops = data.get("shops") or data.get("city_shops") or []
        assert isinstance(shops, list) and len(shops) > 0
        # Every shop should have an 'items' array
        for shop in shops:
            assert "items" in shop, f"shop {shop.get('id')} missing items"
            assert isinstance(shop["items"], list)
        # shop_grocery must exist
        gro = next((s for s in shops if s.get("id") == SHOP_ID), None)
        assert gro is not None, "shop_grocery not found"
        # first_aid_kit item exists in catalog
        all_ids = [it.get("id") for it in data["all_items"]]
        assert ITEM_ID in all_ids


# ---------------- Admin add/remove item ----------------
class TestAdminAddRemoveItem:
    def test_add_item_success(self, admin_session):
        r = admin_session.post(
            f"{API}/admin/city-shops/{SHOP_ID}/items",
            json={"item_id": ITEM_ID},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Response should include item_ids containing the added item
        item_ids = body.get("item_ids") or body.get("shop", {}).get("item_ids") or []
        assert ITEM_ID in item_ids, f"item_ids missing added item: {body}"

    def test_add_duplicate_returns_400(self, admin_session):
        r = admin_session.post(
            f"{API}/admin/city-shops/{SHOP_ID}/items",
            json={"item_id": ITEM_ID},
        )
        assert r.status_code == 400, f"expected 400 on duplicate, got {r.status_code} {r.text}"

    def test_player_shop_reflects_added_item(self, player_session):
        r = player_session.get(f"{API}/shop/stores/{SHOP_ID}/items")
        assert r.status_code == 200, r.text
        payload = r.json()
        items = payload if isinstance(payload, list) else payload.get("items", [])
        ids = [it.get("id") for it in items]
        assert ITEM_ID in ids, f"first_aid_kit not visible to player after add. ids={ids}"

    def test_delete_item_success(self, admin_session):
        r = admin_session.delete(
            f"{API}/admin/city-shops/{SHOP_ID}/items/{ITEM_ID}"
        )
        assert r.status_code == 200, r.text
        # Verify via GET admin
        g = admin_session.get(f"{API}/admin/city-shops")
        shops = g.json().get("shops") or g.json().get("city_shops") or []
        gro = next((s for s in shops if s.get("id") == SHOP_ID), None)
        ids = [it.get("id") for it in (gro.get("items") or [])]
        assert ITEM_ID not in ids

    def test_player_shop_reflects_removed_item(self, player_session):
        r = player_session.get(f"{API}/shop/stores/{SHOP_ID}/items")
        assert r.status_code == 200
        payload = r.json()
        items = payload if isinstance(payload, list) else payload.get("items", [])
        ids = [it.get("id") for it in items]
        assert ITEM_ID not in ids


# ---------------- Not-found cases ----------------
class TestAdminNotFound:
    def test_add_to_nonexistent_shop(self, admin_session):
        r = admin_session.post(
            f"{API}/admin/city-shops/does_not_exist_shop/items",
            json={"item_id": ITEM_ID},
        )
        assert r.status_code == 404, r.text

    def test_add_nonexistent_item(self, admin_session):
        r = admin_session.post(
            f"{API}/admin/city-shops/{SHOP_ID}/items",
            json={"item_id": "definitely_not_a_real_item_xyz"},
        )
        assert r.status_code == 404, r.text


# ---------------- 403 for player token ----------------
class TestAdminForbidden:
    def test_get_admin_city_shops_forbidden(self, player_session):
        r = player_session.get(f"{API}/admin/city-shops")
        assert r.status_code == 403, f"expected 403, got {r.status_code}"

    def test_post_admin_city_shops_items_forbidden(self, player_session):
        r = player_session.post(
            f"{API}/admin/city-shops/{SHOP_ID}/items",
            json={"item_id": ITEM_ID},
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}"
