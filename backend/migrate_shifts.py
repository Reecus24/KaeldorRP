"""One-time migration: apply the standardized 4-shift system to all existing job docs in the DB
and clear any stale registered_shift entries (old shift schema is incompatible)."""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
from seed_data import JOB_SHIFTS


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    updated = 0
    for jid, shifts in JOB_SHIFTS.items():
        res = await db.jobs.update_one({"id": jid}, {"$set": {"shift_options": shifts}})
        updated += res.modified_count
    # Backfill hiring/application tuning defaults on every job that lacks them.
    hire = await db.jobs.update_many(
        {"acceptance_base_chance": {"$exists": False}},
        {"$set": {"acceptance_base_chance": 0.5, "skill_weight": 1.0,
                  "success_response": "Your application for {title} was accepted — the offer is ${wage}/h. Accept it to start working.",
                  "failure_response": "Your application for {title} was rejected: {reason}."}})
    # Any job not in JOB_SHIFTS keeps whatever it had. Clear stale sign-ups from the old schema.
    cleared = await db.players.update_many(
        {"registered_shift": {"$ne": None}}, {"$set": {"registered_shift": None}})
    print(f"Migrated shift_options on {updated} job docs; backfilled hiring params on {hire.modified_count}; "
          f"cleared {cleared.modified_count} stale registrations.")
    # Sanity print for one job
    j = await db.jobs.find_one({"id": "cleaner"}, {"_id": 0, "shift_options": 1, "acceptance_base_chance": 1})
    print("cleaner shifts:", [(s["id"], s["start_hour"], s["duration_hours"]) for s in j["shift_options"]])
    print("cleaner acceptance_base_chance:", j.get("acceptance_base_chance"))


if __name__ == "__main__":
    asyncio.run(main())
