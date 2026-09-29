import json

class TableMetadataRetriever:

    def __init__(
        self,
        schema_file="./sales/enriched_updated_sales_tables_schema.json"
    ):
        with open(
            schema_file,
            "r",
            encoding="utf-8"
        ) as f:

            self.schema = json.load(f)

        self.table_map = {
            table["table_name"].upper(): table
            for table in self.schema
        }

    def get_tables(
        self,
        selected_tables
    ):

        result = []

        for table_name in selected_tables:

            table = self.table_map.get(
                table_name.upper()
            )

            if table:

                result.append({
                    "table_name": table["table_name"],
                    "purpose": table.get("purpose"),
                    "used_for": table.get("used_for", []),
                    "primary_key": table.get("primary_key", []),
                    "foreign_keys": table.get("foreign_keys", []),
                    "columns": table.get("columns", [])
                })

        return result