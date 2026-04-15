# GM Bot — Product Requirements Document

## Original Problem Statement
Build a production-ready private Discord roleplay Game Master bot. Two human players roleplay in-character in Discord channels, and the bot acts as the neutral, consequence-driven Game Master. Needs Node.js Discord bot, FastAPI backend, MongoDB, and a lightweight React admin dashboard.

## Architecture
- **Backend**: FastAPI (Python) — `/app/backend/server.py`, `/app/backend/gm_engine.py`, `/app/backend/dice.py`
- **Discord Bot**: Node.js discord.js v14 — `/app/discord-bot/index.js`
- **Frontend**: React + Shadcn UI — `/app/frontend/`
- **Database**: MongoDB
- **LLM**: OpenAI GPT-5.2 via `emergentintegrations` (Emergent LLM Key)

## Core Features (Implemented)
- [x] Discord bot with slash commands (campaign, scene, recap, rules, tone, etc.)
- [x] Guided `/campaign` generation + PC creation flow
- [x] Per-scene turn logic (split vs shared scenes, multi-player formatting)
- [x] Memory system (short/long-term event extraction, auto-summarization)
- [x] Sandbox economy (inventory, finances, properties, transactions)
- [x] Transparent dice resolution (1W20 with SG display)
- [x] Location auto-creation (channel per location)
- [x] React admin dashboard (Campaigns, PCs, NPCs, Lore, Config)
- [x] Violence & PC Lethality (injury states, NPC mortality, no plot armor)
- [x] Non-repetitive German Writing Style (banned generic phrases)
- [x] Character Background Enforcement (profession/skills determine abilities)
- [x] `/Inventar` Slash Command (categorized inventory + finances)
- [x] `/TW` Slash Command (day change with wage/rent/expenses)
- [x] **Finance Dashboard** (Feb 2026) — full income/expense tracking per PC

## Finance Dashboard Details (Feb 2026)
- **Route**: `/finances` in React dashboard
- **Components**:
  - PC selector dropdown (switches between active characters)
  - Summary cards: Guthaben, Einnahmen (letzte), Ausgaben (letzte), Mietkosten
  - **Übersicht tab**: Wiederkehrende Einnahmen (profession-based), Wiederkehrende Ausgaben (rent, recurring costs), Schulden & Verpflichtungen, Besitz & Mietobjekte
  - **Transaktionslog tab**: Table with Tag, Typ, Beschreibung, Quelle (TW/gameplay), Betrag
  - **Tagesansicht tab**: Transactions grouped by day with daily income/expense/net totals
- **Backend integration**: All transactions from /TW, gameplay, trade, purchases automatically appear with `day` and `source` fields
- **Automatic sync**: Financial state used by GM engine in narration

## Key API Endpoints
- `POST /api/gm/scene-response` — Combined turn-based GM response
- `GET /api/sandbox/inventar/{pc_id}` — Categorized inventory + finances
- `POST /api/sandbox/tagwechsel` — Day change processing (with advance_day flag)
- `GET /api/transactions?campaign_id=X&pc_id=Y` — Transaction history with day/source
- `POST /api/transactions` — Add transaction (auto-adds day + source=gameplay)
- `GET /api/finances`, `GET /api/properties`

## DB Schema
- campaigns: {id, name, tone, world_summary, is_active, current_day}
- player_characters: {id, campaign_id, discord_user_id, character_name, status, background, ...}
- inventory: {id, campaign_id, owner_pc_id, item_name, category, quantity, condition, location, value}
- finances: {id, campaign_id, pc_id, balance, currency, debts, recurring_costs}
- properties: {id, campaign_id, owner_pc_id, name, property_type, status, rent_cost, rent_currency}
- transactions: {id, campaign_id, pc_id, transaction_type, amount, currency, description, counterparty, day, source, timestamp}

## Backlog
- Refactoring: `discord-bot/index.js` (900+ lines) could be split into modules

## Important Notes
- Discord bot on Emergent is STOPPED — user runs it on Hetzner
- All GM output must be in German
- Tagwechsel uses `advance_day` flag: only first PC increments day counter
