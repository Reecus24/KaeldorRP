"""Tests for the /business-market ACQUIRE PREVIEW P0 bug fix (iteration 15).

Verifies:
  1. GET /api/businesses/market returns 10 types, each with a finite numeric 'estimate' object.
  2. profit_day == round(revenue_day - material_day - wage_day, 2) for every type.
  3. Buy endpoint either succeeds (returns owned biz with recipe/materials/products, bankrupt=False)
     or returns proper 400 'cannot afford' — never crashes.
  4. Regression: Dovan owned kiosk P&L still coherent (Net = Rev - Materials - Wages, whole-dollar).
  5. Data check: Mark Pilots player still holds cash while demo accounts do not carry the erroneous +$15k.
"""

import math
import os
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0].strip()
BASE_URL = BASE_URL.rstrip("/")

DEMO = [("kiri@kaeldor.com", "demo123"),
        ("dovan@kaeldor.com", "demo123"),
        ("mara@kaeldor.com", "demo123")]


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, f"no token in {r.json()}"
    return tok


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------- Market estimate ----------
@pytest.fixture(scope="module")
def kiri_token():
    return _login("kiri@kaeldor.com", "demo123")


def test_market_returns_10_types_with_estimate(kiri_token):
    r = requests.get(f"{BASE_URL}/api/businesses/market", headers=_hdr(kiri_token), timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list) and len(data) == 10, f"expected 10 types, got {len(data)}"
    for t in data:
        assert "estimate" in t, f"{t.get('id')} missing 'estimate'"
        est = t["estimate"]
        for k in ("revenue_day", "material_day", "wage_day", "profit_day",
                  "margin_per_unit", "sold_day", "material_cost_per_unit"):
            v = est.get(k)
            assert v is not None, f"{t['id']}.estimate.{k} is None"
            assert isinstance(v, (int, float)), f"{t['id']}.estimate.{k} not numeric: {v!r}"
            assert math.isfinite(v), f"{t['id']}.estimate.{k} not finite: {v}"


def test_market_profit_identity(kiri_token):
    """profit_day must equal round(revenue - material - wage, 2) for every type."""
    r = requests.get(f"{BASE_URL}/api/businesses/market", headers=_hdr(kiri_token), timeout=30)
    assert r.status_code == 200
    for t in r.json():
        e = t["estimate"]
        expected = round(e["revenue_day"] - e["material_day"] - e["wage_day"], 2)
        assert e["profit_day"] == expected, (
            f"{t['id']} profit_day={e['profit_day']} but rev-mat-wage={expected} "
            f"(rev={e['revenue_day']} mat={e['material_day']} wage={e['wage_day']})"
        )


def test_market_product_and_recipe_present(kiri_token):
    """Estimate.product must have name+price; margin_per_unit finite."""
    r = requests.get(f"{BASE_URL}/api/businesses/market", headers=_hdr(kiri_token), timeout=30)
    for t in r.json():
        e = t["estimate"]
        prod = e.get("product") or {}
        assert prod.get("name"), f"{t['id']} product.name empty: {prod}"
        assert isinstance(prod.get("price"), (int, float)) and prod["price"] > 0, f"{t['id']} product.price invalid: {prod}"


# ---------- Buy endpoint ----------
def test_buy_endpoint_ok_or_cannot_afford(kiri_token):
    """Buy the cheapest business Kiri qualifies for — either owns it, or gets a clean 400."""
    mkt = requests.get(f"{BASE_URL}/api/businesses/market", headers=_hdr(kiri_token), timeout=30).json()
    qualified = [t for t in mkt if t.get("qualified")]
    assert qualified, "kiri qualifies for no business type"
    # Cheapest qualified
    target = min(qualified, key=lambda x: x.get("purchase_price", 1e9))
    r = requests.post(f"{BASE_URL}/api/businesses/{target['id']}/buy", headers=_hdr(kiri_token), timeout=30)
    assert r.status_code in (200, 400, 402), f"unexpected {r.status_code}: {r.text}"
    if r.status_code == 200:
        # Confirm owned business has recipe/materials/products and not instantly bankrupt
        owned = requests.get(f"{BASE_URL}/api/businesses/owned", headers=_hdr(kiri_token), timeout=30).json()
        assert owned, "no owned businesses after buy"
        b = next((x for x in owned if x.get("type_id") == target["id"] or x.get("business_type_id") == target["id"]), owned[-1])
        assert b.get("bankrupt") in (False, None), f"instantly bankrupt: {b}"
        # Recipe/materials/products should be initialised
        assert b.get("recipe") is not None or b.get("materials") is not None or b.get("products") is not None, \
            f"owned biz missing supply-chain fields: {list(b.keys())}"
    else:
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"detail": r.text}
        detail = (body.get("detail") or body.get("message") or "").lower()
        assert any(k in detail for k in ("afford", "cash", "money", "insufficient")), \
            f"expected 'cannot afford' style error, got {body}"


# ---------- Regression: Dovan owned kiosk P&L ----------
@pytest.fixture(scope="module")
def dovan_token():
    return _login("dovan@kaeldor.com", "demo123")


def test_dovan_owned_business_pnl_coherent(dovan_token):
    owned = requests.get(f"{BASE_URL}/api/businesses/owned", headers=_hdr(dovan_token), timeout=30).json()
    assert owned, "dovan has no owned businesses"
    for b in owned:
        # Real supply-chain fields live directly on the biz doc (rev_day/material_day/wages_day/net_day)
        rev = b.get("rev_day")
        mat = b.get("material_day")
        wag = b.get("wages_day")
        net = b.get("net_day")
        for name, v in [("rev_day", rev), ("material_day", mat), ("wages_day", wag), ("net_day", net)]:
            assert v is not None, f"biz {b.get('id')} missing {name}"
            assert isinstance(v, (int, float)) and math.isfinite(v), f"biz {b.get('id')} {name} not finite: {v}"
        expected = round(rev - mat - wag, 2)
        # Net/day tile must equal Revenue − Materials − Wages exactly (whole-dollar tolerance)
        assert abs(net - expected) <= 1.0, (
            f"Net/day ({net}) != Rev-Mat-Wage ({expected}) for biz {b.get('id')} "
            f"(rev={rev} mat={mat} wag={wag})"
        )


# ---------- Data check: Mark Pilots credit / demo accounts clean ----------
def test_mongo_data_check():
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "test_database")]
    mark = db.players.find_one({"id": "5fce7bc0-6f8c-42e2-b0ea-0b8d4e3cc5a4"}, {"_id": 0, "cash": 1, "name": 1})
    assert mark is not None, "Mark Pilots player not found"
    # Cash should be materially larger than tiny demo balances
    assert (mark.get("cash") or 0) > 500, f"Mark Pilots cash suspiciously low: {mark}"
    # Demo accounts must not carry the +$15k
    for email in ("mara@kaeldor.com", "dovan@kaeldor.com", "kiri@kaeldor.com"):
        u = db.users.find_one({"email": email}, {"_id": 0, "id": 1})
        if not u:
            continue
        p = db.players.find_one({"user_id": u["id"]}, {"_id": 0, "cash": 1, "name": 1})
        if not p:
            continue
        assert (p.get("cash") or 0) < 5000, f"demo {email} unexpectedly holds >=5k: {p}"
    client.close()
