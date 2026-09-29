import re
from datetime import datetime, timedelta
from Levenshtein import distance
import nepali_datetime


class CurrentDateContext:

    AD_MONTH_MAP = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }

    MONTH_MAP = {
        "baishakh": 1,
        "baisakh": 1,
        "bisekh": 1,
        "baishak": 1,

        "jestha": 2,
        "jeth": 2,
        "jetha": 2,
        "jesthaa": 2,

        "ashadh": 3,
        "asadh": 3,
        "asar": 3,
        "asaar": 3,
        "ashar": 3,

        "shrawan": 4,
        "saun": 4,
        "shawan": 4,
        "sharan": 4,
        "shraban": 4,

        "bhadra": 5,
        "bhadau": 5,
        "Bahadra": 5,

        "ashoj": 6,
        "asoj": 6,
        "ashwin": 6,

        "kartik": 7,
        "kartick": 7,
        "Kartick": 7,

        "mangsir": 8,
        "mansir": 8,
        "mangshir": 8,
        "Mangseer": 8,

        "poush": 9,
        "push": 9,
        "pous":9,

        "magh": 10,
        "marg": 10,
        "mag": 10,

        "falgun": 11,
        "phalgun": 11,
        "fagun": 11,

        "chaitra": 12,
        "chait": 12,
        "chaitr": 12
    }

    # =========================================================
    # Fiscal Year
    # =========================================================

    def _get_fiscal_year(
        self,
        bs_date: nepali_datetime.date
    ) -> str:

        """
        Nepal fiscal year starts from Shrawan (BS month 4).

        Example:
        2083 Shrawan -> Fiscal Year 2083/84
        """

        year = bs_date.year
        month = bs_date.month

        if month >= 4:

            next_year = str(year + 1)[-2:]

            return f"{year}/{next_year}"

        else:

            previous_year = year - 1
            current_year_short = str(year)[-2:]

            return (
                f"{previous_year}/"
                f"{current_year_short}"
            )

    # =========================================================
    # BS Month Name
    # =========================================================

    def _get_month_name(
        self,
        month_number: int
    ) -> str:

        month_names = [
            "Baishakh",
            "Jestha",
            "Ashadh",
            "Shrawan",
            "Bhadra",
            "Ashoj",
            "Kartik",
            "Mangsir",
            "Poush",
            "Magh",
            "Falgun",
            "Chaitra"
        ]

        return month_names[month_number - 1]

    # =========================================================
    # Detect explicit month keyword presence
    # =========================================================

    def _contains_month_keyword(self, user_query):

        if not user_query:
            return False

        return bool(
            re.search(r"\bmonths?\b", user_query, re.IGNORECASE)
        )

    # =========================================================
    # Previous BS Month
    # =========================================================

    def _detect_bs_month(self, user_query):

        query = user_query.lower()

        for month_name, month_number in self.MONTH_MAP.items():

            if re.search(
                rf"\b{re.escape(month_name)}\b",
                query
            ):
                return month_number

        if not self._contains_month_keyword(query):
            return None

        # ==================================================
        # STEP 2: Levenshtein fallback
        # ==================================================

        words = re.findall(
            r"[a-zA-Z]+",
            query
        )
        best_match = None
        best_distance = float("inf")

        for word in words:

            for month_name in self.MONTH_MAP:

                current_distance = distance(
                    word,
                    month_name
                )

                if current_distance < best_distance:

                    best_distance = current_distance
                    best_match = month_name

        # ==================================================
        # STEP 3: Apply threshold
        # ==================================================

        if best_match is None:
            return None

        # Don't accept very different words
        if best_distance > 2:
            return None

        print(
            f"Possible month typo detected: "
            f"'{best_match}' "
            f"(distance={best_distance})"
        )

        return self.MONTH_MAP[best_match]

    # =========================================================
    # Detect BS Month (Strict - No Fuzzy Matching)
    # =========================================================


    def _detect_bs_month_strict(self, user_query):
        """
        Detect month with exact matching only - no Levenshtein fallback.
        Used for disambiguating year vs month checks.
        
        Returns:
            int: Month number (1-12) or None if no exact match
        """

        if not user_query:
            return None

        query = user_query.lower()

        for month_name, month_number in self.MONTH_MAP.items():

            if re.search(
                rf"\b{re.escape(month_name)}\b",
                query
            ):
                return month_number

        return None

    # =========================================================
    # Detect Month Range (from month to month)
    # =========================================================

    def _detect_month_range(self, user_query):
        """
        Detects month range in query like:
        - "from baishak to jestha"
        - "baishak to jestha"
        - "between baishak and jestha"
        
        Returns:
            tuple: (start_month, end_month) or (None, None) if no range found
        """

        query = user_query.lower()

        # Pattern for "from X to Y" or "X to Y"
        range_patterns = [
            r"from\s+(\w+)\s+to\s+(\w+)",
            r"(\w+)\s+to\s+(\w+)",
            r"between\s+(\w+)\s+and\s+(\w+)",
        ]

        for pattern in range_patterns:
            match = re.search(pattern, query)

            if match:
                month1_str = match.group(1)
                month2_str = match.group(2)

                allow_fuzzy = self._contains_month_keyword(query)

                # Get month numbers
                month1 = self._fuzzy_match_month(
                    month1_str,
                    allow_fuzzy=allow_fuzzy,
                )
                month2 = self._fuzzy_match_month(
                    month2_str,
                    allow_fuzzy=allow_fuzzy,
                )

                if month1 is not None and month2 is not None:
                    # Return in order (start to end)
                    if month1 <= month2:
                        return (month1, month2)
                    else:
                        return (month2, month1)

        return (None, None)

    # =========================================================
    # Fuzzy Match Month Name
    # =========================================================

    def _fuzzy_match_month(self, month_str, allow_fuzzy=True):
        """
        Fuzzy match a month string to month number.
        
        Returns:
            int: Month number (1-12) or None if no match
        """

        month_str = month_str.lower().strip()

        # Exact match
        if month_str in self.MONTH_MAP:
            return self.MONTH_MAP[month_str]

        if not allow_fuzzy:
            return None

        # Fuzzy match with Levenshtein distance
        best_match = None
        best_distance = float("inf")

        for month_name, month_number in self.MONTH_MAP.items():
            current_distance = distance(month_str, month_name)

            if current_distance < best_distance:
                best_distance = current_distance
                best_match = month_number

        # Apply threshold
        if best_distance <= 2:
            return best_match

        return None

    # =========================================================
    # Get Multiple Months AD Range
    # =========================================================

    def get_multiple_months_ad_range(
        self,
        bs_year: int,
        start_month: int,
        end_month: int
    ):
        """
        Get AD date range for multiple BS months.
        
        Args:
            bs_year: Bikram Sambat year
            start_month: Starting month (1-12)
            end_month: Ending month (1-12)
            
        Returns:
            dict: Contains ad_start and ad_next dates
        """

        bs_start = nepali_datetime.date(
            bs_year,
            start_month,
            1
        )

        # End of the end_month
        if end_month == 12:
            bs_end = nepali_datetime.date(
                bs_year + 1,
                1,
                1
            )
        else:
            bs_end = nepali_datetime.date(
                bs_year,
                end_month + 1,
                1
            )

        ad_start = bs_start.to_datetime_date()
        ad_next = bs_end.to_datetime_date()

        return {
            "bs_start": bs_start,
            "bs_end": bs_end,
            "ad_start": ad_start,
            "ad_next": ad_next,
            "months": list(range(start_month, end_month + 1))
        }


    def _get_previous_month(
        self,
        bs_date: nepali_datetime.date
    ) -> tuple[int, str]:

        if bs_date.month == 1:

            previous_month = 12

        else:

            previous_month = bs_date.month - 1

        return (
            previous_month,
            self._get_month_name(previous_month)
        )

    def _detect_bs_year(self, user_query):

        if not user_query:
            return None

        query = user_query.lower()

        # Matches:
        # 2082 BS
        # 2082BS
        # BS 2082
        # bs 2082/83
        # 2082/83 BS
        # 2082 (plain number)

        patterns = [
            r"\b(20\d{2})\s*/\s*\d{2}\s*bs\b",
            r"\b(20\d{2})\s*bs\b",
            r"\bbs\s*(20\d{2})\b",
            r"\b(20\d{2})\b",  # Plain year number as last resort
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                query,
                re.IGNORECASE
            )

            if match:
                year = int(match.group(1))
                # Validate it's a reasonable BS year (2000-2100)
                if 2000 <= year <= 2100:
                    return year

        return None

    def _detect_ad_month(self, user_query):

        if not user_query:
            return None

        query = user_query.lower()

        for month_name, month_number in self.AD_MONTH_MAP.items():

            if re.search(
                rf"\b{re.escape(month_name)}\b",
                query,
            ):
                return month_number

        return None

    def _detect_ad_year(self, user_query):

        if not user_query:
            return None

        query = user_query.lower()

        patterns = [
            r"\b(19\d{2}|20\d{2})\s*/\s*\d{2}\b",
            r"\b(19\d{2}|20\d{2})\b",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                query,
                re.IGNORECASE,
            )

            if match:
                year = int(match.group(1))

                if 1900 <= year <= 2100:
                    return year

        return None

    def _detect_ad_date(self, user_query):

        if not user_query:
            return None

        query = user_query.lower()

        patterns = [
            r"\b(19\d{2}|20\d{2})[-/]([0-1]?\d)[-/]([0-3]?\d)\b",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                query,
                re.IGNORECASE,
            )

            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))

                try:
                    return datetime(year, month, day).date()
                except ValueError:
                    return None

        return None

    # =========================================================
    # Detect Current Year Keywords
    # =========================================================

    def _detect_current_year_keyword(self, user_query):
        """
        Detects "this year", "current year" keywords.
        
        Returns:
            bool: True if current year keyword found
        """

        if not user_query:
            return False

        query = user_query.lower()

        return (
            "this year" in query
            or "current year" in query
        )

    # =========================================================
    # Detect Previous Year Keywords
    # =========================================================

    def _detect_previous_year_keyword(self, user_query):
        """
        Detects "last year", "previous year" keywords.
        
        Returns:
            bool: True if previous year keyword found
        """

        if not user_query:
            return False

        query = user_query.lower()

        return (
            "last year" in query
            or "previous year" in query
        )

    # =========================================================
    # Current BS Month Boundaries
    # =========================================================

    def _get_current_month_range(
        self,
        bs_date: nepali_datetime.date
    ):

        """
        Returns:

        BS:
            Current month start
            Next month start

        AD:
            Corresponding AD start
            Corresponding AD next-month start

        We use [start, next_start) instead of
        start/end to make SQL date filtering safer.
        """

        # -----------------------------------------------------
        # Current BS month start
        # -----------------------------------------------------

        bs_month_start = nepali_datetime.date(
            bs_date.year,
            bs_date.month,
            1
        )

        # -----------------------------------------------------
        # Next BS month start
        # -----------------------------------------------------

        if bs_date.month == 12:

            bs_next_month_start = nepali_datetime.date(
                bs_date.year + 1,
                1,
                1
            )

        else:

            bs_next_month_start = nepali_datetime.date(
                bs_date.year,
                bs_date.month + 1,
                1
            )

        # -----------------------------------------------------
        # Convert BS → AD
        # -----------------------------------------------------

        ad_month_start = bs_month_start.to_datetime_date()

        ad_next_month_start = (
            bs_next_month_start.to_datetime_date()
        )

        return (
            bs_month_start,
            bs_next_month_start,
            ad_month_start,
            ad_next_month_start
        )

    # =========================================================
    # Previous BS Month Boundaries
    # =========================================================

    def _get_previous_month_range(
        self,
        bs_date: nepali_datetime.date
    ):

        """
        Returns the previous BS month's start and
        next-month start, along with their AD equivalents.
        """

        if bs_date.month == 1:

            previous_year = bs_date.year - 1

            bs_previous_start = nepali_datetime.date(
                previous_year,
                12,
                1
            )

            bs_previous_next_start = nepali_datetime.date(
                bs_date.year,
                1,
                1
            )

        else:

            bs_previous_start = nepali_datetime.date(
                bs_date.year,
                bs_date.month - 1,
                1
            )

            bs_previous_next_start = nepali_datetime.date(
                bs_date.year,
                bs_date.month,
                1
            )

        # -----------------------------------------------------
        # Convert BS → AD
        # -----------------------------------------------------

        ad_previous_start = (
            bs_previous_start.to_datetime_date()
        )

        ad_previous_next_start = (
            bs_previous_next_start.to_datetime_date()
        )

        return (
            bs_previous_start,
            bs_previous_next_start,
            ad_previous_start,
            ad_previous_next_start


        )

    def get_bs_month_ad_range(self, bs_year: int, bs_month: int):

        bs_start = nepali_datetime.date(
            bs_year,
            bs_month,
            1
        )

        if bs_month == 12:
            bs_next = nepali_datetime.date(
                bs_year + 1,
                1,
                1
            )
        else:
            bs_next = nepali_datetime.date(
                bs_year,
                bs_month + 1,
                1
            )

        ad_start = bs_start.to_datetime_date()
        ad_next = bs_next.to_datetime_date()

        return {
            "bs_start": bs_start,
            "bs_next": bs_next,
            "ad_start": ad_start,
            "ad_next": ad_next
        }

    # =========================================================
    # Get Fiscal Year AD Range
    # =========================================================

    def get_fiscal_year_ad_range(self, bs_year: int):
        """
        Get AD date range for a complete fiscal year (Shrawan - Chaitra).
        
        Nepal fiscal year runs from Shrawan (month 4) to Chaitra (month 12).
        
        Args:
            bs_year: Bikram Sambat year
            
        Returns:
            dict: Contains bs_start, bs_end, ad_start, ad_next, fiscal_year string
        """

        # Fiscal year starts from Shrawan (month 4)
        bs_start = nepali_datetime.date(bs_year, 4, 1)

        # Fiscal year ends just before next Shrawan
        bs_end = nepali_datetime.date(bs_year + 1, 4, 1)

        ad_start = bs_start.to_datetime_date()
        ad_next = bs_end.to_datetime_date()

        # Create fiscal year string (e.g., "2082/83")
        next_year_short = str(bs_year + 1)[-2:]
        fiscal_year = f"{bs_year}/{next_year_short}"

        return {
            "bs_start": bs_start,
            "bs_next": bs_end,
            "ad_start": ad_start,
            "ad_next": ad_next,
            "fiscal_year": fiscal_year
        }

    # =========================================================
    # Context
    # =========================================================

    def get_context(self, user_query=None):
        print(f"User Query for Date Context: {user_query}")

        today_ad = datetime.now()
        today_bs = nepali_datetime.date.today()

        context = []
        date_range = None
        for_else_flag = False

        query = user_query.lower() if user_query else ""

        if not for_else_flag:
            context.append(
                            f"""
                                            CURRENT DATE
                            
                                            Current AD Date:
                                            {today_ad.strftime('%Y-%m-%d %H:%M:%S')}
                            
                                            Current BS Date:
                                            {today_bs.strftime('%Y-%m-%d')}
                            
                                            Current BS Month:
                                            {self._get_month_name(today_bs.month)}
                            
                                            Current Fiscal Year:
                                            {self._get_fiscal_year(today_bs)}
                                            """
                        )
            for_else_flag = True

        else:

            # ==================================================
            # 0. Check for Year Keywords FIRST (before month checks)
            # to avoid Levenshtein distance conflicts with month names
            # ==================================================

            if self._detect_current_year_keyword(user_query):

                date_range = self.get_fiscal_year_ad_range(today_bs.year)

                context.append(
                    f"""
                        AD DATE RANGE FOR DATA EXTRACTION:
                        Following AD date interval should be used when
                        extracting data from the database and generating SQL.                   
                        START_DATE:
                        {date_range['ad_start'].strftime('%Y-%m-%d')}
                        
                        END_DATE:
                        {date_range['ad_next'].strftime('%Y-%m-%d')}
                    """
                )


            # ==================================================
            # 0b. Check for Previous Year Keyword
            # ==================================================

            elif self._detect_previous_year_keyword(user_query):

                previous_year = today_bs.year - 1
                date_range = self.get_fiscal_year_ad_range(previous_year)

                context.append(
                    f"""
                        AD DATE RANGE FOR DATA EXTRACTION:
                        Following AD date interval should be used when
                        extracting data from the database and generating SQL.                    
                        START_DATE:
                        {date_range['ad_start'].strftime('%Y-%m-%d')}
                        
                        END_DATE:
                        {date_range['ad_next'].strftime('%Y-%m-%d')}
                    """
                )

            

            # ==================================================
            # 0c. Check for Explicit AD Date (YYYY-MM-DD)
            # ==================================================

            elif self._detect_ad_date(user_query) is not None:

                requested_date = self._detect_ad_date(user_query)
                date_range = {
                    "ad_start": requested_date,
                    "ad_next": requested_date + timedelta(days=1),
                }

                context.append(
                    f"""
                        AD DATE RANGE FOR DATA EXTRACTION:
                        Following AD date interval should be used when
                        extracting data from the database and generating SQL.                   
                        START_DATE:
                        {date_range['ad_start'].strftime('%Y-%m-%d')}
                        
                        END_DATE:
                        {date_range['ad_next'].strftime('%Y-%m-%d')}
                    """
                )

            

            # ==================================================
            # 0d. Check for Gregorian month + year references
            #     - Treat as AD when year is in the current/past AD range
            #     - Treat as BS when year is greater than current AD year
            # ==================================================

            elif self._detect_ad_month(query) is not None:

                ad_month = self._detect_ad_month(query)
                ad_year = self._detect_ad_year(query)
                bs_year_hint = self._detect_bs_year(user_query)

                if ad_year is not None and ad_year <= today_ad.year:

                    ad_start = datetime(ad_year, ad_month, 1).date()

                    if ad_month == 12:
                        ad_next = datetime(ad_year + 1, 1, 1).date()
                    else:
                        ad_next = datetime(ad_year, ad_month + 1, 1).date()

                    date_range = {
                        "ad_start": ad_start,
                        "ad_next": ad_next,
                    }

                    context.append(
                        f"""
                        AD DATE RANGE FOR DATA EXTRACTION-AD:
                        Following AD date interval should be used when
                        extracting data from the database and generating SQL.                   
                        START_DATE:
                        {date_range['ad_start'].strftime('%Y-%m-%d')}
                        
                        END_DATE:
                        {date_range['ad_next'].strftime('%Y-%m-%d')}
                    """
                    )

                elif bs_year_hint is not None and bs_year_hint > today_ad.year:

                    date_range = self.get_bs_month_ad_range(
                        bs_year=bs_year_hint,
                        bs_month=ad_month,
                    )

                    context.append(
                        f"""
                        AD DATE RANGE FOR DATA EXTRACTION-BS:
                        Following AD date interval should be used when
                        extracting data from the database and generating SQL.                   
                        START_DATE:
                        {date_range['ad_start'].strftime('%Y-%m-%d')}
                        
                        END_DATE:
                        {date_range['ad_next'].strftime('%Y-%m-%d')}
                    """
                    )


            # ==================================================
            # 0e. Check for Explicit Year (no month mentioned)
            # ==================================================

            elif (
                self._detect_bs_year(user_query) is not None
                and self._detect_bs_month_strict(query) is None
                and self._detect_month_range(user_query if user_query else "")[0] is None
            ):

                requested_year = self._detect_bs_year(user_query)
                if requested_year <= today_ad.year:

                    ad_start = datetime(requested_year, 1, 1).date()
                    ad_next = datetime(requested_year + 1, 1, 1).date()

                    date_range = {
                        "ad_start": ad_start,
                        "ad_next": ad_next,
                    }

                    context.append(
                        f"""
                        AD DATE RANGE FOR DATA EXTRACTION:
                        Following AD date interval should be used when
                        extracting data from the database and generating SQL.                
                        START_DATE:
                        {date_range['ad_start'].strftime('%Y-%m-%d')}
                        
                        END_DATE:
                        {date_range['ad_next'].strftime('%Y-%m-%d')}
                    """
                    )

                else:

                    date_range = self.get_fiscal_year_ad_range(requested_year)

                    context.append(
                        f"""
                        AD DATE RANGE FOR DATA EXTRACTION:
                        Following AD date interval should be used when
                        extracting data from the database and generating SQL.                
                        START_DATE:
                        {date_range['ad_start'].strftime('%Y-%m-%d')}
                        
                        END_DATE:
                        {date_range['ad_next'].strftime('%Y-%m-%d')}
                    """
                    )
            

            # ==================================================
            # 1a. Check for Current/Previous Month Keywords
            # ==================================================
            
            elif "this month" in query or "current month" in query:

                date_range = self.get_bs_month_ad_range(
                    bs_year=today_bs.year,
                    bs_month=today_bs.month
                )

                month_name = self._get_month_name(today_bs.month)

                context.append(
                    f"""
                        AD DATE RANGE FOR DATA EXTRACTION:
                        Following AD date interval (start date and end date) should be used when
                        extracting data from the database and generating SQL.                    
                        START_DATE:
                        {date_range['ad_start'].strftime('%Y-%m-%d')}
                        
                        END_DATE:
                        {date_range['ad_next'].strftime('%Y-%m-%d')}
                    """
                )

            

            # ==================================================
            # 1b. Check for Previous/Last Month Keywords
            # ==================================================

            elif "last month" in query or "previous month" in query:

                if today_bs.month == 1:

                    year = today_bs.year - 1
                    month = 12

                else:

                    year = today_bs.year
                    month = today_bs.month - 1

                month_name = self._get_month_name(month)

                date_range = self.get_bs_month_ad_range(
                    bs_year=year,
                    bs_month=month
                )

                context.append(
                    f"""
                        AD DATE RANGE FOR DATA EXTRACTION:
                        Following AD date interval (start date and end date) should be used when
                        extracting data from the database and generating SQL.
                        START_DATE:
                        {date_range['ad_start'].strftime('%Y-%m-%d')}
                        
                        END_DATE:
                        {date_range['ad_next'].strftime('%Y-%m-%d')}
                
                        """
                )

            

            # ==================================================
            # 2. Check for Month Range (e.g., "baishak to jestha")
            # ==================================================

            elif self._detect_month_range(user_query if user_query else "")[0] is not None:

                start_month, end_month = self._detect_month_range(
                    user_query if user_query else ""
                )

                bs_year = (
                    self._detect_bs_year(user_query)
                    if user_query else None
                )

                if bs_year is None:
                    bs_year = today_bs.year

                # Format month names for display
                start_month_name = self._get_month_name(start_month)
                end_month_name = self._get_month_name(end_month)

                date_range = self.get_multiple_months_ad_range(
                    bs_year=bs_year,
                    start_month=start_month,
                    end_month=end_month
                )

                context.append(
                    f"""
                        AD DATE RANGE FOR DATA EXTRACTION:
                        Following AD date interval should be used when
                        extracting data from the database and generating SQL.                    
                        START_DATE:
                        {date_range['ad_start'].strftime('%Y-%m-%d')}
                        
                        END_DATE:
                        {date_range['ad_next'].strftime('%Y-%m-%d')}
                        """
                )

            

            # ==================================================
            # 3. Explicit BS month (single month)
            # ==================================================

            elif self._detect_bs_month(query):

                requested_month = self._detect_bs_month(query)
                requested_year = self._detect_bs_year(
                    user_query
                )
                print(f"Requested BS Month: {requested_month}")

                bs_year = (
                    requested_year
                    if requested_year is not None
                    else today_bs.year
                )

                month_name = self._get_month_name(requested_month)

                date_range = self.get_bs_month_ad_range(
                    bs_year=bs_year,
                    bs_month=requested_month
                )

                context.append(
                    f"""
                        AD DATE RANGE FOR DATA EXTRACTION:
                        Following AD date interval (start date and end date) should be used when
                        extracting data from the database and generating SQL.                    
                        START_DATE:
                        {date_range['ad_start'].strftime('%Y-%m-%d')}
                        
                        END_DATE:
                        {date_range['ad_next'].strftime('%Y-%m-%d')}
                        """
                )

            
        # ==================================================
        # 4. Default: Current Date Context
        # ==================================================

        # else:
            

        if not for_else_flag:
        # ==================================================
        # 5. General Current Date Context
        # ==================================================
            context.append(
                f"""
                    IMPORTANT:
                    The database stores dates in AD/Gregorian.

                    Use the appropriate date column from the retrieved
                    schema with these boundaries.

                    For example, if the relevant date column is SALES_DATE:
                    Select * FROM SALES_TABLE S
                    WHERE TRUNC(s.SALES_DATE) >= TO_DATE('ad_start', 'YYYY-MM-DD')
                    AND TRUNC(s.SALES_DATE) < TO_DATE('ad_next', 'YYYY-MM-DD')
                    ORDER BY s.SALES_DATE ASC;

                    #IMPORTANT# : filter the relevant date column using BOTH boundaries like above examples if start date and end date are present in the context.
                    and replace the ad_start with START_DATE and ad_next with END_DATE (query should contains those date only strictly).

                    Use the actual date column from the retrieved schema.

                    Note: If date is not relevant to the user query, you can ignore this context and proceed with SQL generation.
                    """
                        )
        # print("date context is: ", "\n".join(context))
            
        return "\n".join(context), date_range


if __name__ == "__main__":
    current_date_context = CurrentDateContext()
    
    date_context, date_range = current_date_context.get_context(
        user_query="Show the sales order lines placed in the first quarter of 2025, with order date, customer, item, and total price."
    )
    print(date_context)
    print(f"Date Range: {date_range}")