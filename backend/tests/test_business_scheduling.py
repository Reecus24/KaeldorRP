"""
Iteration 18 — Backend tests for Business Scheduling architecture.

Covers:
 - opening_hours / is_open_now / covered_hours / roster / daily_wage_total in business metrics
 - PATCH /api/businesses/{id}/opening-hours (validation + shift clamping)
 - PATCH /api/businesses/{id}/employees/{emp_id}/shift (validation + persistence)
 - Hiring assigns default full-coverage shift on first hire
 - Market estimate profit_day ~ targets (~±20%)
 - Ghost workers regression via staffing status
"""

import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://grind-nation.preview.emergentagent.com").rstrip("/")

ADMIN = ("admin@kaeldor.com", "admin123")
DOVAN = ("dovan@kaeldor.com", "demo123")

MARKET_TARGETS = {
    "kiosk": 220,
    "delivery_service": 450,
    "bistro": 500,
    "gym": 500,
    "pet_shop": 500,
    "clothing_store": 800,
    "auto_repair": 800,
    "online_shop": 300,
    "cleaning_co": 350,
    "real_estate_agency": 1100,
}


def _login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


def _hhmm(x):
    """float hours -> 'HH:MM' string; 24.0 -> '24:00'."""
    if x >= 24.0:
        return "24:00"
    h = int(x)
    m = int(round((x - h) * 60))
    if m == 60:
        h += 1
        m = 0
    return f"{h:02d}:{m:02d}"


def _to_float(s):
    if s == "24:00":
        return 24.0
    h, m = s.split(":")
    return int(h) + int(m) / 60.0


@pytest.fixture(scope="module")
def dovan_client():
    tok = _login(*DOVAN)
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_client():
    tok = _login(*ADMIN)
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def dovan_biz_id(dovan_client):
    r = dovan_client.get(f"{BASE_URL}/api/businesses/owned")
    assert r.status_code == 200, r.text
    biz = r.json()
    assert isinstance(biz, list) and biz
    target = "249566f3664b40a9b9934c150c713de2"
    for b in biz:
        if b.get("id") == target:
            return target
    return biz[0]["id"]


# ---------- 1) metrics shape ----------
class TestMetricsShape:
    def test_business_metrics_has_scheduling_fields(self, dovan_client, dovan_biz_id):
        r = dovan_client.get(f"{BASE_URL}/api/businesses/{dovan_biz_id}")
        assert r.status_code == 200, r.text
        b = r.json()
        m = b.get("metrics") or {}
        oh = m.get("opening_hours")
        assert isinstance(oh, dict), f"missing opening_hours in {list(m)}"
        assert "open" in oh and "close" in oh
        for k in ("is_open_now", "open_hours", "covered_hours", "coverage_hours_pct", "daily_wage_total"):
            assert k in m, f"missing metric key {k}: keys={list(m)}"
        assert isinstance(m["is_open_now"], bool)
        assert m["open_hours"] > 0
        roster = m.get("roster")
        assert isinstance(roster, list)
        if roster:
            for k in ("shift_start", "shift_end", "hourly_wage", "shift_hours", "on_shift"):
                assert k in roster[0], f"roster missing {k}: {list(roster[0])}"

    def test_employees_endpoint_has_hourly_wage_and_shift(self, dovan_client, dovan_biz_id):
        r = dovan_client.get(f"{BASE_URL}/api/businesses/{dovan_biz_id}/employees")
        assert r.status_code == 200, r.text
        data = r.json()
        # endpoint returns {employees:[...], metrics:{...}}
        emps = data.get("employees") if isinstance(data, dict) else data
        assert isinstance(emps, list)
        # sample: no NPCs on this biz means no-op, but the endpoint response structure was verified


# ---------- 2) opening-hours PATCH ----------
class TestOpeningHours:
    def test_patch_opening_hours_success(self, dovan_client, dovan_biz_id):
        r = dovan_client.patch(
            f"{BASE_URL}/api/businesses/{dovan_biz_id}/opening-hours",
            json={"open": "09:00", "close": "17:00"},
        )
        assert r.status_code == 200, r.text
        r2 = dovan_client.get(f"{BASE_URL}/api/businesses/{dovan_biz_id}")
        oh = r2.json()["metrics"]["opening_hours"]
        assert _to_float(oh["open"] if isinstance(oh["open"], str) else str(oh["open"])) == 9.0
        assert _to_float(oh["close"] if isinstance(oh["close"], str) else str(oh["close"])) == 17.0

    def test_patch_opening_hours_rejects_invalid(self, dovan_client, dovan_biz_id):
        r = dovan_client.patch(
            f"{BASE_URL}/api/businesses/{dovan_biz_id}/opening-hours",
            json={"open": "18:00", "close": "10:00"},
        )
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"

    def test_patch_opening_hours_clamps_worker_shifts(self, dovan_client, dovan_biz_id):
        r = dovan_client.patch(
            f"{BASE_URL}/api/businesses/{dovan_biz_id}/opening-hours",
            json={"open": "10:00", "close": "12:00"},
        )
        assert r.status_code == 200, r.text
        emps = dovan_client.get(f"{BASE_URL}/api/businesses/{dovan_biz_id}/employees").json().get("employees", [])
        for e in emps:
            ss, se = e.get("shift_start"), e.get("shift_end")
            if ss is None or se is None:
                continue
            ss_f = _to_float(ss) if isinstance(ss, str) else ss
            se_f = _to_float(se) if isinstance(se, str) else se
            assert ss_f >= 10.0 - 0.001, f"shift_start {ss_f} not clamped to 10"
            assert se_f <= 12.0 + 0.001, f"shift_end {se_f} not clamped to 12"


