from core import *  # noqa: F401,F403
from fastapi import FastAPI
import routes.player, routes.economy, routes.business, routes.social, routes.admin  # noqa: F401  (registers endpoints)
import routes.journey  # noqa: F401
import routes.realm  # noqa: F401
import routes.world  # noqa: F401
import routes.map_editor  # noqa: F401

app = FastAPI(title="Kaeldor RPG API")


# ============================ STARTUP ============================
app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_methods=["*"],
    allow_headers=["*"],
)


async def seed_demo_players():
    """Idempotently create ~3 identifiable demo players for multiplayer testing."""
    demos = [
        {"email": "mara@kaeldor.com", "name": "Mara Vance", "bg": "worker",
         "cash": 800, "bank": 1500, "devices": ["smartphone", "laptop"], "rep": 60, "job": "cashier"},
        {"email": "dovan@kaeldor.com", "name": "Dovan Reyes", "bg": "hustler",
         "cash": 1200, "bank": 4000, "devices": ["smartphone", "laptop"], "rep": 55, "business": "kiosk"},
        {"email": "kiri@kaeldor.com", "name": "Kiri Sol", "bg": "graduate",
         "cash": 500, "bank": 900, "devices": ["smartphone"], "rep": 75, "job": "sales_assistant"},
    ]
    for d in demos:
        user = await db.users.find_one({"email": d["email"]})
        if user:
            uid = str(user["_id"])
        else:
            res = await db.users.insert_one({"email": d["email"], "password_hash": hash_password("demo123"),
                                             "name": d["name"], "role": "player", "demo": True,
                                             "created_at": now_utc().isoformat()})
            uid = str(res.inserted_id)
        if await db.players.find_one({"user_id": uid}):
            continue
        p = new_player(uid, d["name"], d["bg"])
        p["cash"] = d["cash"]
        p["bank"] = d["bank"]
        p["reputation"] = d["rep"]
        p["last_seen"] = now_utc().isoformat()
        p["inventory"] = {dev: 1 for dev in d["devices"]}
        if d.get("job"):
            j = await db.jobs.find_one({"id": d["job"]}, {"_id": 0})
            if j:
                p["job"] = {"job_id": j["id"], "title": j["title"], "shifts_worked": 12, "hours_worked": 60,
                            "reliability": 70, "hired_at": now_utc().isoformat()}
        await db.players.insert_one({**p})
        if d.get("business"):
            t = await db.business_types.find_one({"id": d["business"]}, {"_id": 0})
            if t:
                recipe = t.get("recipe") or []
                target = t.get("daily_demand", 0)
                now = now_utc()
                biz = {
                    "id": uuid.uuid4().hex, "player_id": p["id"], "type_id": t["id"], "name": f"{d['name'].split()[0]}'s {t['name']}",
                    "category": t.get("category", ""), "purchase_price": t["purchase_price"],
                    "max_level": t.get("max_level", 5), "level": 1, "marketing_level": 0, "reputation": 55.0,
                    "product": t.get("product") or {}, "recipe": recipe,
                    "production_per_worker_hour": t.get("production_per_worker_hour", 0),
                    "daily_demand": target, "materials": {r["id"]: round(target * r.get("qty", 1), 3) for r in recipe},
                    "products": 0.0, "restock_target": target, "auto_restock": True,
                    "cash": 200.0, "debt": 0.0, "revenue_total": 0.0,
                    "rev_day": 0.0, "material_day": 0.0, "wages_day": 0.0, "net_day": 0.0, "exp_day": 0.0,
                    "demand_day": 0.0, "produced_day": 0.0, "sold_day": 0.0,
                    "bankrupt": False, "history": [], "created_at": now.isoformat(), "last_resolved_at": now.isoformat(),
                    "satisfaction": 80.0, "last_applicant_at": now.isoformat(), "morale_avg": 0, "hiring_open": True,
                }
                await db.businesses.insert_one({**biz})
    logger.info("Demo players seeded (mara/dovan/kiri @kaeldor.com / demo123)")


