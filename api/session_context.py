from dataclasses import dataclass


@dataclass
class SessionContext:

    company_code: str = "01"

    # fiscal_year: str | None = None