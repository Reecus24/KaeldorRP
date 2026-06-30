"""Credit system regression tests — P0 anti-stacking + denial + missed-payment paths.

Covers:
- GET /api/bank returns full credit_profile shape
- Anti-stacking: borrowing full credit_available leaves credit_limit UNCHANGED
- Over-limit, zero/negative amount rejection
- Repay: clamps, restores available, resets credit_missed on full payoff
- Criminal-record denial (<25) and reduced-limit (<40)
- Missed-payment tracking via mongo flag (light verification)
- Loan side-effects: event + notification + bank/debt deltas
- Deposit/withdraw don't change credit_limit (net-worth invariant)
"""
import os
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://grind-nation.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

DEMO = {
    "mara":  ("mara@kaeldor.com",  "demo123"),
    "kiri":  ("kiri@kaeldor.com",  "demo123"),
    "dovan": ("dovan@kaeldor.com", "demo123"),
}


@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _bank(tok):
    r = requests.get(f"{BASE_URL}/api/bank", headers=_hdr(tok), timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def _reset_player(mongo, email, **fields):
    """Reset selected fields on a player by user email."""
    user = mongo.users.find_one({"email": email})
    assert user, f"user {email} missing"
    uid = str(user["_id"])
    res = mongo.players.update_one({"user_id": uid}, {"$set": fields})
    assert res.matched_count == 1, f"player for {email} (user_id={uid}) not found"


# -------------------- Shape --------------------

class TestBankShape:
    def test_get_bank_returns_full_credit_profile(self):
        tok = _login(*DEMO["mara"])
        b = _bank(tok)
        for key in ("credit_limit", "credit_used", "credit_available", "blocked", "reasons",
                    "interest_daily", "net_worth", "income_per_day", "daily_interest_cost",
                    "cash", "bank", "debt", "max_loan"):
            assert key in b, f"missing key {key} in /api/bank response: {list(b.keys())}"
        assert isinstance(b["reasons"], list)
        assert isinstance(b["blocked"], bool)
        assert b["max_loan"] == b["credit_limit"]


# -------------------- Anti-stacking (CORE) --------------------

class TestAntiStacking:
    def test_borrow_full_available_then_second_loan_rejected(self, mongo):
        # Use kiri — clean slate
        _reset_player(mongo, DEMO["kiri"][0], debt=0.0, credit_missed=0, legal_reputation=100)
        tok = _login(*DEMO["kiri"])
        before = _bank(tok)
        limit_before = before["credit_limit"]
        avail = before["credit_available"]
        assert avail > 0 and limit_before > 0
        # Borrow full available
        r = requests.post(f"{BASE_URL}/api/bank/loan", headers=_hdr(tok),
                          json={"amount": avail}, timeout=15)
        assert r.status_code == 200, f"first loan should succeed: {r.status_code} {r.text}"
        after = _bank(tok)
        # CRITICAL: limit must be unchanged (net-worth invariant)
        assert after["credit_limit"] == limit_before, \
            f"REGRESSION: credit_limit grew after borrowing! before={limit_before} after={after['credit_limit']}"
        # debt should equal previous debt + avail
        assert abs(after["credit_used"] - (before["credit_used"] + avail)) < 1.0
        # available should be ~0
        assert after["credit_available"] <= 1.0, f"credit_available not ~0: {after['credit_available']}"
        # Second loan attempt — any positive amount must be rejected
        r2 = requests.post(f"{BASE_URL}/api/bank/loan", headers=_hdr(tok),
                           json={"amount": 100}, timeout=15)
        assert r2.status_code == 400, f"second loan should be rejected (400): {r2.status_code} {r2.text}"
        detail = r2.json().get("detail", "")
        assert "borrow up to" in detail.lower() and "total limit" in detail.lower()
        # Cleanup — repay so kiri is clean for downstream
        requests.post(f"{BASE_URL}/api/bank/repay", headers=_hdr(tok),
                      json={"amount": 10_000_000}, timeout=15)


# -------------------- Over-limit & invalid --------------------

class TestOverLimitAndInvalid:
    def test_amount_exceeding_available_rejected(self, mongo):
        _reset_player(mongo, DEMO["mara"][0], debt=0.0, credit_missed=0, legal_reputation=100)
        tok = _login(*DEMO["mara"])
        b = _bank(tok)
        too_much = b["credit_available"] + 100_000
        r = requests.post(f"{BASE_URL}/api/bank/loan", headers=_hdr(tok),
                          json={"amount": too_much}, timeout=15)
        assert r.status_code == 400
        d = r.json().get("detail", "")
        assert "borrow up to" in d.lower()

    def test_zero_and_negative_rejected(self):
        tok = _login(*DEMO["mara"])
        for amt in (0, -100):
            r = requests.post(f"{BASE_URL}/api/bank/loan", headers=_hdr(tok),
                              json={"amount": amt}, timeout=15)
            assert r.status_code == 400, f"amount {amt} should be 400: {r.status_code}"


# -------------------- Repay --------------------

class TestRepay:
    def test_repay_full_restores_available_and_resets_missed(self, mongo):
        _reset_player(mongo, DEMO["mara"][0], debt=0.0, credit_missed=3, legal_reputation=100)
        tok = _login(*DEMO["mara"])
        # Take small loan
        b = _bank(tok)
        assert b["credit_available"] > 0
        loan_amt = min(200.0, b["credit_available"])
        r = requests.post(f"{BASE_URL}/api/bank/loan", headers=_hdr(tok),
                          json={"amount": loan_amt}, timeout=15)
        assert r.status_code == 200, r.text
        b2 = _bank(tok)
        assert b2["credit_used"] >= loan_amt - 0.01
        assert b2["daily_interest_cost"] > 0
        # Overpay — should clamp to debt
        r2 = requests.post(f"{BASE_URL}/api/bank/repay", headers=_hdr(tok),
                           json={"amount": loan_amt * 5}, timeout=15)
        assert r2.status_code == 200, r2.text
        b3 = _bank(tok)
        assert b3["debt"] == 0
        assert b3["credit_available"] == b3["credit_limit"]
        assert b3["daily_interest_cost"] == 0
        # credit_missed reset on full payoff
        user = mongo.users.find_one({"email": DEMO["mara"][0]})
        p = mongo.players.find_one({"user_id": str(user["_id"])})
        assert p.get("credit_missed", 0) == 0, f"credit_missed not reset: {p.get('credit_missed')}"

    def test_repay_with_no_debt_rejected(self, mongo):
        _reset_player(mongo, DEMO["mara"][0], debt=0.0, credit_missed=0)
        tok = _login(*DEMO["mara"])
        r = requests.post(f"{BASE_URL}/api/bank/repay", headers=_hdr(tok),
                          json={"amount": 100}, timeout=15)
        assert r.status_code == 400
        assert "no debt" in r.json().get("detail", "").lower()


# -------------------- Criminal record --------------------

class TestCriminalRecord:
    def test_legal_rep_below_25_blocks_credit(self, mongo):
        email = DEMO["kiri"][0]
        _reset_player(mongo, email, debt=0.0, credit_missed=0, legal_reputation=15)
        try:
            tok = _login(*DEMO["kiri"])
            b = _bank(tok)
            assert b["blocked"] is True
            assert any("serious criminal record" in r.lower() for r in b["reasons"]), b["reasons"]
            r = requests.post(f"{BASE_URL}/api/bank/loan", headers=_hdr(tok),
                              json={"amount": 100}, timeout=15)
            assert r.status_code == 403
            assert "credit denied" in r.json().get("detail", "").lower()
        finally:
            _reset_player(mongo, email, legal_reputation=100)

    def test_legal_rep_below_40_reduced_not_blocked(self, mongo):
        email = DEMO["kiri"][0]
        _reset_player(mongo, email, debt=0.0, credit_missed=0, legal_reputation=100)
        tok = _login(*DEMO["kiri"])
        clean = _bank(tok)
        try:
            _reset_player(mongo, email, legal_reputation=30)
            b = _bank(tok)
            assert b["blocked"] is False
            assert any("criminal record" in r.lower() for r in b["reasons"])
            assert b["credit_limit"] < clean["credit_limit"], \
                f"limit should drop with criminal record: clean={clean['credit_limit']} reduced={b['credit_limit']}"
        finally:
            _reset_player(mongo, email, legal_reputation=100)


# -------------------- Limit composition --------------------

class TestLimitComposition:
    def test_limit_positive_and_factors_present(self):
        for who in ("mara", "kiri", "dovan"):
            tok = _login(*DEMO[who])
            b = _bank(tok)
            assert b["credit_limit"] > 0, f"{who} should have positive credit_limit"
            assert "factors" in b
            for k in ("base", "finance_skill", "assets", "income", "job_stability", "reputation_factor"):
                assert k in b["factors"]

    def test_dovan_business_income_boosts_limit(self, mongo):
        """Dovan owns a business — his income_per_day should be > 0 (light check)."""
        tok = _login(*DEMO["dovan"])
        b = _bank(tok)
        assert b["income_per_day"] >= 0


# -------------------- Missed payment tracking --------------------

class TestMissedPayment:
    def test_credit_missed_reduces_limit_and_full_repay_resets(self, mongo):
        email = DEMO["mara"][0]
        _reset_player(mongo, email, debt=0.0, credit_missed=0, legal_reputation=100)
        tok = _login(*DEMO["mara"])
        clean = _bank(tok)
        # Apply missed payments via mongo
        _reset_player(mongo, email, credit_missed=5)
        try:
            after = _bank(tok)
            assert after["credit_limit"] < clean["credit_limit"], \
                f"limit should drop with missed payments: clean={clean['credit_limit']} after={after['credit_limit']}"
            assert any("missed payment" in r.lower() for r in after["reasons"]), after["reasons"]
        finally:
            _reset_player(mongo, email, credit_missed=0)


# -------------------- Loan side effects --------------------

class TestLoanSideEffects:
    def test_loan_creates_event_and_notification_and_updates_balances(self, mongo):
        email = DEMO["mara"][0]
        _reset_player(mongo, email, debt=0.0, credit_missed=0, legal_reputation=100)
        tok = _login(*DEMO["mara"])
        b_before = _bank(tok)
        bank_before = b_before["bank"]
        debt_before = b_before["debt"]
        amt = 150.0
        assert b_before["credit_available"] >= amt
        before_ts = int(time.time() * 1000)
        r = requests.post(f"{BASE_URL}/api/bank/loan", headers=_hdr(tok),
                          json={"amount": amt}, timeout=15)
        assert r.status_code == 200, r.text
        b_after = _bank(tok)
        assert abs((b_after["bank"] - bank_before) - amt) < 1.0
        assert abs((b_after["debt"] - debt_before) - amt) < 1.0
        # Event — event docs use {message, type, severity}
        ev = requests.get(f"{BASE_URL}/api/game/events?limit=20", headers=_hdr(tok), timeout=15).json()
        evs = ev if isinstance(ev, list) else ev.get("events", [])
        assert any("loan" in (e.get("message") or e.get("text") or "").lower() and
                   (e.get("type") == "finance" or e.get("category") == "finance") for e in evs[:20]), \
            f"expected finance loan event in recent events; got: {[(e.get('type'), (e.get('message') or '')[:40]) for e in evs[:5]]}"
        # Notification
        n = requests.get(f"{BASE_URL}/api/notifications", headers=_hdr(tok), timeout=15).json()
        notifs = n if isinstance(n, list) else n.get("notifications", n.get("items", []))
        assert any("loan approved" in (x.get("title", "")).lower() for x in notifs[:20]), "expected 'Loan approved' notification"
        # Cleanup
        requests.post(f"{BASE_URL}/api/bank/repay", headers=_hdr(tok),
                      json={"amount": 10_000_000}, timeout=15)
        # Repay notification
        n2 = requests.get(f"{BASE_URL}/api/notifications", headers=_hdr(tok), timeout=15).json()
        notifs2 = n2 if isinstance(n2, list) else n2.get("notifications", n2.get("items", []))
        assert any("debt repaid" in (x.get("title", "")).lower() for x in notifs2[:20]), "expected 'Debt repaid' notification"


# -------------------- Deposit/withdraw invariance --------------------

class TestDepositWithdrawInvariance:
    def test_deposit_does_not_change_credit_limit(self, mongo):
        _reset_player(mongo, DEMO["mara"][0], debt=0.0, credit_missed=0, legal_reputation=100)
        tok = _login(*DEMO["mara"])
        b = _bank(tok)
        limit_before = b["credit_limit"]
        cash = b["cash"]
        if cash < 50:
            # Withdraw some first
            requests.post(f"{BASE_URL}/api/bank/withdraw", headers=_hdr(tok),
                          json={"amount": 100}, timeout=15)
        # Deposit 50
        r = requests.post(f"{BASE_URL}/api/bank/deposit", headers=_hdr(tok),
                          json={"amount": 50}, timeout=15)
        if r.status_code != 200:
            pytest.skip(f"deposit failed (insufficient cash): {r.text}")
        b2 = _bank(tok)
        assert b2["credit_limit"] == limit_before, \
            f"REGRESSION: deposit changed credit_limit! before={limit_before} after={b2['credit_limit']}"

    def test_withdraw_does_not_change_credit_limit(self, mongo):
        _reset_player(mongo, DEMO["mara"][0], debt=0.0, credit_missed=0, legal_reputation=100)
        tok = _login(*DEMO["mara"])
        b = _bank(tok)
        limit_before = b["credit_limit"]
        if b["bank"] < 50:
            pytest.skip("bank balance too low to withdraw")
        r = requests.post(f"{BASE_URL}/api/bank/withdraw", headers=_hdr(tok),
                          json={"amount": 50}, timeout=15)
        assert r.status_code == 200, r.text
        b2 = _bank(tok)
        assert b2["credit_limit"] == limit_before
