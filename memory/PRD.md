# Discord RP Game Master Bot - PRD

## Original Problem Statement
Build a production-ready private Discord roleplay Game Master bot as a full-stack app. Bot acts as neutral GM narrating scenes, controlling NPCs, resolving consequences, tracking world state. Admin dashboard for campaign management.

## Architecture
- **FastAPI Backend** (Python): Admin API + LLM Gateway (GPT-5.2 via emergentintegrations)
- **Node.js Discord Bot**: discord.js v14 with 12 slash commands
- **React Frontend**: Dark-themed admin dashboard (obsidian/amber)
- **MongoDB**: Persistent storage for all game state

## User Personas
- **GM Admin**: Manages campaigns, NPCs, lore, rules via dashboard
- **Discord Players**: Interact via slash commands during roleplay sessions

## Core Requirements
- [x] Discord bot with 12 slash commands (/gm, /npc, /roll, /check, /scene, /recap, /journal, /rules, /set_tone, /reset_session, /new_campaign, /set_channel_mode)
- [x] GPT-5.2 powered narration with tone-configurable responses
- [x] Persistent campaign state (campaigns, NPCs, lore, scenes, events, rules, channels)
- [x] Dice rolling engine (standard notation: NdS+M, critical success/failure)
- [x] Admin dashboard with CRUD for all entities
- [x] Export/import campaign data
- [x] Channel mode configuration (IC/OOC/Admin)
- [x] No authentication (admin-only deployment)

## What's Been Implemented (April 14, 2026)
- Full FastAPI backend with 30+ API endpoints
- Discord bot online as "Kaeldor Roleplay#8532" with all 12 commands registered
- React admin dashboard with 7 pages (Dashboard, Campaigns, NPCs, Lore, Rules & Tone, Channels, Event Log)
- GPT-5.2 integration for GM narration, NPC dialogue, skill checks, and recap generation
- Dice engine supporting standard notation
- Campaign export/import functionality
- Event log with terminal-style viewer

## Prioritized Backlog
### P0 (Done)
- All slash commands functional
- Campaign/NPC/Lore CRUD
- LLM narration pipeline
- Dice rolling

### P1 (Next)
- Quest/inventory management UI pages
- Scene creation from dashboard
- Player character profile management
- World summary auto-generation

### P2 (Future)
- Multi-guild support (whitelist)
- Chat history viewer in dashboard
- NPC relationship graph visualization
- Session scheduling integration
- Campaign template library
