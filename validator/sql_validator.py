import re
from datetime import datetime
from pathlib import Path


class SQLValidator:

    def __init__(self):

        # --------------------------------------------------
        # Forbidden SQL operations
        # --------------------------------------------------

        self.forbidden_keywords = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "TRUNCATE",
            "MERGE",
            "CREATE",
            "GRANT",
            "REVOKE",
            "COMMIT",
            "ROLLBACK"
        ]

        # --------------------------------------------------
        # SQL keywords
        # These are NOT column names
        # --------------------------------------------------

        self.sql_keywords = {
            "SELECT",
            "FROM",
            "WHERE",
            "AND",
            "OR",
            "NOT",
            "NULL",
            "IS",
            "IN",
            "LIKE",
            "BETWEEN",
            "GROUP",
            "BY",
            "ORDER",
            "ASC",
            "DESC",
            "HAVING",
            "AS",
            "ON",
            "JOIN",
            "LEFT",
            "RIGHT",
            "FULL",
            "INNER",
            "OUTER",
            "CROSS",
            "DISTINCT",
            "CASE",
            "WHEN",
            "THEN",
            "ELSE",
            "END",
            "UNION",
            "ALL",
            "INTERSECT",
            "MINUS",
            "EXISTS",
            "OVER",
            "PARTITION",
            "ROWS",
            "RANGE",
            "CURRENT",
            "ROW",
            "WITH",
            "FETCH",
            "OFFSET",
            "ROWNUM",
            "NULLS",
            "FIRST",
            "LAST",
            "FOR",
            "UPDATE",
        }

        # --------------------------------------------------
        # Keywords used as fixed arguments inside specific
        # Oracle functions — not column names.
        #
        # EXTRACT(YEAR FROM date_col), EXTRACT(MONTH FROM ...)
        # TRIM(LEADING 'x' FROM col), TRIM(TRAILING ... )
        # --------------------------------------------------

        self.sql_keywords |= {
            "YEAR",
            "MONTH",
            "DAY",
            "HOUR",
            "MINUTE",
            "SECOND",
            "TIMEZONE_HOUR",
            "TIMEZONE_MINUTE",
            "TIMEZONE_REGION",
            "TIMEZONE_ABBR",
            "LEADING",
            "TRAILING",
            "BOTH",
        }

        # --------------------------------------------------
        # Oracle / SQL functions
        # --------------------------------------------------

        self.sql_functions = {
            "SUM",
            "COUNT",
            "AVG",
            "MIN",
            "MAX",
            "LAG",
            "NVL",
            "NVL2",
            "DECODE",
            "LOWER",
            "UPPER",
            "INITCAP",
            "TRIM",
            "LTRIM",
            "RTRIM",
            "SUBSTR",
            "LENGTH",
            "INSTR",
            "REPLACE",
            "ROUND",
            "CEIL",
            "FLOOR",
            "ABS",
            "MOD",
            "TRUNC",
            "TO_DATE",
            "TO_CHAR",
            "TO_NUMBER",
            "ADD_MONTHS",
            "MONTHS_BETWEEN",
            "LAST_DAY",
            "SYSDATE",
            "SYSTIMESTAMP",
            "COALESCE",
            "NULLIF",
            "CAST",
            "EXTRACT",
            "REGEXP_LIKE",
            "REGEXP_SUBSTR",
            "REGEXP_REPLACE",
        }

        self.allowed_tables = self._load_allowed_tables()

    def _load_allowed_tables(self):
        table_file = Path(__file__).resolve().parents[1] / "sales" / "tables.txt"

        if not table_file.exists():
            return set()

        content = table_file.read_text(encoding="utf-8")
        return {
            item.strip().upper()
            for item in content.split(",")
            if item.strip()
        }

    # ==========================================================
