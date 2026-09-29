import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _get_list(name: str, default: str) -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = _get_int("REDIS_PORT", 6379)
REDIS_DB = _get_int("REDIS_DB", 0)
REDIS_TTL = _get_int("REDIS_TTL", 600)

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = _get_int("QDRANT_PORT", 6333)
SCHEMA_COLLECTION = os.getenv("SCHEMA_COLLECTION", "sales_schema")
SQL_EXAMPLES_COLLECTION = os.getenv("SQL_EXAMPLES_COLLECTION", "sql_examples")
COLUMN_COLLECTION = os.getenv("COLUMN_COLLECTION", "sales_columns")
SEMANTIC_CACHE = os.getenv("SEMANTIC_CACHE", "semantic_cache")
EMBEDDING_DIMENSION = _get_int("EMBEDDING_DIMENSION", 1024)
DISTANCE_METRIC = os.getenv("DISTANCE_METRIC", "COSINE")

ORACLE_SERVICE = os.getenv("ORACLE_SERVICE", "FREEPDB1")
ORACLE_HOST = os.getenv("ORACLE_HOST", "localhost")
ORACLE_PORT = _get_int("ORACLE_PORT", 1521)
ORACLE_DB_USER = os.getenv("ORACLE_DB_USER", "suyog")
ORACLE_DB_PASS = os.getenv("ORACLE_DB_PASS", "suyogTest")
ORACLE_INSTANT_CLIENT_LOC = os.getenv("ORACLE_INSTANT_CLIENT_LOC", "")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:14b")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
LLM_PLATFORM = os.getenv("LLM_PLATFORM", "naraRouter")
NARAROUTER_BASE_URL = os.getenv("NARAROUTER_BASE_URL", "https://router.bynara.id/v1")
NARAROUTER_API_KEY = os.getenv("NARAROUTER_API_KEY", "")
XKIRO_BASE_URL = os.getenv("XKIRO_BASE_URL", "https://api.xkiro.com/v1")
XKIRO_API_KEY = os.getenv("XKIRO_API_KEY", "")

CORS_ORIGINS = _get_list("CORS_ORIGINS", "http://localhost:3000")
