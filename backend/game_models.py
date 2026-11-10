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

NEED_STATS = ["energy", "fatigue", "hunger", "mood", "stress", "health"]

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


def new_player(user_id, name, background, bg=None):
    now = now_utc()
    # bg is the character_backgrounds DB doc when available; fall back to the hardcoded defaults.
    if bg is None:
        bg = BACKGROUNDS.get(background) or BACKGROUNDS["drifter"]
    skills = {s: {"level": 1, "xp": 0} for s in SKILLS}
    for s, lvl in (bg.get("skills") or {}).items():
        if s in skills:
            skills[s]["level"] = 1 + int(lvl)
    st = bg.get("stats") or {}
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
        "energy": float(st.get("energy", 100.0)), "fatigue": float(st.get("fatigue", 0.0)),
        "hunger": float(st.get("hunger", 20.0)), "mood": float(st.get("mood", 70.0)),
        "stress": float(st.get("stress", 10.0)), "health": float(st.get("health", 100.0)),
        "reputation": 50.0, "legal_reputation": 75.0,
        "criminal_suspicion": 0.0, "social_status": 10.0,
        "skills": skills,
        "job": None,
        "housing": {"id": "studio_tiny", "owned": False, "since": now.isoformat()},
        "vehicles": [],
        "education": [],
        "inventory": {k: int(v) for k, v in (bg.get("inventory") or {}).items() if int(v) > 0},
        "equipment": {},
        "equip_bonus": {},
        "portfolio": {},
        "current_activity": None,
        "registered_shift": None,
        "status": "free",
        "jail_until": None,
        "hospital_until": None,
        "cooldowns": {},
        "credit_missed": 0,
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
    "journey": {"max_active_stories": 3, "city_events_enabled": True},
    "business_comfort": {
        "default_reserve_days": 1.0,
        "max_reserve_days": 30.0,
        "stock_warning_days": 0.5,
        "finished_stock_days": 1.0,
    },
    # time_scale = game minutes that pass per 1 real minute.
    # 1  => TRUE REAL-TIME (1 game hour = 1 real hour). This is the default.
    # 12 => accelerated test mode (1 game hour = 5 real minutes) for balancing.
    "time_scale": 1.0,
    "decay": {
        "hunger": 3.2,        # hunger rises per game hour
        "energy_awake": 2.4,  # energy falls per game hour while awake
        "fatigue_awake": 1.8, # fatigue rises per game hour while awake
        "stress_relax": 1.2,  # stress drifts down per game hour when idle
        "mood_baseline": 60.0,
    },
    "needs": {
        "health_warning_threshold": 35.0,
        "mood_warning_threshold": 25.0,
        "hunger_damage_threshold": 80.0,
        "hunger_health_loss_per_hour": 1.4,
        "hunger_mood_loss_per_hour": 1.0,
        "fatigue_damage_threshold": 80.0,
        "fatigue_health_loss_per_hour": 0.6,
        "stress_damage_threshold": 80.0,
        "stress_health_loss_per_hour": 0.8,
        "stress_mood_loss_per_hour": 1.0,
        "low_energy_threshold": 15.0,
        "low_energy_stress_per_hour": 1.0,
        "regen_max_hunger": 80.0,
        "regen_max_fatigue": 85.0,
        "regen_max_stress": 85.0,
        "health_regen_per_hour": 0.8,
        "mood_recovery_per_hour": 0.5,
        "mood_fade_per_hour": 0.3,
        "mood_upper_margin": 20.0,
        "student_welfare_enabled": True,
    },
    "hospital": {
        "duration_minutes": 360.0,
        "admission_health": 1.0,
        "discharge_health": 60.0,
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
    "employment": {
        "npc_app_base_minutes": 10,     # base real-time delay before an NPC application resolves
        "npc_app_tier_minutes": 12,     # extra delay per job tier
        "offer_expiry_hours": 24,       # how long an accepted NPC offer stays open
        "player_base_shift_wage": 60,   # baseline per-shift wage for player-owned business jobs
        "player_shift_contribution": 90,  # base business value a player shift produces (x performance)
        "wage_min_mult": 0.7,
        "wage_max_mult": 1.85,
    },
    # ADMIN SANDBOX live-tunable knobs (see /app/docs/ADMIN_SANDBOX.md). Engine reads these each tick.
    "tuning": {
        "upgrade_days": 7,               # in-game days an upgrade takes (1-30)
        "marketing_days": 3,             # in-game days a marketing campaign runs (1-14)
        "raise_cooldown_days": 7,        # min in-game days between NPC wage-raise requests (1-30)
        "satisfaction_mult_min": 0.85,   # production multiplier at 0 satisfaction
        "satisfaction_mult_max": 1.0,    # production multiplier at 100 satisfaction
        "reputation_mult_min": 0.5,      # demand multiplier at 0 reputation
        "reputation_mult_max": 1.0,      # demand multiplier at 100 reputation
        "worker_cond_min": 0.85,         # NPC productivity condition floor (effectiveness->production)
        "worker_cond_max": 1.05,         # NPC productivity condition ceiling
        "accident_eff_threshold": 0.55,  # below this effectiveness, work-injury risk applies
        "accident_chance": 0.30,         # chance of injury per shift when below the threshold
        # progressive income-tax brackets on job wages: [gross_up_to (null = top), rate]
        "tax_brackets": [[100, 0.10], [250, 0.15], [None, 0.22]],
        # financial markets — per-real-hour geometric random walk (1 game hr = 1 real hr)
        "stock_drift": 0.0015,        # expected stock return per hour (0.15%)
        "stock_volatility": 0.03,     # stock hourly volatility (3%)
        "crypto_drift": 0.004,        # expected crypto return per hour (0.4%)
        "crypto_volatility": 0.09,    # crypto hourly volatility (9%)
        # player progression
        "skill_decay_per_hour": 0.35,  # skill XP lost per idle game-hour for skills above L2 (0 = disable)
        # criminal suspicion
        "suspicion_decay_per_hour": 1.5,  # suspicion lost per clean game-hour (0 = never cools down)
        "suspicion_gain_mult": 1.0,       # multiplier on suspicion gained from illegal acts
        # proactive policing: base per-game-hour chance of a police stop, scaled by how far below 40
        # the player's legal_standing sits (0 = disable proactive stops)
        "police_event_per_hour": 0.03,
    },
}


# ---- ADMIN SANDBOX live tuning cache (refreshed on every get_config) ----
TUNE = {}


def apply_tuning(cfg):
    """Refresh the shared tuning cache from the live config doc. Engine functions read TUNE."""
    t = (cfg or {}).get("tuning") or {}
    base = DEFAULT_CONFIG["tuning"]
    for k, v in base.items():
        TUNE[k] = t.get(k, v)
    return TUNE


# Daily-summary ledger: signed per-day money buckets (expenses stored negative).
LEDGER_KEYS = [
    "story_income", "story_costs",
    "wages_earned", "business_income", "crime_income", "social_income", "savings_interest",   # income (+)
    "rent", "bills", "vehicle_costs", "fines", "medical", "living_costs", "taxes",  # expenses (-)
    "loan_interest", "business_pnl", "employee_wages",      # info / debt
]


def empty_ledger():
    d = {k: 0.0 for k in LEDGER_KEYS}
    d["warnings"] = []
    d["rel_events"] = []
    return d
