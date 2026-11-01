"""Coverage for public flight tools and passenger-owned trip data."""

from datetime import date, datetime, timezone

from src.modules import flight_services


def _register(client, email):
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "secure-pass-123",
            "full_name": "Test Passenger",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def test_flight_status_is_explicitly_unavailable_without_provider_key(monkeypatch):
    monkeypatch.delenv("AVIATIONSTACK_ACCESS_KEY", raising=False)

    result = flight_services.get_flight_status("KQ100", date(2026, 12, 1))

    assert result["available"] is False
    assert result["flight"] is None
    assert "kenya-airways.com" in result["official_status_url"]


def test_flight_status_returns_only_matching_kq_record(monkeypatch):
    monkeypatch.setenv("AVIATIONSTACK_ACCESS_KEY", "test-key")
    monkeypatch.setattr(
        flight_services,
        "_json_request",
        lambda *_args, **_kwargs: {
            "data": [
                {
                    "airline": {"iata": "KQ"},
                    "flight": {"iata": "KQ100"},
                    "flight_status": "active",
                    "departure": {
                        "iata": "NBO",
                        "scheduled": "2026-12-01T10:00:00+03:00",
                    },
                    "arrival": {"iata": "LHR", "scheduled": "2026-12-01T18:00:00Z"},
                },
                {
                    "airline": {"iata": "XX"},
                    "flight": {"iata": "KQ100"},
                    "flight_status": "active",
                },
            ]
        },
    )

    result = flight_services.get_flight_status("KQ100", date(2026, 12, 1))

    assert result["available"] is True
    assert result["flight"]["origin"] == "NBO"
    assert result["flight"]["status"] == "active"


def test_search_filters_to_kq_and_returns_checkout_caveat(monkeypatch):
    monkeypatch.setenv("AMADEUS_CLIENT_ID", "client")
    monkeypatch.setenv("AMADEUS_API_URL", "https://api.amadeus.com")
    monkeypatch.setattr(flight_services, "_get_amadeus_token", lambda: "token")
    monkeypatch.setattr(
        flight_services,
        "_json_request",
        lambda *_args, **_kwargs: {
            "data": [
                {
                    "id": "kq-offer",
                    "validatingAirlineCodes": ["KQ"],
                    "price": {"grandTotal": "100.00", "currency": "USD"},
                    "itineraries": [
                        {
                            "segments": [
                                {
                                    "carrierCode": "KQ",
                                    "number": "100",
                                    "departure": {
                                        "iataCode": "NBO",
                                        "at": "2026-12-01T10:00:00",
                                    },
                                    "arrival": {
                                        "iataCode": "LHR",
                                        "at": "2026-12-01T18:00:00",
                                    },
                                }
                            ]
                        }
                    ],
                },
                {
                    "id": "other-offer",
                    "validatingAirlineCodes": ["XX"],
                    "price": {"grandTotal": "80.00", "currency": "USD"},
                    "itineraries": [],
                },
            ]
        },
    )
    from src.schemas.trips import FlightSearchRequest

    result = flight_services.search_kq_flights(
        FlightSearchRequest(
            origin="NBO", destination="LHR", departure_date=date(2026, 12, 1)
        )
    )

    assert result["available"] is True
    assert [offer["offer_id"] for offer in result["offers"]] == ["kq-offer"]
    assert result["offers"][0]["bookable_at_source"] is False
    assert "confirm" in result["message"].lower()


def test_public_flight_endpoints_validate_and_fallback(client, monkeypatch):
    monkeypatch.delenv("AMADEUS_CLIENT_ID", raising=False)
    monkeypatch.delenv("AMADEUS_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(
        "src.routes.flights.get_flight_status",
        lambda flight_number, departure_date: {
            "available": False,
            "source": None,
            "checked_at": datetime.now(timezone.utc),
            "message": "Not configured",
            "flight": None,
            "official_status_url": "https://www.kenya-airways.com/en/book-manage/flight-status/",
        },
    )
    status_response = client.get(
        "/flights/status",
        params={"flight_number": "KQ100", "departure_date": "2026-12-01"},
    )
    invalid_response = client.get(
        "/flights/status",
        params={"flight_number": "XX100", "departure_date": "2026-12-01"},
    )
    search_response = client.post(
        "/flights/search",
        json={"origin": "NBO", "destination": "MBA", "departure_date": "2026-12-01"},
    )

    assert status_response.status_code == 200
    assert status_response.json()["available"] is False
    assert invalid_response.status_code == 422
    assert search_response.status_code == 200
    assert search_response.json()["offers"] == []
    assert "kenya-airways.com" in search_response.json()["booking_url"]


