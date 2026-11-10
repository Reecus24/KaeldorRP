from core import *  # noqa: F401,F403
from business_comfort import operations, restock_quote, material_multiplier




@api.get("/businesses/market")
async def business_market(user: dict = Depends(current_user)):
    p = await get_state(user)
    types = await db.business_types.find({}, {"_id": 0}).to_list(100)
    staffing = {s["id"]: s.get("requirements", []) for s in await db.staffing_requirements.find({}, {"_id": 0}).to_list(100)}
    roles = {r["id"]: r for r in await db.employee_roles.find({}, {"_id": 0}).to_list(100)}
    out = []
    for t in types:
        ok, reason = meets_requirements(p, t.get("requirements"))
        out.append({**t, "qualified": ok, "reason": reason,
                    "estimate": _estimate_market_pnl(t, staffing.get(t["id"], []), roles)})
    return sorted(out, key=lambda x: x.get("purchase_price", 0))




@api.get("/businesses/owned")
async def owned_businesses(user: dict = Depends(current_user)):
    p = await get_state(user)
    bizs = await db.businesses.find({"player_id": p["id"]}, {"_id": 0}).sort("created_at", 1).to_list(100)
    for b in bizs:
        b["metrics"] = await employee_engine.business_metrics(db, b)
        b["operations"] = operations(b, b["metrics"], await get_config(db))
    return bizs




