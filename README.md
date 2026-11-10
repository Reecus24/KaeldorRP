# KAELDOR

A persistent browser life simulation with a React interface, FastAPI backend and MongoDB storage.
The Owner Sandbox controls activities, items, jobs, businesses and simulation settings.

## Local setup

Use Python 3.11+ and Node.js 20+. Validation for this repair used Python 3.13 and Node.js 24.
Start a local MongoDB instance, create a Python virtual environment, then install
`backend/requirements.txt`. This game does not require an Emergent API key or its private Python package.

Set these environment variables before starting the backend:

| Variable | Value |
| --- | --- |
| `MONGO_URL` | Your MongoDB connection URI |
| `DB_NAME` | A separate database for this game |
| `JWT_SECRET` | A long random signing secret |
| `ADMIN_EMAIL` | Your Owner account email |
| `ADMIN_PASSWORD` | Initial Owner password; required only to create a new Owner |

From `backend/`, run `python -m uvicorn server:app --host 127.0.0.1 --port 8001`.
Existing Owner passwords and edited content are preserved at startup.

From `frontend/`, run `npm install --legacy-peer-deps`, then set
`REACT_APP_BACKEND_URL=http://127.0.0.1:8001` and run `npm start`.
For a deployment that serves UI and API on the same origin, omit that variable and proxy `/api`
to FastAPI. Use `npm run build` for the production UI. The host must route client-side page paths
back to `index.html`.

The code repository does not contain the Emergent preview's MongoDB player data. To retain that
world when moving hosts, export/import its database separately and supply the new connection URI.

## Owner editing

After signing in as Owner, open **Owner Sandbox**. **Gameplay Tuning → Tuning** exposes simulation
settings, including needs thresholds and hospital duration/recovery. Numeric and boolean fields
added to the default configuration appear automatically. **Config** retains advanced JSON editing.
Content editors support activities, items, courses, jobs, shops, businesses and more.

New features must follow [AGENTS.md](AGENTS.md): editable balance values, persisted settings,
non-destructive migrations, explicit units, validation and regression coverage.
See [Admin Sandbox](docs/ADMIN_SANDBOX.md) and [Player Stats](docs/PLAYER_STATS_LOGIC.md).

## Verification

Install `backend/requirements-test.txt` in addition to runtime requirements. Set `PYTHONPATH` to
the absolute `backend` folder and `PYTHONUTF8=1`, then run from the repository root:

```text
python -m pytest backend/tests/test_needs_timeline.py backend/tests/test_core_gameplay_guards.py backend/tests/test_player_lock.py backend/tests/test_sandbox_persistence.py backend/tests/test_economy_consistency.py
python tests/verify_economy.py
python tests/verify_markets.py
python backend/tests/test_logic_links.py
```

From `frontend/`: `npm test -- --watchAll=false --runInBand`, then `npm run build`.
The new regression suites use synthetic clocks and isolated mock databases. Older integration
tests contain historical Emergent URLs: configure an isolated local test service before running them.

Request leases serialize each player's read/resolve/mutate/save operation across API workers.
They require a writable MongoDB and synchronized host clocks; they are not multi-document
transactions. Production deployment and testing against the retained live database remain separate
from isolated local verification.
