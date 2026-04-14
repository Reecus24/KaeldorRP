from fastapi import FastAPI, APIRouter, HTTPException, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

from dice import parse_and_roll, format_roll_result
from gm_engine import GameMasterEngine
gm = GameMasterEngine()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ── Pydantic Models ──

class CampaignCreate(BaseModel):
    name: str
    world_summary: str = ""
    tone: str = "realistic"

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    world_summary: Optional[str] = None
    tone: Optional[str] = None
    is_active: Optional[bool] = None
    auto_create_channels: Optional[bool] = None

class NPCCreate(BaseModel):
    campaign_id: str
    name: str
    role: str = ""
    faction: str = ""
    personality_traits: str = ""
    motivation: str = ""
    secrets: str = ""
    relationship_notes: str = ""
    trust_level: int = 0
    status: str = "alive"
    voice_style: str = ""

class NPCUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    faction: Optional[str] = None
    personality_traits: Optional[str] = None
    motivation: Optional[str] = None
    secrets: Optional[str] = None
    relationship_notes: Optional[str] = None
    trust_level: Optional[int] = None
    status: Optional[str] = None
    voice_style: Optional[str] = None

class LoreCreate(BaseModel):
    campaign_id: str
    category: str = "custom"
    title: str
    content: str
    tags: List[str] = []

class LoreUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None

class SceneCreate(BaseModel):
    campaign_id: str
    location: str
    time_of_day: str = ""
    description: str = ""
    active_threats: List[str] = []
    important_npcs: List[str] = []
    tension_level: int = 1
    unresolved_hooks: List[str] = []

class SceneUpdate(BaseModel):
    location: Optional[str] = None
    time_of_day: Optional[str] = None
    description: Optional[str] = None
    active_threats: Optional[List[str]] = None
    important_npcs: Optional[List[str]] = None
    tension_level: Optional[int] = None
    unresolved_hooks: Optional[List[str]] = None
    is_active: Optional[bool] = None

class EventCreate(BaseModel):
    campaign_id: str
    event_type: str = "action"
    summary: str
    details: str = ""

class RulesCreate(BaseModel):
    campaign_id: str
    content: str = ""
    dice_system: str = "narrative"
    critical_enabled: bool = True
    hidden_rolls_enabled: bool = False
    difficulty_classes: str = "Easy:5, Medium:10, Hard:15, Extreme:20"

class RulesUpdate(BaseModel):
    content: Optional[str] = None
    dice_system: Optional[str] = None
    critical_enabled: Optional[bool] = None
    hidden_rolls_enabled: Optional[bool] = None
    difficulty_classes: Optional[str] = None

class ChannelConfigCreate(BaseModel):
    campaign_id: str
    guild_id: str
    channel_id: str
    channel_name: str = ""
    mode: str = "ic"

class ChannelConfigUpdate(BaseModel):
    mode: Optional[str] = None
    channel_name: Optional[str] = None

class QuestCreate(BaseModel):
    campaign_id: str
    title: str
    description: str = ""
    status: str = "active"
    objectives: List[str] = []

class QuestUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    objectives: Optional[List[str]] = None

class NarrateRequest(BaseModel):
    campaign_id: str
    action: str
    channel_id: str = ""

class NPCSpeakRequest(BaseModel):
    campaign_id: str
    npc_name: str
    dialogue_or_intent: str

class RollRequest(BaseModel):
    campaign_id: str
    dice_expression: str
    context: str = ""

class CheckRequest(BaseModel):
    campaign_id: str
    difficulty: str
    context: str

class ResetSessionRequest(BaseModel):
    campaign_id: str

class RecapRequest(BaseModel):
    campaign_id: str

class PlayerCharacterCreate(BaseModel):
    campaign_id: str
    discord_user_id: str = ""
    character_name: str
    status: str = "active"
    short_description: str = ""
    appearance: str = ""
    personality_traits: str = ""
    background: str = ""
    goals: str = ""
    fears: str = ""
    strengths: str = ""
    weaknesses: str = ""
    skills: str = ""
    injuries_conditions: str = ""
    inventory: str = ""
    faction_ties: str = ""
    relationship_notes: str = ""
    gm_secrets: str = ""
    public_knowledge: str = ""
    private_knowledge: str = ""
    current_location: str = ""
    reputation: str = ""
    obligations_notes: str = ""

class PlayerCharacterUpdate(BaseModel):
    character_name: Optional[str] = None
    discord_user_id: Optional[str] = None
    status: Optional[str] = None
    short_description: Optional[str] = None
    appearance: Optional[str] = None
    personality_traits: Optional[str] = None
    background: Optional[str] = None
    goals: Optional[str] = None
    fears: Optional[str] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    skills: Optional[str] = None
    injuries_conditions: Optional[str] = None
    inventory: Optional[str] = None
    faction_ties: Optional[str] = None
    relationship_notes: Optional[str] = None
    gm_secrets: Optional[str] = None
    public_knowledge: Optional[str] = None
    private_knowledge: Optional[str] = None
    current_location: Optional[str] = None
    reputation: Optional[str] = None
    obligations_notes: Optional[str] = None

class AllowedPlayerCreate(BaseModel):
    campaign_id: str
    discord_user_id: str
    discord_username: str = ""

class MessageDrivenRequest(BaseModel):
    campaign_id: str
    player_discord_id: str
    player_message: str
    channel_id: str = ""

class CampaignGenerateRequest(BaseModel):
    prompt: str

