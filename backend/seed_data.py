"""Kaeldor RPG - default seed content. All durations are in GAME minutes.
At the default true real-time scale (time_scale = 1), 1 game minute = 1 real minute,
so these values double as the real-world wait times.
"""

JOBS = [
    {"id": "cleaner", "title": "Cleaner", "category": "entry", "tier": 1,
     "description": "Mop floors and empty bins. Honest, tiring work.",
     "hourly_wage": 11, "requirements": {}, "shift_options": [2, 4, 6],
     "fatigue_per_hour": 5, "stress_per_hour": 2, "energy_per_hour": 4,
     "skill_xp": {"fitness": 6}, "vehicle_required": None,
     "promotion_to": "warehouse_worker",
     "promotion_req": {"hours": 40, "reputation": 55}},
    {"id": "cashier", "title": "Cashier", "category": "retail", "tier": 1,
     "description": "Scan items and handle the till at a busy store.",
     "hourly_wage": 13, "requirements": {}, "shift_options": [4, 6, 8],
     "fatigue_per_hour": 4, "stress_per_hour": 4, "energy_per_hour": 4,
     "skill_xp": {"sales": 6, "charisma": 3}, "vehicle_required": None,
     "promotion_to": "sales_assistant",
     "promotion_req": {"hours": 40, "skills": {"sales": 4}}},
    {"id": "kitchen_helper", "title": "Kitchen Helper", "category": "food", "tier": 1,
     "description": "Prep ingredients and wash dishes in a hot kitchen.",
     "hourly_wage": 14, "requirements": {}, "shift_options": [4, 8],
     "fatigue_per_hour": 6, "stress_per_hour": 5, "energy_per_hour": 5,
     "skill_xp": {"cooking": 7}, "vehicle_required": None,
     "promotion_to": "barista",
     "promotion_req": {"hours": 40, "skills": {"cooking": 4}}},
    {"id": "delivery_driver", "title": "Delivery Driver", "category": "logistics", "tier": 1,
     "description": "Deliver food and parcels across the city. Needs a vehicle.",
     "hourly_wage": 16, "requirements": {"education": ["driving_license"]},
     "shift_options": [2, 4, 6], "fatigue_per_hour": 4, "stress_per_hour": 4,
     "energy_per_hour": 4, "skill_xp": {"driving": 7}, "vehicle_required": "any",
     "promotion_to": "logistics_manager",
     "promotion_req": {"hours": 120, "skills": {"driving": 6}, "education": ["business_basic"]}},
    {"id": "warehouse_worker", "title": "Warehouse Worker", "category": "logistics", "tier": 2,
     "description": "Lift, sort and stack in a sprawling depot.",
     "hourly_wage": 17, "requirements": {}, "shift_options": [6, 8],
     "fatigue_per_hour": 7, "stress_per_hour": 3, "energy_per_hour": 6,
     "skill_xp": {"fitness": 8, "crafting": 3}, "vehicle_required": None,
     "promotion_to": "logistics_manager",
     "promotion_req": {"hours": 120, "skills": {"fitness": 6}}},
    {"id": "sales_assistant", "title": "Sales Assistant", "category": "retail", "tier": 2,
     "description": "Upsell customers on the shop floor for commission.",
     "hourly_wage": 18, "requirements": {"skills": {"sales": 3}}, "shift_options": [4, 6, 8],
     "fatigue_per_hour": 3, "stress_per_hour": 4, "energy_per_hour": 3,
     "skill_xp": {"sales": 9, "charisma": 5}, "vehicle_required": None,
     "promotion_to": "store_manager",
     "promotion_req": {"hours": 120, "skills": {"sales": 7}, "education": ["sales_training"]}},
    {"id": "call_center", "title": "Call Center Agent", "category": "office", "tier": 2,
     "description": "Take calls and soothe angry customers. Stressful.",
     "hourly_wage": 17, "requirements": {}, "shift_options": [4, 6, 8],
     "fatigue_per_hour": 3, "stress_per_hour": 7, "energy_per_hour": 3,
     "skill_xp": {"charisma": 7, "technology": 3}, "vehicle_required": None,
     "promotion_to": "office_assistant",
     "promotion_req": {"hours": 120, "skills": {"charisma": 5}}},
    {"id": "barista", "title": "Barista", "category": "food", "tier": 2,
     "description": "Pull espresso shots and charm the morning crowd.",
     "hourly_wage": 16, "requirements": {"skills": {"cooking": 2}}, "shift_options": [4, 6],
     "fatigue_per_hour": 4, "stress_per_hour": 4, "energy_per_hour": 4,
     "skill_xp": {"cooking": 6, "charisma": 5}, "vehicle_required": None,
     "promotion_to": "restaurant_manager",
     "promotion_req": {"hours": 120, "skills": {"cooking": 6, "management": 3}}},
    {"id": "mechanic_apprentice", "title": "Mechanic Apprentice", "category": "trade", "tier": 2,
     "description": "Learn the trade turning wrenches in a garage.",
     "hourly_wage": 19, "requirements": {"skills": {"crafting": 3}}, "shift_options": [4, 8],
     "fatigue_per_hour": 6, "stress_per_hour": 3, "energy_per_hour": 5,
     "skill_xp": {"crafting": 9, "technology": 4}, "vehicle_required": None,
     "promotion_to": None, "promotion_req": {}},
    {"id": "office_assistant", "title": "Office Assistant", "category": "office", "tier": 3,
     "description": "Manage schedules and paperwork for the firm.",
     "hourly_wage": 22, "requirements": {"education": ["business_basic"], "min_legal_reputation": 50}, "shift_options": [6, 8],
     "fatigue_per_hour": 2, "stress_per_hour": 4, "energy_per_hour": 2,
     "skill_xp": {"management": 8, "finance": 4}, "vehicle_required": None,
     "promotion_to": "store_manager",
     "promotion_req": {"hours": 240, "skills": {"management": 6}, "education": ["management_course"]}},
    {"id": "store_manager", "title": "Store Manager", "category": "management", "tier": 4,
     "description": "Run the floor, the staff and the numbers.",
     "hourly_wage": 32, "requirements": {"skills": {"management": 5}, "education": ["management_course"], "min_legal_reputation": 60, "min_social_status": 20, "min_reputation": 60},
     "shift_options": [6, 8], "fatigue_per_hour": 3, "stress_per_hour": 6, "energy_per_hour": 3,
     "skill_xp": {"management": 12, "finance": 6, "sales": 4}, "vehicle_required": None,
     "promotion_to": None, "promotion_req": {}},
    {"id": "restaurant_manager", "title": "Restaurant Manager", "category": "management", "tier": 4,
     "description": "Command the kitchen and front of house.",
     "hourly_wage": 34, "requirements": {"skills": {"cooking": 6, "management": 5}, "min_legal_reputation": 55, "min_social_status": 20, "min_reputation": 55},
     "shift_options": [6, 8], "fatigue_per_hour": 4, "stress_per_hour": 7, "energy_per_hour": 4,
     "skill_xp": {"management": 12, "cooking": 6}, "vehicle_required": None,
     "promotion_to": None, "promotion_req": {}},
    {"id": "logistics_manager", "title": "Logistics Manager", "category": "management", "tier": 4,
     "description": "Optimize routes and run the whole depot.",
     "hourly_wage": 36, "requirements": {"skills": {"management": 5, "driving": 5}, "education": ["business_basic"], "min_legal_reputation": 60, "min_social_status": 25, "min_reputation": 60},
     "shift_options": [6, 8], "fatigue_per_hour": 3, "stress_per_hour": 6, "energy_per_hour": 3,
     "skill_xp": {"management": 12, "driving": 6, "finance": 5}, "vehicle_required": None,
     "promotion_to": None, "promotion_req": {}},
]

# ============================ JOB SHIFTS — Universal Shift & Risk Engine ============================
# Each job offers hand-tuned, individual shift options. A shift can only be STARTED while the current
# game hour is inside start_window (HARD gate). min_hour > max_hour = an overnight window that wraps
# past midnight (e.g. 21 -> 3). pay_multiplier / xp_multiplier scale the shift's wage & skill XP;
# injury_risk is the per-shift chance of an on-the-job injury (health loss + stress) — the shift
# still finishes. All fields are admin-editable via Admin ▸ Gameplay Tuning ▸ Job Shifts.
# STANDARDIZED 4-SHIFT SYSTEM (fixed start times — players must REGISTER before the shift begins;
# the character AUTO-STARTS work when the game clock reaches start_hour). All shifts share the same
# clock across every job:
#   Early Shift  08:00 - 13:00 (5h)
#   Late Shift   13:00 - 18:00 (5h)
#   Full Shift   08:00 - 18:00 (10h)
#   Night Shift  22:00 - 08:00 (10h, wraps past midnight)
# start_window is derived {min_hour, max_hour} purely for display/legacy helpers. Night shifts pay &
# XP more but carry higher injury risk. Admins can disable Night per-job via the dashboard later.
def _shift(sid, name, start_hour, hours, risk, pay=1.0, xp=1.0):
    return {"id": sid, "name": name, "start_hour": start_hour, "duration_hours": hours,
            "start_window": {"min_hour": start_hour, "max_hour": (start_hour + hours) % 24},
            "injury_risk": round(risk, 3), "pay_multiplier": pay, "xp_multiplier": xp}


def _std_shifts(risk, include_night=True):
    """Build the standardized shift set for a job from its base per-shift injury risk."""
    shifts = [
        _shift("early", "Early Shift", 8, 5, risk),
        _shift("late", "Late Shift", 13, 5, risk * 1.1, pay=1.10, xp=1.05),
        _shift("full", "Full Shift", 8, 10, risk * 1.2, pay=1.05, xp=1.05),
    ]
    if include_night:
        shifts.append(_shift("night", "Night Shift", 22, 10, risk * 2.0 + 0.05, pay=1.45, xp=1.20))
    return shifts


# Per-job base injury risk + whether the Night shift is offered by default (office desk jobs skip it).
JOB_SHIFT_CONFIG = {
    "cleaner":             {"risk": 0.04, "night": True},
    "cashier":             {"risk": 0.02, "night": True},
    "kitchen_helper":      {"risk": 0.06, "night": True},
    "delivery_driver":     {"risk": 0.06, "night": True},
    "warehouse_worker":    {"risk": 0.08, "night": True},
    "sales_assistant":     {"risk": 0.02, "night": True},
    "call_center":         {"risk": 0.02, "night": True},
    "barista":             {"risk": 0.03, "night": True},
    "mechanic_apprentice": {"risk": 0.08, "night": True},
    "office_assistant":    {"risk": 0.01, "night": False},
    "store_manager":       {"risk": 0.02, "night": False},
    "restaurant_manager":  {"risk": 0.04, "night": True},
    "logistics_manager":   {"risk": 0.03, "night": True},
}

JOB_SHIFTS = {jid: _std_shifts(c["risk"], c["night"]) for jid, c in JOB_SHIFT_CONFIG.items()}
# Override the legacy int shift_options ([2,4,6]) with the rich per-job shift schema.
# Default hiring/application tuning (admin-editable via Sandbox -> Job Editor / Applications):
#   acceptance_base_chance : baseline hire probability before stat modifiers (0.0-1.0)
#   skill_weight           : multiplier on how much skill-over-requirement helps the chance
#   success_response       : message when hired (placeholders: {title} {wage} {reason})
#   failure_response       : message when rejected (placeholders: {title} {wage} {reason})
DEFAULT_HIRE_SUCCESS = "Your application for {title} was accepted — the offer is ${wage}/h. Accept it to start working."
DEFAULT_HIRE_FAILURE = "Your application for {title} was rejected: {reason}."
for _j in JOBS:
    if _j["id"] in JOB_SHIFTS:
        _j["shift_options"] = JOB_SHIFTS[_j["id"]]
    # Progressive visibility: jobs default to visible in the Job Center. Admins can hide
    # "rank-up only" jobs (reachable only via promotion) by setting this False.
    _j.setdefault("visible_in_listings", True)
    _j.setdefault("acceptance_base_chance", 0.5)
    _j.setdefault("skill_weight", 1.0)
    _j.setdefault("success_response", DEFAULT_HIRE_SUCCESS)
    _j.setdefault("failure_response", DEFAULT_HIRE_FAILURE)


