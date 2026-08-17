from sqlalchemy import Column, String, Integer
from database.database import Base

class Doctor(Base):
    __tablename__ = "doctors"

    doctor_id = Column(String, primary_key=True, index=True)
    doctor_name = Column(String, nullable=False)
    department = Column(String, nullable=False)
    available_days = Column(String, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    slot_duration = Column(Integer, nullable=False)

class Appointment(Base):
    __tablename__ = "appointments"

    appointment_id = Column(String, primary_key=True, index=True)
    patient_name = Column(String, nullable=False)
    mobile = Column(String, nullable=False)
    doctor_id = Column(String, nullable=False)
    doctor_name = Column(String, nullable=False)
    department = Column(String, nullable=False)
    appointment_date = Column(String, nullable=False)
    appointment_time = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=True)
    cancelled_at = Column(String, nullable=True)

class HospitalInfo(Base):
    __tablename__ = "hospital_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=False)