async def migrate_hours_based_promotions():
    """Convert legacy shift-count promotion requirements + player job progress to hour-based."""
    async for j in db.jobs.find({"promotion_req.shifts": {"$exists": True}}, {"_id": 0, "id": 1, "promotion_req": 1}):
        old = j.get("promotion_req") or {}
        new_req = {k: v for k, v in old.items() if k != "shifts"}
        new_req.setdefault("hours", old.get("shifts", 0) * 5)
        await db.jobs.update_one({"id": j["id"]}, {"$set": {"promotion_req": new_req}})
    async for pl in db.players.find({"job": {"$ne": None}, "job.hours_worked": {"$exists": False}}, {"_id": 0, "id": 1, "job": 1}):
        job = pl.get("job") or {}
        if job:
            await db.players.update_one({"id": pl["id"]}, {"$set": {"job.hours_worked": round(job.get("shifts_worked", 0) * 5, 1)}})
    await db.player_employment.update_many({"hours_at_last_raise": {"$exists": False}}, {"$set": {"hours_at_last_raise": 0}})


async def migrate_player_employment_hourly():
    """Convert player employment + open business offers from per-shift to per-hour wages."""
    async for e in db.player_employment.find({"wage_per_hour": {"$exists": False}}, {"_id": 0, "id": 1, "wage_per_shift": 1}):
        wph = round(e.get("wage_per_shift", 60) / 4.0, 2)
        await db.player_employment.update_one({"id": e["id"]}, {"$set": {"wage_per_hour": wph, "total_value_added": 0.0}})
    async for a in db.business_applications.find({"status": "offered", "wage_offer": {"$ne": None}, "wage_hourly_migrated": {"$ne": True}}, {"_id": 0, "id": 1, "wage_offer": 1}):
        await db.business_applications.update_one({"id": a["id"]}, {"$set": {"wage_offer": round(a["wage_offer"] / 4.0, 2), "wage_hourly_migrated": True}})
    async for e in db.player_employment.find({"schedule": {"$exists": False}}, {"_id": 0, "id": 1}):
        await db.player_employment.update_one({"id": e["id"]}, {"$set": {
            "schedule": employment.make_schedule("early"), "clocked_out_until": None}})
    # tag legacy finance-history entries so the UI can label them Forecast vs Booking
    async for b in db.businesses.find({"history": {"$exists": True, "$ne": []}}, {"_id": 0, "id": 1, "history": 1}):
        hist = b.get("history") or []
        changed = False
        for h in hist:
            if "kind" not in h:
                h["kind"] = "accrual"
                changed = True
        if changed:
            await db.businesses.update_one({"id": b["id"]}, {"$set": {"history": hist}})


async def _backfill_fields(collection, query, defaults):
    """Seed only absent fields; existing zeroes, empty lists and owner edits are authoritative."""
    for field, value in defaults.items():
        await collection.update_many(
            {**query, field: {"$exists": False}}, {"$set": {field: value}})


