"""Iteration 38 — Backend tests for:
 (1) Shop `price_pct` (replaces discount_pct)
 (2) Admin job reason_strings editor (per-job accept/reject overrides)
 (3) Admin Applications monitor (list, filter, override, validation)
 (4) Admin 403 with player token
"""
import os
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@kaeldor.com", "password": "admin123"}
PLAYER = {"email": "mara@kaeldor.com", "password": "demo123"}


def _login(session, creds):
    r = session.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def admin_sess():
    s = requests.Session()
    _login(s, ADMIN)
    return s


@pytest.fixture(scope="module")
def player_sess():
    s = requests.Session()
    _login(s, PLAYER)
    return s


# ---------------------------------------------------------------- Price % ----
class TestShopPricePct:
    def test_admin_city_shops_returns_price_pct(self, admin_sess):
        r = admin_sess.get(f"{API}/admin/city-shops", timeout=15)
        assert r.status_code == 200
        data = r.json()
        shops = data["shops"]
        grocery = next((s for s in shops if s["id"] == "shop_grocery"), None)
        assert grocery is not None, "shop_grocery must exist"
        assert grocery["items"], "grocery should have items"
        for it in grocery["items"]:
            assert "price_pct" in it, "each item must expose price_pct"
            assert "discount_pct" not in it, "discount_pct should be gone"
            assert isinstance(it["price_pct"], int)

    def test_price_pct_150_flows_to_player_shop(self, admin_sess, player_sess):
        # Get full current shop_grocery
        r = admin_sess.get(f"{API}/admin/city-shops", timeout=15)
        grocery = next(s for s in r.json()["shops"] if s["id"] == "shop_grocery")
        coffee = next(it for it in grocery["items"] if it["id"] == "coffee")
        base = coffee["base_price"]
        assert base == 4, f"expected coffee base $4, got {base}"

        # Build items_config with coffee.price_pct=150
        items_config = {it["id"]: {"capacity": it["capacity"], "price_pct": it["price_pct"]}
                        for it in grocery["items"]}
        items_config["coffee"] = {"capacity": items_config["coffee"]["capacity"], "price_pct": 150}

        put_body = {
            "id": grocery["id"],
            "name": grocery["name"],
            "category": grocery["category"],
            "business_type_id": grocery.get("business_type_id"),
            "location_id": grocery.get("location_id"),
            "opening_hours": grocery.get("opening_hours"),
            "items_config": items_config,
            "item_ids": [it["id"] for it in grocery["items"]],
        }
        pr = admin_sess.put(f"{API}/admin/city-shops/shop_grocery", json=put_body, timeout=15)
        assert pr.status_code == 200, pr.text

        try:
            # Player fetches store items
            gr = player_sess.get(f"{API}/shop/stores/shop_grocery/items", timeout=15)
            assert gr.status_code == 200, gr.text
            payload = gr.json()
            items = payload.get("items") if isinstance(payload, dict) else payload
            p_coffee = next(it for it in items if it["id"] == "coffee")
            assert p_coffee["price_pct"] == 150, f"expected 150, got {p_coffee['price_pct']}"
            assert p_coffee["price"] == 6, f"expected $6 (4×1.5), got {p_coffee['price']}"
            assert p_coffee.get("base_price") == 4
        finally:
            # RESET coffee to 100
            items_config["coffee"] = {"capacity": items_config["coffee"]["capacity"], "price_pct": 100}
            put_body["items_config"] = items_config
            rr = admin_sess.put(f"{API}/admin/city-shops/shop_grocery", json=put_body, timeout=15)
            assert rr.status_code == 200

            # Verify reset
            gr2 = player_sess.get(f"{API}/shop/stores/shop_grocery/items", timeout=15)
            items2 = gr2.json().get("items") if isinstance(gr2.json(), dict) else gr2.json()
            p2 = next(it for it in items2 if it["id"] == "coffee")
            assert p2["price"] == 4 and p2["price_pct"] == 100


