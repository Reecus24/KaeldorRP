from core import *  # noqa: F401,F403




@api.get("/shop/items")
async def shop_items(user: dict = Depends(current_user)):
    return await db.items.find({}, {"_id": 0}).to_list(200)




@api.get("/shop/stores")
async def shop_stores(user: dict = Depends(current_user)):
    await get_state(user)
    cfg = await get_config(db)
    g_now = game_now(cfg, now_utc())
    shops = await db.city_shops.find({"active": True}, {"_id": 0}).to_list(100)
    shops.sort(key=lambda s: (s.get("order", 99), s.get("name", "")))
    counts = {}
    for it in await db.items.find({}, {"_id": 0, "store_type": 1}).to_list(300):
        counts[it.get("store_type")] = counts.get(it.get("store_type"), 0) + 1
    btypes = {b["id"]: b["name"] for b in await db.business_types.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(100)}
    for s in shops:
        await _resolve_shop_stock(s, cfg)
        s["item_count"] = counts.get(s.get("category"), 0)
        s["business_type_name"] = btypes.get(s.get("business_type_id"))
        s["opening_hours"] = s.get("opening_hours") or _default_opening()
        s["is_open_now"] = employment.is_open_now(s["opening_hours"], g_now)
        stock = s.get("stock") or {}
        s["in_stock_count"] = sum(1 for v in stock.values() if v > 0)
        s["on_sale"] = any(int((c or {}).get("price_pct", 100)) < 100 for c in (s.get("items_config") or {}).values())
    return shops




@api.get("/shop/stores/{store_id}/items")
async def shop_store_items(store_id: str, user: dict = Depends(current_user)):
    await get_state(user)
    cfg = await get_config(db)
    g_now = game_now(cfg, now_utc())
    shop = await db.city_shops.find_one({"id": store_id, "active": True}, {"_id": 0})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    await _resolve_shop_stock(shop, cfg)
    shop["opening_hours"] = shop.get("opening_hours") or _default_opening()
    is_open = employment.is_open_now(shop["opening_hours"], g_now)
    shop["is_open_now"] = is_open
    cfgmap = shop.get("items_config") or {}
    stock = shop.get("stock") or {}
    items = await shop_item_docs(shop)
    out = []
    for it in items:
        ic = cfgmap.get(it["id"]) or {}
        pct = int(ic.get("price_pct", 100))
        remaining = int(stock.get(it["id"], 0))
        out.append({**it, "base_price": it["price"], "price": _shop_price(it["price"], pct),
                    "price_pct": pct, "stock": remaining,
                    "capacity": int(ic.get("capacity", SHOP_DEFAULT_CAPACITY)),
                    "sold_out": remaining <= 0})
    return {"shop": shop, "is_open_now": is_open, "items": out}




