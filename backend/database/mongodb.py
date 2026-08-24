from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import MONGO_URL, DB_NAME, logger

client: AsyncIOMotorClient = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=3000)
db = client[DB_NAME]


async def init_db():
    """Ensure database indexes are properly configured and run lightweight migrations."""
    try:
        await db.rzp_events.create_index("event_id", unique=True)
    except Exception:
        logger.exception("Failed to create rzp_events index")

    try:
        # Email verification indexes
        await db.users.create_index("email_verified")
        await db.used_verification_jti.create_index("jti", unique=True)
        # Auto-purge used jti records 2 days after use (well after 24h JWT expiry).
        await db.used_verification_jti.create_index("used_at", expireAfterSeconds=60 * 60 * 24 * 2)

        # Password reset indexes
        await db.used_reset_jti.create_index("jti", unique=True)
        await db.used_reset_jti.create_index("used_at", expireAfterSeconds=60 * 60 * 24 * 2)

        # Idempotent migration: legacy users (no email_verified field) are forced to re-verify.
        result = await db.users.update_many(
            {"email_verified": {"$exists": False}},
            {"$set": {"email_verified": False}},
        )
        if result.modified_count:
            logger.info(f"Migrated {result.modified_count} legacy users to email_verified=False")
        logger.info("MongoDB indexes and migrations applied.")
    except Exception:
        logger.exception("Failed to apply email verification indexes/migration")


async def close_db():
    """Close the MongoDB connection client."""
    client.close()
    logger.info("MongoDB client connection closed.")