async def migrate_business_supply_chain():
    """Migrate business_types + existing businesses to the supply-chain model, and give NPC
    employees a schedule + hourly wage so they run through the same worker logic as players."""
    seed_types = {t["id"]: t for t in CONTENT_MAP["business_types"][1]}
    for tid, t in seed_types.items():
        await _backfill_fields(db.business_types, {"id": tid}, {
            "product": t.get("product"), "recipe": t.get("recipe"),
            "production_per_worker_hour": t.get("production_per_worker_hour"),
            "daily_demand": t.get("daily_demand"),
            "opening_hours": t.get("opening_hours") or {"open": "08:00", "close": "20:00"}})
    # Existing businesses follow their stored definition. Propagation is an explicit Owner
    # Sandbox operation, never a side effect of restarting the server.
    live_types = {t["id"]: t async for t in db.business_types.find({}, {"_id": 0})}
    now_iso = now_utc().isoformat()
    async for b in db.businesses.find({}, {"_id": 0}):
        t = live_types.get(b.get("type_id")) or {}
        recipe = t.get("recipe") or []
        target = t.get("daily_demand", 0)
        await _backfill_fields(db.businesses, {"id": b["id"]}, {
            "product": t.get("product") or {}, "recipe": recipe,
            "production_per_worker_hour": t.get("production_per_worker_hour", 0),
            "daily_demand": target, "restock_target": target, "auto_restock": True,
            "materials": {r["id"]: round(target * r.get("qty", 1), 3) for r in recipe},
            "products": 0.0, "last_resolved_at": now_iso, "bankrupt": False,
            "opening_hours": t.get("opening_hours") or {"open": "08:00", "close": "20:00"},
            "satisfaction": 80.0})
    async for e in db.employees.find({"status": {"$in": ["active", "sick"]}, "schedule": {"$exists": False}}, {"_id": 0, "id": 1, "daily_wage": 1}):
        await db.employees.update_one({"id": e["id"]}, {"$set": {
            "schedule": employment.make_schedule("early"), "wage_per_hour": round(e.get("daily_wage", 90) / 8.0, 2)}})
    # Existing worker schedules and job gates may have been customized by the Owner.
    for jd in JOBS:
        await _backfill_fields(db.jobs, {"id": jd["id"]}, {"requirements": jd.get("requirements", {})})
    # Backfill daily-summary baseline snapshot for players missing it (before -> after comparison).
    async for pl in db.players.find({"day_start_snapshot": {"$exists": False}},
                                    {"cash": 1, "bank": 1, "debt": 1, "energy": 1, "health": 1,
                                     "hunger": 1, "fatigue": 1, "stress": 1, "mood": 1, "level": 1, "id": 1}):
        snap = {"cash": round(pl.get("cash", 0), 2), "bank": round(pl.get("bank", 0), 2),
                "debt": round(pl.get("debt", 0), 2), "energy": round(pl.get("energy", 0), 1),
                "health": round(pl.get("health", 0), 1), "hunger": round(pl.get("hunger", 0), 1),
                "fatigue": round(pl.get("fatigue", 0), 1), "stress": round(pl.get("stress", 0), 1),
                "mood": round(pl.get("mood", 0), 1), "level": pl.get("level", 1)}
        await db.players.update_one({"id": pl["id"]}, {"$set": {"day_start_snapshot": snap}})
    # Initialize missing anchors without resetting a configured world pace or date.
    cfg_doc = await db.config.find_one({"id": "global"})
    if cfg_doc and not cfg_doc.get("time_synced_de"):
        try:
            from zoneinfo import ZoneInfo
            offset = datetime.now(ZoneInfo("Europe/Berlin")).utcoffset() or timedelta(hours=2)
        except Exception:
            offset = timedelta(hours=2)
        now = now_utc()
        await _backfill_fields(db.config, {"id": "global"}, {
            "time_scale": 1.0, "world_start_real": now.isoformat(),
            "world_start_game": (now + offset).isoformat()})
        await db.config.update_one({"id": "global"}, {"$set": {"time_synced_de": True}})


async def migrate_city_shops():
    """Backfill opening_hours + items_config onto existing city_shops from seed defaults (one-time)."""
    seed_map = {s["id"]: s for s in seed_data.CITY_SHOPS}
    async for s in db.city_shops.find({"opening_hours": {"$exists": False}}, {"_id": 0, "id": 1, "category": 1}):
        seed = seed_map.get(s["id"], {})
        oh = seed.get("opening_hours") or {"open": "08:00", "close": "20:00"}
        ic = seed.get("items_config") or {}
        await db.city_shops.update_one({"id": s["id"]}, {"$set": {
            "opening_hours": oh, "items_config": ic, "last_refresh_day": -1}})


async def migrate_job_sectors():
    """Insert any seed job sector whose id is missing (covers DBs seeded before new sectors were added)."""
    if await db.content_seeds.find_one({"_id": "job_sectors"}):
        return  # The content seeder owns this catalogue; preserve subsequent Owner deletions.
    for s in seed_data.JOB_SECTORS:
        existing = await db.job_sectors.find_one({"id": s["id"]}, {"_id": 0, "id": 1})
        if not existing:
            await db.job_sectors.insert_one({**s})


