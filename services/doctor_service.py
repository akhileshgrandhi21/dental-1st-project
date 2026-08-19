import logging
from sqlalchemy.orm import Session
from database.models import Doctor
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Specialization/Department Synonym Mapping
SYNONYM_MAP = {
    # Cardiology
    "cardiologist": "Cardiology",
    "cardio": "Cardiology",
    "heart doctor": "Cardiology",
    "heart specialist": "Cardiology",
    "heart": "Cardiology",
    
    # Pediatrics
    "children doctor": "Pediatrics",
    "child doctor": "Pediatrics",
    "kids doctor": "Pediatrics",
    "pediatrician": "Pediatrics",
    "children specialist": "Pediatrics",
    "kids specialist": "Pediatrics",
    "pediatrics": "Pediatrics",
    "child": "Pediatrics",
    "children": "Pediatrics",
    
    # General Medicine
    "general physician": "General Medicine",
    "general doctor": "General Medicine",
    "physician": "General Medicine",
    "medicine doctor": "General Medicine",
    "general medicine": "General Medicine",
    "gp": "General Medicine",
    "medicine": "General Medicine",
    "family doctor": "General Medicine",
    "general doctor": "General Medicine"
}

class DoctorService:
    def __init__(self, db: Session):
        self.db = db

    def get_doctors(self) -> List[Dict[str, Any]]:
        """Retrieves all doctors from the database as dictionaries."""
        docs = self.db.query(Doctor).all()
        return [{
            "Doctor ID": doc.doctor_id,
            "Doctor Name": doc.doctor_name,
            "Department": doc.department,
            "Available Days": doc.available_days,
            "Start Time": doc.start_time,
            "End Time": doc.end_time,
            "Slot Duration": doc.slot_duration
        } for doc in docs]

    def get_doctor_by_id(self, doctor_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single doctor by Doctor ID as a dictionary."""
        # Make search query ID validation flexible (e.g. matching "d1" or "D1" to "D001")
        query_id = doctor_id.strip().upper()
        doc = self.db.query(Doctor).filter(Doctor.doctor_id == query_id).first()
        if not doc:
            # Try parsing leading D and padding (e.g. "D1" -> "D001")
            if query_id.startswith("D"):
                try:
                    num = int(query_id[1:])
                    padded_id = f"D{num:03d}"
                    doc = self.db.query(Doctor).filter(Doctor.doctor_id == padded_id).first()
                except ValueError:
                    pass
        if not doc:
            return None
        return {
            "Doctor ID": doc.doctor_id,
            "Doctor Name": doc.doctor_name,
            "Department": doc.department,
            "Available Days": doc.available_days,
            "Start Time": doc.start_time,
            "End Time": doc.end_time,
            "Slot Duration": doc.slot_duration
        }

    def clean_name_for_comparison(self, name: str) -> str:
        """Helper to normalize a name by converting to lowercase, removing 'dr.'/'dr', and stripping spaces."""
        cleaned = name.lower().strip()
        # Remove common prefixes
        if cleaned.startswith("dr."):
            cleaned = cleaned[3:].strip()
        elif cleaned.startswith("dr"):
            cleaned = cleaned[2:].strip()
        # Remove extra whitespace between words
        return " ".join(cleaned.split())

    def get_doctor_by_name(self, doctor_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single doctor by Doctor Name (checks exact and normalized matches)."""
        docs = self.get_doctors()
        query = doctor_name.strip()
        
        # 1. Exact match check
        for doc in docs:
            if doc.get("Doctor Name") == query:
                return doc
                
        # 2. Normalized check (case insensitive & ignoring "Dr." prefix)
        query_norm = self.clean_name_for_comparison(query)
        for doc in docs:
            doc_name = str(doc.get("Doctor Name", ""))
            doc_norm = self.clean_name_for_comparison(doc_name)
            
            # Match if normalized full names are equal, OR if query is a token/part of doctor name
            if doc_norm == query_norm or query_norm in doc_norm or doc_norm in query_norm:
                return doc
        return None

    def search_doctors(self, query: str) -> List[Dict[str, Any]]:
        """
        Flexible search for doctors by name (first name, last name, partial names),
        doctor ID, department, or specialization synonyms.
        """
        logger.info(f"Doctor search initiated for query: '{query}'")
        if not query:
            return []

        cleaned_query = query.lower().strip()
        
        # 1. Check if the query is a Doctor ID (exact or padded)
        # e.g., "D001" or "d1"
        test_id_match = self.get_doctor_by_id(cleaned_query)
        if test_id_match:
            logger.info(f"Matched query '{query}' to Doctor ID: '{test_id_match['Doctor ID']}'")
            return [test_id_match]

        # 2. Check synonym map first
        target_department = None
        for syn, dept in SYNONYM_MAP.items():
            if syn == cleaned_query or cleaned_query in syn or syn in cleaned_query:
                target_department = dept
                break
        
        docs = self.get_doctors()
        matched = []
        
        query_norm = self.clean_name_for_comparison(query)
        query_tokens = set(query_norm.split())

        for doc in docs:
            doc_id = doc["Doctor ID"].lower()
            doc_name_cleaned = self.clean_name_for_comparison(doc["Doctor Name"])
            doc_name_tokens = set(doc_name_cleaned.split())
            doc_dept = doc["Department"].lower()
            
            # Check matches:
            # 1. Department matches synonym target department
            # 2. Direct department match
            # 3. Doctor ID match (substring check)
            # 4. Token overlap matching (first name, last name, or partial tokens)
            is_dept_match = target_department and doc["Department"].lower() == target_department.lower()
            is_direct_dept_match = cleaned_query in doc_dept or doc_dept in cleaned_query
            is_id_match = cleaned_query in doc_id
            
            # Token match check
            has_token_overlap = False
            if query_tokens and doc_name_tokens:
                for q_t in query_tokens:
                    for d_t in doc_name_tokens:
                        if q_t in d_t or d_t in q_t:
                            has_token_overlap = True
                            break
                    if has_token_overlap:
                        break
            
            if is_dept_match or is_direct_dept_match or is_id_match or has_token_overlap:
                matched.append(doc)
                
        logger.info(f"Doctor search completed: found {len(matched)} match(es) for query '{query}'")
        return matched
