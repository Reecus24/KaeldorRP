"""Isolated request-serialization checks; no live MongoDB connection."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient
from pymongo.errors import AutoReconnect

from player_lock import player_operation


def test_concurrent_consumption_cannot_overwrite_newer_player_snapshot():
    async def scenario():
        db = AsyncMongoMockClient().test
        await db.players.insert_one({"_id": "u", "hunger": 80, "food": 2})
        first_entered, release_first, second_entered = (asyncio.Event() for _ in range(3))

        async def consume(first=False):
            async with player_operation(db, "u", poll_interval=0.001):
                snapshot = await db.players.find_one({"_id": "u"})
                if first:
                    first_entered.set()
                    await release_first.wait()
                else:
                    second_entered.set()
                snapshot["hunger"] -= 10
                snapshot["food"] -= 1
                await db.players.replace_one({"_id": "u"}, snapshot)

        first = asyncio.create_task(consume(True))
        await first_entered.wait()
        second = asyncio.create_task(consume())
        await asyncio.sleep(0.02)
        assert not second_entered.is_set()
        release_first.set()
        await asyncio.gather(first, second)
        p = await db.players.find_one({"_id": "u"})
        assert (p["hunger"], p["food"]) == (60, 0)
        assert await db.player_operation_locks.count_documents({}) == 0

    asyncio.run(scenario())


def test_exception_releases_lock_for_next_request():
    async def scenario():
        db = AsyncMongoMockClient().test
        with pytest.raises(ValueError, match="handler failed"):
            async with player_operation(db, "u"):
                raise ValueError("handler failed")
        assert await db.player_operation_locks.find_one({"_id": "u"}) is None
        async with player_operation(db, "u", wait_timeout=0.05):
            assert await db.player_operation_locks.find_one({"_id": "u"}) is not None

    asyncio.run(scenario())


def test_expired_lease_can_be_taken_over():
    async def scenario():
        db = AsyncMongoMockClient().test
        await db.player_operation_locks.insert_one({
            "_id": "u", "owner": "crashed-worker",
            "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
        })
        async with player_operation(db, "u"):
            lock = await db.player_operation_locks.find_one({"_id": "u"})
            assert lock["owner"] != "crashed-worker"
        assert await db.player_operation_locks.count_documents({}) == 0

    asyncio.run(scenario())


def test_different_users_can_process_concurrently():
    async def scenario():
        db = AsyncMongoMockClient().test
        a, b = asyncio.Event(), asyncio.Event()

        async def request(user, entered, other):
            async with player_operation(db, user):
                entered.set()
                await asyncio.wait_for(other.wait(), timeout=1)

        await asyncio.gather(request("a", a, b), request("b", b, a))

    asyncio.run(scenario())


def test_busy_timeout_does_not_release_current_owner():
    async def scenario():
        db = AsyncMongoMockClient().test
        async with player_operation(db, "u"):
            owner = (await db.player_operation_locks.find_one({"_id": "u"}))["owner"]
            with pytest.raises(HTTPException) as error:
                async with player_operation(db, "u", wait_timeout=0.025, poll_interval=0.002):
                    pytest.fail("second request entered while the first still owns the lease")
            assert error.value.status_code == 503
            assert error.value.headers == {"Retry-After": "1"}
            assert (await db.player_operation_locks.find_one({"_id": "u"}))["owner"] == owner

    asyncio.run(scenario())


def test_heartbeat_keeps_lease_after_original_expiry():
    async def scenario():
        db = AsyncMongoMockClient().test
        async with player_operation(db, "u", lease_seconds=0.12, renew_interval=0.02):
            initial = await db.player_operation_locks.find_one({"_id": "u"})
            await asyncio.sleep(0.18)
            refreshed = await db.player_operation_locks.find_one({"_id": "u"})
            assert refreshed["owner"] == initial["owner"]
            assert refreshed["expires_at"] > initial["expires_at"]
            with pytest.raises(HTTPException):
                async with player_operation(db, "u", wait_timeout=0.02, poll_interval=0.002):
                    pytest.fail("heartbeat did not preserve ownership")

    asyncio.run(scenario())


def test_request_cancellation_releases_lease_and_heartbeat():
    async def scenario():
        db = AsyncMongoMockClient().test
        entered = asyncio.Event()

        async def request():
            async with player_operation(db, "u", lease_seconds=0.12, renew_interval=0.02):
                entered.set()
                await asyncio.sleep(10)

        task = asyncio.create_task(request())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await db.player_operation_locks.count_documents({}) == 0
        assert not [t for t in asyncio.all_tasks() if t.get_name().startswith("player-lease-")]

    asyncio.run(scenario())


def test_lost_lease_cancels_before_further_writes_and_preserves_successor():
    async def scenario():
        db = AsyncMongoMockClient().test
        entered = asyncio.Event()
        wrote = []

        async def request():
            async with player_operation(db, "u", lease_seconds=0.12, renew_interval=0.01):
                entered.set()
                await asyncio.sleep(10)
                wrote.append(True)

        task = asyncio.create_task(request())
        await entered.wait()
        await db.player_operation_locks.update_one({"_id": "u"}, {"$set": {
            "owner": "successor", "expires_at": datetime.now(timezone.utc) + timedelta(seconds=30),
        }})
        with pytest.raises(HTTPException) as error:
            await asyncio.wait_for(task, timeout=1)
        assert error.value.status_code == 503
        assert wrote == []
        assert (await db.player_operation_locks.find_one({"_id": "u"}))["owner"] == "successor"

    asyncio.run(scenario())


def test_database_error_during_renewal_cancels_request():
    async def scenario():
        collection = AsyncMongoMockClient().test.player_operation_locks

        class BrokenRenewal:
            calls = 0

            async def update_one(self, *args, **kwargs):
                self.calls += 1
                if self.calls > 1:
                    raise AutoReconnect("simulated unavailable database")
                return await collection.update_one(*args, **kwargs)

            async def delete_one(self, *args, **kwargs):
                return await collection.delete_one(*args, **kwargs)

        with pytest.raises(HTTPException) as error:
            async with player_operation(SimpleNamespace(player_operation_locks=BrokenRenewal()), "u",
                                        lease_seconds=0.12, renew_interval=0.01):
                await asyncio.sleep(1)
                pytest.fail("request continued despite lease renewal failure")
        assert error.value.status_code == 503
        assert await collection.count_documents({}) == 0

    asyncio.run(scenario())
