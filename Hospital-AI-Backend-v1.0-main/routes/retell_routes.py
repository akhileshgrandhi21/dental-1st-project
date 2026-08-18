import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

router = APIRouter()


def _validate_retell_secret(secret: str | None) -> None:
    expected = os.getenv("RETELL_WEBHOOK_SECRET")
    if not expected:
        return
    if secret != expected:
        raise HTTPException(status_code=401, detail="Invalid Retell webhook secret")


@router.get("/retell/webhook", tags=["Retell AI"])
async def retell_webhook_health() -> dict[str, Any]:
    return {
        "success": True,
        "message": "Retell webhook endpoint is ready",
    }


@router.post("/retell/webhook", tags=["Retell AI"])
async def retell_webhook(
    request: Request,
    x_retell_webhook_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """Receive Retell webhook events.

    The payload is intentionally accepted as a generic object so Retell event
    versions can evolve without breaking the endpoint. Business actions should
    be handled in dedicated service functions after validating the event type.
    """
    _validate_retell_secret(x_retell_webhook_secret)

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    event = payload.get("event") if isinstance(payload, dict) else None
    call = payload.get("call") if isinstance(payload, dict) else None

    # Keep the first integration deliberately side-effect free. This endpoint
    # can safely be connected in Retell and verified before appointment logic
    # is enabled.
    return {
        "success": True,
        "message": "Retell webhook received",
        "data": {
            "event": event,
            "call_id": call.get("call_id") if isinstance(call, dict) else None,
        },
    }
