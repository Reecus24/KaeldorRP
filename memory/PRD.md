# GM Bot — Product Requirements Document

## Original Problem Statement
Build a production-ready private Discord roleplay Game Master bot. Two human players roleplay in-character in Discord channels, and the bot acts as the neutral, consequence-driven Game Master.

## Architecture
- **Backend**: FastAPI (Python) — `server.py`, `gm_engine.py`, `dice.py`
- **Discord Bot**: Node.js discord.js v14 — `discord-bot/index.js`
- **Frontend**: React + Shadcn UI — `frontend/`
- **Database**: MongoDB (persistent — all data survives restarts/redeploys)
- **LLM**: OpenAI GPT-5.2 via `emergentintegrations`

## Implemented Features
- [x] Discord bot with slash commands
- [x] Guided `/campaign` generation + PC creation
- [x] Per-scene turn logic (multi-player formatting)
- [x] Memory system (event extraction, auto-summarization)
- [x] Sandbox economy (inventory, finances, properties, transactions)
- [x] Transparent dice resolution (1W20 with SG)
- [x] Location auto-creation
- [x] Violence & PC Lethality (injury states, no plot armor)
- [x] Non-repetitive German Writing Style
- [x] Character Background Enforcement
- [x] `/Inventar` + `/TW` Slash Commands
- [x] **Finance & Inventory Dashboard** (`/finances`)
  - Inventar tab: persistent CRUD, categorized by location, inline qty +/-, add/edit/delete
  - Finanzen tab: recurring income/expenses, debts, properties
  - Transaktionslog: table with day/type/source/amount
  - Tagesansicht: grouped by day with daily totals

## Persistence Model
All data stored in MongoDB collections:
- `inventory`: {id, campaign_id, owner_pc_id, item_name, category, quantity, condition, location, value, description}
- `finances`: {id, campaign_id, pc_id, balance, currency, debts, recurring_costs}
- `transactions`: {id, campaign_id, pc_id, transaction_type, amount, currency, description, day, source, timestamp}
- `properties`: {id, campaign_id, owner_pc_id, name, property_type, rent_cost, status}

## Key API Endpoints
- `GET/POST/PUT/DELETE /api/inventory` — Full CRUD for inventory items
- `GET /api/sandbox/inventar/{pc_id}` — Categorized view
- `POST /api/sandbox/tagwechsel` — Day change processing
- `GET /api/transactions` — Transaction history with day/source
- `POST /api/transactions` — Add transaction (auto-adds day + source)

## Backlog
- Refactoring: `discord-bot/index.js` modularization (optional)

## Notes
- Discord bot on Emergent is STOPPED — user runs on Hetzner
- All GM output in German
- Tagwechsel uses `advance_day` flag for multi-PC support
