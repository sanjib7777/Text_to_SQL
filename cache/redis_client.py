from redis import Redis
from redis.exceptions import ConnectionError
from cache.config import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB
)


class RedisClient:
    _instance = None

    def __new__(cls):

        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    def __init__(self):

        if hasattr(self, "_initialized"):
            return

        self.client = Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )

        self._initialized = True

    def get_client(self):
        return self.client

    def get(self, key):

        return self.client.get(key)

    def set(self, key, value, ttl=None):

        self.client.set(name=key, value=value, ex=ttl)

    def exists(self, key):

        return self.client.exists(key)

    def delete(self, key):

        self.client.delete(key)

    def flush(self):

        self.client.flushdb()


    def ping(self):

        try:

            self.client.ping()

            print("Connected to Redis")

            return True

        except ConnectionError:

            print("Redis Connection Failed")

            return False


if __name__=="__main__":
    rc = RedisClient()
    


