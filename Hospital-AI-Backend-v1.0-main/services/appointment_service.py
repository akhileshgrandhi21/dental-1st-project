import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from database.models import Appointment, Doctor
from services.availability_service import AvailabilityService
from services.doctor_service import DoctorService
from utils.date_parser import parse_flexible_date, parse_flexible_time
from config import TIMEZONE, DEFAULT_START_TIME, DEFAULT_END_TIME

# Setup logging
logger = logging.getLogger(__name__)

class AppointmentService:
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

    def cancel_appointment(self, appointment_id: str) -> Dict[str, Any]:
        """
        Soft-deletes an appointment by setting its status to 'Cancelled' and setting
        the cancellation timestamp.
        """
        logger.info(f"Cancellation requested for Appointment ID: {appointment_id}")

        appt = self.db.query(Appointment).filter(Appointment.appointment_id == appointment_id).first()
        if not appt:
            logger.warning(f"Cancellation failed: Appointment {appointment_id} not found.")
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "Appointment not found",
                    "errors": [f"Appointment ID '{appointment_id}' does not exist."]
                }
            )

        if appt.status == "Cancelled":
            logger.warning(f"Cancellation failed: Appointment ID {appointment_id} is already cancelled.")
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "Appointment is already cancelled",
                    "errors": ["Cannot cancel an already cancelled appointment."]
                }
            )

        # Update appointment status in database
        timestamp = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")
        appt.status = "Cancelled"
        appt.cancelled_at = timestamp
        self.db.commit()

        logger.info(f"Successfully cancelled appointment {appointment_id}")
        return {
            "success": True,
            "message": "Appointment cancelled successfully.",
            "data": {
                "appointment_id": appointment_id,
                "status": "Cancelled",
                "cancelled_at": timestamp,
                "patient_name": appt.patient_name
            },
            "errors": []
        }

    def reschedule_appointment(
        self, 
        appointment_id: str, 
        new_date: str, 
        new_time: str,
        doctor_id_input: Optional[str] = None,
        doctor_name_input: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Updates target appointment's Date, Time, and optionally Doctor,
        verifying slot availability first. Supports flexible date and time parsing.
        """
        logger.info(f"Reschedule requested for Appointment ID {appointment_id} to '{new_date}' at '{new_time}'")

        appt = self.db.query(Appointment).filter(Appointment.appointment_id == appointment_id).first()
        if not appt:
            logger.warning(f"Reschedule failed: Appointment {appointment_id} not found.")
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "Appointment not found",
                    "errors": [f"Appointment ID '{appointment_id}' does not exist."]
                }
            )

        if appt.status == "Cancelled":
            logger.warning(f"Reschedule failed: Appointment {appointment_id} is already cancelled.")
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "Cannot reschedule a cancelled appointment",
                    "errors": ["Rescheduling cancelled appointments is disabled."]
                }
            )

        # Flexible Date parsing
        try:
            check_date = parse_flexible_date(new_date)
            normalized_new_date = check_date.strftime("%Y-%m-%d")
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": str(e),
                    "errors": [str(e)]
                }
            )

        # Past Date Validation using configured Timezone
        current_date_tz = datetime.now(ZoneInfo(TIMEZONE)).date()
        if check_date < current_date_tz:
            logger.warning(f"Reschedule validation failed: date {normalized_new_date} is in the past compared to today {current_date_tz}")
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": f"Cannot reschedule to a past date (Date: {normalized_new_date}).",
                    "errors": [f"Selected date '{normalized_new_date}' is prior to today's date '{current_date_tz.strftime('%Y-%m-%d')}'."]
                }
            )

        # Flexible Time parsing
        try:
            new_time_norm = parse_flexible_time(new_time)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": str(e),
                    "errors": [str(e)]
                }
            )

        # Check Closed Hospital Hours boundary
        if new_time_norm < DEFAULT_START_TIME or new_time_norm > DEFAULT_END_TIME:
            logger.warning(f"Reschedule validation failed: Selected time {new_time_norm} is outside hospital hours {DEFAULT_START_TIME}-{DEFAULT_END_TIME}")
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": f"Hospital is closed at {new_time_norm}. Hospital hours: {DEFAULT_START_TIME} to {DEFAULT_END_TIME}.",
                    "errors": [f"Selected slot time is outside the hospital operational window."]
                }
            )

        # Resolve doctor if provided in reschedule request
        doctor = None
        if doctor_id_input:
            doctor = self.db.query(Doctor).filter(Doctor.doctor_id == doctor_id_input).first()
            if not doctor:
                # Flexible lookup
                test_id_doc = self.doc_service.get_doctor_by_id(doctor_id_input)
                if test_id_doc:
                    doctor = self.db.query(Doctor).filter(Doctor.doctor_id == test_id_doc["Doctor ID"]).first()
        elif doctor_name_input:
            doctor = self.db.query(Doctor).filter(Doctor.doctor_name == doctor_name_input).first()
            if not doctor:
                matched_docs = self.doc_service.search_doctors(doctor_name_input)
                if matched_docs:
                    doctor = self.db.query(Doctor).filter(Doctor.doctor_id == matched_docs[0]["Doctor ID"]).first()
        
        if doctor:
            doctor_id = doctor.doctor_id
            doctor_name = doctor.doctor_name
        else:
            if doctor_id_input or doctor_name_input:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "success": False,
                        "message": "Doctor not found",
                        "errors": [f"No doctor found matching '{doctor_id_input or doctor_name_input}'"]
                    }
                )
            # Default to existing doctor
            doctor_id = appt.doctor_id
            doctor_name = appt.doctor_name

        current_date = appt.appointment_date
        current_time = self.normalize_time(appt.appointment_time)

        # If date, time, and doctor are identical, return success with no action
        if current_date == normalized_new_date and current_time == new_time_norm and appt.doctor_id == doctor_id:
            return {
                "success": True,
                "message": "Appointment rescheduled successfully.",
                "data": {
                    "appointment_id": appointment_id,
                    "old_slot": {"date": current_date, "time": current_time},
                    "new_slot": {"date": normalized_new_date, "time": new_time_norm},
                    "doctor_name": doctor_name
                },
                "errors": []
            }

        # Validate availability using AvailabilityService
        avail_res = self.avail.get_available_slots(doctor_id, normalized_new_date)
        if avail_res.get("status") == "error":
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": avail_res.get("message"),
                    "errors": [avail_res.get("message")]
                }
            )

        if avail_res.get("status") in ["unavailable", "fully_booked"]:
            msg = avail_res.get("message")
            logger.warning(f"Reschedule failed: doctor unavailable. Details: {msg}")
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

        available_slots = avail_res.get("available_slots", [])
        if new_time_norm not in available_slots:
            logger.warning(f"Reschedule failed: Slot {new_time_norm} is unavailable for {doctor_name} on {normalized_new_date}")
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": f"Selected time slot {new_time_norm} is unavailable.",
                    "errors": [f"Slot {new_time_norm} is already booked or outside doctor's work hours."],
                    "data": {
                        "available_slots": available_slots,
                        "next_available_date": avail_res.get("next_available_date")
                    }
                }
            )

        # Update reschedule coordinates in database
        appt.appointment_date = normalized_new_date
        appt.appointment_time = new_time_norm
        appt.doctor_id = doctor_id
        appt.doctor_name = doctor_name
        if doctor:
            appt.department = doctor.department
            
        appt.status = "Rescheduled"
        appt.updated_at = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")
        self.db.commit()

        logger.info(f"Successfully rescheduled appointment {appointment_id} to {normalized_new_date} {new_time_norm}")
        return {
            "success": True,
            "message": "Appointment rescheduled successfully.",
            "data": {
                "appointment_id": appointment_id,
                "old_slot": {
                    "date": current_date,
                    "time": current_time
                },
                "new_slot": {
                    "date": normalized_new_date,
                    "time": new_time_norm
                },
                "doctor_name": doctor_name
            },
            "errors": []
        }

    def get_appointment_status(self, appointment_id: Optional[str] = None, mobile: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieves appointment matching either specific ID or specific mobile.
        """
        if not appointment_id and not mobile:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "Must provide either appointment_id or mobile number query parameter.",
                    "errors": ["Missing search criteria."]
                }
            )

        query = self.db.query(Appointment)
        if appointment_id:
            query = query.filter(Appointment.appointment_id == appointment_id)
        if mobile:
            mobile_cleaned = self.normalize_mobile(mobile)
            query = query.filter(Appointment.mobile == mobile_cleaned)

        appts = query.all()
        mapped_appts = []
        for appt in appts:
            mapped_appts.append({
                "Appointment ID": appt.appointment_id,
                "Patient Name": appt.patient_name,
                "Mobile": int(appt.mobile) if appt.mobile.isdigit() else appt.mobile,
                "Doctor ID": appt.doctor_id,
                "Doctor Name": appt.doctor_name,
                "Department": appt.department,
                "Date": appt.appointment_date,
                "Time": appt.appointment_time,
                "Status": appt.status,
                "Created At": appt.created_at,
                "Updated At": appt.updated_at,
                "Cancelled At": appt.cancelled_at
            })

        if not mapped_appts:
            if appointment_id:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "success": False,
                        "message": "Appointment not found",
                        "errors": [f"No appointment found with ID: {appointment_id}"]
                    }
                )
            else:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "success": False,
                        "message": "No appointments found matching mobile",
                        "errors": [f"No appointments found matching the mobile number: {mobile}"]
                    }
                )

        # Sort matching appointments by Date and Time (reverse chronological)
        mapped_appts.sort(key=lambda x: (x.get("Date", ""), x.get("Time", "")), reverse=True)

        return {
            "success": True,
            "message": "Appointments retrieved successfully",
            "data": {
                "appointments": mapped_appts
            },
            "appointments": mapped_appts,
            "errors": []
        }