# Job Sectors / Agencies. The Job Center groups jobs into sectors; players browse a
# sector, then see only the jobs assigned to it. Admin-editable via Sandbox -> Job Sectors.
JOB_SECTORS = [
    {"id": "sector_retail", "name": "Retail & Sales", "icon": "ShoppingBag", "order": 1, "active": True,
     "desc": "Shop floors, tills and commission — serve customers and climb toward store management.",
     "job_ids": ["cashier", "sales_assistant", "store_manager"]},
    {"id": "sector_hospitality", "name": "Food & Hospitality", "icon": "UtensilsCrossed", "order": 2, "active": True,
     "desc": "Kitchens, cafes and restaurants — feed the city and rise from prep cook to running the place.",
     "job_ids": ["kitchen_helper", "barista", "restaurant_manager"]},
    {"id": "sector_logistics", "name": "Logistics & Transport", "icon": "Truck", "order": 3, "active": True,
     "desc": "Deliveries, warehouses and depots — keep Kaeldor's goods moving day and night.",
     "job_ids": ["delivery_driver", "warehouse_worker", "logistics_manager"]},
    {"id": "sector_corporate", "name": "Corporate & Office", "icon": "Building2", "order": 4, "active": True,
     "desc": "Phones, desks and admin — steady indoor work with a path into the back office.",
     "job_ids": ["call_center", "office_assistant"]},
    {"id": "sector_trades", "name": "Trades & Manual Labor", "icon": "Wrench", "order": 5, "active": True,
     "desc": "Hands-on graft — cleaning, repairs and workshops for those who'd rather build than sit.",
     "job_ids": ["cleaner", "mechanic_apprentice"]},
    {"id": "sector_military", "name": "Military & Defense", "icon": "Shield", "order": 6, "active": True,
     "desc": "Join the defense forces — enlist and rise through the ranks of Kaeldor's army.",
     "job_ids": ["army_private", "army_corporal", "army_sergeant"]},
    {"id": "sector_public", "name": "Public Services", "icon": "Landmark", "order": 7, "active": True,
     "desc": "Serve the city — policing and municipal work that keep Kaeldor running.",
     "job_ids": ["police_officer", "garbageman", "garbageman_2"]},
]


ACTIONS = [
    {"id": "sleep", "name": "Sleep", "category": "rest", "duration_minutes": 480,
     "requirements": {}, "money_cost": 0, "money_reward": 0,
     "effects": {"energy": 80, "fatigue": -70, "stress": -20, "hunger": 15, "health": 8},
     "skill_xp": {}, "risk_level": "none", "cooldown_minutes": 0,
     "blocking": True, "offline": True, "result_text": "You wake up rested.", "sleep": True},
    {"id": "nap", "name": "Power Nap", "category": "rest", "duration_minutes": 30,
     "requirements": {}, "money_cost": 0, "money_reward": 0,
     "effects": {"energy": 25, "fatigue": -18, "stress": -6, "hunger": 4},
     "skill_xp": {}, "risk_level": "none", "cooldown_minutes": 0,
     "blocking": True, "offline": True, "result_text": "A quick nap helps.", "sleep": True},
    {"id": "eat_cheap", "name": "Eat Cheap Meal", "category": "food", "duration_minutes": 8,
     "requirements": {}, "money_cost": 9, "money_reward": 0,
     "effects": {"hunger": -45, "mood": 3, "health": -1},
     "skill_xp": {}, "risk_level": "none", "cooldown_minutes": 0,
     "blocking": False, "offline": False, "result_text": "Cheap and filling."},
    {"id": "cook_meal", "name": "Cook a Meal", "category": "food", "duration_minutes": 30,
     "requirements": {}, "money_cost": 6, "money_reward": 0,
     "effects": {"hunger": -55, "mood": 6, "health": 3},
     "skill_xp": {"cooking": 10}, "risk_level": "none", "cooldown_minutes": 0,
     "blocking": True, "offline": False, "result_text": "A home-cooked meal. Delicious."},
    {"id": "eat_restaurant", "name": "Eat at Restaurant", "category": "food", "duration_minutes": 50,
     "requirements": {}, "money_cost": 38, "money_reward": 0,
     "effects": {"hunger": -70, "mood": 14, "stress": -8, "health": 2},
     "skill_xp": {}, "risk_level": "none", "cooldown_minutes": 0,
     "blocking": True, "offline": False, "result_text": "A treat for yourself."},
    {"id": "grocery", "name": "Grocery Shopping", "category": "errand", "duration_minutes": 18,
     "requirements": {}, "money_cost": 55, "money_reward": 0,
     "effects": {"hunger": -20, "energy": -5, "mood": 2},
     "skill_xp": {}, "risk_level": "none", "cooldown_minutes": 60,
     "blocking": True, "offline": False, "result_text": "Pantry stocked for the week."},
    {"id": "gym", "name": "Gym Workout", "category": "health", "duration_minutes": 60,
     "requirements": {}, "money_cost": 12, "money_reward": 0,
     "effects": {"fitness": 0, "energy": -18, "fatigue": 10, "health": 8, "mood": 8, "stress": -10},
     "skill_xp": {"fitness": 16}, "risk_level": "none", "cooldown_minutes": 30,
     "blocking": True, "offline": False, "result_text": "Sweaty but stronger."},
    {"id": "jog", "name": "Go Jogging", "category": "health", "duration_minutes": 35,
     "requirements": {}, "money_cost": 0, "money_reward": 0,
     "effects": {"energy": -10, "fatigue": 6, "health": 4, "mood": 6, "stress": -8},
     "skill_xp": {"fitness": 9}, "risk_level": "none", "cooldown_minutes": 20,
     "blocking": True, "offline": False, "result_text": "Fresh air does you good."},
    {"id": "relax", "name": "Watch TV & Relax", "category": "leisure", "duration_minutes": 40,
     "requirements": {}, "money_cost": 0, "money_reward": 0,
     "effects": {"stress": -16, "mood": 10, "energy": 4},
     "skill_xp": {}, "risk_level": "none", "cooldown_minutes": 0,
     "blocking": False, "offline": True, "result_text": "You unwind on the couch."},
    {"id": "meditate", "name": "Meditate", "category": "leisure", "duration_minutes": 15,
     "requirements": {}, "money_cost": 0, "money_reward": 0,
     "effects": {"stress": -22, "mood": 6, "fatigue": -5},
     "skill_xp": {}, "risk_level": "none", "cooldown_minutes": 45,
     "blocking": True, "offline": False, "result_text": "Calm and centered."},
    {"id": "read", "name": "Read a Book", "category": "leisure", "duration_minutes": 45,
     "requirements": {}, "money_cost": 0, "money_reward": 0,
     "effects": {"stress": -8, "mood": 5, "energy": -4},
     "skill_xp": {"studying": 8, "creativity": 4}, "risk_level": "none", "cooldown_minutes": 0,
     "blocking": True, "offline": True, "result_text": "You learned something new."},
    {"id": "side_gig", "name": "Online Freelance Gig", "category": "hustle", "duration_minutes": 40,
     "requirements": {}, "money_cost": 0, "money_reward": 45,
     "effects": {"energy": -14, "fatigue": 8, "stress": 6, "mood": 2},
     "skill_xp": {"technology": 8, "creativity": 6}, "risk_level": "none", "cooldown_minutes": 20,
     "blocking": False, "offline": True, "result_text": "Gig delivered and paid."},
    {"id": "delivery_run", "name": "Quick Delivery Run", "category": "hustle", "duration_minutes": 30,
     "requirements": {"vehicle": "any"}, "money_cost": 0, "money_reward": 22,
     "effects": {"energy": -8, "fatigue": 5, "hunger": 4}, "skill_xp": {"driving": 6},
     "risk_level": "low", "cooldown_minutes": 15, "blocking": True, "offline": True,
     "result_text": "Parcels delivered, tip earned."},
    {"id": "repair_vehicle", "name": "Repair Your Vehicle", "category": "maintenance", "duration_minutes": 90,
     "requirements": {"vehicle": "any"}, "money_cost": 80, "money_reward": 0,
     "effects": {"energy": -10, "fatigue": 8}, "skill_xp": {"crafting": 10},
     "risk_level": "none", "cooldown_minutes": 0, "blocking": True, "offline": False,
     "result_text": "Your vehicle runs smoothly again.", "repairs_vehicle": True},
    {"id": "renovate_home", "name": "Renovate Apartment", "category": "maintenance", "duration_minutes": 240,
     "requirements": {}, "money_cost": 350, "money_reward": 0,
     "effects": {"mood": 18, "energy": -20, "fatigue": 15}, "skill_xp": {"crafting": 14},
     "risk_level": "none", "cooldown_minutes": 0, "blocking": True, "offline": True,
     "result_text": "Your home looks brand new."},
]

COURSES = [
    {"id": "driving_license", "title": "Driving License", "category": "license", "duration_minutes": 720,
     "cost": 280, "requirements": {}, "grants_skills": {"driving": 3},
     "unlocks": "Delivery jobs & driving careers", "desc": "Learn to drive legally."},
    {"id": "business_basic", "title": "Basic Business Course", "category": "business", "duration_minutes": 2880,
     "cost": 350, "requirements": {}, "grants_skills": {"management": 2, "finance": 2},
     "unlocks": "Office jobs & smarter business deals", "desc": "Fundamentals of running a business."},
    {"id": "cooking_cert", "title": "Cooking Certificate", "category": "trade", "duration_minutes": 1440,
     "cost": 320, "requirements": {}, "grants_skills": {"cooking": 4},
     "unlocks": "Better food jobs & bistro bonuses", "desc": "Professional cooking techniques."},
    {"id": "sales_training", "title": "Sales Training", "category": "business", "duration_minutes": 1440,
     "cost": 300, "requirements": {}, "grants_skills": {"sales": 4, "charisma": 2},
     "unlocks": "Sales careers & retail bonuses", "desc": "Close any deal."},
    {"id": "management_course", "title": "Management Course", "category": "business", "duration_minutes": 4320,
     "cost": 600, "requirements": {"education": ["business_basic"]}, "grants_skills": {"management": 5},
     "unlocks": "Manager roles & business efficiency", "desc": "Lead teams and operations."},
    {"id": "it_course", "title": "IT Course", "category": "tech", "duration_minutes": 2880,
     "cost": 500, "requirements": {}, "grants_skills": {"technology": 5},
     "unlocks": "Tech gigs & online business", "desc": "Modern technology skills."},
    {"id": "finance_course", "title": "Finance Course", "category": "business", "duration_minutes": 2880,
     "cost": 550, "requirements": {}, "grants_skills": {"finance": 5},
     "unlocks": "Lower loan rates & investment options", "desc": "Master money management."},
    {"id": "law_basics", "title": "Law Basics", "category": "legal", "duration_minutes": 2160,
     "cost": 520, "requirements": {}, "grants_skills": {"street_smarts": 3, "finance": 2},
     "unlocks": "Reduced fines & legal protection", "desc": "Know your rights."},
    {"id": "university_degree", "title": "University Degree", "category": "degree", "duration_minutes": 14400,
     "cost": 2500, "requirements": {"education": ["business_basic"]},
     "grants_skills": {"management": 4, "finance": 4, "studying": 5, "technology": 3},
     "unlocks": "Top-tier careers & prestige", "desc": "A full degree. Long but worth it."},
]

