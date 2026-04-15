# GM Bot — Product Requirements Document

## Original Problem Statement
Build a production-ready private Discord roleplay Game Master bot with real lethality, persistent economy, and no hidden mercy logic.

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
- [x] `/Inventar` + `/TW` Slash Commands
- [x] Finance & Inventory Dashboard (`/finances`)
- [x] Character creation → auto-init inventory + finances
- [x] **True PC Lethality** — no hidden mercy, no last-second saves, explicit death triggers
- [x] **Scene State Rules** — success = real state change, anti-loop enforcement
- [x] **Anti-Repetition** — no recycled threats, forced progression every turn
- [x] **Discord Formatting** — clean paragraphs, separated dice blocks

## GM Rules (gm_engine.py)
Key rule sections in system prompts:
- `_lethality()`: PC death triggers, forbidden mercy behaviors, wound chain
- `_scene_state_rules()`: Success must change tactical state, anti-loop rules, forced progression
- `_writing_style()`: Discord formatting, anti-KI-Floskeln, anti-repetition
- `_background_enforcement()`: Profession/skills binding, spontaneous claims rejection

## Inventory Persistence
- **Storage**: MongoDB `inventory` collection
- **Auto-init**: Character creation text parsed into structured items + finances
- **3 fallback layers**:
  1. Discord bot `finalizeCreation` → calls `init-from-character`
  2. Discord `/inventar` command → auto-init if 0 items but text exists
  3. Dashboard `loadAll()` → auto-init if 0 items but text exists
- **Sync**: Dashboard and Discord both read/write same MongoDB collection

## Backlog
- discord-bot/index.js modularization (optional)

## Notes
- Discord bot on Emergent is STOPPED
- All GM output in German
