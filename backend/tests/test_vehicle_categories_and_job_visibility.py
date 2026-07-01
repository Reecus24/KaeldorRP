"""Iteration 34 — Vehicle Dealer Categorization + Progressive Job Visibility.

Covers:
- Public /api/vehicle-categories (list + counts) and /api/vehicle-categories/{id} (filtered)
- Admin CRUD /api/admin/vehicle-categories (+ vehicle assignment helper)
- Admin PUT /api/admin/jobs/{job_id}/visibility toggle
- Player-side job listings honour visible_in_listings (sector detail + job_count decrement)
- Hidden jobs remain fetchable/promotable (job doc still exists w/ same fields).
Restores state (cleaner visible; seed vehicle categories intact) before exit.
"""
import os
import uuid
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except FileNotFoundError:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL is not set")


BASE = _load_backend_url()
API = f"{BASE}/api"

ADMIN = ("admin@kaeldor.com", "admin123")
PLAYER = ("shiftplayer@kaeldor.com", "demo123")

SEED_CATEGORY_IDS = {"cat_bikes", "cat_economy", "cat_utility", "cat_luxury"}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def player_token():
    return _login(*PLAYER)


@pytest.fixture(scope="module")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def player_h(player_token):
    return {"Authorization": f"Bearer {player_token}"}


