"""External flight-data adapters with explicit unavailable states."""

import json
import os
import time
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

KQ_STATUS_URL = "https://www.kenya-airways.com/en/book-manage/flight-status/"
KQ_BOOKING_URL = "https://www.kenya-airways.com/en/book-manage/"
HTTP_TIMEOUT_SECONDS = 12
_amadeus_token: Optional[str] = None
_amadeus_token_expires_at = 0.0


class FlightProviderError(Exception):
    """A provider request failed or returned unusable data."""


def _json_request(url: str, headers: Optional[dict] = None, data: bytes = None) -> dict:
    request = Request(
        url,
        data=data,
        headers={"Accept": "application/json", **(headers or {})},
        method="POST" if data is not None else "GET",
    )
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 429:
            raise FlightProviderError(
                "The flight-data provider rate limit was reached."
            ) from exc
        raise FlightProviderError(
            "The flight-data provider could not complete the request."
        ) from exc
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise FlightProviderError(
            "The flight-data provider is temporarily unavailable."
        ) from exc


def _to_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def get_flight_status(flight_number: str, departure_date: date) -> dict:
    """Look up KQ live status via Aviationstack, never fabricate a result."""
    api_key = os.getenv("AVIATIONSTACK_ACCESS_KEY")
    if not api_key:
        return {
            "available": False,
            "source": None,
            "checked_at": datetime.now(timezone.utc),
            "message": "Live flight status is not configured yet. Check the official KQ status page.",
            "flight": None,
            "official_status_url": KQ_STATUS_URL,
        }

    base_url = os.getenv(
        "AVIATIONSTACK_API_URL", "https://api.aviationstack.com/v1/flights"
    )
    query = urlencode(
        {
            "access_key": api_key,
            "flight_iata": flight_number,
            "flight_date": departure_date.isoformat(),
        }
    )
    try:
        payload = _json_request(f"{base_url}?{query}")
        if payload.get("error"):
            raise FlightProviderError("The flight-data provider rejected the request.")
        records = payload.get("data") or []
        matching = next(
            (
                item
                for item in records
                if (item.get("flight", {}).get("iata") or "").upper()
                == flight_number.upper()
                and (item.get("airline", {}).get("iata") or "").upper() == "KQ"
            ),
            None,
        )
        if not matching:
            return {
                "available": False,
                "source": "Aviationstack",
                "checked_at": datetime.now(timezone.utc),
                "message": "No matching KQ flight status was returned. Check the flight number and date, or use KQ's official page.",
                "flight": None,
                "official_status_url": KQ_STATUS_URL,
            }

        departure = matching.get("departure") or {}
        arrival = matching.get("arrival") or {}
        flight = matching.get("flight") or {}
        return {
            "available": True,
            "source": "Aviationstack",
            "checked_at": datetime.now(timezone.utc),
            "message": "Status received from the flight-data provider. Confirm important changes with Kenya Airways.",
            "flight": {
                "flight_number": flight_number,
                "flight_date": departure_date,
                "status": matching.get("flight_status"),
                "origin": departure.get("iata"),
                "destination": arrival.get("iata"),
                "departure_at": _to_datetime(
                    departure.get("estimated") or departure.get("scheduled")
                ),
                "arrival_at": _to_datetime(
                    arrival.get("estimated") or arrival.get("scheduled")
                ),
                "terminal": departure.get("terminal"),
                "gate": departure.get("gate"),
            },
            "official_status_url": KQ_STATUS_URL,
        }
    except FlightProviderError as exc:
        return {
            "available": False,
            "source": "Aviationstack",
            "checked_at": datetime.now(timezone.utc),
            "message": f"{exc} Check the official KQ status page.",
            "flight": None,
            "official_status_url": KQ_STATUS_URL,
        }