def test_trip_crud_and_reminders_require_passenger_and_enforce_ownership(client):
    token = _register(client, "one@example.com")
    other_token = _register(client, "two@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}
    trip_payload = {
        "origin": "nbo",
        "destination": "mba",
        "departure_date": "2026-12-01",
        "flight_number": "kq100",
    }

    assert client.get("/trips").status_code == 401
    created = client.post("/trips", json=trip_payload, headers=headers)
    assert created.status_code == 201
    trip = created.json()
    assert trip["origin"] == "NBO"
    trip_id = trip["trip_id"]

    reminder_response = client.post(
        f"/trips/{trip_id}/reminders",
        json={
            "title": "Check travel documents",
            "remind_at": "2026-11-24T10:00:00+03:00",
        },
        headers=headers,
    )
    assert reminder_response.status_code == 201
    reminder_id = reminder_response.json()["reminder_id"]
    patched = client.patch(
        f"/trips/{trip_id}/reminders/{reminder_id}",
        json={"completed": True},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["completed"] is True
    assert client.get("/trips", headers=headers).json()[0]["reminders"]

    assert client.get(f"/trips/{trip_id}", headers=other_headers).status_code == 404
    assert (
        client.post(
            f"/trips/{trip_id}/reminders",
            json={"title": "Not mine", "remind_at": "2026-11-24T10:00:00+03:00"},
            headers=other_headers,
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/trips/{trip_id}", json={"label": "Other"}, headers=other_headers
        ).status_code
        == 404
    )
    assert client.delete(f"/trips/{trip_id}", headers=other_headers).status_code == 404

    assert (
        client.patch(
            f"/trips/{trip_id}", json={"label": "Holiday"}, headers=headers
        ).json()["label"]
        == "Holiday"
    )
    assert client.delete(f"/trips/{trip_id}", headers=headers).status_code == 204
    assert client.get("/trips", headers=headers).json() == []


def test_trip_assistant_uses_mock_response_without_exposing_provider_secrets(
    client, monkeypatch
):
    monkeypatch.setattr(
        "src.routes.flights.answer_trip_question",
        lambda message, history: {
            "response": "Tell me your travel date to find KQ options.",
            "actions": [],
        },
    )
    response = client.post(
        "/flights/assistant",
        json={"message": "I want to fly from Nairobi to London"},
    )
    assert response.status_code == 200
    assert "travel date" in response.json()["response"]
    assert response.json()["actions"] == []


def test_send_test_trip_alert_and_notifications(client):
    headers = {"Authorization": f"Bearer {_register(client, 'passenger-alerts@example.com')}"}

    create_res = client.post(
        "/trips",
        json={
            "origin": "NBO",
            "destination": "LHR",
            "departure_date": "2026-12-10",
            "flight_number": "KQ100",
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    trip_id = create_res.json()["trip_id"]

    # Test sending instant trip alert
    alert_res = client.post(f"/trips/{trip_id}/test-alert", headers=headers)
    assert alert_res.status_code == 200
    assert alert_res.json()["status"] == "success"
    assert alert_res.json()["recipient"] == "passenger-alerts@example.com"

    # Add a reminder
    rem_res = client.post(
        f"/trips/{trip_id}/reminders",
        json={"title": "Pack passport and visa", "remind_at": "2026-12-09T10:00:00+03:00"},
        headers=headers,
    )
    assert rem_res.status_code == 201
    reminder_id = rem_res.json()["reminder_id"]

    # Test sending instant reminder alert
    rem_test_res = client.post(f"/trips/{trip_id}/reminders/{reminder_id}/test", headers=headers)
    assert rem_test_res.status_code == 200
    assert rem_test_res.json()["status"] == "success"

    # Test active notifications
    notif_res = client.get("/trips/notifications/active", headers=headers)
    assert notif_res.status_code == 200
    notifs = notif_res.json()
    assert len(notifs) >= 2
    assert any(n["type"] == "advisory" for n in notifs)
    assert any(n["type"] == "reminder" for n in notifs)
