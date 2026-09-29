from typing import List, Dict, TYPE_CHECKING
import json
from click import prompt
from requests import session

from prompts.system_prompt import SYSTEM_PROMPT

if TYPE_CHECKING:
    from api.session_context import SessionContext

class PromptBuilder:
    """
    Builds chat messages for the LLM.
    """

    def __init__(self):
        self.system_prompt = SYSTEM_PROMPT

    def build_messages(
        self,
        user_question: str,
        session: "SessionContext",
        retrieved_schema: List[Dict],
        query_intent: Dict,
        retrieved_examples: List[Dict],
        # current_date_context: str = "",
    ):
        """
        Returns messages in Ollama/OpenAI chat format.
        """

        user_prompt = self._build_user_prompt(
            user_question=user_question,
            session=session,
            retrieved_schema=retrieved_schema,
            query_intent=query_intent,
            retrieved_examples=retrieved_examples,
            # current_date_context=current_date_context,
        )

        return [
            {
                "role": "system",
                "content": self.system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

    ####################################################################
    # USER PROMPT
    ####################################################################

    def _build_user_prompt(
        self,
        user_question: str,
        session: "SessionContext",
        retrieved_schema: List[Dict],
        query_intent: Dict,
        retrieved_examples: List[Dict],
        # current_date_context: str,
    ) -> str:

        prompt = []

        ###############################################################
        # SQL EXAMPLES
        ###############################################################
        prompt.append("\n")
        prompt.append("=" * 70)
        prompt.append("SIMILAR SQL EXAMPLES")
        prompt.append("=" * 70)

        if len(retrieved_examples) == 0:

            prompt.append("No similar SQL examples found.")

        else:

            for idx, example in enumerate(retrieved_examples, start=1):

                prompt.append(f"\nExample {idx}")

                prompt.append(
                    f"Description : {example.get('description')}"
                )

                prompt.append("\nSQL:")

                prompt.append(example.get("sql_query", ""))

                prompt.append("-" * 70)

        

        ###############################################################
        # SCHEMA
        ###############################################################

        prompt.append("=" * 70)
        prompt.append("RETRIEVED DATABASE SCHEMA")
        prompt.append("=" * 70)

        for table in retrieved_schema:
            # prompt.append(f"\nScore: {table.get('score')}")

            prompt.append(f"\nTable Name : {table.get('table_name')}")

            # if table.get("module"):
            #     prompt.append(f"Module : {table.get('module')}")

            if table.get("purpose"):
                prompt.append(f"Purpose : {table.get('purpose')}")

            if table.get("used_for"):
                prompt.append(
                    f"Used For : {', '.join(table.get('used_for'))}"
                )

            if table.get("primary_key"):
                prompt.append(
                    f"Primary Keys : {', '.join(table['primary_key'])}"
                )

            if table.get("foreign_keys"):

                prompt.append("Foreign Keys:")

                for fk in table["foreign_keys"]:

                    if isinstance(fk, dict):
                        prompt.append(
                            f"  - {fk.get('column')} -> {fk.get('references')}"
                        )
                    else:
                        prompt.append(f"  - {fk}")

            prompt.append("\n Available Columns:")

            columns = table.get("columns", [])

            for col in columns:
                name = col.get("name", "")
                # desc = col.get("description", "")
                
                if name:
                    # Append both name and description if available
                    # if desc:
                    #     prompt.append(f" - {name}: {desc}")
                    # else:
                        prompt.append(f" - {name}")


            prompt.append("-" * 70)
            
        prompt.append("""
                ==================================================
                MANDATORY SQL ALIAS RULES
                =================================================
                - Every table MUST have a unique alias, even if only one table is used in the SQL query.
                - Every column reference MUST use its table alias (alias.COLUMN_NAME).
                - Always use aliases in SELECT, WHERE, JOIN, GROUP BY, HAVING, ORDER BY, aggregates, CASE, and subqueries.
                - NEVER use unqualified column names or mix aliased and unaliased references.
                - Before returning SQL, verify that all tables and columns follow these rules.
                #Important Notes: Do NOT copy table aliases from retrieved SQL examples; choose your own clear and unique aliases for every table.
                """)

        prompt.append(""" 
        ==================================================
        MANDATORY JOIN RULES
        =================================================
        - Alaways use COMPANY_CODE in JOIN conditions along with any other columns used for the JOIN.
            left_alias.COMPANY_CODE = right_alias.COMPANY_CODE
        """)
        
        prompt.append("\n")
        prompt.append("=" * 50)
        prompt.append("FILTERS TO USE IN EVERY SQL QUERY")
        prompt.append("=" * 50)
        company_code = (
            session.company_code
            if session and session.company_code
            else "N/A"
        )
        prompt.append("Company Code:")
        prompt.append(company_code)
        prompt.append("""
            ===================================================
            MANDATORY FILTERS
            ==================================================

            The following filters MUST be included:

            IMPORTANT:
            - The values shown below are ACTUAL VALUES.
            - Do NOT replace them with placeholders.
            - Do NOT write {company_code}.
            - Use the exact values provided below.
            - Apply COMPANY_CODE and DELETED_FLAG only to the primary transaction table.

            MANDATORY CONDITIONS:`

            """
        )
        prompt.append(
            f"COMPANY_CODE = '{company_code}'"
        )

        prompt.append(
            "DELETED_FLAG = 'N'"
        )

        
        # print("prompt to check the filter values is ", prompt)

        # ###############################################################
        # # CURRENT DATE CONTEXT
        # ###############################################################

        # prompt.append("\n")
        # prompt.append("=" * 70)
        # prompt.append("CURRENT DATE CONTEXT")
        # prompt.append("=" * 70)

        # if current_date_context.strip():

        #     prompt.append(current_date_context)

        # else:

        #     prompt.append("Not Available")


        date_filter = query_intent.get("date_filter", {})
        if date_filter.get("required", True):

            start_date = date_filter.get("start_date")
            end_date = date_filter.get("end_date")

            prompt.append(f"""
        ==================================================
        MANDATORY DATE FILTER
        ==================================================

        A date filter IS REQUIRED for this query.

        START DATE: {start_date}
        END DATE: {end_date}

        Rules:
        - Use the appropriate date column from the retrieved schema.
        - START DATE is inclusive.
        - END DATE is exclusive.
        - The SQL MUST filter using BOTH boundaries.
        - Do NOT change, modify, or invent the dates.
        - Use the exact dates specified above.
        """)

        else:

            prompt.append("""
        ==================================================
        DATE FILTER
        ==================================================

        A date filter is NOT required for this query.

        IMPORTANT:
        - DO NOT add any date filter to the SQL.
        - DO NOT assume a date range from the user's question.
        - DO NOT add SYSDATE, CURRENT_DATE, TRUNC(date_column),
        or any other implicit date restriction.
        """)


        ###############################################################
        # USER QUESTION
        ###############################################################


        
        
        prompt.append("\n")
        prompt.append("=" * 70)
        prompt.append("USER QUESTION")
        prompt.append("=" * 70)

        prompt.append(user_question)

        prompt.append(
            "\nQUERY REQUIREMENTS(Date context, Row limit and Filters):"
        )

        prompt.append(
            json.dumps(
                query_intent,
                indent=4
            )
        )

        prompt.append("""

        ===========================================================
        OUTPUT — SQL ONLY
        ===========================================================
        
        Just return ONLY the executable Oracle SQL query of strictly oracle 11g version.

        The first character of your response must be S from SELECT.

        Do NOT write any explanation.
        Do NOT write any introduction.
        Do NOT write any conclusion.
        Do NOT use markdown.
        Do NOT use ```sql.
        Do NOT include comments.
        Do NOT include text before the SQL.
        Do NOT include text after the SQL.

        Your entire response must be either:

        SELECT ...

        OR exactly:

        I don't know 

        OR exactly:

        INSUFFICIENT_SCHEMA
            """)

        print("Prompt built successfully")
        # print(prompt)

        return "\n".join(prompt)

        


