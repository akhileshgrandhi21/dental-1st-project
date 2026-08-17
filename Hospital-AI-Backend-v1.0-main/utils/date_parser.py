import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from config import TIMEZONE

logger = logging.getLogger(__name__)

def parse_flexible_date(date_input: str) -> date:
    """
    Parses dynamic human expressions ("today", "tomorrow", "next monday", "next friday", etc.)
    as well as standard "YYYY-MM-DD" formats, converting them to a Python date object.
    Raises ValueError on invalid input or formats.
    """
    if not date_input or not isinstance(date_input, str):
        raise ValueError("Date input must be a non-empty string.")

    cleaned = date_input.strip().lower()

    # Get local current date using configured timezone
    try:
        tz = ZoneInfo(TIMEZONE)
        today_tz = datetime.now(tz).date()
    except Exception as e:
        logger.error(f"Error loading timezone {TIMEZONE}: {e}. Falling back to default system date.")
        today_tz = date.today()

    if cleaned == "today":
        return today_tz
    elif cleaned == "tomorrow":
        return today_tz + timedelta(days=1)

    # Next weekday parsing (e.g. "next monday", "next friday")
    if cleaned.startswith("next "):
        weekday_name = cleaned[5:].strip()
        days_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
            "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6
        }
        if weekday_name in days_map:
            target_weekday = days_map[weekday_name]
            current_weekday = today_tz.weekday()
            
            # Days ahead to the upcoming target weekday
            days_ahead = (target_weekday - current_weekday) % 7
            if days_ahead == 0:
                days_ahead = 7
            return today_tz + timedelta(days=days_ahead)

    # Only accept documented formats: YYYY-MM-DD and natural expressions
    try:
        return datetime.strptime(cleaned, "%Y-%m-%d").date()
    except ValueError:
        logger.warning(f"Failed to parse flexible date: '{date_input}'")
        raise ValueError(
            f"Invalid date format or keyword: '{date_input}'. "
            "Supported: 'today', 'tomorrow', 'next <weekday>', or 'YYYY-MM-DD'."
        )

def parse_flexible_time(time_input: str) -> str:
    """
    Parses and normalizes custom time inputs (e.g. "9", "9am", "9:30 AM", "14:00")
    to standard "HH:MM" 24-hour time format.
    Raises ValueError on invalid inputs.
    """
    if not time_input or not isinstance(time_input, str):
        raise ValueError("Time input must be a non-empty string.")

    cleaned = time_input.strip().lower()

    # Check AM/PM suffixes
    is_pm = "pm" in cleaned
    is_am = "am" in cleaned

    # Strip AM/PM strings and extra spaces
    time_num = cleaned.replace("am", "").replace("pm", "").strip()

    # Match hour and minute parts
    if ":" in time_num:
        parts = time_num.split(":")
        if len(parts) == 2:
            try:
                hour = int(parts[0])
                minute = int(parts[1])
            except ValueError:
                raise ValueError(f"Invalid numeric characters in time: '{time_input}'")
        else:
            raise ValueError(f"Invalid time format: '{time_input}'")
    else:
        # Single hours digits like "9" or "14"
        try:
            hour = int(time_num)
            minute = 0
        except ValueError:
            raise ValueError(f"Invalid hours format: '{time_input}'")

    # Shift hour parameters for PM/AM conventions
    if is_pm and hour < 12:
        hour += 12
    elif is_am and hour == 12:
        hour = 0

    # Boundary verification checks
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        logger.warning(f"Time out of range bounds: hour={hour}, minute={minute} from input '{time_input}'")
        raise ValueError(f"Time is out of valid range: '{time_input}'. Hour must be 0-23, Minute 0-59.")

    return f"{hour:02d}:{minute:02d}"
