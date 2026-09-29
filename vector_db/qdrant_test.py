import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from vector_db.config import ( QDRANT_HOST, QDRANT_PORT, SCHEMA_COLLECTION, EMBEDDING_DIMENSION, DISTANCE_METRIC, SQL_EXAMPLES_COLLECTION, COLUMN_COLLECTION, SEMANTIC_CACHE )

class QdrantDB:
    def __init__(self, host=QDRANT_HOST, port=QDRANT_PORT):
        self.client = QdrantClient(host=host, port=port)

    def get_client(self):
        return self.client

    def scroll(
    self,
    collection_name,
    limit=100,
    with_payload=True
    ):
        return self.client.scroll(
            collection_name=collection_name,
            limit=limit,
            with_payload=with_payload
        )

    def collection_exists(self, collection_name):
        collections = self.client.get_collections().collections
        return any(col.name == collection_name for col in collections)

    def create_collection(self, collection_name, vector_size=EMBEDDING_DIMENSION, distance: Distance = Distance.COSINE):
        if not self.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=distance,
                )
            )
            print(f" Collection '{collection_name}' created successfully.")
        else:
            print(f" Collection '{collection_name}' already exists.")

    def delete_collection(self, collection_name):
        if self.collection_exists(collection_name):
            self.client.delete_collection(collection_name=collection_name)
            print(f" Collection '{collection_name}' deleted successfully.")
        else:
            print(f" Collection '{collection_name}' does not exist.")

if __name__ == "__main__":
    qdrant_db = QdrantDB()
    # qdrant_db.create_collection(SCHEMA_COLLECTION) 
    qdrant_db.create_collection(COLUMN_COLLECTION)