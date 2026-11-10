"""Kaeldor RPG - multiplayer communication helpers (world chat + player messaging).

Polling-based (no websockets). Stores world_chat and messages collections.
Device gates: SMS needs a courier seal in inventory, email needs a scribe's kit.
"""
import re
from datetime import timedelta
from game_models import now_utc

# Lightweight profanity filter placeholder (admin can extend). Masks whole words.
PROFANITY = ["fuck", "shit", "bitch", "asshole", "bastard", "cunt", "dick", "slut"]
_PROFANITY_RE = re.compile(r"(?i)\b(" + "|".join(re.escape(w) for w in PROFANITY) + r")\b")

DEVICE_FOR = {"sms": "smartphone", "email": "laptop"}


def clean_text(text):
    if not text:
        return ""
    return _PROFANITY_RE.sub(lambda m: "*" * len(m.group(0)), text)


def has_device(p, channel):
    return DEVICE_FOR.get(channel) in (p.get("inventory") or {})


def sms_thread_id(a, b):
    lo, hi = sorted([a, b])
    return f"sms:{lo}:{hi}"


def is_online(p, cfg):
    last = p.get("last_seen")
    if not last:
        return False
    try:
        from game_engine import parse_dt
        dt = parse_dt(last)
        window = cfg.get("comms", {}).get("online_window_minutes", 3)
        return dt and (now_utc() - dt) <= timedelta(minutes=window)
    except Exception:
        return False
