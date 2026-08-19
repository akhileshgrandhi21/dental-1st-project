from pydantic import BaseModel, Field, model_validator
from typing import Optional

from utils.date_parser import parse_flexible_date, parse_flexible_time

class Appointment(BaseModel):
    appointment_id: str = Field(
        alias="Appointment ID", 
        description="Unique sequential identifier of the appointment (e.g. APT-000001)",
        examples=["APT-000001"]
    )
    patient_name: str = Field(
        alias="Patient Name", 
        description="Full legal name of the patient",
        examples=["David Miller"]
    )
    mobile: str = Field(
        alias="Mobile", 
        description="Registered phone/mobile number of the patient",
        examples=["9998887776"]
    )
    doctor_id: str = Field(
        alias="Doctor ID", 
        description="Unique identifier of the assigned doctor",
        examples=["D001"]
    )
    doctor_name: str = Field(
        alias="Doctor Name", 
        description="Full name of the assigned doctor",
        examples=["Dr. Rajesh Kumar"]
    )
    department: str = Field(
        alias="Department", 
        description="Medical department or specialty of the doctor",
        examples=["Cardiology"]
    )
    date: str = Field(
        alias="Date", 
        description="Standardized date of the appointment (YYYY-MM-DD)",
        examples=["2026-08-03"]
    )
    time: str = Field(
        alias="Time", 
        description="Standardized 24-hour time of the appointment (HH:MM)",
        examples=["10:30"]
    )
    status: str = Field(
        alias="Status", 
        description="Current state of the appointment (e.g. Booked, Cancelled, Rescheduled)",
        examples=["Booked"]
    )
    created_at: str = Field(
        alias="Created At", 
        description="UTC/Local timestamp when the appointment was created (YYYY-MM-DD HH:MM:SS)",
        examples=["2026-07-30 17:00:30"]
    )
    updated_at: Optional[str] = Field(
        default=None, 
        alias="Updated At", 
        description="Timestamp when the appointment was last rescheduled",
        examples=["2026-07-30 18:30:15"]
    )
    cancelled_at: Optional[str] = Field(
        default=None, 
        alias="Cancelled At", 
        description="Timestamp when the appointment was soft-deleted or cancelled",
        examples=["2026-07-30 19:15:00"]
    )

    model_config = {
        "populate_by_name": True
    }

class AppointmentCreate(BaseModel):
    patient_name: str = Field(
        ..., 
        min_length=1, 
        description="Full name of the patient. Must not be blank.",
        examples=["David Miller"]
    )
    mobile: str = Field(
        ..., 
        min_length=5, 
        description="Patient contact mobile phone number. Must contain at least 5 digits.",
        examples=["9998887776"]
    )
    doctor_name: Optional[str] = Field(
        default=None, 
        min_length=1, 
        description="Optional doctor name search query (flexible matching). Either doctor_name or doctor_id must be provided.",
        examples=["Dr. Rajesh Kumar"]
    )
    doctor_id: Optional[str] = Field(
        default=None, 
        min_length=1, 
        description="Optional unique doctor ID. Either doctor_name or doctor_id must be provided.",
        examples=["D001"]
    )
    date: str = Field(
        ..., 
        description="Appointment date. Supports 'today', 'tomorrow', 'next <weekday>', or standard formats like 'YYYY-MM-DD'.",
        examples=["tomorrow", "2026-08-03"]
    )
    time: str = Field(
        ..., 
        description="Appointment slot time. Supports formats like '9', '9am', '9:30 AM', '14:00'. Normalizes to HH:MM.",
        examples=["9:30 AM", "10:30"]
    )

    @model_validator(mode="after")
    def validate_inputs(self) -> 'AppointmentCreate':
        if not self.doctor_id and not self.doctor_name:
            raise ValueError("Must provide either doctor_id or doctor_name to identify the doctor.")

        try:
            parsed_date = parse_flexible_date(self.date)
        except ValueError as e:
            raise ValueError(str(e))

        try:
            normalized_time = parse_flexible_time(self.time)
        except ValueError as e:
            raise ValueError(str(e))

        self.date = parsed_date.strftime("%Y-%m-%d")
        self.time = normalized_time
        return self

class AppointmentReschedule(BaseModel):
    appointment_id: str = Field(
        ..., 
        min_length=1, 
        description="Unique sequential identifier of the appointment to reschedule.",
        examples=["APT-000001"]
    )
    new_date: str = Field(
        ..., 
        description="New appointment date. Supports 'today', 'tomorrow', 'next <weekday>', or standard formats like 'YYYY-MM-DD'.",
        examples=["next monday", "2026-08-10"]
    )
    new_time: str = Field(
        ..., 
        description="New slot time. Supports formats like '9', '9am', '9:30 AM', '14:00'. Normalizes to HH:MM.",
        examples=["12:00", "2:00 PM"]
    )
    doctor_id: Optional[str] = Field(
        default=None, 
        min_length=1, 
        description="Optional new doctor ID (if transferring the appointment to another doctor).",
        examples=["D002"]
    )
    doctor_name: Optional[str] = Field(
        default=None, 
        min_length=1, 
        description="Optional new doctor name search query (if transferring the appointment).",
        examples=["Dr. Priya Sharma"]
    )

    @model_validator(mode="after")
    def validate_inputs(self) -> 'AppointmentReschedule':
        try:
            parsed_date = parse_flexible_date(self.new_date)
        except ValueError as e:
            raise ValueError(str(e))

        try:
            self.new_time = parse_flexible_time(self.new_time)
        except ValueError as e:
            raise ValueError(str(e))

        self.new_date = parsed_date.strftime("%Y-%m-%d")
        return self
