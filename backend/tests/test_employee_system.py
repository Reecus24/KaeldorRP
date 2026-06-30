"""
Kaeldor RPG — Employee + Hiring System backend tests.
Covers: buy_business seeds 3 applicants, /businesses/owned metrics,
business detail, employees, applicants, events; hire/reject/recruit;
employee raise/fire/train + training-options; staffing affects net_day.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
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


def _sess(token=None):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def wealthy_player():
    """Use the existing seeded player@kaeldor.com who has cash and an owned kiosk."""
    s = _sess()
    r = s.post(f"{API}/auth/login", json={"email": "player@kaeldor.com", "password": "player123"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    s.headers["Authorization"] = f"Bearer {token}"
    # Top-up via loans if needed (this player has hustler background so larger cap)
    def _player():
        return s.get(f"{API}/game/state").json()["player"]
    p = _player()
    # If player has no character, fail loudly
    assert "cash" in p, "player has no character"
    # If broke, take a loan
    if p["cash"] + p["bank"] < 4000:
        for _ in range(6):
            bank = s.get(f"{API}/bank").json()
            ml = bank.get("max_loan", 0)
            if ml < 50:
                break
            s.post(f"{API}/bank/loan", json={"amount": round(ml)})
            if _player()["cash"] + _player()["bank"] >= 4500:
                break
    return {"session": s, "token": token}
    return {"session": s, "token": token}


@pytest.fixture(scope="module")
def owned_kiosk(wealthy_player):
    s = wealthy_player["session"]
    owned = s.get(f"{API}/businesses/owned").json()
    biz = next((b for b in owned if b["type_id"] == "kiosk"), None)
    if biz is None:
        # Buy one
        market = s.get(f"{API}/businesses/market").json()
        kiosk = next(b for b in market if b["id"] == "kiosk")
        r = s.post(f"{API}/businesses/{kiosk['id']}/buy")
        assert r.status_code == 200, r.text
        owned = s.get(f"{API}/businesses/owned").json()
        biz = next(b for b in owned if b["type_id"] == "kiosk")
    return biz


class TestBuyBusinessSeedsApplicants:
    def test_owned_business_has_metrics(self, wealthy_player, owned_kiosk):
        s = wealthy_player["session"]
        owned = s.get(f"{API}/businesses/owned").json()
        b = next(b for b in owned if b["id"] == owned_kiosk["id"])
        assert "metrics" in b
        m = b["metrics"]
        for key in ("net_day", "rev_day", "exp_day", "wage_per_day",
                    "coverage", "satisfaction", "morale_avg",
                    "applicant_count", "bankruptcy_risk", "employee_count"):
            assert key in m, f"metric {key} missing"

    def test_buy_seeds_three_applicants(self, wealthy_player):
        """Buy a brand-new business; verify exactly 3 applicants spawn."""
        s = wealthy_player["session"]
        p = s.get(f"{API}/game/state").json()["player"]
        if p["cash"] + p["bank"] < 4500:
            # try one more loan
            bank = s.get(f"{API}/bank").json()
            if bank.get("max_loan", 0) > 50:
                s.post(f"{API}/bank/loan", json={"amount": round(bank["max_loan"])})
            p = s.get(f"{API}/game/state").json()["player"]
            if p["cash"] + p["bank"] < 4500:
                pytest.skip(f"cannot afford another kiosk: {p['cash']+p['bank']}")
        before_owned = s.get(f"{API}/businesses/owned").json()
        before_ids = {b["id"] for b in before_owned}
        r = s.post(f"{API}/businesses/kiosk/buy")
        if r.status_code != 200:
            pytest.skip(f"buy failed: {r.text}")
        after = s.get(f"{API}/businesses/owned").json()
        new_biz = next(b for b in after if b["id"] not in before_ids)
        apps = s.get(f"{API}/businesses/{new_biz['id']}/applicants").json()
        assert isinstance(apps, list)
        assert len(apps) == 3, f"expected 3 applicants on new biz, got {len(apps)}"
        for a in apps:
            for k in ("id", "name", "role", "skill", "reliability", "daily_wage", "traits"):
                assert k in a, f"applicant missing {k}"

    def test_business_detail_endpoint(self, wealthy_player, owned_kiosk):
        s = wealthy_player["session"]
        r = s.get(f"{API}/businesses/{owned_kiosk['id']}")
        assert r.status_code == 200
        data = r.json()
        assert "business" in data and "metrics" in data
        assert data["business"]["id"] == owned_kiosk["id"]

    def test_employees_initially_has_some(self, wealthy_player, owned_kiosk):
        s = wealthy_player["session"]
        r = s.get(f"{API}/businesses/{owned_kiosk['id']}/employees")
        assert r.status_code == 200
        assert "employees" in r.json() and "metrics" in r.json()

    def test_business_events_log(self, wealthy_player, owned_kiosk):
        s = wealthy_player["session"]
        r = s.get(f"{API}/businesses/{owned_kiosk['id']}/events")
        assert r.status_code == 200
        evs = r.json()
        assert isinstance(evs, list)
        # Each event should have text + ts (basic event schema)
        for e in evs:
            assert "ts" in e


class TestHiringFlow:
    def test_hire_moves_applicant_to_active(self, wealthy_player, owned_kiosk):
        s = wealthy_player["session"]
        apps_before = s.get(f"{API}/businesses/{owned_kiosk['id']}/applicants").json()
        assert len(apps_before) >= 1
        applicant = apps_before[0]
        r = s.post(f"{API}/businesses/{owned_kiosk['id']}/applicants/{applicant['id']}/hire")
        assert r.status_code == 200, r.text
        # Verify removed from applicants
        apps_after = s.get(f"{API}/businesses/{owned_kiosk['id']}/applicants").json()
        assert applicant["id"] not in [a["id"] for a in apps_after]
        assert len(apps_after) == len(apps_before) - 1
        # Verify present in employees
        emps = s.get(f"{API}/businesses/{owned_kiosk['id']}/employees").json()["employees"]
        assert any(e["id"] == applicant["id"] for e in emps)

    def test_reject_removes_applicant(self, wealthy_player, owned_kiosk):
        s = wealthy_player["session"]
        apps_before = s.get(f"{API}/businesses/{owned_kiosk['id']}/applicants").json()
        if not apps_before:
            pytest.skip("no applicants to reject")
        applicant = apps_before[0]
        r = s.post(f"{API}/businesses/{owned_kiosk['id']}/applicants/{applicant['id']}/reject")
        assert r.status_code == 200
        apps_after = s.get(f"{API}/businesses/{owned_kiosk['id']}/applicants").json()
        assert applicant["id"] not in [a["id"] for a in apps_after]

    def test_recruit_adds_premium_applicant(self, wealthy_player, owned_kiosk):
        s = wealthy_player["session"]
        p_before = s.get(f"{API}/game/state").json()["player"]
        cash_before = p_before["cash"] + p_before["bank"]
        apps_before = s.get(f"{API}/businesses/{owned_kiosk['id']}/applicants").json()
        r = s.post(f"{API}/businesses/{owned_kiosk['id']}/recruit")
        assert r.status_code == 200, r.text
        cost = r.json().get("cost", 250)
        apps_after = s.get(f"{API}/businesses/{owned_kiosk['id']}/applicants").json()
        assert len(apps_after) == len(apps_before) + 1
        p_after = s.get(f"{API}/game/state").json()["player"]
        assert p_after["cash"] + p_after["bank"] <= cash_before - cost + 1


class TestEmployeeActions:
    def _first_active_or_hire(self, s, biz_id):
        emps = s.get(f"{API}/businesses/{biz_id}/employees").json()["employees"]
        actives = [e for e in emps if e["status"] == "active"]
        if actives:
            return actives[0]
        # Hire one
        apps = s.get(f"{API}/businesses/{biz_id}/applicants").json()
        if not apps:
            # Try recruit to spawn one
            s.post(f"{API}/businesses/{biz_id}/recruit")
            apps = s.get(f"{API}/businesses/{biz_id}/applicants").json()
        if not apps:
            pytest.skip("no applicants available to hire")
        r = s.post(f"{API}/businesses/{biz_id}/applicants/{apps[0]['id']}/hire")
        assert r.status_code == 200, r.text
        emps = s.get(f"{API}/businesses/{biz_id}/employees").json()["employees"]
        return next(e for e in emps if e["id"] == apps[0]["id"])

    def test_raise_increases_wage(self, wealthy_player, owned_kiosk):
        s = wealthy_player["session"]
        emp = self._first_active_or_hire(s, owned_kiosk["id"])
        old_wage = emp["daily_wage"]
        r = s.post(f"{API}/businesses/employees/{emp['id']}/raise")
        assert r.status_code == 200
        emps = s.get(f"{API}/businesses/{owned_kiosk['id']}/employees").json()["employees"]
        new = next((e for e in emps if e["id"] == emp["id"]), None)
        if new is None:
            pytest.skip("employee no longer present after raise (quit/fired by resolve)")
        # Allow equal in the rare case wage was capped/rounded the same
        assert new["daily_wage"] >= old_wage, f"wage went down: {old_wage} -> {new['daily_wage']}"

    def test_training_options_listed(self, wealthy_player):
        s = wealthy_player["session"]
        r = s.get(f"{API}/training-options")
        assert r.status_code == 200
        opts = r.json()
        assert isinstance(opts, list) and len(opts) >= 1
        assert {"id", "label", "cost", "duration_minutes"}.issubset(opts[0].keys())

    def test_train_starts_countdown(self, wealthy_player, owned_kiosk):
        s = wealthy_player["session"]
        emp = self._first_active_or_hire(s, owned_kiosk["id"])
        opts = s.get(f"{API}/training-options").json()
        # Pick cheapest option to ensure affordability
        opt = min(opts, key=lambda o: o["cost"])
        r = s.post(f"{API}/businesses/employees/{emp['id']}/train", json={"option_id": opt["id"]})
        assert r.status_code == 200, r.text
        # verify training pill present
        emps = s.get(f"{API}/businesses/{owned_kiosk['id']}/employees").json()["employees"]
        new = next(e for e in emps if e["id"] == emp["id"])
        assert new.get("training") and new["training"].get("ends_at")
        # Double train should 400
        r2 = s.post(f"{API}/businesses/employees/{emp['id']}/train", json={"option_id": opt["id"]})
        assert r2.status_code == 400


class TestStaffingAffectsMetrics:
    """Verify that hiring staff improves coverage and net/day."""
    @pytest.fixture(scope="class")
    def second_biz(self, wealthy_player):
        s = wealthy_player["session"]
        # Get another loan if needed and buy a second kiosk
        for _ in range(8):
            p = s.get(f"{API}/game/state").json()["player"]
            if p["cash"] + p["bank"] >= 4500:
                break
            bank = s.get(f"{API}/bank").json()
            ml = bank.get("max_loan", 0)
            if ml < 50:
                break
            s.post(f"{API}/bank/loan", json={"amount": round(ml)})
        market = s.get(f"{API}/businesses/market").json()
        kiosk = next(b for b in market if b["id"] == "kiosk")
        r = s.post(f"{API}/businesses/{kiosk['id']}/buy")
        if r.status_code != 200:
            pytest.skip(f"cannot afford second kiosk: {r.text}")
        owned = s.get(f"{API}/businesses/owned").json()
        # second kiosk (latest)
        kiosks = [b for b in owned if b["type_id"] == "kiosk"]
        return kiosks[-1]

    def test_coverage_low_when_unstaffed(self, wealthy_player, second_biz):
        s = wealthy_player["session"]
        owned = s.get(f"{API}/businesses/owned").json()
        b = next(b for b in owned if b["id"] == second_biz["id"])
        # 0 employees -> coverage 0% (or very low)
        assert b["metrics"]["coverage"] <= 10, f"expected low coverage, got {b['metrics']['coverage']}"

    def test_coverage_improves_after_hire(self, wealthy_player, second_biz):
        s = wealthy_player["session"]
        before = s.get(f"{API}/businesses/owned").json()
        b_before = next(b for b in before if b["id"] == second_biz["id"])
        cov_before = b_before["metrics"]["coverage"]
        net_before = b_before["metrics"]["net_day"]

        apps = s.get(f"{API}/businesses/{second_biz['id']}/applicants").json()
        # hire all applicants to maximize coverage
        for a in apps:
            s.post(f"{API}/businesses/{second_biz['id']}/applicants/{a['id']}/hire")

        after = s.get(f"{API}/businesses/owned").json()
        b_after = next(b for b in after if b["id"] == second_biz["id"])
        cov_after = b_after["metrics"]["coverage"]
        net_after = b_after["metrics"]["net_day"]
        assert cov_after > cov_before, f"coverage didn't improve: {cov_before}->{cov_after}"
        # Net/day should improve OR at least revenue should go up. wages may also rise.
        assert b_after["metrics"]["rev_day"] >= b_before["metrics"]["rev_day"], \
            f"revenue did not improve: {b_before['metrics']['rev_day']}->{b_after['metrics']['rev_day']}"


class TestFireFlow:
    def test_fire_removes_employee(self, wealthy_player, owned_kiosk):
        s = wealthy_player["session"]
        emps = s.get(f"{API}/businesses/{owned_kiosk['id']}/employees").json()["employees"]
        if not emps:
            pytest.skip("no employee to fire")
        emp = emps[0]
        r = s.post(f"{API}/businesses/employees/{emp['id']}/fire")
        assert r.status_code == 200
        emps_after = s.get(f"{API}/businesses/{owned_kiosk['id']}/employees").json()["employees"]
        assert emp["id"] not in [e["id"] for e in emps_after]


# ============== Admin content editor for new content types ==============
@pytest.fixture(scope="module")
def admin_session():
    s = _sess()
    r = s.post(f"{API}/auth/login", json={"email": "admin@kaeldor.com", "password": "admin123"})
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


class TestAdminEmployeeContent:
    @pytest.mark.parametrize("ctype", [
        "employee_roles", "employee_traits", "staffing_requirements",
        "training_options", "employee_events"
    ])
    def test_list_content(self, admin_session, ctype):
        r = admin_session.get(f"{API}/admin/content/{ctype}")
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 1, f"{ctype} list is empty"

    def test_crud_training_option(self, admin_session):
        new_id = f"TEST_{uuid.uuid4().hex[:8]}"
        payload = {
            "id": new_id, "label": "TEST training", "description": "x",
            "cost": 50, "duration_minutes": 5, "skill_gain": 5,
            "morale_gain": 5, "loyalty_gain": 5, "fail_chance": 0.0,
        }
        r = admin_session.post(f"{API}/admin/content/training_options", json=payload)
        assert r.status_code == 200, r.text
        # Update
        payload["label"] = "TEST training v2"
        r2 = admin_session.put(f"{API}/admin/content/training_options/{new_id}", json=payload)
        assert r2.status_code == 200, r2.text
        # Delete
        r3 = admin_session.delete(f"{API}/admin/content/training_options/{new_id}")
        assert r3.status_code == 200, r3.text
