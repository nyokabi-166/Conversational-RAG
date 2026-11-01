"""Authenticated saved trips and in-app reminders."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from src.core.auth import AuthUser, require_role
from src.core.database import get_db
from src.models.entities import PassengerAccount, SavedTrip, TripReminder
from src.modules.flight_services import get_flight_status
from src.modules.notifications import send_flight_alert
from src.schemas.trips import (
    SavedTripCreate,
    SavedTripDTO,
    SavedTripUpdate,
    TripReminderCreate,
    TripReminderDTO,
    TripReminderUpdate,
)

router = APIRouter(prefix="/trips", tags=["trips"])
passenger_dependency = require_role(["passenger"])


def _owned_trip(db: Session, trip_id: str, passenger_id: str) -> SavedTrip:
    trip = (
        db.query(SavedTrip)
        .options(joinedload(SavedTrip.reminders))
        .filter(
            SavedTrip.trip_id == trip_id,
            SavedTrip.passenger_id == passenger_id,
        )
        .first()
    )
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found.")
    return trip


@router.get("", response_model=list[SavedTripDTO])
def list_trips(
    current_user: AuthUser = Depends(passenger_dependency),
    db: Session = Depends(get_db),
):
    return (
        db.query(SavedTrip)
        .options(joinedload(SavedTrip.reminders))
        .filter(SavedTrip.passenger_id == current_user.user_id)
        .order_by(SavedTrip.departure_date.asc())
        .all()
    )


@router.post("", response_model=SavedTripDTO, status_code=status.HTTP_201_CREATED)
def create_trip(
    payload: SavedTripCreate,
    current_user: AuthUser = Depends(passenger_dependency),
    db: Session = Depends(get_db),
):
    trip = SavedTrip(passenger_id=current_user.user_id, **payload.model_dump())
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


@router.get("/{trip_id}", response_model=SavedTripDTO)
def get_trip(
    trip_id: str,
    current_user: AuthUser = Depends(passenger_dependency),
    db: Session = Depends(get_db),
):
    return _owned_trip(db, trip_id, current_user.user_id)


@router.patch("/{trip_id}", response_model=SavedTripDTO)
def update_trip(
    trip_id: str,
    payload: SavedTripUpdate,
    current_user: AuthUser = Depends(passenger_dependency),
    db: Session = Depends(get_db),
):
    trip = _owned_trip(db, trip_id, current_user.user_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(trip, field, value)
    if trip.origin == trip.destination:
        raise HTTPException(status_code=422, detail="Trip airports must be different.")
    if trip.return_date and trip.return_date < trip.departure_date:
        raise HTTPException(
            status_code=422, detail="Return date cannot be before departure date."
        )
    db.commit()
    db.refresh(trip)
    return trip


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(
    trip_id: str,
    current_user: AuthUser = Depends(passenger_dependency),
    db: Session = Depends(get_db),
):
    trip = _owned_trip(db, trip_id, current_user.user_id)
    db.delete(trip)
    db.commit()


@router.post(
    "/{trip_id}/reminders",
    response_model=TripReminderDTO,
    status_code=status.HTTP_201_CREATED,
)
def create_reminder(
    trip_id: str,
    payload: TripReminderCreate,
    current_user: AuthUser = Depends(passenger_dependency),
    db: Session = Depends(get_db),
):
    trip = _owned_trip(db, trip_id, current_user.user_id)
    reminder = TripReminder(trip_id=trip.trip_id, **payload.model_dump())
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.patch("/{trip_id}/reminders/{reminder_id}", response_model=TripReminderDTO)
def update_reminder(
    trip_id: str,
    reminder_id: str,
    payload: TripReminderUpdate,
    current_user: AuthUser = Depends(passenger_dependency),
    db: Session = Depends(get_db),
):
    trip = _owned_trip(db, trip_id, current_user.user_id)
    reminder = (
        db.query(TripReminder)
        .filter(
            TripReminder.reminder_id == reminder_id,
            TripReminder.trip_id == trip.trip_id,
        )
        .first()
    )
    if reminder is None:
        raise HTTPException(status_code=404, detail="Reminder not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(reminder, field, int(value) if field == "completed" else value)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.delete(
    "/{trip_id}/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_reminder(
    trip_id: str,
    reminder_id: str,
    current_user: AuthUser = Depends(passenger_dependency),
    db: Session = Depends(get_db),
):
    trip = _owned_trip(db, trip_id, current_user.user_id)
    reminder = (
        db.query(TripReminder)
        .filter(
            TripReminder.reminder_id == reminder_id,
            TripReminder.trip_id == trip.trip_id,
        )
        .first()
    )
    if reminder is None:
        raise HTTPException(status_code=404, detail="Reminder not found.")
    db.delete(reminder)
    db.commit()


@router.post("/{trip_id}/test-alert")
def send_test_trip_alert(
    trip_id: str,
    current_user: AuthUser = Depends(passenger_dependency),
    db: Session = Depends(get_db),
):
    """Instantly dispatch an email alert for this trip to the logged-in passenger."""
    trip = _owned_trip(db, trip_id, current_user.user_id)
    passenger = db.query(PassengerAccount).filter(PassengerAccount.passenger_id == current_user.user_id).first()
    recipient_email = (passenger.email if passenger else None) or current_user.username
    if not recipient_email or "@" not in recipient_email:
        raise HTTPException(
            status_code=400,
            detail="Your passenger account does not have a valid email address configured.",
        )

    flight_status_data = None
    if trip.flight_number:
        try:
            flight_status_data = get_flight_status(trip.flight_number, trip.departure_date)
        except Exception:
            pass

    result = send_flight_alert(
        to_email=recipient_email,
        passenger_name=passenger.full_name or "Passenger" if passenger else "Passenger",
        flight_number=trip.flight_number or "KQ Trip",
        origin=trip.origin,
        destination=trip.destination,
        departure_date=trip.departure_date.isoformat(),
        reminder_title=f"Instant Flight Alert & Preparation Advisory ({trip.origin} → {trip.destination})",
        flight_status=flight_status_data,
    )
    return {
        "status": "success" if result.get("sent") else "failed",
        "recipient": recipient_email,
        "provider": result.get("provider"),
        "message": result.get("message") or f"Flight alert dispatched to {recipient_email}.",
    }


@router.post("/{trip_id}/reminders/{reminder_id}/test")
def send_test_reminder_alert(
    trip_id: str,
    reminder_id: str,
    current_user: AuthUser = Depends(passenger_dependency),
    db: Session = Depends(get_db),
):
    """Instantly dispatch an email alert for a specific reminder."""
    trip = _owned_trip(db, trip_id, current_user.user_id)
    reminder = (
        db.query(TripReminder)
        .filter(
            TripReminder.reminder_id == reminder_id,
            TripReminder.trip_id == trip.trip_id,
        )
        .first()
    )
    if reminder is None:
        raise HTTPException(status_code=404, detail="Reminder not found.")

    passenger = db.query(PassengerAccount).filter(PassengerAccount.passenger_id == current_user.user_id).first()
    recipient_email = (passenger.email if passenger else None) or current_user.username
    if not recipient_email or "@" not in recipient_email:
        raise HTTPException(
            status_code=400,
            detail="Your passenger account does not have a valid email address configured.",
        )

    flight_status_data = None
    if trip.flight_number:
        try:
            flight_status_data = get_flight_status(trip.flight_number, trip.departure_date)
        except Exception:
            pass

    result = send_flight_alert(
        to_email=recipient_email,
        passenger_name=passenger.full_name or "Passenger" if passenger else "Passenger",
        flight_number=trip.flight_number or "KQ Trip",
        origin=trip.origin,
        destination=trip.destination,
        departure_date=trip.departure_date.isoformat(),
        reminder_title=reminder.title,
        flight_status=flight_status_data,
    )
    return {
        "status": "success" if result.get("sent") else "failed",
        "recipient": recipient_email,
        "provider": result.get("provider"),
        "message": result.get("message") or f"Reminder alert dispatched to {recipient_email}.",
    }


@router.get("/notifications/active")
def get_active_notifications(
    current_user: AuthUser = Depends(passenger_dependency),
    db: Session = Depends(get_db),
):
    """Get active flight reminders and advisories for the in-app notification center."""
    trips = (
        db.query(SavedTrip)
        .options(joinedload(SavedTrip.reminders))
        .filter(SavedTrip.passenger_id == current_user.user_id)
        .all()
    )

    notifications = []
    for trip in trips:
        # Trip preparation advisory
        notifications.append(
            {
                "id": f"prep-{trip.trip_id}",
                "trip_id": trip.trip_id,
                "flight_number": trip.flight_number or "KQ",
                "route": f"{trip.origin} → {trip.destination}",
                "title": f"Trip preparation: {trip.origin} to {trip.destination}",
                "message": f"Departing on {trip.departure_date.isoformat()}. Web check-in opens 24h prior.",
                "created_at": trip.created_at,
                "type": "advisory",
            }
        )
        for reminder in trip.reminders:
            notifications.append(
                {
                    "id": f"rem-{reminder.reminder_id}",
                    "trip_id": trip.trip_id,
                    "flight_number": trip.flight_number or "KQ",
                    "route": f"{trip.origin} → {trip.destination}",
                    "title": reminder.title,
                    "message": f"Reminder for flight on {trip.departure_date.isoformat()}",
                    "remind_at": reminder.remind_at,
                    "completed": bool(reminder.completed),
                    "type": "reminder",
                }
            )

    return notifications
