"""Phase C — Player Employment & Job Applications end-to-end tests.

Covers NPC applications, player job market, player business hiring, offer
acceptance, shift work + payment, owner management, and edge cases.
Uses Mongo direct writes to fast-forward resolves_at / activity ends_at to
keep the suite deterministic; time_scale is left at 1.0.
"""
import os
import time
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
    tok = r.json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def state(headers):
    """Return the player dict (flattened) — server.py /game/state wraps under 'player'."""
    r = requests.get(f"{API}/game/state", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    s = r.json()
    p = s.get("player") or s
    # bubble up commonly used activity into player for tests
    p.setdefault("current_activity", s.get("activity"))
    return p


def past_iso(minutes=60):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


# ============================ FIXTURES ============================
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
def dovan_biz(dovan_h):
    s = state(dovan_h)
    bizs = requests.get(f"{API}/businesses/owned", headers=dovan_h, timeout=20).json()
    # Get Dovan's kiosk
    target = next((b for b in bizs if "kiosk" in b["name"].lower() or "dovan" in b["name"].lower()), None)
    if not target:
        target = bizs[0] if bizs else None
    assert target, "Dovan must own at least one business"
    # ensure hiring open
    bdoc = db.businesses.find_one({"id": target["id"]})
    if not bdoc.get("hiring_open"):
        requests.post(f"{API}/businesses/{target['id']}/toggle-hiring", headers=dovan_h, timeout=20)
    return target["id"]


# ============================ NPC APPLICATIONS ============================
class TestNpcApplications:
    def test_list_jobs_and_apply(self, player_h):
        # Cleanup prior pending apps so this is clean
        pid = state(player_h)["id"]
        db.applications.update_many(
            {"player_id": pid, "status": {"$in": ["pending", "accepted"]}},
            {"$set": {"status": "withdrawn"}},
        )
        r = requests.get(f"{API}/jobs", headers=player_h, timeout=20)
        assert r.status_code == 200
        jobs = r.json()
        assert isinstance(jobs, list) and len(jobs) > 0
        # pick a low-tier job not currently held
        cur_job = state(player_h).get("job") or {}
        target = next((j for j in jobs if j["id"] != cur_job.get("job_id")), jobs[0])

        ap = requests.post(f"{API}/jobs/{target['id']}/apply", headers=player_h, json={"message": "TEST_npc"}, timeout=20)
        assert ap.status_code == 200, ap.text
        body = ap.json()
        assert body["ok"] and body["resolves_in_minutes"] > 0

        # duplicate -> 409
        dup = requests.post(f"{API}/jobs/{target['id']}/apply", headers=player_h, json={}, timeout=20)
        assert dup.status_code == 409

        # listed in /jobs/applications as pending
        apps = requests.get(f"{API}/jobs/applications", headers=player_h, timeout=20).json()
        mine = [a for a in apps if a["job_id"] == target["id"] and a["status"] == "pending"]
        assert mine, "pending application not found"
        self.app_id = mine[0]["id"]

        # Fast-forward resolves_at into the past
        db.applications.update_one({"id": mine[0]["id"]}, {"$set": {"resolves_at": past_iso(120)}})

        # Trigger resolve via state read (resolve_npc_applications hooked here)
        state(player_h)
        apps2 = requests.get(f"{API}/jobs/applications", headers=player_h, timeout=20).json()
        resolved = next((a for a in apps2 if a["id"] == mine[0]["id"]), None)
        assert resolved is not None
        assert resolved["status"] in ("accepted", "rejected"), f"got {resolved['status']}"
        if resolved["status"] == "accepted":
            assert isinstance(resolved.get("wage_offer"), (int, float)) and resolved["wage_offer"] > 0
        else:
            assert resolved.get("reason"), "rejection must include a human reason"

    def test_criminal_record_blocks_application(self, kiri_h):
        # set kiri legal_reputation < 25 directly
        pid = state(kiri_h)["id"]
        old_legal = db.players.find_one({"id": pid}).get("legal_reputation", 100)
        try:
            db.players.update_one({"id": pid}, {"$set": {"legal_reputation": 10}})
            jobs = requests.get(f"{API}/jobs", headers=kiri_h, timeout=20).json()
            jid = jobs[0]["id"]
            r = requests.post(f"{API}/jobs/{jid}/apply", headers=kiri_h, json={}, timeout=20)
            assert r.status_code == 403, f"expected 403 got {r.status_code} {r.text}"
        finally:
            db.players.update_one({"id": pid}, {"$set": {"legal_reputation": old_legal}})

    def test_accept_offer_auto_withdraws_others(self, player_h):
        pid = state(player_h)["id"]
        # ensure we have an 'accepted' application — force one
        jobs = requests.get(f"{API}/jobs", headers=player_h, timeout=20).json()
        cur_job = state(player_h).get("job") or {}
        candidates = [j for j in jobs if j["id"] != cur_job.get("job_id")]
        j1, j2 = candidates[0], candidates[1]
        # cleanup
        db.applications.update_many(
            {"player_id": pid, "status": {"$in": ["pending", "accepted"]}},
            {"$set": {"status": "withdrawn"}},
        )
        # apply to both
        for j in (j1, j2):
            requests.post(f"{API}/jobs/{j['id']}/apply", headers=player_h, json={}, timeout=20)
        # force one accepted, other pending
        a1 = db.applications.find_one({"player_id": pid, "job_id": j1["id"], "status": "pending"})
        a2 = db.applications.find_one({"player_id": pid, "job_id": j2["id"], "status": "pending"})
        assert a1 and a2
        db.applications.update_one({"id": a1["id"]}, {"$set": {"status": "accepted", "wage_offer": 25.0, "resolved": True}})
        # accept
        r = requests.post(f"{API}/jobs/applications/{a1['id']}/accept", headers=player_h, timeout=20)
        assert r.status_code == 200, r.text
        # j2 should be withdrawn
        a2x = db.applications.find_one({"id": a2["id"]})
        assert a2x["status"] == "withdrawn", f"expected withdrawn, got {a2x['status']}"
        # player.job set
        assert state(player_h)["job"]["job_id"] == j1["id"]


# ============================ PLAYER JOB MARKET ============================
class TestJobMarket:
    def test_market_lists_hiring_businesses(self, mara_h, dovan_biz):
        r = requests.get(f"{API}/jobs/market", headers=mara_h, timeout=20)
        assert r.status_code == 200
        listings = r.json()
        ids = [b["business_id"] for b in listings]
        assert dovan_biz in ids, f"Dovan biz {dovan_biz} missing from market"
        listing = next(b for b in listings if b["business_id"] == dovan_biz)
        assert "owner_name" in listing
        assert listing["base_shift_wage"] > 0

    def test_market_apply_and_duplicate_blocked(self, mara_h, dovan_biz, mara_pid):
        # cleanup prior pending/offered apps for mara at this biz
        db.business_applications.update_many(
            {"business_id": dovan_biz, "applicant_id": mara_pid, "status": {"$in": ["pending", "offered"]}},
            {"$set": {"status": "withdrawn"}},
        )
        db.player_employment.update_many(
            {"business_id": dovan_biz, "employee_player_id": mara_pid, "status": "active"},
            {"$set": {"status": "quit"}},
        )

        r = requests.post(f"{API}/jobs/market/{dovan_biz}/apply", headers=mara_h,
                          json={"role": "Cashier", "message": "TEST_market"}, timeout=20)
        assert r.status_code == 200, r.text
        # duplicate -> 409
        dup = requests.post(f"{API}/jobs/market/{dovan_biz}/apply", headers=mara_h,
                            json={"role": "Cashier", "message": "dup"}, timeout=20)
        assert dup.status_code == 409
        # market listing reflects pending
        listings = requests.get(f"{API}/jobs/market", headers=mara_h, timeout=20).json()
        listing = next(b for b in listings if b["business_id"] == dovan_biz)
        assert listing["my_status"] in ("pending", "offered")

    def test_apply_to_closed_business_400(self, mara_h, dovan_h, dovan_biz):
        # close hiring
        requests.post(f"{API}/businesses/{dovan_biz}/toggle-hiring", headers=dovan_h, timeout=20)
        try:
            # need a player not currently applied/employed — use kiri
            kh = login(*KIRI)
            kpid = state(kh)["id"]
            db.business_applications.update_many(
                {"business_id": dovan_biz, "applicant_id": kpid},
                {"$set": {"status": "withdrawn"}},
            )
            r = requests.post(f"{API}/jobs/market/{dovan_biz}/apply", headers=kh,
                              json={"role": "Helper"}, timeout=20)
            assert r.status_code == 400, f"expected 400 closed got {r.status_code}"
        finally:
            # reopen
            bdoc = db.businesses.find_one({"id": dovan_biz})
            if not bdoc.get("hiring_open"):
                requests.post(f"{API}/businesses/{dovan_biz}/toggle-hiring", headers=dovan_h, timeout=20)


# ============================ OWNER HIRING FLOW ============================
class TestOwnerHiring:
    def test_owner_sees_applications_with_snapshot(self, dovan_h, dovan_biz, mara_pid):
        r = requests.get(f"{API}/businesses/{dovan_biz}/player-applications", headers=dovan_h, timeout=20)
        assert r.status_code == 200, r.text
        apps = r.json()
        mine = [a for a in apps if a["applicant_id"] == mara_pid]
        assert mine, "Mara's application missing for owner"
        a = mine[0]
        assert a.get("stats"), "missing stats snapshot"
        assert a.get("recommended_wage", 0) > 0

    def test_owner_sends_offer_and_applicant_receives_it(self, dovan_h, mara_h, dovan_biz, mara_pid):
        # find mara's pending app
        apps = requests.get(f"{API}/businesses/{dovan_biz}/player-applications", headers=dovan_h, timeout=20).json()
        a = next(x for x in apps if x["applicant_id"] == mara_pid)
        offer = requests.post(
            f"{API}/businesses/{dovan_biz}/player-applications/{a['id']}/offer",
            headers=dovan_h, json={"wage_per_shift": 75.5, "role": "Cashier"}, timeout=20,
        )
        assert offer.status_code == 200, offer.text

        # applicant sees it in /jobs/employment
        emp = requests.get(f"{API}/jobs/employment", headers=mara_h, timeout=20).json()
        offered = [x for x in emp["applications"] if x["id"] == a["id"]]
        assert offered, "offered app not visible to applicant"
        assert offered[0]["status"] == "offered"
        assert abs(offered[0]["wage_offer"] - 75.5) < 0.01

        # notification on applicant side
        notifs = requests.get(f"{API}/notifications", headers=mara_h, timeout=20).json()
        items = notifs.get("items") if isinstance(notifs, dict) else notifs
        assert any("offer" in (n.get("title", "") + n.get("body", "")).lower() for n in items), "offer notification missing"

    def test_accept_offer_creates_employment_and_notifies_owner(self, dovan_h, mara_h, dovan_biz, mara_pid):
        # find the offered app
        emp = requests.get(f"{API}/jobs/employment", headers=mara_h, timeout=20).json()
        offered = next((x for x in emp["applications"] if x["status"] == "offered" and x["business_id"] == dovan_biz), None)
        assert offered, "no offered app to accept"
        r = requests.post(f"{API}/jobs/employment/applications/{offered['id']}/accept",
                          headers=mara_h, timeout=20)
        assert r.status_code == 200, r.text

        # active employment exists
        emp2 = requests.get(f"{API}/jobs/employment", headers=mara_h, timeout=20).json()
        actives = [e for e in emp2["employments"] if e["business_id"] == dovan_biz]
        assert actives, "active employment not created"

        # owner notification 'Offer accepted'
        notifs = requests.get(f"{API}/notifications", headers=dovan_h, timeout=20).json()
        items = notifs.get("items") if isinstance(notifs, dict) else notifs
        assert any("accepted" in (n.get("title", "") + n.get("body", "")).lower() for n in items), "owner missing accepted notif"

    def test_accept_invalid_offer_400(self, mara_h):
        # random id
        r = requests.post(f"{API}/jobs/employment/applications/doesnotexist/accept",
                          headers=mara_h, timeout=20)
        assert r.status_code == 400


# ============================ SHIFT FLOW ============================
class TestShiftWork:
    def test_work_shift_pays_wage_and_updates_business(self, mara_h, dovan_h, dovan_biz, mara_pid, dovan_pid):
        # ensure mara has an active employment at dovan's biz — bootstrap one via DB if needed
        emp_doc = db.player_employment.find_one({"business_id": dovan_biz, "employee_player_id": mara_pid, "status": "active"})
        if not emp_doc:
            import uuid as _u
            from datetime import datetime as _dt
            emp_doc = {
                "id": _u.uuid4().hex, "business_id": dovan_biz, "business_name": "Dovan's Street Kiosk",
                "owner_id": dovan_pid, "employee_player_id": mara_pid, "employee_name": "Mara Vance",
                "role": "Cashier", "wage_per_shift": 80.0, "status": "active",
                "hired_at": _dt.utcnow().isoformat(), "reliability": 60, "performance": 60,
                "total_hours_worked": 0, "total_wages_earned": 0.0, "last_paid_at": None,
            }
            db.player_employment.insert_one(emp_doc)
        emp = {k: v for k, v in emp_doc.items() if k != "_id"}

        money_before = state(mara_h)["cash"]
        biz_before = db.businesses.find_one({"id": dovan_biz})
        biz_cash_before = biz_before.get("cash", 0)

        # ensure not busy AND has energy
        db.players.update_one({"id": mara_pid}, {"$set": {"current_activity": None, "energy": 95, "fatigue": 10}})

        r = requests.post(f"{API}/jobs/employment/{emp['id']}/work",
                          headers=mara_h, json={"hours": 4}, timeout=20)
        assert r.status_code == 200, r.text

        # fast-forward activity end_time
        pdoc = db.players.find_one({"id": mara_pid})
        act = pdoc.get("current_activity") or {}
        assert act, "shift activity missing"
        # try common end-time field names
        for fld in ("ends_at", "end_time", "end_at", "completes_at"):
            if act.get(fld):
                act[fld] = past_iso(120)
        # Mongo set
        db.players.update_one({"id": mara_pid}, {"$set": {"current_activity": act}})

        # trigger resolve via state read
        s2 = state(mara_h)
        # the shift activity should be done (current_activity gone or status idle)
        assert (s2.get("current_activity") is None) or (s2.get("current_activity", {}).get("type") != "player_shift"), \
            f"shift didn't complete: {s2.get('current_activity')}"
        money_after = s2["cash"]
        assert money_after > money_before, f"wage not paid: before {money_before} after {money_after}"

        # employment stats updated
        emp_after = db.player_employment.find_one({"id": emp["id"]})
        assert emp_after["total_hours_worked"] >= 4
        assert emp_after["total_wages_earned"] > 0

        # owner notification 'finished a shift'
        notifs = requests.get(f"{API}/notifications", headers=dovan_h, timeout=20).json()
        items = notifs.get("items") if isinstance(notifs, dict) else notifs
        assert any("shift" in (n.get("title", "") + n.get("body", "")).lower() for n in items), "owner missing shift notif"


# ============================ OWNER MGMT: RAISE / FIRE / QUIT ============================
class TestOwnerManagement:
    def test_raise_and_employee_lists(self, dovan_h, mara_h, dovan_biz, mara_pid):
        emps = requests.get(f"{API}/businesses/{dovan_biz}/player-employees", headers=dovan_h, timeout=20).json()
        target = next((e for e in emps if e["employee_player_id"] == mara_pid), None)
        assert target, "owner doesn't see employee"
        r = requests.post(f"{API}/businesses/{dovan_biz}/player-employees/{target['id']}/raise",
                          headers=dovan_h, json={"wage_per_shift": 120.0}, timeout=20)
        assert r.status_code == 200
        emp_doc = db.player_employment.find_one({"id": target["id"]})
        assert abs(emp_doc["wage_per_shift"] - 120.0) < 0.01

    def test_employee_quit(self, mara_h, dovan_biz, mara_pid):
        emp = db.player_employment.find_one({"business_id": dovan_biz, "employee_player_id": mara_pid, "status": "active"})
        assert emp, "no active emp to quit"
        r = requests.post(f"{API}/jobs/employment/{emp['id']}/quit", headers=mara_h, timeout=20)
        assert r.status_code == 200
        assert db.player_employment.find_one({"id": emp["id"]})["status"] == "quit"

    def test_owner_fire(self, dovan_h, kiri_h, dovan_biz):
        kpid = state(kiri_h)["id"]
        # ensure hiring open
        bdoc = db.businesses.find_one({"id": dovan_biz})
        if not bdoc.get("hiring_open"):
            requests.post(f"{API}/businesses/{dovan_biz}/toggle-hiring", headers=dovan_h, timeout=20)
        # cleanup
        db.business_applications.update_many(
            {"business_id": dovan_biz, "applicant_id": kpid}, {"$set": {"status": "withdrawn"}}
        )
        db.player_employment.update_many(
            {"business_id": dovan_biz, "employee_player_id": kpid, "status": "active"},
            {"$set": {"status": "quit"}},
        )
        # apply -> offer -> accept -> fire
        r = requests.post(f"{API}/jobs/market/{dovan_biz}/apply", headers=kiri_h,
                          json={"role": "Helper"}, timeout=20)
        assert r.status_code == 200, r.text
        app = db.business_applications.find_one({"business_id": dovan_biz, "applicant_id": kpid, "status": "pending"})
        offer = requests.post(f"{API}/businesses/{dovan_biz}/player-applications/{app['id']}/offer",
                              headers=dovan_h, json={"wage_per_shift": 50.0, "role": "Helper"}, timeout=20)
        assert offer.status_code == 200
        acc = requests.post(f"{API}/jobs/employment/applications/{app['id']}/accept", headers=kiri_h, timeout=20)
        assert acc.status_code == 200
        emp = db.player_employment.find_one({"business_id": dovan_biz, "employee_player_id": kpid, "status": "active"})
        assert emp
        fire = requests.post(f"{API}/businesses/{dovan_biz}/player-employees/{emp['id']}/fire",
                             headers=dovan_h, timeout=20)
        assert fire.status_code == 200
        assert db.player_employment.find_one({"id": emp["id"]})["status"] == "fired"


# ============================ EDGE CASES ============================
class TestEdgeCases:
    def test_reject_application_path(self, dovan_h, kiri_h, dovan_biz):
        kpid = state(kiri_h)["id"]
        db.business_applications.update_many(
            {"business_id": dovan_biz, "applicant_id": kpid, "status": {"$in": ["pending", "offered"]}},
            {"$set": {"status": "withdrawn"}},
        )
        # apply
        r = requests.post(f"{API}/jobs/market/{dovan_biz}/apply", headers=kiri_h,
                          json={"role": "Helper"}, timeout=20)
        assert r.status_code == 200
        app = db.business_applications.find_one({"business_id": dovan_biz, "applicant_id": kpid, "status": "pending"})
        rej = requests.post(f"{API}/businesses/{dovan_biz}/player-applications/{app['id']}/reject",
                            headers=dovan_h, timeout=20)
        assert rej.status_code == 200
        assert db.business_applications.find_one({"id": app["id"]})["status"] == "rejected"
        # rejection notification
        notifs = requests.get(f"{API}/notifications", headers=kiri_h, timeout=20).json()
        items = notifs.get("items") if isinstance(notifs, dict) else notifs
        assert any("declined" in (n.get("title", "") + n.get("body", "")).lower() for n in items)

    def test_offer_expiry_for_npc_apps(self, player_h):
        pid = state(player_h)["id"]
        jobs = requests.get(f"{API}/jobs", headers=player_h, timeout=20).json()
        # cleanup
        db.applications.update_many(
            {"player_id": pid, "status": {"$in": ["pending", "accepted"]}},
            {"$set": {"status": "withdrawn"}},
        )
        cur = state(player_h).get("job") or {}
        target = next(j for j in jobs if j["id"] != cur.get("job_id"))
        requests.post(f"{API}/jobs/{target['id']}/apply", headers=player_h, json={}, timeout=20)
        a = db.applications.find_one({"player_id": pid, "job_id": target["id"], "status": "pending"})
        # force accepted with expired offer
        db.applications.update_one({"id": a["id"]}, {"$set": {
            "status": "accepted", "wage_offer": 30.0, "resolved": True,
            "offer_expires_at": past_iso(60),
        }})
        state(player_h)  # triggers resolve_npc_applications
        a2 = db.applications.find_one({"id": a["id"]})
        assert a2["status"] == "expired", f"expected expired got {a2['status']}"

    def test_toggle_hiring_persists(self, dovan_h, dovan_biz):
        b0 = db.businesses.find_one({"id": dovan_biz})
        cur = b0.get("hiring_open", False)
        r = requests.post(f"{API}/businesses/{dovan_biz}/toggle-hiring", headers=dovan_h, timeout=20)
        assert r.status_code == 200
        assert r.json()["hiring_open"] == (not cur)
        # restore
        requests.post(f"{API}/businesses/{dovan_biz}/toggle-hiring", headers=dovan_h, timeout=20)


# ============================ TIME SCALE GUARD ============================
def test_time_scale_unchanged():
    cfg = db.config.find_one() or {}
    ts = cfg.get("time_scale", 1.0)
    assert abs(ts - 1.0) < 0.001, f"time_scale not 1.0 (={ts}) — production requires real-time"
