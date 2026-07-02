"""One-time migration: seed the character_backgrounds collection from CHARACTER_BACKGROUNDS
if it's empty (moves the previously hardcoded presets into the DB)."""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
from seed_data import CHARACTER_BACKGROUNDS


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    existing = await db.character_backgrounds.count_documents({})
    if existing == 0:
        await db.character_backgrounds.insert_many([{**b} for b in CHARACTER_BACKGROUNDS])
        print(f"Seeded {len(CHARACTER_BACKGROUNDS)} character backgrounds.")
    else:
        print(f"character_backgrounds already has {existing} docs — no seed needed.")
    ids = [b["id"] async for b in db.character_backgrounds.find({}, {"_id": 0, "id": 1})]
    print("backgrounds:", ids)


if __name__ == "__main__":
    asyncio.run(main())
