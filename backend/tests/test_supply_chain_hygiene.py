"""
Iteration 13 tests: Hygiene removal + Supply-chain business rewrite.

Covers:
- Hygiene fully removed from /api/game/state and /api/actions
- Supply-chain P&L math consistency on business detail
- No instant bankruptcy after buying a fresh business
- Rename endpoint validation
- Buy-materials + restock-settings endpoints
- Unified worker projections (player + NPC) return units_per_hour/margin_per_unit
- Player employment endpoint for Mara
"""
import os
import random
import string
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

DOVAN = ("dovan@kaeldor.com", "demo123")
MARA = ("mara@kaeldor.com", "demo123")
KIRI = ("kiri@kaeldor.com", "demo123")
DOVAN_KIOSK_ID = "249566f3664b40a9b9934c150c713de2"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def dovan():
    return _login(*DOVAN)


@pytest.fixture(scope="module")
def mara():
    return _login(*MARA)


@pytest.fixture(scope="module")
def kiri():
    return _login(*KIRI)


# ============ HYGIENE FULLY REMOVED ============

class TestHygieneRemoved:
    def test_game_state_has_no_hygiene(self, dovan):
        r = dovan.get(f"{API}/game/state", timeout=15)
        assert r.status_code == 200
        state = r.json()
        player = state.get("player") or state
        # No 'hygiene' key anywhere in the player doc
        assert "hygiene" not in player, f"'hygiene' still present in player: {list(player.keys())}"
        # Confirm the expected needs are present
        needs_keys = {"energy", "hunger", "mood", "stress", "health"}
        # fatigue is derived from energy in some builds; treat softly
        for k in needs_keys:
            assert k in player, f"missing expected need '{k}'"

    def test_actions_have_no_shower_or_hygiene(self, dovan):
        r = dovan.get(f"{API}/actions", timeout=15)
        assert r.status_code == 200
        acts = r.json()
        assert isinstance(acts, list)
        for a in acts:
            aid = (a.get("id") or "").lower()
            name = (a.get("name") or "").lower()
            assert "shower" not in aid, f"'shower' action still present: {a}"
            assert "shower" not in name
            effects = a.get("effects") or {}
            assert "hygiene" not in effects, f"action {aid} has hygiene effect: {effects}"


# ============ SUPPLY-CHAIN P&L (owner view) ============

