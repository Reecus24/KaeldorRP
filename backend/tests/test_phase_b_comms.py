"""Phase B — Communication backend tests.

Covers:
  - Presence (/players/online, /players/directory)
  - World Chat (send, mask, anti-spam 429, GET shape)
  - Admin moderation (list, soft delete, mute, unmute)
  - Player Messaging (device gate, threads, unread, reply threading, notifications)
  - Block toggle (sender 403)

Auth: JWT in Authorization header. Demo players (mara/dovan/kiri) seeded on startup.
"""
import os
import time
import pytest
import requests

from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("admin@kaeldor.com", "admin123")
MARA = ("mara@kaeldor.com", "demo123")
DOVAN = ("dovan@kaeldor.com", "demo123")
KIRI = ("kiri@kaeldor.com", "demo123")

CHAT_COOLDOWN = 5  # seconds (server default 4) — buffer


# ---------- helpers ----------
def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _me_player_id(tok):
    r = requests.get(f"{API}/game/state", headers=_h(tok), timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["player"]["id"]


@pytest.fixture(scope="module")
def tokens():
    out = {
        "admin": _login(*ADMIN),
        "mara": _login(*MARA),
        "dovan": _login(*DOVAN),
        "kiri": _login(*KIRI),
    }
    return out


@pytest.fixture(scope="module")
def pids(tokens):
    return {
        "mara": _me_player_id(tokens["mara"]),
        "dovan": _me_player_id(tokens["dovan"]),
        "kiri": _me_player_id(tokens["kiri"]),
    }


# ---------- presence ----------
class TestPresence:
    def test_online_endpoint_shape(self, tokens):
        # Touch /game/state for mara so last_seen is recent
        requests.get(f"{API}/game/state", headers=_h(tokens["mara"]), timeout=15)
        r = requests.get(f"{API}/players/online", headers=_h(tokens["mara"]), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "online" in d and "count" in d
        assert isinstance(d["online"], list)
        assert isinstance(d["count"], int)
        # mara just hit /game/state in fixture so should be online
        names = [p["name"] for p in d["online"]]
        assert any("Mara" in n for n in names), f"Mara not in online list: {names}"

    def test_directory_excludes_self_and_has_online_flag(self, tokens, pids):
        r = requests.get(f"{API}/players/directory", headers=_h(tokens["mara"]), timeout=15)
        assert r.status_code == 200
        lst = r.json()
        assert isinstance(lst, list)
        ids = [p["id"] for p in lst]
        assert pids["mara"] not in ids, "directory must exclude self"
        for p in lst:
            assert "online" in p and isinstance(p["online"], bool)
            assert "name" in p and "id" in p


# ---------- world chat ----------
class TestWorldChat:
    def test_chat_get_shape(self, tokens):
        r = requests.get(f"{API}/chat/world", headers=_h(tokens["mara"]), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "messages" in d and "online_count" in d
        assert isinstance(d["messages"], list)

    def test_chat_send_masks_profanity_and_cooldown(self, tokens):
        # Wait clear of any previous cooldown
        time.sleep(CHAT_COOLDOWN)
        text = "this is shit and fine"
        r = requests.post(f"{API}/chat/world", headers=_h(tokens["dovan"]),
                          json={"message": text}, timeout=15)
        assert r.status_code == 200, r.text
        msg = r.json()["message"]
        assert "shit" not in msg["message"].lower(), f"profanity not masked: {msg['message']}"
        assert "****" in msg["message"]

        # immediate second post => 429
        r2 = requests.post(f"{API}/chat/world", headers=_h(tokens["dovan"]),
                           json={"message": "again"}, timeout=15)
        assert r2.status_code == 429, f"expected 429 got {r2.status_code}: {r2.text}"


# ---------- admin moderation ----------
class TestAdminChat:
    def test_admin_list_delete_and_hidden(self, tokens):
        # mara posts a message we'll delete
        time.sleep(CHAT_COOLDOWN)
        text = "TEST_delete_marker_xyz"
        r = requests.post(f"{API}/chat/world", headers=_h(tokens["mara"]),
                          json={"message": text}, timeout=15)
        assert r.status_code == 200, r.text
        mid = r.json()["message"]["id"]

        # admin list includes it
        r = requests.get(f"{API}/admin/chat", headers=_h(tokens["admin"]), timeout=15)
        assert r.status_code == 200
        ids = [m["id"] for m in r.json()]
        assert mid in ids

        # delete
        r = requests.delete(f"{API}/admin/chat/{mid}", headers=_h(tokens["admin"]), timeout=15)
        assert r.status_code == 200

        # /chat/world no longer shows it
        r = requests.get(f"{API}/chat/world?limit=200", headers=_h(tokens["mara"]), timeout=15)
        assert r.status_code == 200
        public_ids = [m["id"] for m in r.json()["messages"]]
        assert mid not in public_ids, "soft-deleted message must not appear in /chat/world"

    def test_mute_blocks_post_and_unmute_restores(self, tokens, pids):
        # mute kiri
        r = requests.post(f"{API}/admin/chat/mute", headers=_h(tokens["admin"]),
                          json={"player_id": pids["kiri"], "minutes": 5}, timeout=15)
        assert r.status_code == 200, r.text

        time.sleep(CHAT_COOLDOWN)
        r = requests.post(f"{API}/chat/world", headers=_h(tokens["kiri"]),
                          json={"message": "hello"}, timeout=15)
        assert r.status_code == 403, f"muted kiri should be 403, got {r.status_code}: {r.text}"

        # unmute
        r = requests.post(f"{API}/admin/chat/unmute", headers=_h(tokens["admin"]),
                          json={"player_id": pids["kiri"]}, timeout=15)
        assert r.status_code == 200

        time.sleep(CHAT_COOLDOWN)
        r = requests.post(f"{API}/chat/world", headers=_h(tokens["kiri"]),
                          json={"message": "unmuted ok"}, timeout=15)
        assert r.status_code == 200, f"after unmute expected 200 got {r.status_code}: {r.text}"


# ---------- messaging ----------
class TestMessaging:
    def test_device_gate_kiri_email_forbidden(self, tokens, pids):
        # kiri has no laptop => email must 403
        r = requests.post(f"{API}/messages/send", headers=_h(tokens["kiri"]), json={
            "to_player_id": pids["dovan"], "channel": "email",
            "subject": "hi", "body": "test"
        }, timeout=15)
        assert r.status_code == 403, f"kiri email expected 403 got {r.status_code}: {r.text}"

    def test_device_gate_kiri_sms_ok(self, tokens, pids):
        r = requests.post(f"{API}/messages/send", headers=_h(tokens["kiri"]), json={
            "to_player_id": pids["dovan"], "channel": "sms", "body": "hello via sms"
        }, timeout=15)
        assert r.status_code == 200, r.text

    def test_unblock_if_blocked(self, tokens, pids):
        # ensure dovan has NOT blocked mara at start of message flow
        # /messages/block toggles; we GET the player record indirectly by trying a send
        r = requests.post(f"{API}/messages/send", headers=_h(tokens["mara"]), json={
            "to_player_id": pids["dovan"], "channel": "sms", "body": "ping for state probe"
        }, timeout=15)
        if r.status_code == 403 and "blocked" in r.text.lower():
            # toggle off
            r2 = requests.post(f"{API}/messages/block", headers=_h(tokens["dovan"]),
                               json={"player_id": pids["mara"]}, timeout=15)
            assert r2.status_code == 200
            # retry
            r = requests.post(f"{API}/messages/send", headers=_h(tokens["mara"]), json={
                "to_player_id": pids["dovan"], "channel": "sms", "body": "ping after unblock"
            }, timeout=15)
        assert r.status_code == 200, f"mara->dovan sms must work in pre-block state: {r.text}"

    def test_send_threads_unread_and_notification(self, tokens, pids):
        # send sms and email from mara to dovan
        r1 = requests.post(f"{API}/messages/send", headers=_h(tokens["mara"]), json={
            "to_player_id": pids["dovan"], "channel": "sms", "body": "SMS body from mara"
        }, timeout=15)
        assert r1.status_code == 200, r1.text
        sms_tid = r1.json()["thread_id"]

        r2 = requests.post(f"{API}/messages/send", headers=_h(tokens["mara"]), json={
            "to_player_id": pids["dovan"], "channel": "email",
            "subject": "Hello Dovan", "body": "Email body from mara"
        }, timeout=15)
        assert r2.status_code == 200, r2.text
        email_tid = r2.json()["thread_id"]

        # dovan threads
        r = requests.get(f"{API}/messages/threads", headers=_h(tokens["dovan"]), timeout=15)
        assert r.status_code == 200
        threads = r.json()
        tmap = {t["thread_id"]: t for t in threads}
        assert sms_tid in tmap and email_tid in tmap, f"threads missing: {list(tmap.keys())}"
        assert tmap[sms_tid]["unread"] >= 1
        assert tmap[email_tid]["unread"] >= 1
        # other_name correct (from dovan's POV the other is Mara)
        assert "Mara" in tmap[sms_tid]["other_name"]
        assert "Mara" in tmap[email_tid]["other_name"]

        # unread total
        r = requests.get(f"{API}/messages/unread", headers=_h(tokens["dovan"]), timeout=15)
        assert r.status_code == 200
        total = r.json()["count"]
        assert total >= 2, f"expected >=2 unread, got {total}"

        # notification fired
        r = requests.get(f"{API}/notifications", headers=_h(tokens["dovan"]), timeout=15)
        assert r.status_code == 200
        items = r.json().get("items", [])
        # match type=message in recent notifications
        msg_notifs = [n for n in items if n.get("type") == "message"]
        assert len(msg_notifs) >= 1, f"no message-type notifs found among {[n.get('type') for n in items[:10]]}"

        # open sms thread => marks read, unread total drops
        r = requests.get(f"{API}/messages/thread/{sms_tid}", headers=_h(tokens["dovan"]), timeout=15)
        assert r.status_code == 200
        msgs = r.json()["messages"]
        assert len(msgs) >= 1

        r = requests.get(f"{API}/messages/unread", headers=_h(tokens["dovan"]), timeout=15)
        new_total = r.json()["count"]
        assert new_total < total, f"unread should drop after reading sms thread: was {total} now {new_total}"

        # store ids for reply test via class attr
        TestMessaging.sms_tid = sms_tid
        TestMessaging.email_tid = email_tid

    def test_reply_keeps_thread(self, tokens, pids):
        # dovan replies in sms thread (deterministic via thread_id)
        r = requests.post(f"{API}/messages/send", headers=_h(tokens["dovan"]), json={
            "to_player_id": pids["mara"], "channel": "sms", "body": "sms reply"
        }, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["thread_id"] == TestMessaging.sms_tid, "sms reply must hit same thread (deterministic id)"

        # email reply with explicit thread_id
        r = requests.post(f"{API}/messages/send", headers=_h(tokens["dovan"]), json={
            "to_player_id": pids["mara"], "channel": "email",
            "thread_id": TestMessaging.email_tid, "subject": "Re: Hello Dovan", "body": "email reply"
        }, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["thread_id"] == TestMessaging.email_tid

        # fetch sms thread as mara — both directions present
        r = requests.get(f"{API}/messages/thread/{TestMessaging.sms_tid}",
                         headers=_h(tokens["mara"]), timeout=15)
        assert r.status_code == 200
        msgs = r.json()["messages"]
        froms = {m["from_player_id"] for m in msgs}
        assert pids["mara"] in froms and pids["dovan"] in froms, f"both sides should appear, got {froms}"


# ---------- block toggle ----------
class TestBlock:
    def test_block_then_unblock(self, tokens, pids):
        # dovan blocks mara
        r = requests.post(f"{API}/messages/block", headers=_h(tokens["dovan"]),
                          json={"player_id": pids["mara"]}, timeout=15)
        assert r.status_code == 200
        # if status came back 'unblocked' (already blocked from prior runs), toggle again to ensure blocked
        if r.json().get("status") == "unblocked":
            r = requests.post(f"{API}/messages/block", headers=_h(tokens["dovan"]),
                              json={"player_id": pids["mara"]}, timeout=15)
            assert r.json()["status"] == "blocked"

        # mara -> dovan should now 403
        r = requests.post(f"{API}/messages/send", headers=_h(tokens["mara"]), json={
            "to_player_id": pids["dovan"], "channel": "sms", "body": "should be blocked"
        }, timeout=15)
        assert r.status_code == 403, f"expected 403 after block, got {r.status_code}: {r.text}"

        # unblock
        r = requests.post(f"{API}/messages/block", headers=_h(tokens["dovan"]),
                          json={"player_id": pids["mara"]}, timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "unblocked"

        # mara -> dovan should work again
        r = requests.post(f"{API}/messages/send", headers=_h(tokens["mara"]), json={
            "to_player_id": pids["dovan"], "channel": "sms", "body": "after unblock"
        }, timeout=15)
        assert r.status_code == 200, r.text
