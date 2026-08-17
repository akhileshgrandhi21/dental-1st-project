import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.database import Base
from database.models import Doctor, Appointment, HospitalInfo
from services.doctor_service import DoctorService
from services.appointment_service import AppointmentService

def test_database_manager_enhanced():
    # Setup in-memory SQLite database
    engine = create_engine("sqlite:///:memory:")
    SessionClass = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionClass()
    
    try:
        # Seed test data
        doc1 = Doctor(
            doctor_id="D001",
            doctor_name="Dr. Rajesh Kumar",
            department="Cardiology",
            available_days="Mon,Tue,Wed,Fri",
            start_time="09:00",
            end_time="13:00",
            slot_duration=30
        )
        doc2 = Doctor(
            doctor_id="D002",
            doctor_name="Dr. Priya Sharma",
            department="Pediatrics",
            available_days="Mon-Sat",
            start_time="10:00",
            end_time="16:00",
            slot_duration=30
        )
        db.add(doc1)
        db.add(doc2)
        db.commit()

        doc_srv = DoctorService(db)
        appt_srv = AppointmentService(db)

        # 1. Test get_doctor_by_id
        d1 = doc_srv.get_doctor_by_id("D001")
        print("\n--- Doctor by ID (D001) ---")
        print(d1)
        assert d1 is not None
        assert d1["Doctor Name"] == "Dr. Rajesh Kumar"
        print("get_doctor_by_id test passed.")

        # 2. Test get_doctor_by_name
        doc_name_exact = doc_srv.get_doctor_by_name("Dr. Priya Sharma")
        print("\n--- Doctor by Name Exact (Dr. Priya Sharma) ---")
        print(doc_name_exact)
        assert doc_name_exact is not None
        assert doc_name_exact["Doctor ID"] == "D002"

        doc_name_norm = doc_srv.get_doctor_by_name("priya sharma")
        print("\n--- Doctor by Name Normalized (priya sharma) ---")
        print(doc_name_norm)
        assert doc_name_norm is not None
        assert doc_name_norm["Doctor ID"] == "D002"
        print("get_doctor_by_name tests passed.")

        # 3. Save appointment with fields (Department, Created At)
        new_appt = Appointment(
            appointment_id="APP-ENHANCED-001",
            patient_name="Alice Smith",
            mobile="9999999999",
            doctor_id="D003",
            doctor_name="Dr. Arjun Reddy",
            department="General Medicine",
            appointment_date="2026-08-05",
            appointment_time="11:30",
            status="Booked",
            created_at="2026-07-30 12:00:00"
        )
        db.add(new_appt)
        db.commit()
        print("\nSaved enhanced test appointment.")

        # 4. Get appointment by ID
        status_res = appt_srv.get_appointment_status(appointment_id="APP-ENHANCED-001")
        print("\n--- Saved Appointment Status ---")
        print(status_res)
        assert status_res["success"] is True
        saved_appt = status_res["data"]["appointments"][0]
        assert saved_appt["Patient Name"] == "Alice Smith"
        assert saved_appt["Department"] == "General Medicine"
        assert saved_appt["Created At"] is not None
        print("save_appointment and get_appointment_by_id tests passed.")

        # 5. Cancel (delete/soft delete) appointment
        cancel_res = appt_srv.cancel_appointment("APP-ENHANCED-001")
        print(f"\nCancel status response: {cancel_res}")
        assert cancel_res["success"] is True

        # 6. Verify cancelled
        status_res2 = appt_srv.get_appointment_status(appointment_id="APP-ENHANCED-001")
        assert status_res2["success"] is True
        cancelled_appt = status_res2["data"]["appointments"][0]
        assert cancelled_appt["Status"] == "Cancelled"
        assert cancelled_appt["Cancelled At"] is not None
        print("cancel_appointment test passed.")

        print("\nAll database manager tests passed successfully!")

    finally:
        db.close()

if __name__ == "__main__":
    test_database_manager_enhanced()