ITEMS = [
    # --- Consumables (instant effect, consumed on use) ---
    {"id": "energy_drink", "name": "Energy Drink", "category": "consumable", "price": 5,
     "effects": {"energy": 18, "fatigue": -6, "health": -2}, "desc": "Cheap caffeine boost."},
    {"id": "protein_bar", "name": "Protein Bar", "category": "consumable", "price": 4,
     "effects": {"hunger": -18, "health": 1}, "desc": "Snack on the go."},
    {"id": "coffee", "name": "Coffee", "category": "consumable", "price": 4,
     "effects": {"energy": 12, "mood": 4}, "desc": "Liquid motivation."},
    {"id": "painkillers", "name": "Painkillers", "category": "consumable", "price": 12,
     "effects": {"health": 10, "stress": -5}, "desc": "Ease the aches."},
    {"id": "first_aid_kit", "name": "First Aid Kit", "category": "consumable", "price": 45,
     "effects": {"health": 35}, "desc": "Patch yourself up fast."},
    {"id": "sleeping_pills", "name": "Sleeping Pills", "category": "consumable", "price": 20,
     "effects": {"fatigue": -30, "stress": -10, "energy": 10}, "desc": "A deep, restful night."},
    # --- Apparel (slot: outfit) ---
    {"id": "nice_clothes", "name": "Nice Outfit", "category": "apparel", "price": 120, "slot": "outfit",
     "equip": {"social_status_floor": 12, "social_success": 0.05, "tip_rate": 0.03},
     "desc": "Dress to impress. Equip for a passive social standing & tips boost."},
    {"id": "business_suit", "name": "Business Suit", "category": "apparel", "price": 480, "slot": "outfit",
     "equip": {"social_status_floor": 22, "reputation_floor": 45, "social_success": 0.08, "tip_rate": 0.05},
     "desc": "Sharp tailoring that commands respect in any room."},
    # --- Accessory (slot: accessory) ---
    {"id": "luxury_watch", "name": "Luxury Watch", "category": "accessory", "price": 900, "slot": "accessory",
     "equip": {"social_status_floor": 18, "reputation_floor": 35, "social_success": 0.04},
     "desc": "A status symbol on your wrist — equip to raise your standing."},
    # --- Devices (slots: phone / computer) ---
    {"id": "smartphone", "name": "Smartphone", "category": "device", "price": 250, "slot": "phone",
     "equip": {"mood_floor": 20},
     "desc": "Stay connected. Required to send SMS to other players. Equip to keep your spirits up."},
    {"id": "laptop", "name": "Laptop", "category": "device", "price": 600, "slot": "computer",
     "equip": {"work_effectiveness": 0.05, "mood_floor": 15},
     "desc": "Work, browse and write email. Required to send email. Equip for a work performance boost."},
    # --- Work / Fitness gear (slot: work_gear) ---
    {"id": "toolbelt", "name": "Pro Toolbelt", "category": "gear", "price": 320, "slot": "work_gear",
     "equip": {"work_effectiveness": 0.09},
     "desc": "The right tools make every shift more productive."},
    {"id": "athletic_gear", "name": "Athletic Gear", "category": "gear", "price": 240, "slot": "work_gear",
     "equip": {"energy_drain_mult": 0.85, "health_regen": 0.6, "work_effectiveness": 0.03},
     "desc": "Stay in shape — slower energy drain and faster recovery when equipped."},
]

# City Shops: map each item to a store type so shops sell only their category.
ITEM_STORE_TYPE = {
    "energy_drink": "grocery", "protein_bar": "grocery", "coffee": "grocery",
    "painkillers": "pharmacy", "first_aid_kit": "pharmacy", "sleeping_pills": "pharmacy",
    "nice_clothes": "clothing", "business_suit": "clothing", "luxury_watch": "clothing",
    "smartphone": "electronics", "laptop": "electronics",
    "toolbelt": "hardware", "athletic_gear": "hardware",
}
ITEM_CATEGORY_OPTIONS = ["grocery", "pharmacy", "clothing", "electronics", "hardware"]
for _it in ITEMS:
    _it.setdefault("store_type", ITEM_STORE_TYPE.get(_it["id"], "grocery"))

# Default city shops (admin-editable via the Sandbox → City Shops tab).
# Default per-shop stock capacity when an item has no explicit config.
SHOP_DEFAULT_CAPACITY = 25

# City Shops. Each shop has opening_hours (players can only buy while OPEN),
# and items_config: per-item daily stock capacity + a manual discount (%) for sale events.
# Stock refreshes to capacity at game midnight (00:00) every game day.
CITY_SHOPS = [
    {"id": "shop_grocery", "name": "Kaeldor Fresh Foods", "category": "grocery", "icon": "ShoppingBasket",
     "desc": "Grocery Store — daily food and beverages to keep your needs topped up.",
     "business_type_id": "kiosk", "location_id": None, "active": True, "order": 1,
     "opening_hours": {"open": "07:00", "close": "22:00"},
     "items_config": {
         "coffee": {"capacity": 60, "price_pct": 100},
         "energy_drink": {"capacity": 60, "price_pct": 100},
         "protein_bar": {"capacity": 60, "price_pct": 100}}},
    {"id": "shop_pharmacy", "name": "MediCare Pharmacy", "category": "pharmacy", "icon": "Cross",
     "desc": "Pharmacy — painkillers, first aid and recovery items for your health.",
     "business_type_id": None, "location_id": None, "active": True, "order": 2,
     "opening_hours": {"open": "00:00", "close": "24:00"},
     "items_config": {
         "painkillers": {"capacity": 40, "price_pct": 100},
         "first_aid_kit": {"capacity": 15, "price_pct": 100},
         "sleeping_pills": {"capacity": 25, "price_pct": 100}}},
    {"id": "shop_clothing", "name": "Vantage Apparel", "category": "clothing", "icon": "Shirt",
     "desc": "Clothing Boutique — outfits and accessories that boost your social standing.",
     "business_type_id": None, "location_id": None, "active": True, "order": 3,
     "opening_hours": {"open": "10:00", "close": "20:00"},
     "items_config": {
         "nice_clothes": {"capacity": 12, "price_pct": 100},
         "business_suit": {"capacity": 6, "price_pct": 100},
         "luxury_watch": {"capacity": 4, "price_pct": 100}}},
    {"id": "shop_electronics", "name": "Circuit City", "category": "electronics", "icon": "Laptop",
     "desc": "Electronics Store — smartphones and laptops for comms and work.",
     "business_type_id": None, "location_id": None, "active": True, "order": 4,
     "opening_hours": {"open": "09:00", "close": "21:00"},
     "items_config": {
         "smartphone": {"capacity": 10, "price_pct": 100},
         "laptop": {"capacity": 6, "price_pct": 100}}},
    {"id": "shop_hardware", "name": "Ironworks Hardware & Sports", "category": "hardware", "icon": "Hammer",
     "desc": "Hardware & Sports — pro tools and fitness gear for the grind.",
     "business_type_id": None, "location_id": None, "active": True, "order": 5,
     "opening_hours": {"open": "08:00", "close": "18:00"},
     "items_config": {
         "toolbelt": {"capacity": 8, "price_pct": 100},
         "athletic_gear": {"capacity": 10, "price_pct": 100}}},
]


HOUSING = [
    {"id": "studio_tiny", "name": "Tiny Studio", "tier": 1, "rent_per_day": 18, "buy_price": 0,
     "deposit": 0, "bills_per_day": 4, "sleep_quality": 0.8, "mood_bonus": -2,
     "social_status": 0, "storage": 5, "desc": "A cramped starter studio. Better than the street."},
    {"id": "cheap_apt", "name": "Cheap Apartment", "tier": 2, "rent_per_day": 30, "buy_price": 9000,
     "deposit": 300, "bills_per_day": 6, "sleep_quality": 0.95, "mood_bonus": 2,
     "social_status": 5, "storage": 10, "desc": "Small but livable one-room apartment."},
    {"id": "one_bed", "name": "1-Bedroom Flat", "tier": 3, "rent_per_day": 52, "buy_price": 18000,
     "deposit": 600, "bills_per_day": 9, "sleep_quality": 1.1, "mood_bonus": 6,
     "social_status": 12, "storage": 18, "desc": "A proper home with a real bedroom."},
    {"id": "condo", "name": "Modern Condo", "tier": 4, "rent_per_day": 95, "buy_price": 42000,
     "deposit": 1200, "bills_per_day": 14, "sleep_quality": 1.25, "mood_bonus": 12,
     "social_status": 25, "storage": 30, "desc": "Sleek downtown living with a view."},
    {"id": "townhouse", "name": "Townhouse", "tier": 5, "rent_per_day": 150, "buy_price": 85000,
     "deposit": 2500, "bills_per_day": 22, "sleep_quality": 1.35, "mood_bonus": 18,
     "social_status": 40, "storage": 50, "desc": "Space, comfort and status."},
    {"id": "penthouse", "name": "Luxury Penthouse", "tier": 6, "rent_per_day": 320, "buy_price": 250000,
     "deposit": 6000, "bills_per_day": 40, "sleep_quality": 1.5, "mood_bonus": 30,
     "social_status": 70, "storage": 100, "desc": "The top of the city. Pure luxury."},
]

VEHICLES = [
    {"id": "bicycle", "name": "Bicycle", "type": "bike", "price": 180, "fuel_per_day": 0,
     "insurance_per_day": 0, "maintenance_per_day": 1, "accident_risk": 0.02, "speed": 1,
     "resale": 0.5, "desc": "Cheap, healthy, slow. Enables basic deliveries."},
    {"id": "scooter", "name": "Scooter", "type": "scooter", "price": 900, "fuel_per_day": 3,
     "insurance_per_day": 2, "maintenance_per_day": 2, "accident_risk": 0.05, "speed": 2,
     "resale": 0.55, "desc": "Zippy through traffic."},
    {"id": "cheap_car", "name": "Cheap Used Car", "type": "car", "price": 3200, "fuel_per_day": 6,
     "insurance_per_day": 4, "maintenance_per_day": 4, "accident_risk": 0.06, "speed": 3,
     "resale": 0.5, "desc": "Unreliable but it runs."},
    {"id": "reliable_car", "name": "Reliable Car", "type": "car", "price": 9500, "fuel_per_day": 7,
     "insurance_per_day": 6, "maintenance_per_day": 3, "accident_risk": 0.03, "speed": 4,
     "resale": 0.6, "desc": "Dependable daily driver."},
    {"id": "van", "name": "Cargo Van", "type": "van", "price": 14000, "fuel_per_day": 11,
     "insurance_per_day": 8, "maintenance_per_day": 6, "accident_risk": 0.05, "speed": 3,
     "resale": 0.6, "desc": "Hauls goods for business."},
    {"id": "delivery_van", "name": "Delivery Van", "type": "van", "price": 18000, "fuel_per_day": 12,
     "insurance_per_day": 9, "maintenance_per_day": 6, "accident_risk": 0.05, "speed": 3,
     "resale": 0.62, "desc": "Built for the delivery grind."},
    {"id": "luxury_car", "name": "Luxury Car", "type": "car", "price": 65000, "fuel_per_day": 16,
     "insurance_per_day": 20, "maintenance_per_day": 12, "accident_risk": 0.04, "speed": 5,
     "resale": 0.55, "desc": "Status on wheels."},
]

