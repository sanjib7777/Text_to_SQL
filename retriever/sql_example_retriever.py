from qdrant_client.models import Filter

from vector_db.qdrant_test import QdrantDB

from vector_db.config import SQL_EXAMPLES_COLLECTION


class SQLExampleRetriever:

    def __init__(self):

        self.qdrant = QdrantDB()
        self.client = self.qdrant.get_client()

    def retrieve(
        self,
        query_vector,
        top_k: int = 5,
        query_filter: Filter | None = None,
    ):
        """
        Retrieve top-k most relevant SQL examples.

        Returns:
            List[Dict]
        """

        

        results = self.client.query_points(
            collection_name=SQL_EXAMPLES_COLLECTION,
            query=query_vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
            with_vectors=False,
        )

        examples = []

        for point in results.points:

            examples.append(
                {
                    "score": round(point.score, 4),
                    # "example_id": point.payload.get("example_id"),
                    "description": point.payload.get("description"),
                    "sql_query": point.payload.get("sql_query"),
                }
            )
            
        # print("retrived examples are: ",[ex["sql_query"] for ex in examples])

        return examples


# if __name__ == "__main__":

#     retriever = SQLExampleRetriever()

#     query = "Generate previous month's sales order report"

#     examples = retriever.retrieve(
#         query=query,
#         top_k=5
#     )

#     print("\nRelevant SQL Examples\n")

#     for idx, example in enumerate(examples, start=1):

#         print("=" * 80)

#         print(f"Rank        : {idx}")
#         print(f"Score       : {example['score']}")
#         # print(f"Example ID  : {example['example_id']}")
#         print(f"Description : {example['description']}")

#         print("\nSQL Query:\n")
#         print(example["sql_query"])