"""Schemas for flight discovery and passenger trip management."""

import re
from datetime import date, datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _iata_code(value: str) -> str:
    normalized = value.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", normalized):
        raise ValueError("Use a three-letter airport code, such as NBO.")
    return normalized


def _flight_number(value: Optional[str]) -> Optional[str]:
    if value is None or not value.strip():
        return None
    normalized = re.sub(r"\s+", "", value).upper()
    if not re.fullmatch(r"KQ\d{1,4}[A-Z]?", normalized):
        raise ValueError("Enter a Kenya Airways flight number, such as KQ100.")
    return normalized


class FlightStatusRequest(BaseModel):
    flight_number: str = Field(..., min_length=3, max_length=8)
    departure_date: date

    @field_validator("flight_number")
    @classmethod
    def validate_flight_number(cls, value: str) -> str:
        result = _flight_number(value)
        if result is None:
            raise ValueError("A flight number is required.")
        return result


class FlightSearchRequest(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3)
    destination: str = Field(..., min_length=3, max_length=3)
    departure_date: date
    return_date: Optional[date] = None
    adults: int = Field(default=1, ge=1, le=9)
    travel_class: str = Field(
        default="ECONOMY", pattern="^(ECONOMY|PREMIUM_ECONOMY|BUSINESS|FIRST)$"
    )

    @field_validator("origin", "destination")
    @classmethod
    def validate_iata(cls, value: str) -> str:
        return _iata_code(value)

    @model_validator(mode="after")
    def validate_route_and_dates(self):
        if self.origin == self.destination:
            raise ValueError("Origin and destination must be different.")
        if self.return_date and self.return_date < self.departure_date:
            raise ValueError("Return date cannot be before departure date.")
        return self


class FlightSegment(BaseModel):
    carrier_code: str
    flight_number: str
    origin: str
    destination: str
    departure_at: Optional[datetime] = None
    arrival_at: Optional[datetime] = None


class FlightOffer(BaseModel):
    offer_id: str
    price: str
    currency: str
    validating_airline: str
    segments: List[FlightSegment]
    bookable_at_source: bool = False


class FlightSearchResponse(BaseModel):
    available: bool
    source: Optional[str] = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str
    offers: List[FlightOffer] = Field(default_factory=list)
    booking_url: str


class FlightStatus(BaseModel):
    flight_number: str
    flight_date: date
    status: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    departure_at: Optional[datetime] = None
    arrival_at: Optional[datetime] = None
    terminal: Optional[str] = None
    gate: Optional[str] = None


class FlightStatusResponse(BaseModel):
    available: bool
    source: Optional[str] = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str
    flight: Optional[FlightStatus] = None
    official_status_url: str


class TripReminderCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=160)
    remind_at: datetime

    @field_validator("remind_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Reminder time must include a timezone.")
        return value.astimezone(timezone.utc)


class TripReminderUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=160)
    remind_at: Optional[datetime] = None
    completed: Optional[bool] = None

    @field_validator("remind_at")
    @classmethod
    def require_timezone(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Reminder time must include a timezone.")
            return value.astimezone(timezone.utc)
        return value


class SavedTripCreate(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3)
    destination: str = Field(..., min_length=3, max_length=3)
    departure_date: date
    return_date: Optional[date] = None
    flight_number: Optional[str] = Field(None, max_length=8)
    label: Optional[str] = Field(None, max_length=120)

    @field_validator("origin", "destination")
    @classmethod
    def validate_iata(cls, value: str) -> str:
        return _iata_code(value)

    @field_validator("flight_number")
    @classmethod
    def validate_flight_number(cls, value: Optional[str]) -> Optional[str]:
        return _flight_number(value)

    @model_validator(mode="after")
    def validate_trip(self):
        if self.origin == self.destination:
            raise ValueError("Origin and destination must be different.")
        if self.return_date and self.return_date < self.departure_date:
            raise ValueError("Return date cannot be before departure date.")
        return self


class SavedTripUpdate(BaseModel):
    origin: Optional[str] = Field(None, min_length=3, max_length=3)
    destination: Optional[str] = Field(None, min_length=3, max_length=3)
    departure_date: Optional[date] = None
    return_date: Optional[date] = None
    flight_number: Optional[str] = Field(None, max_length=8)
    label: Optional[str] = Field(None, max_length=120)

    @field_validator("origin", "destination")
    @classmethod
    def validate_iata(cls, value: Optional[str]) -> Optional[str]:
        return _iata_code(value) if value is not None else value

    @field_validator("flight_number")
    @classmethod
    def validate_flight_number(cls, value: Optional[str]) -> Optional[str]:
        return _flight_number(value)


class TripReminderDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reminder_id: str
    trip_id: str
    title: str
    remind_at: datetime
    completed: bool


class SavedTripDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trip_id: str
    origin: str
    destination: str
    departure_date: date
    return_date: Optional[date]
    flight_number: Optional[str]
    label: Optional[str]
    created_at: datetime
    reminders: List[TripReminderDTO] = Field(default_factory=list)


class TripAssistantRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: List[dict] = Field(default_factory=list, max_length=12)


class TripAssistantAction(BaseModel):
    tool: str
    result: dict


class TripAssistantResponse(BaseModel):
    response: str
    actions: List[TripAssistantAction] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
