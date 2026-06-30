"""
Kaeldor RPG - Social Contacts & Relationships system regression tests.

Covers:
  - lazy contact seeding on /api/game/state
  - GET /api/social/contacts list + summary
  - GET /api/social/contacts/{cid} detail (view + history + actions + opps + warnings)
  - Instant interactions (small_talk, call_text) + 409 cooldown
  - Gift flow (flowers OK, missing gift_id => 400, money charge)
  - Activity interactions (hang_out) -> blocking current_activity + 409 if busy
  - Action gating (ask_reference, ask_loan, invite_date, meet_shady applies_to)
  - Discovery actions list + start
  - Block / unblock toggle + interactions blocked while blocked
  - Integration hooks: rent housing -> landlord contact
  - Admin CRUD for 5 new content types
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


# --------------------- helpers ---------------------
def _sess(token=None):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s


def _login(email, password):
    s = _sess()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    token = r.json()["token"]
    s.headers["Authorization"] = f"Bearer {token}"
    return s


def _ensure_free(s):
    """Cancel any in-progress activity for player so we can start new ones."""
    st = s.get(f"{API}/game/state").json()
    if st.get("activity") or (st.get("player") or {}).get("current_activity"):
        s.post(f"{API}/game/cancel-activity")


def _money(s):
    """Return (cash, bank) tuple from game state."""
    st = s.get(f"{API}/game/state").json()
    p = st.get("player", st)
    return float(p.get("cash", 0)), float(p.get("bank", 0))


def _clear_cd(s, action_id, contact_id):
    """Use a simple stuff: don't bypass cooldowns; expect tests to use a different contact."""
    pass


# --------------------- fixtures ---------------------
@pytest.fixture(scope="module")
def player():
    s = _login("player@kaeldor.com", "player123")
    # Touch state to ensure contacts seeded lazily
    r = s.get(f"{API}/game/state")
    assert r.status_code == 200
    return s


@pytest.fixture(scope="module")
def fresh_player():
    """Fresh player so we can test integration hooks without leftover state."""
    email = f"socialtest_{uuid.uuid4().hex[:10]}@example.com"
    s = _sess()
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "pass1234", "name": "Sosh"})
    assert r.status_code == 200
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    r2 = s.post(f"{API}/character/create", json={"name": "SoshTest", "background": "graduate"})
    assert r2.status_code == 200
    # Pull state to seed social
    s.get(f"{API}/game/state")
    return s


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kaeldor.com", "admin123")


@pytest.fixture(scope="module")
def contacts(player):
    r = player.get(f"{API}/social/contacts")
    assert r.status_code == 200
    return r.json()


# --------------------- contacts list + seeding ---------------------
class TestContactsListAndSeed:
    def test_player_contacts_listed(self, contacts):
        assert "contacts" in contacts and "summary" in contacts
        cs = contacts["contacts"]
        # Seed creates ~6+ baseline contacts (friends/family/mentor/love/shady)
        assert len(cs) >= 5, f"expected seeded contacts, got {len(cs)}"
        # Required fields on each contact view
        required = {"id", "name", "relationship_type", "category", "relationship_score",
                    "trust", "respect", "attraction", "mood", "traits", "status",
                    "last_interaction_seconds"}
        sample = cs[0]
        missing = required - set(sample.keys())
        assert not missing, f"missing fields on contact view: {missing}"
        # Score range checks
        for c in cs:
            assert -100 <= c["relationship_score"] <= 100

    def test_summary_shape(self, contacts):
        s = contacts["summary"]
        for k in ("total", "close", "romantic", "angry", "avg_score"):
            assert k in s, f"summary missing {k}"
        assert s["total"] == len(contacts["contacts"])

    def test_relationship_types_diverse(self, contacts):
        types = {c["relationship_type"] for c in contacts["contacts"]}
        # Expected baseline relationship_types
        # (we tolerate variety but expect at least friend + family OR mentor present)
        assert types & {"friend", "family", "mentor", "partner", "shady_contact"}, \
            f"baseline relationship types missing, got {types}"


