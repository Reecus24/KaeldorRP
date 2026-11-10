from core import *  # noqa: F401,F403
import market_engine
from config_schema import merge_config, validate_config, validate_content, validate_json, flatten_patch
from journey_engine import COLLECTIONS as JOURNEY_COLLECTIONS, validate_definition
from realm_engine import COLLECTIONS as REALM_COLLECTIONS, validate_definition as validate_realm


@api.get("/admin/journey/templates")
async def journey_templates(admin: dict = Depends(admin_user)):
    from copy import deepcopy
    return {kind: deepcopy(CONTENT_MAP[kind][1][0]) for kind in JOURNEY_COLLECTIONS}


@api.post("/admin/journey/{kind}/validate")
async def validate_journey_draft(kind: str, body: dict, admin: dict = Depends(admin_user)):
    if kind not in JOURNEY_COLLECTIONS:
        raise HTTPException(404, "Unknown journey content type.")
    draft = {**body, "id": body.get("id") or "draft"}
    try:
        validate_definition(kind, draft)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {"valid": True}




# ============================ ADMIN ============================
@api.get("/admin/content/{ctype}")
async def admin_list(ctype: str, admin: dict = Depends(admin_user)):
    if ctype not in CONTENT_MAP:
        raise HTTPException(status_code=404, detail="Unknown content type")
    coll = CONTENT_MAP[ctype][0]
    return await db[coll].find({}, {"_id": 0}).to_list(500)




