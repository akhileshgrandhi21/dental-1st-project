import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database.database import get_db
from services.dashboard_service import DashboardService
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard")

# Dependency
def get_dashboard_service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(db)

@router.get(
    "/stats",
    summary="Get dashboard statistics",
    description="Returns aggregate counts for today's active appointments, upcoming, cancelled, completed, and total doctors.",
    response_description="Dashboard counters metadata map."
)
def get_stats(service: DashboardService = Depends(get_dashboard_service)):
    try:
        stats = service.get_stats()
        return {
            "success": True,
            "message": "Dashboard stats retrieved successfully",
            "data": stats,
            "errors": []
        }
    except Exception as e:
        logger.error(f"Failed to retrieve dashboard stats: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to retrieve dashboard stats",
                "errors": [str(e)]
            }
        )

@router.get(
    "/appointments",
    summary="List paginated appointments",
    description="Retrieves sorted, filtered, and paginated appointments. Supports searching and date/doctor filtering.",
    response_description="Paginated list of appointment records."
)
def get_appointments(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Records per page"),
    status: Optional[str] = Query(None, description="Filter by status (e.g. Booked, Rescheduled, Cancelled)"),
    doctor_id: Optional[str] = Query(None, description="Filter by Doctor ID"),
    date: Optional[str] = Query(None, description="Filter by Date (YYYY-MM-DD)"),
    search: Optional[str] = Query(None, description="Search term for patient name, mobile, or ID"),
    service: DashboardService = Depends(get_dashboard_service)
):
    try:
        res = service.get_paginated_appointments(
            page=page, 
            limit=limit, 
            status=status, 
            doctor_id=doctor_id, 
            date=date, 
            search=search
        )
        return {
            "success": True,
            "message": "Appointments retrieved successfully",
            "data": res,
            "errors": []
        }
    except Exception as e:
        logger.error(f"Failed to query paginated appointments: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to query appointments list",
                "errors": [str(e)]
            }
        )

@router.get(
    "/appointment/{appointment_id}",
    summary="Get complete appointment details",
    description="Retrieves the detailed record values of a single appointment.",
    response_description="A complete appointment profile record."
)
def get_appointment_detail(
    appointment_id: str,
    service: DashboardService = Depends(get_dashboard_service)
):
    try:
        appt = service.get_appointment_detail(appointment_id)
        if not appt:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "Appointment not found",
                    "errors": [f"No appointment found with ID: '{appointment_id}'"]
                }
            )
        return {
            "success": True,
            "message": "Appointment details retrieved successfully",
            "data": appt,
            "errors": []
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve appointment details: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to retrieve appointment details",
                "errors": [str(e)]
            }
        )

@router.get(
    "/doctors",
    summary="Get all dashboard doctors",
    description="Retrieves a list of all active doctor profiles for schedule configurations.",
    response_description="List of available doctors."
)
def get_doctors(service: DashboardService = Depends(get_dashboard_service)):
    try:
        doctors = service.get_doctors()
        return {
            "success": True,
            "message": "Doctors list retrieved successfully",
            "data": doctors,
            "errors": []
        }
    except Exception as e:
        logger.error(f"Failed to retrieve doctors list: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to retrieve doctors list",
                "errors": [str(e)]
            }
        )

@router.get(
    "/recent",
    summary="Get recently booked appointments",
    description="Retrieves the last 10 booked appointments in descending chronological order.",
    response_description="List of recent appointment records."
)
def get_recent(service: DashboardService = Depends(get_dashboard_service)):
    try:
        recent = service.get_recent_appointments()
        return {
            "success": True,
            "message": "Recent appointments retrieved successfully",
            "data": recent,
            "errors": []
        }
    except Exception as e:
        logger.error(f"Failed to retrieve recent appointments: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to retrieve recent appointments",
                "errors": [str(e)]
            }
        )

@router.get(
    "/patients",
    summary="Get unique patients directory list",
    description="Retrieves sorted, paginated list of unique patients matching name or mobile search patterns.",
    response_description="Paginated list of patient profiles."
)
def get_patients(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Records per page"),
    search: Optional[str] = Query(None, description="Search pattern (name or mobile)"),
    service: DashboardService = Depends(get_dashboard_service)
):
    try:
        res = service.get_unique_patients(page=page, limit=limit, search=search)
        return {
            "success": True,
            "message": "Patients list retrieved successfully",
            "data": res,
            "errors": []
        }
    except Exception as e:
        logger.error(f"Failed to retrieve patients list: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to retrieve unique patients list",
                "errors": [str(e)]
            }
        )

