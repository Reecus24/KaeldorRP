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

## Implemented (Feb 2026)
- [x] **Violence & PC Lethality** — PCs can die, NPCs have no plot armor, injury states (leicht verletzt → tot), world reacts to violence (witnesses, revenge, law)
- [x] **Non-repetitive German Writing Style** — Banned generic AI phrases, varied sentence structure, specific sensory details, short/concrete responses
- [x] **Character Background Enforcement** — Background/profession determines abilities, spontaneous claims rejected, high SG for out-of-background actions
- [x] **`/Inventar` Slash Command** — Categorized inventory display (Ausgerüstet, Mitgeführt, Gelagert, Verbrauchsgüter, Werkzeuge, Wertsachen, Dokumente, Handelswaren) + Finanzen + Besitz
- [x] **`/TW` (Tagwechsel) Slash Command** — Day change processing: profession-based wages, property rent, recurring costs, debt display, balance update, day counter

## Key API Endpoints
- `POST /api/gm/scene-response` — Combined turn-based GM response
- `POST /api/gm/message-driven` — Single-message GM response
- `GET /api/sandbox/inventar/{pc_id}` — Categorized inventory + finances
- `POST /api/sandbox/tagwechsel` — Day change processing
- `POST /api/campaigns`, `GET /api/campaigns/active`
- `POST /api/player-characters`, `GET /api/player-characters/active`
- `POST /api/inventory`, `POST /api/finances`, `POST /api/properties`
- `POST /api/transactions`

## DB Schema
- campaigns: {id, name, tone, world_summary, is_active, current_day}
- player_characters: {id, campaign_id, discord_user_id, character_name, status, background, skills, injuries_conditions, ...}
- inventory: {id, campaign_id, owner_pc_id, item_name, category, quantity, condition, location, value}
- finances: {id, campaign_id, pc_id, balance, currency, debts, recurring_costs}
- properties: {id, campaign_id, owner_pc_id, name, property_type, status, rent_cost, rent_currency}
- transactions: {id, campaign_id, pc_id, transaction_type, amount, currency, description}
- memory_events, scene_memory, relationship_map, knowledge_store, npcs, lore_entries, events, recaps

## Backlog
- Refactoring: `discord-bot/index.js` (800+ lines) could be split into modules
- No other pending tasks

## Important Notes
- Discord bot on Emergent is STOPPED — user runs it on Hetzner
- All GM output must be in German
- The `emergentintegrations` package is installed via custom extra-index-url