# ============================ VEHICLE CATEGORIES (Dealer showroom) ============================
# The Vehicle Dealer groups models into browsable categories (same Sector/Box pattern as the Job
# Center and City Shops). Each vehicle carries a `category_id` linking to a vehicle_categories doc;
# any vehicle without an active category falls into a player-facing "Other Vehicles" catch-all.
VEHICLE_CATEGORIES = [
    {"id": "cat_bikes", "name": "Bikes & Scooters", "icon": "Bike", "order": 1, "active": True,
     "desc": "Fast, agile two-wheelers for darting through city traffic on a tight budget."},
    {"id": "cat_economy", "name": "Compact & Economy", "icon": "Car", "order": 2, "active": True,
     "desc": "Affordable everyday cars — your first reliable set of four wheels."},
    {"id": "cat_utility", "name": "Vans & Utility", "icon": "Truck", "order": 3, "active": True,
     "desc": "Cargo haulers built for delivery work and moving goods for your business."},
    {"id": "cat_luxury", "name": "Luxury", "icon": "Gem", "order": 4, "active": True,
     "desc": "Premium status symbols — top speed, top comfort, top price."},
]
VEHICLE_CATEGORY_MAP = {
    "bicycle": "cat_bikes", "scooter": "cat_bikes",
    "cheap_car": "cat_economy", "reliable_car": "cat_economy",
    "van": "cat_utility", "delivery_van": "cat_utility",
    "luxury_car": "cat_luxury",
}
for _v in VEHICLES:
    _v["category_id"] = VEHICLE_CATEGORY_MAP.get(_v["id"])


# Supply-chain model: each business buys named ingredients (recipe), workers process them into a
# finished product, and the product is sold to meet demand. Profit = sales - materials - wages.
# NO rent / artificial fixed costs on owned businesses. production_per_worker_hour = finished units a
# fully-productive worker makes per game-hour; daily_demand = max units/day sellable at full rep+marketing.
BUSINESS_TYPES = [
    {"id": "kiosk", "name": "Street Kiosk", "category": "retail", "purchase_price": 4000,
     "product": {"name": "Snack & Drink Combo", "price": 12.0},
     "recipe": [{"id": "snacks", "name": "Snacks", "qty": 1, "cost": 4.0},
                {"id": "drinks", "name": "Drinks", "qty": 1, "cost": 2.5}],
     "production_per_worker_hour": 2.7, "daily_demand": 220, "opening_hours": {"open": "08:00", "close": "20:00"},
     "requirements": {}, "max_level": 5, "legal_risk": 0.02,
     "desc": "Snacks and drinks on a busy corner. Easy entry into business."},
    {"id": "delivery_service", "name": "Delivery Service", "category": "logistics", "purchase_price": 9000,
     "product": {"name": "Completed Delivery", "price": 26.0},
     "recipe": [{"id": "fuel", "name": "Fuel", "qty": 1, "cost": 7.0},
                {"id": "packaging", "name": "Packaging", "qty": 1, "cost": 5.0}],
     "production_per_worker_hour": 3.74, "daily_demand": 130, "opening_hours": {"open": "09:00", "close": "21:00"},
     "requirements": {"education": ["driving_license"]}, "max_level": 6, "legal_risk": 0.03,
     "desc": "Couriers on demand across the city."},
    {"id": "bistro", "name": "Bistro", "category": "food", "purchase_price": 22000,
     "product": {"name": "Meal Served", "price": 38.0},
     "recipe": [{"id": "fresh_ingredients", "name": "Fresh Ingredients", "qty": 1, "cost": 12.0},
                {"id": "beverages", "name": "Beverages", "qty": 1, "cost": 7.0}],
     "production_per_worker_hour": 3.07, "daily_demand": 150, "opening_hours": {"open": "10:00", "close": "22:00"},
     "requirements": {"skills": {"cooking": 4}}, "max_level": 6, "legal_risk": 0.04,
     "desc": "A cozy neighborhood eatery."},
    {"id": "clothing_store", "name": "Clothing Store", "category": "retail", "purchase_price": 28000,
     "product": {"name": "Garment Sold", "price": 78.0},
     "recipe": [{"id": "wholesale_apparel", "name": "Wholesale Apparel", "qty": 1, "cost": 34.0},
                {"id": "packaging", "name": "Packaging", "qty": 1, "cost": 4.0}],
     "production_per_worker_hour": 2.62, "daily_demand": 110, "opening_hours": {"open": "10:00", "close": "19:00"},
     "requirements": {"skills": {"sales": 4}}, "max_level": 6, "legal_risk": 0.03,
     "desc": "Trendy fashion for the downtown crowd."},
    {"id": "auto_repair", "name": "Auto Repair Shop", "category": "trade", "purchase_price": 35000,
     "product": {"name": "Repair Job", "price": 210.0},
     "recipe": [{"id": "spare_parts", "name": "Spare Parts", "qty": 1, "cost": 90.0},
                {"id": "shop_supplies", "name": "Shop Supplies", "qty": 1, "cost": 15.0}],
     "production_per_worker_hour": 0.96, "daily_demand": 45, "opening_hours": {"open": "08:00", "close": "18:00"},
     "requirements": {"skills": {"crafting": 5}}, "max_level": 6, "legal_risk": 0.05,
     "desc": "Fix cars, charge a premium."},
    {"id": "gym", "name": "Fitness Gym", "category": "service", "purchase_price": 40000,
     "product": {"name": "Training Session", "price": 30.0},
     "recipe": [{"id": "utilities", "name": "Utilities", "qty": 1, "cost": 10.0},
                {"id": "equipment_upkeep", "name": "Equipment Upkeep", "qty": 1, "cost": 5.0}],
     "production_per_worker_hour": 3.15, "daily_demand": 170, "opening_hours": {"open": "06:00", "close": "22:00"},
     "requirements": {"skills": {"fitness": 5}}, "max_level": 6, "legal_risk": 0.02,
     "desc": "Memberships and personal training."},
    {"id": "pet_shop", "name": "Pet Shop", "category": "retail", "purchase_price": 26000,
     "product": {"name": "Pet Goods Sold", "price": 48.0},
     "recipe": [{"id": "pet_stock", "name": "Pet Stock", "qty": 1, "cost": 20.0},
                {"id": "animal_feed", "name": "Animal Feed", "qty": 1, "cost": 4.0}],
     "production_per_worker_hour": 2.85, "daily_demand": 110, "opening_hours": {"open": "09:00", "close": "18:00"},
     "requirements": {}, "max_level": 5, "legal_risk": 0.02,
     "desc": "Pets, food and accessories."},
    {"id": "online_shop", "name": "Online Shop", "category": "tech", "purchase_price": 12000,
     "product": {"name": "Order Fulfilled", "price": 52.0},
     "recipe": [{"id": "inventory", "name": "Inventory", "qty": 1, "cost": 22.0},
                {"id": "shipping", "name": "Shipping", "qty": 1, "cost": 4.0}],
     "production_per_worker_hour": 1.0, "daily_demand": 150, "opening_hours": {"open": "00:00", "close": "24:00"},
     "requirements": {"skills": {"technology": 4}}, "max_level": 7, "legal_risk": 0.03,
     "desc": "E-commerce with low overhead, high scale."},
    {"id": "cleaning_co", "name": "Cleaning Company", "category": "service", "purchase_price": 15000,
     "product": {"name": "Cleaning Contract", "price": 110.0},
     "recipe": [{"id": "cleaning_supplies", "name": "Cleaning Supplies", "qty": 1, "cost": 38.0},
                {"id": "transport", "name": "Transport", "qty": 1, "cost": 14.0}],
     "production_per_worker_hour": 0.42, "daily_demand": 80, "opening_hours": {"open": "06:00", "close": "20:00"},
     "requirements": {}, "max_level": 6, "legal_risk": 0.02,
     "desc": "Contracts with offices and homes."},
    {"id": "real_estate_agency", "name": "Real Estate Agency", "category": "finance", "purchase_price": 55000,
     "product": {"name": "Deal Closed", "price": 1900.0},
     "recipe": [{"id": "marketing_spend", "name": "Marketing Spend", "qty": 1, "cost": 600.0},
                {"id": "legal_fees", "name": "Legal Fees", "qty": 1, "cost": 300.0}],
     "production_per_worker_hour": 0.154, "daily_demand": 9, "opening_hours": {"open": "09:00", "close": "17:00"},
     "requirements": {"education": ["business_basic"], "skills": {"finance": 5}}, "max_level": 7,
     "legal_risk": 0.05, "desc": "Buy, sell and broker property deals."},
]

ILLEGAL_ACTIONS = [
    {"id": "petty_theft", "name": "Petty Theft", "category": "crime", "duration_minutes": 45,
     "reward_min": 30, "reward_max": 120, "suspicion_gain": 8, "police_risk": 0.20,
     "failure_chance": 0.25, "jail_minutes": 360, "fine_amount": 150, "reputation_impact": -6,
     "skill_xp": {"street_smarts": 8}, "blocking": True, "offline": True,
     "desc": "Snatch something unattended. Low reward, real risk."},
    {"id": "black_market", "name": "Black Market Deal", "category": "crime", "duration_minutes": 90,
     "reward_min": 150, "reward_max": 500, "suspicion_gain": 14, "police_risk": 0.28,
     "failure_chance": 0.30, "jail_minutes": 1080, "fine_amount": 600, "reputation_impact": -10,
     "skill_xp": {"street_smarts": 14, "sales": 5}, "blocking": True, "offline": True,
     "desc": "Move goods that fell off a truck."},
    {"id": "street_race", "name": "Street Race", "category": "crime", "duration_minutes": 60,
     "reward_min": 200, "reward_max": 700, "suspicion_gain": 12, "police_risk": 0.25,
     "failure_chance": 0.35, "jail_minutes": 720, "fine_amount": 500, "reputation_impact": -4,
     "skill_xp": {"driving": 16}, "blocking": True, "offline": True,
     "requirements": {"vehicle": "any"}, "desc": "Bet big and race for pink slips."},
    {"id": "tax_evasion", "name": "Tax Evasion Attempt", "category": "fraud", "duration_minutes": 240,
     "reward_min": 300, "reward_max": 1200, "suspicion_gain": 18, "police_risk": 0.22,
     "failure_chance": 0.30, "jail_minutes": 1440, "fine_amount": 1500, "reputation_impact": -8,
     "skill_xp": {"finance": 14, "street_smarts": 6}, "blocking": False, "offline": True,
     "desc": "Cook the books and hope no audit comes."},
    {"id": "smuggling", "name": "Smuggling Job", "category": "crime", "duration_minutes": 300,
     "reward_min": 500, "reward_max": 1800, "suspicion_gain": 22, "police_risk": 0.33,
     "failure_chance": 0.35, "jail_minutes": 2160, "fine_amount": 2000, "reputation_impact": -12,
     "skill_xp": {"street_smarts": 20, "driving": 8}, "blocking": True, "offline": True,
     "requirements": {"vehicle": "any"}, "desc": "Haul contraband across town. High stakes."},
    {"id": "fraud", "name": "Fraud Scheme", "category": "fraud", "duration_minutes": 180,
     "reward_min": 250, "reward_max": 1000, "suspicion_gain": 16, "police_risk": 0.26,
     "failure_chance": 0.32, "jail_minutes": 1440, "fine_amount": 1200, "reputation_impact": -10,
     "skill_xp": {"technology": 10, "street_smarts": 8}, "blocking": False, "offline": True,
     "desc": "An elaborate con. Don't get traced."},
    {"id": "illegal_gambling", "name": "Illegal Gambling Night", "category": "vice", "duration_minutes": 150,
     "reward_min": -400, "reward_max": 1500, "suspicion_gain": 10, "police_risk": 0.18,
     "failure_chance": 0.45, "jail_minutes": 480, "fine_amount": 400, "reputation_impact": -4,
     "skill_xp": {"street_smarts": 8, "finance": 4}, "blocking": True, "offline": True,
     "desc": "High-stakes back-room poker. You might lose it all."},
    {"id": "bribe", "name": "Bribe Attempt", "category": "fraud", "duration_minutes": 30,
     "reward_min": 0, "reward_max": 0, "suspicion_gain": 6, "police_risk": 0.30,
     "failure_chance": 0.40, "jail_minutes": 1080, "fine_amount": 800, "reputation_impact": -6,
     "skill_xp": {"charisma": 6, "street_smarts": 6}, "blocking": False, "offline": False,
     "lowers_suspicion": 30, "desc": "Pay someone to make your record look cleaner."},
]