@router.delete(
    "/patient",
    summary="Soft delete a patient",
    description="Cancels all active bookings under the given patient name and contact mobile.",
    response_description="Successful patient deletion state."
)
def delete_patient(
    patient_name: str = Query(..., description="Full patient name"),
    mobile: str = Query(..., description="Patient mobile number"),
    service: DashboardService = Depends(get_dashboard_service)
):
    try:
        success = service.delete_patient(patient_name=patient_name, mobile=mobile)
        if not success:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "Patient not found",
                    "errors": [f"No appointments found to cancel for patient '{patient_name}' with mobile '{mobile}'"]
                }
            )
        return {
            "success": True,
            "message": f"Successfully deleted patient '{patient_name}' and cancelled all associated appointments.",
            "data": {},
            "errors": []
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete patient: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to perform patient deletion",
                "errors": [str(e)]
            }
        )

# Pydantic models for admin updates
from pydantic import BaseModel, Field

class DoctorUpdate(BaseModel):
    doctor_id: str = Field(..., description="Unique Doctor ID")
    doctor_name: Optional[str] = Field(None, description="Doctor name")
    department: Optional[str] = Field(None, description="Specialty department")
    available_days: Optional[str] = Field(None, description="Days available (e.g. Mon-Fri)")
    start_time: Optional[str] = Field(None, description="Start timing (HH:MM)")
    end_time: Optional[str] = Field(None, description="End timing (HH:MM)")
    slot_duration: Optional[int] = Field(None, description="Consultation slot length")

class HospitalInfoUpdate(BaseModel):
    hospital_name: Optional[str] = Field(None, alias="Hospital Name")
    opening_time: Optional[str] = Field(None, alias="Opening Time")
    closing_time: Optional[str] = Field(None, alias="Closing Time")
    emergency: Optional[str] = Field(None, alias="Emergency")
    phone: Optional[str] = Field(None, alias="Phone")
    address: Optional[str] = Field(None, alias="Address")
    insurance: Optional[str] = Field(None, alias="Insurance")

    model_config = {
        "populate_by_name": True
    }

@router.put(
    "/doctor",
    summary="Update doctor details",
    description="Allows administrator to modify timing schedules, working days, or names of a doctor profile.",
    response_description="Updated doctor record details."
)
def update_doctor(
    payload: DoctorUpdate,
    service: DashboardService = Depends(get_dashboard_service)
):
    try:
        updated = service.update_doctor(payload.model_dump(exclude_none=True))
        if not updated:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "Doctor not found",
                    "errors": [f"No doctor found with ID: '{payload.doctor_id}'"]
                }
            )
        return {
            "success": True,
            "message": "Doctor details updated successfully.",
            "data": updated,
            "errors": []
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update doctor: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to update doctor details",
                "errors": [str(e)]
            }
        )

@router.delete(
    "/doctor/{doctor_id}",
    summary="Delete doctor profile",
    description="Removes doctor profile from system and cancels all their booked appointments.",
    response_description="Successful deletion response."
)
def delete_doctor(
    doctor_id: str,
    service: DashboardService = Depends(get_dashboard_service)
):
    try:
        success = service.delete_doctor(doctor_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "message": "Doctor not found",
                    "errors": [f"No doctor profile found with ID: '{doctor_id}'"]
                }
            )
        return {
            "success": True,
            "message": f"Successfully deleted doctor '{doctor_id}' and cancelled all associated appointments.",
            "data": {},
            "errors": []
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete doctor {doctor_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to perform doctor deletion",
                "errors": [str(e)]
            }
        )

@router.put(
    "/hospital-info",
    summary="Update hospital info settings",
    description="Allows administrator to modify hospital metadata keys (address, hours, emergency contact, name).",
    response_description="Updated hospital configurations."
)
def update_hospital_info(
    payload: HospitalInfoUpdate,
    service: DashboardService = Depends(get_dashboard_service)
):
    try:
        data_dict = payload.model_dump(by_alias=True, exclude_none=True)
        updated = service.update_hospital_info(data_dict)
        return {
            "success": True,
            "message": "Hospital configurations updated successfully.",
            "data": updated,
            "errors": []
        }
    except Exception as e:
        logger.error(f"Failed to update hospital info settings: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to update hospital config settings",
                "errors": [str(e)]
            }
        )
