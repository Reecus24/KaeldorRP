"""Editable open-world definitions. IDs are save references, never display labels."""

WORLD_CONFIG = {
    "start_region": "millhaven", "random_creation": True,
    "base_success": 0.55, "chance_per_skill": 0.04,
    "min_success": 0.05, "max_success": 0.95,
    "report_limit": 60, "memory_turns": 24, "max_active_quests": 8,
    "max_foundings": 5, "dialogue_cooldown_seconds": 3,
    "max_pending_intents": 10,
}

WORLD_REGIONS = [
    {"id": "millhaven", "name": "Millhaven", "biome": "village", "x": 33, "y": 54,
     "description": "A mill turns beside the river. Farmers, apprentices and wanderers share its crowded square.",
     "connections": [{"to": "greenfields", "minutes": 4}, {"to": "ironwood", "minutes": 8}, {"to": "cinderforge", "minutes": 6}, {"to": "reedharbour", "minutes": 10}], "active": True},
    {"id": "greenfields", "name": "The Greenfields", "biome": "fields", "x": 19, "y": 77,
     "description": "Barley, muddy paths and scattered cottages. Honest work is always needed here.",
     "connections": [{"to": "millhaven", "minutes": 4}, {"to": "ironwood", "minutes": 7}], "active": True},
    {"id": "ironwood", "name": "Ironwood", "biome": "forest", "x": 17, "y": 27,
     "description": "Old trees conceal game trails and the Thornbound's hidden camp.",
     "connections": [{"to": "millhaven", "minutes": 8}, {"to": "greenfields", "minutes": 7}, {"to": "oldwatch", "minutes": 12}], "active": True},
    {"id": "cinderforge", "name": "Cinderforge", "biome": "forge", "x": 57, "y": 38,
     "description": "Hammer blows carry across the valley. Master smiths insist on practice before a maker's mark.",
     "connections": [{"to": "millhaven", "minutes": 6}, {"to": "oldwatch", "minutes": 9}, {"to": "reedharbour", "minutes": 8}], "active": True},
    {"id": "reedharbour", "name": "Reedharbour", "biome": "harbour", "x": 70, "y": 70,
     "description": "River barges carry grain and iron. At the shipyard, every hull begins as an apprentice's drawing.",
     "connections": [{"to": "millhaven", "minutes": 10}, {"to": "cinderforge", "minutes": 8}, {"to": "moonfen", "minutes": 11}], "active": True},
    {"id": "oldwatch", "name": "Oldwatch Keep", "biome": "keep", "x": 59, "y": 15,
     "description": "The Crownwardens train beneath an ancient watchtower. Discipline matters as much as courage.",
     "connections": [{"to": "ironwood", "minutes": 12}, {"to": "cinderforge", "minutes": 9}], "active": True},
    {"id": "moonfen", "name": "The Moonfen", "biome": "marsh", "x": 88, "y": 38,
     "description": "Silver herbs grow among drowned ruins. An old healer keeps a lantern lit for travellers.",
     "connections": [{"to": "reedharbour", "minutes": 11}], "active": True},
]

WORLD_SKILLS = [{"id": key, "name": name, "active": True} for key, name in [
    ("sales", "Bartering"), ("crafting", "Smithing"), ("street_smarts", "Skulduggery"),
    ("shipbuilding", "Shipbuilding"), ("medicine", "Herblore & Healing"), ("survival", "Woodcraft"),
    ("fitness", "Arms & Endurance"), ("management", "Stewardship"), ("cooking", "Cooking"),
    ("charisma", "Diplomacy"), ("technology", "Runecraft"), ("studying", "Scholarship"),
    ("finance", "Accounting"), ("driving", "Horsemanship"), ("creativity", "Artistry")]]

WORLD_PROFESSIONS = [
    {"id": "farmer", "name": "Farmer", "description": "Work the land. No formal apprenticeship required.", "requirements": {}, "active": True},
    {"id": "thief", "name": "Thief", "description": "A life learned in the streets, with consequences when a mark notices.", "requirements": {"skills": {"street_smarts": 2}}, "active": True},
    {"id": "merchant", "name": "Merchant", "description": "Know your prices, read a customer and build a trade house.", "requirements": {"skills": {"sales": 3}}, "active": True},
    {"id": "smith", "name": "Smith", "description": "Earn your maker's mark through supervised forge work.", "requirements": {"skills": {"crafting": 4}, "training": {"smithing": 8}}, "active": True},
    {"id": "shipwright", "name": "Shipwright", "description": "Learn hull construction before accepting a vessel commission.", "requirements": {"skills": {"shipbuilding": 4}, "training": {"shipbuilding": 10}}, "active": True},
    {"id": "healer", "name": "Healer", "description": "Supervised practice distinguishes a healer from a herb gatherer.", "requirements": {"skills": {"medicine": 4}, "training": {"medicine": 8}}, "active": True},
    {"id": "hunter", "name": "Hunter", "description": "Learn to track, forage and live beyond the walls.", "requirements": {"skills": {"survival": 3}}, "active": True},
]

