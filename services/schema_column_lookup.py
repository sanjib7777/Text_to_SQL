import json

class SchemaColumnLookup:

    def __init__(
        self,
        schema_file="./sales/enriched_updated_sales_tables_schema.json"
    ):
        with open(
            schema_file,
            "r",
            encoding="utf-8"
        ) as f:
            # The schema is a list of table objects
            self.schema = json.load(f)

    def find_tables_for_columns(
        self,
        columns
    ):
        result = {column: [] for column in columns}
        # Normalize target columns to uppercase for case-insensitive matching
        target_columns_map = {col.upper(): col for col in columns}

        # Iterate over each table directly in the top-level list
        for table in self.schema:
            table_name = table.get("table_name")
            
            for col in table.get("columns", []):
                col_name_upper = col.get("name", "").upper()
                
                # Check if this column is in the target list
                if col_name_upper in target_columns_map:
                    original_column_key = target_columns_map[col_name_upper]
                    result[original_column_key].append(table_name)

        return result


if __name__ == "__main__":
    lookup = SchemaColumnLookup()

    columns = [
        "CATEGORY_CODE",
        "CATEGORY_EDESC",
        "CALC_TOTAL_PRICE"
    ]

    column_table_map = lookup.find_tables_for_columns(columns)

    print("Column to Table Mapping:")
    print(json.dumps(column_table_map, indent=4))