RANDOM_EVENTS = [
    {"id": "tip_jar", "scope": "job", "name": "Generous Tip", "weight": 3,
     "effects": {"cash": 25, "mood": 5}, "message": "A customer left a generous tip!"},
    {"id": "tough_shift", "scope": "job", "name": "Tough Shift", "weight": 2,
     "effects": {"stress": 10, "fatigue": 8}, "message": "An exhausting rush wore you out."},
    {"id": "praised", "scope": "job", "name": "Praised by Boss", "weight": 2,
     "effects": {"reputation": 5, "mood": 6}, "message": "Your boss praised your work."},
    {"id": "minor_injury", "scope": "job", "name": "Minor Injury", "weight": 1,
     "effects": {"health": -10, "stress": 6}, "message": "You hurt yourself on the job."},
    {"id": "good_reviews", "scope": "business", "name": "Glowing Reviews", "weight": 3,
     "effects": {"reputation": 8}, "message": "Customers left glowing reviews!"},
    {"id": "bad_reviews", "scope": "business", "name": "Bad Reviews", "weight": 2,
     "effects": {"reputation": -10}, "message": "A wave of bad reviews hit your business."},
    {"id": "viral", "scope": "business", "name": "Viral Popularity", "weight": 1,
     "effects": {"reputation": 15, "cash": 200}, "message": "Your business went viral online!"},
    {"id": "theft", "scope": "business", "name": "Theft", "weight": 1,
     "effects": {"cash": -150}, "message": "Someone stole from your business."},
    {"id": "inspection", "scope": "business", "name": "Inspection", "weight": 1,
     "effects": {"reputation": -4}, "message": "A surprise inspection rattled your staff."},
    {"id": "lucky_find", "scope": "general", "name": "Lucky Find", "weight": 2,
     "effects": {"cash": 30, "mood": 5}, "message": "You found cash on the street!"},
]


EMPLOYEE_ROLES = [
    {"id": "cashier", "label": "Cashier", "wage_min": 70, "wage_max": 110, "is_manager": False, "desc": "Handles the till and customers."},
    {"id": "cook", "label": "Cook", "wage_min": 95, "wage_max": 150, "is_manager": False, "desc": "Prepares the food."},
    {"id": "server", "label": "Server", "wage_min": 70, "wage_max": 105, "is_manager": False, "desc": "Waits tables and serves guests."},
    {"id": "delivery_driver", "label": "Delivery Driver", "wage_min": 85, "wage_max": 135, "is_manager": False, "desc": "Delivers orders across the city."},
    {"id": "cleaner", "label": "Cleaner", "wage_min": 60, "wage_max": 95, "is_manager": False, "desc": "Keeps the place spotless."},
    {"id": "mechanic", "label": "Mechanic", "wage_min": 115, "wage_max": 180, "is_manager": False, "desc": "Repairs vehicles."},
    {"id": "salesperson", "label": "Salesperson", "wage_min": 80, "wage_max": 135, "is_manager": False, "desc": "Drives sales and upsells."},
    {"id": "manager", "label": "Manager", "wage_min": 170, "wage_max": 270, "is_manager": True, "desc": "Runs the business day-to-day, cutting negative events and boosting performance."},
    {"id": "security", "label": "Security", "wage_min": 90, "wage_max": 135, "is_manager": False, "desc": "Deters theft and trouble."},
    {"id": "warehouse_worker", "label": "Warehouse Worker", "wage_min": 75, "wage_max": 115, "is_manager": False, "desc": "Handles stock and logistics."},
    {"id": "customer_support", "label": "Customer Support", "wage_min": 80, "wage_max": 125, "is_manager": False, "desc": "Helps online customers."},
    {"id": "accountant", "label": "Accountant", "wage_min": 120, "wage_max": 185, "is_manager": False, "desc": "Manages the books and taxes."},
    {"id": "trainer", "label": "Trainer", "wage_min": 95, "wage_max": 145, "is_manager": False, "desc": "Coaches gym members."},
    {"id": "animal_care", "label": "Animal Care", "wage_min": 70, "wage_max": 110, "is_manager": False, "desc": "Looks after the animals."},
]

EMPLOYEE_TRAITS = [
    {"id": "hardworking", "label": "Hardworking", "desc": "Boosts revenue, steady morale.", "effects": {"revenue": 0.08, "morale_drift": 0.4}},
    {"id": "lazy", "label": "Lazy", "desc": "Reduces revenue.", "effects": {"revenue": -0.08, "morale_drift": -0.2}},
    {"id": "charismatic", "label": "Charismatic", "desc": "Raises customer satisfaction.", "effects": {"satisfaction": 6, "revenue": 0.04}},
    {"id": "unreliable", "label": "Unreliable", "desc": "Higher quit & sick chance.", "effects": {"revenue": -0.04, "quit": 0.008, "sick": 0.004}},
    {"id": "fast_learner", "label": "Fast Learner", "desc": "Gains skill faster.", "effects": {"learning": 1.8}},
    {"id": "loyal", "label": "Loyal", "desc": "Rarely quits.", "effects": {"quit": -0.01, "morale_drift": 0.3}},
    {"id": "expensive", "label": "Expensive", "desc": "Demands a higher wage.", "effects": {"wage_mult": 1.4, "revenue": 0.03}},
    {"id": "conflict_prone", "label": "Conflict-Prone", "desc": "Drags down morale.", "effects": {"morale_drift": -0.5}},
    {"id": "customer_favorite", "label": "Customer Favorite", "desc": "Big satisfaction & revenue boost.", "effects": {"satisfaction": 10, "revenue": 0.06}},
    {"id": "theft_risk", "label": "Theft Risk", "desc": "May steal from the business.", "effects": {"theft": 0.01}},
    {"id": "efficient", "label": "Efficient", "desc": "Higher revenue & satisfaction.", "effects": {"revenue": 0.07, "satisfaction": 3}},
    {"id": "sickly", "label": "Sickly", "desc": "Often calls in sick.", "effects": {"sick": 0.012}},
]

STAFFING_REQUIREMENTS = [
    {"id": "kiosk", "requirements": [{"role": "cashier", "recommended": 1}]},
    {"id": "delivery_service", "requirements": [{"role": "delivery_driver", "recommended": 2}, {"role": "cashier", "recommended": 1}]},
    {"id": "bistro", "requirements": [{"role": "cook", "recommended": 1}, {"role": "server", "recommended": 1}]},
    {"id": "clothing_store", "requirements": [{"role": "salesperson", "recommended": 1}, {"role": "cashier", "recommended": 1}]},
    {"id": "auto_repair", "requirements": [{"role": "mechanic", "recommended": 2}, {"role": "cashier", "recommended": 1}]},
    {"id": "gym", "requirements": [{"role": "trainer", "recommended": 1}, {"role": "cleaner", "recommended": 1}]},
    {"id": "pet_shop", "requirements": [{"role": "cashier", "recommended": 1}, {"role": "animal_care", "recommended": 1}]},
    {"id": "online_shop", "requirements": [{"role": "customer_support", "recommended": 1}, {"role": "warehouse_worker", "recommended": 1}]},
    {"id": "cleaning_co", "requirements": [{"role": "cleaner", "recommended": 2}]},
    {"id": "real_estate_agency", "requirements": [{"role": "salesperson", "recommended": 2}, {"role": "accountant", "recommended": 1}]},
]

TRAINING_OPTIONS = [
    {"id": "basic_skills", "label": "Basic Skills Workshop", "duration_minutes": 720, "cost": 150,
     "skill_gain": 2, "morale_gain": 5, "loyalty_gain": 3, "fail_chance": 0.15, "desc": "Quick fundamentals (~12h)."},
    {"id": "advanced_skills", "label": "Advanced Training", "duration_minutes": 2880, "cost": 400,
     "skill_gain": 4, "morale_gain": 8, "loyalty_gain": 5, "fail_chance": 0.2, "desc": "Deep skill development (~2 days)."},
    {"id": "customer_service", "label": "Customer Service Course", "duration_minutes": 1440, "cost": 250,
     "skill_gain": 2, "morale_gain": 7, "loyalty_gain": 4, "fail_chance": 0.15, "desc": "Improves service quality (~1 day)."},
    {"id": "leadership", "label": "Leadership Program", "duration_minutes": 2880, "cost": 500,
     "skill_gain": 3, "morale_gain": 6, "loyalty_gain": 9, "fail_chance": 0.25, "desc": "Grooms future managers (~2 days)."},
]

EMPLOYEE_EVENTS = [
    {"id": "ev_raise", "kind": "raise_request", "weight": 3, "severity": "info", "message": "{name} is asking for a raise.", "effects": {}},
    {"id": "ev_fav", "kind": "customer_favorite", "weight": 2, "severity": "success", "message": "{name} has become a customer favorite!", "effects": {"satisfaction": 5, "reputation": 3}},
    {"id": "ev_conflict", "kind": "staff_conflict", "weight": 2, "severity": "warning", "message": "A conflict broke out between staff.", "effects": {"satisfaction": -4}},
    {"id": "ev_great", "kind": "great_review", "weight": 3, "severity": "success", "message": "A customer left a glowing review of your staff!", "effects": {"reputation": 6, "satisfaction": 4}},
    {"id": "ev_bad", "kind": "bad_review", "weight": 2, "severity": "warning", "message": "A customer complained about poor service.", "effects": {"reputation": -8, "satisfaction": -4}},
    {"id": "ev_accident", "kind": "accident", "weight": 1, "severity": "danger", "message": "A workplace accident hurt {name} and cost you money.", "effects": {"cash": -120}},
    {"id": "ev_mgr", "kind": "manager_save", "weight": 2, "severity": "info", "message": "Your manager smoothly handled a crisis.", "effects": {"reputation": 2}},
    {"id": "ev_exp", "kind": "exp_boost", "weight": 2, "severity": "info", "message": "{name} improved through experience.", "effects": {}},
]


