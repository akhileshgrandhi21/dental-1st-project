from pydantic import BaseModel, Field

class Doctor(BaseModel):
    doctor_id: str = Field(alias="Doctor ID")
    doctor_name: str = Field(alias="Doctor Name")
    department: str = Field(alias="Department")
    available_days: str = Field(alias="Available Days")
    start_time: str = Field(alias="Start Time")
    end_time: str = Field(alias="End Time")
    slot_duration: int = Field(alias="Slot Duration")

    model_config = {
        "populate_by_name": True
    }

