from core import *  # noqa: F401,F403
from config_schema import validate_content, validate_json
from world_engine import validate_definition
from world_map import validate_map, compare_query


class MapStyleBody(BaseModel):
    expected: dict
    appearance: dict
    expected_start: str
    start_region: str


class MapPlaceBody(BaseModel):
    expected: dict
    region: dict


@api.get("/admin/world/map")
async def inspect_map(admin: dict = Depends(admin_user)):
    cfg = await get_config(db)
    return {"regions": await db.world_regions.find({}, {"_id": 0}).to_list(500),
            "appearance": cfg["world_map"], "start_region": cfg["world"]["start_region"],
            "time_scale": cfg["time_scale"]}


@api.put("/admin/world/map/style")
async def save_map_style(body: MapStyleBody, admin: dict = Depends(admin_user)):
    stored = await db.config.find_one({"id": "global"})
    if not stored:
        raise HTTPException(409, "World settings are not initialized yet.")
    cfg = await get_config(db)
    current = cfg["world_map"]
    if current != body.expected or cfg["world"]["start_region"] != body.expected_start:
        raise HTTPException(409, "The map was changed in another editor. Reload the saved map before applying your draft.")
    updated = {**current, **body.appearance}
    try:
        validate_json(updated); validate_map(updated)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if body.start_region != body.expected_start and not await db.world_regions.find_one({"id": body.start_region, "active": {"$ne": False}}):
        raise HTTPException(422, "Choose an active starting location.")
    query = {"id": "global", "world_map": {"$eq": stored["world_map"]} if "world_map" in stored else {"$exists": False},
             "world.start_region": {"$eq": stored["world"]["start_region"]} if "start_region" in stored.get("world", {}) else {"$exists": False}}
    result = await db.config.update_one(query, {"$set": {"world_map": updated, "world.start_region": body.start_region}})
    if not result.matched_count:
        raise HTTPException(409, "Another Owner saved first. Reload to keep their changes.")
    return {"ok": True, "appearance": updated, "start_region": body.start_region}


@api.put("/admin/world/map/regions/{region_id}")
async def save_map_place(region_id: str, body: MapPlaceBody, admin: dict = Depends(admin_user)):
    current = await db.world_regions.find_one({"id": region_id}, {"_id": 0})
    if not current:
        raise HTTPException(404, "This location has been removed. Reload the map.")
    if current != body.expected:
        raise HTTPException(409, "This location was changed in another editor. Reload before applying your draft.")
    updated = {**current, **body.region, "id": region_id}
    updated.pop("_id", None)
    try:
        validate_content(updated); validate_definition("world_regions", updated)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    result = await db.world_regions.update_one(compare_query(current, updated), {"$set": updated})
    if not result.matched_count:
        raise HTTPException(409, "Another Owner saved first. Reload to keep their changes.")
    return {"ok": True, "region": await db.world_regions.find_one({"id": region_id}, {"_id": 0})}
