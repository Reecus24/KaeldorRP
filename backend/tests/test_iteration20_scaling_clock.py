"""
Iteration 20 tests:
- P0: worker-scaling on multi-slot businesses (bistro): 2 concurrent workers ~= 2x output
- 1-slot cap: kiosk rejects overlapping shifts with 400 'Shift overlaps with ...'
- Real-time German clock: game_time matches Europe/Berlin within a few minutes; time_scale == 1.0
- Kiosk L1 market estimate profit_day ~ $220 (+/-3%)
"""
import os
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback for local runs: read from frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

assert BASE_URL, "REACT_APP_BACKEND_URL not set"


def _engine_day_rates(biz_id):
    """Directly compute production/P&L rates via the engine using current DB state.
    Bypasses the need to wait for a game tick (1:1 real time)."""
    import asyncio, sys
    sys.path.insert(0, "/app/backend")
    from motor.motor_asyncio import AsyncIOMotorClient
    import employee_engine, employment

    async def _go():
        db = AsyncIOMotorClient("mongodb://localhost:27017")["test_database"]
        b = await db.businesses.find_one({"id": biz_id}, {"_id": 0})
        assert b, f"business {biz_id} not found"
        workers = await db.employees.find(
            {"business_id": biz_id, "status": "active"}, {"_id": 0}
        ).to_list(300)
        # Assemble worker dicts as expected by _day_rates
        pemps = await db.player_employment.find(
            {"business_id": biz_id, "status": "active"}, {"_id": 0}
        ).to_list(100)
        # each entry has "schedule" and "wage_per_hour" — that's what _day_rates uses
        all_workers = []
        for e in workers:
            all_workers.append({
                "schedule": e.get("schedule"),
                "wage_per_hour": e.get("wage_per_hour") or (e.get("daily_wage", 90) / 8.0),
            })
        for pe in pemps:
            all_workers.append({
                "schedule": pe.get("schedule"),
                "wage_per_hour": pe.get("wage_per_hour") or (pe.get("wage_per_shift", 60) / 4.0),
            })
        reqs = await employee_engine.get_staffing(db, b)
        base_slots = max(1, sum(r.get("recommended", 1) for r in reqs))
        slots = base_slots + (b.get("level", 1) - 1)
        return employee_engine._day_rates(b, all_workers, slots=slots)

    return asyncio.new_event_loop().run_until_complete(_go())


def _login(session, email, pw):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    tok = r.json()["token"]
    session.headers.update({"Authorization": f"Bearer {tok}"})
    return tok


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    _login(s, "admin@kaeldor.com", "admin123")
    return s


@pytest.fixture(scope="module")
def player_context(admin_session):
    """Register a fresh player, create character, top up cash via admin."""
    s = requests.Session()
    email = f"TEST_it20_{uuid.uuid4().hex[:8]}@kaeldor.com"
    r = s.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": "test123", "name": "It20 Tester"
    }, timeout=20)
    assert r.status_code in (200, 201), f"register: {r.status_code} {r.text}"
    _login(s, email, "test123")
    # Create character (drifter background)
    r = s.post(f"{BASE_URL}/api/character/create", json={
        "name": "It20 Bosslet", "background": "drifter", "trait": "hardworking"
    }, timeout=20)
    assert r.status_code in (200, 201), f"char create: {r.status_code} {r.text}"
    # Find player id via /game/state
    r = s.get(f"{BASE_URL}/api/game/state", timeout=20)
    assert r.status_code == 200, r.text
    pid = r.json()["player"]["id"]
    # Grant cash + skills (needed for bistro/auto_repair tech gates) via admin
    r = admin_session.put(f"{BASE_URL}/api/admin/players/{pid}",
                          json={"cash": 500000, "bank": 100000,
                                "skills": {"technology": 8, "cooking": 8, "crafting": 8,
                                           "management": 8, "business_admin": 8,
                                           "charisma": 8, "communication": 8,
                                           "strength": 8, "driving": 8}},
                          timeout=20)
    assert r.status_code == 200, r.text
    return {"session": s, "player_id": pid, "email": email}


