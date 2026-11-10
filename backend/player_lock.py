"""Cross-worker leases for a complete read/resolve/mutate/save player operation.

Use one lease around the *whole* authenticated request, not just resolve_player.
The collection's built-in unique _id index arbitrates ownership on standalone
MongoDB as well as replica sets. Expiry is checked by queries; no TTL index is
required. A failed renewal cancels the request so it cannot continue writing.

This is serialization, not a database transaction: cancellation cannot undo a
write already accepted by MongoDB. Hosts must have synchronized UTC clocks.
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import logging
import math
import uuid

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError, PyMongoError


logger = logging.getLogger(__name__)
LEASE_SECONDS = 30.0
WAIT_SECONDS = 10.0
POLL_SECONDS = 0.05


def _now():
    return datetime.now(timezone.utc)


def _unavailable(detail):
    return HTTPException(status_code=503, detail=detail, headers={"Retry-After": "1"})


@asynccontextmanager
async def player_operation(db, user_id, *, lease_seconds=LEASE_SECONDS,
                           wait_timeout=WAIT_SECONDS, renew_interval=None,
                           poll_interval=POLL_SECONDS):
    """Serialize operations for one user; independent users can proceed together.

    Timing arguments are injectable for deterministic, isolated concurrency tests.
    Callers must not detach player writes into background tasks outside this scope.
    """
    renew_interval = lease_seconds / 3 if renew_interval is None else renew_interval
    for name, value in (("lease_seconds", lease_seconds), ("wait_timeout", wait_timeout),
                        ("renew_interval", renew_interval), ("poll_interval", poll_interval)):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a finite positive number")
    if renew_interval >= lease_seconds:
        raise ValueError("renew_interval must be shorter than lease_seconds")
    if not user_id:
        raise ValueError("A user_id is required for player serialization")

    collection = db.player_operation_locks
    token = uuid.uuid4().hex
    key = str(user_id)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + wait_timeout
    parent = asyncio.current_task()
    lost = asyncio.Event()
    acquired = False
    heartbeat = None

    async def release():
        try:
            # Never delete a successor's lease after expiry/takeover.
            await asyncio.wait_for(collection.delete_one({"_id": key, "owner": token}),
                                   timeout=min(3.0, lease_seconds))
        except (PyMongoError, asyncio.TimeoutError):
            logger.warning("Could not release player operation lease; it will expire", exc_info=True)

    async def renew():
        try:
            while True:
                await asyncio.sleep(renew_interval)
                now = _now()
                result = await asyncio.wait_for(collection.update_one(
                    {"_id": key, "owner": token, "expires_at": {"$gt": now}},
                    {"$set": {"expires_at": now + timedelta(seconds=lease_seconds)}},
                ), timeout=min(renew_interval, lease_seconds - renew_interval))
                if result.matched_count != 1:
                    raise RuntimeError("Player operation lease ownership expired or changed")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Player operation lease lost; cancelling its request", exc_info=True)
            lost.set()
            parent.cancel()

    try:
        while not acquired:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise _unavailable("Your character is processing another request. Please retry.")
            now = _now()
            expiry = now + timedelta(seconds=lease_seconds)
            try:
                result = await asyncio.wait_for(collection.update_one(
                    {"_id": key, "$or": [{"expires_at": {"$lte": now}}, {"owner": token}]},
                    {"$set": {"owner": token, "expires_at": expiry}}, upsert=True,
                ), timeout=remaining)
                acquired = result.matched_count == 1 or result.upserted_id is not None
                if acquired and expiry <= _now():
                    # A slow claim must be renewed before any player data is read.
                    acquired = False
                    continue
            except DuplicateKeyError:
                # Another live owner occupies this user's unique _id.
                pass
            except (PyMongoError, asyncio.TimeoutError) as exc:
                raise _unavailable("Character state is temporarily unavailable. Please retry.") from exc
            if not acquired:
                await asyncio.sleep(min(poll_interval, max(0, deadline - loop.time())))

        heartbeat = asyncio.create_task(renew(), name=f"player-lease-{key}")
        try:
            yield
            if lost.is_set():
                raise _unavailable("Character state changed while processing. Please retry.")
        except asyncio.CancelledError as exc:
            if lost.is_set():
                raise _unavailable("Character state changed while processing. Please retry.") from exc
            raise
    finally:
        if heartbeat is not None:
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass
        # Also release after an ambiguous acquire timeout: a remote write may have
        # succeeded before the timeout. The owner filter makes cleanup harmless.
        cleanup = asyncio.create_task(release())
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            await cleanup
            raise
