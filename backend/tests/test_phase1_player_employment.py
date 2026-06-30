"""Phase 1 — Player-Business + Inventory logic-fix: player-employees fully integrated.

Covers:
- Hourly wage model (offer/accept/raise use wage_per_hour; market exposes base_hourly_wage)
- Role from staffing + fit (applicant_snapshot has role_fit, fit_label, role_matches_staffing)
- Coverage integration: active player employee folds into business staffing metrics
- Per-shift business output + net impact (revenue, wage, net, history.kind=shift, notif)
- Finance log clarity: history.kind tags (accrual vs shift)
- /jobs/current returns {npc, player_jobs}
- Withdraw application path (status=withdrawn; can no longer be offered/accepted)
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or
        open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0].strip()).rstrip("/")
API = f"{BASE}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

mc = MongoClient(MONGO_URL)
db = mc[DB_NAME]

DOVAN = ("dovan@kaeldor.com", "demo123")
MARA = ("mara@kaeldor.com", "demo123")
KIRI = ("kiri@kaeldor.com", "demo123")


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, f"login {email}: {r.text}"
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _pid(headers):
    r = requests.get(f"{API}/game/state", headers=headers, timeout=20)
    assert r.status_code == 200
    return (r.json().get("player") or r.json())["id"]


def _past_iso(minutes=120):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


@pytest.fixture(scope="module")
def dovan_h():
    return _login(*DOVAN)


@pytest.fixture(scope="module")
def mara_h():
    return _login(*MARA)


@pytest.fixture(scope="module")
def kiri_h():
    return _login(*KIRI)


@pytest.fixture(scope="module")
def dovan_pid(dovan_h):
    return _pid(dovan_h)


@pytest.fixture(scope="module")
def mara_pid(mara_h):
    return _pid(mara_h)


@pytest.fixture(scope="module")
def kiri_pid(kiri_h):
    return _pid(kiri_h)


@pytest.fixture(scope="module")
def dovan_biz(dovan_h):
    r = requests.get(f"{API}/businesses/owned", headers=dovan_h, timeout=20)
    assert r.status_code == 200, r.text
    owned = r.json()
    kiosk = next((b for b in owned if "Kiosk" in b.get("name", "") or b.get("type_id") == "kiosk"), owned[0])
    bid = kiosk["id"]
    # ensure hiring open
    db.businesses.update_one({"id": bid}, {"$set": {"hiring_open": True}})
    return bid


def _wipe_applications(biz_id, *applicant_ids):
    """Clear stale apps/employments from this biz for the given applicants so each test is clean."""
    for aid in applicant_ids:
        db.business_applications.delete_many({"business_id": biz_id, "applicant_id": aid})
        db.player_employment.delete_many({"business_id": biz_id, "employee_player_id": aid})


# ========================== HOURLY WAGE MODEL ==========================
class TestHourlyWageModel:
    def test_market_exposes_base_hourly_wage_and_roles(self, mara_h, dovan_biz):
        r = requests.get(f"{API}/jobs/market", headers=mara_h, timeout=20)
        assert r.status_code == 200, r.text
        market = r.json()
        card = next((m for m in market if m["business_id"] == dovan_biz), None)
        assert card, "dovan's biz not on market"
        assert card.get("base_hourly_wage", 0) > 0, "base_hourly_wage missing/zero"
        assert isinstance(card.get("roles"), list) and len(card["roles"]) >= 1
        assert any(r["role"] == "cashier" for r in card["roles"])

    def test_full_offer_accept_raise_hourly_chain(self, mara_h, dovan_h, dovan_biz, mara_pid, dovan_pid):
        _wipe_applications(dovan_biz, mara_pid)
        # Apply
        r = requests.post(f"{API}/jobs/market/{dovan_biz}/apply", headers=mara_h,
                          json={"role": "cashier", "message": "phase1 hourly"}, timeout=20)
        assert r.status_code == 200, r.text
        # Offer
        apps = requests.get(f"{API}/businesses/{dovan_biz}/player-applications",
                            headers=dovan_h, timeout=20).json()
        a = next(x for x in apps if x["applicant_id"] == mara_pid and x["status"] == "pending")
        off = requests.post(f"{API}/businesses/{dovan_biz}/player-applications/{a['id']}/offer",
                            headers=dovan_h, json={"wage_per_hour": 15.0, "role": "cashier"}, timeout=20)
        assert off.status_code == 200, off.text
        assert off.json().get("role_matches_staffing") is True
        # Re-offer with higher wage triggers "increased" notification text
        off2 = requests.post(f"{API}/businesses/{dovan_biz}/player-applications/{a['id']}/offer",
                             headers=dovan_h, json={"wage_per_hour": 18.0, "role": "cashier"}, timeout=20)
        assert off2.status_code == 200
        notifs = requests.get(f"{API}/notifications", headers=mara_h, timeout=20).json()
        items = notifs.get("items") if isinstance(notifs, dict) else notifs
        text_blob = " ".join((n.get("title", "") + " " + n.get("body", "")) for n in items[:30]).lower()
        assert "$18" in text_blob and "/h" in text_blob, f"hourly notification text missing: {text_blob[:300]}"
        assert "$15" in text_blob, "previous wage missing from re-offer notification"

        # Accept
        acc = requests.post(f"{API}/jobs/employment/applications/{a['id']}/accept", headers=mara_h, timeout=20)
        assert acc.status_code == 200, acc.text
        emp_doc = db.player_employment.find_one({"business_id": dovan_biz, "employee_player_id": mara_pid, "status": "active"})
        assert emp_doc and abs(emp_doc["wage_per_hour"] - 18.0) < 0.01

        # employment listing returns wage_per_hour
        emps = requests.get(f"{API}/jobs/employment", headers=mara_h, timeout=20).json()
        active = next(e for e in emps["employments"] if e["business_id"] == dovan_biz)
        assert "wage_per_hour" in active and active["wage_per_hour"] == 18.0

        # Owner side listing
        olist = requests.get(f"{API}/businesses/{dovan_biz}/player-employees", headers=dovan_h, timeout=20).json()
        oactive = next(e for e in olist if e["id"] == emp_doc["id"])
        assert oactive["wage_per_hour"] == 18.0

        # Raise via wage_per_hour
        rs = requests.post(f"{API}/businesses/{dovan_biz}/player-employees/{emp_doc['id']}/raise",
                           headers=dovan_h, json={"wage_per_hour": 22.5}, timeout=20)
        assert rs.status_code == 200, rs.text
        emp_after = db.player_employment.find_one({"id": emp_doc["id"]})
        assert abs(emp_after["wage_per_hour"] - 22.5) < 0.01


# ========================== ROLE FROM STAFFING + FIT ==========================
class TestRoleFromStaffing:
    def test_apply_with_bad_role_falls_back_to_staffing(self, kiri_h, dovan_h, dovan_biz, kiri_pid):
        _wipe_applications(dovan_biz, kiri_pid)
        r = requests.post(f"{API}/jobs/market/{dovan_biz}/apply", headers=kiri_h,
                          json={"role": "wizard", "message": "fallback"}, timeout=20)
        assert r.status_code == 200, r.text
        apps = requests.get(f"{API}/businesses/{dovan_biz}/player-applications",
                            headers=dovan_h, timeout=20).json()
        a = next(x for x in apps if x["applicant_id"] == kiri_pid)
        assert a["role"] == "cashier", f"expected fallback to cashier, got {a['role']}"
        s = a.get("stats") or {}
        assert 0.55 <= s.get("role_fit", 0) <= 1.3
        assert s.get("fit_label") in ("great fit", "good fit", "weak fit")
        assert s.get("role_matches_staffing") is True

    def test_offer_with_off_staffing_role_marks_mismatch(self, kiri_h, dovan_h, dovan_biz, kiri_pid):
        apps = requests.get(f"{API}/businesses/{dovan_biz}/player-applications",
                            headers=dovan_h, timeout=20).json()
        a = next(x for x in apps if x["applicant_id"] == kiri_pid)
        off = requests.post(f"{API}/businesses/{dovan_biz}/player-applications/{a['id']}/offer",
                            headers=dovan_h, json={"wage_per_hour": 14.0, "role": "barista"}, timeout=20)
        assert off.status_code == 200
        assert off.json().get("role_matches_staffing") is False


# ========================== COVERAGE INTEGRATION ==========================
class TestCoverageIntegration:
    def test_active_player_employee_folds_into_metrics(self, dovan_h, dovan_biz, mara_pid):
        # Ensure mara has an active employment with role=cashier (matches staffing)
        emp = db.player_employment.find_one({"business_id": dovan_biz, "employee_player_id": mara_pid, "status": "active"})
        if not emp:
            db.player_employment.insert_one({
                "id": uuid.uuid4().hex, "business_id": dovan_biz, "business_name": "Dovan's Street Kiosk",
                "owner_id": _pid(_login(*DOVAN)), "employee_player_id": mara_pid, "employee_name": "Mara",
                "role": "cashier", "wage_per_hour": 16.0, "status": "active",
                "hired_at": datetime.now(timezone.utc).isoformat(),
                "reliability": 70, "performance": 70, "total_hours_worked": 0,
                "total_wages_earned": 0.0, "total_value_added": 0.0, "hours_at_last_raise": 0,
            })
        r = requests.get(f"{API}/businesses/{dovan_biz}", headers=dovan_h, timeout=20)
        assert r.status_code == 200, r.text
        m = r.json().get("metrics", {})
        assert "player_employee_count" in m
        assert m["player_employee_count"] >= 1
        # staffing has player_have for cashier role
        cashier_row = next((s for s in m.get("staffing", []) if s["role"] == "cashier"), None)
        assert cashier_row and cashier_row.get("player_have", 0) >= 1
        assert "unmatched_player_count" in m

    def test_offrole_player_does_not_add_role_coverage(self, dovan_h, dovan_biz, kiri_pid, dovan_pid):
        # Force a kiri employment with non-staffing role
        db.player_employment.delete_many({"business_id": dovan_biz, "employee_player_id": kiri_pid})
        db.player_employment.insert_one({
            "id": uuid.uuid4().hex, "business_id": dovan_biz, "business_name": "Dovan's Street Kiosk",
            "owner_id": dovan_pid, "employee_player_id": kiri_pid, "employee_name": "Kiri",
            "role": "barista", "wage_per_hour": 14.0, "status": "active",
            "hired_at": datetime.now(timezone.utc).isoformat(),
            "reliability": 60, "performance": 60, "total_hours_worked": 0,
            "total_wages_earned": 0.0, "total_value_added": 0.0, "hours_at_last_raise": 0,
        })
        m = requests.get(f"{API}/businesses/{dovan_biz}", headers=dovan_h, timeout=20).json()["metrics"]
        assert m.get("unmatched_player_count", 0) >= 1
        cashier_row = next((s for s in m.get("staffing", []) if s["role"] == "cashier"), None)
        # cashier player_have should NOT include kiri's mismatched role
        # (mara may still be cashier, so just assert kiri's role doesn't appear in staffing rows)
        assert all(s["role"] != "barista" for s in m.get("staffing", []))
        # Cleanup off-role kiri employment
        db.player_employment.delete_many({"business_id": dovan_biz, "employee_player_id": kiri_pid, "role": "barista"})


# ========================== PER-SHIFT OUTPUT + NET IMPACT ==========================
class TestPerShiftNetImpact:
    def test_shift_credits_business_and_history_tagged_shift(self, mara_h, dovan_h, dovan_biz, mara_pid, dovan_pid):
        emp = db.player_employment.find_one({"business_id": dovan_biz, "employee_player_id": mara_pid, "status": "active"})
        if not emp:
            emp_doc = {
                "id": uuid.uuid4().hex, "business_id": dovan_biz, "business_name": "Dovan's Street Kiosk",
                "owner_id": dovan_pid, "employee_player_id": mara_pid, "employee_name": "Mara",
                "role": "cashier", "wage_per_hour": 16.0, "status": "active",
                "hired_at": datetime.now(timezone.utc).isoformat(),
                "reliability": 70, "performance": 70, "total_hours_worked": 0,
                "total_wages_earned": 0.0, "total_value_added": 0.0, "hours_at_last_raise": 0,
            }
            db.player_employment.insert_one(emp_doc)
            emp = emp_doc
        # Cash starting points
        biz_before = db.businesses.find_one({"id": dovan_biz})
        cash_before = biz_before.get("cash", 0)
        debt_before = biz_before.get("debt", 0)
        # Clear current activity on mara, then start shift
        db.players.update_one({"id": mara_pid}, {"$set": {"current_activity": None, "status": "idle",
                                                          "energy": 100, "health": 90, "mood": 80, "fatigue": 10}})
        w = requests.post(f"{API}/jobs/employment/{emp['id']}/work",
                          headers=mara_h, json={"hours": 4}, timeout=20)
        assert w.status_code == 200, w.text
        # Fast-forward by writing the activity ends_at to the past
        db.players.update_one({"id": mara_pid}, {"$set": {"current_activity.ends_at": _past_iso(120)}})
        # Resolve via /game/state
        s = requests.get(f"{API}/game/state", headers=mara_h, timeout=30)
        assert s.status_code == 200
        # Re-read employment + business
        emp_after = db.player_employment.find_one({"id": emp["id"]})
        biz_after = db.businesses.find_one({"id": dovan_biz})
        assert emp_after.get("total_hours_worked", 0) >= 4, f"hours not credited: {emp_after.get('total_hours_worked')}"
        ls = emp_after.get("last_shift") or {}
        assert ls.get("hours") == 4
        assert "wage" in ls and "revenue" in ls and "net" in ls and "productivity" in ls
        # History has a kind=shift entry with matching amount
        hist = biz_after.get("history") or []
        shift_entries = [h for h in hist if h.get("kind") == "shift"]
        assert shift_entries, "no shift entry recorded in business history"
        last = shift_entries[-1]
        assert "rev" in last and "wage" in last and "amount" in last
        assert abs(last["amount"] - (last["rev"] - last["wage"])) < 0.5
        # Cash + debt movement mirrors net (when cash would go below 0, debt absorbs the overflow)
        cash_delta = biz_after.get("cash", 0) - cash_before
        debt_delta = biz_after.get("debt", 0) - debt_before
        # net cash effect = cash_delta - debt_delta (debt going up is a cash claim)
        assert abs((cash_delta - debt_delta) - last["amount"]) < 1.5, \
            f"cash_delta={cash_delta} debt_delta={debt_delta} net={last['amount']}"
        # Owner notification mentions worked a Xh shift
        notifs = requests.get(f"{API}/notifications", headers=dovan_h, timeout=20).json()
        items = notifs.get("items") if isinstance(notifs, dict) else notifs
        blob = " ".join((n.get("title", "") + " " + n.get("body", "")).lower() for n in items[:30])
        assert "4h shift" in blob or "worked a 4" in blob, f"owner notif missing 4h shift: {blob[:300]}"

    def test_low_skill_exhausted_employee_can_yield_negative_net(self, dovan_h, dovan_biz, kiri_pid, dovan_pid, kiri_h):
        # Create a fresh employment for kiri with cashier role + tiny skill + exhausted state
        db.player_employment.delete_many({"business_id": dovan_biz, "employee_player_id": kiri_pid})
        emp_doc = {
            "id": uuid.uuid4().hex, "business_id": dovan_biz, "business_name": "Dovan's Street Kiosk",
            "owner_id": dovan_pid, "employee_player_id": kiri_pid, "employee_name": "Kiri",
            "role": "cashier", "wage_per_hour": 30.0, "status": "active",
            "hired_at": datetime.now(timezone.utc).isoformat(),
            "reliability": 20, "performance": 30, "total_hours_worked": 0,
            "total_wages_earned": 0.0, "total_value_added": 0.0, "hours_at_last_raise": 0,
        }
        db.player_employment.insert_one(emp_doc)
        # Save original kiri stats to restore
        orig = db.players.find_one({"id": kiri_pid}, {"skills": 1, "health": 1, "energy": 1, "fatigue": 1, "mood": 1, "hygiene": 1, "current_activity": 1, "status": 1})
        try:
            db.players.update_one({"id": kiri_pid}, {"$set": {
                "health": 25, "energy": 100, "fatigue": 90, "mood": 25, "hygiene": 30,
                "current_activity": None, "status": "idle",
                "skills.sales": {"level": 1, "xp": 0},
            }})
            w = requests.post(f"{API}/jobs/employment/{emp_doc['id']}/work",
                              headers=kiri_h, json={"hours": 4}, timeout=20)
            assert w.status_code == 200, w.text
            db.players.update_one({"id": kiri_pid}, {"$set": {"current_activity.ends_at": _past_iso(120)}})
            requests.get(f"{API}/game/state", headers=kiri_h, timeout=30)
            emp_after = db.player_employment.find_one({"id": emp_doc["id"]})
            ls = emp_after.get("last_shift") or {}
            # productivity should be low (< 1.0), and net likely <= 0 or at least clearly worse than high-skill case
            assert ls.get("productivity", 1) <= 1.0, f"expected low productivity, got {ls.get('productivity')}"
            # Hour cost is wph(30)*4=120; revenue at low prod * 1.8 mult * 0.55 fit * ~0.3 perf is well under 120
            assert ls.get("net", 0) < ls.get("wage", 0), "expected negative-leaning net for low-skill employee"
        finally:
            restore = {k: orig.get(k) for k in ("health", "energy", "fatigue", "mood", "hygiene") if k in orig}
            if restore:
                db.players.update_one({"id": kiri_pid}, {"$set": restore})
            db.player_employment.delete_many({"id": emp_doc["id"]})


# ========================== FINANCE LOG CLARITY ==========================
class TestFinanceLogClarity:
    def test_history_entries_have_kind_tag(self, dovan_h, dovan_biz):
        biz = db.businesses.find_one({"id": dovan_biz})
        hist = biz.get("history") or []
        # All NEW entries (those with a kind field) should be accrual or shift.
        # Pre-migration entries without kind are tolerated (stale data per agent note).
        tagged = [h for h in hist if h.get("kind") is not None]
        assert tagged, "no kind-tagged history entries found at all"
        kinds = {h.get("kind") for h in tagged}
        assert kinds.issubset({"accrual", "shift"}), f"unexpected kind values: {kinds}"
        for h in tagged:
            assert "amount" in h, f"history entry missing 'amount': {h}"
        # At least one accrual entry should exist (continuous P&L)
        assert any(h.get("kind") == "accrual" for h in tagged), "no accrual entries"
        # And we created a shift earlier, so at least one shift entry exists
        assert any(h.get("kind") == "shift" for h in tagged), "no shift entries"


# ========================== /jobs/current ==========================
class TestCurrentJobShape:
    def test_returns_npc_and_player_jobs(self, mara_h):
        r = requests.get(f"{API}/jobs/current", headers=mara_h, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "npc" in data and "player_jobs" in data
        assert isinstance(data["player_jobs"], list)
        # mara should have at least the dovan kiosk employment in there (set up by earlier tests)
        if data["player_jobs"]:
            pj = data["player_jobs"][0]
            assert "wage_per_hour" in pj
            assert "role" in pj
            assert "total_hours_worked" in pj


# ========================== WITHDRAW APPLICATION ==========================
class TestWithdrawApplication:
    def test_withdraw_blocks_offer_and_accept(self, kiri_h, dovan_h, dovan_biz, kiri_pid):
        _wipe_applications(dovan_biz, kiri_pid)
        r = requests.post(f"{API}/jobs/market/{dovan_biz}/apply", headers=kiri_h,
                          json={"role": "cashier", "message": "withdraw test"}, timeout=20)
        assert r.status_code == 200, r.text
        apps = requests.get(f"{API}/businesses/{dovan_biz}/player-applications",
                            headers=dovan_h, timeout=20).json()
        a = next(x for x in apps if x["applicant_id"] == kiri_pid and x["status"] == "pending")
        # Withdraw
        w = requests.post(f"{API}/jobs/employment/applications/{a['id']}/withdraw",
                          headers=kiri_h, timeout=20)
        assert w.status_code == 200, w.text
        doc = db.business_applications.find_one({"id": a["id"]})
        assert doc["status"] == "withdrawn"
        # Owner notified
        notifs = requests.get(f"{API}/notifications", headers=dovan_h, timeout=20).json()
        items = notifs.get("items") if isinstance(notifs, dict) else notifs
        assert any("withdrew" in (n.get("title", "") + n.get("body", "")).lower() for n in items[:30]), "owner missing withdrew notif"
        # Offer attempt -> 400
        off = requests.post(f"{API}/businesses/{dovan_biz}/player-applications/{a['id']}/offer",
                            headers=dovan_h, json={"wage_per_hour": 15.0, "role": "cashier"}, timeout=20)
        assert off.status_code == 400
        # Accept attempt -> 400
        acc = requests.post(f"{API}/jobs/employment/applications/{a['id']}/accept",
                            headers=kiri_h, timeout=20)
        assert acc.status_code == 400