# ============================ SOCIAL CONTACTS & RELATIONSHIPS ============================
# NPC archetypes are templates used to spawn per-player contacts.
NPC_ARCHETYPES = [
    {"id": "boss", "label": "Your Manager", "relationship_type": "boss", "category": "work",
     "age_min": 35, "age_max": 60, "start_score": 15, "base_trust": 35, "base_respect": 45, "decay_rate": 0.7,
     "trait_pool": ["demanding", "fair", "ambitious", "moody"], "intro_text": "You started reporting to this manager.",
     "desc": "The person who signs off on your shifts, raises and promotions."},
    {"id": "coworker", "label": "Coworker", "relationship_type": "coworker", "category": "work",
     "age_min": 19, "age_max": 50, "start_score": 22, "base_trust": 30, "base_respect": 30, "decay_rate": 1.1,
     "trait_pool": ["funny", "warm", "flaky", "ambitious", "honest"], "intro_text": "You met them at work.",
     "desc": "A colleague you see most shifts."},
    {"id": "landlord", "label": "Landlord", "relationship_type": "landlord", "category": "housing",
     "age_min": 35, "age_max": 65, "start_score": 12, "base_trust": 25, "base_respect": 30, "decay_rate": 0.6,
     "trait_pool": ["demanding", "fair", "materialistic", "honest"], "intro_text": "You signed a lease with them.",
     "desc": "Holds your deposit and decides whether you stay or go."},
    {"id": "business_contact", "label": "Business Contact", "relationship_type": "business_contact", "category": "business",
     "age_min": 28, "age_max": 60, "start_score": 18, "base_trust": 30, "base_respect": 40, "decay_rate": 0.8,
     "trait_pool": ["ambitious", "materialistic", "honest", "warm"], "intro_text": "A useful contact in the business world.",
     "desc": "Supplier deals, investment tips and introductions for your ventures."},
    {"id": "best_friend", "label": "Best Friend", "relationship_type": "friend", "category": "friend",
     "age_min": 19, "age_max": 45, "start_score": 58, "base_trust": 62, "base_respect": 50, "decay_rate": 0.7,
     "trait_pool": ["warm", "funny", "loyal", "supportive"], "intro_text": "An old, close friend who's always had your back.",
     "desc": "Your ride-or-die. The first call when things go sideways."},
    {"id": "old_friend", "label": "Friend", "relationship_type": "friend", "category": "friend",
     "age_min": 18, "age_max": 50, "start_score": 35, "base_trust": 40, "base_respect": 35, "decay_rate": 1.0,
     "trait_pool": ["funny", "warm", "flaky", "moody", "honest"], "intro_text": "A friend from around town.",
     "desc": "Good company when you make time for them."},
    {"id": "neighbor", "label": "Neighbor", "relationship_type": "friend", "category": "friend",
     "age_min": 20, "age_max": 65, "start_score": 25, "base_trust": 30, "base_respect": 30, "decay_rate": 1.0,
     "trait_pool": ["warm", "honest", "distant", "funny"], "intro_text": "You live near each other.",
     "desc": "A friendly face from the building."},
    {"id": "love_interest", "label": "Love Interest", "relationship_type": "partner", "category": "romance",
     "age_min": 19, "age_max": 45, "start_score": 22, "base_trust": 25, "base_respect": 30, "base_attraction": 32,
     "romance_capable": True, "decay_rate": 1.3, "trait_pool": ["warm", "jealous", "funny", "moody", "materialistic"],
     "intro_text": "Sparks flew the moment you met.", "desc": "Could become something more — if you invest in it."},
    {"id": "shady_dealer", "label": "Shady Contact", "relationship_type": "shady_contact", "category": "underworld",
     "age_min": 22, "age_max": 55, "start_score": 15, "base_trust": 18, "base_respect": 25, "decay_rate": 1.0,
     "trait_pool": ["hot_tempered", "materialistic", "ambitious", "distant"], "intro_text": "You know them from the wrong side of town.",
     "desc": "Connections to risky, lucrative work — and trouble."},
    {"id": "mentor", "label": "Mentor", "relationship_type": "mentor", "category": "work",
     "age_min": 40, "age_max": 70, "start_score": 40, "base_trust": 45, "base_respect": 60, "decay_rate": 0.6,
     "trait_pool": ["honest", "warm", "ambitious", "supportive"], "intro_text": "A wise figure who's taken an interest in you.",
     "desc": "Career advice, references and the occasional door opened."},
    {"id": "sibling", "label": "Sibling", "relationship_type": "family", "category": "family",
     "age_min": 16, "age_max": 55, "start_score": 50, "base_trust": 58, "base_respect": 45, "decay_rate": 0.5,
     "trait_pool": ["loyal", "warm", "moody", "honest", "supportive"], "intro_text": "Family. Always family.",
     "desc": "Blood ties run deep, even when you don't talk for a while."},
    {"id": "customer_regular", "label": "Regular Customer", "relationship_type": "customer", "category": "business",
     "age_min": 20, "age_max": 65, "start_score": 26, "base_trust": 30, "base_respect": 30, "decay_rate": 1.2,
     "trait_pool": ["warm", "demanding", "funny", "materialistic"], "intro_text": "A familiar face who keeps coming back.",
     "desc": "Loyal patrons can become your best word-of-mouth."},
    {"id": "manager", "label": "Industry Manager", "relationship_type": "manager", "category": "business",
     "age_min": 32, "age_max": 60, "start_score": 8, "base_trust": 15, "base_respect": 35, "decay_rate": 0.7,
     "trait_pool": ["ambitious", "fair", "demanding", "honest"], "intro_text": "A sharp operations manager you got talking to.",
     "desc": "A well-connected manager. Build the relationship to negotiate a permanent staff wage discount for your businesses.",
     "perk": {"type": "wage_discount", "step": 0.05, "label": "Staff wage discount"}},
    {"id": "wholesaler", "label": "Wholesale Supplier", "relationship_type": "wholesaler", "category": "business",
     "age_min": 30, "age_max": 62, "start_score": 8, "base_trust": 15, "base_respect": 35, "decay_rate": 0.7,
     "trait_pool": ["materialistic", "ambitious", "honest", "fair"], "intro_text": "A supplier who moves serious volume.",
     "desc": "A bulk supplier. Build the relationship to unlock a permanent material cost discount for your businesses.",
     "perk": {"type": "material_discount", "step": 0.05, "label": "Material cost discount"}},
    {"id": "bar_regular", "label": "Bar Regular", "relationship_type": "friend", "category": "friend",
     "age_min": 21, "age_max": 55, "start_score": 18, "base_trust": 22, "base_respect": 25, "decay_rate": 1.1,
     "trait_pool": ["funny", "warm", "moody", "honest"], "intro_text": "You struck up a conversation over a drink.",
     "desc": "A friendly regular from the bar scene."},
    {"id": "gym_coach", "label": "Gym Coach", "relationship_type": "coach", "category": "friend",
     "age_min": 25, "age_max": 55, "start_score": 15, "base_trust": 25, "base_respect": 40, "decay_rate": 0.8,
     "trait_pool": ["supportive", "ambitious", "honest", "demanding"], "intro_text": "A coach who noticed you at the gym.",
     "desc": "A fitness coach. Good for motivation and mood."},
    {"id": "athlete", "label": "Fellow Athlete", "relationship_type": "friend", "category": "friend",
     "age_min": 19, "age_max": 45, "start_score": 16, "base_trust": 22, "base_respect": 30, "decay_rate": 1.0,
     "trait_pool": ["warm", "funny", "loyal", "ambitious"], "intro_text": "You spot each other at the gym.",
     "desc": "A training partner from the gym."},
]

# NPC categorization for the Location Filter System (tags + numeric attributes 0-100).
# Attributes let admins gate encounters (e.g. social_status > 70 luxury club; legal_standing < 30 hangout).
ARCHETYPE_META = {
    "best_friend":     {"tags": ["Social"],              "social_status": 50, "legal_standing": 65, "wealth": 45},
    "old_friend":      {"tags": ["Social"],              "social_status": 48, "legal_standing": 65, "wealth": 45},
    "sibling":         {"tags": ["Social"],              "social_status": 50, "legal_standing": 68, "wealth": 45},
    "parent":          {"tags": ["Social"],              "social_status": 55, "legal_standing": 75, "wealth": 55},
    "love_interest":   {"tags": ["Social"],              "social_status": 55, "legal_standing": 65, "wealth": 50},
    "neighbor":        {"tags": ["Drifter", "Social"],   "social_status": 45, "legal_standing": 62, "wealth": 40},
    "mentor":          {"tags": ["Corporate", "Social"], "social_status": 70, "legal_standing": 80, "wealth": 65},
    "boss":            {"tags": ["Corporate", "Wealthy"],"social_status": 72, "legal_standing": 78, "wealth": 78},
    "coworker":        {"tags": ["Corporate"],           "social_status": 45, "legal_standing": 70, "wealth": 42},
    "manager":         {"tags": ["Corporate", "Wealthy"],"social_status": 68, "legal_standing": 76, "wealth": 72},
    "wholesaler":      {"tags": ["Corporate", "Wealthy"],"social_status": 62, "legal_standing": 66, "wealth": 76},
    "business_contact":{"tags": ["Corporate"],           "social_status": 60, "legal_standing": 68, "wealth": 65},
    "landlord":        {"tags": ["Wealthy"],             "social_status": 58, "legal_standing": 72, "wealth": 80},
    "customer_regular":{"tags": ["Drifter"],             "social_status": 45, "legal_standing": 65, "wealth": 45},
    "bar_regular":     {"tags": ["Drifter"],             "social_status": 42, "legal_standing": 58, "wealth": 38},
    "gym_coach":       {"tags": ["Fitness"],             "social_status": 60, "legal_standing": 75, "wealth": 52},
    "athlete":         {"tags": ["Fitness"],             "social_status": 55, "legal_standing": 72, "wealth": 46},
    "shady_dealer":    {"tags": ["Criminal"],            "social_status": 35, "legal_standing": 15, "wealth": 45},
}
ARCHETYPE_TAG_OPTIONS = ["Criminal", "Wealthy", "Corporate", "Fitness", "Social", "Drifter"]
for _a in NPC_ARCHETYPES:
    _m = ARCHETYPE_META.get(_a["id"], {"tags": ["Drifter"], "social_status": 50, "legal_standing": 65, "wealth": 45})
    _a.setdefault("tags", _m["tags"])
    _a.setdefault("social_status", _m["social_status"])
    _a.setdefault("legal_standing", _m["legal_standing"])
    _a.setdefault("wealth", _m["wealth"])


SOCIAL_TRAITS = [
    {"id": "warm", "label": "Warm", "desc": "Easy to get along with; relationships hold up well.", "effects": {"success_mod": 0.08, "decay_mult": -0.2}},
    {"id": "distant", "label": "Distant", "desc": "Hard to reach; relationship fades faster.", "effects": {"success_mod": -0.06, "decay_mult": 0.3}},
    {"id": "loyal", "label": "Loyal", "desc": "Sticks around; very slow to drift away.", "effects": {"decay_mult": -0.35, "success_mod": 0.03}},
    {"id": "flaky", "label": "Flaky", "desc": "Unreliable; the bond slips when ignored.", "effects": {"decay_mult": 0.35, "success_mod": -0.04}},
    {"id": "funny", "label": "Funny", "desc": "Great company; interactions tend to land well.", "effects": {"success_mod": 0.07}},
    {"id": "moody", "label": "Moody", "desc": "Unpredictable; interactions are hit or miss.", "effects": {"success_mod": -0.07, "decay_mult": 0.1}},
    {"id": "honest", "label": "Honest", "desc": "Straight shooter; respects sincerity.", "effects": {"success_mod": 0.03}},
    {"id": "materialistic", "label": "Materialistic", "desc": "Values gifts and money over words.", "effects": {"success_mod": -0.03}},
    {"id": "ambitious", "label": "Ambitious", "desc": "Driven; respects status and success.", "effects": {"success_mod": 0.02}},
    {"id": "jealous", "label": "Jealous", "desc": "Possessive in romance; quick to feel slighted.", "effects": {"success_mod": -0.05, "decay_mult": 0.2}},
    {"id": "supportive", "label": "Supportive", "desc": "Always in your corner.", "effects": {"success_mod": 0.06, "decay_mult": -0.25}},
    {"id": "demanding", "label": "Demanding", "desc": "High expectations; harder to please.", "effects": {"success_mod": -0.06}},
    {"id": "fair", "label": "Fair", "desc": "Reasonable and even-handed.", "effects": {"success_mod": 0.04}},
    {"id": "hot_tempered", "label": "Hot-Tempered", "desc": "Volatile; failures sting harder.", "effects": {"success_mod": -0.05, "decay_mult": 0.15}},
]