# ----------------------------- PUBLIC / PLAYER -----------------------------
class TestPublicVehicleCategories:
    def test_list_categories(self, player_h):
        r = requests.get(f"{API}/vehicle-categories", headers=player_h, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "categories" in data and "owned" in data
        ids = {c["id"] for c in data["categories"]}
        # 4 seed categories must be present
        assert SEED_CATEGORY_IDS.issubset(ids), f"missing seed cats: {SEED_CATEGORY_IDS - ids}"
        for c in data["categories"]:
            assert "name" in c and "vehicle_count" in c and "desc" in c

    def test_category_detail_bikes(self, player_h):
        r = requests.get(f"{API}/vehicle-categories/cat_bikes", headers=player_h, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["category"]["id"] == "cat_bikes"
        # every listing must belong to this cat (backend filter)
        for v in d["listings"]:
            assert v.get("category_id") == "cat_bikes"

    def test_category_detail_other_catchall(self, player_h):
        r = requests.get(f"{API}/vehicle-categories/other", headers=player_h, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["category"]["id"] == "other"
        # if any listings exist here, their category_id must be missing/inactive
        for v in d["listings"]:
            cat_id = v.get("category_id")
            assert cat_id is None or cat_id not in SEED_CATEGORY_IDS

    def test_category_detail_404(self, player_h):
        r = requests.get(f"{API}/vehicle-categories/does-not-exist", headers=player_h, timeout=30)
        assert r.status_code == 404


# ------------------------------- ADMIN CRUD --------------------------------
class TestAdminVehicleCategories:
    def test_admin_list(self, admin_h):
        r = requests.get(f"{API}/admin/vehicle-categories", headers=admin_h, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "categories" in data and "vehicles" in data
        ids = {c["id"] for c in data["categories"]}
        assert SEED_CATEGORY_IDS.issubset(ids)
        for c in data["categories"]:
            assert "vehicle_count" in c
        for v in data["vehicles"]:
            assert "id" in v and "name" in v

    def test_non_admin_forbidden(self, player_h):
        r = requests.get(f"{API}/admin/vehicle-categories", headers=player_h, timeout=30)
        assert r.status_code in (401, 403)

    def test_create_edit_delete_and_assignment_flow(self, admin_h):
        # Pick an existing vehicle to assign (from admin list)
        vlist = requests.get(f"{API}/admin/vehicle-categories", headers=admin_h, timeout=30).json()["vehicles"]
        assert vlist, "no vehicles seeded"
        target_vehicle = vlist[0]  # cheapest
        original_cat_id = target_vehicle.get("category_id")
        vid = target_vehicle["id"]

        # CREATE new test category with this vehicle assigned
        name = f"TEST_cat_{uuid.uuid4().hex[:6]}"
        body = {"name": name, "desc": "iter34 test", "icon": "Car", "active": True,
                "order": 500, "vehicle_ids": [vid]}
        r = requests.post(f"{API}/admin/vehicle-categories", headers=admin_h, json=body, timeout=30)
        assert r.status_code == 200, r.text
        new_id = r.json()["id"]
        assert new_id.startswith("vcat_")

        try:
            # verify assignment via admin list
            v_after = next(v for v in requests.get(f"{API}/admin/vehicle-categories", headers=admin_h).json()["vehicles"] if v["id"] == vid)
            assert v_after.get("category_id") == new_id, "vehicle not reassigned to new category"

            # public detail should include this vehicle
            det = requests.get(f"{API}/vehicle-categories/{new_id}", headers=admin_h, timeout=30).json()
            assert any(v["id"] == vid for v in det["listings"])

            # EDIT — rename + drop the vehicle
            body_upd = {"name": name + "_x", "desc": "renamed", "icon": "Bike", "active": True,
                        "order": 500, "vehicle_ids": []}
            r = requests.put(f"{API}/admin/vehicle-categories/{new_id}", headers=admin_h, json=body_upd, timeout=30)
            assert r.status_code == 200, r.text
            det2 = requests.get(f"{API}/vehicle-categories/{new_id}", headers=admin_h, timeout=30).json()
            assert not any(v["id"] == vid for v in det2["listings"])
            # vehicle now uncategorized
            v_now = next(v for v in requests.get(f"{API}/admin/vehicle-categories", headers=admin_h).json()["vehicles"] if v["id"] == vid)
            assert v_now.get("category_id") in (None, "")

            # 404 on unknown update
            r = requests.put(f"{API}/admin/vehicle-categories/nope_id", headers=admin_h, json=body_upd, timeout=30)
            assert r.status_code == 404
        finally:
            # DELETE the test category
            r = requests.delete(f"{API}/admin/vehicle-categories/{new_id}", headers=admin_h, timeout=30)
            assert r.status_code == 200

            # public detail now 404 for deleted cat
            r = requests.get(f"{API}/vehicle-categories/{new_id}", headers=admin_h, timeout=30)
            assert r.status_code == 404

            # restore vehicle's original category assignment
            if original_cat_id:
                # find the original cat's current vehicle list and re-attach
                cur_veh = requests.get(f"{API}/admin/vehicle-categories", headers=admin_h).json()["vehicles"]
                assigned = [v["id"] for v in cur_veh if v.get("category_id") == original_cat_id]
                if vid not in assigned:
                    assigned.append(vid)
                orig_cat = next(c for c in requests.get(f"{API}/admin/vehicle-categories", headers=admin_h).json()["categories"] if c["id"] == original_cat_id)
                body_restore = {"name": orig_cat["name"], "desc": orig_cat.get("desc", ""),
                                "icon": orig_cat.get("icon", "Car"), "active": bool(orig_cat.get("active", True)),
                                "order": orig_cat.get("order", 50), "vehicle_ids": assigned}
                r = requests.put(f"{API}/admin/vehicle-categories/{original_cat_id}", headers=admin_h, json=body_restore, timeout=30)
                assert r.status_code == 200

    def test_seed_categories_still_present(self, admin_h):
        cats = requests.get(f"{API}/admin/vehicle-categories", headers=admin_h).json()["categories"]
        ids = {c["id"] for c in cats}
        assert SEED_CATEGORY_IDS.issubset(ids), "seed categories were lost!"


# --------------------------- JOB VISIBILITY --------------------------------
class TestJobVisibility:
    JOB_ID = "cleaner"
    SECTOR_ID = "sector_trades"  # cleaner's sector

    def _sector_detail(self, headers):
        return requests.get(f"{API}/jobs/sectors/{self.SECTOR_ID}", headers=headers, timeout=30)

    def _sector_list(self, headers):
        return requests.get(f"{API}/jobs/sectors", headers=headers, timeout=30)

    def test_hide_removes_cleaner_from_sector_and_decrements_count(self, admin_h, player_h):
        # Baseline
        det0 = self._sector_detail(player_h).json()
        base_jobs = det0.get("jobs", [])
        base_ids = {j["id"] for j in base_jobs}
        assert self.JOB_ID in base_ids, f"cleaner missing from baseline {self.SECTOR_ID}: {base_ids}"
        base_count = next((s["job_count"] for s in self._sector_list(player_h).json() if s["id"] == self.SECTOR_ID), None)
        assert base_count is not None

        # HIDE
        r = requests.put(f"{API}/admin/jobs/{self.JOB_ID}/visibility", headers=admin_h,
                         json={"visible": False}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["visible_in_listings"] is False

        try:
            det1 = self._sector_detail(player_h).json()
            hidden_ids = {j["id"] for j in det1.get("jobs", [])}
            assert self.JOB_ID not in hidden_ids, "cleaner still listed after hide"
            new_count = next((s["job_count"] for s in self._sector_list(player_h).json() if s["id"] == self.SECTOR_ID), None)
            assert new_count == base_count - 1, f"job_count should drop by 1: {base_count} -> {new_count}"

            # Non-admin can't toggle
            r_forbidden = requests.put(f"{API}/admin/jobs/{self.JOB_ID}/visibility", headers=player_h,
                                       json={"visible": True}, timeout=30)
            assert r_forbidden.status_code in (401, 403)

            # 404 for unknown job
            r_404 = requests.put(f"{API}/admin/jobs/nope_job_xyz/visibility", headers=admin_h,
                                 json={"visible": True}, timeout=30)
            assert r_404.status_code == 404
        finally:
            # RESTORE — cleaner Visible again
            r = requests.put(f"{API}/admin/jobs/{self.JOB_ID}/visibility", headers=admin_h,
                             json={"visible": True}, timeout=30)
            assert r.status_code == 200
            assert r.json()["visible_in_listings"] is True

        # verify restoration
        det2 = self._sector_detail(player_h).json()
        assert self.JOB_ID in {j["id"] for j in det2.get("jobs", [])}, "cleaner not restored"
        restored_count = next((s["job_count"] for s in self._sector_list(player_h).json() if s["id"] == self.SECTOR_ID), None)
        assert restored_count == base_count
