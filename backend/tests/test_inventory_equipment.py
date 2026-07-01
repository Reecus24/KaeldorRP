"""Phase 4 Inventory & Equipment API tests.
Covers: GET /inventory flags, GET /equipment slots, buy->equip->unequip flow,
slot replacement, and use-consumable vs equipment gating.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def mara_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": "mara@kaeldor.com", "password": "demo123"})
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def dovan_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": "dovan@kaeldor.com", "password": "demo123"})
    assert r.status_code == 200
    tok = r.json().get("token") or r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


def _get_state(client):
    r = client.get(f"{API}/game/state")
    assert r.status_code == 200, r.text
    return r.json()


def _get_money(client):
    st = _get_state(client)
    p = st.get("player", st)
    return (p.get("cash", 0) or 0) + (p.get("bank", 0) or 0)


def _buy(client, iid, qty=1):
    return client.post(f"{API}/shop/buy", json={"item_id": iid, "qty": qty})


def test_shop_lists_expected_categories(mara_client):
    r = mara_client.get(f"{API}/shop/items")
    assert r.status_code == 200
    items = r.json()
    ids = {i["id"] for i in items}
    # Required items exist
    for iid in ["energy_drink", "first_aid_kit", "sleeping_pills",
                "nice_clothes", "business_suit", "luxury_watch",
                "toolbelt", "athletic_gear"]:
        assert iid in ids, f"missing shop item {iid}"
    # No legacy 'gift' item
    assert "gift" not in ids


def test_equipment_endpoint_returns_5_slots(mara_client):
    r = mara_client.get(f"{API}/equipment")
    assert r.status_code == 200
    data = r.json()
    slot_ids = {s["slot"] for s in data.get("slots", [])}
    assert slot_ids == {"outfit", "accessory", "phone", "computer", "work_gear"}, slot_ids
    assert "bonuses" in data


def test_inventory_flags_and_equip_unequip_flow(mara_client):
    # Ensure outfit slot is empty first (mara may have nice_clothes equipped from prior test)
    eq = mara_client.get(f"{API}/equipment").json()
    outfit_slot = next(s for s in eq["slots"] if s["slot"] == "outfit")
    if outfit_slot.get("item"):
        u = mara_client.post(f"{API}/equipment/outfit/unequip")
        assert u.status_code == 200

    # Ensure nice_clothes is in inventory; buy if missing
    inv = mara_client.get(f"{API}/inventory").json()
    have_nice = any(i["id"] == "nice_clothes" for i in inv)
    if not have_nice:
        money = _get_money(mara_client)
        if money < 120:
            pytest.skip(f"mara has ${money}, needs $120 for nice_clothes")
        b = _buy(mara_client, "nice_clothes")
        assert b.status_code == 200, b.text
        inv = mara_client.get(f"{API}/inventory").json()

    nice = next(i for i in inv if i["id"] == "nice_clothes")
    assert nice.get("equippable") is True
    assert nice.get("equipped") is False
    assert nice.get("usable") in (False, None)  # apparel not usable

    # Equip
    r = mara_client.post(f"{API}/inventory/nice_clothes/equip")
    assert r.status_code == 200, r.text
    assert r.json().get("slot") == "outfit"

    # Verify equipment endpoint reflects it + bonuses
    eq2 = mara_client.get(f"{API}/equipment").json()
    outfit = next(s for s in eq2["slots"] if s["slot"] == "outfit")
    assert outfit["item"] is not None
    assert outfit["item"]["id"] == "nice_clothes"
    b = eq2["bonuses"]
    assert b.get("social_status_floor", 0) >= 12
    assert b.get("social_success", 0) >= 0.05
    assert b.get("tip_rate", 0) >= 0.03

    # Inventory should now mark equipped
    inv2 = mara_client.get(f"{API}/inventory").json()
    nice2 = next(i for i in inv2 if i["id"] == "nice_clothes")
    assert nice2["equipped"] is True

    # Unequip
    u = mara_client.post(f"{API}/equipment/outfit/unequip")
    assert u.status_code == 200
    eq3 = mara_client.get(f"{API}/equipment").json()
    outfit3 = next(s for s in eq3["slots"] if s["slot"] == "outfit")
    assert outfit3["item"] is None
    assert eq3["bonuses"].get("social_status_floor", 0) < 12


def test_slot_replacement_outfit(mara_client):
    # Ensure both items in inventory
    inv = mara_client.get(f"{API}/inventory").json()
    if not any(i["id"] == "nice_clothes" for i in inv):
        _buy(mara_client, "nice_clothes")
    if not any(i["id"] == "business_suit" for i in inv):
        money = _get_money(mara_client)
        if money < 480:
            pytest.skip(f"mara has ${money}, needs $480 for business_suit")
        b = _buy(mara_client, "business_suit")
        assert b.status_code == 200, b.text

    # Equip nice_clothes
    r1 = mara_client.post(f"{API}/inventory/nice_clothes/equip")
    assert r1.status_code == 200
    # Equip business_suit -> should replace
    r2 = mara_client.post(f"{API}/inventory/business_suit/equip")
    assert r2.status_code == 200
    eq = mara_client.get(f"{API}/equipment").json()
    outfit = next(s for s in eq["slots"] if s["slot"] == "outfit")
    assert outfit["item"]["id"] == "business_suit"
    # nice_clothes should no longer be marked equipped
    inv2 = mara_client.get(f"{API}/inventory").json()
    nice = next(i for i in inv2 if i["id"] == "nice_clothes")
    assert nice["equipped"] is False
    # Cleanup: unequip
    mara_client.post(f"{API}/equipment/outfit/unequip")


def test_use_equipment_rejected(mara_client):
    inv = mara_client.get(f"{API}/inventory").json()
    if not any(i["id"] == "nice_clothes" for i in inv):
        _buy(mara_client, "nice_clothes")
    r = mara_client.post(f"{API}/inventory/nice_clothes/use")
    assert r.status_code == 400
    assert "equip" in r.text.lower()


def test_use_consumable_energy_drink(mara_client):
    # Buy 1 energy drink
    money = _get_money(mara_client)
    if money < 5:
        pytest.skip("insufficient funds for energy_drink")
    b = _buy(mara_client, "energy_drink")
    assert b.status_code == 200, b.text
    inv = mara_client.get(f"{API}/inventory").json()
    ed = next((i for i in inv if i["id"] == "energy_drink"), None)
    assert ed is not None
    assert ed.get("usable") is True
    assert ed.get("equippable") is False
    qty_before = ed.get("qty", ed.get("quantity", 1))
    # Use
    u = mara_client.post(f"{API}/inventory/energy_drink/use")
    assert u.status_code == 200, u.text
    inv2 = mara_client.get(f"{API}/inventory").json()
    ed2 = next((i for i in inv2 if i["id"] == "energy_drink"), None)
    qty_after = (ed2 or {}).get("qty", (ed2 or {}).get("quantity", 0)) if ed2 else 0
    assert qty_after == qty_before - 1


def test_dovan_active_perks_data(dovan_client):
    # Dovan has NO social perks -> perks summary should be empty/none
    st = _get_state(dovan_client)
    p = st.get("player", st)
    perks = p.get("social_perks") or p.get("perks") or {}
    active = [k for k, v in (perks.items() if isinstance(perks, dict) else []) if v]
    assert not any("wage" in k or "material" in k for k in active), f"unexpected perks: {perks}"