# --------------------- contact detail ---------------------
class TestContactDetail:
    def test_detail_endpoint(self, player, contacts):
        cid = contacts["contacts"][0]["id"]
        r = player.get(f"{API}/social/contacts/{cid}")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("contact", "history", "actions", "opportunities", "warnings"):
            assert k in d
        # actions should be a list with availability info
        assert isinstance(d["actions"], list) and len(d["actions"]) > 0
        sample = d["actions"][0]
        for k in ("id", "label", "available"):
            assert k in sample

    def test_detail_unknown_404(self, player):
        r = player.get(f"{API}/social/contacts/does-not-exist")
        assert r.status_code == 404


# --------------------- instant interactions ---------------------
def _find_contact(contacts, relationship_types):
    """Return first contact view whose relationship_type is in given set, or None."""
    for c in contacts["contacts"]:
        if c["relationship_type"] in relationship_types:
            return c
    return None


def _any_active_contact(contacts):
    for c in contacts["contacts"]:
        if c.get("status") != "blocked":
            return c
    return contacts["contacts"][0]


class TestInstantInteractions:
    def test_small_talk_success_then_cooldown(self, player, contacts):
        c = _any_active_contact(contacts)
        r = player.post(f"{API}/social/contacts/{c['id']}/interact", json={"action_id": "small_talk"})
        # If it was already on cooldown from a prior run, accept 409 and skip
        if r.status_code == 409:
            pytest.skip("small_talk already on cooldown; cannot retest immediately")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        # Immediate replay must be cooled down
        r2 = player.post(f"{API}/social/contacts/{c['id']}/interact", json={"action_id": "small_talk"})
        assert r2.status_code == 409, f"expected 409 cooldown, got {r2.status_code} {r2.text}"

    def test_call_text_success(self, player, contacts):
        c = _any_active_contact(contacts)
        r = player.post(f"{API}/social/contacts/{c['id']}/interact", json={"action_id": "call_text"})
        if r.status_code == 409:
            pytest.skip("call_text on cooldown from prior run")
        assert r.status_code == 200, r.text


class TestGiftFlow:
    def test_gift_without_id_returns_400_or_409(self, player, contacts):
        """Note: server checks cooldown before missing-gift validation. Either is acceptable
        as a refusal — but if cooldown is fresh, we should get 400.
        """
        c = _any_active_contact(contacts)
        r = player.post(f"{API}/social/contacts/{c['id']}/interact", json={"action_id": "give_gift"})
        assert r.status_code in (400, 409), f"expected 400 missing gift_id, got {r.status_code} {r.text}"
        # Important: surface this validation-order quirk; report when 409 occurs first
        if r.status_code == 409:
            pytest.skip("cooldown precedes gift_id validation in current handler (logged)")

    def test_gift_flowers_success_and_charges(self, player, contacts):
        c = _any_active_contact(contacts)
        cash0, bank0 = _money(player)
        if cash0 + bank0 < 30:
            pytest.skip(f"insufficient funds ({cash0+bank0}) to test gift")
        r = player.post(f"{API}/social/contacts/{c['id']}/interact",
                        json={"action_id": "give_gift", "gift_id": "flowers"})
        if r.status_code == 409:
            pytest.skip("give_gift cooldown active")
        assert r.status_code == 200, r.text
        cash1, bank1 = _money(player)
        delta = (cash0 + bank0) - (cash1 + bank1)
        assert delta >= 24, f"expected ~25 charge for flowers, was {delta}"

    def test_gift_unknown_returns_404(self, player, contacts):
        c = _any_active_contact(contacts)
        r = player.post(f"{API}/social/contacts/{c['id']}/interact",
                        json={"action_id": "give_gift", "gift_id": "does_not_exist"})
        # Could be 404 (unknown gift) or 409 if on cooldown
        assert r.status_code in (404, 409), r.text


