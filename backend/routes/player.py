from core import *  # noqa: F401,F403




@api.post("/auth/register")
async def register(body: RegisterBody, response: Response):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    doc = {"email": email, "password_hash": hash_password(body.password), "name": body.name,
           "role": "player", "created_at": now_utc().isoformat()}
    res = await db.users.insert_one(doc)
    uid = str(res.inserted_id)
    token = create_access_token(uid, email)
    set_auth_cookie(response, token)
    return {"token": token, "user": {"id": uid, "email": email, "name": body.name, "role": "player"}}




@api.post("/auth/login")
async def login(body: LoginBody, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    uid = str(user["_id"])
    token = create_access_token(uid, email)
    set_auth_cookie(response, token)
    return {"token": token, "user": {"id": uid, "email": email, "name": user.get("name"), "role": user.get("role", "player")}}




@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}




@api.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    return {"id": user["id"], "email": user["email"], "name": user.get("name"), "role": user.get("role", "player")}




@api.get("/backgrounds")
async def list_backgrounds():
    return [{"id": k, **v} for k, v in BACKGROUNDS.items()]




@api.post("/character/create")
async def create_character(body: CharacterBody, user: dict = Depends(current_user)):
    existing = await db.players.find_one({"user_id": user["id"]})
    if existing:
        raise HTTPException(status_code=400, detail="Character already exists")
    p = new_player(user["id"], body.name, body.background)
    await db.players.insert_one({**p})
    await add_event(db, p["id"], f"Welcome to Kaeldor, {body.name}. Your new life begins now.", "system", "info")
    return {"ok": True}




