"""Shared quotes and operating-reserve calculations for UI and execution."""
import math


def material_multiplier(player):
    return 1 - min(0.20, max(0, (player.get("social_perks") or {}).get("material_discount", 0)))


def restock_quote(b, target, multiplier=1):
    stock = b.get("materials") or {}
    materials = dict(stock)
    lines = []
    for r in b.get("recipe") or []:
        missing = max(0, round(target * r.get("qty", 1) - stock.get(r["id"], 0), 3))
        cost = missing * r.get("cost", 0) * multiplier
        materials[r["id"]] = round(stock.get(r["id"], 0) + missing, 3)
        lines.append({"id": r["id"], "name": r.get("name", r["id"]), "quantity": missing, "cost": round(cost, 2)})
    total = round(sum(max(0, target * r.get("qty", 1) - stock.get(r["id"], 0)) * r.get("cost", 0) * multiplier
                      for r in b.get("recipe") or []), 2)
    from_business = min(max(0, b.get("cash", 0)), total)
    return {"cost": total, "from_business": round(from_business, 2), "from_owner": round(total - from_business, 2),
            "units": target, "lines": lines, "materials": materials}


def operations(b, m, cfg):
    tune = cfg.get("business_comfort", {})
    days = min(tune.get("max_reserve_days", 30), max(0, b.get("reserve_days", tune.get("default_reserve_days", 1))))
    cost = max(0, m.get("material_day", 0)) + max(0, m.get("wage_per_day", 0))
    debt = max(0, b.get("debt", 0))
    reserve = math.ceil((cost * days + debt) * 100) / 100
    cash = max(0, b.get("cash", 0))
    unit_stock = min((r.get("stock", 0) / r["qty"] for r in m.get("materials", []) if r.get("qty", 0) > 0), default=0)
    demand = max(0, m.get("sold_day", 0))
    stock_days = unit_stock / demand if demand else None
    alerts = []
    if debt > 0:
        alerts.append({"title": "Clear outstanding business debt", "detail": "New funding first pays outstanding wages and other business debt.", "tab": "overview"})
    if not m.get("staff_count"):
        alerts.append({"title": "Hire your first worker", "detail": "Applicants are ready to review. Production needs a worker with a shift.", "tab": "applicants"})
    elif m.get("coverage_hours_pct", 100) < 100:
        alerts.append({"title": "Review uncovered opening hours", "detail": "Match employee shifts to opening hours before adding more staff.", "tab": "schedule"})
    if cash < reserve:
        alerts.append({"title": "Build your operating reserve", "detail": "Keep money in the business for materials and wages before taking a payout.", "tab": "overview"})
    if stock_days is not None and stock_days < tune.get("stock_warning_days", 0.5):
        alerts.append({"title": "Check your supplies", "detail": "Automatic restocking uses business cash. Review the purchase quote if funds are tight.", "tab": "overview"})
    if m.get("net_day", 0) < 0:
        alerts.append({"title": "Review the daily cost breakdown", "detail": "Forecast wages and materials exceed sales. Check shift overlap and demand before expanding.", "tab": "schedule"})
    return {"reserve_days": days, "max_reserve_days": tune.get("max_reserve_days", 30),
            "reserve": round(reserve, 2), "safe_to_collect": round(max(0, cash - reserve), 2),
            "reserve_gap": round(max(0, reserve - cash), 2), "daily_cost": round(cost, 2),
            "cash_runway_days": round(cash / cost, 1) if cost else None,
            "stock_days": round(stock_days, 1) if stock_days is not None else None,
            "status": "Needs attention" if alerts else "On track", "alerts": alerts}
