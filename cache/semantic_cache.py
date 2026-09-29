from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import uuid

from vector_db.config import (
    QDRANT_HOST,
    QDRANT_PORT,
    SEMANTIC_CACHE,
)

from cache.cache_manager import CacheManager


class SemanticCache:

    def __init__(
        self,
        collection_name=SEMANTIC_CACHE,
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        similarity_threshold=0.90
    ):

        self.collection_name = collection_name
        self.similarity_threshold = similarity_threshold

        # Qdrant
        self.client = QdrantClient(
            host=host,
            port=port
        )

        # Redis
        self.cache_manager = CacheManager()



    def store(
        self,
        query: str,
        query_vector: list,
        cache_key: str
    ):
        """
        Store query embedding in Qdrant semantic cache.

        Stores:
            - query_vector -> Qdrant vector
            - query        -> payload
            - cache_key    -> payload
        """

        try:

            point = PointStruct(
                id=str(uuid.uuid4()),

                vector=query_vector,

                payload={
                    "query": query,
                    "cache_key": cache_key
                }
            )

            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )

            print("Semantic cache stored successfully.")

            return True

        except Exception as e:

            print(f"Failed to store semantic cache: {e}")

            return False

    ##############################################################
    # SEARCH SEMANTIC CACHE
    ##############################################################

    def search(
        self,
        query_vector,
        limit=1
    ):
        """
        Search Qdrant using an already generated query vector.

        Returns cached result if similarity is above threshold.
        Otherwise returns None.
        """

        try:

            results = self.client.query_points(

                collection_name=self.collection_name,

                query=query_vector,

                limit=limit,

                with_payload=True
            )

            points = results.points

            if not points:

                print("Semantic Cache: No similar query found.")

                return None

            best_match = points[0]

            score = best_match.score

            print(
                f"Semantic Cache Similarity Score: {score:.4f}"
            )

            ######################################################
            # CHECK THRESHOLD
            ######################################################

            if score < self.similarity_threshold:

                print(
                    f"Semantic Cache MISS "
                    f"(score {score:.4f} < "
                    f"threshold {self.similarity_threshold})"
                )

                return None

            print("Semantic Cache MATCH")

            ######################################################
            # GET CACHE KEY
            ######################################################

            payload = best_match.payload or {}

            cache_key = payload.get("cache_key")

            if not cache_key:

                print(
                    "Semantic Cache ERROR: "
                    "cache_key not found in Qdrant payload."
                )

                return None

            print(f"Cache Key: {cache_key}")

            ######################################################
            # GET ACTUAL DATA FROM REDIS
            ######################################################

            cached_result = self.cache_manager.get_cache(
                cache_key
            )

            if cached_result is None:

                print(
                    "Semantic Cache MISS: "
                    "Qdrant matched but Redis data not found."
                )

                return None

            print(
                "Semantic Cache HIT: "
                "Result retrieved from Redis."
            )

            ######################################################
            # RETURN RESULT
            ######################################################

            return {
                "success": True,

                "source": "exact_cache",

                "similarity_score": score,

                "cache_key": cache_key,

                "generated_sql": cached_result.get("sql"),

                "columns": cached_result.get("columns", []),

                "rows": cached_result.get("rows", []),

                "row_count": cached_result.get(
                    "row_count",
                    len(cached_result.get("rows", []))
                )
            }

        except Exception as e:

            print(
                f"Semantic cache search failed: {e}"
            )

            return None