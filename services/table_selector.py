class TableSelector:

    @staticmethod
    def select_tables(
        column_table_map,
        retrieved_tables
    ):
        # Extract table names from the retrieved tables dictionary list
        retrieved_table_name = retrieved_tables

        # 1. Start with ALL retrieved tables
        selected_tables = set(retrieved_table_name)

        # 2. Ensure every column in column_table_map is covered
        for column, tables in column_table_map.items():
            # Check if any candidate table for this column is already retrieved/selected
            matching = [
                t for t in tables
                if t in selected_tables
            ]

            if matching:
                # Column is already covered by a selected/retrieved table
                continue
            elif tables:
                # Fallback: Pick the first available candidate table for this column
                selected_tables.add(tables[0])

        return list(selected_tables)


if __name__ == "__main__":
    column_table_map = {
        "CATEGORY_CODE": ["sales_table", "category_table"],
        "CATEGORY_EDESC": ["category_table"],
        "TOTAL_SALES": ["sales_table"]
    }

    retrieved_tables = [
        {"table_name": "sales_table"},
        {"table_name": "customer_table"}
    ]

    selected_tables = TableSelector.select_tables(
        column_table_map,
        retrieved_tables
    )

    print("Selected Tables:", selected_tables)