@api.post("/shop/buy")
async def shop_buy(body: BuyBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    g_now = game_now(cfg, now_utc())
    it = await db.items.find_one({"id": body.item_id}, {"_id": 0})
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    # Locate the shop: prefer the explicit store, else the active shop for this item's category.
    shop = None
    if body.store_id:
        shop = await db.city_shops.find_one({"id": body.store_id, "active": True}, {"_id": 0})
    if not shop:
        shop = await db.city_shops.find_one({"category": it.get("store_type"), "active": True}, {"_id": 0})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    await _resolve_shop_stock(shop, cfg)
    if not employment.is_open_now(shop.get("opening_hours") or _default_opening(), g_now):
        raise HTTPException(status_code=400, detail=f"{shop['name']} is closed right now. Come back during opening hours.")
    qty = max(1, body.qty)
    remaining = int((shop.get("stock") or {}).get(body.item_id, 0))
    if remaining < qty:
        raise HTTPException(status_code=400, detail=f"Out of stock — only {remaining} left. Restocks at midnight.")
    pct = int(((shop.get("items_config") or {}).get(body.item_id) or {}).get("price_pct", 100))
    unit = _shop_price(it["price"], pct)
    total = unit * qty
    if p["cash"] + p["bank"] < total:
        raise HTTPException(status_code=400, detail="Not enough money")
    charge(p, total)
    p.setdefault("inventory", {})
    p["inventory"][body.item_id] = p["inventory"].get(body.item_id, 0) + qty
    await db.city_shops.update_one({"id": shop["id"]}, {"$set": {f"stock.{body.item_id}": remaining - qty}})
    tag = f" (−{100 - pct}% sale)" if pct < 100 else (f" (+{pct - 100}% markup)" if pct > 100 else "")
    await add_event(db, p["id"], f"Bought {qty}x {it['name']} for ${total}{tag} at {shop['name']} — added to your inventory.", "shop", "info")
    await save_player(p)
    return {"ok": True}




@api.get("/bank")
async def bank_info(user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    prof = await credit_profile(p, cfg)
    prof["max_loan"] = prof["credit_limit"]  # backwards-compat alias
    return prof




@api.post("/bank/deposit")
async def deposit(body: AmountBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    amt = round(body.amount, 2)
    if amt <= 0 or p["cash"] < amt:
        raise HTTPException(status_code=400, detail="Invalid amount")
    p["cash"] -= amt
    p["bank"] += amt
    await save_player(p)
    return {"ok": True}




@api.post("/bank/withdraw")
async def withdraw(body: AmountBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    amt = round(body.amount, 2)
    if amt <= 0 or p["bank"] < amt:
        raise HTTPException(status_code=400, detail="Invalid amount")
    p["bank"] -= amt
    p["cash"] += amt
    await save_player(p)
    return {"ok": True}




@api.post("/bank/loan")
async def take_loan(body: AmountBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    prof = await credit_profile(p, cfg)
    amt = round(body.amount, 2)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")
    if prof["blocked"]:
        raise HTTPException(status_code=403, detail=f"Credit denied: {', '.join(prof['reasons']) or 'you are not eligible right now'}.")
    if amt > prof["credit_available"]:
        raise HTTPException(status_code=400,
                            detail=f"You can borrow up to ${round(prof['credit_available'])} more "
                                   f"(total limit ${prof['credit_limit']}, already used ${round(prof['debt'])}).")
    p["bank"] = round(p["bank"] + amt, 2)
    p["debt"] = round(p["debt"] + amt, 2)
    rate_pct = round(prof["interest_daily"] * 100, 2)
    await add_event(db, p["id"], f"Took a ${round(amt)} loan. Total debt now ${round(p['debt'])} at {rate_pct}%/day interest.", "finance", "warning")
    await add_notification(db, p["id"], "finance", "Loan approved",
                           f"${round(amt)} added to your bank. Total debt ${round(p['debt'])} ({rate_pct}%/day).", "info", "/bank")
    await save_player(p)
    new_prof = await credit_profile(p, cfg)
    return {"ok": True, "debt": p["debt"], "credit_limit": new_prof["credit_limit"],
            "credit_available": new_prof["credit_available"]}




@api.post("/bank/repay")
async def repay(body: AmountBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    amt = round(body.amount, 2)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")
    amt = min(amt, p["debt"])
    if amt <= 0:
        raise HTTPException(status_code=400, detail="You have no debt to repay")
    if p["cash"] + p["bank"] < amt:
        raise HTTPException(status_code=400, detail="Not enough money")
    charge(p, amt)
    p["debt"] = round(p["debt"] - amt, 2)
    if p["debt"] <= 0:
        p["debt"] = 0.0
        p["credit_missed"] = 0  # cleared the slate — restore creditworthiness
    await add_event(db, p["id"], f"Repaid ${round(amt)} of debt. Remaining debt ${round(p['debt'])}.", "finance", "success")
    await add_notification(db, p["id"], "finance", "Debt repaid", f"Repaid ${round(amt)}. Remaining debt ${round(p['debt'])}.", "success", "/bank")
    await save_player(p)
    return {"ok": True, "debt": p["debt"]}




# ============================ REAL ESTATE ============================
@api.get("/housing")
async def list_housing(user: dict = Depends(current_user)):
    p = await get_state(user)
    houses = await db.housing.find({}, {"_id": 0}).to_list(100)
    return {"current": p.get("housing"), "listings": sorted(houses, key=lambda x: x.get("tier", 1))}




@api.post("/housing/{house_id}/rent")
async def rent_house(house_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    h = await db.housing.find_one({"id": house_id}, {"_id": 0})
    if not h:
        raise HTTPException(status_code=404, detail="Housing not found")
    cur = p.get("housing") or {}
    if cur.get("id") == house_id and not cur.get("owned"):
        raise HTTPException(status_code=400, detail="You already rent this place")
    deposit = h.get("deposit", 0)
    refund = round(cur.get("deposit_paid", 0), 2) if (cur and not cur.get("owned")) else 0.0
    if p["cash"] + p["bank"] + refund < deposit:
        raise HTTPException(status_code=400, detail="Cannot afford the deposit")
    if refund > 0:
        add_money(p, refund)
        await add_event(db, p["id"], f"Deposit refunded from your old place: +${round(refund)}.", "housing", "success")
    charge(p, deposit)
    p["housing"] = {"id": house_id, "owned": False, "since": now_utc().isoformat(), "deposit_paid": deposit}
    await add_event(db, p["id"], f"You moved into {h['name']} (renting). Deposit ${round(deposit)} paid.", "housing", "success")
    await save_player(p)
    await social_engine.ensure_landlord(db, p, h)
    return {"ok": True, "refunded": refund}




@api.post("/housing/{house_id}/buy")
async def buy_house(house_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    h = await db.housing.find_one({"id": house_id}, {"_id": 0})
    if not h:
        raise HTTPException(status_code=404, detail="Housing not found")
    if h.get("buy_price", 0) <= 0:
        raise HTTPException(status_code=400, detail="This property is not for sale")
    if p["cash"] + p["bank"] < h["buy_price"]:
        raise HTTPException(status_code=400, detail="Cannot afford to buy this property")
    charge(p, h["buy_price"])
    cur = p.get("housing") or {}
    refund = round(cur.get("deposit_paid", 0), 2) if (cur and not cur.get("owned")) else 0.0
    if refund > 0:
        add_money(p, refund)
        await add_event(db, p["id"], f"Deposit refunded from your old rental: +${round(refund)}.", "housing", "success")
    p["housing"] = {"id": house_id, "owned": True, "since": now_utc().isoformat()}
    p["social_status"] = clamp(p["social_status"] + h.get("social_status", 0) * 0.2)
    await add_event(db, p["id"], f"You bought {h['name']}! No more rent.", "housing", "success")
    await save_player(p)
    return {"ok": True, "refunded": refund}




@api.post("/housing/move-out")
async def move_out(user: dict = Depends(current_user)):
    p = await get_state(user)
    cur = p.get("housing") or {}
    if not cur.get("id"):
        raise HTTPException(status_code=400, detail="You have no home to move out of")
    if cur.get("owned"):
        raise HTTPException(status_code=400, detail="You own this property — sell it instead")
    refund = round(cur.get("deposit_paid", 0), 2)
    if refund > 0:
        add_money(p, refund)
        await add_event(db, p["id"], f"You moved out. Deposit refunded: +${round(refund)}.", "housing", "success")
    else:
        await add_event(db, p["id"], "You moved out and are between homes.", "housing", "info")
    p["housing"] = {}
    await save_player(p)
    return {"ok": True, "refunded": refund}




@api.post("/housing/sell")
async def sell_property(user: dict = Depends(current_user)):
    p = await get_state(user)
    cur = p.get("housing") or {}
    if not cur.get("owned"):
        raise HTTPException(status_code=400, detail="You don't own a property to sell")
    h = await db.housing.find_one({"id": cur["id"]}, {"_id": 0})
    if not h:
        raise HTTPException(status_code=404, detail="Property not found")
    value = round(h.get("buy_price", 0) * 0.6)
    add_money(p, value)
    p["housing"] = {}
    await add_event(db, p["id"], f"You sold {h['name']} for ${value} (60% of purchase price).", "housing", "success")
    await save_player(p)
    return {"ok": True, "value": value}




# ============================ VEHICLES ============================
@api.get("/vehicles")
async def list_vehicles(user: dict = Depends(current_user)):
    p = await get_state(user)
    vehicles = await db.vehicles.find({}, {"_id": 0}).to_list(100)
    return {"owned": p.get("vehicles", []), "listings": sorted(vehicles, key=lambda x: x.get("price", 0))}


@api.get("/vehicle-categories")
async def list_vehicle_categories(user: dict = Depends(current_user)):
    p = await get_state(user)
    cats = await db.vehicle_categories.find({"active": True}, {"_id": 0}).to_list(100)
    cats.sort(key=lambda c: (c.get("order", 99), c.get("name", "")))
    vehicles = await db.vehicles.find({}, {"_id": 0, "category_id": 1}).to_list(300)
    active_ids = {c["id"] for c in cats}
    counts = {}
    for v in vehicles:
        counts[v.get("category_id")] = counts.get(v.get("category_id"), 0) + 1
    out = [{**c, "vehicle_count": counts.get(c["id"], 0)} for c in cats]
    uncat = sum(1 for v in vehicles if v.get("category_id") not in active_ids)
    if uncat > 0:
        out.append({"id": "other", "name": "Other Vehicles", "icon": "Car", "order": 999, "active": True,
                    "virtual": True, "desc": "Vehicles not yet sorted into a category.", "vehicle_count": uncat})
    return {"categories": out, "owned": p.get("vehicles", [])}


@api.get("/vehicle-categories/{category_id}")
async def vehicle_category_detail(category_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    vehicles = await db.vehicles.find({}, {"_id": 0}).to_list(300)
    if category_id == "other":
        active_ids = {c["id"] for c in await db.vehicle_categories.find({"active": True}, {"_id": 0, "id": 1}).to_list(100)}
        cat = {"id": "other", "name": "Other Vehicles", "icon": "Car", "virtual": True,
               "desc": "Vehicles not yet sorted into a category."}
        listings = [v for v in vehicles if v.get("category_id") not in active_ids]
    else:
        cat = await db.vehicle_categories.find_one({"id": category_id, "active": True}, {"_id": 0})
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")
        listings = [v for v in vehicles if v.get("category_id") == category_id]
    listings.sort(key=lambda x: x.get("price", 0))
    return {"category": cat, "listings": listings, "owned": p.get("vehicles", [])}




@api.post("/vehicles/{vehicle_id}/buy")
async def buy_vehicle(vehicle_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    v = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if p["cash"] + p["bank"] < v["price"]:
        raise HTTPException(status_code=400, detail="Cannot afford this vehicle")
    charge(p, v["price"])
    p.setdefault("vehicles", []).append({
        "instance_id": uuid.uuid4().hex, "type_id": vehicle_id, "name": v["name"],
        "condition": 100, "since": now_utc().isoformat(), "spec": v,
    })
    await add_event(db, p["id"], f"You bought a {v['name']}.", "vehicle", "success")
    await save_player(p)
    return {"ok": True}




@api.post("/vehicles/{instance_id}/sell")
async def sell_vehicle(instance_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    veh = next((x for x in p.get("vehicles", []) if x["instance_id"] == instance_id), None)
    if not veh:
        raise HTTPException(status_code=404, detail="You don't own that vehicle")
    spec = veh.get("spec", {})
    value = round(spec.get("price", 0) * spec.get("resale", 0.5) * (veh.get("condition", 100) / 100.0))
    p["vehicles"] = [x for x in p["vehicles"] if x["instance_id"] != instance_id]
    add_money(p, value)
    await add_event(db, p["id"], f"Sold your {veh['name']} for ${value}.", "vehicle", "info")
    await save_player(p)
    return {"ok": True, "value": value}




@api.get("/market/stocks")
async def market_stocks(user: dict = Depends(current_user)):
    await get_state(user)
    cfg = await get_config(db)
    return await market_engine.get_market(db, cfg, "stock")




@api.get("/market/crypto")
async def market_crypto(user: dict = Depends(current_user)):
    p = await get_state(user)
    access, reason, _ = await underworld_access(p)
    if not access:
        return {"access": False, "reason": reason, "assets": []}
    cfg = await get_config(db)
    return {"access": True, "reason": None, "assets": await market_engine.get_market(db, cfg, "crypto")}




@api.get("/market/portfolio")
async def market_portfolio(user: dict = Depends(current_user)):
    p = await get_state(user)
    return await market_engine.portfolio_view(db, p)




@api.post("/market/buy")
async def market_buy(body: TradeBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    return await _do_trade(p, body.asset_id, body.qty, "buy")




@api.post("/market/sell")
async def market_sell(body: TradeBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    return await _do_trade(p, body.asset_id, body.qty, "sell")
