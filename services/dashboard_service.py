import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List, Optional
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from database.models import Doctor, Appointment, HospitalInfo
from config import TIMEZONE

logger = logging.getLogger(__name__)

class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def get_stats(self) -> Dict[str, int]:
        """
        Calculates metric statistics for the admin dashboard panel dashboard,
        including live patient count and revenue estimates.
        """
        tz = ZoneInfo(TIMEZONE)
        today_str = datetime.now(tz).strftime("%Y-%m-%d")

        try:
            # 1. Today's Appointments (status is not Cancelled and date is today)
            today_count = self.db.query(Appointment).filter(
                Appointment.appointment_date == today_str,
                Appointment.status != "Cancelled"
            ).count()

            # 2. Upcoming Appointments (status is not Cancelled and date is in the future)
            upcoming_count = self.db.query(Appointment).filter(
                Appointment.appointment_date > today_str,
                Appointment.status != "Cancelled"
            ).count()

            # 3. Cancelled Appointments (status is Cancelled)
            cancelled_count = self.db.query(Appointment).filter(
                Appointment.status == "Cancelled"
            ).count()

            # 4. Completed Appointments (status is Completed, or active and date is in the past)
            completed_count = self.db.query(Appointment).filter(
                or_(
                    Appointment.status == "Completed",
                    (Appointment.status != "Cancelled") & (Appointment.appointment_date < today_str)
                )
            ).count()

            # 5. Total Doctors
            total_doctors = self.db.query(Doctor).count()

            # 6. Total Unique Patients (based on unique mobile numbers)
            total_patients = self.db.query(Appointment.mobile).distinct().count()

            # 7. Estimated Revenue (Placeholder: $100 per completed booking)
            active_count = self.db.query(Appointment).filter(Appointment.status != "Cancelled").count()
            revenue = active_count * 100

            logger.info(f"Dashboard stats calculated: today={today_count}, upcoming={upcoming_count}, cancelled={cancelled_count}, completed={completed_count}, doctors={total_doctors}, patients={total_patients}, revenue={revenue}")

            return {
                "today_appointments": today_count,
                "upcoming_appointments": upcoming_count,
                "cancelled_appointments": cancelled_count,
                "completed_appointments": completed_count,
                "total_doctors": total_doctors,
                "total_patients": total_patients,
                "estimated_revenue": revenue
            }
        except Exception as e:
            logger.error(f"Error computing dashboard stats: {e}", exc_info=True)
            raise e

    def get_paginated_appointments(
        self, 
        page: int = 1, 
        limit: int = 10, 
        status: Optional[str] = None, 
        doctor_id: Optional[str] = None, 
        date: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieves paginated, filtered, and sorted appointments list.
        """
        try:
            query = self.db.query(Appointment)

            # Apply Filters
            if status:
                query = query.filter(Appointment.status == status)
            if doctor_id:
                query = query.filter(Appointment.doctor_id == doctor_id)
            if date:
                query = query.filter(Appointment.appointment_date == date)
            if search:
                search_term = f"%{search.strip()}%"
                query = query.filter(
                    or_(
                        Appointment.patient_name.ilike(search_term),
                        Appointment.mobile.ilike(search_term),
                        Appointment.appointment_id.ilike(search_term),
                        Appointment.doctor_name.ilike(search_term)
                    )
                )

            # Calculate total match count
            total = query.count()

            # Order by date desc, time desc, created_at desc (newest first)
            query = query.order_by(
                Appointment.appointment_date.desc(),
                Appointment.appointment_time.desc(),
                Appointment.created_at.desc()
            )

            # Apply pagination offset limits
            offset = (page - 1) * limit
            appointments = query.offset(offset).limit(limit).all()

            # Map to response shape
            mapped_appointments = []
            for appt in appointments:
                mapped_appointments.append({
                    "appointment_id": appt.appointment_id,
                    "patient_name": appt.patient_name,
                    "mobile": int(appt.mobile) if appt.mobile.isdigit() else appt.mobile,
                    "doctor_name": appt.doctor_name,
                    "department": appt.department,
                    "appointment_date": appt.appointment_date,
                    "appointment_time": appt.appointment_time,
                    "status": appt.status,
                    "created_at": appt.created_at
                })

            total_pages = (total + limit - 1) // limit if total > 0 else 0

            return {
                "appointments": mapped_appointments,
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": total_pages
            }
        except Exception as e:
            logger.error(f"Error querying paginated appointments: {e}", exc_info=True)
            raise e

    def get_appointment_detail(self, appointment_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the complete data fields for a single appointment model.
        """
        appt = self.db.query(Appointment).filter(Appointment.appointment_id == appointment_id).first()
        if not appt:
            return None
        return {
            "appointment_id": appt.appointment_id,
            "patient_name": appt.patient_name,
            "mobile": int(appt.mobile) if appt.mobile.isdigit() else appt.mobile,
            "doctor_id": appt.doctor_id,
            "doctor_name": appt.doctor_name,
            "department": appt.department,
            "appointment_date": appt.appointment_date,
            "appointment_time": appt.appointment_time,
            "status": appt.status,
            "created_at": appt.created_at,
            "updated_at": appt.updated_at,
            "cancelled_at": appt.cancelled_at
        }

    def get_doctors(self) -> List[Dict[str, Any]]:
        """
        Returns the doctors directory schedules.
        """
        docs = self.db.query(Doctor).all()
        return [{
            "doctor_id": doc.doctor_id,
            "doctor_name": doc.doctor_name,
            "department": doc.department,
            "available_days": doc.available_days,
            "start_time": doc.start_time,
            "end_time": doc.end_time,
            "slot_duration": doc.slot_duration
        } for doc in docs]

    def get_recent_appointments(self) -> List[Dict[str, Any]]:
        """
        Retrieves the last 10 booked appointments.
        """
        try:
            appts = self.db.query(Appointment).order_by(
                Appointment.created_at.desc(),
                Appointment.appointment_date.desc(),
                Appointment.appointment_time.desc()
            ).limit(10).all()

            return [{
                "appointment_id": a.appointment_id,
                "patient_name": a.patient_name,
                "mobile": int(a.mobile) if a.mobile.isdigit() else a.mobile,
                "doctor_name": a.doctor_name,
                "department": a.department,
                "appointment_date": a.appointment_date,
                "appointment_time": a.appointment_time,
                "status": a.status,
                "created_at": a.created_at
            } for a in appts]
        except Exception as e:
            logger.error(f"Error querying recent appointments: {e}", exc_info=True)
            raise e

    def get_unique_patients(self, page: int = 1, limit: int = 10, search: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieves unique patients list grouped by name and mobile.
        """
        tz = ZoneInfo(TIMEZONE)
        today_str = datetime.now(tz).strftime("%Y-%m-%d")

        try:
            query = self.db.query(
                Appointment.patient_name,
                Appointment.mobile,
                func.count(Appointment.appointment_id).label("total_appointments"),
                func.max(Appointment.appointment_date).label("last_visit")
            ).group_by(Appointment.patient_name, Appointment.mobile)

            if search:
                search_term = f"%{search.strip()}%"
                query = query.filter(
                    or_(
                        Appointment.patient_name.ilike(search_term),
                        Appointment.mobile.ilike(search_term)
                    )
                )

            subq = query.subquery()
            total = self.db.query(func.count()).select_from(subq).scalar() or 0
            query = query.order_by(func.max(Appointment.appointment_date).desc())

            offset = (page - 1) * limit
            results = query.offset(offset).limit(limit).all()

            patients = []
            for r in results:
                p_name, p_mobile, count, last_visit = r
                
                has_active = self.db.query(Appointment).filter(
                    Appointment.patient_name == p_name,
                    Appointment.mobile == p_mobile,
                    Appointment.status != "Cancelled",
                    Appointment.appointment_date >= today_str
                ).first() is not None

                patients.append({
                    "patient_name": p_name,
                    "mobile": int(p_mobile) if p_mobile.isdigit() else p_mobile,
                    "total_appointments": count,
                    "last_visit": last_visit,
                    "status": "Active" if has_active else "Regular"
                })

            total_pages = (total + limit - 1) // limit if total > 0 else 0

            return {
                "patients": patients,
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": total_pages
            }
        except Exception as e:
            logger.error(f"Error querying patients: {e}", exc_info=True)
            raise e

    def delete_patient(self, patient_name: str, mobile: str) -> bool:
        """
        Physically deletes all appointments matching the patient's name and mobile
        from PostgreSQL (Supabase) so they disappear completely.
        """
        try:
            # Query count to verify existence
            count = self.db.query(Appointment).filter(
                Appointment.patient_name == patient_name,
                Appointment.mobile == mobile
            ).count()

            if count == 0:
                logger.warning(f"No appointments found to delete for patient '{patient_name}' and mobile '{mobile}'")
                return False

            # Perform physical delete (db.delete)
            self.db.query(Appointment).filter(
                Appointment.patient_name == patient_name,
                Appointment.mobile == mobile
            ).delete(synchronize_session=False)

            self.db.commit()
            logger.info(f"Successfully physically deleted {count} appointment(s) for patient '{patient_name}' from Supabase.")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting patient appointments: {e}", exc_info=True)
            raise e

    def create_doctor(self, doctor_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Registers a new doctor profile, auto-generating a unique sequential Dxxx ID if not provided.
        """
        doc_id = doctor_data.get("doctor_id")
        
        # Auto generate doctor ID if blank
        if not doc_id:
            docs = self.db.query(Doctor.doctor_id).all()
            max_num = 0
            for d_tuple in docs:
                d_id = d_tuple[0]
                if d_id.startswith("D"):
                    try:
                        num = int(d_id[1:])
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        pass
            doc_id = f"D{max_num + 1:03d}"

        try:
            new_doc = Doctor(
                doctor_id=doc_id,
                doctor_name=doctor_data.get("doctor_name"),
                department=doctor_data.get("department"),
                available_days=doctor_data.get("available_days"),
                start_time=doctor_data.get("start_time"),
                end_time=doctor_data.get("end_time"),
                slot_duration=int(doctor_data.get("slot_duration", 30))
            )
            self.db.add(new_doc)
            self.db.commit()
            logger.info(f"Successfully registered new doctor {doc_id} - {new_doc.doctor_name}")
            return {
                "doctor_id": new_doc.doctor_id,
                "doctor_name": new_doc.doctor_name,
                "department": new_doc.department,
                "available_days": new_doc.available_days,
                "start_time": new_doc.start_time,
                "end_time": new_doc.end_time,
                "slot_duration": new_doc.slot_duration
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error registering new doctor profile: {e}")
            raise e

    def update_doctor(self, doctor_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Updates details of an existing doctor schedule profile.
        """
        doc_id = doctor_data.get("doctor_id")
        doc = self.db.query(Doctor).filter(Doctor.doctor_id == doc_id).first()
        if not doc:
            return None

        try:
            doc.doctor_name = doctor_data.get("doctor_name", doc.doctor_name)
            doc.department = doctor_data.get("department", doc.department)
            doc.available_days = doctor_data.get("available_days", doc.available_days)
            doc.start_time = doctor_data.get("start_time", doc.start_time)
            doc.end_time = doctor_data.get("end_time", doc.end_time)
            doc.slot_duration = int(doctor_data.get("slot_duration", doc.slot_duration))
            
            self.db.commit()
            logger.info(f"Successfully updated doctor {doc_id} profile details.")
            return {
                "doctor_id": doc.doctor_id,
                "doctor_name": doc.doctor_name,
                "department": doc.department,
                "available_days": doc.available_days,
                "start_time": doc.start_time,
                "end_time": doc.end_time,
                "slot_duration": doc.slot_duration
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating doctor {doc_id} details: {e}")
            raise e

    def delete_doctor(self, doctor_id: str) -> bool:
        """
        Physically deletes a doctor profile and cascades physical deletion to all associated appointments.
        """
        doc = self.db.query(Doctor).filter(Doctor.doctor_id == doctor_id).first()
        if not doc:
            return False

        try:
            # Physically delete all appointments associated with this doctor first
            self.db.query(Appointment).filter(
                Appointment.doctor_id == doctor_id
            ).delete(synchronize_session=False)

            # Physically remove the doctor profile row
            self.db.delete(doc)
            self.db.commit()
            logger.info(f"Successfully physically deleted doctor {doctor_id} and all associated appointments from Supabase.")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting doctor {doctor_id}: {e}")
            raise e

    def update_hospital_info(self, info_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates hospital metadata keys in the HospitalInfo database table.
        """
        try:
            for key, value in info_data.items():
                row = self.db.query(HospitalInfo).filter(HospitalInfo.key == key).first()
                if row:
                    row.value = str(value)
                else:
                    self.db.add(HospitalInfo(key=key, value=str(value)))
            
            self.db.commit()
            logger.info("Successfully updated hospital settings configurations.")
            return info_data
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating hospital configuration keys: {e}")
            raise e
