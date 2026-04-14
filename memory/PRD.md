# Discord RP Game Master Bot - PRD (Updated April 14, 2026)

## Architecture
- **FastAPI Backend**: Admin API + LLM Gateway (GPT-5.2) + MongoDB
- **Node.js Discord Bot**: discord.js v14 - message-driven + 12 slash commands + auto-fallback for intents
- **React Frontend**: Admin dashboard (dark obsidian/amber theme, 8 pages)
- **MongoDB**: Persistent storage (14 collections)

## What's Been Implemented

### Phase 1 - MVP (Initial)
- Full backend with 40+ endpoints, dice engine, campaign export/import
- Discord bot with slash commands, React admin dashboard

### Phase 2 - Message-Driven German GM
- Message-driven GM: natural IC channel reading, responds only when fictionally appropriate
- All output in German, Player Character profiles (20+ fields)
- /campaign command: world generation + guided character creation + relationship + opening scene
- OOC handling (// and ((...)) markers), allowed player whitelist

### Phase 3 - Current
- **Location channel auto-creation**: When GM marks [NEUER_ORT: name], bot creates Discord channel under campaign category, registers as IC, posts scene header
- **Character change tracking**: GM marks [ÄNDERUNG: Charakter - Change] in responses, bot auto-tracks changes to character_changes collection and event log
- **Graceful intent fallback**: Bot tries MessageContent intent first, falls back to slash-commands-only with clear instructions
- **Campaign auto_create_channels flag**: Enable/disable location channel creation per campaign

## Required Discord Setup
1. Enable **Message Content Intent** at https://discord.com/developers/applications → Bot → Privileged Gateway Intents
2. Set DISCORD_GUILD_ID in /app/discord-bot/.env
3. Bot needs: applications.commands, Send Messages, Embed Links, Read Message History, Manage Channels (for location channels)

## Backlog
- P1: Enable MessageContent intent in portal, test live /campaign flow
- P2: Auto-apply character changes to PC profiles from tracked changes
- P2: Quest/inventory management UI
- P3: Session scheduling, multi-guild support
