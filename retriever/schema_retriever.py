from qdrant_client.models import Filter

from vector_db.qdrant_test import QdrantDB
from vector_db.config import SCHEMA_COLLECTION


class SchemaRetriever:

    def __init__(self):
        

        self.qdrant = QdrantDB()
        self.client = self.qdrant.get_client()

        

    def retrieve(
        self,
        query_vector,
        top_k: int = 4,
        query_filter: Filter | None = None,
    ):
        """
        Retrieve top-k relevant schema documents.

        Returns:
            List of dictionaries containing score and payload.
        """

        results = self.client.query_points(
            collection_name=SCHEMA_COLLECTION,
            query=query_vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
            with_vectors=False,
        )

        retrieved_tables = []

        for point in results.points:

            retrieved_tables.append(
                {
                    "score": round(point.score, 4),
                    "table_name": point.payload.get("table_name"),
                    "module": point.payload.get("module"),
                    "purpose": point.payload.get("purpose"),
                    "primary_key": point.payload.get("primary_key"),
                    "foreign_keys": point.payload.get("foreign_keys"),
                    "columns": point.payload.get("columns"),
                    # "document": point.payload.get("document"),
                }
            )
        print("retrived tables are: ",[tbl["table_name"] for tbl in retrieved_tables])

        return retrieved_tables


# if __name__ == "__main__":

#     retriever = SchemaRetriever()

#     query = "Generate previous months sales order report "

#     tables = retriever.retrieve(
#         query=query,
#         top_k=4
#     )

#     print("\nRelevant Tables\n")

#     for idx, table in enumerate(tables, start=1):

#         print("=" * 70)

#         print(f"Rank       : {idx}")
#         print(f"Score      : {table['score']}")
#         print(f"Table Name : {table['table_name']}")
        