# kind drives special bonuses; timing is "instant" or "activity"; untargeted actions ignore a contact.
RELATIONSHIP_ACTIONS = [
    {"id": "small_talk", "label": "Small Talk", "kind": "small_talk", "category": "light", "timing": "instant",
     "duration_minutes": 0, "cooldown_minutes": 20, "money_cost": 0, "applies_to": "all", "icon": "MessageCircle",
     "desc": "A quick chat to stay on someone's radar.", "requires": {},
     "success": {"base": 0.92}, "on_success": {"relationship_score": 3, "trust": 1, "p_mood": 2},
     "on_fail": {"relationship_score": 1}, "success_text": "A nice little chat with {name}.", "fail_text": "{name} seemed distracted, but it's something."},
    {"id": "call_text", "label": "Call / Text", "kind": "call_text", "category": "light", "timing": "instant",
     "duration_minutes": 0, "cooldown_minutes": 30, "money_cost": 0, "applies_to": "all", "icon": "Phone",
     "desc": "Reach out and keep the connection warm.", "requires": {},
     "success": {"base": 0.9, "score_factor": 0.05}, "on_success": {"relationship_score": 4, "p_mood": 2},
     "on_fail": {"relationship_score": 1}, "success_text": "You caught up with {name}.", "fail_text": "{name} didn't pick up, but they saw you tried."},
    {"id": "apologize", "label": "Apologize", "kind": "apologize", "category": "repair", "timing": "instant",
     "duration_minutes": 0, "cooldown_minutes": 180, "money_cost": 0, "applies_to": "all", "icon": "HeartHandshake",
     "desc": "Mend a damaged relationship. Works best when you mean it.", "requires": {},
     "success": {"base": 0.5, "score_factor": 0.35, "charisma_factor": 0.2}, "on_success": {"relationship_score": 16, "trust": 6, "p_stress": -5},
     "on_fail": {"relationship_score": -3, "p_stress": 4}, "success_text": "{name} accepted your apology.", "fail_text": "{name} isn't ready to forgive you yet."},
    {"id": "ask_reference", "label": "Ask for a Reference", "kind": "ask_reference", "category": "ask", "timing": "instant",
     "duration_minutes": 0, "cooldown_minutes": 720, "money_cost": 0, "applies_to": ["boss", "coworker", "mentor"], "icon": "Award",
     "desc": "A good word that boosts your reputation and standing at work.", "requires": {"min_score": 35},
     "success": {"base": 0.55, "score_factor": 0.35, "trust_factor": 0.2}, "on_success": {"p_reputation": 6, "p_social_status": 3, "relationship_score": -2},
     "on_fail": {"relationship_score": -3}, "success_text": "{name} vouched for you — your reputation gets a lift.", "fail_text": "{name} declined to put their name on the line."},
    {"id": "hang_out", "label": "Hang Out", "kind": "hang_out", "category": "quality", "timing": "activity",
     "duration_minutes": 90, "cooldown_minutes": 60, "money_cost": 0, "blocking": True,
     "applies_to": ["friend", "coworker", "partner", "family", "mentor"], "icon": "Users",
     "desc": "Spend real quality time together. Great for mood.", "requires": {},
     "success": {"base": 0.86, "score_factor": 0.1}, "on_success": {"relationship_score": 11, "trust": 3, "c_mood": 8, "p_mood": 12, "p_stress": -10},
     "on_fail": {"relationship_score": 3, "p_mood": 4}, "success_text": "A great time hanging out with {name}.", "fail_text": "It was a bit awkward with {name} today."},
    {"id": "help_problem", "label": "Help With a Problem", "kind": "help_problem", "category": "quality", "timing": "activity",
     "duration_minutes": 60, "cooldown_minutes": 180, "money_cost": 0, "blocking": True, "applies_to": "all", "icon": "LifeBuoy",
     "desc": "Show up when it matters. Builds deep trust and respect.", "requires": {"min_score": 20},
     "success": {"base": 0.82, "charisma_factor": 0.1}, "on_success": {"relationship_score": 12, "trust": 8, "respect": 6, "p_stress": 3},
     "on_fail": {"relationship_score": 2, "p_stress": 6}, "success_text": "You helped {name} through a rough patch.", "fail_text": "You tried to help {name}, but it didn't go to plan."},
    {"id": "invite_date", "label": "Invite on a Date", "kind": "invite_date", "category": "romance", "timing": "activity",
     "duration_minutes": 120, "cooldown_minutes": 240, "money_cost": 45, "blocking": True, "romance_only": True,
     "applies_to": ["partner"], "icon": "Heart",
     "desc": "Take them somewhere nice. Builds attraction; can turn things romantic.", "requires": {},
     "success": {"base": 0.8, "score_factor": 0.1, "charisma_factor": 0.1}, "on_success": {"relationship_score": 12, "attraction": 13, "c_mood": 8, "p_mood": 15, "p_stress": -8},
     "on_fail": {"relationship_score": -2, "attraction": -3, "p_mood": -3}, "success_text": "A wonderful date with {name}.", "fail_text": "The date with {name} was a little flat."},
    {"id": "meet_shady", "label": "Meet Up (Lay Low)", "kind": "meet_shady", "category": "underworld", "timing": "activity",
     "duration_minutes": 60, "cooldown_minutes": 240, "money_cost": 0, "blocking": True, "applies_to": ["shady_contact"], "icon": "Skull",
     "desc": "Touch base with your contact to cool off the heat before a job.", "requires": {},
     "success": {"base": 0.82, "trust_factor": 0.15}, "on_success": {"relationship_score": 6, "trust": 6, "p_suspicion": -8},
     "on_fail": {"relationship_score": -3, "p_stress": 5}, "success_text": "{name} put in a word — your next job will be lower-risk for a while.", "fail_text": "{name} blew you off. No favors today."},
    {"id": "network_pro", "label": "Talk Business", "kind": "network_pro", "category": "network", "timing": "activity",
     "duration_minutes": 60, "cooldown_minutes": 120, "money_cost": 0, "blocking": True,
     "applies_to": ["manager", "wholesaler", "business_contact"], "icon": "Handshake",
     "desc": "Build a professional relationship. Deepen trust to unlock a permanent business perk (wage or material discount).",
     "requires": {}, "success": {"base": 0.75, "score_factor": 0.15, "trust_factor": 0.2, "charisma_factor": 0.2},
     "on_success": {"relationship_score": 9, "trust": 8, "respect": 4},
     "on_fail": {"relationship_score": 2, "trust": 1}, "success_text": "A productive talk with {name} — the professional bond grows.",
     "fail_text": "{name} kept it strictly polite. No progress today."},
]


# Meeting places (Socials 3.0). Fully DB-driven & admin-editable: each location defines who you
# can meet (npcs) and with what weight. See /app/docs/SOCIAL_SYSTEM_LOGIC.md.
LOCATIONS = [
    {"id": "loc_bar", "name": "The Neon Tap", "category": "bar", "icon": "Beer", "active": True, "order": 1,
     "desc": "A busy downtown bar. A chance to meet regulars, managers or suppliers over a drink.",
     "money_cost": 25, "duration_minutes": 90, "cooldown_minutes": 120, "requires_job": False,
     "suspicion_gain": 0, "success_base": 0.72, "charisma_factor": 0.35,
     "npcs": [{"archetype_id": "bar_regular", "weight": 0.5}, {"archetype_id": "manager", "weight": 0.25}, {"archetype_id": "wholesaler", "weight": 0.25}]},
    {"id": "loc_gym", "name": "Iron Temple Gym", "category": "gym", "icon": "Dumbbell", "active": True, "order": 2,
     "desc": "Train and socialize. A chance to meet a fellow athlete or a coach.",
     "money_cost": 15, "duration_minutes": 90, "cooldown_minutes": 120, "requires_job": False,
     "suspicion_gain": 0, "success_base": 0.75, "charisma_factor": 0.3,
     "npcs": [{"archetype_id": "athlete", "weight": 0.6}, {"archetype_id": "gym_coach", "weight": 0.4}]},
    {"id": "loc_work", "name": "Around the Workplace", "category": "work", "icon": "Briefcase", "active": True, "order": 3,
     "desc": "Chat with people at your job. A chance to meet colleagues or a manager. Requires a job.",
     "money_cost": 0, "duration_minutes": 60, "cooldown_minutes": 120, "requires_job": True,
     "suspicion_gain": 0, "success_base": 0.78, "charisma_factor": 0.3,
     "npcs": [{"archetype_id": "coworker", "weight": 0.65}, {"archetype_id": "manager", "weight": 0.35}]},
    {"id": "loc_streets", "name": "The Backstreets", "category": "street", "icon": "Skull", "active": True, "order": 4,
     "desc": "The wrong side of town. Risky — a chance to meet a Shady Contact who opens the door to the Underworld.",
     "money_cost": 0, "duration_minutes": 90, "cooldown_minutes": 180, "requires_job": False,
     "suspicion_gain": 3, "success_base": 0.6, "charisma_factor": 0.25,
     "include_filtered": True, "category_whitelist": ["Criminal"], "min_attrs": {}, "max_attrs": {"legal_standing": 40}, "filter_weight": 1.0,
     "npcs": [{"archetype_id": "shady_dealer", "weight": 0.7}, {"archetype_id": "bar_regular", "weight": 0.3}]},
    {"id": "loc_park", "name": "Riverside Park", "category": "park", "icon": "Trees", "active": True, "order": 5,
     "desc": "A relaxed public park. Meet friendly faces and unwind.",
     "money_cost": 0, "duration_minutes": 60, "cooldown_minutes": 120, "requires_job": False,
     "suspicion_gain": 0, "success_base": 0.7, "charisma_factor": 0.35,
     "npcs": [{"archetype_id": "bar_regular", "weight": 0.6}, {"archetype_id": "athlete", "weight": 0.4}]},
    {"id": "loc_club", "name": "The Platinum Lounge", "category": "club", "icon": "Wine", "active": True, "order": 6,
     "desc": "An exclusive members' club. Only the wealthy and well-connected get through the door.",
     "money_cost": 120, "duration_minutes": 90, "cooldown_minutes": 180, "requires_job": False,
     "suspicion_gain": 0, "success_base": 0.7, "charisma_factor": 0.4,
     "include_filtered": True, "category_whitelist": ["Wealthy", "Corporate"], "min_attrs": {"social_status": 60}, "max_attrs": {}, "filter_weight": 1.0,
     "npcs": []},
]

GIFT_TYPES = [
    {"id": "coffee_gift", "label": "Coffee & Pastry", "cost": 10, "icon": "Coffee",
     "on_give": {"relationship_score": 4, "c_mood": 4}, "desc": "A small, friendly gesture."},
    {"id": "flowers", "label": "Bouquet of Flowers", "cost": 25, "icon": "Flower",
     "on_give": {"relationship_score": 6, "attraction": 8, "c_mood": 6}, "desc": "Classic and romantic."},
    {"id": "thoughtful_book", "label": "Thoughtful Book", "cost": 30, "icon": "BookOpen",
     "on_give": {"relationship_score": 7, "respect": 5, "c_mood": 5}, "desc": "Shows you really know them."},
    {"id": "dinner_voucher", "label": "Dinner Voucher", "cost": 60, "icon": "UtensilsCrossed",
     "on_give": {"relationship_score": 10, "trust": 4, "attraction": 6, "c_mood": 8}, "desc": "A generous treat."},
    {"id": "cash_envelope", "label": "Cash Envelope", "cost": 100, "icon": "Banknote",
     "on_give": {"relationship_score": 8, "trust": -2}, "desc": "Money talks — but it's a little impersonal."},
    {"id": "luxury_watch", "label": "Luxury Watch", "cost": 400, "icon": "Watch",
     "on_give": {"relationship_score": 18, "respect": 10, "attraction": 10, "c_mood": 10}, "desc": "An unforgettable, high-status gift."},
]

