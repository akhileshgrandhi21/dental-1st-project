import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app import app
from database.database import Base, get_db

def test_patient_dashboard_endpoints():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.models import Doctor, Appointment
    import os

    # Clean up test DB file if left over
    if os.path.exists("test_patient_dashboard.db"):
        try:
            os.remove("test_patient_dashboard.db")
        except Exception:
            pass

    engine = create_engine("sqlite:///test_patient_dashboard.db", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Build tables
    Base.metadata.create_all(bind=engine)
    
    # Seed initial test data
    db = TestingSessionLocal()
    try:
        # Seed a doctor
        db.add(Doctor(doctor_id="D001", doctor_name="Dr. Rajesh Kumar", department="Cardiology", available_days="Mon,Tue", start_time="09:00", end_time="13:00", slot_duration=30))
        
        # Calculate dynamic dates
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        from config import TIMEZONE
        
        today_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")
        upcoming_str = (datetime.now(ZoneInfo(TIMEZONE)) + timedelta(days=2)).strftime("%Y-%m-%d")
        past_str = (datetime.now(ZoneInfo(TIMEZONE)) - timedelta(days=2)).strftime("%Y-%m-%d")

        # Seed 3 appointments for patient David (2 Booked, 1 Rescheduled)
        # Seed 1 appointment for patient Alice (Booked)
        appts = [
            # Patient David (mobile: 9998887776)
            {
                "appointment_id": "APT-000001",
                "patient_name": "David",
                "mobile": "9998887776",
                "doctor_id": "D001",
                "doctor_name": "Dr. Rajesh Kumar",
                "department": "Cardiology",
                "appointment_date": past_str,
                "appointment_time": "10:00",
                "status": "Booked",
                "created_at": "2026-08-02 12:00:00"
            },
            {
                "appointment_id": "APT-000002",
                "patient_name": "David",
                "mobile": "9998887776",
                "doctor_id": "D001",
                "doctor_name": "Dr. Rajesh Kumar",
                "department": "Cardiology",
                "appointment_date": past_str,
                "appointment_time": "11:00",
                "status": "Rescheduled",
                "created_at": "2026-08-02 12:01:00"
            },
            # Patient Alice (mobile: 8888888888)
            {
                "appointment_id": "APT-000003",
                "patient_name": "Alice",
                "mobile": "8888888888",
                "doctor_id": "D001",
                "doctor_name": "Dr. Rajesh Kumar",
                "department": "Cardiology",
                "appointment_date": upcoming_str,
                "appointment_time": "11:30",
                "status": "Booked",
                "created_at": "2026-08-02 12:05:00"
            }
        ]
        for appt in appts:
            db.add(Appointment(**appt))
        
        db.commit()
    finally:
        db.close()

    # Dependency override
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        # 1. Test GET /api/v1/dashboard/patients
        print("\n--- 1. Testing GET /api/v1/dashboard/patients ---")
        res = client.get("/api/v1/dashboard/patients")
        print("Patients list response:", res.json())
        assert res.status_code == 200
        assert res.json()["success"] is True
        
        patients = res.json()["data"]["patients"]
        assert len(patients) == 2  # Alice and David
        
        # Verify fields and sorting (David has last visit 2026-08-04, Alice has 2026-08-05. So Alice is first, David is second)
        assert patients[0]["patient_name"] == "Alice"
        assert patients[0]["total_appointments"] == 1
        assert patients[1]["patient_name"] == "David"
        assert patients[1]["total_appointments"] == 2

        # 2. Test search Patients list
        print("\n--- 2. Testing search on unique patients list ---")
        res_search = client.get("/api/v1/dashboard/patients?search=David")
        print("Search Patients response:", res_search.json())
        assert len(res_search.json()["data"]["patients"]) == 1
        assert res_search.json()["data"]["patients"][0]["patient_name"] == "David"

        # 3. Test DELETE /api/v1/dashboard/patient (soft delete)
        print("\n--- 3. Testing DELETE /api/v1/dashboard/patient ---")
        res_delete = client.delete("/api/v1/dashboard/patient?patient_name=David&mobile=9998887776")
        print("Delete patient response:", res_delete.json())
        assert res_delete.status_code == 200
        assert res_delete.json()["success"] is True

        # Verify that David's appointments are physically deleted from the database
        db_check = TestingSessionLocal()
        try:
            david_appts = db_check.query(Appointment).filter(
                Appointment.patient_name == "David",
                Appointment.mobile == "9998887776"
            ).all()
            assert len(david_appts) == 0
        finally:
            db_check.close()

        # 4. Verify stats count updates correctly
        print("\n--- 4. Verify dashboard stats reflect the deletions ---")
        res_stats = client.get("/api/v1/dashboard/stats")
        print("Dashboard stats after deletion response:", res_stats.json())
        data = res_stats.json()["data"]
        # David's 2 appointments are physically deleted, so cancelled_appointments should be 0.
        # Alice's 1 appointment is booked, so upcoming_appointments should be 1.
        assert data["cancelled_appointments"] == 0
        assert data["upcoming_appointments"] == 1
        # Patient count should be 1 (David's appointments are physically deleted, so only Alice remains in history).
        assert data["total_patients"] == 1
        # Estimated revenue should only count active bookings: Alice (1) * $100 = $100.
        assert data["estimated_revenue"] == 100

        print("\nAll Patient Dashboard REST APIs tests passed successfully!")

    finally:
        app.dependency_overrides.clear()
        if os.path.exists("test_patient_dashboard.db"):
            try:
                os.remove("test_patient_dashboard.db")
            except Exception:
                pass

if __name__ == "__main__":
    test_patient_dashboard_endpoints()
