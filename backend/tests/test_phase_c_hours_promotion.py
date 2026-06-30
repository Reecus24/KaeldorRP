"""Tests for hours-based promotion + raise eligibility (Phase C employment balancing)."""
import os
import asyncio
import pytest
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://grind-nation.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return r.json()["token"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def mara_token():
    return _login("mara@kaeldor.com", "demo123")


@pytest.fixture(scope="module")
def dovan_token():
    return _login("dovan@kaeldor.com", "demo123")


@pytest.fixture(scope="module")
def kiri_token():
    return _login("kiri@kaeldor.com", "demo123")


# ---------- Migration ----------
def test_migration_no_legacy_shift_jobs():
    from motor.motor_asyncio import AsyncIOMotorClient
    async def run():
        cli = AsyncIOMotorClient(MONGO_URL)
        db = cli[DB_NAME]
        legacy = await db.jobs.count_documents({"promotion_req.shifts": {"$exists": True}})
        hours = await db.jobs.count_documents({"promotion_req.hours": {"$exists": True}})
        no_hw = await db.players.count_documents({"job": {"$ne": None}, "job.hours_worked": {"$exists": False}})
        cli.close()
        return legacy, hours, no_hw
    legacy, hours, no_hw = asyncio.run(run())
    assert legacy == 0, f"Found {legacy} legacy promotion_req.shifts jobs"
    assert hours >= 5, f"Expected hour-based jobs; got {hours}"
    assert no_hw == 0, f"Found {no_hw} players whose job lacks hours_worked"


