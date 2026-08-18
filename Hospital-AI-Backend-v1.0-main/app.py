import logging
import os
import time
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from sqlalchemy import text
from collections import defaultdict

SERVER_START_TIME = time.time()
load_dotenv()

from config import (
    HOSPITAL_NAME,
    TIMEZONE,
    DEFAULT_SLOT_DURATION,
    VERSION,
    ENVIRONMENT,
    CORS_ORIGINS
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from database.database import init_db, SessionLocal
logger.info("Initializing database and seeding default data...")
init_db()

from routes.doctor_routes import router as doctor_router
from routes.booking_routes import router as booking_router
from routes.dashboard_routes import router as dashboard_router
from routes.retell_routes import router as retell_router
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Hospital AI Appointment Manager",
    description=(
        "Production-ready FastAPI backend designed for hospital appointment booking and queries. "
        "Optimized for Retell AI receptionist voice capabilities."
    ),
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RateLimiter:
    def __init__(self, limit: int = 120, window: int = 60):
        self.limit = limit
        self.window = window
        self.ip_records = defaultdict(list)

    def is_limited(self, ip: str) -> bool:
        now = time.time()
        self.ip_records[ip] = [t for t in self.ip_records[ip] if now - t < self.window]
        if len(self.ip_records[ip]) >= self.limit:
            return True
        self.ip_records[ip].append(now)
        return False

limiter = RateLimiter(limit=150, window=60)

@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    if limiter.is_limited(client_ip):
        logger.warning(f"Rate limit exceeded for client IP: {client_ip} on path {request.url.path}")
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "message": "Too many requests. Please try again later.",
                "errors": ["Rate limit exceeded. Maximum 150 requests per minute."]
            }
        )
    return await call_next(request)

@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    try:
        return await asyncio.wait_for(call_next(request), timeout=15.0)
    except asyncio.TimeoutError:
        logger.error(f"Request timeout exceeded for path: {request.url.path}")
        return JSONResponse(
            status_code=504,
            content={
                "success": False,
                "message": "Request gateway timeout",
                "errors": ["The server took too long to respond to the request."]
            }
        )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "success" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": str(detail),
            "errors": [str(detail)]
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors_list = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "Validation error")
        errors_list.append(f"{loc}: {msg}")
    logger.warning(f"Request schema validation failure on path {request.url.path}: {errors_list}")
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Input validation failed",
            "errors": errors_list
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on path {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error occurred",
            "errors": [str(exc)]
        }
    )

app.include_router(doctor_router, prefix="/api/v1", tags=["Doctors"])
app.include_router(booking_router, prefix="/api/v1", tags=["Bookings"])
app.include_router(dashboard_router, prefix="/api/v1", tags=["Dashboard"])
app.include_router(retell_router, prefix="/api/v1")

app.mount("/admin", StaticFiles(directory="frontend", html=True), name="admin")

@app.get(
    "/api/v1/ai-capabilities",
    summary="Get AI Receptionist capabilities configurations",
    description=(
        "Exposes hospital specifications, operating timezones, slot durations, available departments, "
        "active doctor profiles directory list, and supported NLP features to assist AI Voice agent configuration."
    ),
    response_description="Model specifications config and capabilities map.",
    tags=["AI Support"]
)
def get_ai_capabilities():
    logger.info("AI Receptionist capability queries requested.")
    db = SessionLocal()
    from services.doctor_service import DoctorService
    try:
        doc_srv = DoctorService(db)
        docs = doc_srv.get_doctors()
        formatted_docs = [{
            "doctor_id": doc["Doctor ID"],
            "doctor_name": doc["Doctor Name"],
            "department": doc["Department"]
        } for doc in docs]
        departments = sorted(list(set(doc["Department"] for doc in docs if doc.get("Department"))))
    except Exception as e:
        logger.error(f"Error fetching doctors list for AI capabilities: {e}")
        formatted_docs = []
        departments = ["Cardiology", "Pediatrics", "General Medicine"]
    finally:
        db.close()

    return {
        "success": True,
        "message": "AI capabilities retrieved successfully",
        "data": {
            "hospital_name": HOSPITAL_NAME,
            "timezone": TIMEZONE,
            "appointment_duration_minutes": DEFAULT_SLOT_DURATION,
            "available_departments": departments,
            "doctors": formatted_docs,
            "supported_features": [
                "flexible_date_keywords_today_tomorrow_weekday",
                "flexible_time_keywords_am_pm_24h",
                "doctor_specialization_synonyms_lookup",
                "doctor_name_token_matching",
                "automatic_sequential_id_generation",
                "rate_limiting_ready"
            ]
        },
        "errors": []
    }

@app.get("/api/v1/system-info", tags=["System Details"])
def system_info():
    return {
        "success": True,
        "message": "System info retrieved successfully",
        "data": {
            "service": "Hospital AI Backend",
            "version": VERSION,
            "status": "running",
            "database": "PostgreSQL",
            "environment": ENVIRONMENT
        },
        "errors": []
    }

@app.get("/health", tags=["API Health Check"])
def health_check():
    db_connected = "disconnected"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db_connected = "connected"
        db.close()
    except Exception as e:
        logger.error(f"Health check database connection failed: {e}")

    uptime_seconds = time.time() - SERVER_START_TIME
    days = int(uptime_seconds // (24 * 3600))
    hours = int((uptime_seconds % (24 * 3600)) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    seconds = int(uptime_seconds % 60)
    formatted_uptime = f"{days}d {hours}h {minutes}m {seconds}s"

    return {
        "success": True,
        "message": "Hospital AI backend is healthy",
        "data": {
            "status": "healthy",
            "database": db_connected,
            "version": VERSION,
            "environment": ENVIRONMENT,
            "uptime_seconds": int(uptime_seconds),
            "uptime_readable": formatted_uptime
        },
        "errors": []
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting uvicorn server...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
