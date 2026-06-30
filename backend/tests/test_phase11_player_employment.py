"""Phase 1.1 API tests: scheduled auto-shifts for player-business employment.

Covers: /api/shift-presets, OfferBody.schedule on offer endpoint, accept carries
schedule, /api/jobs/employment exposes on_shift+schedule, removal of
POST /api/jobs/employment/{id}/work, /api/jobs/employment/{id}/clock-out,
/api/businesses/{id}/backup, business_detail.costs, business_metrics staffing.
Also regression check that NPC manual 'Work a Shift' still exists.
"""
import os
import time
import uuid
import requests
import pytest

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DOVAN_BIZ_ID = "249566f3664b40a9b9934c150c713de2"


def login(email, password):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text}"
    return r.json()["token"]


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def dovan_tok():
    return login("dovan@kaeldor.com", "demo123")


@pytest.fixture(scope="module")
def mara_tok():
    return login("mara@kaeldor.com", "demo123")


@pytest.fixture(scope="module")
def fresh_player():
    """Register a clean player so we can drive an end-to-end apply->offer->accept flow."""
    email = f"test_p11_{uuid.uuid4().hex[:6]}@kaeldor.com"
    r = requests.post(f"{BASE}/auth/register", json={
        "email": email, "password": "Password123!", "name": f"P11 Tester {uuid.uuid4().hex[:4]}",
        "background": "worker"}, timeout=20)
    assert r.status_code in (200, 201), r.text
    tok = r.json().get("token") or login(email, "Password123!")
    # create character if not already
    rc = requests.post(f"{BASE}/character/create", headers=H(tok),
                       json={"name": f"P11 Tester {uuid.uuid4().hex[:4]}", "background": "worker"},
                       timeout=15)
    # 200 ok or 400 already-exists are both fine
    assert rc.status_code in (200, 201, 400), rc.text
    return tok, email