class CharacterQuestionsRequest(BaseModel):
    campaign_id: str

class ConfirmCharStepRequest(BaseModel):
    campaign_id: str
    field: str
    answer: str
    accumulated: dict = {}

class RelationshipRequest(BaseModel):
    campaign_id: str
    pc1_data: dict
    pc2_data: dict

class OpeningSceneRequest(BaseModel):
    campaign_id: str

class CharacterChangeRequest(BaseModel):
    campaign_id: str
    changes: List[str]
    source: str = ""

class MemoryEventCreate(BaseModel):
    campaign_id: str
    event_type: str  # injury, item_lost, item_gained, clue, faction_change, trust_change, oath, debt, damage, secret, relationship, threat, status
    subject: str
    detail: str
    visibility: str = "public"  # gm_only, character_specific, public
    related_pc: str = ""
    related_npc: str = ""

class SceneMemoryUpdate(BaseModel):
    campaign_id: str
    location: str = ""
    summary: str = ""
    present_pcs: List[str] = []
    present_npcs: List[str] = []
    immediate_danger: str = ""
    tension_level: int = 1
    current_objectives: List[str] = []
    unresolved_actions: List[str] = []
    atmosphere: str = ""
    time_of_day: str = ""

class RelationshipCreate(BaseModel):
    campaign_id: str
    entity_a: str
    entity_a_type: str = "pc"  # pc, npc, faction
    entity_b: str
    entity_b_type: str = "npc"
    relationship_type: str = "neutral"  # trust, hostility, debt, oath, family, rivalry, alliance
    value: int = 0  # -100 to 100
    notes: str = ""

class KnowledgeCreate(BaseModel):
    campaign_id: str
    content: str
    visibility: str = "public"  # gm_only, character_specific, public
    character_specific_to: str = ""
    category: str = ""  # clue, secret, lore, discovery
    source: str = ""

class SmartContextRequest(BaseModel):
    campaign_id: str
    player_discord_id: str = ""
    current_message: str = ""

class SceneResponseRequest(BaseModel):
    campaign_id: str
    channel_id: str = ""
    player_actions: List[dict]  # [{discord_id, pc_name, message}]

class AutoSummarizeRequest(BaseModel):
    campaign_id: str

# ── Helper ──

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def new_id():
    return str(uuid.uuid4())