# VALIDATE REQUESTED DATE RANGE
# ==========================================================

    def validate_date_range(
        self,
        sql,
        expected_start_date=None,
        expected_end_date=None
    ):
        """
        Verify that SQL uses the AD date range supplied by
        CurrentDateContext.

        expected_start_date:
            e.g. 2025-07-17

        expected_end_date:
            e.g. 2026-07-17
        """
        print("expected start date:", expected_start_date)
        print("expected end date:", expected_end_date)


        # ======================================================
        # CASE 1: NO DATE FILTER REQUIRED
        # ======================================================

        if not expected_start_date and not expected_end_date:

            date_values = self._extract_sql_dates(sql)

            if date_values:

                return False, (
                    "DATE FILTER NOT REQUIRED.\n\n"

                    "The user query does not require a date filter, "
                    "but the generated SQL contains a date filter.\n\n"

                    f"Dates found in generated SQL:\n"
                    f"{', '.join(date_values)}\n\n"

                    "Remove the date-based filtering condition from "
                    "the SQL query. Do not introduce or assume any "
                    "date range when no date filter is required."
                )

            return True, (
                "No date filter is required and no explicit "
                "date values were found in the SQL."
            )

        # ======================================================
        # CASE 2: INCOMPLETE EXPECTED DATE RANGE
        # ======================================================

        if not expected_start_date or not expected_end_date:

            return False, (
                "Invalid date-filter configuration. "
                "Both expected START_DATE and END_DATE "
                "must be provided when date filtering is required."
            )
       

        # ------------------------------------------------------
        # Convert expected dates to strings
        # ------------------------------------------------------

        expected_start = self._normalize_date(
            expected_start_date
        )

        expected_end = self._normalize_date(
            expected_end_date
        )

        if not expected_start or not expected_end:
            return True, "Expected date range could not be parsed."

        # ------------------------------------------------------
        # Remove SQL string literals that are NOT date values
        # carefully enough to avoid matching unrelated text.
        #
        # We specifically search for Oracle date patterns below.
        # ------------------------------------------------------

        date_values = self._extract_sql_dates(sql)

        # ------------------------------------------------------
        # If SQL contains no explicit dates, don't fail here.
        #
        # Example:
        # SALES_DATE >= SYSDATE - 30
        #
        # Such dynamic date expressions need different handling.
        # ------------------------------------------------------

        if not date_values:
            return True, "No explicit SQL date literals found."

        # ------------------------------------------------------
        # Normalize generated dates
        # ------------------------------------------------------

        generated_dates = set()

        for value in date_values:

            normalized = self._normalize_date(value)

            if normalized:
                generated_dates.add(normalized)

        # ------------------------------------------------------
        # Check required START date
        # ------------------------------------------------------

        if expected_start not in generated_dates:

            return False, (
                "SQL date range mismatch.\n\n"

                f"Expected START_DATE:\n"
                f"{expected_start}\n\n"

                f"Expected END_DATE:\n"
                f"{expected_end}\n\n"

                f"Dates found in generated SQL:\n"
                f"{', '.join(sorted(generated_dates))}\n\n"

                "The generated SQL does not use the required "
                "AD start date. Replace the generated date "
                "with the expected START_DATE."
            )

        # ------------------------------------------------------
        # Check required END date
        # ------------------------------------------------------

        if expected_end not in generated_dates:

            return False, (
                "SQL date range mismatch.\n\n"

                f"Expected START_DATE:\n"
                f"{expected_start}\n\n"

                f"Expected END_DATE:\n"
                f"{expected_end}\n\n"

                f"Dates found in generated SQL:\n"
                f"{', '.join(sorted(generated_dates))}\n\n"

                "The generated SQL does not use the required "
                "AD end date. Replace the generated date "
                "with the expected END_DATE."
            )

        return True, "SQL date range matches the requested date range."




    def validate_session_filters(
        self,
        sql: str,
        retrieved_schema: list,
        session
    ):
        """
        Ensures COMPANY_CODE filters
        are present whenever those columns exist in the
        tables used by the SQL.
        """

        sql_upper = sql.upper()

        company_code = self._normalize_session_value(
            getattr(session, "company_code", None)
        )
        # ---------------------------------------------
        # Find tables used in SQL
        # ---------------------------------------------

        table_pattern = re.compile(
            r"\b(?:FROM|JOIN)\s+([A-Z0-9_]+)(?:\s+([A-Z][A-Z0-9_]*))?",
            re.IGNORECASE
        )

        tables = []

        for match in table_pattern.finditer(sql):

            table_name = match.group(1).upper()

            alias = (
                match.group(2)
                if match.group(2)
                else None
            )

            tables.append(
                (table_name, alias)
            )

        # ---------------------------------------------
        # Validate filters
        # ---------------------------------------------

        errors = []

        for table_name, alias in tables:

            schema = next(
                (
                    t
                    for t in retrieved_schema
                    if t["table_name"].upper() == table_name
                ),
                None
            )

            if not schema:
                continue

            columns = {
                c["name"].upper()
                for c in schema["columns"]
            }

            alias_prefix = f"{alias}." if alias else ""

            # -------------------------------
            # COMPANY_CODE
            # -------------------------------

            if (
                "COMPANY_CODE" in columns
                and company_code
            ):

                patterns = [
                    re.compile(
                        rf"{re.escape(alias_prefix)}COMPANY_CODE\s*=\s*['\"]?{re.escape(company_code)}['\"]?",
                        re.IGNORECASE
                    ),
                    re.compile(
                        rf"\bCOMPANY_CODE\s*=\s*['\"]?{re.escape(company_code)}['\"]?",
                        re.IGNORECASE
                    ),
                ]

                if not any(pattern.search(sql) for pattern in patterns):

                    errors.append(
                        f"""
    Missing mandatory session filter.

    Table:
    {table_name}

    Expected:

    {alias_prefix}COMPANY_CODE = '{company_code}'
    """
                    )

        if errors:

            return False, "\n\n".join(errors)

        return True, None

    def _normalize_session_value(self, value):

        if value is None:
            return None

        return str(value).strip().strip("`").strip("'\"")

    # ==========================================================
    # EXTRACT DATE VALUES FROM SQL
    # ==========================================================

    def _extract_sql_dates(self, sql):

        dates = []

        # ------------------------------------------------------
        # Oracle ANSI DATE syntax
        #
        # DATE '2025-07-17'
        # ------------------------------------------------------

        ansi_date_pattern = re.compile(
            r"\bDATE\s*"
            r"'\s*(\d{4}-\d{2}-\d{2})\s*'",
            re.IGNORECASE
        )

        dates.extend(
            ansi_date_pattern.findall(sql)
        )

        # ------------------------------------------------------
        # TO_DATE syntax
        #
        # TO_DATE('2025-07-17', 'YYYY-MM-DD')
        # ------------------------------------------------------

        to_date_pattern = re.compile(
            r"\bTO_DATE\s*"
            r"\(\s*"
            r"'(\d{4}-\d{2}-\d{2})'"
            r"\s*,",
            re.IGNORECASE
        )

        dates.extend(
            to_date_pattern.findall(sql)
        )

        return dates


    # ==========================================================
    # NORMALIZE DATE
    # ==========================================================

    def _normalize_date(self, value):

        if value is None:
            return None

        # datetime/date object
        if hasattr(value, "strftime"):

            return value.strftime(
                "%Y-%m-%d"
            )

        value = str(value).strip()

        # Extract YYYY-MM-DD if embedded
        match = re.search(
            r"\d{4}-\d{2}-\d{2}",
            value
        )

        if match:
            return match.group(0)

        return None

    # ==========================================================
    # MAIN VALIDATION FUNCTION
    # ==========================================================

    def validate(self, sql, retrieved_schema, expected_start_date=None,expected_end_date=None, session=None):

        if not sql:

            return False, "SQL query is empty."

        sql = sql.strip()

        # ------------------------------------------------------
        # Remove trailing semicolon
        # ------------------------------------------------------

        if sql.endswith(";"):
            sql = sql[:-1].strip()

        # ------------------------------------------------------
        # Remove markdown if accidentally returned by LLM
        # ------------------------------------------------------

        sql = self.clean_sql(sql)

        # ------------------------------------------------------
        # 1. Check forbidden operations
        # ------------------------------------------------------

        forbidden_error = self.check_forbidden_keywords(sql)

        if forbidden_error:

            return False, forbidden_error

        # ------------------------------------------------------
        # 2. Only SELECT allowed
        # ------------------------------------------------------

        if not re.match(r"^\s*SELECT\b", sql, re.IGNORECASE):

            return False, (
                "Only SELECT queries are allowed."
            )

        # ------------------------------------------------------
        # 2b. Reject Oracle-11g-incompatible pagination syntax
        #
        # LIMIT / OFFSET..FETCH / FETCH FIRST..ROWS ONLY are not
        # valid Oracle 11g syntax (FETCH FIRST is 12c+, LIMIT is
        # not Oracle at all). Catching this explicitly, with a
        # precise correction, avoids the misleading "column does
        # not exist" error these previously fell through to.
        # ------------------------------------------------------

        pagination_error = self.check_oracle11g_pagination(sql)

        if pagination_error:

            return False, pagination_error

        # ------------------------------------------------------
        # 3. Build schema map from ALL retrieved tables.
        #
        # This represents every table the RAG pipeline retrieved
        # as context. Table names in the SQL are NOT required to
        # exist here (they may legitimately come from a few-shot
        # SQL example instead). This map is used only to look up
        # columns for whichever tables in the SQL DO happen to
        # have known schema.
        # ------------------------------------------------------

        schema_map = self.build_schema_map(
            retrieved_schema
        )

        if not schema_map:

            return False, (
                "No valid retrieved schema was provided."
            )

        # ------------------------------------------------------
        # 4. Extract tables and aliases actually used in SQL
        # ------------------------------------------------------

        table_aliases = self.extract_table_aliases(sql)

        if not table_aliases:

            return False, (
                "No valid table was found in the SQL query."
            )

        # ------------------------------------------------------
        # 5. Validate that every table referenced in the SQL
        # is in the approved sales table allowlist.
        # ------------------------------------------------------

        is_valid, message = self.validate_company_code_joins(
            sql=sql,
            retrieved_schema=retrieved_schema,
            table_aliases=table_aliases
        )

        if not is_valid:
            return False, message

        valid, message = self.validate_referenced_tables(
            table_aliases=table_aliases,
            schema_map=schema_map
        )

        if not valid:
            return False, message

        # ------------------------------------------------------
        # 6/8. Validate qualified (alias.column) AND unqualified
        # columns, SCOPE-AWARE.
        #
        # Example:
        #
        # o.ORDER_NO          <- qualified
        # ITEM_CODE           <- unqualified
        #
        # IMPORTANT: this is scope-aware. A subquery's own
        # FROM/JOIN tables are only visible inside that subquery
        # (plus any of ITS OWN nested subqueries and, for
        # correlated references, its ancestor queries) — never to
        # sibling subqueries elsewhere in the SQL. Without this,
        # a query like:
        #
        #   SELECT i.ITEM_CODE, r.TOTAL_RETURN_QTY,
        #          inv.TOTAL_INVOICED_QTY
        #   FROM (SELECT ITEM_CODE, SUM(QUANTITY) ...
        #         FROM SA_SALES_RETURN GROUP BY ITEM_CODE) r
        #   JOIN (SELECT ITEM_CODE, SUM(QUANTITY) ...
        #         FROM SA_SALES_INVOICE GROUP BY ITEM_CODE) inv
        #     ON r.ITEM_CODE = inv.ITEM_CODE
        #   JOIN IP_ITEM_MASTER_SETUP i ON r.ITEM_CODE = i.ITEM_CODE
        #
        # would incorrectly flag the unqualified ITEM_CODE inside
        # each derived table's own SELECT/GROUP BY as "ambiguous"
        # between SA_SALES_RETURN, SA_SALES_INVOICE and
        # IP_ITEM_MASTER_SETUP — even though each occurrence sits
        # inside its own self-contained subquery with only ONE
        # source table in scope there.
        # ------------------------------------------------------

        valid, message = self.validate_columns_scoped(
            sql=sql,
            schema_map=schema_map
        )

        if not valid:

            return False, message

        # ------------------------------------------------------
        # 9. Validate aliases in SELECT
        # ------------------------------------------------------

        valid, message = self.validate_select_aliases(
            sql
        )

        if not valid:

            return False, message

        # ------------------------------------------------------
        # DATE RANGE VALIDATION
        # ------------------------------------------------------

        date_valid, date_message = self.validate_date_range(
            sql=sql,
            expected_start_date=expected_start_date,
            expected_end_date=expected_end_date
        )

        valid, error = self.validate_session_filters(
            sql,
            retrieved_schema,
            session
        )

        if not valid:
            return False, error

        if not date_valid:

            return False, date_message

        # ------------------------------------------------------
        # Everything passed
        # ------------------------------------------------------

        return True, "SQL is valid."


    # ==========================================================
    # ORACLE 11g PAGINATION SYNTAX CHECK
    #
    # Detects pagination syntax that is invalid in Oracle 11g
    # and returns a precise, actionable correction message
    # instead of letting it fall through to the generic
    # column-existence check (which produces a misleading
    # "column does not exist" error for keywords like LIMIT,
    # ONLY, OFFSET).
    # ==========================================================

    def check_oracle11g_pagination(self, sql):

        sql_without_strings = self.remove_string_literals(sql)

        # --------------------------------------------------
        # LIMIT n   (not valid Oracle syntax at all)
        # --------------------------------------------------

        if re.search(
            r"\bLIMIT\s+\d+\b",
            sql_without_strings,
            re.IGNORECASE
        ):

            return (
                "LIMIT is not valid Oracle 11g syntax. "
                "Use ROWNUM instead, e.g.: "
                "SELECT * FROM (<original query with ORDER BY>) "
                "WHERE ROWNUM <= N"
            )

        # --------------------------------------------------
        # FETCH FIRST n ROWS ONLY   (Oracle 12c+, not 11g)
        # OFFSET n ROWS FETCH NEXT m ROWS ONLY   (Oracle 12c+)
        # --------------------------------------------------

        if re.search(
            r"\bFETCH\s+(?:FIRST|NEXT)\s+\d+\s+ROWS?\s+ONLY\b",
            sql_without_strings,
            re.IGNORECASE
        ):

            return (
                "FETCH FIRST/NEXT ... ROWS ONLY is Oracle 12c+ "
                "syntax and is not valid in Oracle 11g. "
                "Use ROWNUM instead, e.g.: "
                "SELECT * FROM (<original query with ORDER BY>) "
                "WHERE ROWNUM <= N"
            )

        # --------------------------------------------------
        # OFFSET n ROWS   (Oracle 12c+, not 11g)
        # --------------------------------------------------

        if re.search(
            r"\bOFFSET\s+\d+\s+ROWS\b",
            sql_without_strings,
            re.IGNORECASE
        ):

            return (
                "OFFSET ... ROWS is Oracle 12c+ syntax and is "
                "not valid in Oracle 11g. Use ROWNUM-based "
                "pagination instead."
            )

        return None


    # ==========================================================
    # ROW-LIMITING INTENT PRESERVATION CHECK
    #
    # Catches a specific LLM failure mode during correction: the
    # original (invalid) SQL had pagination syntax (LIMIT, FETCH
    # FIRST/NEXT ... ROWS ONLY, OFFSET ... ROWS), and instead of
    # translating it to the Oracle 11g ROWNUM equivalent, the
    # correction simply deleted it — passing syntax validation
    # while silently changing "return N rows" into "return all
    # rows". This is a semantic regression, not a syntax error,
    # so the normal validate() checks cannot catch it on their
    # own; call this separately, comparing the SQL BEFORE and
    # AFTER a correction round-trip.
    #
    # Returns an error string if the limit was dropped, or None
    # if either there was no limit to preserve, or it was
    # correctly preserved via ROWNUM.
    # ==========================================================

    def validate_company_code_joins(
        self,
        sql,
        retrieved_schema,
        table_aliases
    ):

        # --------------------------------------------------
        # Build:
        # TABLE_NAME -> set(columns)
        # --------------------------------------------------

        schema_columns = {}

        for table in retrieved_schema:

            table_name = table.get("table_name", "").upper()

            columns = {
                col.get("name", "").upper()
                for col in table.get("columns", [])
                if col.get("name")
            }

            schema_columns[table_name] = columns

        # --------------------------------------------------
        # Find JOIN ... ON sections
        # --------------------------------------------------

        join_pattern = re.compile(
            r"""
            \bJOIN\s+
            ([A-Za-z_][A-Za-z0-9_$#]*)
            (?:\s+(?:AS\s+)?
            ([A-Za-z_][A-Za-z0-9_$#]*))?
            \s+
            ON\s+
            (.*?)
            (?=
                \b(?:(?:LEFT|RIGHT|INNER|FULL|CROSS)\s+)?JOIN\b
                |\bWHERE\b
                |\bGROUP\s+BY\b
                |\bORDER\s+BY\b
                |\bHAVING\b
                |\bUNION\b
                |$
            )
            """,
            re.IGNORECASE | re.DOTALL | re.VERBOSE
        )

        matches = join_pattern.findall(sql)

        for table_name, alias, on_condition in matches:

            table_name = table_name.upper()

            if alias:
                alias = alias.upper()
            else:
                alias = table_name

            # --------------------------------------------------
            # Find the table on the left side of the JOIN
            # --------------------------------------------------

            # Find aliases referenced in ON condition.
            alias_pattern = re.compile(
                r"\b([A-Za-z_][A-Za-z0-9_$#]*)\."
                r"[A-Za-z_][A-Za-z0-9_$#]*\b",
                re.IGNORECASE
            )

            aliases_in_condition = {
                a.upper()
                for a in alias_pattern.findall(on_condition)
            }

            # --------------------------------------------------
            # Check joined table
            # --------------------------------------------------

            joined_columns = schema_columns.get(
                table_name,
                set()
            )

            if "COMPANY_CODE" not in joined_columns:
                continue

            # --------------------------------------------------
            # Find left-side tables
            # --------------------------------------------------

            for left_alias in aliases_in_condition:

                if left_alias == alias:
                    continue

                left_table = table_aliases.get(
                    left_alias
                )

                if not left_table:
                    continue

                left_columns = schema_columns.get(
                    left_table,
                    set()
                )

                if "COMPANY_CODE" not in left_columns:
                    continue

                # --------------------------------------------------
                # Both tables have COMPANY_CODE.
                # Verify JOIN contains it.
                # --------------------------------------------------

                company_join_pattern = re.compile(
                    rf"""
                    \b{re.escape(left_alias)}
                    \s*\.\s*COMPANY_CODE
                    \s*=\s*
                    \b{re.escape(alias)}
                    \s*\.\s*COMPANY_CODE
                    |
                    \b{re.escape(alias)}
                    \s*\.\s*COMPANY_CODE
                    \s*=\s*
                    \b{re.escape(left_alias)}
                    \s*\.\s*COMPANY_CODE
                    """,
                    re.IGNORECASE | re.VERBOSE
                )

                if not company_join_pattern.search(
                    on_condition
                ):

                    return False, (
                        "COMPANY_CODE JOIN validation failed.\n\n"
                        f"Both '{left_table}' and "
                        f"'{table_name}' contain COMPANY_CODE.\n\n"
                        f"The JOIN between aliases "
                        f"'{left_alias}' and '{alias}' "
                        "must include:\n\n"
                        f"{left_alias}.COMPANY_CODE = "
                        f"{alias}.COMPANY_CODE\n\n"
                        "Do not remove the existing JOIN condition; "
                        "add COMPANY_CODE to the JOIN condition."
                    )

        return True, "COMPANY_CODE JOIN conditions are valid."

    def check_row_limit_preserved(self, original_sql, corrected_sql):

        original_without_strings = self.remove_string_literals(
            original_sql
        )

        had_pagination = bool(
            re.search(
                r"\bLIMIT\s+\d+\b"
                r"|\bFETCH\s+(?:FIRST|NEXT)\s+\d+\s+ROWS?\s+ONLY\b"
                r"|\bOFFSET\s+\d+\s+ROWS\b",
                original_without_strings,
                re.IGNORECASE
            )
        )

        if not had_pagination:

            return None

        corrected_without_strings = self.remove_string_literals(
            corrected_sql
        )

        has_valid_rownum_wrapper = bool(
            re.search(
                r"^\s*SELECT\s+\*\s+FROM\s*\(.*\)\s*WHERE\s+ROWNUM\s*<=\s*\d+\s*$",
                corrected_without_strings,
                re.IGNORECASE | re.DOTALL,
            )
        )

        has_any_rownum = bool(
            re.search(
                r"\bROWNUM\b",
                corrected_without_strings,
                re.IGNORECASE
            )
        )

        if not has_valid_rownum_wrapper:
            if has_any_rownum:
                return (
                    "The corrected query uses ROWNUM, but it is not "
                    "wrapped in the required Oracle pattern: "
                    "SELECT * FROM (<query>) WHERE ROWNUM <= N."
                )

            return (
                "The original query limited results using "
                "LIMIT/FETCH/OFFSET syntax, but the corrected "
                "query no longer limits the number of rows at "
                "all. Deleting the row-limiting clause is not a "
                "valid fix — it changes 'return N rows' into "
                "'return all rows'. Re-wrap the query using the "
                "ROWNUM pattern to preserve the original row "
                "limit, e.g.: SELECT * FROM (<query with ORDER "
                "BY>) WHERE ROWNUM <= N"
            )

        return None


    # ==========================================================
    # CLEAN SQL
    # ==========================================================

    def clean_sql(self, sql):

        sql = sql.strip()

        # Remove ```sql
        sql = re.sub(
            r"^```sql\s*",
            "",
            sql,
            flags=re.IGNORECASE
        )

        # Remove ```
        sql = re.sub(
            r"^```\s*",
            "",
            sql
        )

        sql = re.sub(
            r"\s*```$",
            "",
            sql
        )

        sql = sql.strip()

        if sql.endswith(";"):
            sql = sql[:-1].strip()

        return sql


    # ==========================================================
    # FORBIDDEN KEYWORDS
    # ==========================================================

    def check_forbidden_keywords(self, sql):

        # Remove strings first so that words inside
        # strings do not cause false positives.
        sql_without_strings = self.remove_string_literals(sql)

        for keyword in self.forbidden_keywords:

            pattern = rf"\b{re.escape(keyword)}\b"

            if re.search(
                pattern,
                sql_without_strings,
                re.IGNORECASE
            ):

                return (
                    f"Forbidden SQL operation detected: "
                    f"{keyword}"
                )

        return None


    # ==========================================================
    # BUILD TABLE -> COLUMN MAP (ALL RETRIEVED TABLES)
    # ==========================================================

    def build_schema_map(self, retrieved_schema):

        schema_map = {}

        for table in retrieved_schema:

            table_name = table.get(
                "table_name",
                ""
            ).strip().upper()

            if not table_name:
                continue

            columns = set()

            for column in table.get("columns", []):

                if isinstance(column, dict):

                    column_name = column.get(
                        "name",
                        ""
                    )

                else:

                    column_name = str(column)

                if column_name:

                    columns.add(
                        column_name.strip().upper()
                    )

            schema_map[table_name] = columns

        return schema_map


    # ==========================================================
    # BUILD TABLE -> COLUMN MAP (ONLY TABLES USED IN THIS SQL)
    # ==========================================================

    def build_used_schema_map(self, table_aliases, schema_map):

        used_tables = set(table_aliases.values())

        used_schema_map = {}

        for table_name in used_tables:

            if table_name in schema_map:

                used_schema_map[table_name] = schema_map[
                    table_name
                ]
                continue

            fallback_columns = self._load_table_columns_from_local_schema(
                table_name
            )

            if fallback_columns:
                used_schema_map[table_name] = fallback_columns

        return used_schema_map

    def _load_table_columns_from_local_schema(self, table_name):

        table_file = (
            Path(__file__).resolve().parents[1]
            / "sales"
            / "txt_sales_tables"
            / f"{table_name}.txt"
        )

        if not table_file.exists():
            return None

        content = table_file.read_text(encoding="utf-8")
        lines = [line.rstrip() for line in content.splitlines()]

        columns_section = False
        columns = set()

        for line in lines:

            stripped = line.strip()

            if not stripped:
                continue

            if not columns_section:

                if stripped.upper() == "COLUMNS":
                    columns_section = True

                continue

            if re.match(
                r"^(?:PRIMARY KEY|FOREIGN KEYS|TABLE NAME|MODULE|PURPOSE|BUSINESS USAGE)$",
                stripped,
                re.IGNORECASE,
            ):
                break

            if re.match(
                r"^[A-Za-z_][A-Za-z0-9_$#]*$",
                stripped,
            ):
                columns.add(stripped.upper())

        return columns if columns else None

    # ==========================================================
    # VALIDATE REFERENCED TABLES
    # ==========================================================

    def validate_referenced_tables(
        self,
        table_aliases,
        schema_map
    ):

        referenced_tables = {
            table_name
            for table_name in table_aliases.values()
            if table_name is not None
        }

        # Only validate actual physical tables.
        # Derived/subquery aliases such as R and INV
        # are not database tables.
        referenced_physical_tables = {
            table_name
            for table_name in referenced_tables
            if table_name in schema_map
            or table_name in self.allowed_tables
        }

        disallowed_tables = [
            table_name
            for table_name in referenced_physical_tables
            if table_name not in self.allowed_tables
        ]

        if disallowed_tables:

            approved_tables = ", ".join(
                sorted(self.allowed_tables)
            )

            return False, (
                "Referenced table(s) are not allowed: "
                f"{', '.join(disallowed_tables)}. "
                f"Use only these approved sales tables: "
                f"{approved_tables}."
            )

        return True, None


    # ==========================================================
    # EXTRACT TABLE ALIASES
    # ==========================================================

    def extract_table_aliases(self, sql):

        aliases = {}

        sql_for_parsing = self._neutralize_non_clause_from(sql)

        # ======================================================
        # Physical FROM tables
        # ======================================================

        from_pattern = re.compile(
            r"\bFROM\s+"
            r"([A-Za-z_][A-Za-z0-9_$#]*)"
            r"(?:\s+(?:AS\s+)?"
            r"([A-Za-z_][A-Za-z0-9_$#]*))?",
            re.IGNORECASE
        )

        # ======================================================
        # Physical JOIN tables
        # ======================================================

        join_pattern = re.compile(
            r"\bJOIN\s+"
            r"([A-Za-z_][A-Za-z0-9_$#]*)"
            r"(?:\s+(?:AS\s+)?"
            r"([A-Za-z_][A-Za-z0-9_$#]*))?",
            re.IGNORECASE
        )

        sql_keywords = {
            "WHERE",
            "JOIN",
            "LEFT",
            "RIGHT",
            "INNER",
            "OUTER",
            "FULL",
            "CROSS",
            "ON",
            "GROUP",
            "ORDER",
            "HAVING",
            "UNION",
            "CONNECT",
            "START",
        }

        # ======================================================
        # Physical tables
        # ======================================================

        for pattern in [from_pattern, join_pattern]:

            matches = pattern.findall(sql_for_parsing)

            for table_name, alias in matches:

                table_name = table_name.upper()

                if alias:
                    alias = alias.upper()
                else:
                    alias = table_name

                if alias in sql_keywords:
                    alias = table_name

                aliases[alias] = table_name

        # ======================================================
        # Derived table / subquery aliases
        #
        # Examples:
        #
        # FROM (...) r
        # JOIN (...) inv
        #
        # We only need to register the alias here.
        # ======================================================

        derived_pattern = re.compile(
            r"\)\s*"
            r"(?:AS\s+)?"
            r"([A-Za-z_][A-Za-z0-9_$#]*)"
            r"(?=\s*(?:"
            r"LEFT\s+JOIN|"
            r"RIGHT\s+JOIN|"
            r"INNER\s+JOIN|"
            r"FULL\s+JOIN|"
            r"CROSS\s+JOIN|"
            r"JOIN|"
            r"ON|"
            r"WHERE|"
            r"GROUP\s+BY|"
            r"ORDER\s+BY|"
            r"HAVING|"
            r"UNION|"
            r"$"
            r"))",
            re.IGNORECASE
        )

        derived_matches = derived_pattern.findall(
            sql_for_parsing
        )

        for alias in derived_matches:

            alias = alias.upper()
            if alias not in sql_keywords:
                aliases[alias] = None

            # Do NOT treat this as a physical database table.
            # None means "derived table".
            

        return aliases


    # ==========================================================
    # NEUTRALIZE NON-CLAUSE "FROM" KEYWORDS
    #
    # Masks the FROM used inside EXTRACT(field FROM source) and
    # TRIM(... FROM ...) so it is never mistaken for the FROM
    # that introduces a table. Returns a modified copy; never
    # mutates the SQL that gets validated/executed.
    # ==========================================================

    def _neutralize_non_clause_from(self, sql):

        extract_fields = (
            r"YEAR|MONTH|DAY|HOUR|MINUTE|SECOND|"
            r"TIMEZONE_HOUR|TIMEZONE_MINUTE|"
            r"TIMEZONE_REGION|TIMEZONE_ABBR"
        )

        # EXTRACT(YEAR FROM ORDER_DATE) -> EXTRACT(YEAR XFROM ORDER_DATE)
        sql = re.sub(
            r"(\bEXTRACT\s*\(\s*(?:" + extract_fields + r")\s+)"
            r"FROM\b",
            r"\1XFROM",
            sql,
            flags=re.IGNORECASE
        )

        # TRIM(LEADING 'x' FROM col) -> TRIM(LEADING 'x' XFROM col)
        # TRIM(col FROM col)         -> TRIM(col XFROM col)
        sql = re.sub(
            r"(\bTRIM\s*\(\s*(?:LEADING\s+|TRAILING\s+|BOTH\s+)?"
            r"(?:'[^']*'|[A-Za-z_][A-Za-z0-9_$#]*)?\s*)"
            r"FROM\b",
            r"\1XFROM",
            sql,
            flags=re.IGNORECASE
        )

        return sql


    # ==========================================================
    # QUERY SCOPES (subquery-aware column resolution)
    # ==========================================================
    #
    # Everything below builds a tree of "scopes" out of the SQL,
    # one per SELECT/WITH block, based purely on parenthesis
    # nesting: a "(" is a scope boundary only when the very next
    # token is SELECT or WITH (a subquery/CTE), not for ordinary
    # function-call or grouping parens like SUM(...), TO_DATE(...).
    #
    # Each scope's OWN table/alias list only ever includes tables
    # introduced in ITS OWN FROM/JOIN clause, not any nested
    # subquery's tables and not any sibling subquery's tables.
    # Column resolution then walks from the innermost scope
    # outward (self -> parent -> grandparent -> ... -> root),
    # stopping at the first level where the column matches one or
    # more tables there. This mirrors real SQL scoping: an
    # unqualified/qualified column resolves against the smallest
    # enclosing query block it can, and two independent subqueries
    # that each unambiguously use the same column name never
    # collide with each other.
    # ==========================================================

    def build_scopes(self, sql):
        """
        Splits `sql` into a list of query scopes based on subquery
        parentheses (parens whose content begins with SELECT or
        WITH). Scope 0 is always the outermost/root query.

        Each scope is a dict:
            {
                'id': int,
                'parent': int or None,
                'start': int,   # index into `sql`
                'end': int,     # index into `sql`
            }

        `sql[start:end]` is the scope's full text, INCLUDING the
        text of any nested subqueries it contains (those get
        blanked out separately by `_scope_own_text` when needed).
        """

        n = len(sql)
        scopes = [{'id': 0, 'parent': None, 'start': 0, 'end': n}]
        scope_stack = [(0, 0)]
        depth = 0
        i = 0

        while i < n:
            ch = sql[i]

            # ------------------------------------------------
            # Skip over string literals so parens/keywords
            # inside them are never misread as SQL structure.
            # ------------------------------------------------

            if ch == "'":
                i += 1
                while i < n:
                    if sql[i] == "'" and i + 1 < n and sql[i + 1] == "'":
                        i += 2
                        continue
                    if sql[i] == "'":
                        i += 1
                        break
                    i += 1
                continue

            if ch == '(':
                depth += 1

                j = i + 1
                while j < n and sql[j].isspace():
                    j += 1

                is_subquery_open = bool(
                    re.match(
                        r"(SELECT|WITH)\b",
                        sql[j:j + 10],
                        re.IGNORECASE
                    )
                )

                if is_subquery_open:
                    new_id = len(scopes)
                    scopes.append({
                        'id': new_id,
                        'parent': scope_stack[-1][0],
                        'start': j,
                        'end': None,
                    })
                    scope_stack.append((new_id, depth))

                i += 1
                continue

            if ch == ')':

                if len(scope_stack) > 1 and scope_stack[-1][1] == depth:
                    scope_id, _ = scope_stack.pop()
                    scopes[scope_id]['end'] = i

                depth -= 1
                i += 1
                continue

            i += 1

        # Defensive: close any scope left open by malformed SQL
        # (unbalanced parens) so we still return usable spans.

        for scope in scopes:
            if scope['end'] is None:
                scope['end'] = n

        return scopes

    def _scope_own_text(self, sql, scope, scopes):
        """
        Returns this scope's own SQL text with every descendant
        scope's inner text replaced by spaces of the same length.

        This means a table/column that only appears inside a
        nested subquery is never picked up as belonging to THIS
        level. Offsets are preserved (blanked, not deleted) so
        nothing shifts and surrounding structure (e.g. the ")"
        and derived-table alias right after it) stays intact.
        """

        start, end = scope['start'], scope['end']
        text = list(sql[start:end])

        for other in scopes:

            if other['id'] == scope['id']:
                continue

            if other['start'] >= start and other['end'] <= end:

                for idx in range(other['start'] - start, other['end'] - start):
                    if 0 <= idx < len(text):
                        text[idx] = ' '

        return ''.join(text)

    def _is_from_clause_subquery(self, sql, scope):
        """
        True if `scope` (a nested SELECT/WITH scope) is the row
        source of a FROM or JOIN clause in its parent, e.g.

            FROM (SELECT ...) alias
            JOIN (SELECT ...) ON ...

        False for a subquery appearing in WHERE/HAVING, e.g.

            WHERE x IN (SELECT ...)
            WHERE EXISTS (SELECT ...)
            HAVING SUM(x) > (SELECT AVG(...) FROM t)

        Works by walking backward from the scope's start (which
        is where the "SELECT"/"WITH" token begins) past the
        opening "(" and any whitespace, to the word immediately
        preceding it.
        """

        start = scope['start']
        i = start - 1

        while i >= 0 and sql[i].isspace():
            i -= 1

        if i < 0 or sql[i] != '(':
            return False

        i -= 1

        while i >= 0 and sql[i].isspace():
            i -= 1

        j = i

        while j >= 0 and (sql[j].isalnum() or sql[j] in '_$#'):
            j -= 1

        word = sql[j + 1:i + 1].upper()

        return word in ('FROM', 'JOIN')

    def _get_scope_chain(self, scope_id, scope_info):
        """
        Returns [scope_id, parent_id, grandparent_id, ..., 0] —
        the innermost-to-outermost chain of scopes visible from
        `scope_id`, used to resolve correlated/inherited table
        references.
        """

        chain = []
        current = scope_id

        while current is not None:
            chain.append(current)
            current = scope_info[current]['parent']

        return chain

    def _table_columns(self, table_name, schema_map):
        """
        Resolves a table's column set, checking the retrieved
        schema map first and falling back to the local on-disk
        schema files. Returns None if the table is a derived
        table (table_name is None) or its schema is unknown.
        """

        if table_name is None:
            return None

        if table_name in schema_map:
            return schema_map[table_name]

        return self._load_table_columns_from_local_schema(table_name)

    # ==========================================================
    # VALIDATE COLUMNS (scope-aware, combined qualified +
    # unqualified check)
    # ==========================================================

    def validate_columns_scoped(self, sql, schema_map):

        scopes = self.build_scopes(sql)

        scope_info = {}

        for scope in scopes:

            own_text = self._scope_own_text(sql, scope, scopes)
            own_aliases = self.extract_table_aliases(own_text)

            scope_info[scope['id']] = {
                'own_text': own_text,
                'own_aliases': own_aliases,
                'parent': scope['parent'],
                'has_from_subquery_child': False,
            }

        # ------------------------------------------------------
        # Mark scopes whose FROM/JOIN clause contains a derived
        # table (a nested subquery used as a row source), as
        # opposed to a subquery that only appears in a
        # WHERE/HAVING predicate (EXISTS, scalar subquery, IN).
        #
        # A FROM-clause subquery can expose arbitrary output
        # columns (via its own SELECT list / column aliases) to
        # its parent scope, unqualified — e.g.
        #
        #   SELECT AVG(TOTAL_SALES)
        #   FROM (SELECT ... SUM(x) AS TOTAL_SALES ... )
        #
        # We don't re-parse the derived table's SELECT list, so
        # we can't know exactly which columns it exposes. Instead
        # we treat it the same conservative way an unresolvable
        # physical table already is: an unqualified identifier
        # that doesn't match anything else in scope is skipped
        # rather than failed, since it may legitimately be one of
        # the derived table's output columns. A WHERE-clause
        # subquery's own row source is irrelevant to the parent's
        # unqualified columns, so it deliberately does NOT get
        # this treatment.
        # ------------------------------------------------------

        for scope in scopes:

            parent_id = scope['parent']

            if parent_id is None:
                continue

            if self._is_from_clause_subquery(sql, scope):
                scope_info[parent_id]['has_from_subquery_child'] = True

        for scope_id, info in scope_info.items():

            valid, message = self._validate_qualified_in_scope(
                own_text=info['own_text'],
                scope_id=scope_id,
                scope_info=scope_info,
                schema_map=schema_map
            )

            if not valid:
                return False, message

            valid, message = self._validate_unqualified_in_scope(
                own_text=info['own_text'],
                scope_id=scope_id,
                scope_info=scope_info,
                schema_map=schema_map
            )

            if not valid:
                return False, message

        return True, "Columns are valid."

    # ----------------------------------------------------------
    # Qualified (alias.column) check, scope-aware.
    #
    # The alias is looked up starting at this scope and walking
    # outward, so a correlated reference to an ancestor query's
    # alias still resolves correctly, while an alias declared in
    # a sibling subquery (out of scope entirely) correctly does
    # NOT resolve.
    # ----------------------------------------------------------

    def _validate_qualified_in_scope(
        self,
        own_text,
        scope_id,
        scope_info,
        schema_map
    ):

        pattern = re.compile(
            r"\b([A-Za-z_][A-Za-z0-9_$#]*)"
            r"\s*\.\s*"
            r"([A-Za-z_][A-Za-z0-9_$#]*)\b",
            re.IGNORECASE
        )

        cleaned = self.remove_string_literals(own_text)
        matches = pattern.findall(cleaned)

        chain = self._get_scope_chain(scope_id, scope_info)

        NOT_FOUND = object()

        for alias, column in matches:

            alias_upper = alias.upper()
            column_upper = column.upper()

            resolved_table = NOT_FOUND

            for scope_id_in_chain in chain:

                aliases = scope_info[scope_id_in_chain]['own_aliases']

                if alias_upper in aliases:
                    resolved_table = aliases[alias_upper]
                    break

            if resolved_table is NOT_FOUND:

                return False, (
                    f"Alias '{alias}' is not declared "
                    f"in the SQL query."
                )

            # Derived table / subquery alias, or an alias whose
            # table has no known schema — nothing to validate
            # this column against, skip.

            if resolved_table is None:
                continue

            columns = self._table_columns(resolved_table, schema_map)

            if columns is None:
                continue

            if column_upper not in columns:

                return False, (
                    f"Column '{column}' does not exist "
                    f"in table '{resolved_table}'. "
                    f"Use only columns from the "
                    f"retrieved schema."
                )

        return True, "Qualified columns are valid."

    # ----------------------------------------------------------
    # Unqualified column check, scope-aware.
    #
    # Resolution walks from the innermost scope outward and stops
    # at the first level where the identifier matches one or more
    # tables declared THERE. Ambiguity is only flagged when
    # multiple tables at that SAME level share the column name —
    # never across unrelated sibling/descendant subqueries.
    # ----------------------------------------------------------

    def _validate_unqualified_in_scope(
        self,
        own_text,
        scope_id,
        scope_info,
        schema_map
    ):

        cleaned_sql = self.remove_string_literals(own_text)

        # Remove double-quoted aliases, e.g. AS "TOTAL SALES"

        cleaned_sql = re.sub(
            r'"[^"]*"',
            " ",
            cleaned_sql
        )

        # Collect unquoted output column aliases (AS TOTAL_AMOUNT)
        # declared at THIS level, so they're skipped as columns.

        select_alias_pattern = re.compile(
            r"\bAS\s+([A-Za-z_][A-Za-z0-9_$#]*)",
            re.IGNORECASE
        )

        select_aliases = {
            alias.upper()
            for alias in select_alias_pattern.findall(cleaned_sql)
        }

        # Remove qualified references (alias.column) so they
        # aren't re-checked here as unqualified identifiers.

        cleaned_sql = re.sub(
            r"\b[A-Za-z_][A-Za-z0-9_$#]*"
            r"\s*\.\s*"
            r"[A-Za-z_][A-Za-z0-9_$#]*\b",
            " ",
            cleaned_sql
        )

        # Remove numeric literals.

        cleaned_sql = re.sub(
            r"\b\d+(?:\.\d+)?\b",
            " ",
            cleaned_sql
        )

        identifier_pattern = re.compile(
            r"\b[A-Za-z_][A-Za-z0-9_$#]*\b",
            re.IGNORECASE
        )

        identifiers = identifier_pattern.findall(cleaned_sql)

        chain = self._get_scope_chain(scope_id, scope_info)

        # ------------------------------------------------------
        # Precompute, per level in the chain: the set of tables/
        # aliases visible there (so table/alias names themselves
        # are never mistaken for columns), each level's known-
        # schema column map, and whether ANY table anywhere in
        # the chain has unknown schema (used as the conservative
        # fallback: if we can't resolve an identifier anywhere
        # AND some table's contents are unknown, skip rather than
        # fail, since the column may legitimately belong to that
        # unknown table).
        # ------------------------------------------------------

        chain_table_names = set()
        chain_aliases_all = set()
        any_unknown_table = False
        per_level_schema = {}

        for scope_id_in_chain in chain:

            aliases = scope_info[scope_id_in_chain]['own_aliases']

            chain_aliases_all |= set(aliases.keys())

            level_tables = {
                table_name
                for table_name in aliases.values()
                if table_name is not None
            }

            chain_table_names |= level_tables

            # A FROM/JOIN-clause subquery at this level can expose
            # unknown output columns to this scope unqualified
            # (see build-time comment in validate_columns_scoped).

            if scope_info[scope_id_in_chain].get(
                'has_from_subquery_child'
            ):
                any_unknown_table = True

            level_schema = {}

            for table_name in level_tables:

                columns = self._table_columns(table_name, schema_map)

                if columns is None:
                    any_unknown_table = True
                else:
                    level_schema[table_name] = columns

            per_level_schema[scope_id_in_chain] = level_schema

        # ------------------------------------------------------
        # Check identifiers
        # ------------------------------------------------------

        for identifier in identifiers:

            identifier_upper = identifier.upper()

            if identifier_upper in self.sql_keywords:
                continue

            if identifier_upper in self.sql_functions:
                continue

            if identifier_upper in chain_table_names:
                continue

            if identifier_upper in chain_aliases_all:
                continue

            if identifier_upper in select_aliases:
                continue

            resolved = False

            for scope_id_in_chain in chain:

                level_schema = per_level_schema[scope_id_in_chain]

                matching_tables = [
                    table_name
                    for table_name, columns in level_schema.items()
                    if identifier_upper in columns
                ]

                if not matching_tables:
                    continue

                if len(matching_tables) > 1:

                    return False, (
                        f"Column '{identifier}' is ambiguous "
                        f"between the tables used in this query: "
                        f"{', '.join(matching_tables)}. "
                        f"Use a table alias."
                    )

                resolved = True
                break

            if resolved:
                continue

            if any_unknown_table:
                continue

            return False, (
                f"Column '{identifier}' does not exist "
                f"in the tables used by this SQL query."
            )

        return True, "Unqualified columns are valid."

    # ==========================================================
    # LEGACY FLAT VALIDATORS (kept for backward compatibility /
    # direct unit testing; no longer called by validate(), which
    # now uses validate_columns_scoped() instead — see above for
    # why the flat, whole-SQL versions produced false "ambiguous"
    # / "does not exist" errors for multi-subquery SQL).
    # ==========================================================

    # ==========================================================
    # VALIDATE alias.column
    #
    # Scoped to used_schema_map. If the alias's table has no
    # known schema (e.g. it came from a few-shot example, not
    # the retrieved schema), the column is skipped rather than
    # failed, since there is nothing to validate it against.
    # ==========================================================

    def validate_qualified_columns(
        self,
        sql,
        table_aliases,
        used_schema_map
    ):

        pattern = re.compile(
            r"\b"
            r"([A-Za-z_][A-Za-z0-9_$#]*)"
            r"\s*\.\s*"
            r"([A-Za-z_][A-Za-z0-9_$#]*)"
            r"\b",
            re.IGNORECASE
        )

        matches = pattern.findall(sql)

        for alias, column in matches:

            alias_upper = alias.upper()
            column_upper = column.upper()

            # --------------------------------------------------
            # Alias must be declared in this SQL's FROM/JOIN
            # --------------------------------------------------

            if alias_upper not in table_aliases:

                return False, (
                    f"Alias '{alias}' is not declared "
                    f"in the SQL query."
                )

            table_name = table_aliases[
                alias_upper
            ]

            # --------------------------------------------------
            # Table has no known schema (e.g. it came from a
            # few-shot example, not the retrieved schema).
            # Nothing to validate this column against — skip
            # rather than fail.
            # --------------------------------------------------

            if table_name is None:
                continue

            if table_name not in used_schema_map:
                continue

            valid_columns = used_schema_map[table_name]

            if column_upper not in valid_columns:

                return False, (
                    f"Column '{column}' does not exist "
                    f"in table '{table_name}'. "
                    f"Use only columns from the "
                    f"retrieved schema."
                )

        return True, "Qualified columns are valid."


    # ==========================================================
    # VALIDATE UNQUALIFIED COLUMNS
    #
    # An unqualified identifier can only match columns belonging
    # to tables that appear in this SQL's FROM/JOIN AND have
    # known schema. Columns that exist only in other retrieved-
    # but-unused tables are invisible to this check, by
    # construction. If the SQL also references a table with NO
    # known schema (e.g. from a few-shot example), an unmatched
    # identifier is skipped rather than failed, since it may
    # belong to that unknown table.
    # ==========================================================

    def validate_unqualified_columns(
        self,
        sql,
        table_aliases,
        used_schema_map
    ):

        # ------------------------------------------------------
        # Remove strings
        # ------------------------------------------------------

        cleaned_sql = self.remove_string_literals(sql)

        # ------------------------------------------------------
        # Remove double-quoted aliases
        #
        # Example:
        # AS "TOTAL SALES"
        #
        # We don't want TOTAL or SALES treated as columns.
        # ------------------------------------------------------

        cleaned_sql = re.sub(
            r'"[^"]*"',
            " ",
            cleaned_sql
        )

        # ------------------------------------------------------
        # Collect UNQUOTED output column aliases declared via AS
        #
        # Example:
        # SUM(CALC_TOTAL_PRICE) AS TOTAL_AMOUNT
        #
        # TOTAL_AMOUNT is an output alias, not a real column.
        # We record it so it is skipped everywhere it appears
        # in the query (e.g. if later referenced again in
        # ORDER BY), not just at the point it's declared. This
        # covers the case where the LLM didn't wrap the alias
        # in double quotes as the prompt instructed.
        # ------------------------------------------------------

        select_alias_pattern = re.compile(
            r"\bAS\s+([A-Za-z_][A-Za-z0-9_$#]*)",
            re.IGNORECASE
        )

        select_aliases = {
            alias.upper()
            for alias in select_alias_pattern.findall(cleaned_sql)
        }

        # ------------------------------------------------------
        # Remove qualified references
        #
        # o.ORDER_NO
        #
        # so ORDER_NO isn't checked again as unqualified.
        # ------------------------------------------------------

        cleaned_sql = re.sub(
            r"\b[A-Za-z_][A-Za-z0-9_$#]*"
            r"\s*\.\s*"
            r"[A-Za-z_][A-Za-z0-9_$#]*\b",
            " ",
            cleaned_sql
        )

        # ------------------------------------------------------
        # Remove numeric values
        # ------------------------------------------------------

        cleaned_sql = re.sub(
            r"\b\d+(?:\.\d+)?\b",
            " ",
            cleaned_sql
        )

        # ------------------------------------------------------
        # Extract identifiers
        # ------------------------------------------------------

        identifier_pattern = re.compile(
            r"\b[A-Za-z_][A-Za-z0-9_$#]*\b",
            re.IGNORECASE
        )

        identifiers = identifier_pattern.findall(
            cleaned_sql
        )

        sql_tables = set(table_aliases.values())

        # ------------------------------------------------------
        # If any table in this SQL has no known schema, we can't
        # be certain an unmatched identifier isn't a column of
        # that unknown table — so "does not exist" can't be
        # safely enforced. Ambiguity between KNOWN tables is
        # still checked, since that's independent of the unknown
        # table's contents.
        # ------------------------------------------------------

        has_unknown_table = bool(
            sql_tables - set(used_schema_map.keys())
        )

        # ------------------------------------------------------
        # Check identifiers
        # ------------------------------------------------------

        for identifier in identifiers:

            identifier_upper = identifier.upper()

            # --------------------------------------------------
            # SQL keyword
            # --------------------------------------------------

            if identifier_upper in self.sql_keywords:
                continue

            # --------------------------------------------------
            # SQL function
            # --------------------------------------------------

            if identifier_upper in self.sql_functions:
                continue

            # --------------------------------------------------
            # Table name
            # --------------------------------------------------

            if identifier_upper in sql_tables:
                continue

            # --------------------------------------------------
            # Table alias
            # --------------------------------------------------

            if identifier_upper in table_aliases:
                continue

            # --------------------------------------------------
            # Output column alias (declared via AS, unquoted)
            # --------------------------------------------------

            if identifier_upper in select_aliases:
                continue

            # --------------------------------------------------
            # Find column ONLY in tables used by this SQL
            # --------------------------------------------------

            matching_tables = []

            for table_name, columns in used_schema_map.items():

                if identifier_upper in columns:

                    matching_tables.append(
                        table_name
                    )

            # --------------------------------------------------
            # Column does not match any KNOWN table used by SQL.
            #
            # If an unknown table (no retrieved schema) is also
            # part of this SQL, we cannot rule out that the
            # column belongs to it — skip rather than fail.
            # --------------------------------------------------

            if not matching_tables:

                if has_unknown_table:
                    continue

                return False, (
                    f"Column '{identifier}' does not exist "
                    f"in the tables used by this SQL query."
                )

            # --------------------------------------------------
            # Ambiguous only if the SAME column name exists in
            # MULTIPLE tables actually used by this SQL
            # (a real Oracle ambiguity, not a retrieval artifact)
            # --------------------------------------------------

            if len(matching_tables) > 1:

                return False, (
                    f"Column '{identifier}' is ambiguous "
                    f"between the tables used in this query: "
                    f"{', '.join(matching_tables)}. "
                    f"Use a table alias."
                )

        return True, "Unqualified columns are valid."


    # ==========================================================
    # SELECT ALIAS CHECK
    # ==========================================================

    def validate_select_aliases(self, sql):

        # This method is intentionally lightweight.
        #
        # It prevents obvious mistakes such as:
        #
        # SELECT something AS
        #
        # but doesn't try to fully parse Oracle SQL.

        invalid_pattern = re.compile(
            r"\bAS\s*$",
            re.IGNORECASE
        )

        if invalid_pattern.search(sql):

            return False, (
                "Invalid SELECT alias."
            )

        return True, "SELECT aliases are valid."


    # ==========================================================
    # REMOVE STRING LITERALS
    # ==========================================================

    def remove_string_literals(self, sql):


        return re.sub(
            r"'(?:''|[^'])*'",
            " ",
            sql
        )