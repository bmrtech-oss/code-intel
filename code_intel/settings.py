import os

USE_BITEMPORAL = os.getenv("USE_BITEMPORAL", "false").lower() == "true"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/codeintel")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
READ_MODEL_STRICT_SYNC = os.getenv("READ_MODEL_STRICT_SYNC", "true").lower() == "true"
USE_TEMPORAL = os.getenv("USE_TEMPORAL", "false").lower() == "true"

# Feature Flags
def is_feature_enabled(feature_name: str, default: bool = False) -> bool:
    """Check if a feature is enabled via environment variable."""
    return os.getenv(f"FEATURE_{feature_name.upper()}", str(default)).lower() == "true"

# Security Configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama") # "ollama", "openrouter", or "google"
LLM_MODEL = os.getenv("LLM_MODEL", "phi3:mini")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
