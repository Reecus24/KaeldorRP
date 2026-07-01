"""Backend tests for Dynamic Social Locations & Encounters (iteration 24)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback for CI where frontend env is not available inside backend
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

SEED_IDS = {"loc_bar", "loc_gym", "loc_work", "loc_streets", "loc_park"}


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kaeldor.com", "admin123")


@pytest.fixture(scope="module")
def mara():
    return _login("mara@kaeldor.com", "demo123")


@pytest.fixture(scope="module")
def kiri():
    return _login("kiri@kaeldor.com", "demo123")


# ---- Admin GET /api/admin/locations ----
class TestAdminLocationsList:
    def test_admin_lists_all_seeded_locations(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/locations", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "locations" in data and "archetypes" in data
        ids = {l["id"] for l in data["locations"]}
        missing = SEED_IDS - ids
        assert not missing, f"missing seeded locations: {missing}"

    def test_encounters_normalized_to_100(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/locations", timeout=10)
        for loc in r.json()["locations"]:
            enc = loc.get("encounters") or []
            if not enc:
                continue
            total = sum(e.get("chance", 0) for e in enc)
            # backend stores chance as fraction 0..1 (frontend multiplies by 100)
            assert abs(total - 1.0) < 0.02, f"{loc['id']} normalized to {total} not ~1.0"

    def test_bar_has_expected_archetype_pills(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/locations", timeout=10)
        bar = next(l for l in r.json()["locations"] if l["id"] == "loc_bar")
        # expected chances per problem statement
        labels = {e["label"]: e["chance"] for e in bar["encounters"]}
        # weights 2,1,1 → 0.50/0.25/0.25 fractions (frontend renders as 50/25/25%)
        vals = sorted(labels.values(), reverse=True)
        assert abs(vals[0] - 0.5) < 0.01 and abs(vals[1] - 0.25) < 0.01 and abs(vals[2] - 0.25) < 0.01, labels


# ---- Player GET /api/social/locations ----
class TestPlayerSocialLocations:
    def test_player_sees_active_locations(self, mara):
        r = mara.get(f"{BASE_URL}/api/social/locations", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        ids = {l["id"] for l in data}
        # All 5 seeded active
        assert SEED_IDS.issubset(ids), f"missing: {SEED_IDS - ids}"

    def test_each_location_exposes_encounters_with_chance(self, mara):
        r = mara.get(f"{BASE_URL}/api/social/locations", timeout=10)
        for loc in r.json():
            assert "encounters" in loc
            assert "available" in loc
            for e in loc["encounters"]:
                assert "archetype_id" in e and "label" in e and "chance" in e

    def test_loc_work_requires_job(self, mara):
        r = mara.get(f"{BASE_URL}/api/social/locations", timeout=10)
        w = next(l for l in r.json() if l["id"] == "loc_work")
        # mara has a job — should be available (or blocked by other reason but not "Requires a job")
        assert w["reason"] != "Requires a job"


# ---- Admin CRUD create → update → delete → verify list ----
class TestAdminLocationCRUD:
    def test_full_crud_flow(self, admin):
        # get an archetype to attach
        listing = admin.get(f"{BASE_URL}/api/admin/locations", timeout=10).json()
        assert listing["archetypes"], "no archetypes available"
        arch = listing["archetypes"][0]
        arch_id = arch.get("id") or arch.get("archetype_id") or arch.get("key")
        assert arch_id, f"cannot find archetype id in {arch}"

        # CREATE
        payload = {
            "name": "TEST_Throwaway_Loc",
            "category": "other",
            "desc": "temp test loc",
            "money_cost": 5,
            "duration_minutes": 30,
            "cooldown_minutes": 10,
            "requires_job": False,
            "active": True,
            "order": 95,
            "npcs": [{"archetype_id": arch_id, "weight": 3}],
        }
        r = admin.post(f"{BASE_URL}/api/admin/locations", json=payload, timeout=10)
        assert r.status_code == 200, r.text
        new_id = r.json()["id"]
        assert isinstance(new_id, str) and len(new_id) > 0

        # VERIFY via GET
        listing2 = admin.get(f"{BASE_URL}/api/admin/locations", timeout=10).json()
        created = next((l for l in listing2["locations"] if l["id"] == new_id), None)
        assert created is not None
        assert created["name"] == "TEST_Throwaway_Loc"
        assert len(created["encounters"]) == 1
        assert created["encounters"][0]["chance"] == 1.0

        # UPDATE: rename + add a second npc (equal weights → 50/50)
        upd = dict(payload)
        upd["name"] = "TEST_Throwaway_Renamed"
        upd["npcs"] = [
            {"archetype_id": arch_id, "weight": 1},
            {"archetype_id": arch_id, "weight": 1},
        ]
        r = admin.put(f"{BASE_URL}/api/admin/locations/{new_id}", json=upd, timeout=10)
        assert r.status_code == 200, r.text

        listing3 = admin.get(f"{BASE_URL}/api/admin/locations", timeout=10).json()
        updated = next(l for l in listing3["locations"] if l["id"] == new_id)
        assert updated["name"] == "TEST_Throwaway_Renamed"
        assert len(updated["encounters"]) == 2
        # each should be 50%
        assert all(abs(e["chance"] - 0.5) < 0.01 for e in updated["encounters"])

        # DELETE
        r = admin.delete(f"{BASE_URL}/api/admin/locations/{new_id}", timeout=10)
        assert r.status_code == 200

        listing4 = admin.get(f"{BASE_URL}/api/admin/locations", timeout=10).json()
        assert new_id not in {l["id"] for l in listing4["locations"]}

    def test_edit_seed_bar_weight_reflects_normalized(self, admin):
        # Read current bar, tweak a weight, verify normalized change, then restore.
        listing = admin.get(f"{BASE_URL}/api/admin/locations", timeout=10).json()
        bar = next(l for l in listing["locations"] if l["id"] == "loc_bar")
        original_npcs = [dict(n) for n in bar.get("npcs", [])]
        assert original_npcs, "loc_bar seed must have npcs"

        # mutate: set first npc weight to 6 (dominant)
        mutated = [dict(n) for n in original_npcs]
        mutated[0]["weight"] = 6
        body = {k: bar.get(k) for k in [
            "name", "category", "desc", "icon", "money_cost", "duration_minutes",
            "cooldown_minutes", "requires_job", "suspicion_gain", "success_base",
            "charisma_factor", "active", "order"
        ]}
        body["npcs"] = mutated
        r = admin.put(f"{BASE_URL}/api/admin/locations/loc_bar", json=body, timeout=10)
        assert r.status_code == 200, r.text

        listing2 = admin.get(f"{BASE_URL}/api/admin/locations", timeout=10).json()
        bar2 = next(l for l in listing2["locations"] if l["id"] == "loc_bar")
        top = max(bar2["encounters"], key=lambda e: e["chance"])
        assert top["chance"] > 0.70, f"expected dominant >70%, got {top}"

        # Restore original
        body["npcs"] = original_npcs
        r = admin.put(f"{BASE_URL}/api/admin/locations/loc_bar", json=body, timeout=10)
        assert r.status_code == 200


# ---- Player visit resolution ----
class TestPlayerVisit:
    def test_mara_visit_park_starts_activity(self, mara):
        state = mara.get(f"{BASE_URL}/api/game/state", timeout=10).json()
        act = state.get("activity") or {}
        if act and act.get("blocking"):
            pytest.skip(f"mara already busy with {act}")
        r = mara.post(f"{BASE_URL}/api/social/visit/loc_park", timeout=10)
        assert r.status_code in (200, 409), r.text
        if r.status_code == 200:
            data = r.json()
            assert data.get("ok") is True
            assert "activity" in data
            act = data["activity"]
            # kind is 'social' and name mentions the visit
            assert act.get("kind") == "social"
            assert "Riverside Park" in act.get("name", "") or "park" in act.get("name", "").lower()
            # verify persistence via state
            st2 = mara.get(f"{BASE_URL}/api/game/state", timeout=10).json()
            assert st2.get("activity", {}).get("kind") == "social"

    def test_visit_unknown_location_404(self, mara):
        r = mara.post(f"{BASE_URL}/api/social/visit/does_not_exist", timeout=10)
        assert r.status_code == 404
