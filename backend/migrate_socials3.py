"""One-off migration for the Socials 3.0 + economy rebalance overhaul.
- Re-seed relationship_actions & npc_archetypes with the new content.
- Update business_types template + existing player businesses (pph/demand rebalance).
- Normalize chronically-low business reputation.
- Delete the old "magic" social circle (auto-seeded friends/family/etc.), keep boss/landlord.
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient

import seed_data


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    # 1. Re-seed dynamic social content
    for coll, data in (("relationship_actions", seed_data.RELATIONSHIP_ACTIONS),
                       ("npc_archetypes", seed_data.NPC_ARCHETYPES)):
        await db[coll].delete_many({})
        if data:
            await db[coll].insert_many([{**d} for d in data])
        print(f"re-seeded {coll}: {len(data)} docs")

    # 2. Rebalance template + existing businesses by type
    rebal = {t["id"]: {"production_per_worker_hour": t["production_per_worker_hour"],
                       "daily_demand": t["daily_demand"]} for t in seed_data.BUSINESS_TYPES}
    for tid, patch in rebal.items():
        await db.business_types.update_one({"id": tid}, {"$set": patch})
    n = 0
    async for b in db.businesses.find({}, {"_id": 0, "id": 1, "type_id": 1, "reputation": 1}):
        patch = dict(rebal.get(b.get("type_id"), {}))
        if (b.get("reputation") or 0) < 50:
            patch["reputation"] = 50.0
        if patch:
            await db.businesses.update_one({"id": b["id"]}, {"$set": patch})
            n += 1
    print(f"rebalanced {n} businesses")

    # 3. Delete the magic social circle (keep only key contacts: boss / landlord)
    res = await db.contacts.delete_many({"$or": [{"key": None}, {"key": {"$exists": False}}]})
    print(f"deleted {res.deleted_count} auto-seeded contacts")

    print("migration complete")


if __name__ == "__main__":
    asyncio.run(main())