def _get_amadeus_token() -> str:
    global _amadeus_token, _amadeus_token_expires_at
    if _amadeus_token and time.time() < _amadeus_token_expires_at:
        return _amadeus_token
    client_id = os.getenv("AMADEUS_CLIENT_ID")
    client_secret = os.getenv("AMADEUS_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise FlightProviderError("Live flight-offer search is not configured yet.")
    base_url = os.getenv("AMADEUS_API_URL", "https://test.api.amadeus.com").rstrip("/")
    body = urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode("utf-8")
    payload = _json_request(
        f"{base_url}/v1/security/oauth2/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=body,
    )
    _amadeus_token = payload["access_token"]
    _amadeus_token_expires_at = time.time() + max(
        int(payload.get("expires_in", 1800)) - 60, 60
    )
    return _amadeus_token


def _make_offer(offer: dict) -> dict:
    itineraries = offer.get("itineraries") or []
    segments = []
    for itinerary in itineraries:
        for segment in itinerary.get("segments") or []:
            carrier = segment.get("carrierCode", "")
            segments.append(
                {
                    "carrier_code": carrier,
                    "flight_number": f"{carrier}{segment.get('number', '')}",
                    "origin": (segment.get("departure") or {}).get("iataCode", ""),
                    "destination": (segment.get("arrival") or {}).get("iataCode", ""),
                    "departure_at": _to_datetime(
                        (segment.get("departure") or {}).get("at")
                    ),
                    "arrival_at": _to_datetime(
                        (segment.get("arrival") or {}).get("at")
                    ),
                }
            )
    return {
        "offer_id": offer.get("id", ""),
        "price": (offer.get("price") or {}).get("grandTotal", ""),
        "currency": (offer.get("price") or {}).get("currency", ""),
        "validating_airline": (offer.get("validatingAirlineCodes") or ["KQ"])[0],
        "segments": segments,
        # Offers from Amadeus are not directly transferable to KQ checkout.
        "bookable_at_source": False,
    }


def search_kq_flights(payload: Any) -> dict:
    """Search an offer provider and expose only offers explicitly tied to KQ."""
    client_id = os.getenv("AMADEUS_CLIENT_ID")
    if not client_id:
        return {
            "available": False,
            "source": None,
            "checked_at": datetime.now(timezone.utc),
            "message": "Live KQ flight search credentials are not configured yet. Continue on Kenya Airways to view current schedules and fares.",
            "offers": [],
            "booking_url": KQ_BOOKING_URL,
        }

    base_url = os.getenv("AMADEUS_API_URL", "https://test.api.amadeus.com").rstrip("/")
    try:
        token = _get_amadeus_token()
        params: Dict[str, Any] = {
            "originLocationCode": payload.origin,
            "destinationLocationCode": payload.destination,
            "departureDate": payload.departure_date.isoformat(),
            "adults": payload.adults,
            "travelClass": payload.travel_class,
            "includedAirlineCodes": "KQ",
            "max": 10,
        }
        if payload.return_date:
            params["returnDate"] = payload.return_date.isoformat()
        data = _json_request(
            f"{base_url}/v2/shopping/flight-offers?{urlencode(params)}",
            headers={"Authorization": f"Bearer {token}"},
        )
        offers = []
        for offer in data.get("data") or []:
            validation_carriers = offer.get("validatingAirlineCodes") or []
            segment_carriers = {
                segment.get("carrierCode")
                for itinerary in offer.get("itineraries") or []
                for segment in itinerary.get("segments") or []
            }
            if "KQ" in validation_carriers or "KQ" in segment_carriers:
                offers.append(_make_offer(offer))
        return {
            "available": True,
            "source": "Amadeus",
            "checked_at": datetime.now(timezone.utc),
            "message": (
                "These KQ offers were returned by the search provider. Prices and availability may change; confirm them on Kenya Airways."
                if offers
                else "The provider returned no verifiable KQ offers for those details. Try Kenya Airways' booking page."
            ),
            "offers": offers,
            "booking_url": KQ_BOOKING_URL,
        }
    except (FlightProviderError, KeyError, ValueError, TypeError):
        return {
            "available": False,
            "source": "Amadeus" if os.getenv("AMADEUS_CLIENT_ID") else None,
            "checked_at": datetime.now(timezone.utc),
            "message": "Live KQ flight search is unavailable right now. Continue on Kenya Airways to see current options.",
            "offers": [],
            "booking_url": KQ_BOOKING_URL,
        }
