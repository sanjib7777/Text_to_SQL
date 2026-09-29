import json
import uuid

from qdrant_client.models import PointStruct

from qdrant_test import QdrantDB
from embeddings import EmbeddingModel
from config import SQL_EXAMPLES_COLLECTION


EXAMPLES_JSON = "example.json"


class SQLExamplesIndexer:

    def __init__(self):

        self.qdrant = QdrantDB()
        self.client = self.qdrant.get_client()

        self.embedding_model = EmbeddingModel()

    def load_examples(self):

        with open(EXAMPLES_JSON, "r", encoding="utf-8") as f:
            return json.load(f)

    def index(self):

        examples = self.load_examples()

        points = []

        print(f"\nFound {len(examples)} SQL examples.\n")

        for example in examples:

            description = example["description"]

            vector = self.embedding_model.embed(description)

            payload = {
                "example_id": example["example_id"],
                "description": example["description"],
                "sql_query": example["sql_query"]
            }

            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=payload
                )
            )

            print(f"Indexed Example {example['example_id']}")

        self.client.upsert(
            collection_name=SQL_EXAMPLES_COLLECTION,
            wait=True,
            points=points
        )

        print(f"\nSuccessfully indexed {len(points)} SQL examples.")


if __name__ == "__main__":

    indexer = SQLExamplesIndexer()
    indexer.index()