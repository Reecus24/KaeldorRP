"""The Ashen March: authored defaults. Legacy IDs keep existing saves compatible."""
from copy import deepcopy
import re

NAMES = {
    "jobs": ["Farmhand", "Market Stall Tender", "Scullion", "Mounted Courier", "Granary Keeper", "Guild Trader", "Town Crier", "Tavern Cook", "Smith's Apprentice", "Court Scribe", "Guild Steward", "Innkeeper", "Caravan Master"],
    "actions": ["Sleep by the Hearth", "Rest on a Bedroll", "Eat Pottage", "Cook a Hearth Meal", "Dine at the Inn", "Visit the Provisioner", "Train in the Yard", "Walk the Woodland Trail", "Listen to the Bard", "Pray at the Shrine", "Read a Chronicle", "Gather Firewood", "Carry a Sealed Letter", "Tend Mounts & Mend Harness", "Repair the Homestead"],
    "courses": ["Horsemanship", "Merchant's Apprenticeship", "Cook's Apprenticeship", "The Art of Barter", "Guild Stewardship", "Runecraft", "Keeping the Ledger", "Laws of the Crown", "Scholar of the Royal Academy"],
    "items": ["Emberroot Tonic", "Travel Bread", "Herbal Tea", "Willowbark Salve", "Healer's Satchel", "Dreamleaf Draught", "Linen Tunic", "Guildmaster's Robe", "Silver Signet", "Courier Seal", "Scribe's Kit", "Artisan's Toolbelt", "Padded Training Garb"],
    "housing": ["Village Hayloft", "Woodcutter's Cottage", "Timber Homestead", "Merchant's House", "Stone Manor", "Hilltop Keep"],
    "vehicles": ["Pack Donkey", "Moorland Pony", "Riding Horse", "Courser", "Ox Cart", "Merchant's Wagon", "Noble's Carriage"],
    "business_types": ["Provisioner's Stall", "Caravan Post", "Hearth & Hound Inn", "Weaver's Workshop", "Village Smithy", "Training Yard", "Falconer's Mews", "Runesmith's Workshop", "Launderer's Yard", "Steward's Hall"],
    "employee_roles": ["Stall Tender", "Cook", "Inn Servant", "Courier", "Yard Hand", "Smith", "Trader", "Steward", "Watchman", "Granary Hand", "Herald", "Ledger Keeper", "Weapons Tutor", "Falconer"],
    "locations": ["The Hearth & Hound", "Old Keep Training Yard", "The Guild Quarter", "Thornwood Crossroads", "Willowbank Meadow", "The Gilded Hall"],
    "city_shops": ["Millgate Provisions", "Sister Elowen's Apothecary", "The Loom & Needle", "The Scribe & Seal", "Ironroot Forge"],
    "job_sectors": ["Market & Guilds", "Inns & Kitchens", "Caravans & Stables", "Court & Scribes", "Fields & Workshops", "The Crown's Muster", "Service to the Realm"],
    "vehicle_categories": ["Pack Beasts", "Saddle Horses", "Carts & Wagons", "Noble Carriages"],
    "market_assets": ["Ironroot Iron", "Willowbank Grain", "Dawnwell Herbs", "Southroad Wool", "Moonstone", "Star Amber", "Wyrmglass", "Shadow Pearl"],
    "illegal_actions": ["Cut a Purse", "Fence Stolen Goods", "The Midnight Horse Race", "Evade the Baron's Tithe", "Smuggle through the Marsh", "Forge a Guild Writ", "Dice in the Cellar", "Bribe the Bailiff"],
}

