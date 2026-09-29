import nepali_datetime

# Create a Bikram Sambat (BS) date: Year, Month, Day (e.g., 1st Baishakh 2081)
bs_date = nepali_datetime.date(2081, 6, 6)

# Convert BS to AD (English / Gregorian date)
ad_date = bs_date.to_datetime_date()

print(ad_date)  # Output: 2024-04-13