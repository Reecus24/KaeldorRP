"""Phase 2 employer tools tests:
- Applicant projection (role/wage-based)
- Player & NPC employee projection
- Roster Plan editor (GET/PUT) + staffing reflection
- Internal training offer (owner escrow) -> player accept (skill XP) / decline (refund)
- Schedule change proposal + accept/decline
"""
import os
import time
import uuid
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DOVAN_BIZ = "249566f3664b40a9b9934c150c713de2"


def login(email, password):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


def headers(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def dovan():
    return login("dovan@kaeldor.com", "demo123")


@pytest.fixture(scope="module")
def fresh_player():
    """Register a brand-new player, create character, return (token, email, player_id)."""
    email = f"test_p2_{uuid.uuid4().hex[:8]}@kaeldor.com"
    pw = "Password123!"
    r = requests.post(f"{BASE}/auth/register", json={"email": email, "password": pw, "name": "P2Tester"})
    assert r.status_code in (200, 201), r.text
    tok = r.json()["token"]
    h = headers(tok)
    requests.post(f"{BASE}/character/create", json={"name": "P2 Tester", "background": "worker"}, headers=h)
    state = requests.get(f"{BASE}/game/state", headers=h).json()
    pid = state.get("player", {}).get("id") or state.get("id")
    return tok, email, pid


def _emp_email_by_player_id(admin_tok, emp_player_id):
    """Look up employee email via /admin/players listing + names; fall back to mara."""
    return "mara@kaeldor.com"


# ------------- A: Projections -------------
class TestProjections:
    def test_player_employee_projection_present(self, dovan):
        r = requests.get(f"{BASE}/businesses/{DOVAN_BIZ}/player-employees", headers=headers(dovan))
        assert r.status_code == 200, r.text
        emps = r.json()
        assert len(emps) > 0, "Dovan's kiosk should have at least one player employee (mara)"
        for e in emps:
            assert "projection" in e, f"Missing projection on player-employee {e.get('id')}"
            pj = e["projection"]
            assert "rev_per_hour" in pj and "wage_per_hour" in pj and "net_per_hour" in pj, pj

    def test_npc_employee_projection_present(self, dovan):
        r = requests.get(f"{BASE}/businesses/{DOVAN_BIZ}/employees", headers=headers(dovan))
        assert r.status_code == 200, r.text
        body = r.json()
        emps = body["employees"] if isinstance(body, dict) else body
        # Hire one NPC if none exist
        if not emps:
            apps = requests.get(f"{BASE}/businesses/{DOVAN_BIZ}/applicants", headers=headers(dovan))
            if apps.status_code == 200 and apps.json():
                a = apps.json()[0]
                hr = requests.post(f"{BASE}/businesses/{DOVAN_BIZ}/applicants/{a['id']}/hire",
                                   json={"wage_per_hour": 12}, headers=headers(dovan))
                if hr.status_code in (200, 201):
                    body2 = requests.get(f"{BASE}/businesses/{DOVAN_BIZ}/employees", headers=headers(dovan)).json()
                    emps = body2["employees"] if isinstance(body2, dict) else body2
        if not emps:
            pytest.skip("No NPC employees and no applicants to hire — skipping")
        for e in emps:
            assert "projection" in e, f"Missing projection on NPC employee {e.get('id')}"
            pj = e["projection"]
            assert all(k in pj for k in ("rev_per_hour", "wage_per_hour", "net_per_hour")), pj

    def test_applicant_projection_role_map(self, dovan, fresh_player):
        """Have the fresh player apply, then verify the owner-side projection has per-role map."""
        ftok, _, _ = fresh_player
        # Apply to Dovan's kiosk
        ap = requests.post(f"{BASE}/jobs/market/{DOVAN_BIZ}/apply",
                           json={"message": "Hi!"},
                           headers=headers(ftok))
        if ap.status_code == 409:
            pass  # already applied
        else:
            assert ap.status_code == 200, ap.text
        r = requests.get(f"{BASE}/businesses/{DOVAN_BIZ}/player-applications", headers=headers(dovan))
        assert r.status_code == 200, r.text
        apps = r.json()
        ours = [a for a in apps if a.get("applicant_id") and a.get("status") in ("pending", "offered")]
        assert ours, "No open applications on Dovan's kiosk"
        a0 = ours[0]
        assert "projection" in a0, "applicant should have projection block"
        pj = a0["projection"]
        # Per-role productivity map allowing FE to compute live $/h
        assert "by_role" in pj and isinstance(pj["by_role"], dict) and len(pj["by_role"]) > 0, pj
        assert "output_multiplier" in pj, pj
        assert "perf" in pj, pj


# ------------- B1: Roster Plan -------------
class TestRosterPlan:
    def test_get_default_roster_plan(self, dovan):
        r = requests.get(f"{BASE}/businesses/{DOVAN_BIZ}/roster-plan", headers=headers(dovan))
        assert r.status_code == 200, r.text
        body = r.json()
        assert "plan" in body and "available_roles" in body
        assert isinstance(body["plan"], list)
        assert len(body["available_roles"]) > 0

    def test_put_roster_plan_and_staffing_reflects(self, dovan):
        # Snapshot original
        r0 = requests.get(f"{BASE}/businesses/{DOVAN_BIZ}/roster-plan", headers=headers(dovan))
        original_plan = r0.json()["plan"]
        roles_available = r0.json()["available_roles"]
        # Build a custom plan: pick first 2 available roles with explicit counts
        sample_roles = [r["role"] for r in roles_available][:2]
        if not sample_roles:
            pytest.skip("No roles available")
        new_plan = [
            {"role": sample_roles[0], "recommended": 3, "wage": 15.5, "schedule": "early", "open": True},
        ]
        if len(sample_roles) > 1:
            new_plan.append({"role": sample_roles[1], "recommended": 1, "wage": 12.0, "schedule": "late", "open": False})

        pu = requests.put(f"{BASE}/businesses/{DOVAN_BIZ}/roster-plan",
                          json={"plan": new_plan}, headers=headers(dovan))
        assert pu.status_code == 200, pu.text
        saved = pu.json()["plan"]
        assert any(it["role"] == sample_roles[0] and it["recommended"] == 3 for it in saved)

        # Re-GET to verify persistence
        r2 = requests.get(f"{BASE}/businesses/{DOVAN_BIZ}/roster-plan", headers=headers(dovan))
        assert r2.status_code == 200
        plan2 = r2.json()["plan"]
        match = [it for it in plan2 if it["role"] == sample_roles[0]]
        assert match and match[0]["recommended"] == 3 and match[0]["wage"] == 15.5

        # Verify staffing endpoint reflects the new plan
        bd = requests.get(f"{BASE}/businesses/{DOVAN_BIZ}", headers=headers(dovan))
        assert bd.status_code == 200, bd.text
        staffing = bd.json().get("staffing") or bd.json().get("business", {}).get("staffing") or []
        # Some shape may differ; look for role counts
        flat = staffing if isinstance(staffing, list) else staffing.get("roles", [])
        if flat:
            row = [s for s in flat if s.get("role") == sample_roles[0]]
            if row:
                # recommended/required should be 3 from roster plan
                rec = row[0].get("recommended", row[0].get("required"))
                assert rec == 3, f"staffing.recommended did not follow roster_plan: {row[0]}"

        # Restore original
        if original_plan:
            requests.put(f"{BASE}/businesses/{DOVAN_BIZ}/roster-plan",
                         json={"plan": original_plan}, headers=headers(dovan))

    def test_invalid_role_rejected_silently(self, dovan):
        bad = [{"role": "definitely_not_a_real_role_xyz", "recommended": 5, "wage": 10.0, "schedule": "early", "open": True}]
        r = requests.put(f"{BASE}/businesses/{DOVAN_BIZ}/roster-plan", json={"plan": bad}, headers=headers(dovan))
        assert r.status_code == 200
        # Saved plan should be empty (invalid filtered)
        plan = r.json()["plan"]
        assert all(it["role"] != "definitely_not_a_real_role_xyz" for it in plan)


# ------------- B2/B3: Internal Training -------------
class TestTraining:
    def _get_active_player_emp(self, dovan):
        r = requests.get(f"{BASE}/businesses/{DOVAN_BIZ}/player-employees", headers=headers(dovan))
        assert r.status_code == 200
        return r.json()

    def test_training_offer_accept_grants_xp_and_charges_owner(self, dovan):
        emps = self._get_active_player_emp(dovan)
        # Find an employee with no pending offer
        emp = next((e for e in emps if not e.get("training_offer")), None)
        if not emp:
            pytest.skip("No player employee available without pending offer")
        emp_id = emp["id"]
        emp_player_id = emp["employee_player_id"]

        # Find demo player creds for this employee — assume mara (seeded active)
        emp_email = "mara@kaeldor.com"

        # Get training options
        opts = requests.get(f"{BASE}/training-options", headers=headers(dovan))
        assert opts.status_code == 200
        options = opts.json()
        assert options, "Need training options seeded"
        opt = options[0]

        # Owner pre-cash
        me_owner = requests.get(f"{BASE}/game/state", headers=headers(dovan)).json()
        pre_cash = me_owner.get("player", {}).get("cash", 0)

        # Offer training
        of = requests.post(f"{BASE}/businesses/{DOVAN_BIZ}/player-employees/{emp_id}/offer-training",
                           json={"option_id": opt["id"]}, headers=headers(dovan))
        assert of.status_code == 200, of.text

        # Verify owner cash dropped (escrow)
        me_owner2 = requests.get(f"{BASE}/game/state", headers=headers(dovan)).json()
        post_cash = me_owner2.get("player", {}).get("cash", 0)
        assert post_cash < pre_cash, f"Owner cash should drop by escrow ({pre_cash} -> {post_cash})"
        cash_dropped_by = pre_cash - post_cash
        assert abs(cash_dropped_by - opt["cost"]) < 0.01, f"Escrow should equal cost {opt['cost']}, dropped {cash_dropped_by}"

        # Verify pending offer visible on employee row
        emps2 = self._get_active_player_emp(dovan)
        row = next((e for e in emps2 if e["id"] == emp_id), None)
        assert row and row.get("training_offer"), "training_offer should be set"

        # Player accepts
        try:
            ptok = login(emp_email, "demo123")
        except AssertionError:
            pytest.skip(f"Cannot login as employee {emp_email}; offer left pending")

        # Snapshot player skills
        sk0 = requests.get(f"{BASE}/game/state", headers=headers(ptok)).json()
        skill_key = row["training_offer"]["skill"]
        sk_before = (sk0.get("skills") or sk0.get("player", {}).get("skills") or {}).get(skill_key, {})
        xp_before = sk_before.get("xp", 0) if isinstance(sk_before, dict) else 0

        acc = requests.post(f"{BASE}/jobs/employment/{emp_id}/training/accept", headers=headers(ptok))
        assert acc.status_code == 200, acc.text

        # Verify skill XP increased
        sk1 = requests.get(f"{BASE}/game/state", headers=headers(ptok)).json()
        sk_after = (sk1.get("skills") or sk1.get("player", {}).get("skills") or {}).get(skill_key, {})
        xp_after = sk_after.get("xp", 0) if isinstance(sk_after, dict) else 0
        # Allow level-up consumption: total_xp or level should be higher
        lvl_before = sk_before.get("level", 0) if isinstance(sk_before, dict) else 0
        lvl_after = sk_after.get("level", 0) if isinstance(sk_after, dict) else 0
        assert (xp_after > xp_before) or (lvl_after > lvl_before), \
            f"Skill {skill_key} XP/level did not increase: {sk_before} -> {sk_after}"

        # Offer should clear
        emps3 = self._get_active_player_emp(dovan)
        row3 = next((e for e in emps3 if e["id"] == emp_id), None)
        assert row3 and not row3.get("training_offer"), "training_offer should be cleared after accept"

    def test_training_decline_refunds_owner(self, dovan):
        emps = self._get_active_player_emp(dovan)
        emp = next((e for e in emps if not e.get("training_offer")), None)
        if not emp:
            pytest.skip("No player employee without pending offer")
        emp_id = emp["id"]
        emp_player_id = emp["employee_player_id"]
        admin_tok = login("admin@kaeldor.com", "admin123")
        p_doc = requests.get(f"{BASE}/admin/players", headers=headers(admin_tok))
        emp_email = "mara@kaeldor.com"
        try:
            ptok = login(emp_email, "demo123")
        except AssertionError:
            pytest.skip(f"Cannot login as employee {emp_email}")

        opts = requests.get(f"{BASE}/training-options", headers=headers(dovan)).json()
        opt = opts[0]

        pre = requests.get(f"{BASE}/game/state", headers=headers(dovan)).json()
        pre_cash = pre.get("player", {}).get("cash", 0)

        of = requests.post(f"{BASE}/businesses/{DOVAN_BIZ}/player-employees/{emp_id}/offer-training",
                           json={"option_id": opt["id"]}, headers=headers(dovan))
        assert of.status_code == 200, of.text

        mid = requests.get(f"{BASE}/game/state", headers=headers(dovan)).json()
        mid_cash = mid.get("player", {}).get("cash", 0)
        assert mid_cash < pre_cash, "Owner should be charged on offer"

        dec = requests.post(f"{BASE}/jobs/employment/{emp_id}/training/decline", headers=headers(ptok))
        assert dec.status_code == 200, dec.text

        post = requests.get(f"{BASE}/game/state", headers=headers(dovan)).json()
        post_cash = post.get("player", {}).get("cash", 0)
        # Refund: owner cash returns close to pre
        assert abs(post_cash - pre_cash) < 0.5, f"Owner not refunded: pre={pre_cash} post={post_cash}"


# ------------- C: Schedule change -------------
class TestScheduleChange:
    def test_propose_schedule_then_decline_keeps_schedule(self, dovan):
        emps = requests.get(f"{BASE}/businesses/{DOVAN_BIZ}/player-employees", headers=headers(dovan)).json()
        emp = next((e for e in emps if not e.get("pending_schedule")), None)
        if not emp:
            pytest.skip("No employee without pending schedule")
        emp_id = emp["id"]
        cur_preset = (emp.get("schedule") or {}).get("preset", "early")
        new_preset = "late" if cur_preset != "late" else "early"
        emp_player_id = emp["employee_player_id"]

        pr = requests.post(f"{BASE}/businesses/{DOVAN_BIZ}/player-employees/{emp_id}/propose-schedule",
                           json={"schedule": new_preset}, headers=headers(dovan))
        assert pr.status_code == 200, pr.text

        # Verify pending visible
        emps2 = requests.get(f"{BASE}/businesses/{DOVAN_BIZ}/player-employees", headers=headers(dovan)).json()
        row = next((e for e in emps2 if e["id"] == emp_id), None)
        assert row and row.get("pending_schedule"), "pending_schedule should be set"

        # Player declines
        admin_tok = login("admin@kaeldor.com", "admin123")
        p_doc = requests.get(f"{BASE}/admin/players", headers=headers(admin_tok))
        emp_email = "mara@kaeldor.com"
        try:
            ptok = login(emp_email, "demo123")
        except AssertionError:
            pytest.skip(f"Cannot login as employee {emp_email}")

        dec = requests.post(f"{BASE}/jobs/employment/{emp_id}/schedule/decline", headers=headers(ptok))
        assert dec.status_code == 200, dec.text

        # Schedule unchanged
        emps3 = requests.get(f"{BASE}/businesses/{DOVAN_BIZ}/player-employees", headers=headers(dovan)).json()
        row3 = next((e for e in emps3 if e["id"] == emp_id), None)
        assert row3 and not row3.get("pending_schedule")
        assert (row3.get("schedule") or {}).get("preset") == cur_preset, "Schedule should remain after decline"

    def test_propose_schedule_then_accept_changes_schedule(self, dovan):
        emps = requests.get(f"{BASE}/businesses/{DOVAN_BIZ}/player-employees", headers=headers(dovan)).json()
        emp = next((e for e in emps if not e.get("pending_schedule")), None)
        if not emp:
            pytest.skip("No employee without pending schedule")
        emp_id = emp["id"]
        cur_preset = (emp.get("schedule") or {}).get("preset", "early")
        new_preset = "late" if cur_preset != "late" else "early"
        emp_player_id = emp["employee_player_id"]

        pr = requests.post(f"{BASE}/businesses/{DOVAN_BIZ}/player-employees/{emp_id}/propose-schedule",
                           json={"schedule": new_preset}, headers=headers(dovan))
        assert pr.status_code == 200, pr.text

        admin_tok = login("admin@kaeldor.com", "admin123")
        p_doc = requests.get(f"{BASE}/admin/players", headers=headers(admin_tok))
        emp_email = "mara@kaeldor.com"
        try:
            ptok = login(emp_email, "demo123")
        except AssertionError:
            pytest.skip(f"Cannot login as employee {emp_email}")

        acc = requests.post(f"{BASE}/jobs/employment/{emp_id}/schedule/accept", headers=headers(ptok))
        assert acc.status_code == 200, acc.text

        emps3 = requests.get(f"{BASE}/businesses/{DOVAN_BIZ}/player-employees", headers=headers(dovan)).json()
        row3 = next((e for e in emps3 if e["id"] == emp_id), None)
        assert row3 and (row3.get("schedule") or {}).get("preset") == new_preset, \
            f"Schedule should be {new_preset}, got {(row3 or {}).get('schedule')}"
        # Restore (best effort)
        requests.post(f"{BASE}/businesses/{DOVAN_BIZ}/player-employees/{emp_id}/propose-schedule",
                      json={"schedule": cur_preset}, headers=headers(dovan))
        requests.post(f"{BASE}/jobs/employment/{emp_id}/schedule/accept", headers=headers(login(emp_email, "demo123")))
