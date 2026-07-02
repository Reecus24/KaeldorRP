"""Offline / async shift resolution (P0). Shifts must clock in and out on the GAME CLOCK alone,
paying out even if the player is offline for the whole window.
Run: python3 /app/backend/tests/test_offline_shifts.py
"""
import asyncio, sys, os
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv; load_dotenv('/app/backend/.env')
from datetime import timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import game_engine as ge
from game_engine import now_utc, get_config
from game_models import new_player
from routes.player import _build_shift_payload

PID = "OFFLINE_SHIFT_TEST"


async def _setup(db, cfg, energy, start_ago_h, offline_h):
    j = await db.jobs.find_one({'id': 'cleaner'}, {'_id': 0})
    shift = next(s for s in j['shift_options'] if isinstance(s, dict))
    hours = int(shift['duration_hours'])
    p = new_player('offline_test_user', 'Offline Tester', 'drifter')
    p['id'] = PID
    p['energy'] = float(energy)
    p['job'] = {'job_id': j['id'], 'title': j['title'], 'hourly_wage': j['hourly_wage'],
                'reliability': 60, 'shifts_worked': 0, 'hours_worked': 0}
    now = now_utc()
    start_real = now - timedelta(hours=start_ago_h)
    p['registered_shift'] = {
        'job_id': j['id'], 'title': j['title'], 'shift_id': shift['id'], 'shift_name': shift.get('name'),
        'start_hour': 8, 'duration_hours': hours, 'start_game': '', 'start_real': start_real.isoformat(),
        'registered_at': (now - timedelta(hours=offline_h)).isoformat(), 'payload': _build_shift_payload(j, p, shift, hours),
    }
    p['last_resolved_at'] = (now - timedelta(hours=offline_h)).isoformat()
    await db.players.delete_one({'id': PID})
    await db.players.insert_one({**p})
    return hours, p['cash']


async def _cleanup(db):
    await db.players.delete_one({'id': PID})
    await db.events.delete_many({'player_id': PID})
    await db.notifications.delete_many({'player_id': PID})


async def main():
    c = AsyncIOMotorClient(os.environ['MONGO_URL']); db = c[os.environ['DB_NAME']]
    cfg = await get_config(db); assert cfg['time_scale'] == 1.0, "expects 1:1 time scale"
    print("=" * 60); print("OFFLINE / ASYNC SHIFT RESOLUTION"); print("=" * 60)

    # A) Fully offline, shift window entirely in the past, healthy energy at start -> COMPLETES + pays.
    hours, cash0 = await _setup(db, cfg, energy=60, start_ago_h=8, offline_h=9)
    doc = await db.players.find_one({'id': PID}, {'_id': 0}); await ge.resolve_player(db, doc)
    assert doc['job']['shifts_worked'] == 1, f"A: shift should complete, got {doc['job']['shifts_worked']}"
    assert doc['cash'] > cash0, f"A: wages should accrue offline ({doc['cash']} vs {cash0})"
    assert doc.get('registered_shift') is None and doc.get('current_activity') is None
    print(f"\u2713 A Full offline: shift completed & paid (+${round(doc['cash']-cash0,2)}), shifts_worked=1")
    await _cleanup(db)

    # B) Returns MID-shift (started 2h ago, 5h shift) -> shift IN PROGRESS, not yet completed.
    hours, cash0 = await _setup(db, cfg, energy=80, start_ago_h=2, offline_h=3)
    doc = await db.players.find_one({'id': PID}, {'_id': 0}); await ge.resolve_player(db, doc)
    assert doc.get('current_activity') and doc['current_activity'].get('kind') == 'job', "B: shift should be in progress"
    assert doc['job']['shifts_worked'] == 0, "B: not completed yet"
    assert doc.get('registered_shift') is None, "B: registration consumed"
    print("\u2713 B Mid-shift return: shift auto-started and is IN PROGRESS (persists offline)")
    await _cleanup(db)

    # C) Genuinely exhausted AT start (energy 8, shift started 30 min ago) -> correctly MISSED.
    hours, cash0 = await _setup(db, cfg, energy=8, start_ago_h=0.5, offline_h=0.6)
    doc = await db.players.find_one({'id': PID}, {'_id': 0}); await ge.resolve_player(db, doc)
    assert doc['job']['shifts_worked'] == 0, "C: exhausted -> shift missed"
    assert doc['job']['reliability'] < 60, "C: reliability penalty for missed shift"
    print("\u2713 C Exhausted at start: shift correctly MISSED with reliability penalty")
    await _cleanup(db)

    # D) Shift starts in the FUTURE -> not started, registration intact.
    hours, cash0 = await _setup(db, cfg, energy=80, start_ago_h=-2, offline_h=0.1)
    doc = await db.players.find_one({'id': PID}, {'_id': 0}); await ge.resolve_player(db, doc)
    assert doc['job']['shifts_worked'] == 0 and doc.get('registered_shift') is not None, "D: future shift stays pending"
    assert doc.get('current_activity') is None, "D: not started"
    print("\u2713 D Future shift: stays pending until its start time")
    await _cleanup(db)

    print("=" * 60); print("ALL OFFLINE-SHIFT CHECKS PASSED \u2713"); print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