SOCIAL_EVENTS = [
    {"id": "se_friend_help", "kind": "friend_help", "relationship_type": "friend", "weight": 3, "severity": "success",
     "message": "{name} helped you out with something — good friends are gold.", "effects": {"relationship_score": 5, "interact": True}, "player_effects": {"mood": 5}},
    {"id": "se_coworker_invite", "kind": "coworker_invite", "relationship_type": "coworker", "weight": 3, "severity": "info",
     "message": "{name} invited you out after work.", "effects": {"relationship_score": 4, "interact": True}, "player_effects": {"mood": 4, "stress": -3}},
    {"id": "se_boss_praise", "kind": "boss_praise", "relationship_type": "boss", "weight": 2, "severity": "success",
     "message": "Your boss {name} praised your work in front of everyone.", "effects": {"relationship_score": 6, "respect": 4, "interact": True}, "player_effects": {"reputation": 4, "mood": 5}},
    {"id": "se_landlord_complaint", "kind": "landlord_complaint", "relationship_type": "landlord", "weight": 2, "severity": "warning",
     "message": "Your landlord {name} complained about noise and late rent.", "effects": {"relationship_score": -6}, "player_effects": {"stress": 5}},
    {"id": "se_partner_upset", "kind": "partner_upset", "relationship_type": "partner", "weight": 2, "severity": "warning",
     "message": "{name} is upset that you've been so distant lately.", "effects": {"relationship_score": -8, "attraction": -5}, "player_effects": {"stress": 8, "mood": -6}},
    {"id": "se_shady_offer", "kind": "shady_offer", "relationship_type": "shady_contact", "weight": 2, "severity": "info",
     "message": "{name} hinted at a lucrative but risky job if you're interested.", "effects": {"trust": 3}, "player_effects": {"criminal_suspicion": 3}},
    {"id": "se_business_deal", "kind": "business_deal", "relationship_type": "business_contact", "weight": 2, "severity": "success",
     "message": "{name} threw a sweet supplier deal your way.", "effects": {"relationship_score": 5, "interact": True}, "player_effects": {"cash": 120, "mood": 4}},
    {"id": "se_friend_borrow", "kind": "friend_borrow", "relationship_type": "friend", "weight": 2, "severity": "info",
     "message": "{name} asked to borrow a little money. You helped out.", "effects": {"relationship_score": 6, "trust": 4, "interact": True}, "player_effects": {"cash": -80}},
    {"id": "se_argument", "kind": "argument", "relationship_type": "any", "weight": 2, "severity": "warning",
     "message": "You and {name} got into an argument.", "effects": {"relationship_score": -7}, "player_effects": {"stress": 6, "mood": -5}},
    {"id": "se_improve", "kind": "improve", "relationship_type": "any", "weight": 2, "severity": "success",
     "message": "You and {name} grew closer out of the blue.", "effects": {"relationship_score": 6, "trust": 3, "interact": True}, "player_effects": {"mood": 4}},
    {"id": "se_family_checkin", "kind": "family_checkin", "relationship_type": "family", "weight": 2, "severity": "success",
     "message": "{name} called just to check in on you.", "effects": {"relationship_score": 5, "interact": True}, "player_effects": {"mood": 6, "stress": -4}},
    {"id": "se_mentor_advice", "kind": "mentor_advice", "relationship_type": "mentor", "weight": 2, "severity": "info",
     "message": "Your mentor {name} shared some valuable advice.", "effects": {"relationship_score": 4, "respect": 3, "interact": True}, "player_effects": {"mood": 3}},
]


MARKET_ASSETS = [
    # --- Stocks (open market, traded in the Bank) ---
    {"id": "stk_kael", "symbol": "KAEL", "name": "KaelCorp Industries", "kind": "stock", "base_price": 145.0, "price": 145.0, "prev_price": 145.0, "history": [145.0], "desc": "Blue-chip conglomerate. Steady, low volatility."},
    {"id": "stk_nova", "symbol": "NOVA", "name": "Nova Systems", "kind": "stock", "base_price": 82.0, "price": 82.0, "prev_price": 82.0, "history": [82.0], "desc": "Consumer tech. Balanced growth."},
    {"id": "stk_helx", "symbol": "HELX", "name": "Helix Biotech", "kind": "stock", "base_price": 310.0, "price": 310.0, "prev_price": 310.0, "history": [310.0], "desc": "Biotech. Higher risk, higher upside."},
    {"id": "stk_orb", "symbol": "ORB", "name": "Orbit Logistics", "kind": "stock", "base_price": 47.0, "price": 47.0, "prev_price": 47.0, "history": [47.0], "desc": "Freight & logistics. Affordable entry."},
    # --- Crypto (Underworld-gated, traded in the Underworld) ---
    {"id": "cry_btk", "symbol": "BTK", "name": "BitKoin", "kind": "crypto", "base_price": 32000.0, "price": 32000.0, "prev_price": 32000.0, "history": [32000.0], "desc": "The original. Volatile store of value."},
    {"id": "cry_etk", "symbol": "ETK", "name": "EtherKoin", "kind": "crypto", "base_price": 2100.0, "price": 2100.0, "prev_price": 2100.0, "history": [2100.0], "desc": "Smart-contract chain. Very volatile."},
    {"id": "cry_kld", "symbol": "KLD", "name": "KaelChain", "kind": "crypto", "base_price": 8.5, "price": 8.5, "prev_price": 8.5, "history": [8.5], "desc": "Local upstart token. Extreme swings."},
    {"id": "cry_dgz", "symbol": "DGZ", "name": "DogeZ", "kind": "crypto", "base_price": 0.42, "price": 0.42, "prev_price": 0.42, "history": [0.42], "desc": "Meme coin. Pure degeneracy."},
]


CHARACTER_BACKGROUNDS = [
    {"id": "drifter", "label": "Drifter", "order": 1, "active": True,
     "desc": "You've lived on the edge. Street-smart but broke.",
     "cash": 120, "bank": 40, "debt": 0,
     "stats": {"health": 100, "energy": 100, "fatigue": 0, "hunger": 20, "mood": 70, "stress": 10},
     "skills": {"street_smarts": 4, "fitness": 2}, "inventory": {}},
    {"id": "graduate", "label": "Fresh Graduate", "order": 2, "active": True,
     "desc": "Educated and ambitious, but in debt and inexperienced.",
     "cash": 80, "bank": 150, "debt": 200,
     "stats": {"health": 100, "energy": 100, "fatigue": 0, "hunger": 20, "mood": 70, "stress": 15},
     "skills": {"studying": 4, "finance": 2, "technology": 2}, "inventory": {}},
    {"id": "hustler", "label": "Hustler", "order": 3, "active": True,
     "desc": "A natural salesperson with charm and big dreams.",
     "cash": 200, "bank": 60, "debt": 0,
     "stats": {"health": 100, "energy": 100, "fatigue": 0, "hunger": 20, "mood": 75, "stress": 10},
     "skills": {"sales": 4, "charisma": 3}, "inventory": {}},
    {"id": "worker", "label": "Blue Collar", "order": 4, "active": True,
     "desc": "Hard-working and reliable, used to long shifts.",
     "cash": 150, "bank": 120, "debt": 0,
     "stats": {"health": 100, "energy": 100, "fatigue": 0, "hunger": 20, "mood": 70, "stress": 10},
     "skills": {"fitness": 3, "crafting": 3, "driving": 1}, "inventory": {}},
    {"id": "cook", "label": "Line Cook", "order": 5, "active": True,
     "desc": "You know your way around a kitchen.",
     "cash": 130, "bank": 90, "debt": 0,
     "stats": {"health": 100, "energy": 100, "fatigue": 0, "hunger": 20, "mood": 70, "stress": 10},
     "skills": {"cooking": 4, "management": 1}, "inventory": {}},
]


from journey_content import JOURNEY_GOALS, STORY_ARCS, CITY_EVENTS

CONTENT_MAP = {
    "journey_goals": ("journey_goals", JOURNEY_GOALS),
    "story_arcs": ("story_arcs", STORY_ARCS),
    "city_events": ("city_events", CITY_EVENTS),
    "jobs": ("jobs", JOBS),
    "actions": ("actions", ACTIONS),
    "courses": ("courses", COURSES),
    "items": ("items", ITEMS),
    "housing": ("housing", HOUSING),
    "vehicles": ("vehicles", VEHICLES),
    "business_types": ("business_types", BUSINESS_TYPES),
    "illegal_actions": ("illegal_actions", ILLEGAL_ACTIONS),
    "random_events": ("random_events", RANDOM_EVENTS),
    "employee_roles": ("employee_roles", EMPLOYEE_ROLES),
    "employee_traits": ("employee_traits", EMPLOYEE_TRAITS),
    "staffing_requirements": ("staffing_requirements", STAFFING_REQUIREMENTS),
    "training_options": ("training_options", TRAINING_OPTIONS),
    "employee_events": ("employee_events", EMPLOYEE_EVENTS),
    "npc_archetypes": ("npc_archetypes", NPC_ARCHETYPES),
    "social_traits": ("social_traits", SOCIAL_TRAITS),
    "relationship_actions": ("relationship_actions", RELATIONSHIP_ACTIONS),
    "gift_types": ("gift_types", GIFT_TYPES),
    "social_events": ("social_events", SOCIAL_EVENTS),
    "market_assets": ("market_assets", MARKET_ASSETS),
    "locations": ("locations", LOCATIONS),
    "city_shops": ("city_shops", CITY_SHOPS),
    "job_sectors": ("job_sectors", JOB_SECTORS),
    "vehicle_categories": ("vehicle_categories", VEHICLE_CATEGORIES),
    "character_backgrounds": ("character_backgrounds", CHARACTER_BACKGROUNDS),
}


from realm_content import convert_defaults, REALM_RANKS, FACTIONS, EXPEDITIONS, COMBAT_ITEMS
LEGACY_DEFAULTS = convert_defaults(CONTENT_MAP)
ITEMS.extend(COMBAT_ITEMS)
CITY_SHOPS[-1]["items_config"].update({item["id"]: {"capacity": 20, "price_pct": 100} for item in COMBAT_ITEMS})
CONTENT_MAP.update({"realm_ranks": ("realm_ranks", REALM_RANKS), "factions": ("factions", FACTIONS),
                    "expeditions": ("expeditions", EXPEDITIONS)})


from world_content import WORLD_CONTENT
CONTENT_MAP.update(WORLD_CONTENT)


async def seed_content(db):
    established = await db.config.find_one({"id": "global"}) is not None
    new_collections = {"journey_goals", "story_arcs", "city_events", "realm_ranks", "factions", "expeditions"} | set(WORLD_CONTENT)
    for ctype, (coll, data) in CONTENT_MAP.items():
        # A seed receipt preserves an intentionally empty Owner collection.
        await db[coll].create_index("id", unique=True)
        if not await db.content_seeds.find_one({"_id": ctype}):
            if await db[coll].count_documents({}) == 0 and (not established or ctype in new_collections):
                from copy import deepcopy
                for doc in data:
                    await db[coll].update_one({"id": doc["id"]}, {"$setOnInsert": deepcopy(doc)}, upsert=True)
            await db.content_seeds.update_one({"_id": ctype}, {"$set": {"seeded": True}}, upsert=True)
        continue
    from realm_migration import migrate_realm
    await migrate_realm(db, LEGACY_DEFAULTS, CONTENT_MAP)
    # New equipment is introduced once, independently of the legacy items collection.
    if not await db.content_seeds.find_one({"_id": "realm_equipment_v1"}):
        from copy import deepcopy
        for item in COMBAT_ITEMS:
            await db.items.update_one({"id": item["id"]}, {"$setOnInsert": deepcopy(item)}, upsert=True)
        await db.content_seeds.update_one({"_id": "realm_equipment_v1"}, {"$set": {"seeded": True}}, upsert=True)
    cfg = await db.config.find_one({"id": "global"})
    from game_models import DEFAULT_CONFIG
    from datetime import datetime, timezone
    if not cfg:
        base = {**DEFAULT_CONFIG, "world_start_real": datetime.now(timezone.utc).isoformat()}
        await db.config.insert_one(base)
    else:
        patch = {}
        if "social" not in cfg:
            patch["social"] = DEFAULT_CONFIG["social"]
        if "tuning" not in cfg:
            patch["tuning"] = DEFAULT_CONFIG["tuning"]
        if not cfg.get("world_start_real"):
            patch["world_start_real"] = datetime.now(timezone.utc).isoformat()
            patch["world_start_game"] = cfg.get("world_start_game") or DEFAULT_CONFIG["world_start_game"]
        if patch:
            await db.config.update_one({"id": "global"}, {"$set": patch})