def action(identifier, name, region, skill, difficulty, duration, gold, **extra):
    return {"id": identifier, "name": name, "description": name + ". The dice decide the result; practice improves your odds.",
            "regions": region, "skill": skill, "difficulty": difficulty, "duration_minutes": duration,
            "energy_cost": 3, "money_cost": 0, "cooldown_minutes": 1, "requirements": {}, "supplies": {},
            "outcomes": [
                {"id": "success", "name": "Success", "success": True, "weight": 3, "coins": [gold, gold + 4], "xp": 35, "effects": {}, "items": {}, "training": {}},
                {"id": "excellent", "name": "Exceptional work", "success": True, "weight": 1, "coins": [gold + 4, gold + 10], "xp": 50, "effects": {}, "items": {}, "training": {}},
                {"id": "setback", "name": "A setback", "success": False, "weight": 1, "coins": [0, 0], "xp": 15, "effects": {}, "items": {}, "training": {}},
            ], "active": True, **extra}

WORLD_ACTIONS = [
    action("field_work", "Help with the harvest", ["greenfields", "millhaven"], "fitness", 1, 10, 8),
    action("market_trade", "Trade at the market", ["millhaven", "reedharbour"], "sales", 2, 12, 12),
    action("practice_sleight", "Practice sleight of hand", ["ironwood", "millhaven"], "street_smarts", 1, 10, 0),
    action("pickpocket", "Pick a merchant's pocket", ["millhaven", "reedharbour"], "street_smarts", 5, 8, 28,
           requirements={"professions": ["thief"]}),
    action("gather_herbs", "Gather silverleaf herbs", ["moonfen", "ironwood"], "survival", 2, 12, 7),
    action("track_game", "Track wild game", ["ironwood"], "survival", 4, 20, 20),
    action("smith_lesson", "Train at the forge", ["cinderforge"], "crafting", 1, 60, 2, money_cost=8, teacher_id="brann"),
    action("hull_lesson", "Study hull construction", ["reedharbour"], "shipbuilding", 1, 90, 2, money_cost=10, teacher_id="elin"),
    action("healer_lesson", "Assist the healer", ["moonfen"], "medicine", 1, 60, 2, money_cost=8, teacher_id="ysra"),
    action("forge_blade", "Forge a commissioned blade", ["cinderforge"], "crafting", 5, 90, 60, requirements={"professions": ["smith"]}),
    action("build_skiff", "Build a river skiff", ["reedharbour"], "shipbuilding", 6, 180, 140, money_cost=35, requirements={"professions": ["shipwright"]}),
    action("treat_wounds", "Treat a villager's wounds", ["moonfen", "millhaven"], "medicine", 5, 45, 35, requirements={"professions": ["healer"]}),
    action("guard_drill", "Drill with the watch", ["oldwatch"], "fitness", 2, 30, 8),
    action("trade_contract", "Negotiate a caravan contract", ["millhaven", "reedharbour"], "sales", 6, 60, 55, requirements={"professions": ["merchant"]}),
]
for a in WORLD_ACTIONS:
    if a["id"] in ("forge_blade", "build_skiff", "trade_contract"):
        a["workshop_kind"] = {"forge_blade": "smithy", "build_skiff": "shipyard", "trade_contract": "business"}[a["id"]]
    if a["id"] in ("smith_lesson", "hull_lesson", "healer_lesson"):
        field = {"smith_lesson": "smithing", "hull_lesson": "shipbuilding", "healer_lesson": "medicine"}[a["id"]]
        for outcome in a["outcomes"]:
            outcome["training"] = {field: 1} if outcome["success"] else {}
            outcome["xp"] *= 3
    if a["id"] == "pickpocket":
        for outcome in a["outcomes"]:
            outcome["effects"] = {"criminal_suspicion": 3 if outcome["success"] else 18, "legal_reputation": -2 if outcome["success"] else -8}

WORLD_QUESTS = [
    {"id": "bread_for_winter", "name": "Bread for winter", "npc_id": "mira", "description": "Help the harvest twice, then return to Mira.", "action_id": "field_work", "target": 2, "success_only": False, "reward_coins": 30, "active": True},
    {"id": "first_sparks", "name": "The first sparks", "npc_id": "brann", "description": "Complete three successful forge lessons and report to Brann.", "action_id": "smith_lesson", "target": 3, "success_only": True, "reward_coins": 60, "active": True},
    {"id": "river_hands", "name": "Hands for the river", "npc_id": "elin", "description": "Complete three successful hull lessons and return to Elin.", "action_id": "hull_lesson", "target": 3, "success_only": True, "reward_coins": 75, "active": True},
    {"id": "quiet_feet", "name": "Quiet feet", "npc_id": "rook", "description": "Practice sleight of hand successfully three times. Rook will remember.", "action_id": "practice_sleight", "target": 3, "success_only": True, "reward_coins": 35, "active": True},
    {"id": "silverleaf", "name": "A basket of silverleaf", "npc_id": "ysra", "description": "Gather herbs successfully three times and return to Ysra.", "action_id": "gather_herbs", "target": 3, "success_only": True, "reward_coins": 45, "active": True},
]

