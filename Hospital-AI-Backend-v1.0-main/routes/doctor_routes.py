import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database.database import get_db
from services.doctor_service import DoctorService
from services.hospital_service import HospitalService
from typing import List, Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get(
    "/doctors",
    summary="List all doctors",
    description="Retrieves a complete list of all doctors along with their departments and schedules.",
    response_description="A list of available doctor profiles."
)
def get_doctors(db: Session = Depends(get_db)):
    try:
        service = DoctorService(db)
        doctors = service.get_doctors()
        return {
            "success": True,
            "message": "Doctors retrieved successfully",
            "data": doctors,
            "errors": []
        }
    except Exception as e:
        logger.error(f"Error fetching doctors: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to retrieve doctors",
                "errors": [str(e)]
            }
        )

@router.get(
    "/hospital-info",
    summary="Get hospital details",
    description="Retrieves metadata about the hospital, such as address, phone number, and operating hours.",
    response_description="Hospital contact and schedule details."
)
def get_hospital_info(db: Session = Depends(get_db)):
    try:
        service = HospitalService(db)
        info = service.get_hospital_info()
        return {
            "success": True,
            "message": "Hospital info retrieved successfully",
            "data": info,
            "errors": []
        }
    except Exception as e:
        logger.error(f"Error fetching hospital info: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to retrieve hospital info",
                "errors": [str(e)]
            }
        )

@router.get(
    "/search-doctors",
    summary="Search doctors by query",
    description="Searches for doctors flexibly by partial name, department, or specialization synonyms (e.g. 'pediatrician', 'physician', 'cardiologist').",
    response_description="A list of matched doctor profiles containing ID, Name, and Department."
)
def search_doctors(
    query: str = Query(..., min_length=1, description="Search query string (e.g., 'rajesh', 'child doctor')"),
    db: Session = Depends(get_db)
):
    try:
        service = DoctorService(db)
        matched_docs = service.search_doctors(query)
        # Format list to return ID, Name, and Department as specified in requirements
        formatted_docs = []
        for doc in matched_docs:
            formatted_docs.append({
                "doctor_id": doc["Doctor ID"],
                "doctor_name": doc["Doctor Name"],
                "department": doc["Department"]
            })
            
        logger.info(f"Doctor search completed for query '{query}': {len(formatted_docs)} matches found")
        return {
            "success": True,
            "message": "Doctors searched successfully",
            "data": formatted_docs,
            "errors": []
        }
    except Exception as e:
        logger.error(f"Error during doctor search: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to search doctors",
                "errors": [str(e)]
            }
        )

@router.get(
    "/departments",
    summary="List all departments",
    description="Retrieves a list of all distinct departments present in the hospital configuration.",
    response_description="A list of department names."
)
def get_departments(db: Session = Depends(get_db)):
    try:
        service = DoctorService(db)
        docs = service.get_doctors()
        # Extract unique departments
        departments = sorted(list(set(doc["Department"] for doc in docs if doc.get("Department"))))
        return {
            "success": True,
            "message": "Departments retrieved successfully",
            "data": departments,
            "errors": []
        }
    except Exception as e:
        logger.error(f"Error fetching departments: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Failed to retrieve departments",
                "errors": [str(e)]
            }
        )

@router.get(
    "/doctors-by-department/{department}",
    summary="Get doctors in department",
    description="Retrieves all doctor profiles working in the specified department.",
    response_description="A list of doctor profiles in the department."
)
def get_doctors_by_department(department: str, db: Session = Depends(get_db)):
    try:
        service = DoctorService(db)
        docs = service.get_doctors()
        # Filter by department case-insensitively
        filtered_docs = [
            doc for doc in docs 
            if doc.get("Department") and doc["Department"].lower() == department.strip().lower()
        ]
        
        logger.info(f"Retrieved {len(filtered_docs)} doctors for department '{department}'")
        return {
            "success": True,
            "message": "Doctors by department retrieved successfully",
            "data": filtered_docs,
            "errors": []
        }
    except Exception as e:
        logger.error(f"Error fetching doctors by department: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": f"Failed to retrieve doctors for department: {department}",
                "errors": [str(e)]
            }
        )