@api.get("/game/state")
async def game_state(user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    return {
        "player": p,
        "activity": serialize_activity(p),
        "confinement": confine_remaining(p),
        "net_worth": p["net_worth"],
        "net_worth_breakdown": await net_worth_parts(p),
        "time_scale": cfg["time_scale"],
        "effectiveness": round(effectiveness(p), 2),
        "game_time": game_now(cfg).isoformat(),
        "world_start_real": cfg.get("world_start_real"),
        "world_start_game": cfg.get("world_start_game"),
    }




@api.get("/game/events")
async def game_events(limit: int = 60, user: dict = Depends(current_user)):
    p = await fetch_raw_player(user["id"])
    evs = await db.events.find({"player_id": p["id"]}, {"_id": 0}).sort("ts", -1).to_list(limit)
    return evs




@api.post("/game/cancel-activity")
async def cancel_activity(user: dict = Depends(current_user)):
    p = await get_state(user)
    if not p.get("current_activity"):
        raise HTTPException(status_code=400, detail="Nothing to cancel")
    act = p["current_activity"]
    if act["kind"] in ("job", "course"):
        p["stress"] = clamp(p["stress"] + 8)
    p["current_activity"] = None
    p["status"] = "free"
    await add_event(db, p["id"], f"You abandoned '{act['name']}' early.", "system", "warning")
    await save_player(p)
    return {"ok": True}




# ============================ ACTIONS ============================
@api.get("/actions")
async def list_actions(user: dict = Depends(current_user)):
    p = await get_state(user)
    actions = await db.actions.find({}, {"_id": 0}).to_list(200)
    out = []
    for a in actions:
        ok, reason = meets_requirements(p, a.get("requirements"))
        cd = p.get("cooldowns", {}).get(a["id"])
        on_cd = cd and parse_dt(cd) > now_utc()
        out.append({**a, "available": bool(ok and not on_cd),
                    "reason": reason if not ok else ("On cooldown" if on_cd else ""),
                    "cooldown_remaining": round((parse_dt(cd) - now_utc()).total_seconds()) if on_cd else 0})
    return out




@api.post("/actions/{action_id}/start")
async def start_action(action_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    ensure_free(p)
    a = await db.actions.find_one({"id": action_id}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Action not found")
    ok, reason = meets_requirements(p, a.get("requirements"))
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    cd = p.get("cooldowns", {}).get(action_id)
    if cd and parse_dt(cd) > now_utc():
        raise HTTPException(status_code=409, detail="Action on cooldown")
    cfg = await get_config(db)
    if a.get("money_cost", 0) > 0:
        if p["cash"] + p["bank"] < a["money_cost"]:
            raise HTTPException(status_code=400, detail="Not enough money")
        charge(p, a["money_cost"])
    sleep_quality = 1.0
    if a.get("sleep"):
        hd = await db.housing.find_one({"id": p.get("housing", {}).get("id")}, {"_id": 0})
        sleep_quality = (hd or {}).get("sleep_quality", 1.0)
    payload = {
        "name": a["name"], "effects": a.get("effects", {}), "skill_xp": a.get("skill_xp", {}),
        "money_reward": a.get("money_reward", 0), "result_text": a.get("result_text", "Done."),
        "sleep": a.get("sleep", False), "sleep_quality": sleep_quality,
        "repairs_vehicle": a.get("repairs_vehicle", False), "action_id": action_id,
    }
    set_activity(p, "action", a["name"], a["duration_minutes"], cfg, payload,
                 blocking=a.get("blocking", True), sleep_flag=a.get("sleep", False))
    if a.get("cooldown_minutes", 0) > 0:
        ts = cfg["time_scale"]
        p.setdefault("cooldowns", {})[action_id] = (
            now_utc() + timedelta(seconds=real_seconds(a["duration_minutes"] + a["cooldown_minutes"], ts))).isoformat()
    await add_event(db, p["id"], f"Started: {a['name']}.", "action", "info")
    await save_player(p)
    return {"ok": True, "activity": serialize_activity(p)}




# ============================ JOBS ============================
@api.get("/jobs")
async def list_jobs(user: dict = Depends(current_user)):
    p = await get_state(user)
    jobs = await db.jobs.find({}, {"_id": 0}).to_list(200)
    out = []
    for j in jobs:
        ok, reason = meets_requirements(p, j.get("requirements"))
        out.append({**j, "qualified": ok, "reason": reason})
    return sorted(out, key=lambda x: x.get("tier", 1))




@api.get("/jobs/sectors")
async def list_job_sectors(user: dict = Depends(current_user)):
    p = await get_state(user)
    sectors = await db.job_sectors.find({"active": True}, {"_id": 0}).to_list(100)
    sectors.sort(key=lambda s: (s.get("order", 99), s.get("name", "")))
    all_jobs = {j["id"]: j for j in await db.jobs.find({}, {"_id": 0}).to_list(300)}
    out = []
    covered = set()
    for s in sectors:
        jids = [jid for jid in (s.get("job_ids") or []) if jid in all_jobs]
        covered.update(jids)
        open_count = sum(1 for jid in jids if meets_requirements(p, all_jobs[jid].get("requirements"))[0])
        out.append({**s, "job_count": len(jids), "open_count": open_count})
    # Safety net: surface any job not assigned to a sector so nothing is unreachable.
    unassigned = [j for jid, j in all_jobs.items() if jid not in covered]
    if unassigned:
        open_count = sum(1 for j in unassigned if meets_requirements(p, j.get("requirements"))[0])
        out.append({"id": "unassigned", "name": "General Listings", "icon": "Briefcase",
                    "desc": "Other openings across the city that aren't in a dedicated sector yet.",
                    "order": 999, "active": True, "virtual": True,
                    "job_count": len(unassigned), "open_count": open_count})
    return out




@api.get("/jobs/sectors/{sector_id}")
async def job_sector_detail(sector_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    all_jobs = {j["id"]: j for j in await db.jobs.find({}, {"_id": 0}).to_list(300)}
    if sector_id == "unassigned":
        sectors = await db.job_sectors.find({"active": True}, {"_id": 0, "job_ids": 1}).to_list(100)
        covered = {jid for s in sectors for jid in (s.get("job_ids") or [])}
        s = {"id": "unassigned", "name": "General Listings", "icon": "Briefcase",
             "desc": "Other openings across the city that aren't in a dedicated sector yet.", "virtual": True}
        job_ids = [jid for jid in all_jobs if jid not in covered]
    else:
        s = await db.job_sectors.find_one({"id": sector_id, "active": True}, {"_id": 0})
        if not s:
            raise HTTPException(status_code=404, detail="Sector not found")
        job_ids = s.get("job_ids") or []
    jobs = []
    for jid in job_ids:
        j = all_jobs.get(jid)
        if not j:
            continue
        ok, reason = meets_requirements(p, j.get("requirements"))
        jobs.append({**j, "qualified": ok, "reason": reason})
    jobs.sort(key=lambda x: x.get("tier", 1))
    return {"sector": s, "jobs": jobs}




@api.get("/jobs/current")
async def current_job(user: dict = Depends(current_user)):
    p = await get_state(user)
    jd = await db.jobs.find_one({"id": p["job"]["job_id"]}, {"_id": 0}) if p.get("job") else None
    npc = None
    if p.get("job"):
        promo = None
        if jd and jd.get("promotion_to"):
            target = await db.jobs.find_one({"id": jd["promotion_to"]}, {"_id": 0})
            ev = await evaluate_promotion(p, jd)
            promo = {"target": target, **ev}
        npc = {"job": p["job"], "details": jd, "promotion": promo}
    pe = await db.player_employment.find({"employee_player_id": p["id"], "status": "active"}, {"_id": 0}).to_list(50)
    cfg = await get_config(db)
    g_now = game_now(cfg, now_utc())
    player_jobs = [decorate_employment_live(e, cfg, g_now) for e in pe]
    return {"npc": npc, "player_jobs": player_jobs,
            "job": p.get("job"), "details": jd, "promotion": (npc or {}).get("promotion") if npc else None}




@api.post("/jobs/{job_id}/apply")
async def apply_job(job_id: str, body: ApplyBody = ApplyBody(), user: dict = Depends(current_user)):
    p = await get_state(user)
    j = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    ok, reason = meets_requirements(p, j.get("requirements"))
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    if p["legal_reputation"] < 25:
        raise HTTPException(status_code=403, detail="Your criminal record blocks this application.")
    existing = await db.applications.find_one({"player_id": p["id"], "job_id": job_id, "status": {"$in": ["pending", "accepted"]}}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="You already have an active application for this job.")
    cfg = await get_config(db)
    delay = employment.application_delay_minutes(j, cfg)
    now = now_utc()
    app = {"id": uuid.uuid4().hex, "player_id": p["id"], "job_id": job_id, "title": j["title"],
           "status": "pending", "submitted_at": now.isoformat(),
           "resolves_at": (now + timedelta(seconds=real_seconds(delay, cfg["time_scale"]))).isoformat(),
           "message": body.message, "wage_offer": None, "reason": None, "resolved": False}
    await db.applications.insert_one({**app})
    await add_event(db, p["id"], f"You applied for {j['title']}. A decision is expected in about {delay} minutes.", "job", "info")
    return {"ok": True, "resolves_in_minutes": delay}




@api.post("/jobs/quit")
async def quit_job(user: dict = Depends(current_user)):
    p = await get_state(user)
    if not p.get("job"):
        raise HTTPException(status_code=400, detail="You have no job")
    title = p["job"]["title"]
    p["job"] = None
    await add_event(db, p["id"], f"You quit your job as {title}.", "job", "warning")
    await save_player(p)
    return {"ok": True}




@api.post("/jobs/work")
async def work_shift(body: ShiftBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    ensure_free(p)
    if not p.get("job"):
        raise HTTPException(status_code=400, detail="You have no job")
    j = await db.jobs.find_one({"id": p["job"]["job_id"]}, {"_id": 0})
    if not j:
        raise HTTPException(status_code=404, detail="Job no longer exists")
    if p["energy"] < 10:
        raise HTTPException(status_code=400, detail="Too exhausted to work. Rest first.")
    cfg = await get_config(db)
    shifts = j.get("shift_options") or []
    dict_shifts = [s for s in shifts if isinstance(s, dict)]
    shift = None
    enforce_window = True
    if body.shift_id:
        shift = next((s for s in dict_shifts if s.get("id") == body.shift_id), None)
        if not shift:
            raise HTTPException(status_code=400, detail="Invalid shift option")
    elif body.hours is not None:
        # Legacy path (backward-compatible API callers): match by duration, no window gate.
        enforce_window = False
        shift = next((s for s in dict_shifts if s.get("duration_hours") == body.hours), None)
        if not shift and body.hours in [s for s in shifts if isinstance(s, int)]:
            shift = {"id": f"h{body.hours}", "name": f"{body.hours}h shift", "duration_hours": body.hours,
                     "injury_risk": 0.0, "pay_multiplier": 1.0, "xp_multiplier": 1.0}
        if not shift:
            raise HTTPException(status_code=400, detail="Invalid shift length")
    else:
        raise HTTPException(status_code=400, detail="No shift selected")

    if enforce_window and not shift_window_open(shift, game_now(cfg).hour):
        w = shift.get("start_window") or {}
        raise HTTPException(status_code=400,
            detail=f"The {shift.get('name', 'shift')} can only start between "
                   f"{int(w.get('min_hour', 0)):02d}:00 and {int(w.get('max_hour', 24)):02d}:00.")

    hours = int(shift["duration_hours"])
    shift_name = shift.get("name", f"{hours}h")
    payload = {
        "job_id": j["id"], "title": j["title"], "hours": hours, "category": j.get("category"),
        "hourly_wage": p["job"].get("hourly_wage", j["hourly_wage"]), "fatigue_ph": j["fatigue_per_hour"],
        "stress_ph": j["stress_per_hour"], "energy_ph": j["energy_per_hour"],
        "skill_xp": j.get("skill_xp", {}), "shift_name": shift_name,
        "pay_multiplier": float(shift.get("pay_multiplier", 1.0)),
        "xp_multiplier": float(shift.get("xp_multiplier", 1.0)),
        "injury_risk": float(shift.get("injury_risk", 0.0)),
    }
    set_activity(p, "job", f"{j['title']} — {shift_name}", hours * 60, cfg, payload, blocking=True)
    p["status"] = "working"
    await add_event(db, p["id"], f"Clocked in for {shift_name} as {j['title']}.", "job", "info")
    await save_player(p)
    return {"ok": True, "activity": serialize_activity(p)}




@api.post("/jobs/promote")
async def promote(user: dict = Depends(current_user)):
    p = await get_state(user)
    if not p.get("job"):
        raise HTTPException(status_code=400, detail="You have no job")
    jd = await db.jobs.find_one({"id": p["job"]["job_id"]}, {"_id": 0})
    if not jd or not jd.get("promotion_to"):
        raise HTTPException(status_code=400, detail="No promotion available")
    ev = await evaluate_promotion(p, jd)
    if not ev["eligible"]:
        raise HTTPException(status_code=400, detail="; ".join(ev["reasons"]) or "Not eligible for promotion yet")
    target = await db.jobs.find_one({"id": jd["promotion_to"]}, {"_id": 0})
    p["job"] = {"job_id": target["id"], "title": target["title"], "shifts_worked": 0, "hours_worked": 0,
                "reliability": 60, "hired_at": now_utc().isoformat()}
    p["reputation"] = clamp(p["reputation"] + 6)
    p["social_status"] = clamp(p["social_status"] + 5)
    await add_event(db, p["id"], f"Promoted to {target['title']}! Bigger paycheck ahead.", "job", "success")
    await save_player(p)
    await social_engine.ensure_job_contacts(db, p, target)
    return {"ok": True}




# ============================ EDUCATION ============================
@api.get("/courses")
async def list_courses(user: dict = Depends(current_user)):
    p = await get_state(user)
    courses = await db.courses.find({}, {"_id": 0}).to_list(200)
    out = []
    for c in courses:
        ok, reason = meets_requirements(p, c.get("requirements"))
        out.append({**c, "completed": c["id"] in p["education"], "qualified": ok, "reason": reason})
    return out




@api.post("/courses/{course_id}/enroll")
async def enroll_course(course_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    ensure_free(p)
    c = await db.courses.find_one({"id": course_id}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    if course_id in p["education"]:
        raise HTTPException(status_code=400, detail="Already completed")
    ok, reason = meets_requirements(p, c.get("requirements"))
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    if p["cash"] + p["bank"] < c["cost"]:
        raise HTTPException(status_code=400, detail="Not enough money for tuition")
    charge(p, c["cost"])
    cfg = await get_config(db)
    payload = {"course_id": course_id, "title": c["title"], "grants_skills": c.get("grants_skills", {})}
    set_activity(p, "course", f"Studying: {c['title']}", c["duration_minutes"], cfg, payload, blocking=False)
    p["status"] = "studying"
    await add_event(db, p["id"], f"Enrolled in {c['title']}. Study takes time but pays off.", "education", "info")
    await save_player(p)
    return {"ok": True, "activity": serialize_activity(p)}




@api.get("/inventory")
async def get_inventory(user: dict = Depends(current_user)):
    p = await get_state(user)
    inv = p.get("inventory") or {}
    equipment = p.get("equipment") or {}
    equipped_ids = {v for v in equipment.values() if v}
    items = await db.items.find({"id": {"$in": list(inv.keys())}}, {"_id": 0}).to_list(200) if inv else []
    by_id = {it["id"]: it for it in items}
    out = []
    for iid, qty in inv.items():
        it = by_id.get(iid)
        if not it or qty <= 0:
            continue
        out.append({**it, "qty": qty,
                    "usable": it.get("category") == "consumable",
                    "equippable": bool(it.get("slot")),
                    "equipped": iid in equipped_ids})
    return sorted(out, key=lambda x: x["name"])




@api.get("/equipment")
async def get_equipment(user: dict = Depends(current_user)):
    p = await get_state(user)
    eq = p.get("equipment") or {}
    ids = [i for i in eq.values() if i]
    items = await db.items.find({"id": {"$in": ids}}, {"_id": 0}).to_list(50) if ids else []
    by_id = {it["id"]: it for it in items}
    slots = [{"slot": sid, "label": meta["label"], "item": by_id.get(eq.get(sid))}
             for sid, meta in EQUIP_SLOTS.items()]
    return {"slots": slots, "bonuses": p.get("equip_bonus") or {}}




@api.post("/inventory/{item_id}/equip")
async def equip_item(item_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    inv = p.get("inventory") or {}
    if inv.get(item_id, 0) <= 0:
        raise HTTPException(status_code=400, detail="You don't own that item")
    it = await db.items.find_one({"id": item_id}, {"_id": 0})
    if not it or not it.get("slot"):
        raise HTTPException(status_code=400, detail="That item can't be equipped")
    p.setdefault("equipment", {})[it["slot"]] = item_id
    await _recompute_equip_bonus(p)
    await add_event(db, p["id"], f"You equipped {it['name']}.", "shop", "info")
    await save_player(p)
    return {"ok": True, "equipped": True, "slot": it["slot"]}




@api.post("/equipment/{slot}/unequip")
async def unequip_slot(slot: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    eq = p.get("equipment") or {}
    iid = eq.pop(slot, None)
    if iid:
        p["equipment"] = eq
        await _recompute_equip_bonus(p)
        it = await db.items.find_one({"id": iid}, {"_id": 0})
        await add_event(db, p["id"], f"You unequipped {(it or {}).get('name', 'an item')}.", "shop", "info")
        await save_player(p)
    return {"ok": True}




@api.post("/inventory/{item_id}/use")
async def use_item(item_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    inv = p.setdefault("inventory", {})
    if inv.get(item_id, 0) <= 0:
        raise HTTPException(status_code=400, detail="You don't have that item")
    it = await db.items.find_one({"id": item_id}, {"_id": 0})
    if not it:
        raise HTTPException(status_code=404, detail="Item not found")
    if it.get("category") != "consumable":
        raise HTTPException(status_code=400, detail="This item is equipment — equip it instead of using it.")
    cfg = await get_config(db)
    eff = dict(it.get("effects", {}))
    skill_eff = {k: v for k, v in eff.items() if k in SKILLS}
    for k in skill_eff:
        eff.pop(k)
        add_skill_xp(p, k, skill_eff[k], cfg)
    apply_effects(p, eff)
    inv[item_id] = inv.get(item_id, 0) - 1
    if inv[item_id] <= 0:
        inv.pop(item_id, None)
    await add_event(db, p["id"], f"You used {it['name']}.", "shop", "success")
    await save_player(p)
    return {"ok": True}




@api.get("/underworld/status")
async def underworld_status(user: dict = Depends(current_user)):
    p = await get_state(user)
    access, reason, contact = await underworld_access(p)
    return {"access": access, "reason": reason, "contact": contact,
            "criminal_suspicion": p.get("criminal_suspicion", 0),
            "min_score": UW_MIN_SCORE, "min_trust": UW_MIN_TRUST}




@api.get("/illegal-actions")
async def list_illegal(user: dict = Depends(current_user)):
    p = await get_state(user)
    access, reason, _ = await underworld_access(p)
    if not access:
        return {"access": False, "reason": reason, "actions": []}
    buff = p.get("social_buffs", {})
    until = parse_dt(buff.get("until")) if buff.get("until") else None
    risk_mult = buff["crime_risk_mult"] if (buff.get("crime_risk_mult") and until and until > now_utc()) else 1.0
    acts = await db.illegal_actions.find({}, {"_id": 0}).to_list(100)
    out = []
    for a in acts:
        ok, rsn = meets_requirements(p, a.get("requirements"))
        bust, fail = _effective_crime_risk(p, a, risk_mult)
        out.append({**a, "available": ok, "reason": rsn, "bust_risk": bust, "fail_chance": fail})
    return {"access": True, "reason": None, "actions": out}




@api.post("/illegal-actions/{action_id}/commit")
async def commit_illegal(action_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    ensure_free(p)
    access, reason, _ = await underworld_access(p)
    if not access:
        raise HTTPException(status_code=403, detail=reason)
    a = await db.illegal_actions.find_one({"id": action_id}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Action not found")
    ok, reason = meets_requirements(p, a.get("requirements"))
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    cfg = await get_config(db)
    payload = {k: a.get(k) for k in ("name", "reward_min", "reward_max", "suspicion_gain", "police_risk",
                                     "failure_chance", "jail_minutes", "fine_amount", "reputation_impact",
                                     "skill_xp", "lowers_suspicion")}
    buff = p.get("social_buffs", {})
    until = parse_dt(buff.get("until")) if buff.get("until") else None
    if buff.get("crime_risk_mult") and until and until > now_utc():
        payload["risk_mult"] = buff["crime_risk_mult"]
    set_activity(p, "illegal", a["name"], a["duration_minutes"], cfg, payload, blocking=a.get("blocking", True))
    await add_event(db, p["id"], f"You started something risky: {a['name']}...", "crime", "warning")
    await save_player(p)
    return {"ok": True, "activity": serialize_activity(p)}




@api.get("/legal/record")
async def legal_record(user: dict = Depends(current_user)):
    p = await get_state(user)
    return {"criminal_record": p.get("criminal_record", []),
            "criminal_suspicion": p["criminal_suspicion"],
            "legal_reputation": p["legal_reputation"],
            "times_jailed": p.get("stats_meta", {}).get("times_jailed", 0),
            "crimes_committed": p.get("stats_meta", {}).get("crimes_committed", 0)}




# ============================ JAIL / HOSPITAL ============================
@api.get("/jail/status")
async def jail_status(user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    rem = confine_remaining(p).get("jail", 0)
    bail = round(rem / 60 * cfg["time_scale"] * cfg["economy"]["bail_per_minute"]) if rem else 0
    return {"in_jail": p.get("status") == "jail", "remaining_seconds": rem, "bail_cost": bail}




@api.post("/jail/bail")
async def post_bail(user: dict = Depends(current_user)):
    p = await get_state(user)
    if p.get("status") != "jail":
        raise HTTPException(status_code=400, detail="You are not in jail")
    cfg = await get_config(db)
    rem = confine_remaining(p).get("jail", 0)
    bail = round(rem / 60 * cfg["time_scale"] * cfg["economy"]["bail_per_minute"])
    if p["cash"] + p["bank"] < bail:
        raise HTTPException(status_code=400, detail=f"Bail costs ${bail}, you can't afford it")
    charge(p, bail)
    ledger_add(p, "fines", -bail)
    p["jail_until"] = None
    p["status"] = "free"
    p["criminal_suspicion"] = clamp(p["criminal_suspicion"] + 5)
    await add_event(db, p["id"], f"You posted ${bail} bail and walked free.", "legal", "info")
    await save_player(p)
    return {"ok": True}




@api.get("/hospital/status")
async def hospital_status(user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    return {"in_hospital": p.get("status") == "hospital",
            "remaining_seconds": confine_remaining(p).get("hospital", 0),
            "health": p["health"], "treat_cost": cfg["economy"]["hospital_treat_cost"]}




@api.post("/hospital/treat")
async def hospital_treat(user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    cost = cfg["economy"]["hospital_treat_cost"]
    if p["cash"] + p["bank"] < cost:
        raise HTTPException(status_code=400, detail=f"Treatment costs ${cost}")
    charge(p, cost)
    if p.get("status") == "hospital":
        p["hospital_until"] = None
        p["status"] = "free"
    p["health"] = 100.0
    p["stress"] = clamp(p["stress"] - 10)
    ledger_add(p, "medical", -cost)
    await add_event(db, p["id"], f"You paid ${cost} for treatment. Health restored.", "health", "success")
    await save_player(p)
    return {"ok": True}




# ============================ CONFIG (public) ============================
@api.get("/config")
async def public_config():
    cfg = await get_config(db)
    return {"time_scale": cfg["time_scale"], "decay": cfg.get("decay", {}),
            "game_time": game_now(cfg).isoformat(),
            "world_start_real": cfg.get("world_start_real"),
            "world_start_game": cfg.get("world_start_game")}




@api.get("/training-options")
async def list_training_options(user: dict = Depends(current_user)):
    return await db.training_options.find({}, {"_id": 0}).to_list(50)




@api.get("/shift-presets")
async def shift_presets(user: dict = Depends(current_user)):
    return [{"preset": k, "label": v["label"], "start": v["start"], "end": v["end"]}
            for k, v in employment.SHIFT_PRESETS.items()]




# --- NPC applications (applicant) ---
@api.get("/jobs/applications")
async def my_applications(user: dict = Depends(current_user)):
    p = await get_state(user)
    apps = await db.applications.find({"player_id": p["id"]}, {"_id": 0}).sort("submitted_at", -1).to_list(60)
    for a in apps:
        if a["status"] == "pending":
            ra = parse_dt(a.get("resolves_at"))
            a["resolves_in"] = max(0, round((ra - now_utc()).total_seconds())) if ra else 0
    return apps




@api.post("/jobs/applications/{app_id}/accept")
async def accept_offer(app_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    a = await db.applications.find_one({"id": app_id, "player_id": p["id"]}, {"_id": 0})
    if not a or a["status"] != "accepted":
        raise HTTPException(status_code=400, detail="No active offer to accept")
    j = await db.jobs.find_one({"id": a["job_id"]}, {"_id": 0})
    if not j:
        raise HTTPException(status_code=404, detail="Job no longer exists")
    p["job"] = {"job_id": a["job_id"], "title": j["title"], "shifts_worked": 0, "hours_worked": 0, "reliability": 55,
                "hired_at": now_utc().isoformat(), "hourly_wage": a.get("wage_offer") or j["hourly_wage"]}
    await db.applications.update_one({"id": app_id}, {"$set": {"status": "hired"}})
    await db.applications.update_many({"player_id": p["id"], "status": {"$in": ["pending", "accepted"]}, "id": {"$ne": app_id}},
                                      {"$set": {"status": "withdrawn"}})
    await add_event(db, p["id"], f"You accepted the offer — now a {j['title']} at ${p['job']['hourly_wage']}/h.", "job", "success")
    await save_player(p)
    await social_engine.ensure_job_contacts(db, p, j)
    return {"ok": True}




@api.post("/jobs/applications/{app_id}/withdraw")
async def withdraw_application(app_id: str, user: dict = Depends(current_user)):
    p = await fetch_raw_player(user["id"])
    a = await db.applications.find_one({"id": app_id, "player_id": p["id"]}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Application not found")
    if a["status"] not in ("pending", "accepted"):
        raise HTTPException(status_code=400, detail="This application can't be withdrawn")
    await db.applications.update_one({"id": app_id}, {"$set": {"status": "withdrawn"}})
    return {"ok": True}




# --- Player job market (applicant) ---
@api.get("/jobs/market")
async def job_market(user: dict = Depends(current_user)):
    me = await db.players.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    cfg = await get_config(db)
    base = cfg.get("employment", {}).get("player_base_hourly_wage", 14)
    bizs = await db.businesses.find({"hiring_open": True, "bankrupt": {"$ne": True}}, {"_id": 0}).to_list(200)
    out = []
    for b in bizs:
        if me and b["player_id"] == me["id"]:
            continue
        owner = await db.players.find_one({"id": b["player_id"]}, {"_id": 0, "name": 1})
        t = await db.business_types.find_one({"id": b["type_id"]}, {"_id": 0, "name": 1, "category": 1})
        app = await db.business_applications.find_one(
            {"business_id": b["id"], "applicant_id": me["id"], "status": {"$in": ["pending", "offered"]}}, {"_id": 0}) if me else None
        emp = await db.player_employment.find_one(
            {"business_id": b["id"], "employee_player_id": me["id"], "status": "active"}, {"_id": 0}) if me else None
        out.append({"business_id": b["id"], "name": b["name"], "owner_name": owner["name"] if owner else "?",
                    "type": t["name"] if t else "", "category": t["category"] if t else "",
                    "reputation": round(b.get("reputation", 50)), "base_hourly_wage": base,
                    "roles": await _staffing_roles(b),
                    "my_status": "employed" if emp else (app["status"] if app else None)})
    return out




@api.post("/jobs/market/{business_id}/apply")
async def apply_to_business(business_id: str, body: MarketApplyBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    b = await db.businesses.find_one({"id": business_id}, {"_id": 0})
    if not b or b.get("bankrupt") or not b.get("hiring_open"):
        raise HTTPException(status_code=400, detail="This business isn't hiring")
    if b["player_id"] == p["id"]:
        raise HTTPException(status_code=400, detail="You can't apply to your own business")
    if await db.business_applications.find_one({"business_id": business_id, "applicant_id": p["id"], "status": {"$in": ["pending", "offered"]}}, {"_id": 0}):
        raise HTTPException(status_code=409, detail="You already have an active application here")
    if await db.player_employment.find_one({"business_id": business_id, "employee_player_id": p["id"], "status": "active"}, {"_id": 0}):
        raise HTTPException(status_code=409, detail="You already work here")
    cfg = await get_config(db)
    reqs = await employee_engine.get_staffing(db, b)
    role_ids = [r["role"] for r in reqs]
    role = body.role if body.role in role_ids else (role_ids[0] if role_ids else "staff")
    snap = employment.applicant_snapshot(p, cfg, role, reqs)
    app = {"id": uuid.uuid4().hex, "business_id": business_id, "business_name": b["name"], "owner_id": b["player_id"],
           "applicant_id": p["id"], "applicant_name": p["name"], "role": role,
           "message": body.message, "status": "pending", "submitted_at": now_utc().isoformat(),
           "stats": snap, "recommended_wage": snap["recommended_wage"], "wage_offer": None}
    await db.business_applications.insert_one({**app})
    await add_notification(db, b["player_id"], "business", "New job applicant", f"{p['name']} applied to {b['name']} as {role.replace('_', ' ')}.", "info", f"/businesses/{business_id}")
    await add_event(db, p["id"], f"You applied to work at {b['name']} as {role.replace('_', ' ')}.", "job", "info")
    return {"ok": True}




@api.get("/jobs/employment")
async def my_employment(user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    g_now = game_now(cfg, now_utc())
    emps = await db.player_employment.find({"employee_player_id": p["id"], "status": "active"}, {"_id": 0}).to_list(50)
    apps = await db.business_applications.find({"applicant_id": p["id"], "status": {"$in": ["pending", "offered", "rejected"]}}, {"_id": 0}).sort("submitted_at", -1).to_list(50)
    return {"employments": [decorate_employment_live(e, cfg, g_now) for e in emps], "applications": apps}




@api.post("/jobs/employment/applications/{app_id}/accept")
async def accept_business_offer(app_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    a = await db.business_applications.find_one({"id": app_id, "applicant_id": p["id"]}, {"_id": 0})
    if not a or a["status"] != "offered":
        raise HTTPException(status_code=400, detail="No offer to accept")
    b = await db.businesses.find_one({"id": a["business_id"]}, {"_id": 0})
    if not b or b.get("bankrupt"):
        raise HTTPException(status_code=400, detail="That business is unavailable")
    emp = {"id": uuid.uuid4().hex, "business_id": a["business_id"], "business_name": a["business_name"],
           "owner_id": a["owner_id"], "employee_player_id": p["id"], "employee_name": p["name"],
           "role": a.get("role", "staff"), "wage_per_hour": a["wage_offer"], "status": "active",
           "schedule": a.get("schedule") or employment.make_schedule("early"), "clocked_out_until": None,
           "hired_at": now_utc().isoformat(), "reliability": 60, "performance": 60,
           "total_hours_worked": 0, "total_wages_earned": 0.0, "total_value_added": 0.0,
           "hours_at_last_raise": 0, "last_paid_at": None, "today": None, "last_impact": None}
    await db.player_employment.insert_one({**emp})
    await db.business_applications.update_one({"id": app_id}, {"$set": {"status": "accepted"}})
    sched = emp["schedule"]
    await add_notification(db, a["owner_id"], "business", "Offer accepted", f"{p['name']} accepted your offer at {a['business_name']}.", "success", f"/businesses/{a['business_id']}")
    await add_event(db, p["id"], f"You're now working at {a['business_name']} as {a.get('role', 'staff')} (${a['wage_offer']}/h, {sched['label']} {sched['start']:02d}:00–{sched['end']:02d}:00).", "job", "success")
    return {"ok": True}




@api.post("/jobs/employment/applications/{app_id}/decline")
async def decline_business_offer(app_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    a = await db.business_applications.find_one({"id": app_id, "applicant_id": p["id"]}, {"_id": 0})
    if not a or a["status"] not in ("offered", "pending"):
        raise HTTPException(status_code=400, detail="Nothing to decline")
    was_offer = a["status"] == "offered"
    await db.business_applications.update_one({"id": app_id}, {"$set": {"status": "declined" if was_offer else "withdrawn"}})
    if was_offer:
        await add_notification(db, a["owner_id"], "business", "Offer declined", f"{p['name']} declined your offer at {a['business_name']}.", "warning", f"/businesses/{a['business_id']}")
        await add_event(db, p["id"], f"You declined the offer from {a['business_name']}.", "job", "info")
    return {"ok": True}




@api.post("/jobs/employment/applications/{app_id}/withdraw")
async def withdraw_business_application(app_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    a = await db.business_applications.find_one({"id": app_id, "applicant_id": p["id"]}, {"_id": 0})
    if not a or a["status"] not in ("pending", "offered"):
        raise HTTPException(status_code=400, detail="Nothing to withdraw")
    await db.business_applications.update_one({"id": app_id}, {"$set": {"status": "withdrawn"}})
    await add_notification(db, a["owner_id"], "business", "Applicant withdrew",
                           f"{p['name']} withdrew their application at {a['business_name']}.", "info", f"/businesses/{a['business_id']}")
    await add_event(db, p["id"], f"You withdrew your application at {a['business_name']}.", "job", "info")
    return {"ok": True}




@api.post("/jobs/employment/{emp_id}/clock-out")
async def clock_out_player_shift(emp_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    emp = await db.player_employment.find_one({"id": emp_id, "employee_player_id": p["id"], "status": "active"}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="You don't work there")
    cfg = await get_config(db)
    res = await employment.clock_out_early(db, p, cfg, emp)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("detail", "You're not on a scheduled shift right now."))
    await save_player(p)
    return res




@api.post("/jobs/employment/{emp_id}/training/{action}")
async def respond_training(emp_id: str, action: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    emp = await db.player_employment.find_one({"id": emp_id, "employee_player_id": p["id"], "status": "active"}, {"_id": 0})
    if not emp or not emp.get("training_offer"):
        raise HTTPException(status_code=404, detail="No training offer pending")
    offer = emp["training_offer"]
    owner = await db.players.find_one({"id": emp["owner_id"]}, {"_id": 0})
    if action == "accept":
        cfg = await get_config(db)
        add_skill_xp(p, offer["skill"], offer.get("skill_gain", 2) * 50, cfg)
        await save_player(p)
        await db.player_employment.update_one({"id": emp_id}, {"$set": {
            "training_offer": None, "performance": clamp(emp.get("performance", 60) + 4),
            "reliability": clamp(emp.get("reliability", 60) + 3)}})
        await add_event(db, p["id"], f"You completed training paid by {emp['business_name']}: {offer['label']} (+{offer.get('skill_gain', 2)} {offer['skill']}).", "job", "success")
        if owner:
            await add_notification(db, owner["id"], "business", "Training completed",
                                   f"{p['name']} completed {offer['label']} at {emp['business_name']}.", "success", f"/businesses/{emp['business_id']}")
            await add_event(db, owner["id"], f"{p['name']} completed training: {offer['label']}.", "business", "success", emp["business_id"])
        return {"ok": True}
    else:
        # refund the owner's escrowed cost
        if owner:
            add_money(owner, offer.get("cost", 0))
            await db.players.update_one({"id": owner["id"]}, {"$set": {"cash": owner["cash"]}})
            await add_notification(db, owner["id"], "business", "Training declined",
                                   f"{p['name']} declined {offer['label']}; ${offer.get('cost', 0)} refunded.", "warning", f"/businesses/{emp['business_id']}")
        await db.player_employment.update_one({"id": emp_id}, {"$set": {"training_offer": None}})
        await add_event(db, p["id"], f"You declined the training offer from {emp['business_name']}.", "job", "info")
        return {"ok": True}




@api.post("/jobs/employment/{emp_id}/schedule/{action}")
async def respond_schedule(emp_id: str, action: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    emp = await db.player_employment.find_one({"id": emp_id, "employee_player_id": p["id"], "status": "active"}, {"_id": 0})
    if not emp or not emp.get("pending_schedule"):
        raise HTTPException(status_code=404, detail="No schedule change pending")
    ps = emp["pending_schedule"]
    sched = {"preset": ps["preset"], "label": ps["label"], "start": ps["start"], "end": ps["end"]}
    owner_id = emp["owner_id"]
    if action == "accept":
        await db.player_employment.update_one({"id": emp_id}, {"$set": {
            "schedule": sched, "pending_schedule": None, "clocked_out_until": None}})
        await add_event(db, p["id"], f"You accepted the new schedule at {emp['business_name']}: {sched['label']}.", "job", "success")
        await add_notification(db, owner_id, "business", "Schedule change accepted",
                               f"{p['name']} accepted the {sched['label']} schedule at {emp['business_name']}.", "success", f"/businesses/{emp['business_id']}")
    else:
        await db.player_employment.update_one({"id": emp_id}, {"$set": {"pending_schedule": None}})
        await add_event(db, p["id"], f"You declined the proposed schedule change at {emp['business_name']}.", "job", "info")
        await add_notification(db, owner_id, "business", "Schedule change declined",
                               f"{p['name']} declined the {sched['label']} schedule at {emp['business_name']}.", "warning", f"/businesses/{emp['business_id']}")
    return {"ok": True}




@api.post("/jobs/employment/{emp_id}/quit")
async def quit_player_job(emp_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    emp = await db.player_employment.find_one({"id": emp_id, "employee_player_id": p["id"], "status": "active"}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employment not found")
    await db.player_employment.update_one({"id": emp_id}, {"$set": {"status": "quit"}})
    p["reputation"] = clamp(p["reputation"] - 2)
    await add_notification(db, emp["owner_id"], "business", "Employee quit", f"{p['name']} quit at {emp['business_name']}.", "warning", f"/businesses/{emp['business_id']}")
    await add_event(db, p["id"], f"You quit your job at {emp['business_name']}.", "job", "warning")
    await save_player(p)
    return {"ok": True}




@api.get("/daily-summaries")
async def daily_summaries(limit: int = 30, user: dict = Depends(current_user)):
    p = await get_state(user)
    items = await db.daily_summaries.find({"player_id": p["id"]}, {"_id": 0}).sort("real_ts", -1).to_list(limit)
    return items
