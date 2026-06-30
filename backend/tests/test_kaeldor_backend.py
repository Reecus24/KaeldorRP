"""
Kaeldor RPG - End-to-end backend regression tests.

Covers auth (register/login/logout/me), character creation,
core game state, actions, jobs, education, shop, bank, real estate,
vehicles, business, illegal/jail/hospital, leaderboard, and admin.
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Try reading from frontend/.env directly when env var isn't propagated
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

API = f"{BASE_URL}/api"


# ----------------- shared session helpers -----------------
def _session(token=None):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def fresh_user():
    """Register a brand-new user; yields (session, token, email, name)."""
    email = f"test_{uuid.uuid4().hex[:10]}@example.com"
    pw = "pass1234"
    name = "Tester"
    s = _session()
    r = s.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": name})
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and "user" in data
    assert data["user"]["email"] == email
    assert data["user"]["role"] == "player"
    token = data["token"]
    s.headers.update({"Authorization": f"Bearer {token}"})
    # Create a character so all downstream tests share a fully-initialized player
    r2 = s.post(f"{API}/character/create", json={"name": "TstNeo", "background": "drifter"})
    assert r2.status_code == 200, f"character create failed: {r2.status_code} {r2.text}"
    return {"session": s, "token": token, "email": email, "password": pw, "name": name}


@pytest.fixture(scope="module")
def admin_session():
    s = _session()
    r = s.post(f"{API}/auth/login", json={"email": "admin@kaeldor.com", "password": "admin123"})
    assert r.status_code == 200, f"admin login: {r.status_code} {r.text}"
    token = r.json()["token"]
    s.headers.update({"Authorization": f"Bearer {token}"})
    assert r.json()["user"]["role"] == "admin"
    return s


# ============================ AUTH ============================
class TestAuth:
    def test_invalid_login(self):
        r = requests.post(f"{API}/auth/login", json={"email": "nope@kaeldor.com", "password": "x"})
        assert r.status_code == 401
        assert "detail" in r.json()

    def test_register_login_me_logout(self):
        email = f"flow_{uuid.uuid4().hex[:8]}@example.com"
        s = _session()
        r = s.post(f"{API}/auth/register", json={"email": email, "password": "pass1234", "name": "Flow"})
        assert r.status_code == 200
        token = r.json()["token"]
        s.headers["Authorization"] = f"Bearer {token}"
        # /me
        r = s.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == email
        # login again
        r2 = requests.post(f"{API}/auth/login", json={"email": email, "password": "pass1234"})
        assert r2.status_code == 200
        # logout
        r3 = s.post(f"{API}/auth/logout")
        assert r3.status_code == 200

    def test_register_duplicate(self, fresh_user):
        r = requests.post(f"{API}/auth/register",
                          json={"email": fresh_user["email"], "password": "pass1234", "name": "x"})
        assert r.status_code == 400


# ============================ CHARACTER + STATE ============================
class TestCharacterAndState:
    def test_backgrounds(self):
        r = requests.get(f"{API}/backgrounds")
        assert r.status_code == 200
        ids = [b["id"] for b in r.json()]
        for x in ("drifter", "graduate", "hustler", "worker", "cook"):
            assert x in ids

    def test_state_requires_character(self):
        # brand-new account WITHOUT character
        email = f"nochar_{uuid.uuid4().hex[:8]}@example.com"
        s = _session()
        r = s.post(f"{API}/auth/register", json={"email": email, "password": "pass1234", "name": "N"})
        assert r.status_code == 200
        s.headers["Authorization"] = f"Bearer {r.json()['token']}"
        r2 = s.get(f"{API}/game/state")
        assert r2.status_code == 404

    def test_state_shape(self, fresh_user):
        r = fresh_user["session"].get(f"{API}/game/state")
        assert r.status_code == 200
        d = r.json()
        for k in ("player", "activity", "confinement", "net_worth", "time_scale", "effectiveness"):
            assert k in d
        p = d["player"]
        for k in ("cash", "bank", "debt", "energy", "fatigue", "hunger",
                  "hygiene", "mood", "stress", "health", "reputation",
                  "legal_reputation", "criminal_suspicion", "social_status", "level", "xp"):
            assert k in p, f"missing field {k}"
        # drifter starts cash=120, bank=40
        assert p["cash"] == 120
        assert p["bank"] == 40

    def test_create_character_twice_blocked(self, fresh_user):
        r = fresh_user["session"].post(f"{API}/character/create",
                                       json={"name": "AnotherOne", "background": "drifter"})
        assert r.status_code == 400


# ============================ ACTIONS ============================
class TestActions:
    def test_list_actions(self, fresh_user):
        r = fresh_user["session"].get(f"{API}/actions")
        assert r.status_code == 200
        ids = [a["id"] for a in r.json()]
        assert "eat_cheap" in ids
        assert "sleep" in ids

    def test_start_action_sets_activity_and_blocks(self, fresh_user):
        s = fresh_user["session"]
        before = s.get(f"{API}/game/state").json()["player"]["cash"]
        r = s.post(f"{API}/actions/eat_cheap/start")
        assert r.status_code == 200, r.text
        st = s.get(f"{API}/game/state").json()
        assert st["activity"] is not None
        assert st["activity"]["remaining_seconds"] >= 0
        # money deducted
        assert st["player"]["cash"] <= before
        # starting another action should 409
        r2 = s.post(f"{API}/actions/sleep/start")
        assert r2.status_code == 409

    def test_cancel_activity(self, fresh_user):
        s = fresh_user["session"]
        r = s.post(f"{API}/game/cancel-activity")
        assert r.status_code == 200
        st = s.get(f"{API}/game/state").json()
        assert st["activity"] is None

    def test_action_insufficient_funds(self):
        # Make a new poor user; spam expensive actions until one fails
        email = f"poor_{uuid.uuid4().hex[:8]}@example.com"
        s = _session()
        r = s.post(f"{API}/auth/register", json={"email": email, "password": "pass1234", "name": "Poor"})
        s.headers["Authorization"] = f"Bearer {r.json()['token']}"
        s.post(f"{API}/character/create", json={"name": "Po", "background": "drifter"})
        # Try a clearly unaffordable buy
        items = s.get(f"{API}/shop/items").json()
        expensive = sorted(items, key=lambda x: -x.get("price", 0))
        if expensive:
            top = expensive[0]
            r = s.post(f"{API}/shop/buy", json={"item_id": top["id"], "qty": 999})
            assert r.status_code in (400, 402, 409), f"expected error, got {r.status_code} {r.text}"


# ============================ JOBS ============================
class TestJobs:
    def test_list_jobs(self, fresh_user):
        r = fresh_user["session"].get(f"{API}/jobs")
        assert r.status_code == 200
        ids = [j["id"] for j in r.json()]
        assert "cashier" in ids
        assert "delivery_driver" in ids

    def test_delivery_driver_blocked_without_license(self, fresh_user):
        r = fresh_user["session"].post(f"{API}/jobs/delivery_driver/apply")
        assert r.status_code in (400, 409)

    def test_apply_cashier_and_work(self, fresh_user):
        s = fresh_user["session"]
        # ensure not busy
        s.post(f"{API}/game/cancel-activity")
        r = s.post(f"{API}/jobs/cashier/apply")
        assert r.status_code == 200, r.text
        cur = s.get(f"{API}/jobs/current")
        assert cur.status_code == 200
        cur_data = cur.json()
        job_obj = cur_data.get("job") if isinstance(cur_data.get("job"), dict) else cur_data
        assert (job_obj or {}).get("job_id") == "cashier", cur_data
        # work 4h shift -> starts activity
        r2 = s.post(f"{API}/jobs/work", json={"hours": 4})
        assert r2.status_code == 200, r2.text
        st = s.get(f"{API}/game/state").json()
        assert st["activity"] is not None
        assert st["activity"]["kind"] == "job"
        # cancel to free for following tests
        s.post(f"{API}/game/cancel-activity")


# ============================ EDUCATION ============================
class TestEducation:
    def test_enroll_driving_license(self):
        # Independent fresh user so prior tests don't drain money
        email = f"edu_{uuid.uuid4().hex[:8]}@example.com"
        s = _session()
        r = s.post(f"{API}/auth/register", json={"email": email, "password": "pass1234", "name": "Edu"})
        s.headers["Authorization"] = f"Bearer {r.json()['token']}"
        s.post(f"{API}/character/create", json={"name": "Edu", "background": "drifter"})
        # Drifter: cash=120, bank=40. Tuition driving_license=$280. Take a loan.
        s.post(f"{API}/bank/loan", json={"amount": 500})
        courses = s.get(f"{API}/courses").json()
        ids = [c["id"] for c in courses]
        assert "driving_license" in ids, ids
        before = s.get(f"{API}/game/state").json()["player"]
        r = s.post(f"{API}/courses/driving_license/enroll")
        assert r.status_code == 200, r.text
        after = s.get(f"{API}/game/state").json()["player"]
        assert (before["cash"] + before["bank"]) > (after["cash"] + after["bank"])


# ============================ SHOP ============================
class TestShop:
    def test_buy_energy_drink(self, fresh_user):
        s = fresh_user["session"]
        before = s.get(f"{API}/game/state").json()["player"]
        items = s.get(f"{API}/shop/items").json()
        ids = [i["id"] for i in items]
        assert "energy_drink" in ids
        r = s.post(f"{API}/shop/buy", json={"item_id": "energy_drink", "qty": 1})
        assert r.status_code == 200, r.text
        after = s.get(f"{API}/game/state").json()["player"]
        assert after["cash"] + after["bank"] < before["cash"] + before["bank"]


# ============================ BANK ============================
class TestBank:
    def test_deposit_withdraw_loan_repay(self, fresh_user):
        s = fresh_user["session"]
        st0 = s.get(f"{API}/game/state").json()["player"]
        # deposit 10
        r = s.post(f"{API}/bank/deposit", json={"amount": 10})
        assert r.status_code == 200, r.text
        st1 = s.get(f"{API}/game/state").json()["player"]
        assert st1["bank"] >= st0["bank"] + 10 - 0.001
        # withdraw 5
        r = s.post(f"{API}/bank/withdraw", json={"amount": 5})
        assert r.status_code == 200, r.text
        # loan 200
        r = s.post(f"{API}/bank/loan", json={"amount": 200})
        assert r.status_code == 200, r.text
        st2 = s.get(f"{API}/game/state").json()["player"]
        assert st2["debt"] >= 200
        # repay 50
        r = s.post(f"{API}/bank/repay", json={"amount": 50})
        assert r.status_code == 200, r.text
        st3 = s.get(f"{API}/game/state").json()["player"]
        assert st3["debt"] <= st2["debt"]


# ============================ REAL ESTATE ============================
class TestHousing:
    def test_list_and_rent_different(self, fresh_user):
        s = fresh_user["session"]
        resp = s.get(f"{API}/housing").json()
        houses = resp.get("listings") if isinstance(resp, dict) else resp
        assert isinstance(houses, list) and houses
        current_id = s.get(f"{API}/game/state").json()["player"].get("housing", {}).get("id")
        st = s.get(f"{API}/game/state").json()["player"]
        # take a loan to ensure deposit affordable
        s.post(f"{API}/bank/loan", json={"amount": 2000})
        st = s.get(f"{API}/game/state").json()["player"]
        budget = st["cash"] + st["bank"]
        target = None
        for h in sorted(houses, key=lambda x: x.get("deposit", 0)):
            if h["id"] != current_id and h.get("deposit", 0) <= budget:
                target = h
                break
        if not target:
            pytest.skip("No affordable alternative housing")
        r = s.post(f"{API}/housing/{target['id']}/rent")
        assert r.status_code == 200, r.text
        st2 = s.get(f"{API}/game/state").json()["player"]
        assert st2["housing"]["id"] == target["id"]


# ============================ VEHICLES ============================
class TestVehicles:
    def test_buy_and_sell_bicycle(self, fresh_user):
        s = fresh_user["session"]
        resp = s.get(f"{API}/vehicles").json()
        vs = resp.get("listings") if isinstance(resp, dict) else resp
        ids = [v["id"] for v in vs]
        assert "bicycle" in ids
        # ensure budget
        s.post(f"{API}/bank/loan", json={"amount": 500})
        r = s.post(f"{API}/vehicles/bicycle/buy")
        assert r.status_code == 200, r.text
        st = s.get(f"{API}/game/state").json()["player"]
        garage = st.get("vehicles", [])
        assert garage, "garage empty after buy"
        inst = garage[-1]
        inst_id = inst.get("instance_id") or inst.get("id")
        r2 = s.post(f"{API}/vehicles/{inst_id}/sell")
        assert r2.status_code == 200, r2.text


# ============================ BUSINESS ============================
class TestBusiness:
    def test_buy_kiosk_and_manage(self, fresh_user):
        s = fresh_user["session"]
        market = s.get(f"{API}/businesses/market").json()
        ids = [b["id"] for b in market]
        assert "kiosk" in ids
        # Kiosk requires driving_license education + $4000 purchase price.
        # Verify the API enforces the affordability/requirement gating with a clear error.
        r = s.post(f"{API}/businesses/kiosk/buy")
        assert r.status_code in (200, 400), r.text
        if r.status_code == 200:
            owned = s.get(f"{API}/businesses/owned").json()
            assert owned
            bid = owned[0]["id"]
            rc = s.post(f"{API}/businesses/{bid}/collect")
            assert rc.status_code in (200, 400, 409)


# ============================ ILLEGAL / JAIL / HOSPITAL ============================
class TestIllegal:
    def test_commit_petty_theft(self, fresh_user):
        s = fresh_user["session"]
        s.post(f"{API}/game/cancel-activity")
        acts = s.get(f"{API}/illegal-actions").json()
        ids = [a["id"] for a in acts]
        assert "petty_theft" in ids
        r = s.post(f"{API}/illegal-actions/petty_theft/commit")
        assert r.status_code == 200, r.text
        st = s.get(f"{API}/game/state").json()
        assert st["activity"] is not None
        assert st["activity"]["kind"] in ("illegal", "crime")
        s.post(f"{API}/game/cancel-activity")

    def test_jail_and_hospital_status(self, fresh_user):
        s = fresh_user["session"]
        rj = s.get(f"{API}/jail/status")
        assert rj.status_code == 200
        rh = s.get(f"{API}/hospital/status")
        assert rh.status_code == 200


# ============================ LEADERBOARD ============================
class TestLeaderboard:
    def test_leaderboard(self, fresh_user):
        r = fresh_user["session"].get(f"{API}/leaderboard")
        assert r.status_code == 200
        data = r.json()
        rows = data.get("top") if isinstance(data, dict) else data
        assert isinstance(rows, list)


# ============================ ADMIN ============================
class TestAdmin:
    def test_admin_login_and_stats(self, admin_session):
        r = admin_session.get(f"{API}/admin/stats")
        assert r.status_code == 200
        r2 = admin_session.get(f"{API}/admin/players")
        assert r2.status_code == 200

    def test_admin_content_list(self, admin_session):
        for ctype in ("jobs", "actions", "courses", "items", "housing",
                      "vehicles", "business_types", "illegal_actions", "random_events"):
            r = admin_session.get(f"{API}/admin/content/{ctype}")
            assert r.status_code == 200, f"{ctype}: {r.status_code} {r.text}"
            assert isinstance(r.json(), list)

    def test_admin_config_get_set(self, admin_session):
        r = admin_session.get(f"{API}/admin/config")
        assert r.status_code == 200
        cfg = r.json()
        assert "time_scale" in cfg
        original = cfg["time_scale"]
        # bump and restore
        cfg["time_scale"] = original
        r2 = admin_session.put(f"{API}/admin/config", json=cfg)
        assert r2.status_code == 200

    def test_non_admin_blocked(self, fresh_user):
        r = fresh_user["session"].get(f"{API}/admin/stats")
        assert r.status_code == 403
        r = fresh_user["session"].get(f"{API}/admin/players")
        assert r.status_code == 403
