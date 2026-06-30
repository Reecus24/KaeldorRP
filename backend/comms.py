"""Kaeldor RPG - multiplayer communication helpers (world chat + player messaging).

Polling-based (no websockets). Stores world_chat and messages collections.
Device gates: SMS needs a smartphone in inventory, email needs a laptop.
"""
import re
from datetime import timedelta
from game_models import now_utc

# Lightweight profanity filter placeholder (admin can extend). Masks whole words.
PROFANITY = ["fuck", "shit", "bitch", "asshole", "bastard", "cunt", "dick", "slut"]

DEVICE_FOR = {"sms": "smartphone", "email": "laptop"}


def clean_text(text):
    out = text or ""
    for w in PROFANITY:
        out = re.sub(rf"(?i)\b{re.escape(w)}\b", "*" * len(w), out)
    return out


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
