"""Map edits are persisted, validated, Owner-only and conflict-aware."""
import asyncio
from copy import deepcopy
import pytest
from world_map import DEFAULT_WORLD_MAP, validate_map
from world_content import WORLD_CONTENT
from world_engine import validate_definition
from test_world import api_fixture, player


@pytest.mark.parametrize("patch", [
    {"ground_color": "red"}, {"show_compass": 1}, {"terrain": None},
    {"terrain": [{"id": "bad.id", "kind": "forest"}]},
    {"terrain": [{"id": "river", "name": "River", "kind": "river", "width": 2, "points": [[0,0]]}]},
    {"terrain": [{"id": "river", "name": "River", "kind": "river", "width": 31, "points": [[0,0],[100,100]]}]},
    {"terrain": [{"id": "lake", "name": "Lake", "kind": "lake", "width": 10, "height": 10, "x": float("nan"), "y": 20}]},
    {"terrain": [{"id": "lake", "name": "Lake", "kind": "lake", "width": 10, "height": 10, "x": True, "y": 20}]},
    {"terrain": [DEFAULT_WORLD_MAP["terrain"][0]] * 2},
])
def test_rejects_invalid_map_geometry(patch):
    with pytest.raises(ValueError):
        validate_map({**deepcopy(DEFAULT_WORLD_MAP), **patch})


def test_empty_map_and_zero_geometry_are_valid():
    validate_map({**deepcopy(DEFAULT_WORLD_MAP), "title": "", "terrain": []})
    settings = deepcopy(DEFAULT_WORLD_MAP)
    for feature in settings["terrain"]:
        feature["width"] = 0
    validate_map(settings)


@pytest.mark.parametrize("connections", [[{"to":"millhaven","minutes":1}], [{"to":"ironwood","minutes":1},{"to":"ironwood","minutes":2}]])
def test_rejects_self_and_duplicate_routes(connections):
    region=deepcopy(WORLD_CONTENT["world_regions"][1][0])
    assert region["id"] == "millhaven"
    with pytest.raises(ValueError):
        validate_definition("world_regions", {**region,"connections":connections})


def test_owner_map_edits_survive_reload_seed_and_concurrent_saves(monkeypatch):
    import httpx
    import routes.map_editor as editor
    from seed_data import seed_content
    from game_engine import get_config
    db,core,app=api_fixture(monkeypatch)
    monkeypatch.setattr(editor,"db",db)
    async def run():
        await seed_content(db)
        headers={}
        for name,role in [("owner","admin"),("friend","player")]:
            uid=(await db.users.insert_one({"email":name+"@test.local","role":role})).inserted_id
            await db.players.insert_one(player(str(uid)))
            headers[name]={"Authorization":"Bearer "+core.create_access_token(str(uid),name+"@test.local")}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as c:
            c.headers.update(headers["owner"])
            original=(await c.get("/api/admin/world/map")).json()
            region=original["regions"][0]
            edit={**region,"x":0,"y":100,"connections":[{"to":"ironwood","minutes":0}],"future_rules":{"magic":0}}
            region_path=f"/api/admin/world/map/regions/{region['id']}"
            change={"expected":region,"region":edit}
            c.headers.update(headers["friend"])
            assert (await c.get("/api/admin/world/map")).status_code==403
            assert (await c.put(region_path,json=change)).status_code==403
            c.headers.update(headers["owner"])
            assert (await c.put(region_path,json={"expected":region,"region":{**edit,"x":101}})).status_code==422
            responses=await asyncio.gather(*[c.put(region_path,json=change) for _ in range(2)])
            assert sorted(r.status_code for r in responses)==[200,409]
            assert (await db.world_regions.find_one({"id":region["id"]}))["x"]==0
            # Partial edits retain extension fields and stable IDs.
            result=await c.put(region_path,json={"expected":edit,"region":{"id":"renamed","name":"Owner village"}})
            assert result.status_code==200,result.text
            assert result.json()["region"]["future_rules"]=={"magic":0}
            assert result.json()["region"]["id"]==region["id"]
            payload={"expected":original["appearance"],"appearance":{**original["appearance"],"terrain":[],"title":"","future":{"fog":0}},"expected_start":original["start_region"],"start_region":"ironwood"}
            c.headers.update(headers["friend"])
            assert (await c.put("/api/admin/world/map/style",json=payload)).status_code==403
            c.headers.update(headers["owner"])
            assert (await c.put("/api/admin/world/map/style",json={**payload,"start_region":"missing"})).status_code==422
            await db.config.update_one({"id":"global"},{"$set":{"world.future_rule":42,"time_scale":7}})
            responses=await asyncio.gather(*[c.put("/api/admin/world/map/style",json=payload) for _ in range(2)])
            assert sorted(r.status_code for r in responses)==[200,409]
            await seed_content(db)
            cfg=await get_config(db)
            assert cfg["world"]["future_rule"]==42 and cfg["time_scale"]==7
            assert cfg["world_map"]["terrain"]==[] and cfg["world_map"]["title"]==""
            assert cfg["world_map"]["future"]=={"fog":0}
            assert cfg["world"]["start_region"]=="ironwood"
            c.headers.update(headers["friend"])
            public=(await c.get("/api/world")).json()
            assert public["map"]==cfg["world_map"]
            saved=next(r for r in public["regions"] if r["id"]==region["id"])
            assert saved["x"]==0 and saved["y"]==100 and saved["connections"][0]["minutes"]==0
            assert saved["name"]=="Owner village"
    asyncio.run(run())


def test_old_world_gets_appearance_defaults_without_reseeding_empty_landscape(monkeypatch):
    from game_engine import get_config
    import routes.map_editor as editor
    db,_,_=api_fixture(monkeypatch)
    monkeypatch.setattr(editor,"db",db)
    async def run():
        await db.config.insert_one({"id":"global","world":{"start_region":"millhaven"}})
        initial=await editor.inspect_map(admin={})
        assert initial["appearance"]==DEFAULT_WORLD_MAP
        body=editor.MapStyleBody(expected=initial["appearance"],appearance={"terrain":[]},expected_start="millhaven",start_region="millhaven")
        await editor.save_map_style(body,admin={})
        assert (await get_config(db))["world_map"]["terrain"]==[]
    asyncio.run(run())