@api.post("/businesses/{type_id}/buy")
async def buy_business(type_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    t = await db.business_types.find_one({"id": type_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Business type not found")
    ok, reason = meets_requirements(p, t.get("requirements"))
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    if p["cash"] + p["bank"] < t["purchase_price"]:
        raise HTTPException(status_code=400, detail="Cannot afford this business")
    charge(p, t["purchase_price"])
    now = now_utc()
    recipe = t.get("recipe") or []
    restock_target = t.get("daily_demand", 0)
    materials = {r["id"]: round(restock_target * r.get("qty", 1), 3) for r in recipe}  # starting inventory
    biz = {
        "id": uuid.uuid4().hex, "player_id": p["id"], "type_id": type_id, "name": t["name"],
        "category": t.get("category", ""), "purchase_price": t["purchase_price"],
        "max_level": t.get("max_level", 5), "level": 1, "marketing_level": 0, "reputation": 50.0,
        "opening_hours": t.get("opening_hours") or {"open": "08:00", "close": "20:00"},
        # supply chain
        "product": t.get("product") or {}, "recipe": recipe,
        "production_per_worker_hour": t.get("production_per_worker_hour", 0),
        "daily_demand": t.get("daily_demand", 0), "materials": materials, "products": 0.0,
        "restock_target": restock_target, "auto_restock": True,
        "cash": 0.0, "debt": 0.0, "revenue_total": 0.0,
        "rev_day": 0.0, "material_day": 0.0, "wages_day": 0.0, "net_day": 0.0, "exp_day": 0.0,
        "demand_day": 0.0, "produced_day": 0.0, "sold_day": 0.0,
        "bankrupt": False, "history": [], "created_at": now.isoformat(), "last_resolved_at": now.isoformat(),
        "satisfaction": 80.0, "last_applicant_at": now.isoformat(), "morale_avg": 0, "hiring_open": False,
    }
    await db.businesses.insert_one({**biz})
    cfg = await get_config(db)
    reqs = await employee_engine.get_staffing(db, biz)
    for _ in range(3):
        await employee_engine._create_applicant(db, p, cfg, biz, reqs, premium=False)
    await add_event(db, p["id"], f"You acquired a business: {t['name']}! Applicants are waiting to be hired.", "business", "success", biz["id"])
    await save_player(p)
    return {"ok": True}




@api.post("/businesses/{biz_id}/upgrade")
async def upgrade_business(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    if b.get("bankrupt"):
        raise HTTPException(status_code=400, detail="This business is bankrupt")
    if b["level"] >= b["max_level"]:
        raise HTTPException(status_code=400, detail="Already at max level")
    if b.get("activity"):
        raise HTTPException(status_code=400, detail=f"A {b['activity']['type']} is already in progress here")
    cost = round(b["purchase_price"] * 0.4 * b["level"])
    if p["cash"] + p["bank"] < cost:
        raise HTTPException(status_code=400, detail=f"Upgrade costs ¤ {cost}")
    charge(p, cost)
    cfg = await get_config(db)
    now = now_utc()
    dur_days = int((cfg.get("tuning") or {}).get("upgrade_days", 7))
    ends = now + timedelta(seconds=real_seconds(dur_days * 1440, cfg["time_scale"]))
    activity = {"type": "upgrade", "started_at": now.isoformat(), "ends_at": ends.isoformat(),
                "duration_days": dur_days, "completed": False}
    await db.businesses.update_one({"id": biz_id}, {"$set": {"activity": activity}})
    await add_event(db, p["id"], f"Started upgrading {b['name']} (~{dur_days} in-game days). Income is cut 50% during construction; +1 level & staff slot when it's done.", "business", "info", biz_id)
    await save_player(p)
    return {"ok": True, "cost": cost, "activity": activity}




@api.post("/businesses/{biz_id}/marketing")
async def marketing_business(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    if b.get("bankrupt"):
        raise HTTPException(status_code=400, detail="This business is bankrupt")
    if b.get("activity"):
        raise HTTPException(status_code=400, detail=f"A {b['activity']['type']} is already in progress here")
    cost = round(b["purchase_price"] * 0.12 * (b.get("marketing_level", 0) + 1))
    if p["cash"] + p["bank"] < cost:
        raise HTTPException(status_code=400, detail=f"Marketing campaign costs ¤ {cost}")
    charge(p, cost)
    cfg = await get_config(db)
    now = now_utc()
    dur_days = int((cfg.get("tuning") or {}).get("marketing_days", 3))
    ends = now + timedelta(seconds=real_seconds(dur_days * 1440, cfg["time_scale"]))
    activity = {"type": "marketing", "started_at": now.isoformat(), "ends_at": ends.isoformat(),
                "duration_days": dur_days, "completed": False}
    await db.businesses.update_one({"id": biz_id}, {"$set": {"activity": activity}})
    await add_event(db, p["id"], f"Launched a marketing campaign for {b['name']} (~{dur_days} in-game days to roll out). The demand & price boost applies when it completes.", "business", "info", biz_id)
    await save_player(p)
    return {"ok": True, "cost": cost, "activity": activity}




@api.post("/businesses/{biz_id}/collect")
async def collect_business(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    metrics = await employee_engine.business_metrics(db, b)
    op = operations(b, metrics, await get_config(db))
    amount = op["safe_to_collect"]
    if amount <= 0:
        raise HTTPException(status_code=400, detail="No coin above the operating reserve yet. Review reserve settings or let the business earn more.")
    b["cash"] = round(b.get("cash", 0) - amount, 2)
    await db.businesses.update_one({"id": biz_id}, {"$set": {"cash": b["cash"]}})
    add_money(p, amount)
    ledger_add(p, "business_income", amount)
    await add_event(db, p["id"], f"Collected ¤ {amount} profit from {b['name']}.", "business", "success")
    await save_player(p)
    return {"ok": True, "amount": amount, "retained": b["cash"]}




@api.post("/businesses/{biz_id}/inject")
async def inject_business(biz_id: str, body: AmountBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    amt = round(body.amount, 2)
    if amt <= 0 or p["cash"] + p["bank"] < amt:
        raise HTTPException(status_code=400, detail="Invalid amount")
    charge(p, amt)
    paid = min(amt, b.get("debt", 0))
    b["debt"] = round(b.get("debt", 0) - paid, 2)
    b["cash"] = round(b.get("cash", 0) + (amt - paid), 2)
    if b.get("bankrupt") and b["debt"] <= 0:
        b["bankrupt"] = False
    await db.businesses.update_one({"id": biz_id}, {"$set": b})
    await add_event(db, p["id"], f"Injected ¤ {amt} into {b['name']}.", "business", "info")
    await save_player(p)
    return {"ok": True}




@api.post("/businesses/{biz_id}/sell")
async def sell_business(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    if await db.player_employment.find_one({"business_id": biz_id, "status": "active"}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="End active player employment contracts before selling this business, so employees are not left working at a closed business.")
    value = round(b["purchase_price"] * 0.5 * b["level"] * (0.6 + 0.4 * b["reputation"] / 100) - b.get("debt", 0) + b.get("cash", 0))
    value = max(0, value)
    await db.businesses.delete_one({"id": biz_id})
    await db.employees.update_many({"business_id": biz_id, "status": {"$in": ["active", "sick", "applicant"]}},
                                  {"$set": {"status": "fired"}})
    await db.business_applications.update_many(
        {"business_id": biz_id, "status": {"$in": ["pending", "offered"]}},
        {"$set": {"status": "rejected", "reason": "The business has been sold."}})
    add_money(p, value)
    await add_event(db, p["id"], f"Sold {b['name']} for ¤ {value}.", "business", "info")
    await save_player(p)
    return {"ok": True, "value": value}




@api.post("/businesses/{biz_id}/rename")
async def rename_business(biz_id: str, body: RenameBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    await _get_owned_business(p, biz_id)
    name = (body.name or "").strip()
    if not (2 <= len(name) <= 40):
        raise HTTPException(status_code=400, detail="Name must be 2–40 characters")
    await db.businesses.update_one({"id": biz_id}, {"$set": {"name": name}})
    await db.player_employment.update_many({"business_id": biz_id}, {"$set": {"business_name": name}})
    await db.business_applications.update_many({"business_id": biz_id}, {"$set": {"business_name": name}})
    return {"ok": True, "name": name}




@api.post("/businesses/{biz_id}/restock-settings")
async def restock_settings(biz_id: str, body: RestockBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    await _get_owned_business(p, biz_id)
    upd = {}
    if body.auto_restock is not None:
        upd["auto_restock"] = bool(body.auto_restock)
    if body.restock_target is not None:
        if not 0 <= body.restock_target <= 1_000_000:
            raise HTTPException(422, "Stock target must be between 0 and 1,000,000 units.")
        upd["restock_target"] = max(0.0, round(body.restock_target, 1))
    if body.reserve_days is not None:
        cfg = await get_config(db)
        if not 0 <= body.reserve_days <= cfg["business_comfort"]["max_reserve_days"]:
            raise HTTPException(422, "Reserve days are outside the Owner's allowed range.")
        upd["reserve_days"] = body.reserve_days
    if upd:
        await db.businesses.update_one({"id": biz_id}, {"$set": upd})
    return {"ok": True, **upd}




@api.post("/businesses/{biz_id}/buy-materials")
async def buy_materials(biz_id: str, body: MaterialsBody, user: dict = Depends(current_user)):
    """Top up ingredient stock to `units` product-equivalents. Paid from business coin;
    if the business is short, the owner's wallet covers the rest."""
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    recipe = b.get("recipe") or []
    if not recipe:
        raise HTTPException(status_code=400, detail="This business has no supply chain")
    target = body.units if body.units is not None else b.get("restock_target", b.get("daily_demand", 0))
    if not 0 <= target <= 1_000_000:
        raise HTTPException(422, "Stock target must be between 0 and 1,000,000 units.")
    target = round(target, 1)
    quote = restock_quote(b, target, material_multiplier(p))
    cost, new_mats = quote["cost"], quote["materials"]
    if cost <= 0:
        return {"ok": True, "cost": 0, "detail": "Already stocked to target"}
    biz_cash = round(b.get("cash", 0), 2)
    from_biz = min(biz_cash, cost)
    from_owner = round(cost - from_biz, 2)
    if from_owner > 0 and not body.allow_owner_funds:
        raise HTTPException(409, "Business funds are insufficient. Review the quote and explicitly allow personal funds, or inject money first.")
    if from_owner > 0 and (p["cash"] + p["bank"]) < from_owner:
        raise HTTPException(status_code=400, detail=f"Need ¤ {cost} to restock (business has ¤ {biz_cash}); you can't cover the rest")
    if from_owner > 0:
        charge(p, from_owner)
        await save_player(p)
    await db.businesses.update_one({"id": biz_id}, {"$set": {"materials": new_mats, "cash": round(biz_cash - from_biz, 2)}})
    await add_event(db, p["id"], f"Restocked materials at {b['name']} for ¤ {cost}.", "business", "info", biz_id)
    return {"ok": True, "cost": cost, "from_business": from_biz, "from_owner": from_owner}


@api.post("/businesses/{biz_id}/materials-quote")
async def materials_quote(biz_id: str, body: MaterialsBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    target = body.units if body.units is not None else b.get("restock_target", b.get("daily_demand", 0))
    if not 0 <= target <= 1_000_000:
        raise HTTPException(422, "Stock target must be between 0 and 1,000,000 units.")
    q = restock_quote(b, round(target, 1), material_multiplier(p))
    q.pop("materials")
    return q




@api.get("/businesses/{biz_id}")
async def business_detail(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    cfg = await get_config(db)
    tuning = cfg.get("tuning") or {}
    pp = b.get("purchase_price", 1)
    lvl = b.get("level", 1)
    mkt = b.get("marketing_level", 0)
    rep = b.get("reputation", 50)
    can_upgrade = lvl < b.get("max_level", 1)
    activity = b.get("activity")
    costs = {
        "upgrade_cost": round(pp * 0.4 * lvl) if can_upgrade else None,
        "upgrade_from_level": lvl, "upgrade_to_level": lvl + 1 if can_upgrade else lvl,
        "upgrade_adds_slot": can_upgrade, "upgrade_reputation_gain": 4, "can_upgrade": can_upgrade,
        "upgrade_duration_days": int(tuning.get("upgrade_days", 7)),
        "marketing_cost": round(pp * 0.12 * (mkt + 1)),
        "marketing_level": mkt, "marketing_next_level": mkt + 1,
        "marketing_demand_boost_pct": 25, "marketing_price_boost_pct": 12, "marketing_reputation_gain": 8,
        "marketing_duration_days": int(tuning.get("marketing_days", 3)),
        "activity_in_progress": bool(activity), "activity": activity,
        "sell_value": max(0, round(pp * 0.5 * lvl * (0.6 + 0.4 * rep / 100) - b.get("debt", 0) + b.get("cash", 0))),
    }
    metrics = await employee_engine.business_metrics(db, b)
    insight = employee_engine.business_insight(b, metrics)
    return {"business": b, "metrics": metrics, "costs": costs, "insight": insight,
            "operations": operations(b, metrics, cfg)}




@api.get("/businesses/{biz_id}/employees")
async def biz_employees(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    cfg = await get_config(db)
    tmap = {t["id"]: t for t in await db.employee_traits.find({}, {"_id": 0}).to_list(100)}
    emps = await db.employees.find({"business_id": biz_id, "status": {"$in": ["active", "sick"]}}, {"_id": 0}).sort("hire_date", 1).to_list(200)
    opening = b.get("opening_hours")
    for e in emps:
        e["projection"] = employment.npc_employee_projection(e, cfg, tmap, b)
        sh = e.get("schedule")
        e["hourly_wage"] = employee_engine.npc_hourly_wage(e)
        if sh:
            s_h, e_h = employment.shift_bounds(sh)
            e["shift_start"] = employment.float_to_hhmm(s_h)
            e["shift_end"] = employment.float_to_hhmm(e_h)
        else:
            e["shift_start"] = None
            e["shift_end"] = None
        e["shift_hours"] = employment.worker_shift_hours(sh, opening)
    return {"employees": emps, "metrics": await employee_engine.business_metrics(db, b)}




@api.get("/businesses/{biz_id}/applicants")
async def biz_applicants(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    await _get_owned_business(p, biz_id)
    return await db.employees.find({"business_id": biz_id, "status": "applicant"}, {"_id": 0}).to_list(50)




@api.get("/businesses/{biz_id}/events")
async def biz_events(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    await _get_owned_business(p, biz_id)
    return await db.events.find({"player_id": p["id"], "business_id": biz_id}, {"_id": 0}).sort("ts", -1).to_list(50)




@api.post("/businesses/{biz_id}/applicants/{emp_id}/hire")
async def hire_applicant(biz_id: str, emp_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    await _get_owned_business(p, biz_id)
    emp = await db.employees.find_one({"id": emp_id, "business_id": biz_id, "status": "applicant"}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Applicant not found")
    b = await _get_owned_business(p, biz_id)
    m = await employee_engine.business_metrics(db, b)
    if m["staff_count"] >= m["max_hire_slots"]:
        raise HTTPException(status_code=400, detail=f"Staff limit reached ({m['staff_count']}/{m['max_hire_slots']}). You can hire up to {m['max_hire_slots']} workers to cover shifts.")
    sched_key = (emp.get("schedule") or {}).get("preset") or "early"
    wph = b.get("base_hourly_wage") or emp.get("wage_per_hour") or round(emp.get("daily_wage", 90) / 8.0, 2)
    # default shift: cover the largest currently-uncovered slice of opening hours
    existing = await db.employees.find({"business_id": biz_id, "status": "active"}, {"_id": 0, "schedule": 1}).to_list(300)
    pe_existing = await db.player_employment.find({"business_id": biz_id, "status": "active"}, {"_id": 0, "schedule": 1}).to_list(100)
    scheds = [x.get("schedule") for x in existing + pe_existing]
    shift = employment.first_uncovered_shift(b.get("opening_hours"), scheds)
    await db.employees.update_one({"id": emp_id}, {"$set": {
        "status": "active", "hire_date": now_utc().isoformat(), "last_paid": now_utc().isoformat(),
        "wage_per_hour": wph, "schedule": shift}})
    if shift:
        await add_event(db, p["id"], f"You hired {emp['name']} as {emp['role'].replace('_', ' ')} ({shift['label']}).", "business", "success", biz_id)
    else:
        await add_event(db, p["id"], f"You hired {emp['name']} as {emp['role'].replace('_', ' ')}. Opening hours are already covered — assign a shift in the Schedule tab (they cost ¤ 0 until scheduled).", "business", "info", biz_id)
    return {"ok": True}




@api.post("/businesses/{biz_id}/applicants/{emp_id}/reject")
async def reject_applicant(biz_id: str, emp_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    await _get_owned_business(p, biz_id)
    await db.employees.delete_one({"id": emp_id, "business_id": biz_id, "status": "applicant"})
    return {"ok": True}




@api.post("/businesses/{biz_id}/recruit")
async def recruit_applicant(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    cfg = await get_config(db)
    cost = cfg.get("employees", {}).get("recruit_cost", 250)
    if p["cash"] + p["bank"] < cost:
        raise HTTPException(status_code=400, detail=f"Recruiting costs ¤ {cost}")
    charge(p, cost)
    await save_player(p)
    reqs = await employee_engine.get_staffing(db, b)
    await employee_engine._create_applicant(db, p, cfg, b, reqs, premium=True)
    await add_event(db, p["id"], f"A strong candidate applied at {b['name']} after recruiting.", "business", "info", biz_id)
    return {"ok": True, "cost": cost}




@api.post("/businesses/employees/{emp_id}/fire")
async def fire_employee(emp_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    emp, biz = await _get_employee(p, emp_id)
    await db.employees.update_one({"id": emp_id}, {"$set": {"status": "fired"}})
    await add_event(db, p["id"], f"You fired {emp['name']}.", "business", "warning", biz["id"])
    return {"ok": True}




@api.post("/businesses/employees/{emp_id}/raise")
async def give_raise(emp_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    emp, biz = await _get_employee(p, emp_id)
    new_wage = round(emp.get("daily_wage", 80) * 1.12, 2)
    await db.employees.update_one({"id": emp_id}, {"$set": {
        "daily_wage": new_wage, "wage_per_hour": round(new_wage / 8.0, 2), "wants_raise": False,
        "morale": clamp(emp.get("morale", 60) + 10), "loyalty": clamp(emp.get("loyalty", 50) + 6)}})
    await add_event(db, p["id"], f"You gave {emp['name']} a raise to ¤ {round(new_wage / 8.0, 2)}/hr.", "business", "success", biz["id"])
    return {"ok": True}




@api.post("/businesses/employees/{emp_id}/train")
async def train_employee(emp_id: str, body: dict, user: dict = Depends(current_user)):
    p = await get_state(user)
    emp, biz = await _get_employee(p, emp_id)
    if emp.get("training"):
        raise HTTPException(status_code=400, detail="Already in training")
    opt = await db.training_options.find_one({"id": body.get("option_id")}, {"_id": 0})
    if not opt:
        raise HTTPException(status_code=404, detail="Training option not found")
    if p["cash"] + p["bank"] < opt["cost"]:
        raise HTTPException(status_code=400, detail="Not enough money for training")
    charge(p, opt["cost"])
    await save_player(p)
    cfg = await get_config(db)
    ends = (now_utc() + timedelta(seconds=real_seconds(opt["duration_minutes"], cfg["time_scale"]))).isoformat()
    tr = {"option_id": opt["id"], "label": opt["label"], "ends_at": ends,
          "skill_gain": opt["skill_gain"], "morale_gain": opt["morale_gain"],
          "loyalty_gain": opt["loyalty_gain"], "fail_chance": opt["fail_chance"]}
    await db.employees.update_one({"id": emp_id}, {"$set": {"training": tr}})
    await add_event(db, p["id"], f"{emp['name']} started training: {opt['label']}.", "business", "info", biz["id"])
    return {"ok": True}




# --- Player hiring (business owner) ---
@api.get("/businesses/{biz_id}/player-applications")
async def biz_player_applications(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    cfg = await get_config(db)
    reqs = await employee_engine.get_staffing(db, b)
    roles = [r["role"] for r in reqs]
    apps = await db.business_applications.find({"business_id": biz_id, "status": {"$in": ["pending", "offered"]}}, {"_id": 0}).sort("submitted_at", -1).to_list(100)
    for a in apps:
        ap = await db.players.find_one({"id": a["applicant_id"]}, {"_id": 0})
        if ap:
            r2 = roles + ([a["role"]] if a.get("role") and a["role"] not in roles else [])
            a["projection"] = employment.applicant_projection(ap, cfg, r2, b)
    return apps




@api.post("/businesses/{biz_id}/player-applications/{app_id}/offer")
async def offer_player(biz_id: str, app_id: str, body: OfferBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    a = await db.business_applications.find_one({"id": app_id, "business_id": biz_id}, {"_id": 0})
    if not a or a["status"] not in ("pending", "offered"):
        raise HTTPException(status_code=400, detail="Application not open")
    reqs = await employee_engine.get_staffing(db, b)
    role_ids = [r["role"] for r in reqs]
    role = body.role or a.get("role", "staff")
    matches = role in role_ids
    wage = round(max(1.0, body.wage_per_hour), 2)
    prev = a.get("wage_offer")
    was_offered = a["status"] == "offered"
    schedule = employment.make_schedule(body.schedule or (a.get("schedule") or {}).get("preset") or "early")
    await db.business_applications.update_one({"id": app_id}, {"$set": {"status": "offered", "wage_offer": wage, "role": role, "role_matches_staffing": matches, "schedule": schedule}})
    rl = role.replace("_", " ")
    if was_offered and prev:
        direction = "increased to" if wage >= prev else "lowered to"
        await add_notification(db, a["applicant_id"], "job", "Offer updated", f"{b['name']}: wage {direction} ¤ {wage}/h, previously ¤ {prev}/h (as {rl}, {schedule['label']}).", "info", "/job-market")
    else:
        await add_notification(db, a["applicant_id"], "job", "Job offer!", f"{b['name']} offered you ¤ {wage}/h as {rl} ({schedule['label']}).", "success", "/job-market")
    return {"ok": True, "role_matches_staffing": matches}




@api.post("/businesses/{biz_id}/player-applications/{app_id}/reject")
async def reject_player(biz_id: str, app_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    a = await db.business_applications.find_one({"id": app_id, "business_id": biz_id}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Application not found")
    await db.business_applications.update_one({"id": app_id}, {"$set": {"status": "rejected"}})
    await add_notification(db, a["applicant_id"], "job", "Application declined", f"{b['name']} declined your application.", "warning", "/job-market")
    return {"ok": True}




@api.get("/businesses/{biz_id}/player-employees")
async def biz_player_employees(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    cfg = await get_config(db)
    g_now = game_now(cfg, now_utc())
    emps = await db.player_employment.find({"business_id": biz_id, "status": "active"}, {"_id": 0}).to_list(100)
    out = []
    for e in emps:
        e["projection"] = await employment.player_employee_projection(db, cfg, e, b)
        out.append(decorate_employment_live(e, cfg, g_now))
    return out




@api.post("/businesses/{biz_id}/player-employees/{emp_id}/fire")
async def fire_player(biz_id: str, emp_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    emp = await db.player_employment.find_one({"id": emp_id, "business_id": biz_id, "status": "active"}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    await db.player_employment.update_one({"id": emp_id}, {"$set": {"status": "fired"}})
    await add_notification(db, emp["employee_player_id"], "job", "You were let go", f"{b['name']} ended your employment.", "danger", "/job-market")
    await add_event(db, emp["employee_player_id"], f"You were let go from {b['name']}.", "job", "warning")
    return {"ok": True}




@api.post("/businesses/{biz_id}/player-employees/{emp_id}/raise")
async def raise_player(biz_id: str, emp_id: str, body: WageBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    emp = await db.player_employment.find_one({"id": emp_id, "business_id": biz_id, "status": "active"}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    wage = round(max(1.0, body.wage_per_hour), 2)
    prev = emp.get("wage_per_hour") or round(emp.get("wage_per_shift", 60) / 4.0, 2)
    await db.player_employment.update_one({"id": emp_id}, {"$set": {"wage_per_hour": wage, "hours_at_last_raise": emp.get("total_hours_worked", 0), "reliability": clamp(emp.get("reliability", 60) + 5)}})
    await add_notification(db, emp["employee_player_id"], "job", "Pay rise!", f"{b['name']} raised your wage to ¤ {wage}/h, previously ¤ {prev}/h.", "success", "/job-market")
    return {"ok": True}




@api.post("/businesses/{biz_id}/toggle-hiring")
async def toggle_hiring(biz_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    newv = not b.get("hiring_open", False)
    await db.businesses.update_one({"id": biz_id}, {"$set": {"hiring_open": newv}})
    return {"ok": True, "hiring_open": newv}




@api.post("/businesses/{biz_id}/backup")
async def toggle_backup(biz_id: str, body: BackupBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    backup = dict(b.get("backup_roles") or {})
    if body.enabled:
        backup[body.role] = True
    else:
        backup.pop(body.role, None)
    await db.businesses.update_one({"id": biz_id}, {"$set": {"backup_roles": backup}})
    return {"ok": True, "backup_roles": backup}




# ---- Phase 2: internal training for player employees (owner offers -> player accepts/declines) ----
@api.post("/businesses/{biz_id}/player-employees/{emp_id}/offer-training")
async def offer_player_training(biz_id: str, emp_id: str, body: TrainingOfferBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    emp = await db.player_employment.find_one({"id": emp_id, "business_id": biz_id, "status": "active"}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    if emp.get("training_offer"):
        raise HTTPException(status_code=400, detail="A training offer is already pending for this employee")
    opt = await db.training_options.find_one({"id": body.option_id}, {"_id": 0})
    if not opt:
        raise HTTPException(status_code=404, detail="Training option not found")
    if p["cash"] + p["bank"] < opt["cost"]:
        raise HTTPException(status_code=400, detail=f"You can't cover the ¤ {opt['cost']} training cost")
    charge(p, opt["cost"])  # escrow: owner pays now, refunded if declined/expired
    await save_player(p)
    skill = body.skill or employment.ROLE_SKILL.get(emp.get("role")) or "fitness"
    offer = {"option_id": opt["id"], "label": opt["label"], "cost": opt["cost"],
             "skill": skill, "skill_gain": opt["skill_gain"], "desc": opt.get("desc", ""),
             "offered_at": now_utc().isoformat()}
    await db.player_employment.update_one({"id": emp_id}, {"$set": {"training_offer": offer}})
    await add_notification(db, emp["employee_player_id"], "job", "Training offer",
                           f"{b['name']} offered you training: {opt['label']} (+{opt['skill_gain']} {skill}). Accept or decline in Player Jobs.",
                           "info", "/job-market")
    await add_event(db, p["id"], f"You offered {emp['employee_name']} training: {opt['label']} (¤ {opt['cost']} reserved).", "business", "info", biz_id)
    return {"ok": True}




# ---- P2: propose a schedule change (player must accept) ----
@api.post("/businesses/{biz_id}/player-employees/{emp_id}/propose-schedule")
async def propose_schedule(biz_id: str, emp_id: str, body: ProposeScheduleBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await _get_owned_business(p, biz_id)
    emp = await db.player_employment.find_one({"id": emp_id, "business_id": biz_id, "status": "active"}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    sched = employment.make_schedule(body.schedule)
    if (emp.get("schedule") or {}).get("preset") == sched["preset"]:
        raise HTTPException(status_code=400, detail="That's already their current schedule")
    await db.player_employment.update_one({"id": emp_id}, {"$set": {"pending_schedule": {**sched, "proposed_at": now_utc().isoformat()}}})
    await add_notification(db, emp["employee_player_id"], "job", "Schedule change proposed",
                           f"{b['name']} proposed a new schedule: {sched['label']} {sched['start']:02d}:00–{sched['end']:02d}:00. Accept or decline in Player Jobs.",
                           "info", "/job-market")
    return {"ok": True}
