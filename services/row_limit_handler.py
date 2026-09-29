import re


class RowLimitHandler:

    def __init__(self):
        pass

    def apply_limit(
        self,
        generated_sql,
        limit=None,
        user_query=None
    ):

        if limit is None and user_query:
            query_match = re.search(
                r"\b(\d+)\s+(?:rows?|records?|sales\s+orders?)\b",
                user_query,
                re.IGNORECASE,
            )
            if query_match:
                limit = query_match.group(1)

        # No row limit requested
        if limit is None:
            return generated_sql

        try:
            limit = int(limit)
        except (TypeError, ValueError):
            return generated_sql

        if limit <= 0:
            return generated_sql

        sql = generated_sql.strip()

        # Remove trailing semicolon
        if sql.endswith(";"):
            sql = sql[:-1].strip()

        # -------------------------------------------------
        # Already has ROWNUM limit
        # -------------------------------------------------

        rownum_match = re.search(
            r"\bROWNUM\s*<=\s*(\d+)",
            sql,
            re.IGNORECASE
        )

        if rownum_match:

            # Existing limit is already present.
            # Keep the generated SQL unchanged.
            return sql

        # -------------------------------------------------
        # Already has FETCH FIRST
        # -------------------------------------------------

        fetch_match = re.search(
            r"\bFETCH\s+FIRST\s+(\d+)\s+ROWS?\s+ONLY\b",
            sql,
            re.IGNORECASE
        )

        if fetch_match:

            return sql

        # -------------------------------------------------
        # Apply Oracle ROWNUM
        # -------------------------------------------------

        return f"""
SELECT *
FROM (
    {sql}
)
WHERE ROWNUM <= {limit}
""".strip()

    def apply_pagination(self, generated_sql, page=1, page_size=100):
        """Apply an Oracle ROWNUM window without fetching earlier pages."""
        try:
            page = int(page)
            page_size = int(page_size)
        except (TypeError, ValueError):
            return generated_sql

        if page <= 0 or page_size <= 0:
            return generated_sql

        sql = generated_sql.strip()
        if sql.endswith(";"):
            sql = sql[:-1].strip()

        offset = (page - 1) * page_size
        end_row = offset + page_size

        return f"""
SELECT *
FROM (
    SELECT paged_query.*, ROWNUM AS row_number
    FROM (
        {sql}
    ) paged_query
    WHERE ROWNUM <= {end_row}
)
WHERE row_number > {offset}
""".strip()