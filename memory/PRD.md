# Discord RP Game Master Bot - PRD (April 14, 2026)

## Architecture
- FastAPI Backend: 65+ endpoints, smart memory, scene-turn logic, LLM (GPT-5.2)
- Node.js Discord Bot: discord.js v14, per-scene turn tracking, message-driven + 12 commands
- React Frontend: Admin dashboard (8 pages)
- MongoDB: 18+ collections

## Live Play Refinements (Phase 4)
### Per-Scene Turn Logic
- Each IC channel tracks pending player actions independently
- GM waits until ALL PCs present in a scene have acted before responding
- Combined multi-player response: one cohesive GM reply addressing both actions
- Split scenes process independently (no cross-blocking)
- OOC messages don't count as actions

### Response Length
- Default: 2-5 sentences (max ~600 chars normal, ~1200 for combat/reveals)
- Combined responses slightly longer to address both players
- Clean formatting: short paragraphs, NPC dialog in quotes, actions in *italics*

### Scene-Per-Channel Isolation
- sceneTurns Map tracks per-channel state: pendingActions, processing lock
- Each channel/scene has independent turn cycle
- No memory leakage between separate location channels

### New Endpoint
- POST /api/gm/scene-response - combined multi-player turn response

## Memory System (Phase 3)
- Smart context retrieval (scene_memory + memory_events + relationship_map + knowledge_store)
- Auto event extraction, scene updates, periodic summarization
- GM-only vs public vs character-specific knowledge separation

## Core Features
- Message-driven German GM, campaign generation, guided character creation
- Player Character profiles (20+ fields), NPC system, dice engine
- Location channel auto-creation, character change tracking
- Export/import, event log, recap generation

## Phase 5: Output Formatting Refinement (April 15, 2026)
### Player Section Markers
- Multi-player: **Name**: header per player section with paragraph breaks
- Solo-player: no header, direct narration
- Modes: label (bold name), mention (@user), smart (auto-detect same vs split scene)
- Config: PLAYER_SECTION_MODE, SUPPRESS_MENTION_NOTIFICATIONS

### NPC Dialogue
- German quotes „..." with italic action *descriptions*
- Dialogue and narration never blended in one sentence

### Ending Prompts
- Open atmospheric situations, not option-lists
- No "Was macht ihr: A/B/C?" format

### Response Length
- 2-4 sentences per player section (max 500 chars/section)
- Longer only for scene openings, reveals, combat peaks

## Phase 6: Sandbox World + Dice Overhaul (April 15, 2026)

### Sandbox Systems
- **Inventory**: Items with category, condition, location (carried/stored/equipped/vehicle), quantity, value
- **Properties**: Rentals, buildings, businesses with status, rent, features
- **Finances**: Per-PC balance, debts, recurring costs, world-appropriate currency
- **Transactions**: Auto-balance updates on income/expense, full log
- **Economy**: GM generates work opportunities, trade, prices, reputation effects naturally
- **Open World**: No forced plot, players can work/trade/build/socialize/explore freely

### Dice Resolution
- Clear German output: Wurf / Modifikator / Gesamt / Schwierigkeit / Ergebnis
- Categories: Kritischer Erfolg / Erfolg / Teilerfolg / Fehlschlag / Kritischer Fehlschlag
- Nat 20 = auto success (configurable), Nat 1 = auto fail (configurable)
- Impossible actions: nat 20 gives "best possible outcome with explanation"
- Narration MUST match dice result — never silently contradict

### New Collections
inventory, properties, finances, transactions

### Bot Dual-Instance Fix
- Emergent bot instance stopped — only Hetzner runs
- Global commands cleared to prevent duplicate registrations
- handleCampaign uses channel fallback if deferReply fails