class TestSupplyChainPnL:
    def test_business_detail_supply_chain_shape(self, dovan):
        r = dovan.get(f"{API}/businesses/{DOVAN_KIOSK_ID}", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        b = data["business"]
        m = data["metrics"]

        # Supply-chain fields on the business
        assert "product" in b and isinstance(b["product"], dict), "business.product missing"
        assert b["product"].get("name"), "product.name missing"
        assert b["product"].get("price") is not None
        assert "recipe" in b and isinstance(b["recipe"], list) and len(b["recipe"]) >= 1
        for ing in b["recipe"]:
            assert "id" in ing and "cost" in ing and "qty" in ing
        assert "materials" in b and isinstance(b["materials"], dict)
        assert "products" in b
        assert b.get("bankrupt") is False, f"Dovan's kiosk marked bankrupt: {b.get('bankrupt')}"
        assert "restock_target" in b
        assert "auto_restock" in b

        # Metrics: per-day tiles
        for k in ("net_day", "rev_day", "material_day", "wage_per_day"):
            assert k in m, f"metrics missing {k}: keys={list(m.keys())}"
        # Math consistency: rev - materials - wages ≈ net
        expected_net = round(m["rev_day"] - m["material_day"] - m["wage_per_day"], 2)
        got_net = round(m["net_day"], 2)
        # Allow small float tolerance
        assert abs(expected_net - got_net) < 0.5, (
            f"P&L not internally consistent: rev {m['rev_day']} - mats {m['material_day']} "
            f"- wages {m['wage_per_day']} = {expected_net}, but net_day={got_net}"
        )


# ============ NO INSTANT BANKRUPTCY ============

class TestBuyBusinessNoBankruptcy:
    def test_buy_kiosk_is_not_bankrupt(self, kiri):
        # Find a buyable type from market
        r = kiri.get(f"{API}/businesses/market", timeout=15)
        assert r.status_code == 200
        market = r.json()
        # Choose 'kiosk' if available else first item
        type_id = None
        for t in market:
            if (t.get("id") or "").lower() == "kiosk":
                type_id = t["id"]; break
        if type_id is None and market:
            type_id = market[0]["id"]
        assert type_id, "no purchasable business types available"

        # Ensure Kiri has enough cash — top up if needed via existing endpoints (skip if too poor)
        state = kiri.get(f"{API}/game/state", timeout=15).json()
        player = state.get("player") or state
        # Find cheapest affordable type
        wealth = player.get("cash", 0) + player.get("bank", 0)
        market_sorted = sorted(market, key=lambda t: t.get("price", 999999))
        type_id = None
        for t in market_sorted:
            if t.get("price", 999999) <= wealth:
                type_id = t["id"]; break
        if type_id is None:
            pytest.skip(f"Kiri (wealth ${wealth}) cannot afford any business in market")

        rb = kiri.post(f"{API}/businesses/{type_id}/buy", timeout=15)
        if rb.status_code == 400 and ("afford" in rb.text.lower() or "cash" in rb.text.lower()):
            pytest.skip(f"Insufficient funds to buy: {rb.text}")
        assert rb.status_code == 200, f"buy failed: {rb.status_code} {rb.text}"

        owned = kiri.get(f"{API}/businesses/owned", timeout=15).json()
        assert isinstance(owned, list) and len(owned) >= 1
        new_biz = owned[-1]  # last purchased
        assert new_biz.get("bankrupt") is False, f"NEW business bankrupt at t=0: {new_biz}"
        assert new_biz.get("debt", 0) == 0
        assert isinstance(new_biz.get("materials"), dict), "materials missing"
        # Seeded ingredient stock > 0 (at least one ingredient has qty)
        assert sum(new_biz["materials"].values()) > 0, f"materials not seeded: {new_biz['materials']}"
        assert new_biz.get("products", 0) == 0
        assert isinstance(new_biz.get("recipe"), list) and len(new_biz["recipe"]) >= 1


# ============ RENAME ============

class TestRename:
    def test_rename_valid(self, dovan):
        r = dovan.get(f"{API}/businesses/{DOVAN_KIOSK_ID}", timeout=15)
        assert r.status_code == 200
        original = r.json()["business"]["name"]

        new_name = "Dovan's Kiosk QA"
        rr = dovan.post(f"{API}/businesses/{DOVAN_KIOSK_ID}/rename", json={"name": new_name}, timeout=15)
        assert rr.status_code == 200, rr.text
        assert rr.json().get("name") == new_name

        # Verify persistence
        after = dovan.get(f"{API}/businesses/{DOVAN_KIOSK_ID}", timeout=15).json()["business"]
        assert after["name"] == new_name

        # Restore original name
        restore = dovan.post(f"{API}/businesses/{DOVAN_KIOSK_ID}/rename", json={"name": original}, timeout=15)
        assert restore.status_code == 200

    def test_rename_too_short_returns_400(self, dovan):
        r = dovan.post(f"{API}/businesses/{DOVAN_KIOSK_ID}/rename", json={"name": "A"}, timeout=15)
        assert r.status_code == 400, f"expected 400 for too-short name, got {r.status_code}: {r.text}"


# ============ BUY MATERIALS + RESTOCK SETTINGS ============

class TestMaterialsAndRestock:
    def test_restock_settings_update(self, dovan):
        r = dovan.post(f"{API}/businesses/{DOVAN_KIOSK_ID}/restock-settings",
                       json={"auto_restock": True, "restock_target": 12.0}, timeout=15)
        assert r.status_code == 200, r.text
        # Verify
        b = dovan.get(f"{API}/businesses/{DOVAN_KIOSK_ID}", timeout=15).json()["business"]
        assert b.get("auto_restock") is True
        assert abs(b.get("restock_target", 0) - 12.0) < 0.001

    def test_buy_materials(self, dovan):
        # First set a large target so buy has work to do
        dovan.post(f"{API}/businesses/{DOVAN_KIOSK_ID}/restock-settings",
                   json={"restock_target": 30.0}, timeout=15)
        before = dovan.get(f"{API}/businesses/{DOVAN_KIOSK_ID}", timeout=15).json()["business"]
        mats_before = dict(before.get("materials") or {})

        r = dovan.post(f"{API}/businesses/{DOVAN_KIOSK_ID}/buy-materials",
                       json={"units": 30.0}, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert "cost" in body

        # Verify stock topped up
        after = dovan.get(f"{API}/businesses/{DOVAN_KIOSK_ID}", timeout=15).json()["business"]
        mats_after = after.get("materials") or {}
        # Each ingredient level should be >= before (never decreased by top-up)
        for k, v in mats_before.items():
            assert mats_after.get(k, 0) + 0.001 >= v, f"ingredient {k} decreased after restock"


# ============ UNIFIED WORKER PROJECTIONS ============

class TestUnifiedProjections:
    REQUIRED_FIELDS = {"units_per_hour", "margin_per_unit", "productivity",
                       "rev_per_hour", "wage_per_hour", "net_per_hour"}

    def test_player_employee_projection_shape(self, dovan):
        r = dovan.get(f"{API}/businesses/{DOVAN_KIOSK_ID}/player-employees", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        emps = data if isinstance(data, list) else data.get("employees") or data.get("player_employees") or []
        assert len(emps) >= 1, f"expected Mara as player cashier; got {emps}"
        # Find Mara (field is `employee_name` in this API)
        mara_row = None
        for e in emps:
            nm = (e.get("employee_name") or e.get("player_name") or e.get("name") or "").lower()
            if "mara" in nm:
                mara_row = e; break
        assert mara_row is not None, f"Mara not found in player-employees list: {emps}"
        proj = mara_row.get("projection")
        assert isinstance(proj, dict), f"player projection missing: {mara_row}"
        missing = self.REQUIRED_FIELDS - set(proj.keys())
        assert not missing, f"player projection missing fields: {missing}. got={list(proj.keys())}"
        # Math sanity: rev = units * margin (approx), net = rev - wage
        u, m = proj["units_per_hour"], proj["margin_per_unit"]
        rev, wage, net = proj["rev_per_hour"], proj["wage_per_hour"], proj["net_per_hour"]
        # rev_per_hour should reflect units*margin*productivity roughly
        assert abs(rev - (u * m * proj.get("productivity", 1))) < max(1.0, rev * 0.15 + 0.5), \
            f"rev/h not ~ u*m*prod: rev={rev} u={u} m={m} prod={proj.get('productivity')}"
        assert abs((rev - wage) - net) < 0.51, f"net/h != rev - wage: {rev} - {wage} = {rev-wage} vs {net}"

    def test_npc_employee_projection_shape(self, dovan):
        r = dovan.get(f"{API}/businesses/{DOVAN_KIOSK_ID}/employees", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        emps = data.get("employees") if isinstance(data, dict) else data
        if not emps:
            pytest.skip("No NPC employees on Dovan's kiosk to test projection")
        for e in emps:
            proj = e.get("projection")
            assert isinstance(proj, dict), f"NPC {e.get('id')} missing projection"
            missing = self.REQUIRED_FIELDS - set(proj.keys())
            assert not missing, f"NPC projection missing fields: {missing}"


# ============ PLAYER WAGE SWEEP ============

class TestPlayerEmployment:
    def test_mara_employment_and_get_state(self, mara):
        # Repeated get_state must not error
        for _ in range(3):
            gs = mara.get(f"{API}/game/state", timeout=15)
            assert gs.status_code == 200, gs.text

        r = mara.get(f"{API}/jobs/employment", timeout=15)
        assert r.status_code == 200, r.text
        emp = r.json()
        # Response shape: {"employments": [...], "applications": [...]}
        if isinstance(emp, dict) and "employments" in emp:
            employments = emp["employments"]
            assert len(employments) >= 1, "Mara should have >=1 employment"
            row = next((e for e in employments if e.get("business_id") == DOVAN_KIOSK_ID), employments[0])
        elif isinstance(emp, list):
            row = next((e for e in emp if e.get("business_id") == DOVAN_KIOSK_ID), emp[0])
        else:
            row = emp
        assert row, f"unexpected employment shape: {emp}"
        assert "wage_per_hour" in row, f"wage_per_hour missing: {row}"
        assert "on_shift" in row
        # 'today' key present (earnings tracker) — schema is dict with hours/wage/revenue/net
        assert "today" in row, f"today earnings field missing: keys={list(row.keys())}"
        today = row["today"]
        assert isinstance(today, dict) and "wage" in today, f"today.wage missing: {today}"
