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
        "day_ledger": empty_ledger(),
        "last_summary_day": None,
        "last_resolved_at": now.isoformat(),
        "created_at": now.isoformat(),
    }


DEFAULT_CONFIG = {
    "id": "global",
    # time_scale = game minutes that pass per 1 real minute.
    # 1  => TRUE REAL-TIME (1 game hour = 1 real hour). This is the default.
    # 12 => accelerated test mode (1 game hour = 5 real minutes) for balancing.
    "time_scale": 1.0,
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
    "employees": {
        "applicant_interval_hours": 6,  # real hours between new applicants per business
        "max_applicants": 6,
        "recruit_cost": 250,            # cost to recruit a premium applicant
    },
    "social": {
        "decay_per_day": 3.0,           # base relationship-score decay/real-day when ignored
        "close_decay_mult": 0.4,        # close bonds decay this much slower
        "angry_worsen_per_day": 1.5,    # damaged relationships worsen if left unaddressed
        "decay_grace_hours": 8,         # real hours of grace before decay begins
        "event_chance_per_day": 4.0,    # expected random social events per real day
        "mood_factor": 0.35,            # how strongly your social life nudges mood/hour
        "stress_factor": 0.25,          # how strongly your social life relieves stress/hour
        "fire_risk_per_day": 0.15,      # chance/real-day of being fired by an angry boss
        "evict_warn_per_day": 0.25,     # chance/real-day of an angry landlord eviction warning
        "partner_cost_per_day": 25,     # daily life cost of a romantic partner
        "shady_buff_hours": 6,          # how long a shady contact lowers your crime risk
        "shady_buff_mult": 0.65,        # police-risk multiplier while the buff is active
    },
    # World clock anchors (set at first seed). game_now = world_start_game + elapsed_real * time_scale.
    "world_start_real": None,
    "world_start_game": "2050-01-01T08:00:00+00:00",
    "comms": {
        "chat_cooldown_seconds": 4,     # anti-spam: min seconds between world-chat messages
        "chat_max_length": 280,
        "online_window_minutes": 3,     # a player is "online" if active within this window
        "message_max_length": 2000,
    },
}


# Daily-summary ledger: signed per-day money buckets (expenses stored negative).
LEDGER_KEYS = [
    "wages_earned", "crime_income", "social_income",       # income (+)
    "rent", "bills", "vehicle_costs", "fines", "medical", "living_costs",  # expenses (-)
    "loan_interest", "business_pnl", "employee_wages",      # info / debt
]


def empty_ledger():
    d = {k: 0.0 for k in LEDGER_KEYS}
    d["warnings"] = []
    d["rel_events"] = []
    return d
