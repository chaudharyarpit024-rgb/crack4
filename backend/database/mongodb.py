from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import MONGO_URL, DB_NAME, logger

client: AsyncIOMotorClient = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=3000)
db = client[DB_NAME]


async def init_db():
    """Ensure database indexes are properly configured."""
    try:
        await db.rzp_events.create_index("event_id", unique=True)
        logger.info("MongoDB indexes successfully initialized.")
    except Exception:
        logger.exception("Failed to create rzp_events index")


async def close_db():
    """Close the MongoDB connection client."""
    client.close()
    logger.info("MongoDB client connection closed.")
