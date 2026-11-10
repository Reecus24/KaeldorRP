"""One-way, non-destructive world conversion with original records retained for audit."""
from copy import deepcopy

MIGRATION = "ashen_march_v1"

def changed_defaults(current, old, new):
    """Change only untouched default values. Explicit zeros/empty lists/custom prose survive."""
    if current == old:
        return deepcopy(new)
    if isinstance(current, dict) and isinstance(old, dict) and isinstance(new, dict):
        result = deepcopy(current)
        for key, value in new.items():
            if key in current and key in old:
                result[key] = changed_defaults(current[key], old[key], value)
            elif key not in current and key not in old:
                result[key] = deepcopy(value)
        return result
    if isinstance(current, list) and isinstance(old, list) and isinstance(new, list) and current:
        if all(isinstance(row, dict) and "id" in row for rows in (current, old, new) for row in rows):
            before = {row["id"]: row for row in old}
            after = {row["id"]: row for row in new}
            return [changed_defaults(row, before[row["id"]], after[row["id"]])
                    if row["id"] in before and row["id"] in after else deepcopy(row) for row in current]
    return deepcopy(current)

async def migrate_realm(db, old_defaults, content_map):
    if await db.migrations.find_one({"id": MIGRATION}):
        return
    for kind, old_docs in old_defaults.items():
        new_by_id = {d["id"]: d for d in content_map[kind][1]}
        for old in old_docs:
            current = await db[kind].find_one({"id": old["id"]}, {"_id": 0})
            if current is None:
                continue  # Owner deletions remain deleted.
            await db.realm_backups.update_one({"migration": MIGRATION, "kind": kind, "id": old["id"]},
                {"$setOnInsert": {"document": deepcopy(current)}}, upsert=True)
            converted = changed_defaults(current, old, new_by_id[old["id"]])
            await db[kind].replace_one({"id": old["id"]}, converted)
    # Material/product IDs and quantities, money, skills and ownership remain intact.
    old_types = {d["id"]: d for d in old_defaults["business_types"]}
    new_types = {d["id"]: d for d in content_map["business_types"][1]}
    async for b in db.businesses.find({}, {"_id": 0}):
        before = old_types.get(b.get("type_id"))
        after = new_types.get(b.get("type_id"))
        if before and after:
            patch = {key: changed_defaults(b[key], before[key], after[key]) for key in ("recipe", "product") if key in b}
            await db.businesses.update_one({"id": b["id"]}, {"$set": patch})
    # Existing accepted quests keep their progress and economics, with untouched prose converted.
    for kind, journal_key in (("story_arcs", "stories"), ("journey_goals", "goals")):
        olds = {d["id"]: d for d in old_defaults[kind]}
        news = {d["id"]: d for d in content_map[kind][1]}
        async for p in db.players.find({"journal": {"$exists": True}}, {"_id": 0}):
            journal = p.get("journal", {})
            for run in journal.get(journal_key, {}).values():
                definition = run.get("definition", {})
                identifier = definition.get("id")
                if identifier in olds:
                    run["definition"] = changed_defaults(definition, olds[identifier], news[identifier])
            await db.players.update_one({"id": p["id"]}, {"$set": {"journal": journal}})
    jobs_old = {d["id"]: d for d in old_defaults["jobs"]}
    jobs_new = {d["id"]: d for d in content_map["jobs"][1]}
    mounts_old = {d["id"]: d for d in old_defaults["vehicles"]}
    mounts_new = {d["id"]: d for d in content_map["vehicles"][1]}
    async for p in db.players.find({}, {"_id": 0}):
        patch = {}
        job = p.get("job")
        if job and job.get("job_id") in jobs_old:
            identifier = job["job_id"]
            job["title"] = changed_defaults(job.get("title"), jobs_old[identifier]["title"], jobs_new[identifier]["title"])
            patch["job"] = job
        for v in p.get("vehicles", []):
            identifier = v.get("vehicle_id") or v.get("id") or v.get("spec", {}).get("id")
            if identifier in mounts_old:
                v["spec"] = changed_defaults(v.get("spec", {}), mounts_old[identifier], mounts_new[identifier])
                v["name"] = changed_defaults(v.get("name"), mounts_old[identifier]["name"], mounts_new[identifier]["name"])
                patch["vehicles"] = p["vehicles"]
        if patch:
            await db.players.update_one({"id": p["id"]}, {"$set": patch})
    await db.migrations.update_one({"id": MIGRATION}, {"$set": {"complete": True}}, upsert=True)