# ------------------------------------------------------ Reason string editor ----
class TestJobReasonStrings:
    def test_get_job_applications_defaults(self, admin_sess):
        r = admin_sess.get(f"{API}/admin/job-applications", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "accept_reason_keys" in data and "reject_reason_keys" in data
        assert set(["skills", "education", "reputation"]).issubset(set(data["accept_reason_keys"]))
        assert set(["criminal_record", "low_skill"]).issubset(set(data["reject_reason_keys"]))
        cashier = next(j for j in data["jobs"] if j["id"] == "cashier")
        # Reason strings merged with defaults
        assert set(data["accept_reason_keys"]).issubset(set(cashier["reason_strings"]["accept"].keys()))
        assert set(data["reject_reason_keys"]).issubset(set(cashier["reason_strings"]["reject"].keys()))

    def test_put_cashier_reason_overrides_and_reset(self, admin_sess):
        # Load current cashier
        r = admin_sess.get(f"{API}/admin/job-applications", timeout=15)
        cashier = next(j for j in r.json()["jobs"] if j["id"] == "cashier")

        put_body = {
            "acceptance_base_chance": cashier.get("acceptance_base_chance", 0.5),
            "skill_weight": cashier.get("skill_weight", 1.0),
            "success_response": cashier.get("success_response"),
            "failure_response": cashier.get("failure_response"),
            "reason_strings": {
                "accept": {"skills": "outstanding ability"},
                "reject": {"low_skill": "not enough experience"},
            },
        }
        pr = admin_sess.put(f"{API}/admin/job-applications/cashier", json=put_body, timeout=15)
        assert pr.status_code == 200, pr.text

        # GET confirms persistence + defaults still fill non-overridden keys
        r2 = admin_sess.get(f"{API}/admin/job-applications", timeout=15)
        cashier2 = next(j for j in r2.json()["jobs"] if j["id"] == "cashier")
        assert cashier2["reason_strings"]["accept"]["skills"] == "outstanding ability"
        assert cashier2["reason_strings"]["reject"]["low_skill"] == "not enough experience"
        # Non-overridden keys keep defaults
        assert cashier2["reason_strings"]["accept"]["education"] == "solid education"
        assert cashier2["reason_strings"]["reject"]["criminal_record"] == "your criminal record"

        # RESET (empty overrides), keep base chance 0.5 and skill_weight 1.0
        reset_body = {
            "acceptance_base_chance": 0.5,
            "skill_weight": 1.0,
            "success_response": "Your application for {title} was accepted — the offer is ${wage}/h. Accept it to start working.",
            "failure_response": "Your application for {title} was rejected: {reason}.",
            "reason_strings": {"accept": {}, "reject": {}},
        }
        rr = admin_sess.put(f"{API}/admin/job-applications/cashier", json=reset_body, timeout=15)
        assert rr.status_code == 200


# ------------------------------------------------ Applications monitor ----
class TestApplicationsMonitor:
    def test_list_applications(self, admin_sess):
        r = admin_sess.get(f"{API}/admin/applications", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "applications" in data and isinstance(data["applications"], list)
        # If any application exists, each row should have required fields
        if data["applications"]:
            row = data["applications"][0]
            for k in ("id", "player_name", "title", "status", "reason", "outcome_message"):
                assert k in row, f"missing {k}"

    def test_filter_pending(self, admin_sess):
        r = admin_sess.get(f"{API}/admin/applications?status=pending", timeout=15)
        assert r.status_code == 200
        for a in r.json()["applications"]:
            assert a["status"] == "pending"

    def test_override_reason_flow(self, admin_sess, player_sess):
        # Ensure at least one application exists — submit as mara if none
        apps = admin_sess.get(f"{API}/admin/applications?limit=200", timeout=15).json()["applications"]
        if not apps:
            # Try to submit for cashier as mara (may fail if already employed / cooldown)
            player_sess.post(f"{API}/jobs/cashier/apply", json={}, timeout=15)
            apps = admin_sess.get(f"{API}/admin/applications?limit=200", timeout=15).json()["applications"]
        if not apps:
            pytest.skip("No applications exist to override")

        app_id = apps[0]["id"]
        original_reason = apps[0].get("reason") or ""

        pr = admin_sess.put(f"{API}/admin/applications/{app_id}",
                            json={"reason": "admin override test"}, timeout=15)
        assert pr.status_code == 200, pr.text
        data = pr.json()
        assert data.get("reason") == "admin override test"

        # GET reflects the change
        again = admin_sess.get(f"{API}/admin/applications?limit=200", timeout=15).json()["applications"]
        target = next(a for a in again if a["id"] == app_id)
        assert target["reason"] == "admin override test"

        # Restore original (best effort)
        admin_sess.put(f"{API}/admin/applications/{app_id}",
                       json={"reason": original_reason}, timeout=15)

    def test_override_empty_body_400(self, admin_sess):
        apps = admin_sess.get(f"{API}/admin/applications?limit=1", timeout=15).json()["applications"]
        if not apps:
            pytest.skip("No applications exist")
        app_id = apps[0]["id"]
        r = admin_sess.put(f"{API}/admin/applications/{app_id}", json={}, timeout=15)
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"

    def test_override_bad_app_id_404(self, admin_sess):
        r = admin_sess.put(f"{API}/admin/applications/nonexistent-id-xyz",
                           json={"reason": "x"}, timeout=15)
        assert r.status_code == 404


# ------------------------------------------------ Admin 403 with player token ----
class TestAdminAccessControl:
    def test_player_cannot_list_applications(self, player_sess):
        r = player_sess.get(f"{API}/admin/applications", timeout=15)
        assert r.status_code == 403, f"expected 403 got {r.status_code}"

    def test_player_cannot_put_job_applications(self, player_sess):
        r = player_sess.put(f"{API}/admin/job-applications/cashier",
                            json={"acceptance_base_chance": 0.5, "skill_weight": 1.0,
                                  "success_response": "x", "failure_response": "y",
                                  "reason_strings": {"accept": {}, "reject": {}}},
                            timeout=15)
        assert r.status_code == 403