# ---------- /jobs/current for Mara ----------
def test_current_job_mara_promotion_shape(mara_token):
    r = requests.get(f"{API}/jobs/current", headers=_hdr(mara_token), timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    job = data["job"]
    assert job["title"] == "Cashier"
    assert job["hours_worked"] >= 60
    assert "shifts_worked" in job  # still present
    promo = data["promotion"]
    assert promo is not None
    assert promo["target"]["title"] == "Sales Assistant"
    assert promo["need_hours"] == 40
    assert promo["have_hours"] >= 60  # >=60 because earlier shift-add tests may have incremented
    assert promo["hours_met"] is True
    assert promo["eligible"] is False
    assert isinstance(promo["reasons"], list) and any("sales" in r.lower() for r in promo["reasons"])
    assert "requirements" in promo
    assert "reliability" in promo and "boss_rel" in promo


# ---------- Promote endpoint: blocked reason ----------
def test_promote_returns_skill_block_reason(mara_token):
    r = requests.post(f"{API}/jobs/promote", headers=_hdr(mara_token), timeout=15)
    assert r.status_code == 400, r.text
    detail = r.json().get("detail", "")
    assert "sales" in detail.lower(), f"expected sales-skill block reason, got: {detail}"
    # The hours-met path must NOT report 'work N more hours' (the hours requirement is met)
    assert "more hours" not in detail.lower(), f"hours satisfied but got hours-blocked detail: {detail}"


# ---------- Shift adds real hours ----------
def _get_player_by_email(email):
    from motor.motor_asyncio import AsyncIOMotorClient
    async def run():
        cli = AsyncIOMotorClient(MONGO_URL)
        db = cli[DB_NAME]
        u = await db.users.find_one({"email": email}, {"_id": 0})
        p = await db.players.find_one({"user_id": u["id"]} if u and "id" in u else {"name": {"$regex": "."}}, {"_id": 0})
        # Player linkage seems to be name/user-coupling; fetch by name
        if email == "mara@kaeldor.com":
            p = await db.players.find_one({"name": "Mara Vance"}, {"_id": 0})
        cli.close()
        return p
    return asyncio.run(run())


def _fast_forward_activity(player_name):
    from motor.motor_asyncio import AsyncIOMotorClient
    past_iso = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    async def run():
        cli = AsyncIOMotorClient(MONGO_URL)
        db = cli[DB_NAME]
        res = await db.players.update_one(
            {"name": player_name, "current_activity": {"$ne": None}},
            {"$set": {"current_activity.ends_at": past_iso}},
        )
        cli.close()
        return res.modified_count
    return asyncio.run(run())


def test_shift_adds_real_hours_for_mara(mara_token):
    # Snapshot before
    p_before = _get_player_by_email("mara@kaeldor.com")
    if p_before.get("current_activity"):
        # clear any existing activity by fast-forwarding & resolving
        _fast_forward_activity("Mara Vance")
        requests.get(f"{API}/game/state", headers=_hdr(mara_token), timeout=15)
        p_before = _get_player_by_email("mara@kaeldor.com")

    hours_before = p_before["job"]["hours_worked"]
    total_before = p_before.get("stats_meta", {}).get("total_hours_worked", 0)
    shifts_before = p_before["job"].get("shifts_worked", 0)

    # Start a 4h cashier shift (cashier shift_options=[4,6,8])
    r = requests.post(f"{API}/jobs/work", headers=_hdr(mara_token), json={"hours": 4}, timeout=15)
    assert r.status_code == 200, r.text

    # Fast-forward then resolve
    n = _fast_forward_activity("Mara Vance")
    assert n == 1, "Failed to fast-forward activity"
    rs = requests.get(f"{API}/game/state", headers=_hdr(mara_token), timeout=20)
    assert rs.status_code == 200, rs.text

    p_after = _get_player_by_email("mara@kaeldor.com")
    hours_after = p_after["job"]["hours_worked"]
    total_after = p_after.get("stats_meta", {}).get("total_hours_worked", 0)
    shifts_after = p_after["job"].get("shifts_worked", 0)

    assert hours_after == pytest.approx(hours_before + 4, abs=0.01), \
        f"hours_worked should grow by 4: {hours_before} -> {hours_after}"
    assert total_after == pytest.approx(total_before + 4, abs=0.01)
    assert shifts_after == shifts_before + 1


# ---------- Player-employee raise eligibility ----------
def _get_dovan_business():
    from motor.motor_asyncio import AsyncIOMotorClient
    async def run():
        cli = AsyncIOMotorClient(MONGO_URL)
        db = cli[DB_NAME]
        dovan = await db.players.find_one({"name": "Dovan Reyes"}, {"_id": 0})
        biz = await db.businesses.find_one({"player_id": dovan["id"], "hiring_open": True}, {"_id": 0})
        cli.close()
        return dovan, biz
    return asyncio.run(run())


def _ensure_emp_for_kiri(biz_id):
    """Make sure Kiri is an active player_employment under Dovan's biz; create if not."""
    from motor.motor_asyncio import AsyncIOMotorClient
    async def run():
        cli = AsyncIOMotorClient(MONGO_URL)
        db = cli[DB_NAME]
        kiri = await db.players.find_one({"name": "Kiri Sol"}, {"_id": 0})
        emp = await db.player_employment.find_one(
            {"business_id": biz_id, "employee_player_id": kiri["id"], "status": "active"},
            {"_id": 0},
        )
        cli.close()
        return kiri, emp
    return asyncio.run(run())


def _force_hours_for_emp(emp_id, total_hours, hours_at_last_raise):
    from motor.motor_asyncio import AsyncIOMotorClient
    async def run():
        cli = AsyncIOMotorClient(MONGO_URL)
        db = cli[DB_NAME]
        await db.player_employment.update_one(
            {"id": emp_id},
            {"$set": {"total_hours_worked": total_hours, "hours_at_last_raise": hours_at_last_raise}},
        )
        cli.close()
    asyncio.run(run())


def test_raise_eligibility_and_message(dovan_token, kiri_token):
    dovan, biz = _get_dovan_business()
    assert biz is not None, "Dovan biz missing"
    biz_id = biz["id"]

    kiri, emp = _ensure_emp_for_kiri(biz_id)
    if not emp:
        # Apply -> offer -> accept flow
        r = requests.post(
            f"{API}/jobs/market/{biz_id}/apply",
            headers=_hdr(kiri_token),
            json={"role": "Helper", "message": "hi", "expected_wage": 30},
            timeout=15,
        )
        # tolerate 409 (already applied)
        assert r.status_code in (200, 409), r.text
        apps = requests.get(
            f"{API}/businesses/{biz_id}/player-applications", headers=_hdr(dovan_token), timeout=15
        ).json()
        kiri_apps = [a for a in apps if a["applicant_id"] == kiri["id"] and a["status"] in ("pending", "offered")]
        if not kiri_apps:
            pytest.skip("Could not find an open Kiri application")
        app_id = kiri_apps[0]["id"]
        requests.post(
            f"{API}/businesses/{biz_id}/player-applications/{app_id}/offer",
            headers=_hdr(dovan_token),
            json={"wage_per_shift": 30, "role": "Helper"},
            timeout=15,
        )
        # Accept (employment endpoint)
        empapps = requests.get(f"{API}/jobs/employment", headers=_hdr(kiri_token), timeout=15).json()
        offered = [a for a in empapps.get("applications", []) if a.get("status") == "offered" and a.get("business_id") == biz_id]
        assert offered, "no offered app for kiri"
        ra = requests.post(
            f"{API}/jobs/employment/applications/{offered[0]['id']}/accept",
            headers=_hdr(kiri_token),
            timeout=15,
        )
        assert ra.status_code == 200, ra.text
        kiri, emp = _ensure_emp_for_kiri(biz_id)
        assert emp is not None

    emp_id = emp["id"]
    prev_wage = emp.get("wage_per_shift") or 30

    # 1) Force NOT due: total=10, last_raise=0
    _force_hours_for_emp(emp_id, 10, 0)
    rk = requests.get(f"{API}/jobs/employment", headers=_hdr(kiri_token), timeout=15)
    assert rk.status_code == 200
    emps_k = rk.json().get("employments", [])
    me = next(e for e in emps_k if e["id"] == emp_id)
    assert me["raise_due"] is False
    assert me["hours_to_next_raise"] == 30

    ro = requests.get(f"{API}/businesses/{biz_id}/player-employees", headers=_hdr(dovan_token), timeout=15)
    assert ro.status_code == 200
    eo = next(e for e in ro.json() if e["id"] == emp_id)
    assert eo["raise_due"] is False
    assert eo["hours_to_next_raise"] == 30

    # 2) Force DUE: total=50, last_raise=0  -> delta=50 >= 40
    _force_hours_for_emp(emp_id, 50, 0)
    rk2 = requests.get(f"{API}/jobs/employment", headers=_hdr(kiri_token), timeout=15).json()
    me2 = next(e for e in rk2.get("employments", []) if e["id"] == emp_id)
    assert me2["raise_due"] is True
    assert me2["hours_to_next_raise"] == 0

    eo2 = next(e for e in requests.get(f"{API}/businesses/{biz_id}/player-employees", headers=_hdr(dovan_token), timeout=15).json() if e["id"] == emp_id)
    assert eo2["raise_due"] is True

    # 3) Give raise and verify resets + notification body w/ previous wage
    new_wage = round(prev_wage + 10, 2)
    rr = requests.post(
        f"{API}/businesses/{biz_id}/player-employees/{emp_id}/raise",
        headers=_hdr(dovan_token),
        json={"wage_per_shift": new_wage},
        timeout=15,
    )
    assert rr.status_code == 200, rr.text

    # raise_due flips back to False
    eo3 = next(e for e in requests.get(f"{API}/businesses/{biz_id}/player-employees", headers=_hdr(dovan_token), timeout=15).json() if e["id"] == emp_id)
    assert eo3["raise_due"] is False
    assert eo3["wage_per_shift"] == new_wage

    # Kiri's notifications contain "previously $<prev>"
    notif = requests.get(f"{API}/notifications", headers=_hdr(kiri_token), timeout=15)
    assert notif.status_code == 200
    msgs = notif.json().get("items", [])
    found = [n for n in msgs if n.get("title") == "Pay rise!" and f"previously ${prev_wage}" in n.get("body", "")]
    assert found, f"no Pay rise notification with previous wage ${prev_wage}; sample: {msgs[:3]}"


# ---------- Offer updated wage message ----------
def _ensure_clean_app_for_offer_test(biz_id, applicant_id):
    """Clear any open app from applicant to keep test idempotent."""
    from motor.motor_asyncio import AsyncIOMotorClient
    async def run():
        cli = AsyncIOMotorClient(MONGO_URL)
        db = cli[DB_NAME]
        await db.business_applications.delete_many(
            {"business_id": biz_id, "applicant_id": applicant_id, "status": {"$in": ["pending", "offered"]}}
        )
        cli.close()
    asyncio.run(run())


def test_offer_updated_message_contains_prev_and_new_wage(dovan_token, kiri_token):
    dovan, biz = _get_dovan_business()
    biz_id = biz["id"]
    # Use kiri as applicant; clean to avoid 'already employed' conflict if she has active emp
    from motor.motor_asyncio import AsyncIOMotorClient
    async def get_kiri():
        cli = AsyncIOMotorClient(MONGO_URL); db = cli[DB_NAME]
        k = await db.players.find_one({"name": "Kiri Sol"}, {"_id": 0})
        # remove any active emp so apply isn't blocked
        await db.player_employment.update_many(
            {"business_id": biz_id, "employee_player_id": k["id"], "status": "active"},
            {"$set": {"status": "quit"}},
        )
        cli.close(); return k
    kiri = asyncio.run(get_kiri())
    _ensure_clean_app_for_offer_test(biz_id, kiri["id"])

    # apply
    r = requests.post(
        f"{API}/jobs/market/{biz_id}/apply",
        headers=_hdr(kiri_token),
        json={"role": "Helper", "message": "x", "expected_wage": 30},
        timeout=15,
    )
    assert r.status_code == 200, r.text

    apps = requests.get(f"{API}/businesses/{biz_id}/player-applications", headers=_hdr(dovan_token), timeout=15).json()
    app = next(a for a in apps if a["applicant_id"] == kiri["id"] and a["status"] == "pending")
    app_id = app["id"]

    # First offer @ 60
    notif_before = requests.get(f"{API}/notifications", headers=_hdr(kiri_token), timeout=15).json().get("items", [])
    n_offer_before = sum(1 for n in notif_before if n.get("title") == "Job offer!")
    n_upd_before = sum(1 for n in notif_before if n.get("title") == "Offer updated")

    r1 = requests.post(
        f"{API}/businesses/{biz_id}/player-applications/{app_id}/offer",
        headers=_hdr(dovan_token), json={"wage_per_shift": 60, "role": "Helper"}, timeout=15,
    )
    assert r1.status_code == 200, r1.text

    # Second offer @ 85 -> should be 'Offer updated' with both wages
    r2 = requests.post(
        f"{API}/businesses/{biz_id}/player-applications/{app_id}/offer",
        headers=_hdr(dovan_token), json={"wage_per_shift": 85, "role": "Helper"}, timeout=15,
    )
    assert r2.status_code == 200, r2.text

    notif_after = requests.get(f"{API}/notifications", headers=_hdr(kiri_token), timeout=15).json().get("items", [])
    n_offer_after = sum(1 for n in notif_after if n.get("title") == "Job offer!")
    n_upd_after = sum(1 for n in notif_after if n.get("title") == "Offer updated")
    assert n_offer_after == n_offer_before + 1, "first offer should send 'Job offer!'"
    assert n_upd_after == n_upd_before + 1, "second offer should send exactly one 'Offer updated'"

    upd = next(n for n in notif_after if n.get("title") == "Offer updated")
    body = upd.get("body", "")
    assert "increased to $85" in body, f"missing new wage phrasing: {body}"
    assert "previously $60" in body, f"missing previous wage phrasing: {body}"

    # Test 'lowered to' direction with a third offer @ 40
    r3 = requests.post(
        f"{API}/businesses/{biz_id}/player-applications/{app_id}/offer",
        headers=_hdr(dovan_token), json={"wage_per_shift": 40, "role": "Helper"}, timeout=15,
    )
    assert r3.status_code == 200
    notif3 = requests.get(f"{API}/notifications", headers=_hdr(kiri_token), timeout=15).json().get("items", [])
    lowered = [n for n in notif3 if n.get("title") == "Offer updated" and "lowered to $40" in n.get("body", "") and "previously $85" in n.get("body", "")]
    assert lowered, "expected 'lowered to $40 ... previously $85' Offer updated notification"
