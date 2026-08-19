import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app import app
from database.database import Base, get_db

def test_dashboard_endpoints():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.models import Doctor, Appointment, HospitalInfo
    
    # Clean up test DB file if left over
    import os
    if os.path.exists("test_dashboard.db"):
        try:
            os.remove("test_dashboard.db")
        except Exception:
            pass

    engine = create_engine("sqlite:///test_dashboard.db", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Build tables
    Base.metadata.create_all(bind=engine)
    
    # Seed initial test data
    db = TestingSessionLocal()
    try:
        # Seed 3 Doctors
        doc_data = [
            {"doctor_id": "D001", "doctor_name": "Dr. Rajesh Kumar", "department": "Cardiology", "available_days": "Mon,Tue,Wed,Fri", "start_time": "09:00", "end_time": "13:00", "slot_duration": 30},
            {"doctor_id": "D002", "doctor_name": "Dr. Priya Sharma", "department": "Pediatrics", "available_days": "Mon-Sat", "start_time": "10:00", "end_time": "16:00", "slot_duration": 30},
            {"doctor_id": "D003", "doctor_name": "Dr. Arjun Reddy", "department": "General Medicine", "available_days": "Mon-Sat", "start_time": "09:00", "end_time": "17:00", "slot_duration": 30}
        ]
        for doc in doc_data:
            db.add(Doctor(**doc))

        # Seed 4 appointments: 1 today active, 1 upcoming active, 1 past completed, 1 cancelled
        # Let's compute date dynamically
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        from config import TIMEZONE
        
        today_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")
        upcoming_str = (datetime.now(ZoneInfo(TIMEZONE)) + timedelta(days=2)).strftime("%Y-%m-%d")
        past_str = (datetime.now(ZoneInfo(TIMEZONE)) - timedelta(days=2)).strftime("%Y-%m-%d")
        
        appts_data = [
            # 1. Today Active
            {
                "appointment_id": "APT-000001",
                "patient_name": "David",
                "mobile": "9998887776",
                "doctor_id": "D001",
                "doctor_name": "Dr. Rajesh Kumar",
                "department": "Cardiology",
                "appointment_date": today_str,
                "appointment_time": "10:30",
                "status": "Booked",
                "created_at": "2026-08-02 12:00:00"
            },
            # 2. Upcoming Active
            {
                "appointment_id": "APT-000002",
                "patient_name": "Alice",
                "mobile": "9998887776",
                "doctor_id": "D002",
                "doctor_name": "Dr. Priya Sharma",
                "department": "Pediatrics",
                "appointment_date": upcoming_str,
                "appointment_time": "11:30",
                "status": "Booked",
                "created_at": "2026-08-02 12:05:00"
            },
            # 3. Past Completed
            {
                "appointment_id": "APT-000003",
                "patient_name": "Charlie",
                "mobile": "7777777777",
                "doctor_id": "D003",
                "doctor_name": "Dr. Arjun Reddy",
                "department": "General Medicine",
                "appointment_date": past_str,
                "appointment_time": "14:00",
                "status": "Booked",
                "created_at": "2026-07-31 10:00:00"
            },
            # 4. Cancelled
            {
                "appointment_id": "APT-000004",
                "patient_name": "Bob",
                "mobile": "8888888888",
                "doctor_id": "D001",
                "doctor_name": "Dr. Rajesh Kumar",
                "department": "Cardiology",
                "appointment_date": today_str,
                "appointment_time": "09:30",
                "status": "Cancelled",
                "created_at": "2026-08-02 09:00:00",
                "cancelled_at": "2026-08-02 10:00:00"
            }
        ]
        for appt in appts_data:
            db.add(Appointment(**appt))
        
        db.commit()
    finally:
        db.close()

    # Dependency override function
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        # 1. Test GET /api/v1/dashboard/stats
        print("\n--- 1. Testing GET /api/v1/dashboard/stats ---")
        res = client.get("/api/v1/dashboard/stats")
        print("Stats response:", res.json())
        assert res.status_code == 200
        assert res.json()["success"] is True
        data = res.json()["data"]
        assert data["today_appointments"] == 1
        assert data["upcoming_appointments"] == 1
        assert data["cancelled_appointments"] == 1
        assert data["completed_appointments"] == 1
        assert data["total_doctors"] == 3

        # 2. Test GET /api/v1/dashboard/appointments (pagination & filters)
        print("\n--- 2. Testing GET /api/v1/dashboard/appointments ---")
        res = client.get("/api/v1/dashboard/appointments?page=1&limit=2")
        print("Paginated response:", res.json())
        assert res.status_code == 200
        assert len(res.json()["data"]["appointments"]) == 2
        assert res.json()["data"]["total"] == 4
        assert res.json()["data"]["total_pages"] == 2

        # Test filter by doctor_id
        res_filter = client.get("/api/v1/dashboard/appointments?doctor_id=D001")
        print("Filtered by D001 response:", res_filter.json())
        assert len(res_filter.json()["data"]["appointments"]) == 2

        # Test filter by status
        res_status = client.get("/api/v1/dashboard/appointments?status=Cancelled")
        print("Filtered by Cancelled response:", res_status.json())
        assert len(res_status.json()["data"]["appointments"]) == 1

        # Test filter by search
        res_search = client.get("/api/v1/dashboard/appointments?search=Charlie")
        print("Filtered by search name Charlie response:", res_search.json())
        assert len(res_search.json()["data"]["appointments"]) == 1
        assert res_search.json()["data"]["appointments"][0]["patient_name"] == "Charlie"

        # 3. Test GET /api/v1/dashboard/appointment/{appointment_id}
        print("\n--- 3. Testing GET /api/v1/dashboard/appointment/{id} ---")
        res = client.get("/api/v1/dashboard/appointment/APT-000001")
        print("Detail response:", res.json())
        assert res.status_code == 200
        assert res.json()["data"]["patient_name"] == "David"

        # Test 404 for missing appointment
        res_missing = client.get("/api/v1/dashboard/appointment/APT-MISSING-99")
        print("Missing detail response:", res_missing.json())
        assert res_missing.status_code == 404
        assert res_missing.json()["success"] is False

        # 4. Test GET /api/v1/dashboard/doctors
        print("\n--- 4. Testing GET /api/v1/dashboard/doctors ---")
        res = client.get("/api/v1/dashboard/doctors")
        print("Doctors list response:", res.json())
        assert res.status_code == 200
        assert len(res.json()["data"]) == 3
        assert res.json()["data"][0]["doctor_id"] == "D001"

        # 5. Test GET /api/v1/dashboard/recent
        print("\n--- 5. Testing GET /api/v1/dashboard/recent ---")
        res = client.get("/api/v1/dashboard/recent")
        print("Recent response:", res.json())
        assert res.status_code == 200
        # Should return all 4 sorted by created_at desc
        assert len(res.json()["data"]) == 4
        # APT-000002 has created_at 12:05, so it should be first
        assert res.json()["data"][0]["appointment_id"] == "APT-000002"

        print("\nAll Dashboard REST APIs tests passed successfully!")

    finally:
        app.dependency_overrides.clear()
        if os.path.exists("test_dashboard.db"):
            try:
                os.remove("test_dashboard.db")
            except Exception:
                pass

if __name__ == "__main__":
    test_dashboard_endpoints()