@api.post("/admin/content/{ctype}")
async def admin_create(ctype: str, body: dict, admin: dict = Depends(admin_user)):
    if ctype not in CONTENT_MAP:
        raise HTTPException(status_code=404, detail="Unknown content type")
    coll = CONTENT_MAP[ctype][0]
    if not body.get("id"):
        body["id"] = uuid.uuid4().hex
    body.pop("_id", None)
    try:
        validate_content(body)
        if ctype in REALM_COLLECTIONS:
            validate_realm(ctype, body)
        if ctype in JOURNEY_COLLECTIONS:
            validate_definition(ctype, body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if await db[coll].find_one({"id": body["id"]}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="This content ID already exists. Edit the existing entry instead.")
    await db[coll].insert_one(dict(body))
    return {"ok": True, "id": body["id"]}




@api.put("/admin/content/{ctype}/{item_id}")
async def admin_update(ctype: str, item_id: str, body: dict, admin: dict = Depends(admin_user)):
    if ctype not in CONTENT_MAP:
        raise HTTPException(status_code=404, detail="Unknown content type")
    coll = CONTENT_MAP[ctype][0]
    existing = await db[coll].find_one({"id": item_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Item not found")
    body.pop("_id", None)
    body["id"] = item_id
    try:
        validate_content(body)
        if ctype in REALM_COLLECTIONS:
            validate_realm(ctype, {k: v for k, v in {**existing, **body}.items() if k != "_id"})
        if ctype in JOURNEY_COLLECTIONS:
            validate_definition(ctype, {k: v for k, v in {**existing, **body}.items() if k != "_id"})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    # Preserve the admin's exact key order (replace_one, not $set which keeps the old DB order and
    # "scatters" the JSON). Any fields managed by other panels but not in the editor payload are
    # retained (appended) so nothing is accidentally dropped.
    merged = {**body}
    for k, v in existing.items():
        if k not in merged and k != "_id":
            merged[k] = v
    await db[coll].replace_one({"id": item_id}, merged)
    return {"ok": True}




@api.delete("/admin/content/{ctype}/{item_id}")
async def admin_delete(ctype: str, item_id: str, admin: dict = Depends(admin_user)):
    if ctype not in CONTENT_MAP:
        raise HTTPException(status_code=404, detail="Unknown content type")
    coll = CONTENT_MAP[ctype][0]
    await db[coll].delete_one({"id": item_id})
    return {"ok": True}




@api.get("/admin/config")
async def admin_get_config(admin: dict = Depends(admin_user)):
    return await get_config(db)




@api.put("/admin/config")
async def admin_update_config(body: dict, admin: dict = Depends(admin_user)):
    body.pop("_id", None)
    body.pop("id", None)
    current = await get_config(db)
    try:
        validate_config(merge_config(current, body), DEFAULT_CONFIG)
        set_ops = flatten_patch(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    set_ops["id"] = "global"
    await db.config.update_one({"id": "global"}, {"$set": set_ops}, upsert=True)
    return {"ok": True}




@api.get("/admin/players")
async def admin_players(admin: dict = Depends(admin_user)):
    players = await db.players.find({}, {"_id": 0, "name": 1, "level": 1, "cash": 1, "bank": 1,
                                         "debt": 1, "net_worth": 1, "status": 1, "reputation": 1,
                                         "legal_reputation": 1, "criminal_suspicion": 1, "social_status": 1,
                                         "health": 1, "energy": 1, "hunger": 1, "fatigue": 1,
                                         "mood": 1, "stress": 1, "skills": 1,
                                         "id": 1, "created_at": 1}).to_list(500)
    return players




@api.get("/admin/stats")
async def admin_stats(admin: dict = Depends(admin_user)):
    return {
        "users": await db.users.count_documents({}),
        "players": await db.players.count_documents({}),
        "businesses": await db.businesses.count_documents({}),
        "jobs": await db.jobs.count_documents({}),
        "actions": await db.actions.count_documents({}),
        "courses": await db.courses.count_documents({}),
    }




@api.get("/admin/overview")
async def admin_overview(admin: dict = Depends(admin_user)):
    """Realm-wide metrics for the Admin Dashboard summary strips."""
    agg = await db.players.aggregate([{"$group": {"_id": None,
        "nw": {"$sum": "$net_worth"}, "cash": {"$sum": "$coin"},
        "bank": {"$sum": "$vault"}, "debt": {"$sum": "$debt"},
        "susp": {"$avg": "$criminal_suspicion"}}}]).to_list(1)
    a = agg[0] if agg else {}
    players_total = await db.players.count_documents({})
    npc_workers = await db.employees.count_documents({"status": {"$in": ["active", "sick"]}})
    player_workers = await db.player_employment.count_documents({"status": "active"})
    return {
        "players_total": players_total,
        "players_employed": await db.players.count_documents({"job": {"$ne": None}}),
        "businesses_total": await db.businesses.count_documents({}),
        "businesses_hiring": await db.businesses.count_documents({"hiring_open": True}),
        "active_workers": npc_workers + player_workers,
        "npc_workers": npc_workers,
        "player_workers": player_workers,
        "market_value": round(a.get("nw", 0) or 0, 2),
        "total_cash": round(a.get("cash", 0) or 0, 2),
        "total_bank": round(a.get("bank", 0) or 0, 2),
        "total_debt": round(a.get("debt", 0) or 0, 2),
        "avg_net_worth": round((a.get("nw", 0) or 0) / players_total, 2) if players_total else 0,
        "avg_suspicion": round(a.get("susp", 0) or 0, 1),
        "jobs_total": await db.jobs.count_documents({}),
        "actions_total": await db.actions.count_documents({}),
        "courses_total": await db.courses.count_documents({}),
        "events_total": await db.random_events.count_documents({}),
        "illegal_total": await db.illegal_actions.count_documents({}),
        "market_assets_total": await db.market_assets.count_documents({}),
        "shops_total": await db.city_shops.count_documents({}),
        "shops_active": await db.city_shops.count_documents({"active": True}),
        "sectors_total": await db.job_sectors.count_documents({}),
        "locations_total": await db.locations.count_documents({}),
    }




@api.get("/admin/layout")
async def get_admin_layout(admin: dict = Depends(admin_user)):
    u = await db.users.find_one({"_id": ObjectId(admin["id"])}, {"_id": 0, "admin_layout": 1})
    return (u or {}).get("admin_layout") or {"order": [], "hidden": []}




@api.put("/admin/layout")
async def put_admin_layout(body: AdminLayoutBody, admin: dict = Depends(admin_user)):
    layout = {"order": body.order or [], "hidden": body.hidden or []}
    await db.users.update_one({"_id": ObjectId(admin["id"])}, {"$set": {"admin_layout": layout}})
    return {"ok": True, "layout": layout}





@api.get("/admin/feed")
async def admin_feed(limit: int = 40, types: Optional[str] = None, admin: dict = Depends(admin_user)):
    """Live realm feed — most recent events across all players (purchases, hirings, crimes, market moves...)."""
    q = {}
    if types:
        wanted = [t.strip() for t in types.split(",") if t.strip()]
        if wanted:
            q["type"] = {"$in": wanted}
    limit = min(max(limit, 1), 100)
    evs = await db.events.find(q, {"_id": 0}).sort("ts", -1).limit(limit).to_list(limit)
    pids = list({e.get("player_id") for e in evs if e.get("player_id")})
    players = await db.players.find({"id": {"$in": pids}}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    pmap = {p["id"]: p.get("name") for p in players}
    for e in evs:
        e["player_name"] = pmap.get(e.get("player_id")) or "Unknown"
    return evs




@api.get("/admin/business-economy")
async def admin_business_economy(admin: dict = Depends(admin_user)):
    out = []
    for t in await db.business_types.find({}, {"_id": 0}).to_list(100):
        out.append({
            "id": t["id"], "name": t.get("name"),
            "price": (t.get("product") or {}).get("price", 0),
            "material_cost": t.get("material_cost_override", round(sum(r.get("qty", 1) * r.get("cost", 0) for r in (t.get("recipe") or [])), 2)),
            "daily_demand": t.get("daily_demand", 0),
            "production_per_worker_hour": t.get("production_per_worker_hour", 0),
            "base_hourly_wage": t.get("base_hourly_wage"),
            "opening_hours": t.get("opening_hours") or {"open": "08:00", "close": "20:00"},
        })
    return out




@api.put("/admin/business-economy/{type_id}")
async def admin_update_business_economy(type_id: str, body: BizEconomyBody, admin: dict = Depends(admin_user)):
    t = await db.business_types.find_one({"id": type_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Unknown business type")
    tset, bset = {}, {}
    if body.price is not None:
        prod = t.get("product") or {}
        prod["price"] = round(body.price, 2)
        tset["product"] = prod
        bset["product"] = prod
    if body.material_cost is not None:
        tset["material_cost_override"] = round(body.material_cost, 2)
        bset["material_cost_override"] = round(body.material_cost, 2)
    if body.daily_demand is not None:
        tset["daily_demand"] = round(body.daily_demand, 2)
        bset["daily_demand"] = round(body.daily_demand, 2)
    if body.production_per_worker_hour is not None:
        tset["production_per_worker_hour"] = round(body.production_per_worker_hour, 3)
        bset["production_per_worker_hour"] = round(body.production_per_worker_hour, 3)
    if body.base_hourly_wage is not None:
        tset["base_hourly_wage"] = round(body.base_hourly_wage, 2)
        bset["base_hourly_wage"] = round(body.base_hourly_wage, 2)
    if body.opening_open and body.opening_close:
        o = employment.hhmm_to_float(body.opening_open)
        c = 24.0 if body.opening_close == "24:00" else employment.hhmm_to_float(body.opening_close)
        if not (0 <= o < c <= 24):
            raise HTTPException(status_code=400, detail="Opening must be before closing (00:00–24:00).")
        oh = {"open": employment.float_to_hhmm(o), "close": ("24:00" if c >= 24 else employment.float_to_hhmm(c))}
        tset["opening_hours"] = oh
        bset["opening_hours"] = oh
    if tset:
        await db.business_types.update_one({"id": type_id}, {"$set": tset})
    if bset and body.apply_existing:
        await db.businesses.update_many({"type_id": type_id}, {"$set": bset})
    return {"ok": True, "applied_to_existing": bool(bset and body.apply_existing)}




@api.put("/admin/players/{player_id}")
async def admin_update_player(player_id: str, body: AdminPlayerBody, admin: dict = Depends(admin_user)):
    p = await db.players.find_one({"id": player_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Player not found")
    # Settle the old state first. Otherwise the next player request applies all old
    # offline decay to the Owner's newly edited hunger/health/cash values.
    await resolve_player(db, p)
    upd = {}
    for f in ["cash", "bank", "debt"]:
        v = getattr(body, f)
        if v is not None:
            upd[f] = round(float(v), 2)
    for f in ["reputation", "legal_reputation", "criminal_suspicion", "social_status", "health", "energy", "hunger", "fatigue", "mood", "stress"]:
        v = getattr(body, f)
        if v is not None:
            upd[f] = clamp(float(v))
    if body.skills:
        skills = p.get("skills") or {}
        for sid, lvl in body.skills.items():
            if sid in skills:
                skills[sid]["level"] = max(1, int(lvl))
                skills[sid]["xp"] = 0
        upd["skills"] = skills
    p.update(upd)
    p["net_worth"] = await compute_net_worth(p)
    await save_player(p)
    return {"ok": True, "updated": list(upd.keys())}




@api.get("/admin/locations")
async def admin_locations(admin: dict = Depends(admin_user)):
    amap = await _archetype_label_map()
    locs = await db.locations.find({}, {"_id": 0}).to_list(200)
    locs.sort(key=lambda x: (x.get("order", 99), x.get("name", "")))
    for loc in locs:
        loc["encounters"] = _loc_encounters(loc, amap)
    return {"locations": locs,
            "archetypes": sorted(amap.values(), key=lambda a: a.get("label", "")),
            "tag_options": seed_data.ARCHETYPE_TAG_OPTIONS,
            "attr_options": ["social_status", "legal_standing", "wealth"]}




@api.post("/admin/locations")
async def admin_create_location(body: LocationBody, admin: dict = Depends(admin_user)):
    loc = body.model_dump()
    loc["id"] = uuid.uuid4().hex
    loc["npcs"] = _clean_npcs(loc.get("npcs"))
    loc["category_whitelist"] = [t for t in (loc.get("category_whitelist") or []) if t]
    loc["min_attrs"] = _clean_attrs(loc.get("min_attrs"))
    loc["max_attrs"] = _clean_attrs(loc.get("max_attrs"))
    await db.locations.insert_one({**loc})
    return {"ok": True, "id": loc["id"]}




@api.put("/admin/locations/{location_id}")
async def admin_update_location(location_id: str, body: LocationBody, admin: dict = Depends(admin_user)):
    upd = body.model_dump()
    upd["npcs"] = _clean_npcs(upd.get("npcs"))
    upd["category_whitelist"] = [t for t in (upd.get("category_whitelist") or []) if t]
    upd["min_attrs"] = _clean_attrs(upd.get("min_attrs"))
    upd["max_attrs"] = _clean_attrs(upd.get("max_attrs"))
    await db.locations.update_one({"id": location_id}, {"$set": upd})
    return {"ok": True}




@api.delete("/admin/locations/{location_id}")
async def admin_delete_location(location_id: str, admin: dict = Depends(admin_user)):
    await db.locations.delete_one({"id": location_id})
    return {"ok": True}




@api.get("/admin/city-shops")
async def admin_city_shops(admin: dict = Depends(admin_user)):
    cfg = await get_config(db)
    g_now = game_now(cfg, now_utc())
    shops = await db.city_shops.find({}, {"_id": 0}).to_list(200)
    shops.sort(key=lambda s: (s.get("order", 99), s.get("name", "")))
    counts = {}
    for it in await db.items.find({}, {"_id": 0, "store_type": 1}).to_list(300):
        counts[it.get("store_type")] = counts.get(it.get("store_type"), 0) + 1
    btypes = await db.business_types.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(100)
    locs = await db.locations.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(200)
    bmap = {b["id"]: b["name"] for b in btypes}
    all_items = await db.items.find({}, {"_id": 0, "id": 1, "name": 1, "price": 1, "store_type": 1}).to_list(300)
    all_items.sort(key=lambda x: x["name"])
    items_map = {it["id"]: it for it in all_items}
    items_by_cat = {}
    for it in all_items:
        items_by_cat.setdefault(it.get("store_type"), []).append(it)
    for s in shops:
        s["business_type_name"] = bmap.get(s.get("business_type_id"))
        s["opening_hours"] = s.get("opening_hours") or _default_opening()
        s["is_open_now"] = employment.is_open_now(s["opening_hours"], g_now)
        cfgmap = s.get("items_config") or {}
        stock = s.get("stock") or {}
        # Explicit item_ids assignment wins; else fall back to the shop's category (store_type).
        if s.get("item_ids"):
            assigned = [items_map[i] for i in s["item_ids"] if i in items_map]
        else:
            assigned = items_by_cat.get(s.get("category"), [])
        assigned = sorted(assigned, key=lambda x: x["name"])
        s["item_count"] = len(assigned)
        # Editor-friendly per-item config for THIS shop's assigned items.
        s["items"] = [{
            "id": it["id"], "name": it["name"], "base_price": it["price"], "store_type": it.get("store_type"),
            "capacity": int((cfgmap.get(it["id"]) or {}).get("capacity", SHOP_DEFAULT_CAPACITY)),
            "price_pct": int((cfgmap.get(it["id"]) or {}).get("price_pct", 100)),
            "stock": int(stock.get(it["id"], 0)),
        } for it in assigned]
    return {"shops": shops, "category_options": seed_data.ITEM_CATEGORY_OPTIONS,
            "business_types": btypes, "locations": locs,
            "all_items": all_items,
            "items_by_category": {k: sorted(v, key=lambda x: x["name"]) for k, v in items_by_cat.items()},
            "default_capacity": SHOP_DEFAULT_CAPACITY}




@api.post("/admin/city-shops")
async def admin_create_city_shop(body: CityShopBody, admin: dict = Depends(admin_user)):
    shop = body.model_dump()
    shop["opening_hours"] = _norm_opening(shop.get("opening_hours"))
    shop["items_config"] = _norm_items_config(shop.get("items_config"))
    shop["id"] = uuid.uuid4().hex
    shop["stock"] = {}
    shop["last_refresh_day"] = -1  # forces a stock refresh to capacity on first access
    await db.city_shops.insert_one({**shop})
    return {"ok": True, "id": shop["id"]}




@api.put("/admin/city-shops/{shop_id}")
async def admin_update_city_shop(shop_id: str, body: CityShopBody, admin: dict = Depends(admin_user)):
    body_set = body.model_dump()
    body_set["opening_hours"] = _norm_opening(body_set.get("opening_hours"))
    body_set["items_config"] = _norm_items_config(body_set.get("items_config"))
    # Don't wipe an explicit item assignment when the editor didn't send one.
    if body_set.get("item_ids") is None:
        body_set.pop("item_ids", None)
    # Capacities/discounts may have changed — force a stock refresh on next access.
    body_set["last_refresh_day"] = -1
    await db.city_shops.update_one({"id": shop_id}, {"$set": body_set})
    return {"ok": True}




async def _shop_effective_item_ids(shop):
    """Current item_ids, initializing from the legacy category mapping the first time an explicit
    edit happens so no existing items are lost when switching to explicit assignment."""
    ids = shop.get("item_ids")
    if ids:
        return list(ids)
    cat = await db.items.find({"store_type": shop.get("category")}, {"_id": 0, "id": 1}).to_list(300)
    return [c["id"] for c in cat]


@api.post("/admin/city-shops/{shop_id}/items")
async def admin_add_shop_item(shop_id: str, body: dict, admin: dict = Depends(admin_user)):
    """Assign an item (from the global item list) to a shop."""
    item_id = (body or {}).get("item_id")
    shop = await db.city_shops.find_one({"id": shop_id}, {"_id": 0})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    it = await db.items.find_one({"id": item_id}, {"_id": 0, "id": 1})
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    ids = await _shop_effective_item_ids(shop)
    if item_id in ids:
        raise HTTPException(status_code=400, detail="Item is already in this shop")
    ids.append(item_id)
    await db.city_shops.update_one({"id": shop_id}, {"$set": {"item_ids": ids, "last_refresh_day": -1}})
    return {"ok": True, "item_ids": ids}


@api.delete("/admin/city-shops/{shop_id}/items/{item_id}")
async def admin_remove_shop_item(shop_id: str, item_id: str, admin: dict = Depends(admin_user)):
    """Remove an item from a shop."""
    shop = await db.city_shops.find_one({"id": shop_id}, {"_id": 0})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    ids = [i for i in (await _shop_effective_item_ids(shop)) if i != item_id]
    upd = {"item_ids": ids, "last_refresh_day": -1}
    # Drop any per-item config/stock for the removed item.
    await db.city_shops.update_one({"id": shop_id}, {"$set": upd, "$unset": {f"items_config.{item_id}": "", f"stock.{item_id}": ""}})
    return {"ok": True, "item_ids": ids}




@api.delete("/admin/city-shops/{shop_id}")
async def admin_delete_city_shop(shop_id: str, admin: dict = Depends(admin_user)):
    await db.city_shops.delete_one({"id": shop_id})
    return {"ok": True}




@api.get("/admin/job-sectors")
async def admin_job_sectors(admin: dict = Depends(admin_user)):
    sectors = await db.job_sectors.find({}, {"_id": 0}).to_list(200)
    sectors.sort(key=lambda s: (s.get("order", 99), s.get("name", "")))
    jobs = await db.jobs.find({}, {"_id": 0, "id": 1, "title": 1, "category": 1, "tier": 1, "visible_in_listings": 1}).to_list(300)
    jobs.sort(key=lambda x: (x.get("tier", 1), x.get("title", "")))
    assigned = {}
    for s in sectors:
        for jid in (s.get("job_ids") or []):
            assigned[jid] = s["id"]
        s["job_count"] = len(s.get("job_ids") or [])
    return {"sectors": sectors, "jobs": jobs, "assigned": assigned}




@api.post("/admin/job-sectors")
async def admin_create_job_sector(body: JobSectorBody, admin: dict = Depends(admin_user)):
    sector = body.model_dump()
    sector["job_ids"] = list(sector.get("job_ids") or [])
    sector["id"] = uuid.uuid4().hex
    await db.job_sectors.insert_one({**sector})
    return {"ok": True, "id": sector["id"]}




@api.put("/admin/job-sectors/{sector_id}")
async def admin_update_job_sector(sector_id: str, body: JobSectorBody, admin: dict = Depends(admin_user)):
    body_set = body.model_dump()
    body_set["job_ids"] = list(body_set.get("job_ids") or [])
    await db.job_sectors.update_one({"id": sector_id}, {"$set": body_set})
    return {"ok": True}




@api.delete("/admin/job-sectors/{sector_id}")
async def admin_delete_job_sector(sector_id: str, admin: dict = Depends(admin_user)):
    await db.job_sectors.delete_one({"id": sector_id})
    return {"ok": True}


@api.put("/admin/jobs/{job_id}/visibility")
async def admin_set_job_visibility(job_id: str, body: dict, admin: dict = Depends(admin_user)):
    """Toggle whether a job appears in the Job Center listings. Hidden ('rank-up only') jobs
    stay fully reachable via the promotion system, which looks jobs up directly by id."""
    visible = bool(body.get("visible", True))
    res = await db.jobs.update_one({"id": job_id}, {"$set": {"visible_in_listings": visible}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True, "visible_in_listings": visible}


@api.get("/admin/market")
async def admin_market(admin: dict = Depends(admin_user)):
    assets = await db.market_assets.find(
        {}, {"_id": 0, "id": 1, "symbol": 1, "name": 1, "kind": 1, "price": 1, "base_price": 1}).to_list(100)
    assets.sort(key=lambda a: (a.get("kind", ""), a.get("symbol", "")))
    cfg = await get_config(db)
    t = cfg.get("tuning", {})
    return {"assets": assets,
            "tuning": {k: t.get(k) for k in ["stock_drift", "stock_volatility", "crypto_drift", "crypto_volatility"]}}


@api.post("/admin/market/refresh")
async def admin_market_refresh(admin: dict = Depends(admin_user)):
    """Force an immediate price step for every asset so admins see tuning changes take effect now."""
    cfg = await get_config(db)
    n = await market_engine.force_advance(db, cfg)
    return {"ok": True, "advanced": n}


@api.put("/admin/market/{asset_id}")
async def admin_update_market_asset(asset_id: str, body: dict, admin: dict = Depends(admin_user)):
    """Directly set an asset's live price and/or base_price (the random-walk anchor)."""
    upd = {}
    if body.get("price") is not None:
        pr = round(max(0.01, float(body["price"])), 6)
        upd["price"] = pr
        upd["prev_price"] = pr
    if body.get("base_price") is not None:
        upd["base_price"] = round(max(0.01, float(body["base_price"])), 6)
    if not upd:
        raise HTTPException(status_code=400, detail="Provide price and/or base_price")
    upd["last_update"] = market_engine._now().isoformat()
    res = await db.market_assets.update_one({"id": asset_id}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Asset not found")
    if "price" in upd:
        await db.market_assets.update_one({"id": asset_id}, {"$push": {"history": {"$each": [upd["price"]], "$slice": -40}}})
    return {"ok": True}




@api.post("/admin/market")
async def admin_create_market_asset(body: dict, admin: dict = Depends(admin_user)):
    """Create a new Stock or Relic asset. The price engine picks it up automatically."""
    symbol = str(body.get("symbol") or "").strip().upper()
    name = str(body.get("name") or "").strip()
    kind = str(body.get("kind") or "stock").strip().lower()
    if not symbol or not name:
        raise HTTPException(status_code=400, detail="Symbol and name are required")
    if kind not in ("stock", "crypto"):
        raise HTTPException(status_code=400, detail="Kind must be 'stock' or 'relic'")
    try:
        price = round(max(0.01, float(body.get("base_price", body.get("price", 1)))), 6)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Start price must be a number")
    if await db.market_assets.find_one({"symbol": symbol}):
        raise HTTPException(status_code=400, detail=f"An asset with symbol {symbol} already exists")
    slug = "".join(ch for ch in symbol.lower() if ch.isalnum())
    aid = f"{'stk' if kind == 'stock' else 'cry'}_{slug}" if slug else uuid.uuid4().hex
    if await db.market_assets.find_one({"id": aid}):
        aid = f"{aid}_{uuid.uuid4().hex[:6]}"
    doc = {"id": aid, "symbol": symbol, "name": name[:60], "kind": kind,
           "base_price": price, "price": price, "prev_price": price, "history": [price],
           "desc": str(body.get("desc") or "")[:200], "last_update": market_engine._now().isoformat()}
    await db.market_assets.insert_one({**doc})
    return {"ok": True, "asset": doc}




@api.delete("/admin/market/{asset_id}")
async def admin_delete_market_asset(asset_id: str, admin: dict = Depends(admin_user)):
    """Remove an asset from the global market. The price engine stops updating it immediately."""
    res = await db.market_assets.delete_one({"id": asset_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"ok": True}




# ------------------------- Character Origins (backgrounds) -------------------------
_BG_STAT_DEFAULTS = {"health": 100, "energy": 100, "fatigue": 0, "hunger": 20, "mood": 70, "stress": 10}


def _norm_background(body):
    label = str(body.get("label") or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="Name (label) is required")
    stats_in = body.get("stats") or {}
    stats = {k: max(0.0, min(100.0, float(stats_in.get(k, d)))) for k, d in _BG_STAT_DEFAULTS.items()}
    skills = {}
    for s, v in (body.get("skills") or {}).items():
        if s in SKILLS:
            lv = int(v)
            if lv > 0:
                skills[s] = min(20, lv)
    inv = {}
    for iid, q in (body.get("inventory") or {}).items():
        q = int(q)
        if q > 0:
            inv[iid] = q
    return {
        "label": label[:60], "desc": str(body.get("desc") or "")[:300],
        "cash": max(0.0, float(body.get("cash", 100))), "bank": max(0.0, float(body.get("bank", 0))),
        "debt": max(0.0, float(body.get("debt", 0))),
        "stats": stats, "skills": skills, "inventory": inv,
        "order": int(body.get("order", 99)), "active": bool(body.get("active", True)),
    }


@api.get("/admin/backgrounds")
async def admin_list_backgrounds(admin: dict = Depends(admin_user)):
    bgs = await db.character_backgrounds.find({}, {"_id": 0}).to_list(200)
    bgs.sort(key=lambda x: (x.get("order", 99), x.get("label", "")))
    items = await db.items.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(300)
    items.sort(key=lambda x: x["name"])
    return {"backgrounds": bgs, "skills": SKILLS, "items": items, "stat_keys": list(_BG_STAT_DEFAULTS.keys())}


@api.post("/admin/backgrounds")
async def admin_create_background(body: dict, admin: dict = Depends(admin_user)):
    doc = _norm_background(body)
    slug = "".join(ch for ch in doc["label"].lower() if ch.isalnum() or ch == "_").strip("_") or uuid.uuid4().hex[:8]
    if await db.character_backgrounds.find_one({"id": slug}):
        slug = f"{slug}_{uuid.uuid4().hex[:6]}"
    doc["id"] = slug
    await db.character_backgrounds.insert_one({**doc})
    return {"ok": True, "id": doc["id"]}


@api.put("/admin/backgrounds/{bg_id}")
async def admin_update_background(bg_id: str, body: dict, admin: dict = Depends(admin_user)):
    doc = _norm_background(body)
    res = await db.character_backgrounds.update_one({"id": bg_id}, {"$set": doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Background not found")
    return {"ok": True}


@api.delete("/admin/backgrounds/{bg_id}")
async def admin_delete_background(bg_id: str, admin: dict = Depends(admin_user)):
    if await db.character_backgrounds.count_documents({}) <= 1:
        raise HTTPException(status_code=400, detail="At least one character origin must remain")
    res = await db.character_backgrounds.delete_one({"id": bg_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Background not found")
    return {"ok": True}




async def _assign_vehicles_to_category(category_id, vehicle_ids):
    """Set category_id on the listed mounts & carts and clear it from any mount or cart that was in this
    category but is no longer listed (keeps the one-category-per-mount or cart invariant)."""
    ids = list(vehicle_ids or [])
    await db.vehicles.update_many({"category_id": category_id, "id": {"$nin": ids}}, {"$set": {"category_id": None}})
    if ids:
        await db.vehicles.update_many({"id": {"$in": ids}}, {"$set": {"category_id": category_id}})


@api.get("/admin/vehicle-categories")
async def admin_vehicle_categories(admin: dict = Depends(admin_user)):
    cats = await db.vehicle_categories.find({}, {"_id": 0}).to_list(200)
    cats.sort(key=lambda c: (c.get("order", 99), c.get("name", "")))
    vehicles = await db.vehicles.find({}, {"_id": 0, "id": 1, "name": 1, "type": 1, "price": 1, "category_id": 1}).to_list(300)
    vehicles.sort(key=lambda v: v.get("price", 0))
    counts = {}
    for v in vehicles:
        counts[v.get("category_id")] = counts.get(v.get("category_id"), 0) + 1
    for c in cats:
        c["vehicle_count"] = counts.get(c["id"], 0)
    return {"categories": cats, "vehicles": vehicles}


@api.post("/admin/vehicle-categories")
async def admin_create_vehicle_category(body: VehicleCategoryBody, admin: dict = Depends(admin_user)):
    cat = {"id": f"vcat_{uuid.uuid4().hex[:8]}", "name": body.name, "desc": body.desc or "",
           "icon": body.icon or "Car", "active": bool(body.active), "order": body.order or 50}
    await db.vehicle_categories.insert_one({**cat})
    if body.vehicle_ids is not None:
        await _assign_vehicles_to_category(cat["id"], body.vehicle_ids)
    return {"ok": True, "id": cat["id"]}


@api.put("/admin/vehicle-categories/{category_id}")
async def admin_update_vehicle_category(category_id: str, body: VehicleCategoryBody, admin: dict = Depends(admin_user)):
    upd = {"name": body.name, "desc": body.desc or "", "icon": body.icon or "Car",
           "active": bool(body.active), "order": body.order or 50}
    res = await db.vehicle_categories.update_one({"id": category_id}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    if body.vehicle_ids is not None:
        await _assign_vehicles_to_category(category_id, body.vehicle_ids)
    return {"ok": True}


@api.delete("/admin/vehicle-categories/{category_id}")
async def admin_delete_vehicle_category(category_id: str, admin: dict = Depends(admin_user)):
    await db.vehicle_categories.delete_one({"id": category_id})
    await db.vehicles.update_many({"category_id": category_id}, {"$set": {"category_id": None}})
    return {"ok": True}




@api.get("/admin/job-shifts")
async def admin_job_shifts(admin: dict = Depends(admin_user)):
    jobs = await db.jobs.find({}, {"_id": 0, "id": 1, "title": 1, "category": 1, "tier": 1,
                                   "hourly_wage": 1, "shift_options": 1}).to_list(300)
    jobs.sort(key=lambda x: (x.get("tier", 1), x.get("title", "")))
    return {"jobs": jobs}




@api.put("/admin/job-shifts/{job_id}")
async def admin_update_job_shifts(job_id: str, body: dict, admin: dict = Depends(admin_user)):
    raw = body.get("shift_options")
    if not isinstance(raw, list) or not raw:
        raise HTTPException(status_code=400, detail="At least one shift option is required")
    cleaned, seen = [], set()
    for i, s in enumerate(raw):
        if not isinstance(s, dict):
            raise HTTPException(status_code=400, detail="Each shift must be an object")
        sid = (str(s.get("id") or "").strip()) or f"shift{i + 1}"
        if sid in seen:
            raise HTTPException(status_code=400, detail=f"Duplicate shift id: {sid}")
        seen.add(sid)
        try:
            hours = int(s.get("duration_hours"))
            lo = int((s.get("start_window") or {}).get("min_hour", 0))
            hi = int((s.get("start_window") or {}).get("max_hour", 24))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Hours and window must be numbers")
        if hours < 1 or hours > 16:
            raise HTTPException(status_code=400, detail="Shift duration must be 1–16 hours")
        if not (0 <= lo <= 24) or not (0 <= hi <= 24):
            raise HTTPException(status_code=400, detail="Window hours must be 0–24")
        cleaned.append({
            "id": sid, "name": (str(s.get("name") or sid).strip()),
            "duration_hours": hours,
            "start_hour": lo,
            "start_window": {"min_hour": lo, "max_hour": hi},
            "injury_risk": max(0.0, min(1.0, float(s.get("injury_risk", 0.0) or 0.0))),
            "pay_multiplier": max(0.1, float(s.get("pay_multiplier", 1.0) or 1.0)),
            "xp_multiplier": max(0.1, float(s.get("xp_multiplier", 1.0) or 1.0)),
        })
    res = await db.jobs.update_one({"id": job_id}, {"$set": {"shift_options": cleaned}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True, "shift_options": cleaned}




@api.get("/admin/job-applications")
async def admin_job_applications(admin: dict = Depends(admin_user)):
    """Hiring-difficulty, response & reason-string tuning for every job (Admin Sandbox → Applications)."""
    jobs = await db.jobs.find({}, {"_id": 0, "id": 1, "title": 1, "category": 1, "tier": 1,
                                   "acceptance_base_chance": 1, "skill_weight": 1,
                                   "success_response": 1, "failure_response": 1, "reason_strings": 1}).to_list(300)
    for j in jobs:
        j.setdefault("acceptance_base_chance", 0.5)
        j.setdefault("skill_weight", 1.0)
        j.setdefault("success_response", "Your application for {title} was accepted — the offer is ¤ {wage}/h. Accept it to start working.")
        j.setdefault("failure_response", "Your application for {title} was rejected: {reason}.")
        # Merge stored overrides over the defaults so the editor always shows every reason key.
        rs = j.get("reason_strings") or {}
        j["reason_strings"] = {
            "accept": {**employment.DEFAULT_ACCEPT_REASONS, **(rs.get("accept") or {})},
            "reject": {**employment.DEFAULT_REJECT_REASONS, **(rs.get("reject") or {})},
        }
    jobs.sort(key=lambda x: (x.get("tier", 1), x.get("title", "")))
    return {"jobs": jobs,
            "accept_reason_keys": list(employment.DEFAULT_ACCEPT_REASONS.keys()),
            "reject_reason_keys": list(employment.DEFAULT_REJECT_REASONS.keys())}




@api.put("/admin/job-applications/{job_id}")
async def admin_update_job_applications(job_id: str, body: dict, admin: dict = Depends(admin_user)):
    """Tune a job's hire chance, skill weight, roleplay messages and per-outcome reason strings."""
    try:
        base = float(body.get("acceptance_base_chance", 0.5))
        weight = float(body.get("skill_weight", 1.0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Base chance and skill weight must be numbers")
    if not (0.0 <= base <= 1.0):
        raise HTTPException(status_code=400, detail="Acceptance base chance must be between 0.0 and 1.0")
    if not (0.0 <= weight <= 10.0):
        raise HTTPException(status_code=400, detail="Skill weight must be between 0.0 and 10.0")
    success = str(body.get("success_response") or "").strip()
    failure = str(body.get("failure_response") or "").strip()
    if not success or not failure:
        raise HTTPException(status_code=400, detail="Both success and failure responses are required")
    upd = {"acceptance_base_chance": round(base, 3), "skill_weight": round(weight, 3),
           "success_response": success[:400], "failure_response": failure[:400]}
    # Only persist reason strings that actually differ from defaults (keeps docs lean).
    rs_in = body.get("reason_strings") or {}
    accept_ov = {k: str(v)[:200] for k, v in (rs_in.get("accept") or {}).items()
                 if k in employment.DEFAULT_ACCEPT_REASONS and str(v).strip() and str(v).strip() != employment.DEFAULT_ACCEPT_REASONS[k]}
    reject_ov = {k: str(v)[:200] for k, v in (rs_in.get("reject") or {}).items()
                 if k in employment.DEFAULT_REJECT_REASONS and str(v).strip() and str(v).strip() != employment.DEFAULT_REJECT_REASONS[k]}
    upd["reason_strings"] = {"accept": accept_ov, "reject": reject_ov}
    res = await db.jobs.update_one({"id": job_id}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True, **upd}




@api.get("/admin/applications")
async def admin_list_applications(limit: int = 60, status: str = None, admin: dict = Depends(admin_user)):
    """Recent player job applications with their calculated reason, for monitoring & override."""
    q = {}
    if status in ("pending", "accepted", "rejected", "expired"):
        q["status"] = status
    apps = await db.applications.find(q, {"_id": 0}).sort("submitted_at", -1).to_list(min(max(limit, 1), 200))
    pids = list({a["player_id"] for a in apps})
    players = await db.players.find({"id": {"$in": pids}}, {"_id": 0, "id": 1, "name": 1}).to_list(len(pids) or 1)
    pmap = {p["id"]: p["name"] for p in players}
    out = [{
        "id": a["id"], "player_id": a["player_id"], "player_name": pmap.get(a["player_id"], "—"),
        "job_id": a.get("job_id"), "title": a.get("title"), "status": a.get("status"),
        "wage_offer": a.get("wage_offer"), "reason": a.get("reason"),
        "outcome_message": a.get("outcome_message"), "submitted_at": a.get("submitted_at"),
        "resolves_at": a.get("resolves_at"),
    } for a in apps]
    return {"applications": out}




@api.put("/admin/applications/{app_id}")
async def admin_override_application(app_id: str, body: dict, admin: dict = Depends(admin_user)):
    """Manually override the reason string (and optionally the outcome message) for one application."""
    app = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    upd = {}
    if "reason" in body:
        upd["reason"] = str(body.get("reason") or "").strip()[:200]
    if body.get("outcome_message") is not None:
        upd["outcome_message"] = str(body.get("outcome_message") or "").strip()[:400]
    if not upd:
        raise HTTPException(status_code=400, detail="Nothing to update")
    await db.applications.update_one({"id": app_id}, {"$set": upd})
    return {"ok": True, **upd}




@api.get("/admin/chat")
async def admin_chat(limit: int = 100, admin: dict = Depends(admin_user)):
    return await db.world_chat.find({}, {"_id": 0}).sort("ts", -1).to_list(limit)




@api.delete("/admin/chat/{message_id}")
async def admin_delete_chat(message_id: str, admin: dict = Depends(admin_user)):
    await db.world_chat.update_one({"id": message_id}, {"$set": {"deleted": True}})
    return {"ok": True}




@api.post("/admin/chat/mute")
async def admin_mute(body: MuteBody, admin: dict = Depends(admin_user)):
    until = (now_utc() + timedelta(minutes=min(max(1, body.minutes), 525600))).isoformat()
    res = await db.players.update_one({"id": body.player_id}, {"$set": {"chat_muted_until": until}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Player not found")
    return {"ok": True, "muted_until": until}




@api.post("/admin/chat/unmute")
async def admin_unmute(body: PlayerIdBody, admin: dict = Depends(admin_user)):
    await db.players.update_one({"id": body.player_id}, {"$set": {"chat_muted_until": None}})
    return {"ok": True}
