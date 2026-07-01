"""
Test verification for Mark Pilots +$15,000 grant.
- Verify Mark Pilots (player id 5fce7bc0-6f8c-42e2-b0ea-0b8d4e3cc5a4) has ~$15,090 cash.
- Verify credit persists after two DB reads (resolver stability).
- Verify demo accounts (mara, dovan) do NOT retain the erroneous +$15k credit.
- Regression smoke: GET /api/game/state returns 200 for mara/dovan.
"""
import os
import asyncio
import time
import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load backend .env
load_dotenv("/app/backend/.env")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

# Load frontend .env for backend URL
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

MARK_PLAYER_ID = "5fce7bc0-6f8c-42e2-b0ea-0b8d4e3cc5a4"
MARK_EMAIL = "patrick.kuppe02@web.de"


# ---------- Mongo verification for Mark Pilots ----------

def _mongo_read_player(player_id):
    async def _run():
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        doc = await db["players"].find_one({"id": player_id})
        if not doc:
            # try _id fallback
            doc = await db["players"].find_one({"_id": player_id})
        client.close()
        return doc
    return asyncio.get_event_loop().run_until_complete(_run()) if not asyncio.get_event_loop().is_running() else asyncio.run(_run())


def test_mark_pilots_has_15k_credit():
    """Mark Pilots should have cash roughly ~$15,090 (allow drift for scheduled bills)."""
    doc = asyncio.run(_read_player(MARK_PLAYER_ID))
    assert doc is not None, f"Player {MARK_PLAYER_ID} not found in players collection"
    print(f"Mark Pilots doc keys: {list(doc.keys())}")
    cash = doc.get("cash")
    assert cash is not None, "Player has no 'cash' field"
    print(f"Mark Pilots cash = {cash}")
    # The credit +$15,000 must be present. Original balance was ~$90.94, so cash should still
    # be materially above that (well over $1,000) even after some scheduled bill/rent/debt drain.
    assert cash > 1000, f"Expected credit still present (cash > $1,000), got {cash}"
    assert cash <= 20000, f"Cash too high, unexpected: {cash}"


def test_mark_pilots_cash_stable_across_reads():
    """Reading Mark Pilots twice should keep cash stable (no unexpected resolver wipe)."""
    doc1 = asyncio.run(_read_player(MARK_PLAYER_ID))
    time.sleep(2)
    doc2 = asyncio.run(_read_player(MARK_PLAYER_ID))
    assert doc1 and doc2, "Missing Mark Pilots doc on repeat read"
    cash1, cash2 = doc1["cash"], doc2["cash"]
    print(f"Cash read1={cash1}, read2={cash2}")
    # Should not have changed dramatically between two static DB reads (no state API call in between)
    assert abs(cash1 - cash2) < 1.0, f"Cash unexpectedly changed between reads: {cash1} -> {cash2}"
    assert cash2 > 1000, f"Cash below expected credit threshold on 2nd read: {cash2}"


async def _read_player(player_id):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    doc = await db["players"].find_one({"id": player_id})
    if not doc:
        doc = await db["players"].find_one({"_id": player_id})
    client.close()
    return doc


# ---------- API verification for demo accounts ----------

def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    return r


def _get_state(token):
    return requests.get(
        f"{BASE_URL}/api/game/state",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )


@pytest.mark.parametrize("email,password,expected_max_cash,label", [
    ("mara@kaeldor.com", "demo123", 5000, "mara ~ $1,492 expected"),
    ("dovan@kaeldor.com", "demo123", 5000, "dovan ~ $0 expected"),
])
def test_demo_accounts_do_not_hold_15k(email, password, expected_max_cash, label):
    """Demo accounts should NOT retain the erroneous +$15k credit."""
    login = _login(email, password)
    assert login.status_code == 200, f"Login failed for {email}: {login.status_code} {login.text}"
    token = login.json().get("access_token") or login.json().get("token")
    assert token, f"No token returned for {email}: {login.json()}"

    state = _get_state(token)
    assert state.status_code == 200, f"GET /api/game/state failed for {email}: {state.status_code} {state.text[:500]}"
    data = state.json()
    # cash may be in player object
    player = data.get("player") or data
    cash = player.get("cash")
    assert cash is not None, f"No cash field in state for {email}: {list(player.keys())}"
    print(f"{label}: {email} cash = {cash}")
    assert cash < expected_max_cash, f"{email} still holds inflated cash: {cash} (should be < {expected_max_cash})"


def test_regression_smoke_mara_state_coherent():
    login = _login("mara@kaeldor.com", "demo123")
    assert login.status_code == 200
    token = login.json().get("access_token") or login.json().get("token")
    state = _get_state(token)
    assert state.status_code == 200
    data = state.json()
    player = data.get("player") or data
    # coherent player object
    assert isinstance(player, dict) and len(player) > 3
    assert "cash" in player


def test_regression_smoke_dovan_state_coherent():
    login = _login("dovan@kaeldor.com", "demo123")
    assert login.status_code == 200
    token = login.json().get("access_token") or login.json().get("token")
    state = _get_state(token)
    assert state.status_code == 200
    data = state.json()
    player = data.get("player") or data
    assert isinstance(player, dict) and len(player) > 3
    assert "cash" in player
