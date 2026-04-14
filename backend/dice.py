import re
import random

def parse_and_roll(expression: str):
    expression = expression.strip().lower().replace(" ", "")
    parts = re.findall(r'([+-]?)(\d+)?d(\d+)|([+-]?)(\d+)', expression)
    rolls = []
    total = 0
    has_dice = False

    for match in parts:
        if match[2]:  # dice notation: NdS
            has_dice = True
            sign = -1 if match[0] == '-' else 1
            count = int(match[1]) if match[1] else 1
            sides = int(match[2])
            if count > 100 or sides > 1000:
                raise ValueError("Dice values too large")
            dice_results = [random.randint(1, sides) for _ in range(count)]
            subtotal = sum(dice_results) * sign
            total += subtotal
            rolls.append({
                "notation": f"{count}d{sides}",
                "results": dice_results,
                "subtotal": subtotal,
                "sign": "+" if sign == 1 else "-"
            })
        elif match[4]:  # flat modifier
            sign = -1 if match[3] == '-' else 1
            val = int(match[4]) * sign
            total += val
            rolls.append({
                "notation": f"{abs(val)}",
                "results": [abs(val)],
                "subtotal": val,
                "sign": "+" if sign == 1 else "-"
            })

    if not has_dice:
        raise ValueError("No dice found in expression")

    is_critical = False
    is_fumble = False
    if len(rolls) == 1 and rolls[0]["notation"] == "1d20":
        val = rolls[0]["results"][0]
        is_critical = val == 20
        is_fumble = val == 1

    return {
        "expression": expression,
        "rolls": rolls,
        "total": total,
        "is_critical": is_critical,
        "is_fumble": is_fumble
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
        text += " CRITICAL SUCCESS!"
    elif result["is_fumble"]:
        text += " CRITICAL FAILURE!"
    return text
