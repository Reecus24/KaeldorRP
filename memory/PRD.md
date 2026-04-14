# Discord RP Game Master Bot - PRD (April 14, 2026)

## Architecture
- **FastAPI Backend**: 60+ endpoints, smart memory system, LLM Gateway (GPT-5.2)
- **Node.js Discord Bot**: discord.js v14, message-driven + 12 commands, auto intent fallback
- **React Frontend**: Admin dashboard (8 pages, dark obsidian/amber)
- **MongoDB**: 18 collections including structured memory

## Memory Architecture (NEW)
### Short-term: scene_memory
- Active scene state: location, atmosphere, tension, present NPCs, dangers, objectives, time

### Medium-term: memory_events
- Structured events: injury, item_lost/gained, clue, faction_change, trust_change, oath, debt, damage, secret, relationship, threat, status
- Each tagged with visibility (public/gm_only/character_specific), resolved status

### Long-term: recaps (auto-summarized)
- Structured summaries: key_consequences, pc_changes, npc_changes, world_changes, unresolved_hooks

### Knowledge: knowledge_store
- GM-only secrets, character-specific knowledge, public discoveries
- Never revealed unless fictionally appropriate

### Relationships: relationship_map
- PC↔PC, PC↔NPC, NPC↔faction with type/value/notes

### Smart Context Retrieval
- Replaces raw chat history with focused context packet
- Loads: scene memory, active PCs, present NPCs, unresolved events, relationships, lore, knowledge, summaries, minimal recent chat

### Auto-Processing Pipeline (after each GM response)
1. Extract structured memory events from narrative (LLM)
2. Update scene memory (LLM suggests changes)
3. Auto-summarize every 15 events
4. Track character changes

## What's Implemented
- Full message-driven German GM with smart memory
- Campaign generation + guided character creation
- Player Character profiles (20+ fields)
- Location channel auto-creation
- Character change tracking
- 12 slash commands, allowed player whitelist, OOC handling
