import re
import random

# Configurable dice rules (defaults)
DICE_CONFIG = {
    "nat20_auto_success": True,
    "nat1_auto_fail": True,
    "impossible_partial_success": True,
    "show_dc": True,
    "show_modifiers": True,
}

def parse_and_roll(expression: str):
    expression = expression.strip().lower().replace(" ", "")
    parts = re.findall(r'([+-]?)(\d+)?d(\d+)|([+-]?)(\d+)', expression)
    rolls = []
    total = 0
    has_dice = False
    raw_d20 = None

    for match in parts:
        if match[2]:
            has_dice = True
            sign = -1 if match[0] == '-' else 1
            count = int(match[1]) if match[1] else 1
            sides = int(match[2])
            if count > 100 or sides > 1000:
                raise ValueError("Dice values too large")
            dice_results = [random.randint(1, sides) for _ in range(count)]
            subtotal = sum(dice_results) * sign
            total += subtotal
            rolls.append({"notation": f"{count}d{sides}", "results": dice_results, "subtotal": subtotal, "sign": "+" if sign == 1 else "-"})
            if count == 1 and sides == 20 and raw_d20 is None:
                raw_d20 = dice_results[0]
        elif match[4]:
            sign = -1 if match[3] == '-' else 1
            val = int(match[4]) * sign
            total += val
            rolls.append({"notation": f"{abs(val)}", "results": [abs(val)], "subtotal": val, "sign": "+" if sign == 1 else "-"})

    if not has_dice:
        raise ValueError("No dice found in expression")

    is_nat20 = raw_d20 == 20
    is_nat1 = raw_d20 == 1

    return {
        "expression": expression, "rolls": rolls, "total": total,
        "raw_d20": raw_d20, "is_critical": is_nat20, "is_fumble": is_nat1
    }

def resolve_check_result(roll_result: dict, dc: int, modifier: int = 0, config: dict = None):
    """Full resolution with categories and German output."""
    cfg = config or DICE_CONFIG
    raw = roll_result.get("raw_d20", roll_result["total"])
    total = roll_result["total"] + modifier
    is_nat20 = roll_result.get("is_critical", False)
    is_nat1 = roll_result.get("is_fumble", False)

    # Determine outcome category
    if is_nat20 and cfg.get("nat20_auto_success", True):
        category = "kritischer_erfolg"
    elif is_nat1 and cfg.get("nat1_auto_fail", True):
        category = "kritischer_fehlschlag"
    elif total >= dc + 10:
        category = "kritischer_erfolg"
    elif total >= dc:
        category = "erfolg"
    elif total >= dc - 5:
        category = "teilerfolg"
    else:
        category = "fehlschlag"

    # German labels
    labels = {
        "kritischer_erfolg": "Kritischer Erfolg",
        "erfolg": "Erfolg",
        "teilerfolg": "Teilerfolg",
        "fehlschlag": "Fehlschlag",
        "kritischer_fehlschlag": "Kritischer Fehlschlag"
    }

    # Build visible resolution block
    lines = [f"**Wurf:** 1W20 = {raw}"]
    if modifier != 0 and cfg.get("show_modifiers", True):
        lines.append(f"**Modifikator:** {'+' if modifier >= 0 else ''}{modifier}")
    if modifier != 0:
        lines.append(f"**Gesamt:** {total}")
    if cfg.get("show_dc", True):
        lines.append(f"**Schwierigkeit:** {dc}")
    lines.append(f"**Ergebnis:** {labels[category]}")

    return {
        "raw": raw, "modifier": modifier, "total": total, "dc": dc,
        "category": category, "label": labels[category],
        "is_nat20": is_nat20, "is_nat1": is_nat1,
        "display": "\n".join(lines)
    }

def format_roll_result(result: dict) -> str:
    parts = []
    for r in result["rolls"]:
        if "d" in r["notation"]:
            parts.append(f"[{', '.join(str(x) for x in r['results'])}]")
        else:
            parts.append(f"{r['sign']}{r['notation']}")
    detail = " ".join(parts)
    text = f"**{result['expression']}** = {detail} = **{result['total']}**"
    if result["is_critical"]:
        text += " — Kritischer Erfolg!"
    elif result["is_fumble"]:
        text += " — Kritischer Fehlschlag!"
    return text
