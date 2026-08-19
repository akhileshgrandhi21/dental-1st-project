import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from database.models import Doctor, Appointment
from services.doctor_service import DoctorService
from services.availability_service import AvailabilityService
from utils.id_generator import generate_appointment_id
from utils.date_parser import parse_flexible_date, parse_flexible_time
from config import TIMEZONE, HOLIDAYS, DEFAULT_START_TIME, DEFAULT_END_TIME

# Setup logging
logger = logging.getLogger(__name__)

class BookingService:
    def __init__(self, db: Session, availability_service: Optional[AvailabilityService] = None):
        self.db = db
        self.avail = availability_service or AvailabilityService(db)
        self.doc_service = DoctorService(db)

    def normalize_time(self, time_str: str) -> str:
        """Normalizes time to HH:MM format."""
        if not time_str:
            return ""
        parts = str(time_str).split(":")
        if len(parts) >= 2:
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        return time_str

    def normalize_mobile(self, mobile_str: str) -> str:
        """Removes spaces, hyphens, and parentheses from mobile numbers."""
        if not mobile_str:
            return ""
        return re.sub(r"[\s\-\(\)\+]", "", str(mobile_str))

    def validate_booking_inputs(self, data: Dict[str, Any]) -> None:
        """
        Validates the inputs for creating a booking. Normalizes fields and checks time/date boundaries.
        Raises HTTPException if invalid.
        """
        # 1. Validate Patient Name
        patient_name = data.get("patient_name")
        if not patient_name or not str(patient_name).strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "Patient name cannot be empty",
                    "errors": ["The patient_name field is required and must not be blank."]
                }
            )
        # Sanitization: Strip and remove HTML/script injection tags
        sanitized_name = re.sub(r"[<>\&\"\'/]", "", str(patient_name)).strip()
        data["patient_name"] = sanitized_name

        # 2. Validate Mobile
        mobile = data.get("mobile")
        if not mobile:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "Mobile number cannot be empty",
                    "errors": ["The mobile field is required."]
                }
            )

        mobile_cleaned = self.normalize_mobile(str(mobile))
        if not mobile_cleaned.isdigit() or len(mobile_cleaned) < 5:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": f"Invalid mobile number: '{mobile}'",
                    "errors": ["Mobile number must contain at least 5 digits."]
                }
            )
        data["mobile"] = mobile_cleaned

        # 3. Flexible Date Parsing
        date_str = data.get("date")
        if not date_str:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "Date is required",
                    "errors": ["The date field is required."]
                }
            )
        try:
            check_date = parse_flexible_date(str(date_str))
            # Save parsed date and standardized string format back
            data["date_parsed"] = check_date
            data["date"] = check_date.strftime("%Y-%m-%d")
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": str(e),
                    "errors": [str(e)]
                }
            )

        # 4. Past Date Validation using configured Timezone
        current_date_tz = datetime.now(ZoneInfo(TIMEZONE)).date()
        if data["date_parsed"] < current_date_tz:
            logger.warning(f"Booking validation failed: date {data['date']} is in the past compared to today {current_date_tz}")
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": f"Cannot book an appointment in the past (Date: {data['date']}).",
                    "errors": [f"Selected date '{data['date']}' is prior to today's date '{current_date_tz.strftime('%Y-%m-%d')}'."]
                }
            )

        # 5. Flexible Time Parsing
        time_str = data.get("time")
        if not time_str:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "Time is required",
                    "errors": ["The time field is required."]
                }
            )
        try:
            check_time_str = parse_flexible_time(str(time_str))
            data["time"] = check_time_str
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": str(e),
                    "errors": [str(e)]
                }
            )

        # 6. Check Closed Hospital Hours Validation
        if data["time"] < DEFAULT_START_TIME or data["time"] > DEFAULT_END_TIME:
            logger.warning(f"Booking validation failed: Selected time {data['time']} is outside hospital hours {DEFAULT_START_TIME}-{DEFAULT_END_TIME}")
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": f"Hospital is closed at {data['time']}. Hospital hours: {DEFAULT_START_TIME} to {DEFAULT_END_TIME}.",
                    "errors": [f"Selected slot time is outside the hospital operational window."]
                }
            )

    def book_appointment(self, booking_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates, checks availability, and books an appointment.
        """
        # 1. Input Validation and Normalization (raises HTTPException if invalid)
        self.validate_booking_inputs(booking_data)

        patient_name = booking_data["patient_name"]
        mobile = booking_data["mobile"]
        doctor_name_input = booking_data.get("doctor_name")
        doctor_id_input = booking_data.get("doctor_id")
        date_str = booking_data["date"]
        time_str = booking_data["time"]

        logger.info(f"Booking request verified: patient={patient_name}, doctor_id={doctor_id_input}, doctor_name={doctor_name_input}, date={date_str}, time={time_str}")

        # 2. Verify Doctor Exists (Checks id, name, or synonym resolve)
        doctor = None
        if doctor_id_input:
            doctor = self.db.query(Doctor).filter(Doctor.doctor_id == doctor_id_input).first()
            if not doctor:
                # Try flexible resolution for doctor ID
                test_id_doc = self.doc_service.get_doctor_by_id(doctor_id_input)
                if test_id_doc:
                    doctor = self.db.query(Doctor).filter(Doctor.doctor_id == test_id_doc["Doctor ID"]).first()
        elif doctor_name_input:
            doctor = self.db.query(Doctor).filter(Doctor.doctor_name == doctor_name_input).first()
            if not doctor:
                # Normal search with synonyms and tokens
                matched_docs = self.doc_service.search_doctors(doctor_name_input)
                if matched_docs:
                    doctor = self.db.query(Doctor).filter(Doctor.doctor_id == matched_docs[0]["Doctor ID"]).first()

        if not doctor:
            doc_query = doctor_id_input or doctor_name_input or "unspecified"
            logger.warning(f"Doctor lookup failed for search query: '{doc_query}'")
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "Doctor not found",
                    "errors": [f"No active doctor profile found matching identifier: '{doc_query}'."]
                }
            )

        doctor_id = doctor.doctor_id
        doctor_name = doctor.doctor_name
        department = doctor.department

        # 3. Check for Duplicate Active Booking
        # Same doctor, same date, same time, and same patient mobile
        duplicate = self.db.query(Appointment).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == date_str,
            Appointment.appointment_time == time_str,
            Appointment.mobile == mobile,
            Appointment.status != "Cancelled"
        ).first()

        if duplicate:
            logger.warning(f"Duplicate booking attempt detected for mobile {mobile} under doctor {doctor_name} at {date_str} {time_str}")
            raise HTTPException(
                status_code=409,
                detail={
                    "success": False,
                    "message": "An appointment already exists for this patient at the selected time.",
                    "errors": [f"Duplicate booking detected for mobile {mobile} at the same slot."]
                }
            )

        # 4. Check Availability via AvailabilityService
        avail_res = self.avail.get_available_slots(doctor_id, date_str)
        if avail_res.get("status") == "error":
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": avail_res.get("message"),
                    "errors": [avail_res.get("message")]
                }
            )

        # If doctor works but has no slots or is holiday/weekend, get_available_slots returns status: unavailable/fully_booked
        if avail_res.get("status") in ["unavailable", "fully_booked"]:
            msg = avail_res.get("message", "Selected slot date is not available.")
            logger.warning(f"Booking block: doctor unavailable. Details: {msg}")
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": msg,
                    "errors": [msg],
                    "data": {
                        "available_slots": [],
                        "next_available_date": avail_res.get("next_available_date")
                    }
                }
            )

        # Check if the requested slot is available
        available_slots = avail_res.get("available_slots", [])
        if time_str not in available_slots:
            logger.warning(f"Slot {time_str} is not available for doctor {doctor_name} on {date_str}")
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": f"Selected time slot {time_str} is unavailable.",
                    "errors": [f"Slot {time_str} is already booked or outside doctor's work hours."],
                    "data": {
                        "available_slots": available_slots,
                        "next_available_date": avail_res.get("next_available_date")
                    }
                }
            )

        # 5. Generate Professional Sequential ID
        existing_ids = [a[0] for a in self.db.query(Appointment.appointment_id).all()]
        appt_id = generate_appointment_id(existing_ids)

        # 6. Save the Appointment
        created_at_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")
        new_appt = Appointment(
            appointment_id=appt_id,
            patient_name=patient_name,
            mobile=mobile,
            doctor_id=doctor_id,
            doctor_name=doctor_name,
            department=department,
            appointment_date=date_str,
            appointment_time=time_str,
            status="Booked",
            created_at=created_at_str
        )
        self.db.add(new_appt)
        self.db.commit()

        logger.info(f"Successfully booked appointment {appt_id} for {patient_name}")
        
        # Standard Response Format payload matching specifications
        return {
            "success": True,
            "message": "Appointment booked successfully.",
            "data": {
                "appointment": {
                    "appointment_id": appt_id,
                    "patient_name": patient_name,
                    "mobile": int(mobile) if mobile.isdigit() else mobile,
                    "doctor_id": doctor_id,
                    "doctor_name": doctor_name,
                    "department": department,
                    "date": date_str,
                    "time": time_str,
                    "status": "Booked",
                    "created_at": created_at_str
                }
            },
            "errors": []
        }
