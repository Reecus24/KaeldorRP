# GM Bot — Product Requirements Document

## Original Problem Statement
Build a production-ready private Discord roleplay Game Master bot with persistent inventory and finance tracking.

## Architecture
- **Backend**: FastAPI — `server.py`, `gm_engine.py`, `dice.py`
- **Discord Bot**: Node.js discord.js v14 — `discord-bot/index.js`
- **Frontend**: React + Shadcn UI — `frontend/`
- **Database**: MongoDB (all data persistent)
- **LLM**: OpenAI GPT-5.2 via `emergentintegrations`

## Implemented Features
- [x] Discord bot with slash commands
- [x] Guided `/campaign` generation + PC creation
- [x] Per-scene turn logic (multi-player)
- [x] Memory system (event extraction, auto-summarization)
- [x] Sandbox economy (inventory, finances, properties, transactions)
- [x] Transparent dice resolution
- [x] Violence & PC Lethality
- [x] Non-repetitive German Writing Style
- [x] Character Background Enforcement
- [x] `/Inventar` + `/TW` Slash Commands
- [x] Finance & Inventory Dashboard (`/finances`)
- [x] **Character creation → Inventory/Finance auto-init** (Feb 2026)
  - `POST /api/sandbox/init-from-character` parses inventory text into structured items
  - Detects money (10 Silbermünzen, praller Beutel, 25 Goldmünzen)
  - Classifies items (weapon, tool, medical, consumable, valuable, document, equipment)
  - Creates finance record with detected currency and balance
  - Called automatically after Discord character creation

## Key API Endpoints
- `POST /api/sandbox/init-from-character` — Parse PC inventory text → structured items + finances
- `GET/POST/PUT/DELETE /api/inventory` — Full CRUD
- `GET /api/sandbox/inventar/{pc_id}` — Categorized view
- `POST /api/sandbox/tagwechsel` — Day change
- `GET/POST /api/transactions` — Transaction history
- `GET/POST /api/finances` — Finance records

## Backlog
- discord-bot/index.js modularization (optional)

## Notes
- Discord bot on Emergent is STOPPED
- All GM output in German
- Tagwechsel uses `advance_day` flag for multi-PC
