import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from database.models import Appointment
from services.doctor_service import DoctorService
from utils.date_parser import parse_flexible_date
from config import HOLIDAYS, APPOINTMENT_LIMITS_DAYS

# Setup logging
logger = logging.getLogger(__name__)

DAYS_MAP = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6
}

class AvailabilityService:
    def __init__(self, db: Session):
        self.db = db
        self.doc_service = DoctorService(db)

    def parse_available_days(self, days_str: str) -> List[int]:
        """
        Parses available days string from database (e.g. "Mon,Tue,Wed,Fri" or "Mon-Sat")
        into a list of weekday integers (0 = Mon, ..., 6 = Sun).
        """
        if not days_str or not isinstance(days_str, str):
            return []
        
        days_str = days_str.strip()
        available_days = set()

        # Handle ranges like Mon-Sat
        if "-" in days_str:
            parts = days_str.split("-")
            if len(parts) == 2:
                start_day = parts[0].strip()[:3].lower()
                end_day = parts[1].strip()[:3].lower()
                if start_day in DAYS_MAP and end_day in DAYS_MAP:
                    start_idx = DAYS_MAP[start_day]
                    end_idx = DAYS_MAP[end_day]
                    if start_idx <= end_idx:
                        for i in range(start_idx, end_idx + 1):
                            available_days.add(i)
                    else:
                        # Handle wrapping range (e.g. Sat-Tue)
                        for i in range(start_idx, 7):
                            available_days.add(i)
                        for i in range(0, end_idx + 1):
                            available_days.add(i)

        # Handle comma-separated list like Mon,Tue,Wed,Fri
        elif "," in days_str:
            parts = days_str.split(",")
            for p in parts:
                d = p.strip()[:3].lower()
                if d in DAYS_MAP:
                    available_days.add(DAYS_MAP[d])
        else:
            # Single day
            d = days_str.strip()[:3].lower()
            if d in DAYS_MAP:
                available_days.add(DAYS_MAP[d])

        return sorted(list(available_days))

    def is_doctor_available_on_date(self, doctor: Dict[str, Any], check_date: date) -> bool:
        """Checks if a doctor works on the day of the week for the given date."""
        available_days = self.parse_available_days(doctor.get("Available Days", ""))
        return check_date.weekday() in available_days

    def generate_slots(self, start_time_str: str, end_time_str: str, slot_duration: int) -> List[str]:
        """Generates time slot start times (e.g., ['09:00', '09:30', ...])."""
        slots = []
        try:
            start_parts = start_time_str.split(":")
            end_parts = end_time_str.split(":")
            
            start_dt = datetime.strptime(f"{start_parts[0].zfill(2)}:{start_parts[1].zfill(2)}", "%H:%M")
            end_dt = datetime.strptime(f"{end_parts[0].zfill(2)}:{end_parts[1].zfill(2)}", "%H:%M")
            
            current_dt = start_dt
            while current_dt + timedelta(minutes=slot_duration) <= end_dt:
                slots.append(current_dt.strftime("%H:%M"))
                current_dt += timedelta(minutes=slot_duration)
        except Exception as e:
            logger.error(f"Error generating slots: {e}")
        return slots

    def normalize_time(self, time_str: str) -> str:
        """Normalizes times to HH:MM format."""
        if not time_str:
            return ""
        parts = str(time_str).split(":")
        if len(parts) >= 2:
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        return time_str

    def get_available_slots(self, doctor_id: str, date_str: str) -> Dict[str, Any]:
        """
        Gets available slots for a doctor on a specific date, checking calendar,
        holidays, and schedule logic. Supports flexible date keyword inputs.
        """
        doctor = self.doc_service.get_doctor_by_id(doctor_id)
        if not doctor:
            return {"status": "error", "message": f"Doctor with ID {doctor_id} not found"}

        # Flexible Date parsing support
        try:
            check_date = parse_flexible_date(date_str)
            # Re-normalize date_str to standardized format YYYY-MM-DD
            date_str = check_date.strftime("%Y-%m-%d")
        except ValueError as e:
            return {"status": "error", "message": str(e)}

        # 1. Check if date is a configured public/hospital holiday
        if date_str in HOLIDAYS:
            next_date = self.get_next_available_date(doctor, check_date + timedelta(days=1))
            logger.info(f"Availability check: {date_str} is a hospital holiday. Recommending next date: {next_date}")
            return {
                "status": "unavailable",
                "message": f"{doctor['Doctor Name']} is not available on {date_str} (Public/Hospital Holiday).",
                "next_available_date": next_date.strftime("%Y-%m-%d") if next_date else None,
                "available_slots": [],
                "slots": [],
                "doctor": doctor,
                "date": date_str,
                "consultation_duration": doctor["Slot Duration"],
                "department": doctor["Department"]
            }

        # 2. Check if doctor works on this weekday
        if not self.is_doctor_available_on_date(doctor, check_date):
            next_date = self.get_next_available_date(doctor, check_date)
            logger.info(f"Availability check: Doctor not available on weekday {check_date.strftime('%A')}. Recommending: {next_date}")
            return {
                "status": "unavailable",
                "message": f"{doctor['Doctor Name']} is not available on {date_str} ({check_date.strftime('%A')}).",
                "next_available_date": next_date.strftime("%Y-%m-%d") if next_date else None,
                "available_slots": [],
                "slots": [],
                "doctor": doctor,
                "date": date_str,
                "consultation_duration": doctor["Slot Duration"],
                "department": doctor["Department"]
            }

        # Generate all slots for the doctor
        start_time = doctor.get("Start Time", "09:00")
        end_time = doctor.get("End Time", "17:00")
        duration = doctor.get("Slot Duration", 30)
        
        all_slots = self.generate_slots(start_time, end_time, duration)

        # Get booked slots from the database
        appointments_models = self.db.query(Appointment).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == date_str,
            Appointment.status != "Cancelled"
        ).all()

        booked_times = set()
        for appt in appointments_models:
            booked_time = self.normalize_time(appt.appointment_time)
            if booked_time:
                booked_times.add(booked_time)

        # Build list of slots with availability details
        slots_availability = []
        available_slots_only = []
        for slot in all_slots:
            is_available = slot not in booked_times
            slots_availability.append({
                "time": slot,
                "available": is_available
            })
            if is_available:
                available_slots_only.append(slot)

        if not available_slots_only:
            # Doctor is working but fully booked, search next available date
            next_date = self.get_next_available_date(doctor, check_date + timedelta(days=1))
            logger.info(f"Availability check: Doctor is fully booked on {date_str}. Recommending: {next_date}")
            return {
                "status": "fully_booked",
                "message": f"{doctor['Doctor Name']} is fully booked on {date_str}.",
                "next_available_date": next_date.strftime("%Y-%m-%d") if next_date else None,
                "available_slots": [],
                "slots": slots_availability,
                "doctor": doctor,
                "date": date_str,
                "consultation_duration": doctor["Slot Duration"],
                "department": doctor["Department"]
            }

        logger.info(f"Availability check: Doctor has {len(available_slots_only)} slots available on {date_str}")
        return {
            "status": "available",
            "doctor": doctor,
            "date": date_str,
            "available_slots": available_slots_only,
            "slots": slots_availability,
            "consultation_duration": doctor["Slot Duration"],
            "department": doctor["Department"],
            "next_available_date": None
        }

    def get_next_available_date(self, doctor: Dict[str, Any], start_date: date) -> Optional[date]:
        """Finds the next date (within APPOINTMENT_LIMITS_DAYS) on which the doctor has at least one free slot."""
        available_weekdays = self.parse_available_days(doctor.get("Available Days", ""))
        if not available_weekdays:
            return None

        start_time = doctor.get("Start Time", "09:00")
        end_time = doctor.get("End Time", "17:00")
        duration = doctor.get("Slot Duration", 30)
        all_slots = self.generate_slots(start_time, end_time, duration)
        if not all_slots:
            return None

        # Check up to APPOINTMENT_LIMITS_DAYS in the future
        for i in range(0, APPOINTMENT_LIMITS_DAYS + 1):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime("%Y-%m-%d")
            
            # Skip if date is a holiday
            if date_str in HOLIDAYS:
                continue
                
            if current_date.weekday() in available_weekdays:
                # Count booked slots for this doctor in database
                booked_count = self.db.query(Appointment).filter(
                    Appointment.doctor_id == doctor["Doctor ID"],
                    Appointment.appointment_date == date_str,
                    Appointment.status != "Cancelled"
                ).count()
                
                if booked_count < len(all_slots):
                    return current_date

        return None