# --------------------- activity interactions ---------------------
class TestActivityInteractions:
    def test_hang_out_starts_activity_then_409_if_busy(self, player, contacts):
        _ensure_free(player)
        # Re-fetch to get latest status (other tests may have blocked contacts)
        latest = player.get(f"{API}/social/contacts").json()["contacts"]
        eligible = [c for c in latest
                    if c.get("status") != "blocked"
                    and c["relationship_type"] in {"friend", "family", "mentor", "partner", "coworker"}]
        if not eligible:
            pytest.skip("no eligible non-blocked contact for hang_out")
        c = eligible[0]
        r = player.post(f"{API}/social/contacts/{c['id']}/interact", json={"action_id": "hang_out"})
        if r.status_code == 409:
            # try the next eligible contact
            for c2 in eligible[1:]:
                _ensure_free(player)
                r = player.post(f"{API}/social/contacts/{c2['id']}/interact",
                                json={"action_id": "hang_out"})
                if r.status_code == 200:
                    c = c2
                    break
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("started") is True
        assert body.get("activity") is not None

        # Now try to start another activity -> should 409 (busy)
        for c3 in eligible:
            if c3["id"] != c["id"]:
                r2 = player.post(f"{API}/social/contacts/{c3['id']}/interact",
                                 json={"action_id": "hang_out"})
                assert r2.status_code == 409, f"expected busy 409, got {r2.status_code} {r2.text}"
                break

        # Cleanup: cancel activity so next tests can use the slot
        player.post(f"{API}/game/cancel-activity")


# --------------------- action gating ---------------------
class TestActionGating:
    def test_invite_date_only_on_partner(self, player, contacts):
        # Find a non-partner contact (e.g., family) and try invite_date
        c = _find_contact(contacts, {"family", "friend", "mentor"})
        if not c:
            pytest.skip("no non-partner contact found")
        r = player.post(f"{API}/social/contacts/{c['id']}/interact", json={"action_id": "invite_date"})
        # Should be 400 (not applicable / gating) - NOT 409 (cooldown) or 200
        assert r.status_code == 400, f"expected 400 gating refusal, got {r.status_code} {r.text}"

    def test_meet_shady_only_on_shady_contact(self, player, contacts):
        c = _find_contact(contacts, {"family", "friend", "mentor"})
        if not c:
            pytest.skip("no non-shady contact found")
        r = player.post(f"{API}/social/contacts/{c['id']}/interact", json={"action_id": "meet_shady"})
        assert r.status_code == 400, r.text

    def test_ask_reference_excluded_from_friend_actions(self, player, contacts):
        # actions list on a friend contact should NOT include ask_reference
        c = _find_contact(contacts, {"friend", "family"})
        if not c:
            pytest.skip("no friend/family contact")
        d = player.get(f"{API}/social/contacts/{c['id']}").json()
        action_ids = {a["id"] for a in d["actions"]}
        assert "ask_reference" not in action_ids, \
            f"ask_reference should be hidden on {c['relationship_type']}, got {action_ids}"


# --------------------- discovery actions ---------------------
class TestDiscovery:
    def test_discover_list(self, player):
        r = player.get(f"{API}/social/discover-actions")
        assert r.status_code == 200
        items = r.json()
        ids = {a["id"] for a in items}
        assert {"network_business", "meet_new_people"} <= ids, f"missing discovery actions: {ids}"
        for a in items:
            assert "available" in a

    def test_discover_start_activity(self, player):
        _ensure_free(player)
        cash, bank = _money(player)
        if cash + bank < 25:
            pytest.skip("insufficient funds for discovery action")
        r = player.post(f"{API}/social/discover/meet_new_people")
        if r.status_code == 409:
            pytest.skip("meet_new_people on cooldown")
        assert r.status_code == 200, r.text
        assert r.json().get("activity")
        # cleanup
        player.post(f"{API}/game/cancel-activity")


