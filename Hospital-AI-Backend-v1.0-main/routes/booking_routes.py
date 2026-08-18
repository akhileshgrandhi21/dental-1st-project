from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from services.availability_service import AvailabilityService
from services.booking_service import BookingService
from services.appointment_service import AppointmentService
from models.appointment import AppointmentCreate, AppointmentReschedule
from sqlalchemy.orm import Session
from database.database import get_db

router = APIRouter()

class AvailabilityRequest(BaseModel):
    doctor_id: Optional[str] = None
    doctor_name: Optional[str] = None
    date: str

class CancelRequest(BaseModel):
    appointment_id: str

def get_availability_service(db: Session = Depends(get_db)) -> AvailabilityService:
    return AvailabilityService(db)

def get_booking_service(db: Session = Depends(get_db), avail: AvailabilityService = Depends(get_availability_service)) -> BookingService:
    return BookingService(db, avail)

def get_appointment_service(db: Session = Depends(get_db), avail: AvailabilityService = Depends(get_availability_service)) -> AppointmentService:
    return AppointmentService(db, avail)

@router.post("/check-availability", summary="Check doctor slot availability")
def check_availability(req: AvailabilityRequest, avail: AvailabilityService = Depends(get_availability_service)):
    """Checks slots availability for a doctor on a specific date."""
    doctor_id = req.doctor_id
    if not doctor_id and req.doctor_name:
        from services.doctor_service import DoctorService
        doc_srv = DoctorService(avail.db)
        doc = doc_srv.get_doctor_by_name(req.doctor_name)
        if not doc:
            raise HTTPException(status_code=404, detail={
                "success": False,
                "message": "Doctor not found",
                "errors": [f"No doctor found matching name: '{req.doctor_name}'"]
            })
        doctor_id = doc["Doctor ID"]
    elif not doctor_id:
        raise HTTPException(status_code=400, detail={
            "success": False,
            "message": "Must provide either doctor_id or doctor_name",
            "errors": ["Missing doctor identifier."]
        })

    res = avail.get_available_slots(doctor_id, req.date)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail={
            "success": False,
            "message": res.get("message"),
            "errors": [res.get("message")]
        })
    return {
        "success": True,
        "message": f"Availability check completed for doctor ID {doctor_id}",
        "data": res,
        "errors": []
    }

@router.post("/book-appointment", summary="Book a new appointment")
def book_appointment(req: AppointmentCreate, booking_srv: BookingService = Depends(get_booking_service)):
    """Books a new appointment after validations and availability checks."""
    return booking_srv.book_appointment(req.model_dump())

@router.post("/cancel-appointment", summary="Cancel appointment")
def cancel_appointment(req: CancelRequest, appt_srv: AppointmentService = Depends(get_appointment_service)):
    """Cancels an existing appointment (soft-delete)."""
    return appt_srv.cancel_appointment(req.appointment_id)

@router.post("/reschedule-appointment", summary="Reschedule appointment")
def reschedule_appointment(req: AppointmentReschedule, appt_srv: AppointmentService = Depends(get_appointment_service)):
    """Reschedules an existing active appointment."""
    return appt_srv.reschedule_appointment(req.appointment_id, req.new_date, req.new_time, req.doctor_id, req.doctor_name)

@router.get("/appointment-status", summary="Search appointment status")
def get_appointment_status(
    appointment_id: Optional[str] = Query(None, description="Search by unique Appointment ID"),
    mobile: Optional[str] = Query(None, description="Search by registered Mobile Number"),
    appt_srv: AppointmentService = Depends(get_appointment_service)
):
    """Retrieves appointment state by Appointment ID or Mobile Number."""
    return appt_srv.get_appointment_status(appointment_id=appointment_id, mobile=mobile)
