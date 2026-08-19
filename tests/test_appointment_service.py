import sys
from pathlib import Path
from pydantic import ValidationError
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.database import Base
from database.models import Doctor, Appointment
from services.availability_service import AvailabilityService
from services.booking_service import BookingService
from services.appointment_service import AppointmentService
from models.appointment import AppointmentCreate, AppointmentReschedule

def test_appointment_service():
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
        # Seed doctor Rajesh Kumar (D001)
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

        avail = AvailabilityService(db)
        book_service = BookingService(db, availability_service=avail)
        appt_service = AppointmentService(db, availability_service=avail)

        # 1. Test Pydantic Validations
        print("\n--- 1. Testing Pydantic Model Validations ---")
        # Correct Create Schema
        valid_create = {
            "patient_name": "Bob",
            "mobile": "1234567890",
            "doctor_name": "Dr. Rajesh Kumar",
            "date": future_date,
            "time": "09:00"
        }
        create_model = AppointmentCreate(**valid_create)
        print("Pydantic valid model check passed:", create_model)

        # Invalid Date Create Schema
        invalid_create = valid_create.copy()
        invalid_create["date"] = "03/08/2026" # wrong format
        try:
            AppointmentCreate(**invalid_create)
            assert False, "Should have failed date validation!"
        except ValidationError as e:
            print("Successfully caught invalid date validation!")

        # 2. Test Cancellation
        print("\n--- 2. Testing Cancellation ---")
        # First book an appointment
        book_res = book_service.book_appointment(valid_create)
        assert book_res["success"] is True
        appt_id = book_res["data"]["appointment"]["appointment_id"]
        print(f"Booked appointment for cancellation: {appt_id}")

        # Cancel it
        cancel_res = appt_service.cancel_appointment(appt_id)
        print("Cancellation response:", cancel_res)
        assert cancel_res["success"] is True

        # Verify DB fields
        status_res = appt_service.get_appointment_status(appointment_id=appt_id)
        cancelled_appt = status_res["appointments"][0]
        print("Cancelled Appointment Detail:", cancelled_appt)
        assert cancelled_appt["Status"] == "Cancelled"
        assert cancelled_appt["Cancelled At"] is not None
        assert cancelled_appt["Patient Name"] == "Bob"  # preserved fields

        # Cancel again (should fail with HTTPException 400)
        try:
            appt_service.cancel_appointment(appt_id)
            assert False, "Should have thrown HTTPException"
        except HTTPException as e:
            print("Successfully caught duplicate cancellation exception:", e.detail)
            assert e.status_code == 400

        # Cancel non-existent ID (should fail with HTTPException 404)
        try:
            appt_service.cancel_appointment("APT-FAKE-001")
            assert False, "Should have thrown HTTPException"
        except HTTPException as e:
            print("Successfully caught invalid cancel ID exception:", e.detail)
            assert e.status_code == 404

        # 3. Test Rescheduling
        print("\n--- 3. Testing Rescheduling ---")
        # Book another appointment
        valid_create_2 = {
            "patient_name": "Alice",
            "mobile": "9999999999",
            "doctor_name": "Dr. Rajesh Kumar",
            "date": future_date,
            "time": "10:30"
        }
        book_res_2 = book_service.book_appointment(valid_create_2)
        assert book_res_2["success"] is True
        appt_id_2 = book_res_2["data"]["appointment"]["appointment_id"]
        print(f"Booked appointment for rescheduling: {appt_id_2}")

        # Reschedule it to 11:30 (free slot)
        resched_res = appt_service.reschedule_appointment(appt_id_2, future_date, "11:30")
        print("Reschedule success response:", resched_res)
        assert resched_res["success"] is True

        # Verify DB details
        status_res2 = appt_service.get_appointment_status(appointment_id=appt_id_2)
        resched_appt = status_res2["appointments"][0]
        print("Rescheduled Appointment Detail:", resched_appt)
        assert resched_appt["Status"] == "Rescheduled"
        assert resched_appt["Date"] == future_date
        assert resched_appt["Time"] == "11:30"
        assert resched_appt["Updated At"] is not None

        # Reschedule to a booked slot
        book_service.book_appointment({
            "patient_name": "Charlie",
            "mobile": "7777777777",
            "doctor_name": "Dr. Rajesh Kumar",
            "date": future_date,
            "time": "10:00"
        })
        # Try to reschedule Alice to 10:00 (booked by Charlie) (should fail with HTTPException 400)
        try:
            appt_service.reschedule_appointment(appt_id_2, future_date, "10:00")
            assert False, "Should have thrown HTTPException"
        except HTTPException as e:
            print("Successfully caught slot unavailable reschedule exception:", e.detail)
            assert e.status_code == 400
            assert "10:00" not in e.detail["data"]["available_slots"]

        # Try to reschedule cancelled Bob (should fail with HTTPException 400)
        try:
            appt_service.reschedule_appointment(appt_id, future_date, "12:00")
            assert False, "Should have thrown HTTPException"
        except HTTPException as e:
            print("Successfully caught reschedule cancelled exception:", e.detail)
            assert e.status_code == 400

        # 4. Test Lookups
        print("\n--- 4. Testing Lookups (Appointment Status) ---")
        # Lookup by ID
        lookup_id_res = appt_service.get_appointment_status(appointment_id=appt_id_2)
        print("Lookup by ID response:", lookup_id_res)
        assert lookup_id_res["success"] is True
        assert len(lookup_id_res["appointments"]) == 1
        assert lookup_id_res["appointments"][0]["Patient Name"] == "Alice"

        # Lookup by Mobile (Alice mobile: 9999999999)
        lookup_mob_res = appt_service.get_appointment_status(mobile="9999999999")
        print("Lookup by Mobile response:")
        for a in lookup_mob_res["appointments"]:
            print(a)
        assert lookup_mob_res["success"] is True
        assert len(lookup_mob_res["appointments"]) == 1
        assert lookup_mob_res["appointments"][0]["Patient Name"] == "Alice"

        # Lookup by fake Mobile (should fail with HTTPException 404)
        try:
            appt_service.get_appointment_status(mobile="0000000000")
            assert False, "Should have thrown HTTPException"
        except HTTPException as e:
            print("Successfully caught fake Mobile lookup exception:", e.detail)
            assert e.status_code == 404

        print("\nAll AppointmentService integration tests passed successfully!")

    finally:
        db.close()

if __name__ == "__main__":
    test_appointment_service()
