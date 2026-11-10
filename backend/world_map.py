"""Editable atlas appearance; all geometry uses map percentages, not screen pixels."""
import math
import re

DEFAULT_WORLD_MAP = {
    "title": "THE ASHEN MARCH",
    "ground_color": "#21372c", "water_color": "#466c6a", "road_color": "#cab784",
    "forest_color": "#759477", "mountain_color": "#91a083", "show_compass": True,
    "terrain": [
        {"id": "river_reed", "name": "Reed River", "kind": "river", "width": 4,
         "points": [[62.5, 0], [60, 15], [70, 37], [64, 68], [80, 100]]},
        {"id": "ironwood_trees", "name": "Ironwood forest", "kind": "forest", "x": 18, "y": 25, "width": 32, "height": 45},
        {"id": "northern_heights", "name": "Northern heights", "kind": "mountains", "x": 55, "y": 16, "width": 30, "height": 15},
    ],
}


def validate_map(value):
    if not isinstance(value, dict):
        raise ValueError("world_map: expected an object")
    if not isinstance(value.get("title"), str) or len(value["title"]) > 120:
        raise ValueError("Map title: use up to 120 characters")
    for key in ("ground_color", "water_color", "road_color", "forest_color", "mountain_color"):
        if not isinstance(value.get(key), str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value[key]):
            raise ValueError(key + ": use a six-digit hex colour, such as #21372c")
    if not isinstance(value.get("show_compass"), bool):
        raise ValueError("show_compass: expected true or false")
    shapes = value.get("terrain")
    if not isinstance(shapes, list) or len(shapes) > 200:
        raise ValueError("terrain: use a list of up to 200 features")
    seen = set()
    def coordinate(number, label, maximum=100):
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or not 0 <= number <= maximum:
            raise ValueError(label + f": use a finite number between 0 and {maximum}")
    for shape in shapes:
        if not isinstance(shape, dict):
            raise ValueError("Each terrain feature must be an object")
        identifier = shape.get("id")
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", identifier) or identifier in seen:
            raise ValueError("Terrain IDs must be unique and contain only letters, numbers, underscores or hyphens")
        seen.add(identifier)
        if not isinstance(shape.get("name"), str) or len(shape["name"]) > 120:
            raise ValueError("Each terrain feature needs a name up to 120 characters")
        if shape.get("kind") not in ("river", "lake", "forest", "mountains"):
            raise ValueError("Terrain kind: choose river, lake, forest or mountains")
        coordinate(shape.get("width"), "width", 30 if shape["kind"] == "river" else 100)
        if shape["kind"] == "river":
            points = shape.get("points")
            if not isinstance(points, list) or not 2 <= len(points) <= 100:
                raise ValueError("A river needs 2–100 bend points")
            for point in points:
                if not isinstance(point, list) or len(point) != 2:
                    raise ValueError("River points must be [x, y] pairs")
                coordinate(point[0], "river x"); coordinate(point[1], "river y")
        else:
            for key in ("x", "y", "height"):
                coordinate(shape.get(key), key)
    return value


def compare_query(current, updated):
    """Compare all known fields atomically, retaining concurrently added extensions."""
    query = {key: {"$eq": value} for key, value in current.items()}
    for key in updated.keys() - current.keys():
        query[key] = {"$exists": False}
    return query