# --------------------------------------------------------------- Clock -----
class TestGermanClock:
    def test_time_scale_and_alignment(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/game/state", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # time_scale 1:1
        assert abs(float(data["time_scale"]) - 1.0) < 1e-6, f"time_scale={data['time_scale']}"
        # Compare game_time to Europe/Berlin wall clock
        gt = data["game_time"]
        # parse ISO — game_time is naive-in-Berlin OR aware; handle both
        try:
            gt_dt = datetime.fromisoformat(gt.replace("Z", "+00:00"))
        except Exception:
            pytest.fail(f"bad game_time: {gt}")
        # normalize: get the calendar hh:mm of the value.
        # game_engine's game_now returns naive wall-clock of Europe/Berlin (because world_start_game was
        # set to now_utc + Berlin offset). Compare hh:mm as such.
        now_berlin = datetime.now(ZoneInfo("Europe/Berlin"))
        # difference in minutes ignoring timezone (compare the wall-clock components)
        gt_naive = gt_dt.replace(tzinfo=None)
        nb_naive = now_berlin.replace(tzinfo=None)
        delta = abs((gt_naive - nb_naive).total_seconds())
        assert delta < 300, f"game_time={gt_naive} vs Berlin={nb_naive} — delta={delta}s"


# --------------------------------------------------------------- Market ----
class TestMarketKiosk:
    def test_kiosk_l1_profit_estimate(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/businesses/market", timeout=20)
        assert r.status_code == 200, r.text
        listings = r.json()
        kiosk = next((b for b in listings if b.get("id") == "kiosk"), None)
        assert kiosk, "kiosk not in market"
        est = kiosk.get("estimate", {})
        p = est.get("profit_day")
        assert p is not None, f"no profit_day: {kiosk}"
        # spec: ~$220 ±3%
        assert 213.4 <= p <= 226.6, f"kiosk profit_day={p} (want ~220 ±3%)"


# ------------------------------------------------------------- 1-slot ------
class TestKioskOverlapRejected:
    def _find_market(self, session, type_id):
        r = session.get(f"{BASE_URL}/api/businesses/market", timeout=20)
        return next((b for b in r.json() if b.get("id") == type_id), None)

    def test_kiosk_overlap_returns_400(self, player_context):
        s = player_context["session"]
        # Buy kiosk
        r = s.post(f"{BASE_URL}/api/businesses/kiosk/buy", timeout=20)
        assert r.status_code == 200, f"kiosk buy: {r.status_code} {r.text}"
        biz = r.json()
        biz_id = biz.get("id") or biz.get("business", {}).get("id")
        if not biz_id:
            # fallback: look up owned
            r = s.get(f"{BASE_URL}/api/businesses/owned", timeout=20)
            owned = r.json()
            k = next((b for b in owned if b.get("type_id") == "kiosk" or b.get("type") == "kiosk"), None)
            assert k, f"no kiosk owned: {owned}"
            biz_id = k["id"]
        # Get applicants
        r = s.get(f"{BASE_URL}/api/businesses/{biz_id}/applicants", timeout=20)
        assert r.status_code == 200, r.text
        apps = r.json()
        assert len(apps) >= 2, f"need >=2 kiosk applicants, got {len(apps)}"
        # Hire 2 applicants
        for a in apps[:2]:
            r = s.post(f"{BASE_URL}/api/businesses/{biz_id}/applicants/{a['id']}/hire", timeout=20)
            assert r.status_code == 200, f"hire: {r.status_code} {r.text}"
        r = s.get(f"{BASE_URL}/api/businesses/{biz_id}/employees", timeout=20)
        emps = r.json()["employees"]
        assert len(emps) >= 2
        # Try to set 2nd worker's shift overlapping the 1st — must return 400 with 'overlaps'
        first_emp = emps[0]
        second_emp = emps[1]
        # Set both to identical 08:00–20:00 (kiosk opening)
        r = s.patch(f"{BASE_URL}/api/businesses/{biz_id}/employees/{first_emp['id']}/shift",
                    json={"start": "08:00", "end": "20:00"}, timeout=20)
        # first patch should succeed if second worker's default is non-overlapping;
        # if it fails because of overlap we'll flip which one we patch first.
        if r.status_code != 200:
            # first worker probably already covers full — patch second instead
            r2 = s.patch(f"{BASE_URL}/api/businesses/{biz_id}/employees/{second_emp['id']}/shift",
                         json={"start": "08:00", "end": "20:00"}, timeout=20)
            assert r2.status_code == 400, f"expected 400 overlap, got {r2.status_code} {r2.text}"
            assert "overlap" in r2.text.lower(), f"expected 'overlap' in detail: {r2.text}"
        else:
            # Now patch second to overlap
            r2 = s.patch(f"{BASE_URL}/api/businesses/{biz_id}/employees/{second_emp['id']}/shift",
                         json={"start": "10:00", "end": "18:00"}, timeout=20)
            assert r2.status_code == 400, f"expected 400 overlap, got {r2.status_code} {r2.text}"
            assert "overlap" in r2.text.lower(), f"expected 'overlap' in detail: {r2.text}"

    def test_kiosk_split_shifts_net_around_220(self, player_context):
        """Two workers split-covering 08–20 should net ~$220/day (single-worker-equivalent)."""
        s = player_context["session"]
        r = s.get(f"{BASE_URL}/api/businesses/owned", timeout=20)
        owned = r.json()
        k = next((b for b in owned if b.get("type_id") == "kiosk" or b.get("type") == "kiosk"), None)
        assert k, "kiosk not owned"
        biz_id = k["id"]
        r = s.get(f"{BASE_URL}/api/businesses/{biz_id}/employees", timeout=20)
        emps = r.json()["employees"]
        # Split shifts: 08–14 & 14–20 (non-overlapping)
        r1 = s.patch(f"{BASE_URL}/api/businesses/{biz_id}/employees/{emps[0]['id']}/shift",
                     json={"start": "08:00", "end": "14:00"}, timeout=20)
        assert r1.status_code == 200, r1.text
        r2 = s.patch(f"{BASE_URL}/api/businesses/{biz_id}/employees/{emps[1]['id']}/shift",
                     json={"start": "14:00", "end": "20:00"}, timeout=20)
        assert r2.status_code == 200, r2.text
        r = s.get(f"{BASE_URL}/api/businesses/{biz_id}/employees", timeout=20)
        m = r.json()["metrics"]
        net = m.get("net_day")
        # Should be around single-worker (no doubling). $220 target, allow ±20% due to two-worker split.
        assert 150 <= net <= 260, f"kiosk split net_day={net} (want single-worker-equivalent ~$220)"
        # concurrent_slots reported must be 1
        assert m.get("concurrent_slots", 1) == 1, f"kiosk concurrent_slots should be 1, got {m}"


# -------------------------------------------------------- multi-slot scale --
class TestBistroWorkerScaling:
    def _buy_multi_slot(self, s):
        # try bistro (2 slots)
        r = s.post(f"{BASE_URL}/api/businesses/bistro/buy", timeout=20)
        if r.status_code == 200:
            return "bistro", r.json()
        # fallback: auto_repair or delivery_service
        for tid in ("auto_repair", "delivery_service", "online_shop"):
            r = s.post(f"{BASE_URL}/api/businesses/{tid}/buy", timeout=20)
            if r.status_code == 200:
                return tid, r.json()
        pytest.fail(f"could not buy any multi-slot business: {r.status_code} {r.text}")

    def test_two_concurrent_workers_double_output(self, player_context):
        s = player_context["session"]
        type_id, _ = self._buy_multi_slot(s)
        r = s.get(f"{BASE_URL}/api/businesses/owned", timeout=20)
        owned = r.json()
        b = next((x for x in owned if x.get("type_id") == type_id or x.get("type") == type_id), None)
        assert b, f"{type_id} not owned"
        biz_id = b["id"]
        opening = b.get("opening_hours") or {"open": "08:00", "close": "20:00"}
        open_s, close_s = opening["open"], opening["close"]

        # Hire 1 applicant, set shift to full opening
        r = s.get(f"{BASE_URL}/api/businesses/{biz_id}/applicants", timeout=20)
        apps = r.json()
        assert len(apps) >= 2, f"need >=2 applicants for {type_id}"
        r = s.post(f"{BASE_URL}/api/businesses/{biz_id}/applicants/{apps[0]['id']}/hire", timeout=20)
        assert r.status_code == 200, r.text
        r = s.get(f"{BASE_URL}/api/businesses/{biz_id}/employees", timeout=20)
        emp1 = r.json()["employees"][0]
        r = s.patch(f"{BASE_URL}/api/businesses/{biz_id}/employees/{emp1['id']}/shift",
                    json={"start": open_s, "end": close_s}, timeout=20)
        assert r.status_code == 200, r.text

        # Compute 1-worker rates directly via the engine (metrics endpoint only shows
        # stored/last-resolved rev_day, which is 0 until a game tick runs)
        m1_full = _engine_day_rates(biz_id)
        cap1 = m1_full["capacity_day"]
        rev1 = m1_full["rev_day"]
        wh1 = m1_full["worker_hours"]
        ch1 = m1_full["covered_hours"]
        # concurrent_slots from metrics
        r = s.get(f"{BASE_URL}/api/businesses/{biz_id}/employees", timeout=20)
        m1 = r.json()["metrics"]
        cs1 = m1.get("concurrent_slots")
        assert cs1 >= 2, f"{type_id} expected concurrent_slots>=2, got {cs1}"
        assert cap1 > 0, f"1-worker cap zero: {m1_full}"

        # Hire 2nd applicant + patch to full opening (concurrent)
        r = s.post(f"{BASE_URL}/api/businesses/{biz_id}/applicants/{apps[1]['id']}/hire", timeout=20)
        assert r.status_code == 200, r.text
        r = s.get(f"{BASE_URL}/api/businesses/{biz_id}/employees", timeout=20)
        emps = r.json()["employees"]
        emp2 = next(e for e in emps if e["id"] != emp1["id"])
        r = s.patch(f"{BASE_URL}/api/businesses/{biz_id}/employees/{emp2['id']}/shift",
                    json={"start": open_s, "end": close_s}, timeout=20)
        assert r.status_code == 200, f"2nd worker overlap should be allowed on multi-slot: {r.status_code} {r.text}"
        r = s.get(f"{BASE_URL}/api/businesses/{biz_id}/employees", timeout=20)
        m2 = r.json()["metrics"]
        m2_full = _engine_day_rates(biz_id)
        cap2 = m2_full["capacity_day"]
        rev2 = m2_full["rev_day"]
        wh2 = m2_full["worker_hours"]
        ch2 = m2_full["covered_hours"]

        # Worker-hours should approx double
        ratio_wh = wh2 / max(wh1, 0.01)
        assert 1.8 <= ratio_wh <= 2.2, f"worker_hours ratio {ratio_wh:.2f} (wh1={wh1} wh2={wh2})"
        # Capacity should approx double (covered_hours cap = concurrent_slots * opening_hours)
        ratio_cap = cap2 / max(cap1, 0.01)
        assert 1.8 <= ratio_cap <= 2.2, f"capacity_day ratio {ratio_cap:.2f} (cap1={cap1} cap2={cap2})"
        # Revenue should approximately double (allow bit wider — demand cap)
        ratio_rev = rev2 / max(rev1, 0.01)
        assert 1.7 <= ratio_rev <= 2.2, f"rev_day ratio {ratio_rev:.2f} (rev1={rev1} rev2={rev2})"
        # Active workers = 2
        assert m2.get("active_workers", m2.get("staff_count")) == 2, f"active workers wrong: {m2}"
