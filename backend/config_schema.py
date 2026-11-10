"""Owner settings: additive defaults, lossless partial edits and structural validation.

Unknown keys are deliberately retained so new mechanics and content are editable without
adding another hard-coded allowlist. Known defaults define the expected value types.
"""
from copy import deepcopy
from math import isfinite


def merge_config(defaults, overrides):
    result = deepcopy(defaults)
    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def validate_json(value, path="settings"):
    """Reject non-finite values and Mongo field-path operators, including in new fields."""
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or not key or "." in key or key.startswith("$"):
                raise ValueError(f"{path}: field names cannot be empty or contain '.' / start with '$'")
            validate_json(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            validate_json(child, f"{path}[{i}]")
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if not isfinite(value):
            raise ValueError(f"{path}: enter a finite number")


def validate_content(content):
    """Keep arbitrary effects/extension fields, but reject unusable costs and identifiers."""
    validate_json(content, "content")
    requirements = content.get("requirements")
    age = requirements.get("min_age_days") if isinstance(requirements, dict) else None
    if age is not None and (isinstance(age, bool) or not isinstance(age, (int, float)) or age < 0):
        raise ValueError("requirements.min_age_days: use a nonnegative number of real days")
    identifier = content.get("id")
    if not isinstance(identifier, str) or not identifier.strip() or "." in identifier or "$" in identifier:
        raise ValueError("content.id: use a nonempty text ID without '.' or '$'")
    for field in ("price", "buy_price", "purchase_price", "deposit", "money_cost", "cost",
                  "hourly_wage", "base_hourly_wage", "daily_demand", "production_per_worker_hour",
                  "duration_minutes", "cooldown_minutes", "combat_power", "combat_armor"):
        value = content.get(field)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0):
            raise ValueError(f"content.{field}: enter a nonnegative number")
    return content


def _validate_types(value, default, path):
    if isinstance(default, dict):
        if not isinstance(value, dict):
            raise ValueError(f"{path}: expected an object")
        for key, expected in default.items():
            if key in value:
                _validate_types(value[key], expected, f"{path}.{key}" if path else key)
    elif isinstance(default, bool):
        if not isinstance(value, bool):
            raise ValueError(f"{path}: expected true or false")
    elif isinstance(default, (int, float)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{path}: expected a number")
    elif isinstance(default, list) and not isinstance(value, list):
        raise ValueError(f"{path}: expected a list")
    elif isinstance(default, str) and not isinstance(value, str):
        raise ValueError(f"{path}: expected text")


def flatten_patch(patch, prefix=""):
    """Leaf-only $set paths preserve siblings even for deeply nested future settings."""
    validate_json(patch)
    out = {}
    for key, value in patch.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(flatten_patch(value, name))
        else:
            out[name] = value
    return out


def validate_config(config, defaults):
    validate_json(config)
    _validate_types(config, defaults, "")
    from world_engine import validate_settings as validate_world_settings
    validate_world_settings(config["world"])
    from world_map import validate_map
    validate_map(config["world_map"])
    from world_life import validate_settings as validate_life
    validate_life(config["world_life"])
    from realm_engine import validate_settings
    validate_settings(config["realm"])
    journey = config.get("journey", {})
    limit = journey.get("max_active_stories", 3)
    if not 1 <= limit <= 20 or int(limit) != limit:
        raise ValueError("journey.max_active_stories: use a whole number from 1 to 20")
    comfort = config.get("business_comfort", {})
    for key, value in comfort.items():
        if isinstance(value, (int, float)) and not 0 <= value <= 365:
            raise ValueError(f"business_comfort.{key}: must be between 0 and 365 game days")
    if comfort.get("default_reserve_days", 1) > comfort.get("max_reserve_days", 30):
        raise ValueError("Default reserve cannot exceed the maximum reserve.")
    if config.get("time_scale", 1) <= 0:
        raise ValueError("time_scale: must be greater than zero")
    for key in ("skill_per_level", "player_per_level"):
        if config.get("xp", {}).get(key, 1) <= 0:
            raise ValueError(f"xp.{key}: must be greater than zero")
    for section in ("decay", "economy", "needs", "hospital", "comms", "employment", "employees"):
        for key, value in config.get(section, {}).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value < 0:
                raise ValueError(f"{section}.{key}: cannot be negative")
    for section in ("needs", "hospital"):
        for key, value in config.get(section, {}).items():
            if isinstance(value, (int, float)) and ("threshold" in key or key.endswith("_health")):
                if not 0 <= value <= 100:
                    raise ValueError(f"{section}.{key}: must be between 0 and 100")
    for key, value in config.get("hospital", {}).items():
        if "duration" in key and isinstance(value, (int, float)) and value <= 0:
            raise ValueError(f"hospital.{key}: must be greater than zero")
    hospital = config.get("hospital", {})
    if hospital.get("admission_health", 1) <= 0:
        raise ValueError("hospital.admission_health: must be greater than zero")
    if hospital.get("discharge_health", 60) < hospital.get("admission_health", 1):
        raise ValueError("hospital.discharge_health: must be at least the admission health")
    tuning = config.get("tuning", {})
    for key in ("accident_chance", "police_event_per_hour"):
        if key in tuning and not 0 <= tuning[key] <= 1:
            raise ValueError(f"tuning.{key}: must be between 0 and 1")
    for key, value in tuning.items():
        if key.endswith("_min") and key[:-4] + "_max" in tuning:
            if value > tuning[key[:-4] + "_max"]:
                raise ValueError(f"tuning.{key}: minimum cannot exceed maximum")
    brackets = tuning.get("tax_brackets")
    if brackets is not None:
        if not brackets:
            raise ValueError("tuning.tax_brackets: at least one bracket is required")
        previous = 0
        for i, bracket in enumerate(brackets):
            if not isinstance(bracket, list) or len(bracket) != 2:
                raise ValueError("tuning.tax_brackets: expected [upper limit, rate] pairs")
            limit, rate = bracket
            if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0 <= rate <= 1:
                raise ValueError("tuning.tax_brackets: rates must be between 0 and 1")
            if limit is None:
                if i != len(brackets) - 1:
                    raise ValueError("tuning.tax_brackets: only the last upper limit may be null")
            elif isinstance(limit, bool) or not isinstance(limit, (int, float)) or limit <= previous:
                raise ValueError("tuning.tax_brackets: upper limits must increase")
            else:
                previous = limit
    return config
