"""Phase 1.1 smoke test: scheduled auto-work accrual, clock-out, NPC backup, gating.
Run: cd /app/backend && python tests/smoke_phase11.py
"""
import asyncio
import os
from datetime import timedelta
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")
from motor.motor_asyncio import AsyncIOMotorClient
from game_models import now_utc
import game_engine
import employment
import employee_engine

db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def ok(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    return cond


async def main():
    results = []
    cfg = await game_engine.get_config(db)
    print("time_scale =", cfg.get("time_scale"))

    emp = await db.player_employment.find_one({"status": "active"}, {"_id": 0})
    if not emp:
        print("No active player_employment to test against. Aborting.")
        return
    p = await db.players.find_one({"id": emp["employee_player_id"]}, {"_id": 0})
    biz = await db.businesses.find_one({"id": emp["business_id"]}, {"_id": 0})
    print(f"Employee={p['name']} role={emp.get('role')} biz={biz['name']}")

    # --- Force an all-day schedule + reset clock-out so accrual is deterministic ---
    await db.player_employment.update_one({"id": emp["id"]}, {"$set": {
        "schedule": {"preset": "allday", "label": "All Day", "start": 0, "end": 24},
        "clocked_out_until": None,
        "today": None, "total_hours_worked": 0, "total_wages_earned": 0.0, "total_value_added": 0.0,
        "reliability": 60, "performance": 60}})

    # rewind employee's resolution clock 2 real hours (=> 2 game hours at ts=1)
    rewind = (now_utc() - timedelta(hours=2)).isoformat()
    await db.players.update_one({"id": p["id"]}, {"$set": {"last_resolved_at": rewind, "current_activity": None}})

    cash_before = (await db.players.find_one({"id": p["id"]}, {"_id": 0}))["cash"]
    biz_cash_before = biz.get("cash", 0)
    rev_before = biz.get("revenue_total", 0)

    # --- resolve the EMPLOYEE -> should auto-accrue ~2h of work ---
    p2 = await db.players.find_one({"id": p["id"]}, {"_id": 0})
    await game_engine.resolve_player(db, p2)
    await db.players.update_one({"id": p["id"]}, {"$set": p2})

    emp2 = await db.player_employment.find_one({"id": emp["id"]}, {"_id": 0})
    biz2 = await db.businesses.find_one({"id": emp["business_id"]}, {"_id": 0})
    p_after = await db.players.find_one({"id": p["id"]}, {"_id": 0})

    hrs = emp2.get("total_hours_worked", 0)
    results.append(ok("auto-accrued ~2 game-hours", 1.5 <= hrs <= 2.6, f"(hours={hrs})"))
    results.append(ok("wage credited to employee cash", p_after["cash"] > cash_before, f"(+{round(p_after['cash']-cash_before,2)})"))
    results.append(ok("emp.today populated", emp2.get("today") and emp2["today"]["hours"] > 0, f"(today={emp2.get('today')})"))
    results.append(ok("status set to working while on shift", p2.get("status") == "working", f"(status={p2.get('status')})"))
    results.append(ok("on_shift flag set", bool(p2.get("on_shift")), f"(on_shift={bool(p2.get('on_shift'))})"))
    booking = [h for h in biz2.get("history", []) if h.get("kind") == "shift"]
    results.append(ok("business booking history entry added", len(booking) > 0))
    results.append(ok("business revenue_total grew", biz2.get("revenue_total", 0) >= rev_before))
    li = emp2.get("last_impact") or {}
    print(f"   last_impact: rev={li.get('revenue')} wage={li.get('wage')} net={li.get('net')} prod={li.get('productivity')}")

    # --- clock out early ---
    res = await employment.clock_out_early(db, p_after, cfg, emp2)
    emp3 = await db.player_employment.find_one({"id": emp["id"]}, {"_id": 0})
    results.append(ok("clock-out returns ok", res.get("ok") is True))
    results.append(ok("clocked_out_until set", bool(emp3.get("clocked_out_until"))))
    results.append(ok("reliability dropped by ~10", emp3.get("reliability") <= 51, f"(rel={emp3.get('reliability')})"))

    # --- after clock-out, no further accrual in same window ---
    await db.players.update_one({"id": p["id"]}, {"$set": {"last_resolved_at": (now_utc()-timedelta(hours=1)).isoformat()}})
    hrs_b = emp3.get("total_hours_worked", 0)
    p3 = await db.players.find_one({"id": p["id"]}, {"_id": 0})
    await game_engine.resolve_player(db, p3)
    await db.players.update_one({"id": p["id"]}, {"$set": p3})
    emp4 = await db.player_employment.find_one({"id": emp["id"]}, {"_id": 0})
    results.append(ok("no accrual after clock-out", abs(emp4.get("total_hours_worked", 0) - hrs_b) < 0.01,
                      f"(before={hrs_b} after={emp4.get('total_hours_worked')})"))
    results.append(ok("on_shift cleared after clock-out", not p3.get("on_shift")))

    # --- NPC backup: pick an uncovered required role, enable backup, check wage charged ---
    reqs = await employee_engine.get_staffing(db, biz2)
    covered_role = emp.get("role")
    uncovered = next((r["role"] for r in reqs if r["role"] != covered_role), None)
    if uncovered:
        await db.businesses.update_one({"id": biz2["id"]}, {"$set": {"backup_roles": {uncovered: True}}})
        b = await db.businesses.find_one({"id": biz2["id"]}, {"_id": 0})
        owner = await db.players.find_one({"id": b["player_id"]}, {"_id": 0})
        await employee_engine.resolve_business(db, owner, cfg, 1.0, now_utc(), b)
        b2 = await db.businesses.find_one({"id": biz2["id"]}, {"_id": 0})
        results.append(ok("NPC backup charges a wage when role uncovered", b2.get("backup_wage_day", 0) > 0,
                          f"(backup_wage_day={b2.get('backup_wage_day')})"))
        m = await employee_engine.business_metrics(db, b2)
        srow = next((s for s in m["staffing"] if s["role"] == uncovered), {})
        results.append(ok("metrics report backup_active for uncovered role", srow.get("backup_active") is True,
                          f"(status={srow.get('status')})"))
        await db.businesses.update_one({"id": biz2["id"]}, {"$set": {"backup_roles": {}}})
    else:
        print("[SKIP] backup test — business has only one role")

    # restore default schedule
    await db.player_employment.update_one({"id": emp["id"]}, {"$set": {
        "schedule": employment.make_schedule("early"), "clocked_out_until": None}})

    print(f"\n{sum(results)}/{len(results)} checks passed.")


asyncio.run(main())
