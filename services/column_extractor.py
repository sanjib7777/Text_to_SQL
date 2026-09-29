# services/column_extraction/column_extractor.py

import json

from prompts.column_extraction_prompt import (
    ColumnExtractionPrompt
)


class ColumnExtractor:

    def __init__(
        self,
        llm_client
    ):
        self.llm = llm_client

    def extract_columns(
        self,
        user_query
    ):

        prompt = ColumnExtractionPrompt.build(
            user_query
        )

        response = self.llm.generate(
            prompt
        )

        try:

            data = json.loads(
                response
            )

            columns = data.get(
                "required_columns",
                []
            )

            columns = [
                col.upper().strip()
                for col in columns
            ]

            return columns

        except Exception as e:

            print(
                "Column extraction failed:",
                e
            )

            return []




# import re


# class ColumnExtractor:

#     @staticmethod
#     def extract_columns(
#         user_query: str
#     ):
#         """
#         Extract columns from a user query.

#         Required columns:
#         CATEGORY_CODE, CATEGORY_EDESC, TOTAL_SALES

#         Returns:
#         ['CATEGORY_CODE', 'CATEGORY_EDESC', 'TOTAL_SALES']
#         """

#         if not user_query:
#             return []

#         pattern = re.search(
#             r"required\s+columns\s*:\s*(.+?)(?:\.|$)",
#             user_query,
#             re.IGNORECASE
#         )

#         if not pattern:
#             return []

#         raw_columns = pattern.group(1)

#         columns = []

#         for col in raw_columns.split(","):

#             col = col.strip().upper()

#             if col:
#                 columns.append(col)

#         return columns

# if __name__ == "__main__":
    
#     extractor = ColumnExtractor()

#     query = "Required columns: CATEGORY_CODE, CATEGORY_EDESC, TOTAL_SALES. Show invoice revenue by category for branch 01.02."

#     extracted_columns = extractor.extract_columns(query)

#     print("Extracted Columns:", extracted_columns)