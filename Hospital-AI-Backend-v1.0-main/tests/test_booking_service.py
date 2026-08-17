import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.database import Base
from database.models import Doctor, Appointment
from services.availability_service import AvailabilityService
from services.booking_service import BookingService
from services.appointment_service import AppointmentService

def test_booking_service():
    # Setup SQLite in-memory DB
    engine = create_engine("sqlite:///:memory:")
    SessionClass = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = SessionClass()

    # Compute a valid booking date dynamically
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    HOLIDAYS = ["2026-08-15", "2026-01-26", "2026-10-02", "2026-12-25"]
    tz = ZoneInfo("Asia/Kolkata")
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
        # Seed doctors
        doc1 = Doctor(
            doctor_id="D001",
            doctor_name="Dr. Rajesh Kumar",
            department="Cardiology",
            available_days="Mon,Tue,Wed,Fri",
            start_time="09:00",
            end_time="13:00",
            slot_duration=30
        )
        db.add(doc1)
        db.commit()

        avail_service = AvailabilityService(db)
        booking_service = BookingService(db, availability_service=avail_service)
        appt_service = AppointmentService(db, availability_service=avail_service)

        # 1. Test Input Validation Failures
        print("\n--- 1. Testing Validation Failures ---")
        # Missing field (empty name)
        bad_req1 = {"patient_name": "", "mobile": "123456", "doctor_name": "Dr. Rajesh Kumar", "date": future_date, "time": "09:00"}
        try:
            booking_service.book_appointment(bad_req1)
            assert False, "Should have thrown HTTPException for empty name"
        except HTTPException as e:
            print("Successfully caught empty name validation exception:", e.detail)
            assert e.status_code == 400

        # Invalid Date format
        bad_req2 = {"patient_name": "Akshay", "mobile": "9876543210", "doctor_name": "Dr. Rajesh Kumar", "date": "08-03-2026", "time": "09:00"}
        try:
            booking_service.book_appointment(bad_req2)
            assert False, "Should have thrown HTTPException for invalid date format"
        except HTTPException as e:
            print("Successfully caught invalid date format validation exception:", e.detail)
            assert e.status_code == 400

        # Non-existent doctor
        bad_req3 = {"patient_name": "Akshay", "mobile": "9876543210", "doctor_name": "Dr. Strange", "date": future_date, "time": "09:00"}
        try:
            booking_service.book_appointment(bad_req3)
            assert False, "Should have thrown HTTPException for non-existent doctor"
        except HTTPException as e:
            print("Successfully caught non-existent doctor exception:", e.detail)
            assert e.status_code == 404

        # 2. Test Successful Booking
        print("\n--- 2. Testing Successful Booking ---")
        req1 = {
            "patient_name": "Akshay",
            "mobile": "9876543210",
            "doctor_name": "Dr. Rajesh Kumar",
            "date": future_date,  # Monday
            "time": "09:00"
        }
        res1 = booking_service.book_appointment(req1)
        print("Booking 1 result:", res1)
        assert res1["success"] is True
        appt_id = res1["data"]["appointment"]["appointment_id"]
        assert appt_id.startswith("APT-")
        first_appt_id = appt_id

        # Verify it got saved in database
        status_res = appt_service.get_appointment_status(appointment_id=first_appt_id)
        saved_appt = status_res["data"]["appointments"][0]
        print("Saved appointment in DB:", saved_appt)
        assert saved_appt is not None
        assert saved_appt["Patient Name"] == "Akshay"
        assert saved_appt["Department"] == "Cardiology"
        assert saved_appt["Created At"] is not None

        # 3. Test Duplicate Booking Block
        print("\n--- 3. Testing Duplicate Booking ---")
        try:
            booking_service.book_appointment(req1)
            assert False, "Should have thrown HTTPException for duplicate"
        except HTTPException as e:
            print("Successfully caught duplicate booking exception:", e.detail)
            assert e.status_code == 409

        # 4. Test Slot Already Booked (Different Patient)
        print("\n--- 4. Testing Slot Already Booked (Different Patient) ---")
        req2 = {
            "patient_name": "Suresh",
            "mobile": "8888888888",
            "doctor_name": "Dr. Rajesh Kumar",
            "date": future_date,
            "time": "09:00" # same slot
        }
        try:
            booking_service.book_appointment(req2)
            assert False, "Should have thrown HTTPException for booked slot"
        except HTTPException as e:
            print("Successfully caught booked slot availability exception:", e.detail)
            assert e.status_code == 400
            assert "09:30" in e.detail["data"]["available_slots"]
            assert "09:00" not in e.detail["data"]["available_slots"]

        # 5. Test booking sequence increments
        print("\n--- 5. Testing Booking Sequence Increments ---")
        req3 = {
            "patient_name": "Suresh",
            "mobile": "8888888888",
            "doctor_name": "Dr. Rajesh Kumar",
            "date": future_date,
            "time": "09:30" # next slot
        }
        res3 = booking_service.book_appointment(req3)
        print("Booking 2 result:", res3)
        assert res3["success"] is True
        appt_id3 = res3["data"]["appointment"]["appointment_id"]
        assert appt_id3 != first_appt_id
        # Extract numeric suffixes to verify increment
        num1 = int(first_appt_id.split("-")[1])
        num2 = int(appt_id3.split("-")[1])
        assert num2 == num1 + 1
        print(f"Generated sequential IDs: {first_appt_id} -> {appt_id3}")

        print("\nAll BookingService integration tests passed successfully!")

    finally:
        db.close()

if __name__ == "__main__":
    test_booking_service()
