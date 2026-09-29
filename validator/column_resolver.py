from vector_db.qdrant_test import QdrantDB


class ColumnResolver:

    def __init__(
        self,
        collection_name="sales_columns"
    ):

        self.qdrant_client = QdrantDB()
        self.collection_name = collection_name

    # =====================================================
    # Find column across all tables
    # =====================================================

    def find_column(
        self,
        column_name,
        limit=1000
    ):

        target_column = column_name.strip().upper()

        points, _ = self.qdrant_client.scroll(
            collection_name=self.collection_name,
            limit=limit,
            with_payload=True
        )

        matches = []

        for point in points:

            payload = point.payload or {}

            # Depending on your embedding payload
            actual_column = payload.get(
                "column_name",
                payload.get("name", "")
            )

            table_name = payload.get(
                "table_name",
                ""
            )

            if not actual_column or not table_name:
                continue

            if actual_column.upper() == target_column:

                matches.append({
                    "table_name": table_name,
                    "column_name": actual_column,
                    "description": payload.get(
                        "description",
                        ""
                    )
                })

        return matches

    # =====================================================
    # Create LLM-readable message
    # =====================================================

    def resolve(
        self,
        column_name
    ):

        matches = self.find_column(
            column_name
        )

        if not matches:

            return (
                f"Column '{column_name}' "
                f"was not found in the schema."
            )

        lines = []

        lines.append(
            f"Column '{column_name}' exists in:"
        )

        for match in matches:

            lines.append(
                f"- Table: {match['table_name']}"
            )

            lines.append(
                f"  Column: {match['column_name']}"
            )

            if match.get("description"):

                lines.append(
                    f"  Description: "
                    f"{match['description']}"
                )

        return "\n".join(lines)