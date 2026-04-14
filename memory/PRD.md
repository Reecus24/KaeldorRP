# Discord RP Game Master Bot - PRD

## Original Problem Statement
Build a production-ready private Discord roleplay Game Master bot. Two players roleplay naturally via normal Discord messages, and the bot acts as neutral GM narrating in German.

## Architecture
- **FastAPI Backend** (Python): Admin API + LLM Gateway (GPT-5.2 via emergentintegrations)
- **Node.js Discord Bot**: discord.js v14 - message-driven + 12 slash commands
- **React Frontend**: Admin dashboard (dark obsidian/amber theme)
- **MongoDB**: Persistent storage for all game state

## What's Been Implemented (April 14, 2026)

### Phase 1 - MVP (Initial Build)
- Full FastAPI backend with 40+ API endpoints
- Discord bot with 12 slash commands
- React admin dashboard with 7 pages
- GPT-5.2 integration for narration
- Dice engine, campaign export/import

### Phase 2 - Major Refactoring (Current)
- **Message-driven GM behavior**: Bot reads normal messages in IC channels, responds only when fictionally appropriate
- **German language**: All RP output in natural German (narration, NPC dialogue, scene descriptions, recaps, checks)
- **Player Character Profiles**: 20+ fields (background, personality, strengths, weaknesses, injuries, inventory, faction ties, GM secrets, obligations, etc.)
- **Campaign generation**: `/campaign [prompt]` generates complete world in German (title, tone, world, factions, hooks, opening scene)
- **Guided character creation**: Step-by-step in-Discord flow with LLM-generated genre-specific questions
- **Character relationship setup**: Auto-generates meaningful connections between PCs
- **Opening scene generation**: Atmospheric German opening after character creation
- **Allowed player whitelist**: Only configured players can trigger GM in IC channels
- **OOC handling**: Messages starting with // or wrapped in ((...)) are ignored
- **8 new pages/features** in admin dashboard including Player Characters with tabbed editor

## Prioritized Backlog
### P0 (Done)
- Message-driven RP behavior, German output, PC profiles, campaign generation, character creation

### P1 (Next - requires user action)
- Enable MESSAGE_CONTENT privileged intent in Discord Developer Portal for live message-driven RP
- Configure DISCORD_GUILD_ID for guild restriction
- Location channel auto-creation (code-ready, needs ManageChannels permission)

### P2 (Future)
- Quest/inventory management UI pages
- NPC relationship graph visualization
- Character change tracking history
- Session scheduling with Discord reminders
- Multi-guild whitelist support
