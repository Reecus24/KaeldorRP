"""Dialogue boundary for a future self-hosted model. No external services or API keys.

Current dialogue is explicitly scripted. Per-character memories and verified quest
facts are persisted so a future model can use them without owning rewards.
"""
from world_engine import scripted_reply


def availability(cfg):
    return {"enabled": False, "mode": "scripted", "description": "Scripted NPCs with memory · self-hosted AI planned"}


async def reply(db, p, npc, text, offers, cfg):
    return scripted_reply(p, npc, text, offers), "scripted"
