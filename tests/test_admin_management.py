import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app import app
from database.database import Base, get_db

def test_admin_management_endpoints():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.models import Doctor, Appointment, HospitalInfo
    import os

    # Clean up test DB file if left over
    if os.path.exists("test_admin_management.db"):
        try:
            os.remove("test_admin_management.db")
        except Exception:
            pass

    engine = create_engine("sqlite:///test_admin_management.db", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Build tables
    Base.metadata.create_all(bind=engine)
    
    # Seed initial test data
    db = TestingSessionLocal()
    try:
        # Seed a doctor D001
        db.add(Doctor(
            doctor_id="D001",
            doctor_name="Dr. Rajesh Kumar",
            department="Cardiology",
            available_days="Mon,Tue,Wed,Fri",
            start_time="09:00",
            end_time="13:00",
            slot_duration=30
        ))
        
        # Seed appointment with D001
        db.add(Appointment(
            appointment_id="APT-000001",
            patient_name="David",
            mobile="9998887776",
            doctor_id="D001",
            doctor_name="Dr. Rajesh Kumar",
            department="Cardiology",
            appointment_date="2026-08-08",
            appointment_time="10:30",
            status="Booked",
            created_at="2026-08-02 12:00:00"
        ))

        # Seed initial HospitalInfo
        db.add(HospitalInfo(key="Hospital Name", value="ABC Hospital"))
        db.add(HospitalInfo(key="Opening Time", value="09:00"))
        
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
        # 1. Test PUT /api/v1/dashboard/doctor
        print("\n--- 1. Testing PUT /api/v1/dashboard/doctor ---")
        payload = {
            "doctor_id": "D001",
            "doctor_name": "Dr. Rajesh K. Updated",
            "available_days": "Mon-Fri",
            "slot_duration": 45
        }
        res = client.put("/api/v1/dashboard/doctor", json=payload)
        print("Doctor edit response:", res.json())
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert res.json()["data"]["doctor_name"] == "Dr. Rajesh K. Updated"
        assert res.json()["data"]["available_days"] == "Mon-Fri"
        assert res.json()["data"]["slot_duration"] == 45

        # 2. Test PUT /api/v1/dashboard/hospital-info
        print("\n--- 2. Testing PUT /api/v1/dashboard/hospital-info ---")
        info_payload = {
            "Hospital Name": "XYZ Super Speciality Hospital",
            "Address": "New Delhi, India"
        }
        res_info = client.put("/api/v1/dashboard/hospital-info", json=info_payload)
        print("Hospital info update response:", res_info.json())
        assert res_info.status_code == 200
        assert res_info.json()["success"] is True
        assert res_info.json()["data"]["Hospital Name"] == "XYZ Super Speciality Hospital"

        # Check DB directly
        db_check = TestingSessionLocal()
        try:
            name_row = db_check.query(HospitalInfo).filter(HospitalInfo.key == "Hospital Name").first()
            addr_row = db_check.query(HospitalInfo).filter(HospitalInfo.key == "Address").first()
            assert name_row.value == "XYZ Super Speciality Hospital"
            assert addr_row.value == "New Delhi, India"
        finally:
            db_check.close()

        # 3. Test DELETE /api/v1/dashboard/doctor/{doctor_id}
        print("\n--- 3. Testing DELETE /api/v1/dashboard/doctor/{doctor_id} ---")
        res_delete = client.delete("/api/v1/dashboard/doctor/D001")
        print("Doctor delete response:", res_delete.json())
        assert res_delete.status_code == 200
        assert res_delete.json()["success"] is True

        # Verify doctor is deleted and appointments associated with them are physically deleted
        db_check = TestingSessionLocal()
        try:
            doc = db_check.query(Doctor).filter(Doctor.doctor_id == "D001").first()
            assert doc is None
            appt = db_check.query(Appointment).filter(Appointment.appointment_id == "APT-000001").first()
            assert appt is None
        finally:
            db_check.close()

        print("\nAll Admin Management REST APIs tests passed successfully!")

    finally:
        app.dependency_overrides.clear()
        if os.path.exists("test_admin_management.db"):
            try:
                os.remove("test_admin_management.db")
            except Exception:
                pass

if __name__ == "__main__":
    test_admin_management_endpoints()