async def build_smart_context(campaign_id: str, player_discord_id: str = ""):
    """Build focused context for GM instead of raw chat history."""
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not campaign:
        return None

    # Scene memory (short-term)
    scene_mem = await db.scene_memory.find_one({"campaign_id": campaign_id, "is_active": True}, {"_id": 0})

    # Active PCs
    pcs = await db.player_characters.find({"campaign_id": campaign_id, "status": "active"}, {"_id": 0}).to_list(10)
    active_pc = next((p for p in pcs if p.get("discord_user_id") == player_discord_id), None) if player_discord_id else None

    # NPCs present in scene, or all if no scene memory
    present_npc_names = scene_mem.get("present_npcs", []) if scene_mem else []
    if present_npc_names:
        npcs = await db.npcs.find({"campaign_id": campaign_id, "name": {"$in": present_npc_names}}, {"_id": 0}).to_list(20)
    else:
        npcs = await db.npcs.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(20)

    # Active scene from scenes collection (fallback if no scene_memory)
    scene = await db.scenes.find_one({"campaign_id": campaign_id, "is_active": True}, {"_id": 0}) if not scene_mem else None

    # Recent structured memory events (unresolved first, then recent)
    unresolved = await db.memory_events.find(
        {"campaign_id": campaign_id, "resolved": False}, {"_id": 0}
    ).sort("timestamp", -1).to_list(25)

    recent_events = await db.events.find(
        {"campaign_id": campaign_id}, {"_id": 0}
    ).sort("timestamp", -1).to_list(10)

    # Relationships involving PCs
    pc_names = [p.get("character_name", "") for p in pcs]
    relationships = await db.relationship_map.find(
        {"campaign_id": campaign_id, "$or": [{"entity_a": {"$in": pc_names}}, {"entity_b": {"$in": pc_names}}]}, {"_id": 0}
    ).to_list(50) if pc_names else []

    # Location-specific lore
    loc = (scene_mem or {}).get("location", "") or (scene or {}).get("location", "")
    lore = []
    if loc:
        lore = await db.lore_entries.find(
            {"campaign_id": campaign_id, "$or": [
                {"title": {"$regex": loc, "$options": "i"}},
                {"content": {"$regex": loc, "$options": "i"}}
            ]}, {"_id": 0}
        ).to_list(5)

    # GM-only knowledge
    gm_knowledge = await db.knowledge_store.find(
        {"campaign_id": campaign_id, "visibility": "gm_only"}, {"_id": 0}
    ).to_list(20)

    # Public knowledge
    public_knowledge = await db.knowledge_store.find(
        {"campaign_id": campaign_id, "visibility": "public"}, {"_id": 0}
    ).to_list(15)

    # Character-specific knowledge for active PC
    pc_knowledge = []
    if active_pc:
        pc_knowledge = await db.knowledge_store.find(
            {"campaign_id": campaign_id, "visibility": "character_specific", "character_specific_to": active_pc.get("character_name", "")}, {"_id": 0}
        ).to_list(10)

    # Recent scene summaries (last 3)
    summaries = await db.recaps.find(
        {"campaign_id": campaign_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(3)

    # Minimal recent chat for immediate conversational flow
    chat = await db.chat_history.find(
        {"campaign_id": campaign_id}, {"_id": 0}
    ).sort("timestamp", -1).to_list(6)

    return {
        "campaign": campaign,
        "scene_memory": scene_mem,
        "scene": scene,
        "pcs": pcs,
        "active_pc": active_pc,
        "npcs": npcs,
        "unresolved_events": unresolved,
        "recent_events": recent_events[::-1],
        "relationships": relationships,
        "lore": lore,
        "gm_knowledge": gm_knowledge,
        "public_knowledge": public_knowledge,
        "pc_knowledge": pc_knowledge,
        "summaries": summaries[::-1],
        "recent_chat": chat[::-1],
    }

# ── Campaign Routes ──

@api_router.get("/campaigns")
async def list_campaigns():
    return await db.campaigns.find({}, {"_id": 0}).to_list(100)

@api_router.get("/campaigns/active")
async def get_active_campaign():
    campaign = await db.campaigns.find_one({"is_active": True}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "No active campaign. Create one first.")
    return campaign

@api_router.post("/campaigns")
async def create_campaign(data: CampaignCreate):
    await db.campaigns.update_many({}, {"$set": {"is_active": False}})
    doc = {"id": new_id(), "name": data.name, "world_summary": data.world_summary, "tone": data.tone, "is_active": True, "auto_create_channels": False, "created_at": now_iso(), "updated_at": now_iso()}
    await db.campaigns.insert_one(doc)
    doc.pop("_id", None)
    rules = {"id": new_id(), "campaign_id": doc["id"], "content": "", "dice_system": "narrative", "critical_enabled": True, "hidden_rolls_enabled": False, "difficulty_classes": "Easy:5, Medium:10, Hard:15, Extreme:20", "created_at": now_iso(), "updated_at": now_iso()}
    await db.rules.insert_one(rules)
    return doc

@api_router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    c = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Campaign not found")
    return c

@api_router.put("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: str, data: CampaignUpdate):
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    update["updated_at"] = now_iso()
    if update.get("is_active"):
        await db.campaigns.update_many({}, {"$set": {"is_active": False}})
    result = await db.campaigns.update_one({"id": campaign_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Campaign not found")
    return await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})

@api_router.delete("/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: str):
    await db.campaigns.delete_one({"id": campaign_id})
    for col_name in ["npcs", "lore_entries", "scenes", "events", "recaps", "rules", "quests", "chat_history", "channel_configs", "player_characters", "allowed_players"]:
        await db[col_name].delete_many({"campaign_id": campaign_id})
    return {"status": "deleted"}

# ── NPC Routes ──

@api_router.get("/npcs")
async def list_npcs(campaign_id: str = Query(...)):
    return await db.npcs.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(500)

@api_router.post("/npcs")
async def create_npc(data: NPCCreate):
    doc = data.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = now_iso()
    doc["updated_at"] = now_iso()
    await db.npcs.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.put("/npcs/{npc_id}")
async def update_npc(npc_id: str, data: NPCUpdate):
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    update["updated_at"] = now_iso()
    result = await db.npcs.update_one({"id": npc_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "NPC not found")
    return await db.npcs.find_one({"id": npc_id}, {"_id": 0})

@api_router.delete("/npcs/{npc_id}")
async def delete_npc(npc_id: str):
    await db.npcs.delete_one({"id": npc_id})
    return {"status": "deleted"}

# ── Lore Routes ──

@api_router.get("/lore")
async def list_lore(campaign_id: str = Query(...)):
    return await db.lore_entries.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(500)

@api_router.post("/lore")
async def create_lore(data: LoreCreate):
    doc = data.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = now_iso()
    await db.lore_entries.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.put("/lore/{lore_id}")
async def update_lore(lore_id: str, data: LoreUpdate):
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    result = await db.lore_entries.update_one({"id": lore_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Lore entry not found")
    return await db.lore_entries.find_one({"id": lore_id}, {"_id": 0})

@api_router.delete("/lore/{lore_id}")
async def delete_lore(lore_id: str):
    await db.lore_entries.delete_one({"id": lore_id})
    return {"status": "deleted"}

# ── Scene Routes ──

@api_router.get("/scenes/active")
async def get_active_scene(campaign_id: str = Query(...)):
    scene = await db.scenes.find_one({"campaign_id": campaign_id, "is_active": True}, {"_id": 0})
    if not scene:
        return None
    return scene

@api_router.get("/scenes")
async def list_scenes(campaign_id: str = Query(...)):
    return await db.scenes.find({"campaign_id": campaign_id}, {"_id": 0}).sort("created_at", -1).to_list(100)

@api_router.post("/scenes")
async def create_scene(data: SceneCreate):
    await db.scenes.update_many({"campaign_id": data.campaign_id}, {"$set": {"is_active": False}})
    doc = data.model_dump()
    doc["id"] = new_id()
    doc["is_active"] = True
    doc["created_at"] = now_iso()
    await db.scenes.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.put("/scenes/{scene_id}")
async def update_scene(scene_id: str, data: SceneUpdate):
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    if update.get("is_active"):
        scene = await db.scenes.find_one({"id": scene_id}, {"_id": 0})
        if scene:
            await db.scenes.update_many({"campaign_id": scene["campaign_id"]}, {"$set": {"is_active": False}})
    result = await db.scenes.update_one({"id": scene_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Scene not found")
    return await db.scenes.find_one({"id": scene_id}, {"_id": 0})

# ── Event Routes ──

@api_router.get("/events")
async def list_events(campaign_id: str = Query(...), limit: int = 50):
    return await db.events.find({"campaign_id": campaign_id}, {"_id": 0}).sort("timestamp", -1).to_list(limit)

@api_router.post("/events")
async def create_event(data: EventCreate):
    doc = data.model_dump()
    doc["id"] = new_id()
    doc["timestamp"] = now_iso()
    await db.events.insert_one(doc)
    doc.pop("_id", None)
    return doc

# ── Recap Routes ──

@api_router.get("/recaps")
async def list_recaps(campaign_id: str = Query(...)):
    return await db.recaps.find({"campaign_id": campaign_id}, {"_id": 0}).sort("created_at", -1).to_list(100)

@api_router.post("/recaps")
async def create_recap(campaign_id: str = "", summary: str = "", body: dict = None):
    doc = {"id": new_id(), "campaign_id": campaign_id, "summary": summary, "created_at": now_iso()}
    if body:
        doc.update(body)
    await db.recaps.insert_one(doc)
    doc.pop("_id", None)
    return doc

# ── Rules Routes ──

@api_router.get("/rules")
async def get_rules(campaign_id: str = Query(...)):
    rules = await db.rules.find_one({"campaign_id": campaign_id}, {"_id": 0})
    if not rules:
        return {"campaign_id": campaign_id, "content": "", "dice_system": "narrative", "critical_enabled": True, "hidden_rolls_enabled": False, "difficulty_classes": "Easy:5, Medium:10, Hard:15, Extreme:20"}
    return rules

@api_router.put("/rules/{rules_id}")
async def update_rules(rules_id: str, data: RulesUpdate):
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    update["updated_at"] = now_iso()
    result = await db.rules.update_one({"id": rules_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Rules not found")
    return await db.rules.find_one({"id": rules_id}, {"_id": 0})

@api_router.post("/rules")
async def create_rules(data: RulesCreate):
    doc = data.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = now_iso()
    doc["updated_at"] = now_iso()
    await db.rules.insert_one(doc)
    doc.pop("_id", None)
    return doc

# ── Channel Config Routes ──

@api_router.get("/channels")
async def list_channels(guild_id: str = Query(None), campaign_id: str = Query(None)):
    query = {}
    if guild_id:
        query["guild_id"] = guild_id
    if campaign_id:
        query["campaign_id"] = campaign_id
    return await db.channel_configs.find(query, {"_id": 0}).to_list(100)

@api_router.post("/channels")
async def create_channel(data: ChannelConfigCreate):
    existing = await db.channel_configs.find_one({"channel_id": data.channel_id, "campaign_id": data.campaign_id})
    if existing:
        await db.channel_configs.update_one({"channel_id": data.channel_id, "campaign_id": data.campaign_id}, {"$set": {"mode": data.mode, "channel_name": data.channel_name}})
        return await db.channel_configs.find_one({"channel_id": data.channel_id, "campaign_id": data.campaign_id}, {"_id": 0})
    doc = data.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = now_iso()
    await db.channel_configs.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.put("/channels/{config_id}")
async def update_channel(config_id: str, data: ChannelConfigUpdate):
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    result = await db.channel_configs.update_one({"id": config_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Channel config not found")
    return await db.channel_configs.find_one({"id": config_id}, {"_id": 0})

@api_router.delete("/channels/{config_id}")
async def delete_channel(config_id: str):
    await db.channel_configs.delete_one({"id": config_id})
    return {"status": "deleted"}

# ── Quest Routes ──

@api_router.get("/quests")
async def list_quests(campaign_id: str = Query(...)):
    return await db.quests.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(200)

@api_router.post("/quests")
async def create_quest(data: QuestCreate):
    doc = data.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = now_iso()
    await db.quests.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.put("/quests/{quest_id}")
async def update_quest(quest_id: str, data: QuestUpdate):
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    result = await db.quests.update_one({"id": quest_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Quest not found")
    return await db.quests.find_one({"id": quest_id}, {"_id": 0})

@api_router.delete("/quests/{quest_id}")
async def delete_quest(quest_id: str):
    await db.quests.delete_one({"id": quest_id})
    return {"status": "deleted"}

# ── GM Engine Routes ──

@api_router.post("/gm/narrate")
async def gm_narrate(data: NarrateRequest):
    campaign = await db.campaigns.find_one({"id": data.campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    scene = await db.scenes.find_one({"campaign_id": data.campaign_id, "is_active": True}, {"_id": 0})
    npcs = await db.npcs.find({"campaign_id": data.campaign_id}, {"_id": 0}).to_list(100)
    recent_events = await db.events.find({"campaign_id": data.campaign_id}, {"_id": 0}).sort("timestamp", -1).to_list(20)
    chat_history = await db.chat_history.find({"campaign_id": data.campaign_id}, {"_id": 0}).sort("timestamp", -1).to_list(20)
    response = await gm.narrate(campaign, scene, npcs, recent_events[::-1], data.action, chat_history[::-1])
    ts = now_iso()
    await db.chat_history.insert_one({"id": new_id(), "campaign_id": data.campaign_id, "role": "user", "content": data.action, "timestamp": ts})
    await db.chat_history.insert_one({"id": new_id(), "campaign_id": data.campaign_id, "role": "assistant", "content": response, "timestamp": ts})
    await db.events.insert_one({"id": new_id(), "campaign_id": data.campaign_id, "event_type": "action", "summary": data.action[:200], "details": response[:500], "timestamp": ts})
    return {"narration": response}

@api_router.post("/gm/npc-speak")
async def gm_npc_speak(data: NPCSpeakRequest):
    campaign = await db.campaigns.find_one({"id": data.campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    npc = await db.npcs.find_one({"campaign_id": data.campaign_id, "name": {"$regex": f"^{data.npc_name}$", "$options": "i"}}, {"_id": 0})
    if not npc:
        raise HTTPException(404, f"NPC '{data.npc_name}' not found in this campaign")
    scene = await db.scenes.find_one({"campaign_id": data.campaign_id, "is_active": True}, {"_id": 0})
    recent_events = await db.events.find({"campaign_id": data.campaign_id}, {"_id": 0}).sort("timestamp", -1).to_list(10)
    chat_history = await db.chat_history.find({"campaign_id": data.campaign_id}, {"_id": 0}).sort("timestamp", -1).to_list(10)
    response = await gm.npc_speak(campaign, npc, scene, recent_events[::-1], data.dialogue_or_intent, chat_history[::-1])
    ts = now_iso()
    await db.chat_history.insert_one({"id": new_id(), "campaign_id": data.campaign_id, "role": "user", "content": f"[To {npc['name']}] {data.dialogue_or_intent}", "timestamp": ts})
    await db.chat_history.insert_one({"id": new_id(), "campaign_id": data.campaign_id, "role": "assistant", "content": f"[{npc['name']}] {response}", "timestamp": ts})
    await db.events.insert_one({"id": new_id(), "campaign_id": data.campaign_id, "event_type": "npc_interaction", "summary": f"{npc['name']}: {data.dialogue_or_intent[:100]}", "details": response[:500], "timestamp": ts})
    return {"npc_name": npc["name"], "response": response}

@api_router.post("/gm/roll")
async def gm_roll(data: RollRequest):
    try:
        result = parse_and_roll(data.dice_expression)
    except ValueError as e:
        raise HTTPException(400, str(e))
    formatted = format_roll_result(result)
    if data.campaign_id:
        ts = now_iso()
        summary = f"Roll: {data.dice_expression} = {result['total']}"
        if data.context:
            summary += f" ({data.context})"
        await db.events.insert_one({"id": new_id(), "campaign_id": data.campaign_id, "event_type": "roll", "summary": summary, "details": formatted, "timestamp": ts})
    return {"result": result, "formatted": formatted}

@api_router.post("/gm/check")
async def gm_check(data: CheckRequest):
    campaign = await db.campaigns.find_one({"id": data.campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    rules = await db.rules.find_one({"campaign_id": data.campaign_id}, {"_id": 0})
    dc_map = {}
    if rules:
        for pair in rules.get("difficulty_classes", "").split(","):
            pair = pair.strip()
            if ":" in pair:
                name, val = pair.split(":", 1)
                dc_map[name.strip().lower()] = int(val.strip())
    dc = dc_map.get(data.difficulty.lower(), 10)
    roll_result = parse_and_roll("1d20")
    passed = roll_result["total"] >= dc
    formatted = format_roll_result(roll_result)
    scene = await db.scenes.find_one({"campaign_id": data.campaign_id, "is_active": True}, {"_id": 0})
    narrative = await gm.resolve_check(campaign, scene, roll_result, f"{data.difficulty} (DC {dc})", data.context)
    ts = now_iso()
    await db.events.insert_one({"id": new_id(), "campaign_id": data.campaign_id, "event_type": "roll", "summary": f"Check ({data.difficulty}): {data.context} - {'PASS' if passed else 'FAIL'} ({roll_result['total']} vs DC {dc})", "details": narrative[:500], "timestamp": ts})
    return {"roll": formatted, "total": roll_result["total"], "dc": dc, "passed": passed, "is_critical": roll_result["is_critical"], "is_fumble": roll_result["is_fumble"], "narrative": narrative}

@api_router.get("/gm/scene-summary")
async def gm_scene_summary(campaign_id: str = Query(...)):
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    scene = await db.scenes.find_one({"campaign_id": campaign_id, "is_active": True}, {"_id": 0})
    if not scene:
        return {"summary": "No active scene. Use /scene in Discord or create one in the dashboard."}
    npcs = await db.npcs.find({"campaign_id": campaign_id, "name": {"$in": scene.get("important_npcs", [])}}, {"_id": 0}).to_list(20)
    return {"scene": scene, "npcs": npcs, "campaign_name": campaign["name"], "tone": campaign.get("tone", "realistic")}

@api_router.post("/gm/generate-recap")
async def gm_generate_recap(data: RecapRequest):
    campaign = await db.campaigns.find_one({"id": data.campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    events = await db.events.find({"campaign_id": data.campaign_id}, {"_id": 0}).sort("timestamp", -1).to_list(50)
    if not events:
        return {"recap": "No events recorded yet."}
    recap_text = await gm.generate_recap(campaign, events[::-1])
    doc = {"id": new_id(), "campaign_id": data.campaign_id, "summary": recap_text, "created_at": now_iso()}
    await db.recaps.insert_one(doc)
    doc.pop("_id", None)
    return {"recap": recap_text, "recap_doc": doc}

@api_router.post("/gm/reset-session")
async def gm_reset_session(data: ResetSessionRequest):
    await db.scenes.update_many({"campaign_id": data.campaign_id}, {"$set": {"is_active": False}})
    await db.chat_history.delete_many({"campaign_id": data.campaign_id})
    return {"status": "session_reset", "message": "Scene deactivated and chat history cleared. Campaign data preserved."}

# ── Export / Import ──

# ── Player Character Routes ──

@api_router.get("/player-characters")
async def list_player_characters(campaign_id: str = Query(...)):
    return await db.player_characters.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(100)

@api_router.get("/player-characters/active")
async def get_active_pcs(campaign_id: str = Query(...)):
    return await db.player_characters.find({"campaign_id": campaign_id, "status": "active"}, {"_id": 0}).to_list(20)

@api_router.post("/player-characters")
async def create_player_character(data: PlayerCharacterCreate):
    doc = data.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = now_iso()
    doc["updated_at"] = now_iso()
    await db.player_characters.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.put("/player-characters/{pc_id}")
async def update_player_character(pc_id: str, data: PlayerCharacterUpdate):
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    update["updated_at"] = now_iso()
    result = await db.player_characters.update_one({"id": pc_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Player character not found")
    return await db.player_characters.find_one({"id": pc_id}, {"_id": 0})

@api_router.delete("/player-characters/{pc_id}")
async def delete_player_character(pc_id: str):
    await db.player_characters.delete_one({"id": pc_id})
    return {"status": "deleted"}

# ── Allowed Players Routes ──

@api_router.get("/allowed-players")
async def list_allowed_players(campaign_id: str = Query(...)):
    return await db.allowed_players.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(100)

@api_router.post("/allowed-players")
async def add_allowed_player(data: AllowedPlayerCreate):
    existing = await db.allowed_players.find_one({"campaign_id": data.campaign_id, "discord_user_id": data.discord_user_id})
    if existing:
        return await db.allowed_players.find_one({"campaign_id": data.campaign_id, "discord_user_id": data.discord_user_id}, {"_id": 0})
    doc = data.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = now_iso()
    await db.allowed_players.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.delete("/allowed-players/{player_id}")
async def remove_allowed_player(player_id: str):
    await db.allowed_players.delete_one({"id": player_id})
    return {"status": "deleted"}

# ── Message-Driven GM ──

@api_router.post("/gm/message-driven")
async def gm_message_driven(data: MessageDrivenRequest):
    campaign = await db.campaigns.find_one({"id": data.campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    # Build smart context (structured memory retrieval)
    smart_ctx = await build_smart_context(data.campaign_id, data.player_discord_id)
    response = await gm.message_driven_response(
        campaign, None, [], [], smart_ctx.get("pcs", []),
        data.player_message, smart_ctx.get("active_pc"), [],
        smart_ctx=smart_ctx
    )
    ts = now_iso()
    pc_name = (smart_ctx.get("active_pc") or {}).get('character_name', data.player_discord_id)
    await db.chat_history.insert_one({"id": new_id(), "campaign_id": data.campaign_id, "role": "user", "content": f"[{pc_name}] {data.player_message}", "timestamp": ts})
    if response:
        await db.chat_history.insert_one({"id": new_id(), "campaign_id": data.campaign_id, "role": "assistant", "content": response, "timestamp": ts})
        await db.events.insert_one({"id": new_id(), "campaign_id": data.campaign_id, "event_type": "action", "summary": f"{pc_name}: {data.player_message[:150]}", "details": response[:500], "timestamp": ts})
    return {"response": response}

# ── Scene Response (combined turn-based) ──

@api_router.post("/gm/scene-response")
async def gm_scene_response(data: SceneResponseRequest):
    campaign = await db.campaigns.find_one({"id": data.campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    first_player = data.player_actions[0]["discord_id"] if data.player_actions else ""
    smart_ctx = await build_smart_context(data.campaign_id, first_player)
    response = await gm.scene_turn_response(campaign, data.player_actions, smart_ctx)
    ts = now_iso()
    for action in data.player_actions:
        await db.chat_history.insert_one({"id": new_id(), "campaign_id": data.campaign_id, "role": "user", "content": f"[{action.get('pc_name','?')}] {action.get('message','')}", "timestamp": ts})
    if response:
        await db.chat_history.insert_one({"id": new_id(), "campaign_id": data.campaign_id, "role": "assistant", "content": response, "timestamp": ts})
        summary = " / ".join([f"{a.get('pc_name','?')}: {a.get('message','')[:60]}" for a in data.player_actions])
        await db.events.insert_one({"id": new_id(), "campaign_id": data.campaign_id, "event_type": "action", "summary": summary[:200], "details": response[:500], "timestamp": ts})
    return {"response": response}

# ── Campaign Generation ──

@api_router.post("/gm/generate-campaign")
async def gm_generate_campaign(data: CampaignGenerateRequest):
    result = await gm.generate_campaign(data.prompt)
    return result

@api_router.post("/gm/generate-character-questions")
async def gm_generate_character_questions(data: CharacterQuestionsRequest):
    campaign = await db.campaigns.find_one({"id": data.campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    questions = await gm.generate_character_questions(campaign)
    return {"questions": questions}

@api_router.post("/gm/confirm-character-step")
async def gm_confirm_character_step(data: ConfirmCharStepRequest):
    campaign = await db.campaigns.find_one({"id": data.campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    confirmation = await gm.confirm_character_step(campaign, data.field, data.answer, data.accumulated)
    return {"confirmation": confirmation}

@api_router.post("/gm/generate-relationship")
async def gm_generate_relationship(data: RelationshipRequest):
    campaign = await db.campaigns.find_one({"id": data.campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    result = await gm.generate_relationship(campaign, data.pc1_data, data.pc2_data)
    return {"relationship": result}

@api_router.post("/gm/generate-opening-scene")
async def gm_generate_opening_scene(data: OpeningSceneRequest):
    campaign = await db.campaigns.find_one({"id": data.campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    pcs = await db.player_characters.find({"campaign_id": data.campaign_id, "status": "active"}, {"_id": 0}).to_list(10)
    scene_text = await gm.generate_opening_scene(campaign, pcs)
    return {"scene": scene_text}

# ── Character Change Tracking ──

# ── Memory System Routes ──

@api_router.post("/memory/events")
async def create_memory_event(data: MemoryEventCreate):
    doc = data.model_dump()
    doc["id"] = new_id()
    doc["timestamp"] = now_iso()
    doc["resolved"] = False
    await db.memory_events.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/memory/events")
async def list_memory_events(campaign_id: str = Query(...), event_type: str = None, resolved: bool = None, limit: int = 50):
    q = {"campaign_id": campaign_id}
    if event_type: q["event_type"] = event_type
    if resolved is not None: q["resolved"] = resolved
    return await db.memory_events.find(q, {"_id": 0}).sort("timestamp", -1).to_list(limit)

@api_router.put("/memory/events/{event_id}/resolve")
async def resolve_memory_event(event_id: str):
    await db.memory_events.update_one({"id": event_id}, {"$set": {"resolved": True, "resolved_at": now_iso()}})
    return await db.memory_events.find_one({"id": event_id}, {"_id": 0})

@api_router.get("/memory/scene-state")
async def get_scene_memory(campaign_id: str = Query(...)):
    mem = await db.scene_memory.find_one({"campaign_id": campaign_id, "is_active": True}, {"_id": 0})
    return mem or {"campaign_id": campaign_id, "is_active": False}

@api_router.put("/memory/scene-state")
async def update_scene_memory(data: SceneMemoryUpdate):
    update = {k: v for k, v in data.model_dump().items() if v}
    update["updated_at"] = now_iso()
    update["is_active"] = True
    existing = await db.scene_memory.find_one({"campaign_id": data.campaign_id, "is_active": True})
    if existing:
        await db.scene_memory.update_one({"campaign_id": data.campaign_id, "is_active": True}, {"$set": update})
    else:
        update["id"] = new_id()
        update["campaign_id"] = data.campaign_id
        update["created_at"] = now_iso()
        await db.scene_memory.insert_one(update)
    return await db.scene_memory.find_one({"campaign_id": data.campaign_id, "is_active": True}, {"_id": 0})

@api_router.post("/memory/relationships")
async def upsert_relationship(data: RelationshipCreate):
    existing = await db.relationship_map.find_one({
        "campaign_id": data.campaign_id,
        "$or": [
            {"entity_a": data.entity_a, "entity_b": data.entity_b},
            {"entity_a": data.entity_b, "entity_b": data.entity_a}
        ]
    })
    doc = data.model_dump()
    if existing:
        doc["updated_at"] = now_iso()
        await db.relationship_map.update_one({"_id": existing["_id"]}, {"$set": doc})
        return await db.relationship_map.find_one({"_id": existing["_id"]}, {"_id": 0})
    doc["id"] = new_id()
    doc["created_at"] = now_iso()
    await db.relationship_map.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/memory/relationships")
async def list_relationships(campaign_id: str = Query(...), entity: str = None):
    q = {"campaign_id": campaign_id}
    if entity: q["$or"] = [{"entity_a": entity}, {"entity_b": entity}]
    return await db.relationship_map.find(q, {"_id": 0}).to_list(100)

@api_router.post("/memory/knowledge")
async def add_knowledge(data: KnowledgeCreate):
    doc = data.model_dump()
    doc["id"] = new_id()
    doc["created_at"] = now_iso()
    await db.knowledge_store.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/memory/knowledge")
async def list_knowledge(campaign_id: str = Query(...), visibility: str = None, category: str = None):
    q = {"campaign_id": campaign_id}
    if visibility: q["visibility"] = visibility
    if category: q["category"] = category
    return await db.knowledge_store.find(q, {"_id": 0}).to_list(100)

@api_router.post("/memory/smart-context")
async def get_smart_context(data: SmartContextRequest):
    ctx = await build_smart_context(data.campaign_id, data.player_discord_id)
    if not ctx:
        raise HTTPException(404, "Campaign not found")
    formatted = gm.format_smart_context(ctx)
    return {"context": formatted, "stats": {
        "pcs": len(ctx["pcs"]), "npcs": len(ctx["npcs"]),
        "unresolved_events": len(ctx["unresolved_events"]),
        "relationships": len(ctx["relationships"]),
        "knowledge_entries": len(ctx["gm_knowledge"]) + len(ctx["public_knowledge"]),
        "summaries": len(ctx["summaries"])
    }}

@api_router.post("/memory/extract-events")
async def extract_events_from_narrative(campaign_id: str = "", narrative: str = "", body: dict = None):
    if body:
        campaign_id = body.get("campaign_id", campaign_id)
        narrative = body.get("narrative", narrative)
    if not narrative:
        raise HTTPException(400, "narrative required")
    extracted = await gm.extract_memory_events(narrative, campaign_id)
    stored = []
    for ev in extracted:
        doc = {
            "id": new_id(), "campaign_id": campaign_id,
            "event_type": ev.get("type", "status"), "subject": ev.get("subject", ""),
            "detail": ev.get("detail", ""), "visibility": ev.get("visibility", "public"),
            "resolved": False, "timestamp": now_iso()
        }
        await db.memory_events.insert_one(doc)
        doc.pop("_id", None)
        stored.append(doc)
    return {"extracted": len(stored), "events": stored}

@api_router.post("/memory/auto-summarize")
async def auto_summarize(data: AutoSummarizeRequest):
    campaign = await db.campaigns.find_one({"id": data.campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    events = await db.memory_events.find({"campaign_id": data.campaign_id}, {"_id": 0}).sort("timestamp", -1).to_list(30)
    pcs = await db.player_characters.find({"campaign_id": data.campaign_id, "status": "active"}, {"_id": 0}).to_list(10)
    if not events:
        return {"summary": "Keine Ereignisse zum Zusammenfassen."}
    result = await gm.auto_summarize_scene(campaign, events[::-1], pcs)
    doc = {"id": new_id(), "campaign_id": data.campaign_id, "summary": result.get("summary", str(result)), "structured": result, "created_at": now_iso()}
    await db.recaps.insert_one(doc)
    doc.pop("_id", None)
    return {"recap": doc, "structured": result}

@api_router.post("/memory/update-scene")
async def update_scene_from_narrative(campaign_id: str = "", narrative: str = "", body: dict = None):
    if body:
        campaign_id = body.get("campaign_id", campaign_id)
        narrative = body.get("narrative", narrative)
    scene_mem = await db.scene_memory.find_one({"campaign_id": campaign_id, "is_active": True}, {"_id": 0})
    updates = await gm.suggest_scene_update(narrative, scene_mem)
    if updates:
        updates["updated_at"] = now_iso()
        updates["is_active"] = True
        if scene_mem:
            await db.scene_memory.update_one({"campaign_id": campaign_id, "is_active": True}, {"$set": updates})
        else:
            updates["id"] = new_id()
            updates["campaign_id"] = campaign_id
            updates["created_at"] = now_iso()
            await db.scene_memory.insert_one(updates)
    return await db.scene_memory.find_one({"campaign_id": campaign_id, "is_active": True}, {"_id": 0}) or {}

# ── Character Change Tracking (legacy) ──

@api_router.post("/character-changes")
async def track_character_changes(data: CharacterChangeRequest):
    ts = now_iso()
    docs = []
    for change in data.changes:
        doc = {"id": new_id(), "campaign_id": data.campaign_id, "change": change, "source": data.source, "timestamp": ts, "applied": False}
        docs.append(doc)
    if docs:
        await db.character_changes.insert_many(docs)
        # Also log as events
        for change in data.changes:
            await db.events.insert_one({"id": new_id(), "campaign_id": data.campaign_id, "event_type": "character_change", "summary": change, "details": data.source, "timestamp": ts})
    return {"tracked": len(docs), "changes": data.changes}

@api_router.get("/character-changes")
async def list_character_changes(campaign_id: str = Query(...), limit: int = 50):
    return await db.character_changes.find({"campaign_id": campaign_id}, {"_id": 0}).sort("timestamp", -1).to_list(limit)

@api_router.put("/character-changes/{change_id}/apply")
async def apply_character_change(change_id: str):
    result = await db.character_changes.update_one({"id": change_id}, {"$set": {"applied": True, "applied_at": now_iso()}})
    if result.matched_count == 0:
        raise HTTPException(404, "Change not found")
    return await db.character_changes.find_one({"id": change_id}, {"_id": 0})

# ── Export / Import (updated) ──

@api_router.get("/export/{campaign_id}")
async def export_campaign(campaign_id: str):
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    data = {"campaign": campaign}
    for col_name in ["npcs", "lore_entries", "scenes", "events", "recaps", "rules", "quests", "channel_configs", "player_characters", "allowed_players"]:
        data[col_name] = await db[col_name].find({"campaign_id": campaign_id}, {"_id": 0}).to_list(1000)
    return data

@api_router.post("/import")
async def import_campaign(data: dict):
    campaign = data.get("campaign")
    if not campaign:
        raise HTTPException(400, "Missing campaign data")
    campaign["id"] = new_id()
    campaign["is_active"] = True
    campaign["created_at"] = now_iso()
    await db.campaigns.update_many({}, {"$set": {"is_active": False}})
    await db.campaigns.insert_one(campaign)
    cid = campaign["id"]
    for col_name in ["npcs", "lore_entries", "scenes", "events", "recaps", "rules", "quests", "channel_configs", "player_characters", "allowed_players"]:
        items = data.get(col_name, [])
        for item in items:
            item["id"] = new_id()
            item["campaign_id"] = cid
            item.pop("_id", None)
        if items:
            await db[col_name].insert_many(items)
    return {"status": "imported", "campaign_id": cid}

# ── Bot Status ──

@api_router.get("/bot/status")
async def bot_status():
    campaign_count = await db.campaigns.count_documents({})
    npc_count = await db.npcs.count_documents({})
    event_count = await db.events.count_documents({})
    pc_count = await db.player_characters.count_documents({})
    active = await db.campaigns.find_one({"is_active": True}, {"_id": 0})
    return {"campaigns": campaign_count, "npcs": npc_count, "events": event_count, "player_characters": pc_count, "active_campaign": active}

@api_router.get("/")
async def root():
    return {"message": "GM Bot API running"}

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
