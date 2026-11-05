"""Public flight lookup and search endpoints."""

import re
from datetime import date

from fastapi import APIRouter, HTTPException, Query, status

from src.modules.flight_services import get_flight_status, search_kq_flights
from src.modules.trip_assistant import answer_trip_question
from src.schemas.trips import (
    FlightSearchRequest,
    FlightSearchResponse,
    FlightStatusRequest,
    FlightStatusResponse,
    TripAssistantRequest,
    TripAssistantResponse,
)

router = APIRouter(prefix="/flights", tags=["flights"])


@router.get("/status", response_model=FlightStatusResponse)
def flight_status(
    flight_number: str = Query(..., min_length=3, max_length=8),
    departure_date: date = Query(...),
):
    """Look up live KQ flight status; returns an explicit fallback if unavailable."""
    normalized_number = flight_number.upper()
    if not re.fullmatch(r"KQ\d{1,4}[A-Z]?", normalized_number):
        raise HTTPException(
            status_code=422, detail="Enter a KQ flight number, such as KQ100."
        )
    request = FlightStatusRequest(
        flight_number=normalized_number, departure_date=departure_date
    )
    return get_flight_status(request.flight_number, request.departure_date)


@router.post("/search", response_model=FlightSearchResponse)
def flight_search(payload: FlightSearchRequest):
    """Search only for KQ offers and return a hand-off URL for confirmation."""
    return search_kq_flights(payload)


@router.post("/assistant", response_model=TripAssistantResponse)
def trip_assistant(payload: TripAssistantRequest):
    """Answer conversational flight questions and call only read-only tools."""
    try:
        return answer_trip_question(payload.message, payload.history)
    except Exception as exc:
        # A model outage must not result in a fabricated flight answer.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The trip assistant is temporarily unavailable. Use the flight search and status forms or continue on Kenya Airways.",
        ) from exc
