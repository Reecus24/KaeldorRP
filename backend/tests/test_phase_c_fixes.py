"""Phase C — Iteration 7: Verify the 4 surgical backend logic fixes.

FIX 1: Owner notified when applicant DECLINES an offer; status='declined';
       applicant gets event_log 'You declined the offer from ...'.
       Declining a 'pending' app still → 'withdrawn' and no owner notif.
FIX 2: Firing an employee writes an event_log 'You were let go from ...'
       (in addition to the existing notification).
FIX 3: Re-offer (offer on an already-'offered' app) sends 'Offer updated'
       notif (not duplicate 'Job offer!'), and wage_offer reflects new wage.
FIX 4: POST /jobs/employment/{emp_id}/work with hours not in {2,4,6,8}
       returns 400 (not silent fallback). Valid hours (2/4/6/8) → 200.
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE = (os.environ.get("REACT_APP_BACKEND_URL")
        or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0].strip()).rstrip("/")
API = f"{BASE}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

mc = MongoClient(MONGO_URL)
db = mc[DB_NAME]

DOVAN = ("dovan@kaeldor.com", "demo123")
MARA = ("mara@kaeldor.com", "demo123")
KIRI = ("kiri@kaeldor.com", "demo123")
PLAYER = ("player@kaeldor.com", "player123")


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['token']}"}


def state(headers):
    r = requests.get(f"{API}/game/state", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    s = r.json()
    return s.get("player") or s


def notifs(headers):
    r = requests.get(f"{API}/notifications?limit=200", headers=headers, timeout=20).json()
    return r.get("items") if isinstance(r, dict) else r


def events(headers, limit=60):
    r = requests.get(f"{API}/game/events?limit={limit}", headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


def text_blob(n):
    return ((n.get("title") or "") + " " + (n.get("body") or "")).lower()


def event_text(e):
    return ((e.get("text") or e.get("body") or e.get("message") or "")).lower()


# =========== FIXTURES ===========
@pytest.fixture(scope="module")
def dovan_h():
    return login(*DOVAN)


@pytest.fixture(scope="module")
def mara_h():
    return login(*MARA)


@pytest.fixture(scope="module")
def kiri_h():
    return login(*KIRI)


@pytest.fixture(scope="module")
def player_h():
    return login(*PLAYER)


@pytest.fixture(scope="module")
def dovan_pid(dovan_h):
    return state(dovan_h)["id"]


@pytest.fixture(scope="module")
def mara_pid(mara_h):
    return state(mara_h)["id"]


@pytest.fixture(scope="module")
def kiri_pid(kiri_h):
    return state(kiri_h)["id"]


@pytest.fixture(scope="module")
def dovan_biz(dovan_h):
    bizs = requests.get(f"{API}/businesses/owned", headers=dovan_h, timeout=20).json()
    target = next((b for b in bizs if "kiosk" in b["name"].lower() or "dovan" in b["name"].lower()), bizs[0] if bizs else None)
    assert target, "Dovan must own at least one business"
    bdoc = db.businesses.find_one({"id": target["id"]})
    if not bdoc.get("hiring_open"):
        requests.post(f"{API}/businesses/{target['id']}/toggle-hiring", headers=dovan_h, timeout=20)
    return target["id"]


# Helper: clean & apply
def _clean_and_apply(applicant_h, applicant_pid, biz_id, role="Cashier"):
    db.business_applications.update_many(
        {"business_id": biz_id, "applicant_id": applicant_pid, "status": {"$in": ["pending", "offered"]}},
        {"$set": {"status": "withdrawn"}},
    )
    db.player_employment.update_many(
        {"business_id": biz_id, "employee_player_id": applicant_pid, "status": "active"},
        {"$set": {"status": "quit"}},
    )
    r = requests.post(f"{API}/jobs/market/{biz_id}/apply", headers=applicant_h,
                      json={"role": role, "message": "TEST_iter7"}, timeout=20)
    assert r.status_code == 200, f"apply failed: {r.status_code} {r.text}"
    app = db.business_applications.find_one(
        {"business_id": biz_id, "applicant_id": applicant_pid, "status": "pending"},
        {"_id": 0},
    )
    assert app, "pending app not created"
    return app


# =========== FIX 1: DECLINE-OFFER notifies owner + event ===========
class TestFix1DeclineOffer:
    def test_decline_offered_notifies_owner_and_logs_event(self, dovan_h, mara_h, dovan_biz, mara_pid, dovan_pid):
        app = _clean_and_apply(mara_h, mara_pid, dovan_biz)
        # Owner sends offer
        offer = requests.post(
            f"{API}/businesses/{dovan_biz}/player-applications/{app['id']}/offer",
            headers=dovan_h, json={"wage_per_hour": 70.0, "role": "cashier"}, timeout=20,
        )
        assert offer.status_code == 200, offer.text
        # Sanity: status is 'offered'
        a_doc = db.business_applications.find_one({"id": app["id"]})
        assert a_doc["status"] == "offered"

        # Capture owner notifs BEFORE decline
        owner_titles_before = {(n.get("title") or "") for n in (notifs(dovan_h) or [])}

        # Applicant declines
        dec = requests.post(f"{API}/jobs/employment/applications/{app['id']}/decline",
                            headers=mara_h, timeout=20)
        assert dec.status_code == 200, dec.text

        # Status -> 'declined'
        a2 = db.business_applications.find_one({"id": app["id"]})
        assert a2["status"] == "declined", f"expected 'declined' got {a2['status']}"

        # Owner gets 'Offer declined' notification (new, not already there)
        on = notifs(dovan_h) or []
        match = [n for n in on if "offer declined" in text_blob(n) and "mara" in text_blob(n)]
        assert match, f"owner missing 'Offer declined' notif. titles={[n.get('title') for n in on[:10]]}"

        # Applicant event_log contains 'You declined the offer from'
        evs = events(mara_h)
        decline_evs = [e for e in evs if "declined the offer" in event_text(e)]
        assert decline_evs, f"applicant missing decline event. sample={[event_text(e) for e in evs[:5]]}"

    def test_decline_pending_is_withdrawn_no_owner_notif(self, dovan_h, kiri_h, dovan_biz, kiri_pid):
        app = _clean_and_apply(kiri_h, kiri_pid, dovan_biz, role="Helper")
        # status is 'pending' (no offer)
        assert app["status"] == "pending"

        # Snapshot owner notifs BEFORE decline
        owner_notifs_before = notifs(dovan_h) or []
        before_offer_decl_count = sum(
            1 for n in owner_notifs_before
            if "offer declined" in text_blob(n) and "kiri" in text_blob(n)
        )

        dec = requests.post(f"{API}/jobs/employment/applications/{app['id']}/decline",
                            headers=kiri_h, timeout=20)
        assert dec.status_code == 200, dec.text

        a2 = db.business_applications.find_one({"id": app["id"]})
        assert a2["status"] == "withdrawn", f"expected 'withdrawn' got {a2['status']}"

        owner_notifs_after = notifs(dovan_h) or []
        after_offer_decl_count = sum(
            1 for n in owner_notifs_after
            if "offer declined" in text_blob(n) and "kiri" in text_blob(n)
        )
        assert after_offer_decl_count == before_offer_decl_count, \
            "owner should NOT get 'Offer declined' notif for a withdrawn pending app"


# =========== FIX 2: FIRE writes event_log for employee ===========
class TestFix2FireEvent:
    def test_fire_writes_event_log_for_employee(self, dovan_h, kiri_h, dovan_biz, kiri_pid):
        # Set up: fresh apply -> offer -> accept -> fire
        app = _clean_and_apply(kiri_h, kiri_pid, dovan_biz, role="Helper")
        off = requests.post(
            f"{API}/businesses/{dovan_biz}/player-applications/{app['id']}/offer",
            headers=dovan_h, json={"wage_per_hour": 55.0, "role": "helper"}, timeout=20,
        )
        assert off.status_code == 200, off.text
        acc = requests.post(f"{API}/jobs/employment/applications/{app['id']}/accept",
                            headers=kiri_h, timeout=20)
        assert acc.status_code == 200, acc.text
        emp = db.player_employment.find_one(
            {"business_id": dovan_biz, "employee_player_id": kiri_pid, "status": "active"}
        )
        assert emp, "active employment missing"

        fire = requests.post(
            f"{API}/businesses/{dovan_biz}/player-employees/{emp['id']}/fire",
            headers=dovan_h, timeout=20,
        )
        assert fire.status_code == 200, fire.text

        # Employment status now 'fired'
        e2 = db.player_employment.find_one({"id": emp["id"]})
        assert e2["status"] == "fired"

        # Employee event log has 'You were let go from ...'
        evs = events(kiri_h)
        let_go = [e for e in evs if "let go from" in event_text(e)]
        assert let_go, f"fired employee event_log missing 'let go from'. recent={[event_text(e) for e in evs[:5]]}"


# =========== FIX 3: RE-OFFER sends 'Offer updated' notification ===========
class TestFix3ReOffer:
    def test_first_offer_is_job_offer_then_reoffer_is_offer_updated(self, dovan_h, mara_h, dovan_biz, mara_pid):
        app = _clean_and_apply(mara_h, mara_pid, dovan_biz)

        # Snapshot mara notifs BEFORE first offer
        before = notifs(mara_h) or []
        before_job_offer = sum(1 for n in before if "job offer" in text_blob(n))
        before_offer_updated = sum(1 for n in before if "offer updated" in text_blob(n))

        # FIRST offer (pending -> offered)
        first = requests.post(
            f"{API}/businesses/{dovan_biz}/player-applications/{app['id']}/offer",
            headers=dovan_h, json={"wage_per_hour": 60.0, "role": "cashier"}, timeout=20,
        )
        assert first.status_code == 200, first.text

        mid = notifs(mara_h) or []
        mid_job_offer = sum(1 for n in mid if "job offer" in text_blob(n))
        mid_offer_updated = sum(1 for n in mid if "offer updated" in text_blob(n))
        assert mid_job_offer > before_job_offer, \
            "applicant should receive 'Job offer!' on first offer"
        assert mid_offer_updated == before_offer_updated, \
            "applicant should NOT receive 'Offer updated' on first offer"

        # SECOND offer (offered -> offered, different wage)
        second = requests.post(
            f"{API}/businesses/{dovan_biz}/player-applications/{app['id']}/offer",
            headers=dovan_h, json={"wage_per_hour": 85.0, "role": "cashier"}, timeout=20,
        )
        assert second.status_code == 200, second.text

        # wage_offer updated
        a_doc = db.business_applications.find_one({"id": app["id"]})
        assert a_doc["status"] == "offered"
        assert abs(a_doc["wage_offer"] - 85.0) < 0.01, \
            f"wage_offer not updated: {a_doc['wage_offer']}"

        # Applicant gets 'Offer updated' (new), NOT a second 'Job offer!'
        after = notifs(mara_h) or []
        after_job_offer = sum(1 for n in after if "job offer" in text_blob(n))
        after_offer_updated = sum(1 for n in after if "offer updated" in text_blob(n))
        assert after_offer_updated > mid_offer_updated, \
            f"applicant missing 'Offer updated' notif on re-offer (before={mid_offer_updated}, after={after_offer_updated})"
        assert after_job_offer == mid_job_offer, \
            "re-offer should NOT send a second 'Job offer!' notification (duplicate)"


# =========== FIX 4: Invalid shift hours rejected with 400 ===========
class TestFix4InvalidShiftHours:
    def _ensure_active_employment(self, dovan_biz, mara_pid, dovan_pid):
        emp_doc = db.player_employment.find_one(
            {"business_id": dovan_biz, "employee_player_id": mara_pid, "status": "active"}
        )
        if not emp_doc:
            emp_doc = {
                "id": uuid.uuid4().hex, "business_id": dovan_biz,
                "business_name": "Dovan's Street Kiosk",
                "owner_id": dovan_pid, "employee_player_id": mara_pid,
                "employee_name": "Mara Vance", "role": "cashier",
                "wage_per_hour": 75.0, "status": "active",
                "hired_at": datetime.now(timezone.utc).isoformat(),
                "reliability": 60, "performance": 60,
                "total_hours_worked": 0, "total_wages_earned": 0.0, "last_paid_at": None,
            }
            db.player_employment.insert_one(dict(emp_doc))
        return emp_doc["id"]

    @pytest.mark.parametrize("bad_hours", [1, 3, 5, 7, 9])
    def test_invalid_hours_return_400(self, mara_h, dovan_biz, mara_pid, dovan_pid, bad_hours):
        emp_id = self._ensure_active_employment(dovan_biz, mara_pid, dovan_pid)
        # ensure free + energy
        db.players.update_one(
            {"id": mara_pid},
            {"$set": {"current_activity": None, "status": "idle", "energy": 95, "fatigue": 10}},
        )
        r = requests.post(f"{API}/jobs/employment/{emp_id}/work",
                          headers=mara_h, json={"hours": bad_hours}, timeout=20)
        assert r.status_code == 400, f"hours={bad_hours} expected 400 got {r.status_code} {r.text}"
        detail = (r.json().get("detail") or "").lower()
        assert "2, 4, 6, or 8" in detail or "shift length" in detail, \
            f"unexpected detail: {detail!r}"
        # No activity should be set
        p = db.players.find_one({"id": mara_pid})
        cur = p.get("current_activity")
        assert (cur is None) or (cur.get("type") != "player_shift"), \
            f"shift wrongly started for invalid hours={bad_hours}: {cur}"

    @pytest.mark.parametrize("good_hours", [2, 4, 6, 8])
    def test_valid_hours_start_shift(self, mara_h, dovan_biz, mara_pid, dovan_pid, good_hours):
        emp_id = self._ensure_active_employment(dovan_biz, mara_pid, dovan_pid)
        db.players.update_one(
            {"id": mara_pid},
            {"$set": {"current_activity": None, "status": "idle", "energy": 95, "fatigue": 10}},
        )
        r = requests.post(f"{API}/jobs/employment/{emp_id}/work",
                          headers=mara_h, json={"hours": good_hours}, timeout=20)
        assert r.status_code == 200, f"hours={good_hours} expected 200 got {r.status_code} {r.text}"
        # clear the activity so the next parametrize iteration can start
        db.players.update_one(
            {"id": mara_pid},
            {"$set": {"current_activity": None, "status": "idle"}},
        )