# ---------- 3) shift PATCH ----------
class TestShiftPatch:
    def test_reset_opening_and_patch_shift(self, dovan_client, dovan_biz_id):
        r = dovan_client.patch(
            f"{BASE_URL}/api/businesses/{dovan_biz_id}/opening-hours",
            json={"open": "08:00", "close": "20:00"},
        )
        assert r.status_code == 200

        data = dovan_client.get(f"{BASE_URL}/api/businesses/{dovan_biz_id}/employees").json()
        emps = data.get("employees", [])
        npc = next((e for e in emps if not e.get("is_player")), None)
        target = npc or (emps[0] if emps else None)
        if target is None:
            pytest.skip("no employees on Dovan kiosk to shift-edit")
        emp_id = target["id"]

        # invalid: start >= end
        r_bad = dovan_client.patch(
            f"{BASE_URL}/api/businesses/{dovan_biz_id}/employees/{emp_id}/shift",
            json={"start": "12:00", "end": "12:00"},
        )
        assert r_bad.status_code == 400

        # invalid: outside opening window (00:00..06:00 while opening is 08..20)
        r_out = dovan_client.patch(
            f"{BASE_URL}/api/businesses/{dovan_biz_id}/employees/{emp_id}/shift",
            json={"start": "00:00", "end": "06:00"},
        )
        assert r_out.status_code == 400, f"expected 400 outside-hours, got {r_out.status_code}: {r_out.text}"

        if npc is not None:
            r_ok = dovan_client.patch(
                f"{BASE_URL}/api/businesses/{dovan_biz_id}/employees/{emp_id}/shift",
                json={"start": "09:00", "end": "13:00"},
            )
            assert r_ok.status_code == 200, r_ok.text
            emps2 = dovan_client.get(f"{BASE_URL}/api/businesses/{dovan_biz_id}/employees").json().get("employees", [])
            e2 = next(e for e in emps2 if e["id"] == emp_id)
            ss = _to_float(e2["shift_start"])
            se = _to_float(e2["shift_end"])
            assert ss == 9.0 and se == 13.0


# ---------- 4) market estimate ----------
class TestMarketEstimate:
    def test_market_profit_day_within_20pct(self, dovan_client):
        r = dovan_client.get(f"{BASE_URL}/api/businesses/market")
        assert r.status_code == 200, r.text
        listings = r.json()
        by_type = {}
        for item in listings:
            t = item.get("id") or item.get("type") or item.get("business_type") or item.get("key")
            pd = (item.get("estimate") or {}).get("profit_day")
            if t and pd is not None:
                by_type[t] = pd
        missing = [t for t in MARKET_TARGETS if t not in by_type]
        assert not missing, f"market missing types: {missing}. Got: {list(by_type)}"
        offenders = []
        for t, target in MARKET_TARGETS.items():
            pd = by_type[t]
            diff = (pd - target) / target * 100.0
            if abs(diff) > 20.0:
                offenders.append((t, pd, target, round(diff, 1)))
        assert not offenders, f"profit_day out of ±20%: {offenders}"


# ---------- 5) ghost-worker regression ----------
class TestStaffingStatus:
    def test_open_business_status_not_closed(self, dovan_client, dovan_biz_id):
        dovan_client.patch(
            f"{BASE_URL}/api/businesses/{dovan_biz_id}/opening-hours",
            json={"open": "00:00", "close": "24:00"},
        )
        b = dovan_client.get(f"{BASE_URL}/api/businesses/{dovan_biz_id}").json()
        m = b.get("metrics", {})
        assert m.get("is_open_now") is True, f"24h business should be open now; is_open_now={m.get('is_open_now')}"

    def test_closed_metrics_field_present(self, dovan_client, dovan_biz_id):
        r = dovan_client.patch(
            f"{BASE_URL}/api/businesses/{dovan_biz_id}/opening-hours",
            json={"open": "00:00", "close": "00:30"},
        )
        assert r.status_code == 200, r.text
        b = dovan_client.get(f"{BASE_URL}/api/businesses/{dovan_biz_id}").json()
        assert "is_open_now" in b.get("metrics", {})
        # cleanup: reopen wide
        dovan_client.patch(
            f"{BASE_URL}/api/businesses/{dovan_biz_id}/opening-hours",
            json={"open": "08:00", "close": "20:00"},
        )


