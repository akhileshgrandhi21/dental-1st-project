import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# Read connection string from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Use SQLite in-memory or fallback database URL if not set
    logger.warning("DATABASE_URL not set in environment. Falling back to local SQLite database.")
    DATABASE_URL = "sqlite:///local_hospital.db"

# Replace postgres:// with postgresql:// if needed for SQLAlchemy compatibility
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configure SQLAlchemy Engine
# Note: connect_args={"check_same_thread": False} is required only for SQLite
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI dependency to provide a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initializes the database by creating tables and seeding default data if empty."""
    from database.models import Doctor, HospitalInfo
    
    # Auto-create tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 1. Seed Doctor data if empty
        if db.query(Doctor).count() == 0:
            logger.info("Doctors table is empty. Seeding initial doctors data...")
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
            db.commit()
            logger.info("Doctors data seeded successfully.")

        # 2. Seed Hospital Information if empty
        if db.query(HospitalInfo).count() == 0:
            logger.info("Hospital Info table is empty. Seeding hospital info data...")
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
            logger.info("Hospital info data seeded successfully.")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")
        db.rollback()
    finally:
        db.close()
