import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app import app

def test_fastapi_endpoints():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.database import Base, get_db
    from database.models import Doctor, Appointment, HospitalInfo
    
    import os
    if os.path.exists("test_api.db"):
        try:
            os.remove("test_api.db")
        except Exception:
            pass

    engine = create_engine("sqlite:///test_api.db", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Build tables
    Base.metadata.create_all(bind=engine)
    
    # Seed initial data
    db = TestingSessionLocal()
    try:
        doctors_data = [
            {
                "doctor_id": "D001",
                "doctor_name": "Dr. Rajesh Kumar",
                "department": "Cardiology",
                "available_days": "Mon,Tue,Wed,Fri",
                "start_time": "09:00",
                "end_time": "13:00",
                "slot_duration": 30
            },
            {
                "doctor_id": "D002",
                "doctor_name": "Dr. Priya Sharma",
                "department": "Pediatrics",
                "available_days": "Mon-Sat",
                "start_time": "10:00",
                "end_time": "16:00",
                "slot_duration": 30
            },
            {
                "doctor_id": "D003",
                "doctor_name": "Dr. Arjun Reddy",
                "department": "General Medicine",
                "available_days": "Mon-Sat",
                "start_time": "09:00",
                "end_time": "17:00",
                "slot_duration": 30
            }
        ]
        for doc in doctors_data:
            db.add(Doctor(**doc))
        
        hospital_data = [
            {"key": "Hospital Name", "value": "ABC Hospital"},
            {"key": "Opening Time", "value": "09:00"},
            {"key": "Closing Time", "value": "20:00"},
            {"key": "Emergency", "value": "24 Hours"},
            {"key": "Phone", "value": "9876543210"},
            {"key": "Address", "value": "Visakhapatnam"},
            {"key": "Insurance", "value": "Cash, UPI, Insurance"}
        ]
        for info in hospital_data:
            db.add(HospitalInfo(**info))
        db.commit()
    finally:
        db.close()

    # Dependency override function
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
            # No need for finally: close is handled
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    # Compute a valid booking date dynamically
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from config import TIMEZONE, HOLIDAYS
    
    tz = ZoneInfo(TIMEZONE)
    future_date = None
    for i in range(1, 15):
        d = datetime.now(tz) + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        if date_str not in HOLIDAYS and d.weekday() in [0, 1, 2, 4]:
            future_date = date_str
            break
    if not future_date:
        future_date = "2026-08-17"

    try:
        # 1. Test /health
        print("\n--- 1. Testing GET /health ---")
        res = client.get("/health")
        print("Health status response:", res.json())
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert res.json()["data"]["status"] == "healthy"

        # 2. Test /api/v1/doctors
        print("\n--- 2. Testing GET /api/v1/doctors ---")
        res = client.get("/api/v1/doctors")
        print("Doctors list response:", res.json())
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert len(res.json()["data"]) == 3

        # 3. Test /api/v1/hospital-info
        print("\n--- 3. Testing GET /api/v1/hospital-info ---")
        res = client.get("/api/v1/hospital-info")
        print("Hospital info response:", res.json())
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert res.json()["data"]["Hospital Name"] == "ABC Hospital"

        # 3b. Test /api/v1/system-info
        print("\n--- 3b. Testing GET /api/v1/system-info ---")
        res = client.get("/api/v1/system-info")
        print("System info response:", res.json())
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert res.json()["data"]["service"] == "Hospital AI Backend"
        assert res.json()["data"]["database"] == "PostgreSQL"

        # 3c. Test /api/v1/ai-capabilities
        print("\n--- 3c. Testing GET /api/v1/ai-capabilities ---")
        res = client.get("/api/v1/ai-capabilities")
        print("AI Capabilities response:", res.json())
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert res.json()["data"]["hospital_name"] == "ABC Hospital"

        # 3d. Test /api/v1/search-doctors
        print("\n--- 3d. Testing GET /api/v1/search-doctors ---")
        res = client.get("/api/v1/search-doctors?query=rajesh")
        print("Search doctors response:", res.json())
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert len(res.json()["data"]) == 1
        assert res.json()["data"][0]["doctor_name"] == "Dr. Rajesh Kumar"

        # Test search with synonym
        res = client.get("/api/v1/search-doctors?query=pediatrician")
        print("Search pediatrician response:", res.json())
        assert res.status_code == 200
        assert len(res.json()["data"]) == 1
        assert res.json()["data"][0]["doctor_name"] == "Dr. Priya Sharma"

        # 3e. Test /api/v1/departments
        print("\n--- 3e. Testing GET /api/v1/departments ---")
        res = client.get("/api/v1/departments")
        print("Departments response:", res.json())
        assert res.status_code == 200
        assert "Cardiology" in res.json()["data"]

        # 3f. Test /api/v1/doctors-by-department/{department}
        print("\n--- 3f. Testing GET /api/v1/doctors-by-department ---")
        res = client.get("/api/v1/doctors-by-department/Cardiology")
        print("Doctors by department response:", res.json())
        assert res.status_code == 200
        assert len(res.json()["data"]) == 1
        assert res.json()["data"][0]["Doctor Name"] == "Dr. Rajesh Kumar"

        # 4. Test /api/v1/check-availability
        print("\n--- 4. Testing POST /api/v1/check-availability ---")
        avail_payload = {"doctor_id": "D001", "date": future_date}
        res = client.post("/api/v1/check-availability", json=avail_payload)
        print("Availability result:", res.json())
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert len(res.json()["data"]["available_slots"]) == 8

        # 5. Test /api/v1/book-appointment
        print("\n--- 5. Testing POST /api/v1/book-appointment ---")
        book_payload = {
            "patient_name": "David",
            "mobile": "9998887776",
            "doctor_name": "Dr. Rajesh Kumar",
            "date": future_date,
            "time": "10:30"
        }
        res = client.post("/api/v1/book-appointment", json=book_payload)
        print("Book result:", res.json())
        assert res.status_code == 200
        assert res.json()["success"] is True
        appt_id = res.json()["data"]["appointment"]["appointment_id"]
        assert appt_id.startswith("APT-")

        # Test book using flexible parameters: "next monday", "9:30 AM", "Rajesh"
        print("\n--- 5b. Testing POST /api/v1/book-appointment with flexible inputs ---")
        book_payload_flex = {
            "patient_name": "FlexPatient",
            "mobile": "9992223334",
            "doctor_name": "Rajesh",
            "date": "next monday",
            "time": "9:30 AM"
        }
        res_flex = client.post("/api/v1/book-appointment", json=book_payload_flex)
        print("Flexible book result:", res_flex.json())
        assert res_flex.status_code == 200
        assert res_flex.json()["success"] is True
        assert res_flex.json()["data"]["appointment"]["doctor_name"] == "Dr. Rajesh Kumar"
        assert res_flex.json()["data"]["appointment"]["time"] == "09:30"

        # Duplicate check
        res_dup = client.post("/api/v1/book-appointment", json=book_payload)
        print("Duplicate book result:", res_dup.json())
        assert res_dup.status_code == 409
        assert res_dup.json()["success"] is False
        assert "already exists" in res_dup.json()["message"]

        # Booked slot check (different patient)
        book_payload_diff = book_payload.copy()
        book_payload_diff["patient_name"] = "Gary"
        book_payload_diff["mobile"] = "1111111111"
        res_diff = client.post("/api/v1/book-appointment", json=book_payload_diff)
        print("Booked slot result:", res_diff.json())
        assert res_diff.status_code == 400
        assert res_diff.json()["success"] is False
        assert "10:30" not in res_diff.json()["data"]["available_slots"]

        # 6. Test /api/v1/appointment-status
        print("\n--- 6. Testing GET /api/v1/appointment-status ---")
        res = client.get(f"/api/v1/appointment-status?appointment_id={appt_id}")
        print("Status by ID result:", res.json())
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert res.json()["data"]["appointments"][0]["Patient Name"] == "David"

        res_mob = client.get("/api/v1/appointment-status?mobile=9998887776")
        print("Status by Mobile result:", res_mob.json())
        assert res_mob.status_code == 200
        assert res_mob.json()["success"] is True
        assert len(res_mob.json()["data"]["appointments"]) == 1

        # 7. Test /api/v1/reschedule-appointment
        print("\n--- 7. Testing POST /api/v1/reschedule-appointment ---")
        resched_payload = {
            "appointment_id": appt_id,
            "new_date": future_date,
            "new_time": "12:00"
        }
        res = client.post("/api/v1/reschedule-appointment", json=resched_payload)
        print("Reschedule result:", res.json())
        assert res.status_code == 200
        assert res.json()["success"] is True

        # Verify updated date/time in status lookup
        res_check = client.get(f"/api/v1/appointment-status?appointment_id={appt_id}")
        appt_detail = res_check.json()["data"]["appointments"][0]
        assert appt_detail["Time"] == "12:00"
        assert appt_detail["Status"] == "Rescheduled"
        assert appt_detail["Updated At"] is not None

        # 8. Test /api/v1/cancel-appointment
        print("\n--- 8. Testing POST /api/v1/cancel-appointment ---")
        cancel_payload = {"appointment_id": appt_id}
        res = client.post("/api/v1/cancel-appointment", json=cancel_payload)
        print("Cancel result:", res.json())
        assert res.status_code == 200
        assert res.json()["success"] is True

        # Verify updated status to Cancelled
        res_check_cancel = client.get(f"/api/v1/appointment-status?appointment_id={appt_id}")
        appt_detail_cancel = res_check_cancel.json()["data"]["appointments"][0]
        assert appt_detail_cancel["Status"] == "Cancelled"
        assert appt_detail_cancel["Cancelled At"] is not None

        print("\nAll FastAPI Router endpoints tests passed successfully!")

    finally:
        app.dependency_overrides.clear()
        import os
        if os.path.exists("test_api.db"):
            try:
                os.remove("test_api.db")
            except Exception:
                pass

if __name__ == "__main__":
    test_fastapi_endpoints()
