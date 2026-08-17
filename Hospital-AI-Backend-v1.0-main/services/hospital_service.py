import logging
from sqlalchemy.orm import Session
from database.models import HospitalInfo
from typing import Dict, Any

logger = logging.getLogger(__name__)

class HospitalService:
    def __init__(self, db: Session):
        self.db = db

    def get_hospital_info(self) -> Dict[str, Any]:
        """Retrieves hospital info as a key-value dictionary with type conversion for numeric fields."""
        items = self.db.query(HospitalInfo).all()
        info_dict = {}
        for item in items:
            val = item.value
            if val is not None:
                # Try casting integers for matching previous tests (like Phone)
                if val.isdigit():
                    val = int(val)
            info_dict[item.key] = val
        return info_dict
