
class ColumnExtractionPrompt:

    @staticmethod
    def build(user_query):

        return f"""
You are an ERP database analyst.

Your task is to identify the database columns required to answer the user's request.

Rules:

1. Return ONLY JSON.

2. Extract:
   - Directly requested fields by the user.

3. Use ERP-style database column names.

Examples:

User:
Show total order value by item with fields item code, item name, total sales

Output:
{{
    "required_columns": [
        "ITEM_CODE",
        "ITEM_EDESC",
        "TOTAL_SALES"
    ]
}}

User:
{user_query}

Output:
"""