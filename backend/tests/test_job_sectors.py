"""Backend tests for Job Sectors feature (iteration 29).

Covers:
- Player: GET /api/jobs/sectors (browser) and GET /api/jobs/sectors/{id} (detail)
- Admin CRUD: /api/admin/job-sectors (list/create/update/delete)
- Coverage: all DB jobs are covered by seeded sectors (no unassigned virtual).
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@kaeldor.com", "password": "admin123"}
PLAYER = {"email": "player@kaeldor.com", "password": "player123"}

EXPECTED_SECTORS = {
    "sector_retail", "sector_hospitality", "sector_logistics",
    "sector_corporate", "sector_trades", "sector_military", "sector_public",
}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    body = r.json()
    tok = body.get("access_token") or body.get("token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


@pytest.fixture(scope="module")
def player_sess():
    return _login(PLAYER)


@pytest.fixture(scope="module")
def admin_sess():
    return _login(ADMIN)


# ---- Player: sector browser ----

def test_list_sectors_returns_seven_expected(player_sess):
    r = player_sess.get(f"{API}/jobs/sectors", timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list) and len(data) >= 7
    ids = {s["id"] for s in data}
    missing = EXPECTED_SECTORS - ids
    assert not missing, f"missing seeded sectors: {missing}"
    for s in data:
        assert "name" in s and "job_count" in s and "open_count" in s
        assert isinstance(s["job_count"], int)
        assert isinstance(s["open_count"], int)
        assert s["open_count"] <= s["job_count"]


def test_no_unassigned_virtual_sector(player_sess):
    r = player_sess.get(f"{API}/jobs/sectors", timeout=20)
    ids = {s["id"] for s in r.json()}
    assert "unassigned" not in ids, "unexpected virtual General Listings sector present"


def test_sum_job_counts_matches_total_jobs(player_sess, admin_sess):
    r = player_sess.get(f"{API}/jobs/sectors", timeout=20)
    total_by_sector = sum(s["job_count"] for s in r.json())
    r2 = admin_sess.get(f"{API}/admin/job-sectors", timeout=20)
    assert r2.status_code == 200, r2.text
    all_jobs = r2.json().get("jobs", [])
    assert total_by_sector == len(all_jobs), \
        f"sector sum {total_by_sector} != total jobs {len(all_jobs)}"


def test_retail_sector_detail_returns_retail_jobs(player_sess):
    r = player_sess.get(f"{API}/jobs/sectors/sector_retail", timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sector"]["id"] == "sector_retail"
    titles = {j["title"] for j in body["jobs"]}
    for t in ("Cashier", "Sales Assistant", "Store Manager"):
        assert t in titles, f"Retail missing {t}; got {titles}"


def test_logistics_sector_detail_returns_logistics_jobs(player_sess):
    r = player_sess.get(f"{API}/jobs/sectors/sector_logistics", timeout=20)
    assert r.status_code == 200
    titles = {j["title"] for j in r.json()["jobs"]}
    for t in ("Delivery Driver", "Warehouse Worker", "Logistics Manager"):
        assert t in titles, f"Logistics missing {t}; got {titles}"


def test_retail_and_logistics_are_disjoint(player_sess):
    a = {j["id"] for j in player_sess.get(f"{API}/jobs/sectors/sector_retail").json()["jobs"]}
    b = {j["id"] for j in player_sess.get(f"{API}/jobs/sectors/sector_logistics").json()["jobs"]}
    assert a and b and a.isdisjoint(b), "sectors overlap unexpectedly"


def test_unknown_sector_404(player_sess):
    r = player_sess.get(f"{API}/jobs/sectors/does_not_exist", timeout=20)
    assert r.status_code == 404


def test_jobs_have_qualified_flag(player_sess):
    r = player_sess.get(f"{API}/jobs/sectors/sector_retail", timeout=20)
    for j in r.json()["jobs"]:
        assert "qualified" in j and isinstance(j["qualified"], bool)


# ---- Admin CRUD ----

def test_admin_list_job_sectors(admin_sess):
    r = admin_sess.get(f"{API}/admin/job-sectors", timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "sectors" in body and "jobs" in body and "assigned" in body
    ids = {s["id"] for s in body["sectors"]}
    assert EXPECTED_SECTORS.issubset(ids)
    # every sector should have job_count field
    for s in body["sectors"]:
        assert "job_count" in s


def test_player_cannot_access_admin_sectors(player_sess):
    r = player_sess.get(f"{API}/admin/job-sectors", timeout=20)
    assert r.status_code in (401, 403), f"expected forbidden, got {r.status_code}"


def test_admin_crud_create_update_delete(admin_sess, player_sess):
    # pick an existing job to assign
    lst = admin_sess.get(f"{API}/admin/job-sectors").json()
    job_id = lst["jobs"][0]["id"]
    job2_id = lst["jobs"][1]["id"]

    # CREATE
    payload = {
        "name": "TEST_QA_Sector",
        "icon": "Briefcase",
        "desc": "Temp QA sector",
        "active": True,
        "order": 50,
        "job_ids": [job_id],
    }
    r = admin_sess.post(f"{API}/admin/job-sectors", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    new_id = r.json()["id"]
    assert isinstance(new_id, str) and len(new_id) > 0

    try:
        # verify list contains new sector
        listing = admin_sess.get(f"{API}/admin/job-sectors").json()
        match = [s for s in listing["sectors"] if s["id"] == new_id]
        assert match, "new sector not in admin list"
        assert match[0]["name"] == "TEST_QA_Sector"
        assert match[0]["job_count"] == 1

        # verify visible to player
        pr = player_sess.get(f"{API}/jobs/sectors").json()
        pmatch = [s for s in pr if s["id"] == new_id]
        assert pmatch, "new sector not visible to player"
        assert pmatch[0]["job_count"] == 1

        # verify sector detail
        d = player_sess.get(f"{API}/jobs/sectors/{new_id}").json()
        assert d["sector"]["id"] == new_id
        assert len(d["jobs"]) == 1 and d["jobs"][0]["id"] == job_id

        # UPDATE (change name + jobs)
        upd = {**payload, "name": "TEST_QA_Sector_Updated", "job_ids": [job_id, job2_id]}
        r = admin_sess.put(f"{API}/admin/job-sectors/{new_id}", json=upd, timeout=20)
        assert r.status_code == 200, r.text
        listing2 = admin_sess.get(f"{API}/admin/job-sectors").json()
        m2 = [s for s in listing2["sectors"] if s["id"] == new_id][0]
        assert m2["name"] == "TEST_QA_Sector_Updated"
        assert m2["job_count"] == 2

        # DELETE
        r = admin_sess.delete(f"{API}/admin/job-sectors/{new_id}", timeout=20)
        assert r.status_code == 200, r.text
        listing3 = admin_sess.get(f"{API}/admin/job-sectors").json()
        assert not [s for s in listing3["sectors"] if s["id"] == new_id]

        # detail should now 404
        r = player_sess.get(f"{API}/jobs/sectors/{new_id}", timeout=20)
        assert r.status_code == 404
    finally:
        # best-effort cleanup
        admin_sess.delete(f"{API}/admin/job-sectors/{new_id}")


def test_apply_flow_within_sector(player_sess):
    """Player should be able to view + apply within sector (unless already applied/current)."""
    # Neo is a Cashier in retail; find retail jobs, ensure at least one exists.
    r = player_sess.get(f"{API}/jobs/sectors/sector_retail").json()
    jobs = r["jobs"]
    assert jobs, "retail has no jobs"
    # pick a qualified job (may or may not be current). Just verify apply endpoint responds cleanly.
    qj = next((j for j in jobs if j.get("qualified")), None)
    assert qj, "no qualified job for player in retail"
    # Attempt apply — may fail with reason (already current/applied) but endpoint must be reachable.
    resp = player_sess.post(f"{API}/jobs/{qj['id']}/apply", json={"message": "TEST"}, timeout=20)
    assert resp.status_code in (200, 400, 409), f"apply endpoint unexpected: {resp.status_code} {resp.text}"