async def migrate_job_shift_options():
    """Upgrade legacy int shift_options ([2,4,6]) to the rich Shift & Risk schema (one-time)."""
    from seed_data import JOB_SHIFTS
    async for j in db.jobs.find({}, {"_id": 0, "id": 1, "shift_options": 1}):
        so = j.get("shift_options")
        if isinstance(so, list) and (not so or isinstance(so[0], dict)):
            continue
        if j["id"] in JOB_SHIFTS:
            new_so = [{**s} for s in JOB_SHIFTS[j["id"]]]
        else:
            hrs = [h for h in (so or [4]) if isinstance(h, int)] or [4]
            new_so = [{"id": f"h{h}", "name": f"{h}h Shift", "duration_hours": h,
                       "start_window": {"min_hour": 6, "max_hour": 20},
                       "injury_risk": 0.04, "pay_multiplier": 1.0, "xp_multiplier": 1.0} for h in hrs]
        await db.jobs.update_one({"id": j["id"]}, {"$set": {"shift_options": new_so}})


async def migrate_vehicle_categories():
    """Seed mount or cart categories if missing and backfill each mount or cart's category_id (one-time)."""
    from seed_data import VEHICLE_CATEGORIES, VEHICLE_CATEGORY_MAP
    categories = [] if await db.content_seeds.find_one({"_id": "vehicle_categories"}) else VEHICLE_CATEGORIES
    for c in categories:
        if not await db.vehicle_categories.find_one({"id": c["id"]}, {"_id": 0, "id": 1}):
            await db.vehicle_categories.insert_one({**c})
    async for v in db.vehicles.find({}, {"_id": 0, "id": 1, "category_id": 1}):
        if "category_id" not in v:
            await db.vehicles.update_one({"id": v["id"]}, {"$set": {"category_id": VEHICLE_CATEGORY_MAP.get(v["id"])}})


async def migrate_job_visibility():
    """Backfill visible_in_listings=True on any job missing the field (progressive job visibility)."""
    await db.jobs.update_many({"visible_in_listings": {"$exists": False}}, {"$set": {"visible_in_listings": True}})



@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.players.create_index("user_id", unique=True)
    await db.players.create_index("id", unique=True)
    await db.events.create_index([("player_id", 1), ("ts", -1)])
    await db.businesses.create_index("player_id")
    await db.notifications.create_index([("player_id", 1), ("ts", -1)])
    await db.world_chat.create_index([("ts", -1)])
    await db.messages.create_index([("thread_id", 1), ("ts", 1)])
    await db.messages.create_index([("to_player_id", 1), ("read", 1)])
    await db.players.create_index("last_seen")
    await db.applications.create_index([("player_id", 1), ("status", 1)])
    await db.business_applications.create_index([("business_id", 1), ("status", 1)])
    await db.player_employment.create_index([("employee_player_id", 1), ("status", 1)])
    await seed_content(db)
    await migrate_hours_based_promotions()
    await migrate_player_employment_hourly()
    await migrate_business_supply_chain()
    await migrate_city_shops()
    await migrate_job_sectors()
    await migrate_job_shift_options()
    await migrate_vehicle_categories()
    await migrate_job_visibility()
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@kaeldor.com")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    existing = await db.users.find_one({"email": admin_email})
    if not existing and admin_password:
        await db.users.insert_one({"email": admin_email, "password_hash": hash_password(admin_password),
                                   "name": "Game Master", "role": "admin", "created_at": now_utc().isoformat()})
    elif not existing:
        logger.warning("Owner account not created. Set ADMIN_EMAIL and ADMIN_PASSWORD to bootstrap a new Owner.")
    elif existing.get("role") != "admin":
        logger.warning("Configured ADMIN_EMAIL belongs to an existing non-admin account; its role was preserved.")
    if os.environ.get("SEED_DEMO_PLAYERS") == "1":
        await seed_demo_players()
    logger.info("Kaeldor RPG started.")


@app.on_event("shutdown")
async def shutdown():
    client.close()