WORLD_NPCS = [
    {"id": "mira", "name": "Mira Fenwick", "role": "Village steward", "home_region": "millhaven", "personality": "Warm, practical and protective of hungry families.", "goal": "Prepare the village for winter.", "greeting": "Every pair of hands matters here. What sort of life are you hoping to build?", "schedule": [], "active": True},
    {"id": "brann", "name": "Brann Ironwake", "role": "Master smith", "home_region": "cinderforge", "personality": "Gruff, patient with honest apprentices, intolerant of boasts.", "goal": "Train a reliable generation of smiths.", "greeting": "Show me patient hands before you show me a sword. The forge is open to learners.", "schedule": [], "active": True},
    {"id": "elin", "name": "Elin Reed", "role": "Master shipwright", "home_region": "reedharbour", "personality": "Inquisitive, precise and fond of river stories.", "goal": "Build vessels that bring their crews home.", "greeting": "A ship is a promise to everyone aboard. Start with its ribs and learn the river.", "schedule": [], "active": True},
    {"id": "rook", "name": "Rook", "role": "Thornbound scout", "home_region": "ironwood", "personality": "Wry and guarded; admires discretion more than cruelty.", "goal": "Find capable allies without attracting the watch.", "greeting": "Quiet hands, quieter footsteps. There is more than one way to earn your bread.", "schedule": [{"from_hour": 20, "to_hour": 23, "region": "millhaven"}], "active": True},
    {"id": "ysra", "name": "Ysra Willow", "role": "Fen healer", "home_region": "moonfen", "personality": "Gentle and observant; never treats uncertainty as knowledge.", "goal": "Teach careful healing and protect the fen.", "greeting": "Knowing what not to touch is the first lesson. Shall we begin with the herbs?", "schedule": [], "active": True},
    {"id": "tomas", "name": "Tomas Vale", "role": "Caravan broker", "home_region": "millhaven", "personality": "Sociable and shrewd, values kept promises.", "goal": "Open honest trade routes to the harbour.", "greeting": "A fair bargain brings a customer back. A clever bargain brings their neighbours too.", "schedule": [{"from_hour": 10, "to_hour": 16, "region": "reedharbour"}], "active": True},
]

WORLD_CHARTERS = [
    {"id": "fellowship", "name": "Independent faction", "kind": "faction", "cost": 150, "regions": [], "requirements": {}, "description": "Found a named fellowship, write its charter and invite other players.", "active": True},
    {"id": "trade_house", "name": "Trading house", "kind": "business", "cost": 400, "regions": ["millhaven", "reedharbour"], "requirements": {"professions": ["merchant"]}, "description": "Establish a home for your trading company and its members.", "active": True},
    {"id": "smithy", "name": "Independent smithy", "kind": "smithy", "cost": 650, "regions": ["cinderforge", "millhaven"], "requirements": {"professions": ["smith"]}, "description": "Put your name above a forge and take commissions together.", "active": True},
    {"id": "shipyard", "name": "River shipyard", "kind": "shipyard", "cost": 1000, "regions": ["reedharbour"], "requirements": {"professions": ["shipwright"]}, "description": "Open a yard for your own shipbuilding company.", "active": True},
]

WORLD_ORIGINS = [
    {"id": "peasant", "name": "Landless peasant", "description": "Raised among fields; no employment or qualifications.", "weight": 5, "coins": [45, 85], "age": [18, 35], "skills": {"fitness": [1, 3], "survival": [1, 2]}, "inventory": {"protein_bar": 3}, "active": True},
    {"id": "dockhand", "name": "Wandering dockhand", "description": "A river childhood, looking for a new beginning. No formal training.", "weight": 3, "coins": [35, 75], "age": [18, 40], "skills": {"fitness": [1, 2], "shipbuilding": [1, 2]}, "inventory": {"protein_bar": 3}, "active": True},
    {"id": "market_child", "name": "Market wanderer", "description": "Grew up around stalls and bargains; still has a trade to learn.", "weight": 2, "coins": [30, 70], "age": [18, 32], "skills": {"sales": [1, 2], "charisma": [1, 3]}, "inventory": {"protein_bar": 3}, "active": True},
]

WORLD_CONTENT = {name: (name, data) for name, data in [
    ("world_regions", WORLD_REGIONS), ("world_skills", WORLD_SKILLS), ("world_professions", WORLD_PROFESSIONS),
    ("world_actions", WORLD_ACTIONS), ("world_npcs", WORLD_NPCS), ("world_quests", WORLD_QUESTS),
    ("world_charters", WORLD_CHARTERS), ("world_origins", WORLD_ORIGINS),
]}

for origin in WORLD_ORIGINS:
    origin.update(stats={}, training={}, professions=[])

from world_life_content import LIFE_CONTENT
WORLD_CONTENT.update(LIFE_CONTENT)