# Only prose is transformed. Database keys, links, skills and save identifiers are stable.
PHRASES = {
    "Mercer Street": "Millgate", "Maya": "Mira", "city": "realm", "City": "Realm",
    "neighbourhood": "village", "Neighbourhood": "Village", "neighborhood": "village",
    "police": "watch", "Police": "Watch", "hospital": "infirmary", "Hospital": "Infirmary",
    "jail": "dungeon", "Jail": "Dungeon", "apartment": "cottage", "Apartment": "Cottage",
    "studio": "hayloft", "penthouse": "keep", "condo": "merchant house",
    "Smartphone": "Courier Seal", "smartphone": "courier seal", "Laptop": "Scribe's Kit", "laptop": "scribe's kit",
    "phone": "courier seal", "Phone": "Courier Seal", "electronics": "scribal supplies",
    "Electronic": "Scribal", "electronic": "scribal", "online": "guild", "Online": "Guild",
    "digital": "enchanted", "Digital": "Enchanted", "internet": "courier network",
    "TV": "the bard", "caffeine": "emberroot", "pharmacy": "apothecary", "Pharmacy": "Apothecary",
    "gym": "training yard", "Gym": "Training Yard", "coffee": "herbal tea", "Coffee": "Herbal Tea",
    "restaurant": "inn", "Restaurant": "Inn", "barista": "tavern cook", "Barista": "Tavern Cook",
    "mechanic": "smith", "Mechanic": "Smith", "office": "court", "Office": "Court",
    "corporate": "royal", "Corporate": "Royal", "company": "guild", "Company": "Guild",
    "vehicle": "mount or cart", "Vehicle": "Mount or Cart", "vehicles": "mounts & carts", "Vehicles": "Mounts & Carts",
    "car": "horse", "cars": "horses", "van": "wagon", "vans": "wagons", "scooter": "pony", "bicycle": "donkey",
    "driving": "riding", "Driving": "Riding", "driver": "courier", "Driver": "Courier",
    "fuel": "fodder", "Fuel": "Fodder", "insurance": "stable dues", "Insurance": "Stable Dues",
    "technology": "runecraft", "Technology": "Runecraft", "tech": "runes", "Tech": "Runes",
    "university": "royal academy", "University": "Royal Academy", "degree": "scholar's charter",
    "taxi": "carriage", "traffic": "crowded lanes", "delivery app": "courier guild",
    "computer": "writing desk", "software": "rune inscriptions", "Software": "Rune Inscriptions",
    "premium subscription": "guild charter", "subscription": "guild dues", "ads": "heralds",
    "advertising": "town criers", "Advertising": "Town Criers", "social media": "travelling bards",
    "viral": "renowned", "Viral": "Renowned", "reviews": "travellers' tales", "Reviews": "Travellers' Tales",
    "Call / Text": "Send a Letter", "call or text": "send a letter", "texts": "letters", "texted": "wrote to",
    "bank": "vault", "Bank": "Vault", "cash": "coin", "Cash": "Coin",
    "stock market": "commodity exchange", "crypto": "relic", "Crypto": "Relic",
    "Blue-chip conglomerate": "Iron mined in the northern hills", "Consumer tech": "Harvested grain",
    "biotech": "herbalism", "Biotech": "Herbalism", "blockchain": "relic trade",
    "Nightclub": "Noble Hall", "nightclub": "noble hall", "club": "hall",
    "business suit": "guild robe", "luxury watch": "silver signet", "watch": "signet",
}
# Single-word watch is intentionally excluded: the town watch must remain the watch.
PHRASES.pop("watch")
PHRASES.update({"SMS": "courier notes", "email": "sealed letters", "Emails": "Sealed Letters", "smartphones": "courier seals", "laptops": "scribal kits",
    "Electronics Store": "Scribe's stall", "Grocery Store": "Provisioner's stall", "painkillers": "herbal salves",
    "Hardware & Sports": "Forge & Armory", "Phones": "Scrolls", "cafes": "taverns", "restaurants": "inns",
    "poker": "dice", "truck": "wagon", "pink slips": "horse deeds", "downtown bar": "village tavern",
    "Marketing Spend": "Herald's Fee", "Spare Parts": "Iron Ingots", "Shop Supplies": "Charcoal",
    "Utilities": "Firewood & Water", "Inventory": "Runestones", "Shipping": "Courier Fees", "Pet Stock": "Young Falcons",
    "Wholesale Apparel": "Wool & Flax", "Cleaning Supplies": "Soap & Lye", "desktop": "writing desk"})
