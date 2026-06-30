"""Kaeldor RPG - core data models, defaults and helpers."""
import uuid
from datetime import datetime, timezone


def now_utc():
    return datetime.now(timezone.utc)


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


SKILLS = [
    "sales", "cooking", "management", "driving", "charisma", "fitness",
    "technology", "crafting", "creativity", "finance", "studying", "street_smarts",
]

NEED_STATS = ["energy", "fatigue", "hunger", "hygiene", "mood", "stress", "health"]

# Character creation backgrounds
BACKGROUNDS = {
    "drifter": {
        "label": "Drifter",
        "desc": "You've lived on the edge. Street-smart but broke.",
        "cash": 120, "bank": 40,
        "skills": {"street_smarts": 4, "fitness": 2},
    },
    "graduate": {
        "label": "Fresh Graduate",
        "desc": "Educated and ambitious, but in debt and inexperienced.",
        "cash": 80, "bank": 150, "debt": 200,
        "skills": {"studying": 4, "finance": 2, "technology": 2},
    },
    "hustler": {
        "label": "Hustler",
        "desc": "A natural salesperson with charm and big dreams.",
        "cash": 200, "bank": 60,
        "skills": {"sales": 4, "charisma": 3},
    },
    "worker": {
        "label": "Blue Collar",
        "desc": "Hard-working and reliable, used to long shifts.",
        "cash": 150, "bank": 120,
        "skills": {"fitness": 3, "crafting": 3, "driving": 1},
    },
    "cook": {
        "label": "Line Cook",
        "desc": "You know your way around a kitchen.",
        "cash": 130, "bank": 90,
        "skills": {"cooking": 4, "management": 1},
    },
}


def new_player(user_id, name, background):
    now = now_utc()
    bg = BACKGROUNDS.get(background, BACKGROUNDS["drifter"])
    skills = {s: {"level": 1, "xp": 0} for s in SKILLS}
    for s, lvl in bg.get("skills", {}).items():
        if s in skills:
            skills[s]["level"] = 1 + lvl
    return {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "name": name,
        "background": background,
        "level": 1,
        "xp": 0,
        "cash": float(bg.get("cash", 100)),
        "bank": float(bg.get("bank", 0)),
        "debt": float(bg.get("debt", 0)),
        "energy": 100.0, "fatigue": 0.0, "hunger": 20.0, "hygiene": 90.0,
        "mood": 70.0, "stress": 10.0, "health": 100.0,
        "reputation": 50.0, "legal_reputation": 75.0,
        "criminal_suspicion": 0.0, "social_status": 10.0,
        "skills": skills,
        "job": None,
        "housing": {"id": "studio_tiny", "owned": False, "since": now.isoformat()},
        "vehicles": [],
        "education": [],
        "inventory": {},
        "current_activity": None,
        "status": "free",
        "jail_until": None,
        "hospital_until": None,
        "cooldowns": {},
        "criminal_record": [],
        "stats_meta": {
            "shifts_worked": 0, "actions_done": 0, "crimes_committed": 0,
            "times_jailed": 0, "courses_done": 0,
        },
        "last_resolved_at": now.isoformat(),
        "created_at": now.isoformat(),
    }


DEFAULT_CONFIG = {
    "id": "global",
    # time_scale = game minutes that pass per 1 real minute.
    # 12 => 1 game hour (60 min) passes every 5 real minutes (v1 default).
    # Set to 1 for true real-time (1 game hour = 1 real hour).
    "time_scale": 12.0,
    "decay": {
        "hunger": 3.2,        # hunger rises per game hour
        "hygiene": 1.8,       # hygiene falls per game hour
        "energy_awake": 2.4,  # energy falls per game hour while awake
        "fatigue_awake": 1.8, # fatigue rises per game hour while awake
        "stress_relax": 1.2,  # stress drifts down per game hour when idle
        "mood_baseline": 60.0,
    },
    "economy": {
        "loan_interest_daily": 0.015,   # per game day on debt
        "max_loan_multiplier": 3.0,     # loan cap vs net worth-ish
        "bail_per_minute": 0.5,         # cost to bail out per remaining game minute
        "hospital_treat_cost": 150.0,
    },
    "xp": {
        "skill_per_level": 120,         # base xp per skill level
        "player_per_level": 250,        # base xp per player level
    },
}
