import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from qdrant_client.models import Filter
from vector_db.embeddings import EmbeddingModel
from vector_db.qdrant_test import QdrantDB
# from vector_db.embeddings import EmbeddingModel
from vector_db.config import COLUMN_COLLECTION


class ColumnRetriever:

    def __init__(self):
        

        self.client = QdrantDB().get_client()
        # self.embedder = EmbeddingModel()

    def retrieve(
        self,
        query_vector,
        top_k: int = 10,
        query_filter: Filter = None,
    ):
        """
        Retrieve the most relevant columns for a natural language query.

        Returns:
            List[Dict]
        """

        

        results = self.client.query_points(
            collection_name=COLUMN_COLLECTION,
            query=query_vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
            with_vectors=False,
        )

        retrieved_columns = []

        for point in results.points:

            payload = point.payload

            retrieved_columns.append(
                {
                    "score": round(point.score, 4),

                    "table_name": payload.get("table_name"),

                    "module": payload.get("module"),

                    "column_name": payload.get("column_name"),

                    "data_type": payload.get("data_type"),

                    "description": payload.get("description"),

                    "purpose": payload.get("purpose")
                }
            )

        return retrieved_columns


if __name__ == "__main__":

    retriever = ColumnRetriever()
    embedding_model = EmbeddingModel()

    query = "Show total order value by item with the fields item code,  item description and total sales"

    query_vector = embedding_model.embed(query)

    columns = retriever.retrieve(
        query_vector=query_vector,
        top_k=10
    )

    print("\nRelevant Columns\n")

    for i, column in enumerate(columns, start=1):

        print("=" * 80)

        print(f"Rank        : {i}")
        # print(f"Score       : {column['score']}")
        # print(f"Table       : {column['table_name']}")
        print(f"Column      : {column['column_name']}")
        # print(f"Type        : {column['data_type']}")
        # print(f"Description : {column['description']}")