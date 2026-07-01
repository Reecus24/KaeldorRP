# Kaeldor RPG — Backend Architecture (post-refactor, 2026-07-01)

The monolithic `server.py` (~3600 lines) was split into a modular package. API paths and behaviour are
UNCHANGED — only the file organisation changed.

## Backend layout (`/app/backend/`)
```
core.py            # Shared foundation: Mongo client + db, the central `api = APIRouter(prefix="/api")`,
                   # auth (hash/verify/JWT, current_user, admin_user), and ALL shared helpers
                   # (get_state, save_player, credit_profile, meets_requirements, shop/market helpers,
                   # request-body Pydantic models, etc.). Exposes everything via `__all__`.
routes/
  player.py        # auth, character, game state, actions, jobs+sectors, courses/education,
                   # inventory/equipment, hospital/jail/legal/underworld, illegal-actions, daily-summaries
  economy.py       # shop/city-shops, bank & loans, housing, vehicles, stock & crypto markets
  business.py      # owned businesses: buy/manage, supply chain, staffing, hiring, P&L, market
  social.py        # networking & encounters, chat, messages, notifications, player directory, leaderboard
  admin.py         # ALL /admin/* endpoints (sandbox CRUD, tuning, config, overview, feed, layout)
server.py          # ENTRY POINT ONLY: creates FastAPI app, imports core + all route modules
                   # (which register their endpoints on the shared `api` router), CORS,
                   # startup migrations + seeding, include_router, shutdown.

game_engine.py     # Core progression: clock sync, decay_needs, skill decay, taxes, interest,
                   # daily-summary flush, offline resolution (resolve_player).
game_models.py     # PyObjectId models, DEFAULT_CONFIG + TUNE cache (apply_tuning), empty_ledger.
employee_engine.py # NPC hiring, strict wage/production math (NO business rent/fixed costs).
employment.py      # Job applications, shift/roster math, opening-hours helpers.
market_engine.py   # Stocks & crypto price simulation.
seed_data.py       # Base content (jobs, sectors, shops, locations, items...) + CONTENT_MAP.
```

## How the router sharing works (no circular imports)
- `core.py` creates a single `api = APIRouter(prefix="/api")` and imports NOTHING from `routes/`.
- Each `routes/*.py` does `from core import *` and decorates its endpoints with `@api.get/post/...`.
  Importing the module registers those endpoints on the shared `api` router (side effect).
- `server.py` imports `core` (for the app/CORS/db) and imports every route module, then calls
  `app.include_router(api)` exactly once.

## Where to add new logic
- **New endpoint** → pick the matching `routes/*.py` file by domain and add `@api.<verb>("/path")`.
  Reuse helpers/bodies from `core` (already imported via `from core import *`).
- **New shared helper or request-body model** → add it to `core.py` (it is auto-exported through `__all__`).
- **New tunable constant** → add to `DEFAULT_CONFIG["tuning"]` in `game_models.py`; it becomes editable
  in Admin ▸ Gameplay Tuning ▸ Tuning and is read live from `game_models.TUNE`.
- **New core progression/economy math** → `game_engine.py` (guarded by `tests/verify_economy.py` /
  `tests/verify_markets.py` — run them on every change).
- **New content type** → `seed_data.py` + `CONTENT_MAP`, editable via Admin content editors.

## Verification gates (run on every logic change)
```
python3 /app/tests/verify_economy.py
python3 /app/tests/verify_markets.py
```
Both must pass. Then smoke-test one endpoint per route module and, for UI changes, run the testing agent.
