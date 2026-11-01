"""Background worker that periodically checks and dispatches due trip reminders."""

import asyncio
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload

from ..core.database import SessionLocal
from ..logger import logger
from ..models.entities import PassengerAccount, SavedTrip, TripReminder
from .flight_services import get_flight_status
from .notifications import send_flight_alert

_worker_task: asyncio.Task | None = None
_running: bool = False
POLL_INTERVAL_SECONDS = 60


async def process_due_reminders() -> int:
    """Find and execute all due reminders across all passenger trips."""
    now = datetime.now(timezone.utc)
    dispatched_count = 0

    with SessionLocal() as db:
        try:
            due_reminders = (
                db.query(TripReminder)
                .join(SavedTrip, TripReminder.trip_id == SavedTrip.trip_id)
                .options(
                    joinedload(TripReminder.trip).joinedload(SavedTrip.passenger)
                )
                .filter(
                    TripReminder.remind_at <= now,
                    TripReminder.completed == 0,
                )
                .all()
            )

            for reminder in due_reminders:
                trip = reminder.trip
                if not trip:
                    continue

                passenger = trip.passenger
                passenger_email = passenger.email if passenger else None
                passenger_name = (passenger.full_name or "Passenger") if passenger else "Passenger"

                if not passenger_email:
                    logger.warning("Skipping reminder %s: no passenger email attached", reminder.reminder_id)
                    reminder.completed = 1
                    continue

                # Live flight status check if flight number is provided
                flight_status_data = None
                if trip.flight_number:
                    try:
                        flight_status_data = get_flight_status(
                            flight_number=trip.flight_number,
                            departure_date=trip.departure_date,
                        )
                    except Exception as exc:
                        logger.warning("Could not query live status for flight %s: %s", trip.flight_number, exc)

                # Dispatch email notification
                result = send_flight_alert(
                    to_email=passenger_email,
                    passenger_name=passenger_name,
                    flight_number=trip.flight_number or "KQ Trip",
                    origin=trip.origin,
                    destination=trip.destination,
                    departure_date=trip.departure_date.isoformat(),
                    reminder_title=reminder.title,
                    flight_status=flight_status_data,
                )

                reminder.completed = 1
                dispatched_count += 1
                logger.info(
                    "Reminder %s dispatched to %s (sent: %s, provider: %s)",
                    reminder.reminder_id,
                    passenger_email,
                    result.get("sent"),
                    result.get("provider"),
                )

            if dispatched_count > 0:
                db.commit()

        except Exception as exc:
            db.rollback()
            logger.error("Error processing due trip reminders: %s", exc)

    return dispatched_count


async def _reminder_loop():
    """Continuous polling loop executed in the background."""
    global _running
    logger.info("Trip reminder background worker started (interval: %ss)", POLL_INTERVAL_SECONDS)
    while _running:
        try:
            await process_due_reminders()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Unexpected error in reminder worker: %s", exc)

        try:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            break

    logger.info("Trip reminder background worker stopped")


def start_reminder_worker():
    """Start the reminder loop inside the active asyncio event loop."""
    global _worker_task, _running
    if not _running:
        _running = True
        _worker_task = asyncio.create_task(_reminder_loop())


def stop_reminder_worker():
    """Signal the reminder loop to stop and cancel the active task."""
    global _worker_task, _running
    _running = False
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