_pattern = re.compile(r"(?<![\w])(" + "|".join(re.escape(k) for k in sorted(PHRASES, key=len, reverse=True)) + r")(?![\w])")
TEXT_FIELDS = {"name", "title", "label", "desc", "description", "message", "result_text", "success_response", "failure_response", "text", "outcome", "summary"}

def prose(text):
    return _pattern.sub(lambda m: PHRASES[m.group()], text).replace("$", "¤")

def themed(value, field=None):
    if isinstance(value, dict):
        return {k: themed(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [themed(v, field) for v in value]
    return prose(value) if isinstance(value, str) and field in TEXT_FIELDS else value

def convert_defaults(content_map):
    """Return old/new defaults for a compare-before-write migration, never reset an Owner."""
    old = {kind: deepcopy(docs) for kind, (_, docs) in content_map.items()}
    for kind, (_, docs) in content_map.items():
        converted = themed(docs)
        for index, doc in enumerate(converted):
            if kind in NAMES:
                field = "title" if kind in {"jobs", "courses"} else "label" if kind == "employee_roles" else "name"
                doc[field] = NAMES[kind][index]
            if kind == "jobs":
                doc["description"] = ["Tend fields, gather the harvest and earn your first honest coins.", "Serve villagers and barter at the market.", "Chop vegetables and tend the inn's hearth.", "Carry letters and small cargo along the king's roads.", "Keep the harvest safe and account for the village stores.", "Trade cloth and provisions under a guild charter.", "Read proclamations and carry news between villages.", "Prepare hearty meals for weary travellers.", "Work the bellows and learn the craft of iron.", "Copy charters and keep the lord's accounts.", "Lead a guild hall and guide its apprentices.", "Oversee an inn, its cooks and its guests.", "Lead caravans across the realm."][index]
                doc["success_response"] = "Your petition for {title} was accepted — {wage} coins per hour. Accept to begin your service."
                if doc["tier"] > 1:
                    doc["requirements"]["min_age_days"] = {2: 7, 3: 21, 4: 45}[doc["tier"]]
                if index == 0:
                    doc["acceptance_base_chance"] = 1.0
            elif kind == "actions":
                if doc["id"] == "side_gig":
                    doc.update(requirements={}, duration_minutes=30, money_reward=8, money_cost=0, cooldown_minutes=60,
                               skill_xp={"crafting": 8}, result_text="You sell a bundle of dry firewood at Millgate.")
                if doc["id"] == "delivery_run":
                    doc["result_text"] = "The sealed letter reaches its recipient safely."
            elif kind == "housing":
                doc["desc"] = ["A dry corner of the village barn. A humble beginning.", "A small cottage at the edge of the wood.", "A hearth, a bed and a patch of land to call home.", "A comfortable home above the guild quarter.", "A stone manor with room for a growing household.", "A fortified keep overlooking the March."][index]
                if index == 0:
                    doc.update(rent_per_day=4, bills_per_day=1, sleep_quality=1)
            elif kind == "vehicles":
                doc["desc"] = "Carry goods and travel the realm. Fodder, stable dues and care are charged per game day."
            elif kind == "items":
                if doc["id"] == "smartphone":
                    doc["desc"] = "A wax seal recognised by the courier guild. Carry it to send courier notes; equip it to lift your spirits."
                elif doc["id"] == "laptop":
                    doc["desc"] = "Quill, ink and parchment. Carry it to write sealed letters; equip it to improve your work."
                elif doc["id"] == "luxury_watch":
                    doc["desc"] = "A silver signet ring. Equip it to raise your standing among the guilds."
            elif kind == "job_sectors" and doc["id"] == "sector_military":
                doc["realm_destination"] = "/realm"
                doc["desc"] = "Swear an oath to the Crownwardens. Enlist, train and earn rank through service and battles."
            elif kind == "business_types":
                products = ["Bread & Broth", "Caravan Delivery", "Hearth Supper", "Woven Tunic", "Forged Tools", "Training Lesson", "Trained Falcon", "Inscribed Rune", "Clean Linen", "Estate Charter"]
                doc["product"]["name"] = products[index]
                doc["desc"] = "Hire skilled hands, secure supplies and build a reputation for " + products[index].lower() + "."
                doc.setdefault("requirements", {})["min_age_days"] = 7 if index < 3 else 21
                for ingredient in doc.get("recipe", []):
                    # Ingredient IDs remain stable for already purchased materials.
                    ingredient["name"] = {"fuel": "Fodder", "packaging": "Sacks & Twine", "snacks": "Bread", "drinks": "Broth"}.get(ingredient["id"], prose(ingredient["name"]))
            elif kind == "market_assets":
                doc["desc"] = "A lot of " + doc["name"].lower() + ". Prices follow demand in the realm; resale value can fall."
                doc["symbol"] = ["IRON", "GRAIN", "HERB", "WOOL", "MOON", "AMBER", "WYRM", "PEARL"][index]
            elif kind == "character_backgrounds":
                doc["active"] = index == 0
                doc["label"] = "Unemployed Peasant" if index == 0 else "Legacy Origin"
                doc["desc"] = "No title, no master, no trade. Start with a place in the hayloft and earn your future."
                if index == 0:
                    doc.update(cash=80, bank=0, debt=0, skills={}, inventory={"protein_bar": 3})
        docs[:] = converted
    return old

REALM_RANKS = [
    {"id": "peasant", "name": "Peasant", "active": True, "min_days": 0, "min_level": 1, "min_deeds": 0, "description": "A name yet to be known. Work, learn and find your place."},
    {"id": "freeholder", "name": "Freeholder", "active": True, "min_days": 7, "min_level": 3, "min_deeds": 10, "description": "A week of honest effort opens skilled trades and your first workshop."},
    {"id": "burgher", "name": "Burgher", "active": True, "min_days": 21, "min_level": 6, "min_deeds": 35, "description": "A familiar face in the guild quarter. Court service becomes possible."},
    {"id": "notable", "name": "Notable", "active": True, "min_days": 45, "min_level": 10, "min_deeds": 80, "description": "Guilds and caravans seek your leadership."},
    {"id": "magnate", "name": "Magnate", "active": True, "min_days": 90, "min_level": 18, "min_deeds": 160, "description": "Your deeds have become part of the history of the March."},
]

FACTIONS = [
    {"id": "crown", "name": "The Crownwardens", "active": True, "motto": "Hold the road. Keep the oath.", "description": "Join the royal army. Train with the militia, defend travellers and rise through the ranks by service and victories.", "min_legal": 40, "join_cost": 0,
     "ranks": [{"name": n, "renown": r, "service_hours": h, "days": d} for n,r,h,d in [("Militia Recruit",0,0,0),("Man-at-Arms",60,6,7),("Sergeant",220,24,21),("Knight-Captain",600,70,45),("Marshal",1500,180,90)]]},
    {"id": "thorn", "name": "The Thornbound", "active": True, "motto": "No lord owns the forest.", "description": "Join the outlaw bands of Thornwood. Scout hidden trails, raid guarded caravans and earn a feared name. Raids draw the watch's attention.", "min_legal": 0, "join_cost": 0,
     "ranks": [{"name": n, "renown": r, "service_hours": h, "days": d} for n,r,h,d in [("Forest Runner",0,0,0),("Raider",60,6,7),("Outlaw Veteran",220,24,21),("Band Captain",600,70,45),("Thornlord",1500,180,90)]]},
]

def mission(identifier, name, faction, rank, minutes, power, gold, renown, damage, description, **extra):
    return {"id": identifier, "name": name, "active": True, "faction_id": faction, "min_rank": rank,
            "duration_minutes": minutes, "enemy_power": power, "gold": gold, "renown": renown, "xp": renown * 2,
            "win_damage": damage, "loss_damage": damage * 2, "energy_cost": 8, "fatigue_cost": 5,
            "min_health": 40, "cooldown_minutes": 60, "supplies": {}, "suspicion": 0,
            "legal_change": 0, "description": description, **extra}

EXPEDITIONS = [
    mission("yard_drill", "The First Sparring Lesson", None, 0, 15, 5, 2, 0, 2, "Learn to keep your guard against a wooden practice blade.", xp=10, min_health=20, cooldown_minutes=120),
    mission("wolf_trail", "Wolves at Willowbank", None, 0, 45, 16, 18, 0, 6, "Protect the village flocks from wolves in the old orchard.", xp=25, cooldown_minutes=180),
    mission("watch_road", "Watch the King's Road", "crown", 0, 60, 12, 18, 12, 4, "March with the militia and drive raiders from the toll road."),
    mission("escort", "Escort the Harvest Caravan", "crown", 1, 120, 30, 60, 25, 9, "Hold the line when brigands strike the harvest wagons.", supplies={"protein_bar": 1}),
    mission("border", "Defend the Border Tower", "crown", 2, 180, 50, 110, 40, 14, "Defend the northern tower against an ogre warband.", supplies={"protein_bar": 2}),
    mission("wyrm", "The Wyrm of Ashfall", "crown", 3, 240, 80, 240, 70, 23, "Lead the Crownwardens into the ruined keep where a wyrm has nested.", supplies={"protein_bar": 3}),
    mission("forest_scout", "Scout the Hidden Trails", "thorn", 0, 60, 12, 22, 12, 4, "Evade the watch and map a safe route into Thornwood.", suspicion=2, legal_change=-1),
    mission("caravan_raid", "Ambush the Toll Caravan", "thorn", 1, 120, 32, 85, 25, 10, "Outwit armed escorts and seize the baron's toll chest.", suspicion=6, legal_change=-3, supplies={"protein_bar": 1}),
    mission("prison_break", "Break the Iron Convoy", "thorn", 2, 180, 52, 140, 40, 15, "Free your captured companions from the sheriff's escort.", suspicion=8, legal_change=-4, supplies={"protein_bar": 2}),
    mission("shadow_vault", "The Baron's Cursed Vault", "thorn", 3, 240, 82, 280, 70, 24, "Face the baron's rune-bound guardians beneath his keep.", suspicion=12, legal_change=-6, supplies={"protein_bar": 3}),
]

COMBAT_ITEMS = [
    {"id": "rustic_spear", "name": "Ashwood Spear", "category": "gear", "slot": "weapon", "price": 70, "effects": {}, "equip_bonus": {}, "combat_power": 8, "combat_armor": 0, "desc": "A village spear. Equip it before an expedition for +8 power.", "store_type": "hardware"},
    {"id": "iron_sword", "name": "Iron Arming Sword", "category": "gear", "slot": "weapon", "price": 600, "effects": {}, "equip_bonus": {}, "combat_power": 20, "combat_armor": 0, "desc": "A dependable blade. Equip for +20 expedition power.", "store_type": "hardware"},
    {"id": "mail_hauberk", "name": "Riveted Mail", "category": "gear", "slot": "armor", "price": 900, "effects": {}, "equip_bonus": {}, "combat_power": 0, "combat_armor": 6, "desc": "Equip to absorb up to 6 damage per expedition.", "store_type": "hardware"},
    {"id": "runed_blade", "name": "Dawnsteel Runeblade", "category": "gear", "slot": "weapon", "price": 4800, "effects": {}, "equip_bonus": {}, "combat_power": 45, "combat_armor": 0, "desc": "A runesmith's masterpiece. Equip for +45 expedition power.", "store_type": "hardware"},
]
