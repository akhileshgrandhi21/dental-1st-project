import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Explicitly load .env file
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

# Hospital Metadata Configurations (load from environment variables)
HOSPITAL_NAME = os.getenv("HOSPITAL_NAME", "ABC Hospital")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
DEFAULT_SLOT_DURATION = int(os.getenv("DEFAULT_SLOT_DURATION", "30"))
DEFAULT_START_TIME = "09:00"
DEFAULT_END_TIME = "20:00"
APPOINTMENT_LIMITS_DAYS = 14

# Database and App Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///local_hospital.db")
VERSION = os.getenv("VERSION", "1.0.0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# CORS Allowed Origins
raw_cors = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS = [origin.strip() for origin in raw_cors.split(",") if origin.strip()]

# Standard Hospital Holidays (YYYY-MM-DD)
HOLIDAYS = [
    "2026-08-15",  # Independence Day
    "2026-01-26",  # Republic Day
    "2026-10-02",  # Gandhi Jayanti
    "2026-12-25",  # Christmas
]
