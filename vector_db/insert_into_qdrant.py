from pathlib import Path
import uuid
import json
from qdrant_client.models import PointStruct

from qdrant_test import QdrantDB
from embeddings import EmbeddingModel
from config import SCHEMA_COLLECTION


SCHEMA_FOLDER = "../sales/txt_sales_tables"
SCHEMA_JSON = "../sales/enriched_updated_sales_tables_schema.json"



def load_schema_metadata():
    """Load enriched schema metadata from JSON."""
    with open(SCHEMA_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    metadata = {}

    for table in data:
        metadata[table["table_name"]] = table

    return metadata

def main():
    # Load metadata
    schema_metadata = load_schema_metadata()

    # Initialize
    qdrant = QdrantDB()
    client = qdrant.get_client()

    embedding_model = EmbeddingModel()

    files = list(Path(SCHEMA_FOLDER).glob("*.txt"))

    print(f"Found {len(files)} schema files.\n")

    points = []

    for file in files:
        table_name = file.stem

        print(f"Embedding {file.name}")
        if table_name not in schema_metadata:
            print(f"Skipping {table_name}. Metadata not found.")
            continue

        document = file.read_text(
            encoding="utf-8"
        )

        vector = embedding_model.embed(document)
        table = schema_metadata[table_name]

        payload = {

            "table_name": table["table_name"],
            "module": table["module"],
            "purpose": table["purpose"],
            "primary_key": table["primary_key"],
            "foreign_keys": table["foreign_keys"],
            "columns": table["columns"],
            "document": document
        }

        points.append(

            PointStruct(

                id=str(uuid.uuid4()),

                vector=vector,

                payload=payload
            )

        )

    client.upsert(

        collection_name=SCHEMA_COLLECTION,

        wait=True,

        points=points
    )

    print(f"\nInserted {len(points)} tables into Qdrant.")


if __name__ == "__main__":
    main()