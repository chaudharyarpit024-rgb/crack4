import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import MONGO_URL, DB_NAME, logger

_clients: dict = {}


def get_client() -> AsyncIOMotorClient:
    """Retrieve or instantiate an AsyncIOMotorClient bound to the current running event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop not in _clients or _clients[loop] is None:
        client_kwargs = {"serverSelectionTimeoutMS": 5000}
        try:
            import certifi
            client_kwargs["tlsCAFile"] = certifi.where()
        except ImportError:
            pass
        _clients[loop] = AsyncIOMotorClient(MONGO_URL, **client_kwargs)
    return _clients[loop]


def get_db():
    """Retrieve the active database instance bound to the current client."""
    from config.settings import DB_NAME as CURRENT_DB_NAME
    import os
    # Allow DB_NAME override in test environments dynamically
    active_db_name = os.environ.get("DB_NAME", CURRENT_DB_NAME)
    return get_client()[active_db_name]


class _DBProxy:
    """Proxy object forwarding attribute and item access to the active event loop's database."""

    def __getattr__(self, name):
        return getattr(get_db(), name)

    def __getitem__(self, name):
        return get_db()[name]


class _ClientProxy:
    """Proxy object forwarding attribute access to the active event loop's client."""

    def __getattr__(self, name):
        return getattr(get_client(), name)

    def __getitem__(self, name):
        return get_client()[name]


client = _ClientProxy()
db = _DBProxy()


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
    """Close the MongoDB connection client for the active event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop in _clients and _clients[loop] is not None:
        _clients[loop].close()
        _clients.pop(loop, None)
    logger.info("MongoDB client connection closed.")

