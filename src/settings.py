import os

USE_BITEMPORAL = os.getenv("USE_BITEMPORAL", "false").lower() == "true"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/codeintel")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
READ_MODEL_STRICT_SYNC = os.getenv("READ_MODEL_STRICT_SYNC", "true").lower() == "true"
