from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional


from services.availability_service import AvailabilityService
from services.booking_service import BookingService
from services.appointment_service import AppointmentService
from models.appointment import AppointmentCreate, AppointmentReschedule

router = APIRouter()

# Request schemas for simple POST requests
class AvailabilityRequest(BaseModel):
    doctor_id: str
    date: str

class CancelRequest(BaseModel):
    appointment_id: str

from sqlalchemy.orm import Session
from database.database import get_db

# Dependencies
def get_availability_service(db: Session = Depends(get_db)) -> AvailabilityService:
    return AvailabilityService(db)

def get_booking_service(db: Session = Depends(get_db), avail: AvailabilityService = Depends(get_availability_service)) -> BookingService:
    return BookingService(db, avail)

def get_appointment_service(db: Session = Depends(get_db), avail: AvailabilityService = Depends(get_availability_service)) -> AppointmentService:
    return AppointmentService(db, avail)



@router.post(
    "/check-availability",
    summary="Check doctor slot availability",
    description="Calculates and lists all available slots for a doctor on a specific date. Supports searching by doctor name or ID, suggesting next available slot dates if fully booked or unavailable.",
    response_description="Availability check results with lists of active slots."
)
def check_availability(req: AvailabilityRequest, avail: AvailabilityService = Depends(get_availability_service)):
    """Checks slots availability for a doctor on a specific date."""
    doctor_id = req.doctor_id
    if not doctor_id and req.doctor_name:
        from services.doctor_service import DoctorService
        doc_srv = DoctorService(avail.db)
        doc = doc_srv.get_doctor_by_name(req.doctor_name)
        if not doc:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "Doctor not found",
                    "errors": [f"No doctor found matching name: '{req.doctor_name}'"]
                }
            )
        doctor_id = doc["Doctor ID"]
    elif not doctor_id and not req.doctor_name:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": "Must provide either doctor_id or doctor_name",
                "errors": ["Missing doctor identifier."]
            }
        )

    res = avail.get_available_slots(doctor_id, req.date)
    if res.get("status") == "error":
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": res.get("message"),
                "errors": [res.get("message")]
            }
        )
    return {
        "success": True,
        "message": f"Availability check completed for doctor ID {doctor_id}",
        "data": res,
        "errors": []
    }

@router.post(
    "/book-appointment",
    summary="Book a new appointment",
    description="Validates inputs, checks doctor availability, and books a new appointment. Prevents duplicate booking conflicts.",
    response_description="Standardized booking confirmation detail."
)
def book_appointment(req: AppointmentCreate, booking_srv: BookingService = Depends(get_booking_service)):
    """Books a new appointment after validations and availability checks."""
    booking_data = req.model_dump()
    return booking_srv.book_appointment(booking_data)

@router.post(
    "/cancel-appointment",
    summary="Cancel appointment",
    description="Cancels an existing active appointment by setting its status to Cancelled.",
    response_description="Standardized cancellation status details."
)
def cancel_appointment(req: CancelRequest, appt_srv: AppointmentService = Depends(get_appointment_service)):
    """Cancels an existing appointment (soft-delete)."""
    return appt_srv.cancel_appointment(req.appointment_id)

@router.post(
    "/reschedule-appointment",
    summary="Reschedule appointment",
    description="Updates date and time parameters for an existing booking, validating target doctor slot conflict limitations.",
    response_description="Standardized rescheduling result."
)
def reschedule_appointment(req: AppointmentReschedule, appt_srv: AppointmentService = Depends(get_appointment_service)):
    """Reschedules an existing active appointment."""
    return appt_srv.reschedule_appointment(
        req.appointment_id, 
        req.new_date, 
        req.new_time, 
        req.doctor_id, 
        req.doctor_name
    )

@router.get(
    "/appointment-status",
    summary="Search appointment status",
    description="Retrieves status and details for appointments matching either specific ID or registered mobile phone.",
    response_description="Standardized status queries lists."
)
def get_appointment_status(
    appointment_id: Optional[str] = Query(None, description="Search by unique Appointment ID"),
    mobile: Optional[str] = Query(None, description="Search by registered Mobile Number"),
    appt_srv: AppointmentService = Depends(get_appointment_service)
):
    """Retrieves appointment state by Appointment ID or Mobile Number."""
    return appt_srv.get_appointment_status(appointment_id=appointment_id, mobile=mobile)
