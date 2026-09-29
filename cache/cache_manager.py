import json
import hashlib
import re
from datetime import datetime, date
from decimal import Decimal
from cache.redis_client import RedisClient
from cache.config import REDIS_TTL

class CacheManager:

    def __init__(self):
        self.redis = RedisClient()

    def generate_cache_key(self, query: str, scope: str | None = None) -> str:
        """
        Generate a deterministic cache key from the query and company scope.
        """

        normalized = " ".join(query.lower().strip().split())
        if scope:
            normalized = f"{scope.lower().strip()}:{normalized}"

        return hashlib.sha256(normalized.encode()).hexdigest()

    def get_cache_by_query(self, query: str, scope: str | None = None):

        cache_key = self.generate_cache_key(query, scope)

        cached_data = self.get_cache(cache_key)

        return cached_data

    def cache_exists(self, cache_key: str):

        return self.redis.exists(cache_key)

    def _make_json_safe(self, value):
        """
        Convert Oracle/Python values into JSON serializable values.
        """

        if isinstance(value, (datetime, date)):
            return value.isoformat()

        if isinstance(value, Decimal):
            return float(value)

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")

        if isinstance(value, tuple):
            return [
                self._make_json_safe(item)
                for item in value
            ]

        if isinstance(value, list):
            return [
                self._make_json_safe(item)
                for item in value
            ]

        if isinstance(value, dict):
            return {
                key: self._make_json_safe(val)
                for key, val in value.items()
            }

        return value

    def _restore_datetime(self, value):
        """
        Convert ISO datetime strings back to Python datetime objects.
        """

        if isinstance(value, str):
            stripped_value = value.strip()
            if not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})?)?",
                stripped_value,
            ):
                return value

            try:
                if stripped_value.endswith("Z"):
                    stripped_value = stripped_value[:-1] + "+00:00"
                return datetime.fromisoformat(stripped_value)
            except ValueError:
                return value

        if isinstance(value, list):
            return [
                self._restore_datetime(item)
                for item in value
            ]

        if isinstance(value, dict):
            return {
                key: self._restore_datetime(val)
                for key, val in value.items()
            }

        return value

    def get_cache(self, cache_key: str):

        data = self.redis.get(cache_key)

        if data is None:
            return None
        data = json.loads(data)

        return self._restore_datetime(data)

    def save_cache(
        self,
        query,
        sql,
        columns,
        rows,
        execution_time=None,
        base_sql=None,
        scope=None,
    ):
        safe_rows = self._make_json_safe(rows)

        safe_columns = self._make_json_safe(columns)

        cache_key = self.generate_cache_key(query, scope)
        payload = {

            "cache_key": cache_key,

            "query": query,
            "scope": scope,

            "sql": sql,

            "base_sql": base_sql or sql,

            "columns": safe_columns,

            "rows": safe_rows,

            "row_count": len(rows),

            "execution_time": execution_time,

            "created_at": datetime.now().isoformat()

        }

        self.redis.set(
            key = cache_key,
            value = json.dumps(payload),
            ttl = REDIS_TTL
        )

        return cache_key

    def delete_cache(self, cache_key):

        self.redis.delete(cache_key)

if __name__=="__main__":
    cache = CacheManager()

    cache_key = cache.save_cache(

        query="Show previous month sales",

        sql="SELECT * FROM AI_ALLMODULE",

        columns=["MONTH", "NET SALES"],

        rows=[
            ["Shrawan", 150000],
            ["Bhadra", 210000]
        ]

    )

    cache_value = cache.get_cache(cache_key)

    print(cache_value)


    