# --------------------- block / unblock ---------------------
class TestBlockUnblock:
    def test_block_then_interactions_rejected_then_unblock(self, player, contacts):
        c = _any_active_contact(contacts)
        # Block
        r = player.post(f"{API}/social/contacts/{c['id']}/block")
        assert r.status_code == 200
        assert r.json()["status"] == "blocked"

        # Try to interact while blocked -> 400 (validate_action rejects)
        r2 = player.post(f"{API}/social/contacts/{c['id']}/interact",
                         json={"action_id": "small_talk"})
        assert r2.status_code == 400, f"expected 400 when blocked, got {r2.status_code} {r2.text}"

        # Unblock
        r3 = player.post(f"{API}/social/contacts/{c['id']}/block")
        assert r3.status_code == 200
        assert r3.json()["status"] != "blocked"


# --------------------- integration hook: housing -> landlord ---------------------
class TestHousingIntegration:
    def test_rent_creates_landlord(self, fresh_player):
        # Find current housing on fresh player
        s = fresh_player
        listings = s.get(f"{API}/housing").json()
        # try to find a listing different from current that the graduate can afford
        all_list = listings.get("listings", [])
        current_id = (listings.get("current") or {}).get("id")
        cash, bank = _money(s)
        budget = cash + bank
        target = None
        for h in all_list:
            if h["id"] == current_id:
                continue
            rent_up = h.get("deposit", 0)
            if rent_up <= budget:
                target = h
                break
        if not target:
            pytest.skip("no affordable alt housing to rent for landlord test")
        r = s.post(f"{API}/housing/{target['id']}/rent")
        if r.status_code != 200:
            pytest.skip(f"rent failed for landlord test: {r.status_code} {r.text}")
        # Now contacts should include a landlord
        cs = s.get(f"{API}/social/contacts").json()["contacts"]
        landlords = [c for c in cs if c["relationship_type"] == "landlord"]
        assert landlords, "renting did not create a landlord contact"


# --------------------- admin CRUD for new content types ---------------------
NEW_CTYPES = ["npc_archetypes", "social_traits", "relationship_actions", "gift_types", "social_events"]


class TestAdminCRUD:
    @pytest.mark.parametrize("ctype", NEW_CTYPES)
    def test_admin_list(self, admin, ctype):
        r = admin.get(f"{API}/admin/content/{ctype}")
        assert r.status_code == 200, f"{ctype}: {r.status_code} {r.text}"
        items = r.json()
        assert isinstance(items, list)
        assert len(items) > 0, f"{ctype} list is empty"

    def test_admin_create_update_delete_gift(self, admin):
        # Use gift_types as the round-trip CRUD verification
        gid = f"TEST_gift_{uuid.uuid4().hex[:6]}"
        payload = {
            "id": gid, "label": "TEST Gift", "cost": 12, "icon": "Gift",
            "on_give": {"relationship_score": 1}, "desc": "test"
        }
        r = admin.post(f"{API}/admin/content/gift_types", json=payload)
        assert r.status_code == 200, r.text
        # verify in list
        items = admin.get(f"{API}/admin/content/gift_types").json()
        ids = [i["id"] for i in items]
        assert gid in ids

        # update (POST should upsert; try put if available, else re-post)
        payload["cost"] = 22
        r2 = admin.put(f"{API}/admin/content/gift_types/{gid}", json=payload)
        if r2.status_code == 404 or r2.status_code == 405:
            r2 = admin.post(f"{API}/admin/content/gift_types", json=payload)
        assert r2.status_code == 200, r2.text

        # delete
        r3 = admin.delete(f"{API}/admin/content/gift_types/{gid}")
        assert r3.status_code in (200, 204), r3.text
        items2 = admin.get(f"{API}/admin/content/gift_types").json()
        assert gid not in [i["id"] for i in items2], "gift was not deleted"
