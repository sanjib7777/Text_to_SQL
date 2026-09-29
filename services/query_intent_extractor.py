import json
import re
import nepali_datetime
from datetime import datetime


class QueryIntentExtractor:

    def __init__(self, llm):
        self.llm = llm

    # =========================================================
    # SYSTEM PROMPT
    # =========================================================

    SYSTEM_PROMPT = """
You are a query intent extraction system for an Oracle SQL generation agent.

Your ONLY task is to extract structured query requirements from the
user's natural-language question.

Return ONLY valid JSON.

The JSON MUST ALWAYS follow exactly this structure:

{
    "AD": true,
    "date_filter": {
        "required": false,
        "start_date": null,
        "end_date": null
    },
    "order_by": {
        "required": false,
        "column": null,
        "direction": null
    },
    "row_limit": {
        "required": false,
        "value": null
    }
}

==================================================
DATE SYSTEM
==================================================

The system supports both AD (Gregorian) and BS (Bikram Sambat)
dates.

AD FLAG:

- "AD": true  → The requested date is Gregorian/AD.
- "AD": false → The requested date is Nepali Bikram Sambat/BS.

Determine this from the user's query.

Examples:

- "2025" → AD = true
- "January 2025" → AD = true
- "2025 AD" → AD = true
- "2082 BS" → AD = false
- "2082 Bikram Sambat" → AD = false
- "Baishakh 2082" → AD = false
- "Mangsir 2081" → AD = false

If the query contains no date filter:

"AD": true

and:

"date_filter": {
    "required": false,
    "start_date": null,
    "end_date": null
}

==================================================
NEPALI BS MONTH MAPPING
==================================================

When the query uses Nepali/BS months, use the following month numbers:

Baishakh = 01
Jestha = 02
Asadh = 03
Shrawan = 04
Bhadra = 05
Bhadau = 05
Ashoj = 06
Kartik = 07
Mangsir = 08
Poush = 09
Magh = 10
Falgun = 11
Chaitra = 12

These month numbers correspond to the BS calendar.

Examples:

Baishakh 2082 → 2082-01
Jestha 2082 → 2082-02
Asadh 2082 → 2082-03
Shrawan 2082 → 2082-04
Mangsir 2082 → 2082-08
Chaitra 2082 → 2082-12

==================================================
DATE RANGE RULES
==================================================

Always return dates in:

YYYY-MM-DD

format.

The END DATE must be EXCLUSIVE.

For example:

First quarter of 2025:

start_date = "2025-01-01"
end_date = "2025-04-01"

First half of 2025:

start_date = "2025-01-01"
end_date = "2025-07-01"

Second half of 2025:

start_date = "2025-07-01"
end_date = "2026-01-01"

For BS dates, preserve the BS year and month numbers.

Example:

"Baishakh 2082 to Asadh 2082"

should produce:

start_date = "2082-01-01"
end_date = "2082-04-01"

Do NOT convert BS dates into AD dates.

==================================================
ORDER BY
==================================================

- Detect whether the user wants sorting.
- "highest", "largest", "top", "descending" generally means DESC.
- "lowest", "smallest", "ascending" generally means ASC.
- Return the requested column in uppercase when identifiable.
- If no ordering is requested:

"required": false,
"column": null,
"direction": null

==================================================
ROW LIMIT
==================================================

Detect requested number of rows/records/items.

Understand expressions such as:

"top 10"
"first 20"
"show only 50"
"latest 15"
"limit to 100"

Return only the integer.

If no row limit exists:

"required": false,
"value": null

==================================================
RELATIVE DATE INTERPRETATION
==================================================

When the user refers to a relative date without explicitly specifying
a calendar system or year, interpret the date using the current BS
(Bikram Sambat) calendar.

Examples:

- "this month" → Current BS month
- "this year" → Current BS year
- "previous month" → Previous BS month
- "last month" → Previous BS month
- "next month" → Next BS month
- "previous year" → Previous BS year
- "last year" → Previous BS year
- "next year" → Next BS year

Therefore, for relative date expressions without an explicit AD year,
set:

"AD": false

The current BS date will be provided separately in the user prompt.
Use that date to determine the actual BS year and month.

==================================================
EXPLICIT YEAR PRIORITY
==================================================

When the user explicitly mentions a year, determine the calendar system
from the year and any surrounding context.

1. If the user explicitly mentions an AD/Gregorian year, use AD.

Examples:

- "sales for 2025" → AD = true
- "sales for 2026" → AD = true
- "sales in January 2025" → AD = true
- "sales from 2024 to 2025" → AD = true
- "2025 AD" → AD = true
- "Gregorian 2025" → AD = true

2. If the user explicitly mentions a BS year, use BS.

Examples:

- "sales for 2082 BS" → AD = false
- "sales for 2083 BS" → AD = false
- "sales in Baishakh 2082" → AD = false
- "sales from 2081 to 2082 BS" → AD = false
- "2082 Bikram Sambat" → AD = false

3. If a month is explicitly written using a Nepali/BS month name
such as Baishakh, Jestha, Asadh, Shrawan, Bhadra, Ashoj, Kartik,
Mangsir, Poush, Magh, Falgun, or Chaitra, interpret it as BS unless
the user explicitly states that the date is AD.

Examples:

- "Baishakh sales" → AD = false
- "Mangsir 2082" → AD = false
- "sales in Chaitra" → AD = false

4. If the user says only "2025" or "2026" without "AD", interpret
the year as AD/Gregorian.

5. If the user says only a year in the typical BS range, such as
2081, 2082, or 2083, interpret it as BS.

6. If the user mentions a year around the current AD year, such as
2025 or 2026, interpret it as AD unless the user explicitly identifies
it as BS.

7. If the user mentions a year around the current BS year, such as
2081, 2082, or 2083, interpret it as BS unless the user explicitly
identifies it as AD.

==================================================
IMPORTANT
==================================================

- Do NOT generate SQL.
- Do NOT explain anything.
- Do NOT use Markdown.
- Return ONLY valid JSON.
"""

    


    def get_current_date(self) -> str:
        """
        Return the current AD date and time.
        Format: YYYY-MM-DD HH:MM:SS
        """
        today_ad = datetime.now()
        today_bs = nepali_datetime.datetime.now()

        bs_year = today_bs.year
        bs_month = today_bs.month

        # Nepal fiscal year starts from Shrawan (month 4)
        if bs_month >= 4:
            fiscal_year = f"{bs_year}/{str(bs_year + 1)[-2:]}"
        else:
            fiscal_year = f"{bs_year - 1}/{str(bs_year)[-2:]}"

        return (
            f"Current AD Date: {today_ad.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Current BS Date: {today_bs.strftime('%Y-%m-%d')}\n"
            f"Current Fiscal Year: {fiscal_year}"
        )

    def extract(self, user_query: str) -> dict:

        if not user_query or not user_query.strip():
            return self._empty_result()
        date_context = self.get_current_date()

        user_prompt = f"""
        Date Context:
        {date_context}

        User Query:
        {user_query}
        """
        print("user prompt is: ",user_prompt)

        try:

            response = self.llm.generate(
                user_prompt=user_prompt,
                system_prompt=self.SYSTEM_PROMPT
            )

            print("\n========== INTENT EXTRACTOR ==========")
            print(response)

            result = self._parse_json(response)

            result = self._normalize(result)

            return result

        except Exception as e:

            print(
                f"Intent extraction failed: {e}"
            )

            return self._empty_result()

    # =========================================================
    # JSON PARSER
    # =========================================================

    def _parse_json(self, response: str) -> dict:

        response = response.strip()

        # Remove markdown if model accidentally returns it
        response = re.sub(
            r"^```json\s*",
            "",
            response,
            flags=re.IGNORECASE
        )

        response = re.sub(
            r"^```\s*",
            "",
            response
        )

        response = re.sub(
            r"\s*```$",
            "",
            response
        )

        try:
            return json.loads(response)

        except json.JSONDecodeError:

            # Try extracting JSON object
            match = re.search(
                r"\{.*\}",
                response,
                re.DOTALL
            )

            if not match:
                raise ValueError(
                    "LLM did not return valid JSON"
                )

            return json.loads(
                match.group(0)
            )

    def _convert_bs_to_ad(self, date_string):
        """
        Convert a BS date in YYYY-MM-DD format to AD.
        """

        if not date_string:
            return None

        try:
            year, month, day = map(
                int,
                date_string.split("-")
            )

            bs_date = nepali_datetime.date(
                year,
                month,
                day
            )

            ad_date = bs_date.to_datetime_date()

            return ad_date.strftime("%Y-%m-%d")

        except Exception as e:

            print(
                f"BS to AD conversion failed for "
                f"{date_string}: {e}"
            )

            return None

    # =========================================================
    # NORMALIZE
    # =========================================================

    def _normalize(self, data: dict) -> dict:

        # =====================================================
        # AD / BS
        # =====================================================

        is_ad = self._normalize_ad(
            data.get("AD")
        )

        # =====================================================
        # DATE
        # =====================================================

        date_filter = data.get(
            "date_filter",
            {}
        )

        date_required = bool(
            date_filter.get(
                "required",
                False
            )
        )

        start_date = date_filter.get(
            "start_date"
        )

        end_date = date_filter.get(
            "end_date"
        )

        # -----------------------------------------------------
        # Convert BS → AD
        # -----------------------------------------------------

        if date_required and not is_ad:

            print(
                f"BS date detected: "
                f"{start_date} → {end_date}"
            )

            start_date = self._convert_bs_to_ad(
                start_date
            )

            end_date = self._convert_bs_to_ad(
                end_date
            )

            # Conversion failed
            if not start_date or not end_date:

                raise ValueError(
                    "Unable to convert BS date range to AD."
                )

            print(
                f"Converted AD range: "
                f"{start_date} → {end_date}"
            )

        # =====================================================
        # ORDER BY
        # =====================================================

        order_by = data.get(
            "order_by",
            {}
        )

        order_required = bool(
            order_by.get(
                "required",
                False
            )
        )

        order_column = order_by.get(
            "column"
        )

        direction = order_by.get(
            "direction"
        )

        if order_column:

            order_column = str(
                order_column
            ).strip().upper()

        if direction:

            direction = str(
                direction
            ).strip().upper()

            if direction not in {
                "ASC",
                "DESC"
            }:
                direction = None

        if not order_required:

            order_column = None
            direction = None

        # =====================================================
        # ROW LIMIT
        # =====================================================

        row_limit = data.get(
            "row_limit",
            {}
        )

        limit_required = bool(
            row_limit.get(
                "required",
                False
            )
        )

        value = row_limit.get(
            "value"
        )

        if value is not None:

            try:
                value = int(value)

            except (
                TypeError,
                ValueError
            ):
                value = None

        if not limit_required:

            value = None

    
        # =====================================================
        # FINAL RESULT
        # =====================================================

        return {

            # After conversion the dates are AD
            "AD": True,

            "date_filter": {

                "required": date_required,

                "start_date": start_date,

                "end_date": end_date
            },

            "order_by": {

                "required": order_required,

                "column": order_column,

                "direction": direction
            },

            "row_limit": {

                "required": limit_required,

                "value": value
            }               
        }

    # =========================================================
    # EMPTY RESULT
    # =========================================================

    @staticmethod
    def _normalize_ad(value):

        if isinstance(value, bool):
            return value

        if isinstance(value, str):

            value = value.strip().lower()

            if value in ("true", "ad", "gregorian"):
                return True

            if value in ("false", "bs", "bikram sambat"):
                return False

        # Default when no date system is explicitly identified
        return True

    @staticmethod
    def _empty_result():

        return {
            "AD": True,

            "date_filter": {
                "required": False,
                "start_date": None,
                "end_date": None
            },

            "order_by": {
                "required": False,
                "column": None,
                "direction": None
            },

            "row_limit": {
                "required": False,
                "value": None
            }
        }

if __name__ == "__main__":
    from llm.ollama_client import OllamaClient
    client = OllamaClient()
    extractor = QueryIntentExtractor(client)
    result = extractor.extract("Show the total monthly return value.")
    print(result)
