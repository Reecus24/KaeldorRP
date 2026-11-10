from copy import deepcopy
from core import *  # noqa: F401,F403
import journey_engine as journey


class StoryStartBody(BaseModel):
    event_id: Optional[str] = None


class StoryChoiceBody(BaseModel):
    node_id: str
    choice_id: str


@api.get("/journey")
async def journey_view(user: dict = Depends(current_user)):
    p = await get_state(user)
    return await journey.view(db, p, await get_config(db))


@api.post("/journey/goals/{goal_id}/track")
async def track_goal(goal_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    j = journey.journal(p)
    if goal_id not in j["goals"]:
        definition = await db.journey_goals.find_one({"id": goal_id, "active": {"$ne": False}}, {"_id": 0})
        if not definition:
            raise HTTPException(404, "This ambition is not available.")
        j["goals"][goal_id] = {"definition": deepcopy(definition), "index": 0, "baseline": await journey.metrics(db, p)}
    j["focus"] = goal_id
    await save_player(p)
    return {"ok": True}


@api.post("/journey/goals/{goal_id}/claim/{milestone_id}")
async def claim_milestone(goal_id: str, milestone_id: str, user: dict = Depends(current_user)):
    p = await get_state(user)
    run = journey.journal(p)["goals"].get(goal_id)
    if not run or run["index"] >= len(run["definition"]["milestones"]):
        raise HTTPException(409, "There is no milestone to claim.")
    step = run["definition"]["milestones"][run["index"]]
    if step["id"] != milestone_id:
        raise HTTPException(409, "This milestone has already changed. Refresh your journal.")
    current = await journey.metrics(db, p)
    if not all(r["met"] for r in journey.progress(step.get("requirements", []), current, run["baseline"])):
        raise HTTPException(409, "Complete the milestone requirements first.")
    journey.reward(p, step.get("rewards", {}), await get_config(db))
    run["index"] += 1
    run["baseline"] = current
    await save_player(p)
    await add_event(db, p["id"], "Milestone reached: " + step["name"], "journey", "success")
    return {"ok": True}


@api.post("/journey/stories/{story_id}/start")
async def start_story(story_id: str, body: StoryStartBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    cfg = await get_config(db)
    j = journey.journal(p)
    d = await db.story_arcs.find_one({"id": story_id, "active": {"$ne": False}}, {"_id": 0})
    if not d:
        raise HTTPException(404, "This story is not available.")
    event = None
    if d.get("event_only"):
        event = next((e for e in await journey.city_events(db, cfg)
                      if e["id"] == body.event_id and e["is_live"] and story_id in e["arc_ids"]), None)
        if not event:
            raise HTTPException(409, "This city opportunity is not open. Check the upcoming events.")
    rid = journey.run_id(story_id, event)
    if rid in j["stories"]:
        raise HTTPException(409, "You have already accepted this story.")
    if sum(not r.get("completed") for r in j["stories"].values()) >= cfg["journey"]["max_active_stories"]:
        raise HTTPException(409, "Finish an active story before accepting another.")
    current = await journey.metrics(db, p)
    if not all(r["met"] for r in journey.progress(d.get("requirements", []), current)):
        raise HTTPException(409, "You do not meet the entry requirements yet.")
    j["stories"][rid] = {"definition": deepcopy(d), "node": d["start"], "baseline": current,
                         "history": [], "completed": False, "started_at": now_utc().isoformat()}
    await save_player(p)
    return {"ok": True, "run_id": rid}


@api.post("/journey/stories/{run_id}/choose")
async def story_choice(run_id: str, body: StoryChoiceBody, user: dict = Depends(current_user)):
    p = await get_state(user)
    try:
        result = journey.choose(p, run_id, body.node_id, body.choice_id,
                                await journey.metrics(db, p), await get_config(db))
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    await save_player(p)
    await add_event(db, p["id"], result["outcome"] or "A new chapter in your story.", "journey", "success")
    return result
