import json
from pathlib import Path

from qdrant_client.models import PointStruct

from embeddings import EmbeddingModel
from qdrant_test import QdrantDB
from config import COLUMN_COLLECTION


class ColumnEmbedder:

    def __init__(self):

        self.embedder = EmbeddingModel()

        self.client = QdrantDB().get_client()

    def build_text(self, table):

        texts = []

        payloads = []

        for column in table["columns"]:

            text = f"""
                Table: {table['table_name']}

                Module: {table['module']}

                Purpose:
                {table['purpose']}

                Column:
                {column['name']}

                Data Type:
                {column['type']}

                Description:
                {column['description']}
                """

            payload = {

                "table_name": table["table_name"],
                "module": table["module"],

                "column_name": column["name"],

                "data_type": column["type"],

                "length": column.get("length"),

                "description": column["description"],
                
                "purpose": table["purpose"]
            }

            texts.append(text)

            payloads.append(payload)

        return texts, payloads

    def embed_json(self, json_file):

        with open(json_file, "r", encoding="utf-8") as f:
            tables = json.load(f)

        points = []

        point_id = 1

        for table in tables:

            texts, payloads = self.build_text(table)

            vectors = self.embedder.embed(texts)

            for vector, payload in zip(vectors, payloads):

                points.append(

                    PointStruct(

                        id=point_id,

                        vector=vector,

                        payload=payload

                    )

                )

                point_id += 1

        self.client.upsert(

            collection_name=COLUMN_COLLECTION,

            points=points

        )

        print(f"\nInserted {len(points)} columns successfully.")


if __name__ == "__main__":

    embedder = ColumnEmbedder()

    embedder.embed_json(

        Path("../sales/enriched_updated_sales_tables_schema.json")

    )