# ------------------------- shift presets endpoint -------------------------
class TestShiftPresets:
    def test_presets_listed_with_all_5(self, mara_tok):
        r = requests.get(f"{BASE}/shift-presets", headers=H(mara_tok), timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        keys = {p["preset"] for p in data}
        assert {"early", "late", "night", "morning", "evening"} <= keys, keys
        early = next(p for p in data if p["preset"] == "early")
        assert early["start"] == 8 and early["end"] == 16


# ------------------------- business detail costs -------------------------
class TestBusinessDetailCosts:
    def test_costs_block_present(self, dovan_tok):
        r = requests.get(f"{BASE}/businesses/{DOVAN_BIZ_ID}", headers=H(dovan_tok), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "costs" in body
        c = body["costs"]
        for k in ("upgrade_cost", "marketing_cost", "sell_value",
                  "upgrade_revenue_boost_pct", "marketing_revenue_boost_pct"):
            assert k in c, f"costs missing {k}: {c}"
        assert isinstance(c["sell_value"], (int, float))
        assert isinstance(c["marketing_cost"], (int, float)) and c["marketing_cost"] > 0

    def test_metrics_staffing_has_roster_active(self, dovan_tok):
        r = requests.get(f"{BASE}/businesses/{DOVAN_BIZ_ID}", headers=H(dovan_tok), timeout=15)
        assert r.status_code == 200
        m = r.json().get("metrics", {})
        assert "staffing" in m, m
        # at least one role row with the new fields
        s = m["staffing"][0]
        # backend uses player_roster/player_active/active_working terminology
        for k in ("role", "player_roster", "active_working", "status", "backup_enabled", "backup_active"):
            assert k in s, f"staffing row missing {k}: {s}"


# ------------------------- removed manual work endpoint -------------------------
class TestRemovedManualPlayerWork:
    def test_player_employment_work_endpoint_removed(self, mara_tok):
        r = requests.post(f"{BASE}/jobs/employment/anything/work", headers=H(mara_tok), timeout=10)
        # FastAPI returns 405 if path collides or 404 if removed entirely
        assert r.status_code in (404, 405), f"expected 404/405 got {r.status_code}: {r.text}"

    def test_npc_job_work_shift_still_exists(self, mara_tok):
        # Should NOT be 404 — endpoint should be there even if it 400s due to no job/cooldown.
        r = requests.post(f"{BASE}/jobs/work", headers=H(mara_tok),
                          json={"hours": 4}, timeout=15)
        assert r.status_code != 404, f"NPC manual 'Work a Shift' must remain. got {r.status_code}: {r.text}"


# ------------------------- end-to-end offer w/ schedule -------------------------
class TestOfferWithSchedule:
    def test_offer_carries_schedule_to_employment(self, dovan_tok, fresh_player):
        applicant_tok, _ = fresh_player
        # 1) Applicant applies at dovan's kiosk
        # find kiosk in /jobs/market
        mkt = requests.get(f"{BASE}/jobs/market", headers=H(applicant_tok), timeout=15)
        assert mkt.status_code == 200, mkt.text
        listing = next((b for b in mkt.json() if b["business_id"] == DOVAN_BIZ_ID), None)
        if not listing:
            pytest.skip("Kiosk not in /jobs/market (hiring closed or already applied)")
        role = (listing.get("roles") or [{}])[0].get("role") or "staff"
        r_apply = requests.post(f"{BASE}/jobs/market/{DOVAN_BIZ_ID}/apply",
                                headers=H(applicant_tok), json={"role": role}, timeout=15)
        assert r_apply.status_code == 200, r_apply.text

        # 2) Owner sees the application
        apps = requests.get(f"{BASE}/businesses/{DOVAN_BIZ_ID}/player-applications",
                            headers=H(dovan_tok), timeout=15).json()
        my = [a for a in apps if a["applicant_id"] and a["status"] == "pending"]
        assert my, f"no pending apps visible to owner: {apps}"
        app_id = my[0]["id"]

        # 3) Owner sends offer WITH schedule preset = "late"
        r_offer = requests.post(
            f"{BASE}/businesses/{DOVAN_BIZ_ID}/player-applications/{app_id}/offer",
            headers=H(dovan_tok), json={"wage_per_hour": 18.0, "role": role, "schedule": "late"},
            timeout=15)
        assert r_offer.status_code == 200, r_offer.text

        # 4) Applicant's offer view shows the schedule
        emp_view = requests.get(f"{BASE}/jobs/employment", headers=H(applicant_tok), timeout=15).json()
        offered = [a for a in emp_view["applications"] if a["id"] == app_id]
        assert offered and offered[0]["status"] == "offered", offered
        sch = offered[0].get("schedule") or {}
        assert sch.get("preset") == "late", f"schedule not on offer: {offered[0]}"
        assert sch.get("start") == 14 and sch.get("end") == 22, sch

        # 5) Applicant accepts
        r_acc = requests.post(f"{BASE}/jobs/employment/applications/{app_id}/accept",
                              headers=H(applicant_tok), timeout=15)
        assert r_acc.status_code == 200, r_acc.text

        # 6) Active employment carries the schedule + on_shift/window fields
        emp_view2 = requests.get(f"{BASE}/jobs/employment", headers=H(applicant_tok), timeout=15).json()
        emps = emp_view2["employments"]
        assert emps, "no active employments after accept"
        e = [x for x in emps if x["business_id"] == DOVAN_BIZ_ID][-1]
        assert e["schedule"]["preset"] == "late"
        assert "on_shift" in e  # boolean, may be true or false depending on game-clock
        assert "window_ends_at_game" in e

        # 7) clock-out endpoint exists (may 400 if not on shift now)
        r_co = requests.post(f"{BASE}/jobs/employment/{e['id']}/clock-out",
                             headers=H(applicant_tok), timeout=15)
        assert r_co.status_code in (200, 400), f"clock-out should be present (200 or 400), got {r_co.status_code}: {r_co.text}"


# ------------------------- backup toggle endpoint -------------------------
class TestBackupToggle:
    def test_toggle_backup_persists(self, dovan_tok):
        # discover a staffing role on the business
        d = requests.get(f"{BASE}/businesses/{DOVAN_BIZ_ID}", headers=H(dovan_tok), timeout=15).json()
        role = d["metrics"]["staffing"][0]["role"]
        # enable
        r = requests.post(f"{BASE}/businesses/{DOVAN_BIZ_ID}/backup",
                          headers=H(dovan_tok), json={"role": role, "enabled": True}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["backup_roles"].get(role) is True
        # disable (cleanup)
        r2 = requests.post(f"{BASE}/businesses/{DOVAN_BIZ_ID}/backup",
                           headers=H(dovan_tok), json={"role": role, "enabled": False}, timeout=15)
        assert r2.status_code == 200
        assert role not in r2.json()["backup_roles"]


# ------------------------- biz player employees decoration -------------------------
class TestBizPlayerEmployees:
    def test_player_employees_have_schedule(self, dovan_tok):
        r = requests.get(f"{BASE}/businesses/{DOVAN_BIZ_ID}/player-employees",
                         headers=H(dovan_tok), timeout=15)
        assert r.status_code == 200, r.text
        emps = r.json()
        if not emps:
            pytest.skip("no active player employees on dovan's kiosk")
        e = emps[0]
        for k in ("schedule", "on_shift", "window_ends_at_game"):
            assert k in e, f"player-employees missing {k}: {e.keys()}"
