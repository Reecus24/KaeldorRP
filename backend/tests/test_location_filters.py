"""Kaeldor RPG - NPC Filter System tests (iteration_25).
Covers backend filtered-pool behavior and manual-bypass priority on locations.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "admin@kaeldor.com", "password": "admin123"})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_data(admin_client):
    r = admin_client.get(f"{BASE_URL}/api/admin/locations")
    assert r.status_code == 200, r.text
    return r.json()


# ---------- Response shape ----------
class TestAdminLocationsShape:
    def test_tag_options(self, admin_data):
        assert admin_data["tag_options"] == ["Criminal", "Wealthy", "Corporate", "Fitness", "Social", "Drifter"]

    def test_attr_options(self, admin_data):
        assert admin_data["attr_options"] == ["social_status", "legal_standing", "wealth"]

    def test_archetypes_carry_tags_and_attrs(self, admin_data):
        for a in admin_data["archetypes"]:
            assert "tags" in a and isinstance(a["tags"], list)
            for k in ("social_status", "legal_standing", "wealth"):
                assert k in a, f"archetype {a['id']} missing {k}"
                assert 0 <= a[k] <= 100


# ---------- Filter pool: loc_club (Wealthy/Corporate, social_status>=60) ----------
class TestPlatinumLoungeFilterPool:
    def _club(self, admin_data):
        return next(l for l in admin_data["locations"] if l["id"] == "loc_club")

    def test_club_filter_config(self, admin_data):
        club = self._club(admin_data)
        assert club["include_filtered"] is True
        assert set(club["category_whitelist"]) == {"Wealthy", "Corporate"}
        assert club["min_attrs"] == {"social_status": 60}
        assert not club.get("npcs")  # no manual

    def test_club_encounters_only_filter_source(self, admin_data):
        club = self._club(admin_data)
        assert len(club["encounters"]) > 0
        for e in club["encounters"]:
            assert e["source"] == "filter", f"{e['archetype_id']} should be filter"

    def test_club_encounters_match_filter_criteria(self, admin_data):
        club = self._club(admin_data)
        amap = {a["id"]: a for a in admin_data["archetypes"]}
        got_ids = {e["archetype_id"] for e in club["encounters"]}
        # verify each present archetype passes: Wealthy or Corporate AND social_status>=60
        for aid in got_ids:
            a = amap[aid]
            assert set(a["tags"]) & {"Wealthy", "Corporate"}, f"{aid} tags {a['tags']}"
            assert a["social_status"] >= 60, f"{aid} soc_status {a['social_status']}"
        # verify none of the ineligible archetypes leaked in
        ineligible = {a["id"] for a in admin_data["archetypes"]
                      if not (set(a["tags"]) & {"Wealthy", "Corporate"} and a["social_status"] >= 60)}
        assert not (got_ids & ineligible)

    def test_club_expected_five(self, admin_data):
        club = self._club(admin_data)
        got_ids = {e["archetype_id"] for e in club["encounters"]}
        # per review: manager, wholesaler, boss, mentor, business_contact
        assert got_ids == {"manager", "wholesaler", "boss", "mentor", "business_contact"}, got_ids


# ---------- Manual bypass: loc_streets ----------
class TestBackstreetsManualBypass:
    def _streets(self, admin_data):
        return next(l for l in admin_data["locations"] if l["id"] == "loc_streets")

    def test_streets_config(self, admin_data):
        s = self._streets(admin_data)
        assert s["include_filtered"] is True
        assert s["category_whitelist"] == ["Criminal"]
        assert s.get("max_attrs", {}).get("legal_standing") == 40

    def test_manual_bar_regular_bypasses_filter(self, admin_data):
        s = self._streets(admin_data)
        enc = {e["archetype_id"]: e for e in s["encounters"]}
        # bar_regular is Drifter (not Criminal) yet must appear as manual
        assert "bar_regular" in enc, list(enc.keys())
        assert enc["bar_regular"]["source"] == "manual"
        # shady_dealer is also manually assigned in seed
        assert "shady_dealer" in enc
        assert enc["shady_dealer"]["source"] == "manual"


# ---------- CRUD: create filtered → verify pool → delete ----------
class TestCreateFilteredLocation:
    def test_create_filtered_fitness_location(self, admin_client):
        payload = {
            "name": "TEST_Fitness_Filter",
            "category": "gym",
            "desc": "TEST filtered fitness venue",
            "icon": "Dumbbell",
            "money_cost": 0,
            "duration_minutes": 60,
            "cooldown_minutes": 60,
            "active": True,
            "order": 99,
            "npcs": [],
            "include_filtered": True,
            "category_whitelist": ["Fitness"],
            "min_attrs": {},
            "max_attrs": {},
            "filter_weight": 1.0,
        }
        r = admin_client.post(f"{BASE_URL}/api/admin/locations", json=payload)
        assert r.status_code in (200, 201), r.text
        created = r.json()
        new_id = created.get("id") or created.get("location", {}).get("id")
        assert new_id, f"no id in response: {created}"

        try:
            # Verify pool via GET
            g = admin_client.get(f"{BASE_URL}/api/admin/locations")
            assert g.status_code == 200
            data = g.json()
            loc = next((l for l in data["locations"] if l["id"] == new_id), None)
            assert loc, "created location not returned"
            assert loc["include_filtered"] is True
            enc = loc["encounters"]
            assert len(enc) > 0
            got_ids = {e["archetype_id"] for e in enc}
            # Only Fitness-tagged archetypes: gym_coach, athlete
            assert got_ids == {"gym_coach", "athlete"}, got_ids
            for e in enc:
                assert e["source"] == "filter"
        finally:
            d = admin_client.delete(f"{BASE_URL}/api/admin/locations/{new_id}")
            assert d.status_code in (200, 204), d.text


# ---------- Toggle filter tag persists ----------
class TestToggleFilterTagPersists:
    def test_add_fitness_to_club_then_revert(self, admin_client, admin_data):
        club = next(l for l in admin_data["locations"] if l["id"] == "loc_club")
        original = {k: club.get(k) for k in
                    ("name", "category", "desc", "icon", "money_cost", "duration_minutes",
                     "cooldown_minutes", "requires_job", "suspicion_gain", "success_base",
                     "charisma_factor", "active", "order", "npcs",
                     "include_filtered", "category_whitelist", "min_attrs", "max_attrs", "filter_weight")}
        modified = {**original, "category_whitelist": ["Wealthy", "Corporate", "Fitness"]}
        try:
            r = admin_client.put(f"{BASE_URL}/api/admin/locations/loc_club", json=modified)
            assert r.status_code == 200, r.text
            g = admin_client.get(f"{BASE_URL}/api/admin/locations").json()
            club2 = next(l for l in g["locations"] if l["id"] == "loc_club")
            assert set(club2["category_whitelist"]) == {"Wealthy", "Corporate", "Fitness"}
            got = {e["archetype_id"] for e in club2["encounters"]}
            # Fitness archetypes still need social_status>=60 → gym_coach(60) passes, athlete(55) fails
            assert "gym_coach" in got
            assert "athlete" not in got
        finally:
            rv = admin_client.put(f"{BASE_URL}/api/admin/locations/loc_club", json=original)
            assert rv.status_code == 200


# ---------- Player view respects filters ----------
class TestPlayerMeetPeopleFiltered:
    def test_mara_sees_platinum_lounge_with_filtered_pool(self):
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/login",
                   json={"email": "mara@kaeldor.com", "password": "demo123"})
        assert r.status_code == 200
        g = s.get(f"{BASE_URL}/api/social/locations")
        assert g.status_code == 200
        locs = g.json()
        club = next((l for l in locs if l["id"] == "loc_club"), None)
        assert club, "Platinum Lounge missing from player locations"
        assert len(club["encounters"]) >= 5
        for e in club["encounters"]:
            assert e["source"] == "filter"