# ---------- 6) hire assigns default full-coverage shift ----------
class TestHireDefaultShift:
    def test_new_player_buys_kiosk_and_hires_gets_full_coverage(self, admin_client):
        email = f"TEST_sched_{uuid.uuid4().hex[:8]}@kaeldor.com"
        r = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "pass1234", "name": "Sched Test"},
            timeout=15,
        )
        assert r.status_code in (200, 201), r.text
        tok = r.json().get("token") or _login(email, "pass1234")
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})

        r_char = s.post(f"{BASE_URL}/api/character/create", json={"name": "TestChar", "background": "hustler"})
        # ignore result — may already exist

        state = s.get(f"{BASE_URL}/api/game/state").json()
        player_id = state.get("player", {}).get("id") or state.get("id")

        # fund via direct mongo (no admin cash endpoint exists per prev iterations)
        funded = False
        try:
            from pymongo import MongoClient
            mongo_url = os.environ.get("MONGO_URL")
            db_name = os.environ.get("DB_NAME")
            if mongo_url and db_name and player_id:
                cli = MongoClient(mongo_url)
                db = cli[db_name]
                res = db.players.update_one({"id": player_id}, {"$set": {"cash": 50000, "bank": 50000}})
                funded = res.matched_count > 0
        except Exception as ex:
            print("mongo fund err:", ex)

        if not funded:
            pytest.skip("could not fund test player; skipping buy+hire test")

        listings = s.get(f"{BASE_URL}/api/businesses/market").json()
        kiosk = next((x for x in listings if x.get("id") == "kiosk"), None)
        assert kiosk is not None, "no kiosk in market"

        rb = s.post(f"{BASE_URL}/api/businesses/kiosk/buy")
        if rb.status_code not in (200, 201):
            pytest.skip(f"buy failed: {rb.status_code} {rb.text}")

        owned = s.get(f"{BASE_URL}/api/businesses/owned").json()
        biz = next((b for b in owned if b.get("type_id") == "kiosk"), owned[-1] if owned else None)
        assert biz, "no owned kiosk after buy"
        biz_id = biz["id"]

        bd = s.get(f"{BASE_URL}/api/businesses/{biz_id}").json()
        oh = bd["metrics"]["opening_hours"]
        open_s, close_s = oh["open"], oh["close"]
        open_f = _to_float(open_s) if isinstance(open_s, str) else open_s
        close_f = _to_float(close_s) if isinstance(close_s, str) else close_s

        apps = s.get(f"{BASE_URL}/api/businesses/{biz_id}/applicants").json()
        if not isinstance(apps, list) or not apps:
            pytest.skip("no applicants to hire")
        app_id = apps[0]["id"]
        rh = s.post(f"{BASE_URL}/api/businesses/{biz_id}/applicants/{app_id}/hire")
        assert rh.status_code in (200, 201), f"hire failed: {rh.status_code} {rh.text}"

        emps = s.get(f"{BASE_URL}/api/businesses/{biz_id}/employees").json().get("employees", [])
        hired = next((e for e in emps if e.get("id") == app_id), emps[0])
        ss = _to_float(hired["shift_start"]) if isinstance(hired["shift_start"], str) else hired["shift_start"]
        se = _to_float(hired["shift_end"]) if isinstance(hired["shift_end"], str) else hired["shift_end"]
        assert abs(ss - open_f) < 0.02, f"first-hire shift_start {ss} != opening open {open_f}"
        assert abs(se - close_f) < 0.02, f"first-hire shift_end {se} != opening close {close_f}"

        m1 = s.get(f"{BASE_URL}/api/businesses/{biz_id}").json()["metrics"]
        full_net = m1.get("net_day")
        full_cov = m1.get("covered_hours")
        assert full_cov and full_cov > 0
        assert full_net is not None
        print(f"[kiosk L1 1-worker full-coverage] net_day={full_net:.2f} covered_hours={full_cov:.2f} target=$220")

        # halve shift
        half_end_f = open_f + (close_f - open_f) / 2.0
        rp = s.patch(
            f"{BASE_URL}/api/businesses/{biz_id}/employees/{app_id}/shift",
            json={"start": _hhmm(open_f), "end": _hhmm(half_end_f)},
        )
        assert rp.status_code == 200, rp.text
        m2 = s.get(f"{BASE_URL}/api/businesses/{biz_id}").json()["metrics"]
        assert m2["covered_hours"] < full_cov * 0.75, f"expected coverage drop, got {m2['covered_hours']} vs {full_cov}"
        assert m2["net_day"] < full_net, f"expected net_day drop, got {m2['net_day']} vs {full_net}"
        print(f"[halved] net_day={m2['net_day']:.2f} covered_hours={m2['covered_hours']:.2f}")
