import re

from click import prompt


class SQLCorrectionPrompt:

    @staticmethod
    def build(
        user_question,
        generated_sql,
        validation_error,
        retrieved_schema,
        column_resolution=None
    ):

        print(
            "validation error is ...................."
        )
        print(validation_error)

        print(
            "resolve it.........",
            column_resolution
        )

        prompt = []

        
        # ==================================================
        # RETRIEVED SCHEMA
        # ==================================================

        prompt.append("\nRETRIEVED SCHEMA:")

        for table in retrieved_schema:

            table_name = table.get("table_name")

            prompt.append(
                f"\nTABLE: {table_name}"
            )

            prompt.append("VALID COLUMNS:")

            for column in table.get("columns", []):

                name = column.get("name")

                if name:

                    prompt.append(
                        f" - {name}"
                    )
        
                # ==================================================
                # COLUMN RESOLUTION
                # ==================================================
        
        resolved_table = None
        resolved_column = None
        
        if column_resolution:
        
                    # ----------------------------------------------
                    # Extract table and column from resolver result
                    # ----------------------------------------------
        
            table_match = re.search(
                r"Table:\s*([A-Za-z0-9_$#]+)",
                column_resolution,
                re.IGNORECASE
            )
        
            column_match = re.search(
                r"Column:\s*([A-Za-z0-9_$#]+)",
                column_resolution,
                re.IGNORECASE
            )
        
            if table_match:
                resolved_table = table_match.group(1)
        
            if column_match:
                resolved_column = column_match.group(1)
        
                    # ----------------------------------------------
                    # Add resolution information
                    # ----------------------------------------------
        
        if validation_error and (
            "the generated sql does not use the required"
            in validation_error.lower()
        ):

            prompt.append(
                """
        ======================================================
        MANDATORY DATE FILTER CORRECTION
        ======================================================

        The database stores dates in AD/Gregorian format.

        - Use the appropriate date column from the retrieved schema.
        - Filter the date column using BOTH START_DATE and END_DATE.
        - Use TRUNC() with TO_DATE() for date filtering.
        - Replace START_DATE and END_DATE with the actual required dates.
        - Do NOT use any other date range.
        - The generated SQL MUST contain both date boundaries.

        The required pattern is:

        TRUNC(alias.DATE_COLUMN) >= TO_DATE('START_DATE', 'YYYY-MM-DD')
        AND TRUNC(alias.DATE_COLUMN) < TO_DATE('END_DATE', 'YYYY-MM-DD')

        Use the actual date column from the retrieved schema and
        the appropriate table alias.
        """
            )

        prompt.append("""
        ======================================================
        COLUMN RESOLUTION RESULT
        ======================================================

                """)
        
        prompt.append(
            f"\n{column_resolution}"
        )
        
                    # ----------------------------------------------
                    # Explicit JOIN instruction
                    # ----------------------------------------------
        
        if resolved_table and resolved_column:
        
            prompt.append(f"""
            ======================================================
            MANDATORY TABLE ADDITION
            ======================================================
            
            The required column:
            
            {resolved_column}
            
            exists in:
            
            {resolved_table}
            
            Therefore:
            
            - You MUST include {resolved_table} in the SQL query using suitable join.
            - You MUST assign an alias to {resolved_table}.
            - You MUST reference {resolved_column} using the alias
            of {resolved_table}.
            - Use only a valid join relationship available in the
            provided schema or join information.
            """)
        
                # ==================================================
                # PRIORITY
                # ==================================================
    

        prompt.append("""

       
        #JOIN CORRECTION (if necessary)#

        When a required column is found in another table, do not
        simply change the column reference. Add the table containing
        that column to the query and connect/join it to the existing
        tables using a valid relationship (foreign key).

        Do not invent a column or JOIN key. If a valid relationship
        cannot be established from the available schema, return
        INSUFFICIENT_SCHEMA.

        ======================================================
        PRIORITY OF INSTRUCTIONS
        ======================================================
        
        1. Resolve the exact VALIDATION ERROR first.
        
        2. Do not repeat the same invalid column/table
           combination.
        
        3. Preserve the original user's requested intent and meaning of the SQL query.
       
        
        ======================================================
        OUTPUT FORMAT
        ======================================================
        
        Return ONLY the corrected Oracle SQL query.
        
        Do NOT explain anything.
        Do NOT use markdown.
        Do NOT use ```sql.
        Do NOT include comments.
        
        The first word must be SELECT.
        """)

        # ==================================================
        # USER QUESTION
        # ==================================================

        prompt.append("\nUSER QUESTION:")
        prompt.append(user_question)

        # ==================================================
        # PREVIOUS SQL
        # ==================================================

        prompt.append("\nPREVIOUS GENERATED SQL:")
        prompt.append(generated_sql)

        prompt.append("""
        
        ======================================================
         VALIDATION ERROR AND SOLUTION (High Priority)
        ======================================================
        
        Analyze the validation error along with the previous generated sql query properly and find where the error occurs 
        and try to solve it. Validation error is the most important thing to consider while correcting the SQL query which 
        given below:
        """)
        
        prompt.append(
            f"\nVALIDATION ERROR:\n{validation_error}"
        )

        alias_match = re.search(
            r"Alias ['\"]([^'\"]+)['\"] is not declared",
            validation_error,
            re.IGNORECASE
        )

        if alias_match:

            invalid_alias = alias_match.group(1)

            prompt.append(
                f"""
        ======================================================
        INVALID ALIAS
        ======================================================

        The alias '{invalid_alias}' is NOT declared in the SQL.

        You MUST correct every reference using '{invalid_alias}'.

        Do NOT use '{invalid_alias}' unless you explicitly declare
        it for a table in FROM or JOIN.

        Find the table that contains the referenced column and use
        that table's declared alias.

        After correction, verify that '{invalid_alias}' is either:
        - properly declared, or
        - completely removed/replaced.

        The final SQL MUST contain no undeclared aliases.
        """
            )

        # print("final.....................................prompt: \n", prompt)

        return "\n".join(prompt)