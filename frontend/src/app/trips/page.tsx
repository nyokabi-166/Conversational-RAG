"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  Bell,
  BellRing,
  Bot,
  CheckCircle2,
  ExternalLink,
  Mail,
  Plane,
  Plus,
  Search,
  Send,
  Trash2,
} from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { AssistantMarkdown } from "@/components/assistant-markdown";
import {
  apiRequest,
  type ActiveNotification,
  type FlightOfferResult,
  type FlightSearchResult,
  type FlightStatusResult,
  type SavedTrip,
  type TripAssistantResult,
} from "@/lib/api";

const KQ_BOOKING_URL = "https://www.kenya-airways.com/en/book-manage/";
const KQ_STATUS_URL = "https://www.kenya-airways.com/en/book-manage/flight-status/";

function fieldClass() {
  return "mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring/40";
}

function formatDate(value: string | null) {
  if (!value) return "Not provided";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

function formatDateTime(value: string | null) {
  if (!value) return "Not provided";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function OfferCard({ offer }: { offer: FlightOfferResult }) {
  return (
    <article className="rounded-lg border bg-background p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold">{offer.segments.map((segment) => segment.flight_number).join(" · ")}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {offer.segments.map((segment) => `${segment.origin} → ${segment.destination}`).join(" · ")}
          </p>
        </div>
        <p className="font-semibold">{offer.currency} {offer.price}</p>
      </div>
      <div className="mt-3 space-y-1 text-xs text-muted-foreground">
        {offer.segments.map((segment, index) => (
          <p key={`${segment.flight_number}-${index}`}>
            {segment.flight_number}: {formatDateTime(segment.departure_at)} – {formatDateTime(segment.arrival_at)}
          </p>
        ))}
      </div>
      <p className="mt-3 text-xs text-muted-foreground">Confirm current fare and availability on Kenya Airways.</p>
    </article>
  );
}

export default function TripsPage() {
  const { user, token, ready } = useAuth();
  const [trips, setTrips] = useState<SavedTrip[]>([]);
  const [statusFlight, setStatusFlight] = useState("");
  const [statusDate, setStatusDate] = useState("");
  const [statusResult, setStatusResult] = useState<FlightStatusResult | null>(null);
  const [searchOrigin, setSearchOrigin] = useState("");
  const [searchDestination, setSearchDestination] = useState("");
  const [searchDeparture, setSearchDeparture] = useState("");
  const [searchReturn, setSearchReturn] = useState("");
  const [searchAdults, setSearchAdults] = useState(1);
  const [searchResult, setSearchResult] = useState<FlightSearchResult | null>(null);
  const [tripOrigin, setTripOrigin] = useState("");
  const [tripDestination, setTripDestination] = useState("");
  const [tripDeparture, setTripDeparture] = useState("");
  const [tripReturn, setTripReturn] = useState("");
  const [tripFlight, setTripFlight] = useState("");
  const [assistantInput, setAssistantInput] = useState("");
  const [assistantHistory, setAssistantHistory] = useState<Array<{ role: string; content: string }>>([]);
  const [assistantActions, setAssistantActions] = useState<TripAssistantResult["actions"]>([]);
  const [assistantSources, setAssistantSources] = useState<string[]>([]);
  const [reminderTitle, setReminderTitle] = useState<Record<string, string>>({});
  const [reminderTime, setReminderTime] = useState<Record<string, string>>({});
  const [notifications, setNotifications] = useState<ActiveNotification[]>([]);
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifPermission, setNotifPermission] = useState<string>("default");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadNotifications = useCallback(async () => {
    if (user?.role !== "passenger" || !token) {
      setNotifications([]);
      return;
    }
    try {
      const list = await apiRequest<ActiveNotification[]>("/trips/notifications/active", {}, token);
      setNotifications(list);
    } catch {
      // non-blocking
    }
  }, [user, token]);

  const loadTrips = useCallback(async () => {
    if (user?.role !== "passenger" || !token) {
      setTrips([]);
      return;
    }
    try {
      setTrips(await apiRequest<SavedTrip[]>("/trips", {}, token));
      void loadNotifications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load your trips.");
    }
  }, [user, token, loadNotifications]);

  useEffect(() => {
    if (ready) void loadTrips();
    if (typeof window !== "undefined" && "Notification" in window) {
      setNotifPermission(Notification.permission);
    }
  }, [ready, loadTrips]);

  const requestNotificationPermission = async () => {
    if (typeof window !== "undefined" && "Notification" in window) {
      const perm = await Notification.requestPermission();
      setNotifPermission(perm);
      if (perm === "granted") {
        new Notification("Kenya Airways Trip Assistant", {
          body: "Real-time flight alerts and reminders are enabled!",
        });
      }
    }
  };

  const triggerTestAlert = async (tripId: string) => {
    if (!token) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      const res = await apiRequest<{ status: string; recipient: string; provider?: string; message?: string }>(
        `/trips/${encodeURIComponent(tripId)}/test-alert`,
        { method: "POST" },
        token
      );
      setNotice(`✈️ Flight alert dispatched to ${res.recipient} (${res.provider || 'email'})! Check your inbox.`);
      if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "granted") {
        new Notification("✈️ Kenya Airways Flight Alert Dispatched", {
          body: `Advisory sent to ${res.recipient}`,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send flight alert.");
    } finally {
      setBusy(false);
    }
  };

  const triggerReminderTest = async (tripId: string, reminderId: string) => {
    if (!token) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      const res = await apiRequest<{ status: string; recipient: string; provider?: string }>(
        `/trips/${encodeURIComponent(tripId)}/reminders/${encodeURIComponent(reminderId)}/test`,
        { method: "POST" },
        token
      );
      setNotice(`🔔 Reminder alert sent to ${res.recipient}! Check your inbox.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send reminder alert.");
    } finally {
      setBusy(false);
    }
  };

  const submitStatus = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true); setError(null); setNotice(null); setStatusResult(null);
    try {
      const query = new URLSearchParams({ flight_number: statusFlight.trim().toUpperCase(), departure_date: statusDate });
      setStatusResult(await apiRequest<FlightStatusResult>(`/flights/status?${query}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not check flight status.");
    } finally { setBusy(false); }
  };

  const submitSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true); setError(null); setNotice(null); setSearchResult(null);
    try {
      setSearchResult(await apiRequest<FlightSearchResult>("/flights/search", {
        method: "POST",
        body: JSON.stringify({
          origin: searchOrigin.trim().toUpperCase(),
          destination: searchDestination.trim().toUpperCase(),
          departure_date: searchDeparture,
          return_date: searchReturn || null,
          adults: Number(searchAdults),
        }),
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not search KQ flights.");
    } finally { setBusy(false); }
  };

  const saveTrip = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      await apiRequest<SavedTrip>("/trips", {
        method: "POST",
        body: JSON.stringify({
          origin: tripOrigin.trim().toUpperCase(),
          destination: tripDestination.trim().toUpperCase(),
          departure_date: tripDeparture,
          return_date: tripReturn || null,
          flight_number: tripFlight.trim().toUpperCase() || null,
        }),
      }, token);
      setTripOrigin(""); setTripDestination(""); setTripDeparture(""); setTripReturn(""); setTripFlight("");
      setNotice("Trip saved.");
      await loadTrips();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save this trip.");
    } finally { setBusy(false); }
  };

  const askAssistant = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = assistantInput.trim();
    if (!message || busy) return;
    setBusy(true); setError(null); setNotice(null); setAssistantInput(""); setAssistantActions([]); setAssistantSources([]);
    const history = [...assistantHistory, { role: "user", content: message }];
    setAssistantHistory(history);
    try {
      const result = await apiRequest<TripAssistantResult>("/flights/assistant", {
        method: "POST", body: JSON.stringify({ message, history: assistantHistory }),
      });
      setAssistantHistory((current) => [...current, { role: "assistant", content: result.response }]);
      setAssistantActions(result.actions || []);
      setAssistantSources(result.sources || []);
    } catch (err) {
      setAssistantHistory((current) => [...current, { role: "assistant", content: "I couldn’t reach the trip assistant. You can use the flight search or status forms below." }]);
      setError(err instanceof Error ? err.message : "The trip assistant is unavailable.");
    } finally { setBusy(false); }
  };

  const deleteTrip = async (tripId: string) => {
    if (!token) return;
    setError(null);
    try {
      await apiRequest<void>(`/trips/${encodeURIComponent(tripId)}`, { method: "DELETE" }, token);
      await loadTrips();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not delete trip."); }
  };

  const createReminder = async (event: FormEvent<HTMLFormElement>, tripId: string) => {
    event.preventDefault();
    if (!token) return;
    const localTime = reminderTime[tripId];
    if (!localTime) { setError("Choose a date and time for the reminder."); return; }
    setError(null); setNotice(null);
    try {
      await apiRequest(`/trips/${encodeURIComponent(tripId)}/reminders`, {
        method: "POST",
        body: JSON.stringify({ title: reminderTitle[tripId] || "Prepare for my trip", remind_at: new Date(localTime).toISOString() }),
      }, token);
      setReminderTitle((current) => ({ ...current, [tripId]: "" }));
      setReminderTime((current) => ({ ...current, [tripId]: "" }));
      setNotice("Reminder added to your trip.");
      await loadTrips();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not add reminder."); }
  };

  const updateReminder = async (tripId: string, reminderId: string, completed: boolean) => {
    if (!token) return;
    try {
      await apiRequest(`/trips/${encodeURIComponent(tripId)}/reminders/${encodeURIComponent(reminderId)}`, {
        method: "PATCH", body: JSON.stringify({ completed }),
      }, token);
      await loadTrips();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not update reminder."); }
  };

  const deleteReminder = async (tripId: string, reminderId: string) => {
    if (!token) return;
    try {
      await apiRequest<void>(`/trips/${encodeURIComponent(tripId)}/reminders/${encodeURIComponent(reminderId)}`, { method: "DELETE" }, token);
      await loadTrips();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not delete reminder."); }
  };

  const assistantOffers = assistantActions.flatMap((action) => {
    const offers = action.result.offers;
    return Array.isArray(offers) ? offers as FlightOfferResult[] : [];
  });
  const assistantStatusAction = assistantActions.find(
    (action) => action.tool === "get_kq_flight_status",
  );
  const assistantStatus = assistantStatusAction?.result.flight as
    | FlightStatusResult["flight"]
    | undefined;
  const assistantStatusUrl =
    (assistantStatusAction?.result.official_status_url as string | undefined) ||
    KQ_STATUS_URL;
  const assistantBookingUrl =
    (assistantActions.find((action) => action.tool === "search_kq_flights")?.result
      .booking_url as string | undefined) || KQ_BOOKING_URL;

  return (
    <main className="min-h-screen bg-muted/30 px-4 py-6 text-foreground md:px-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <Link href="/" className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />Back to chat</Link>
            <h1 className="text-2xl font-semibold">Plan and manage your trip</h1>
            <p className="mt-1 text-sm text-muted-foreground">Find verified KQ information, save trip details, and receive proactive reminders.</p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowNotifications(!showNotifications)}
              className="relative"
            >
              <Bell className="h-4 w-4 mr-1 text-primary" />
              Alerts
              {notifications.length > 0 && (
                <span className="ml-1.5 rounded-full bg-primary px-1.5 py-0.2 text-[11px] text-primary-foreground font-bold">
                  {notifications.length}
                </span>
              )}
            </Button>
            <a className="inline-flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm hover:bg-accent" href={KQ_BOOKING_URL} target="_blank" rel="noreferrer">Kenya Airways booking <ExternalLink className="h-4 w-4" /></a>
          </div>
        </header>

        {showNotifications && (
          <section className="rounded-xl border bg-card p-5 shadow-sm space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <BellRing className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-semibold">Active Flight Alerts & Advisories</h2>
              </div>
              {notifPermission !== "granted" && (
                <Button size="sm" variant="outline" onClick={() => void requestNotificationPermission()}>
                  Enable Desktop Push Alerts
                </Button>
              )}
            </div>
            {notifications.length === 0 ? (
              <p className="text-sm text-muted-foreground">No active flight advisories or reminders right now. Save a trip below to activate automated alerts.</p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {notifications.map((n) => (
                  <div key={n.id} className="rounded-lg border bg-background p-3.5 text-sm space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-primary/10 text-primary">
                        {n.type}
                      </span>
                      <span className="text-xs text-muted-foreground font-mono">{n.route}</span>
                    </div>
                    <p className="font-semibold text-foreground pt-1">{n.title}</p>
                    <p className="text-xs text-muted-foreground">{n.message}</p>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {error && <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</div>}
        {notice && <div role="status" className="rounded-lg border border-green-600/30 bg-green-600/5 px-4 py-3 text-sm">{notice}</div>}

        <section className="rounded-xl border bg-card p-5 shadow-sm">
          <div className="mb-4 flex items-center gap-2"><Bot className="h-5 w-5" /><h2 className="text-lg font-semibold">Ask the trip assistant</h2></div>
          <p className="mb-4 text-sm text-muted-foreground">Try “Find a KQ flight from Nairobi to London on 20 December” or “What is the status of KQ100 today?” The assistant asks for missing details and only reports provider results.</p>
          <div className="max-h-72 space-y-3 overflow-y-auto">
            {assistantHistory.map((entry, index) => <div key={`${entry.role}-${index}`} className={`rounded-lg px-4 py-3 text-sm ${entry.role === "user" ? "ml-auto max-w-2xl bg-primary text-primary-foreground" : "max-w-3xl border bg-background"}`}>{entry.role === "assistant" ? <AssistantMarkdown content={entry.content} /> : entry.content}</div>)}
          </div>
          {assistantOffers.map((offer) => <div className="mt-3" key={offer.offer_id}><OfferCard offer={offer} /></div>)}
          {assistantStatusAction && <div className="mt-3 rounded-lg border bg-background p-4 text-sm">
            <p>{String(assistantStatusAction.result.message || "Flight status result")}</p>
            {assistantStatus && <div className="mt-2 space-y-1">
              <p className="font-semibold">{assistantStatus.flight_number} · {assistantStatus.status || "Status not provided"}</p>
              <p>{assistantStatus.origin || "—"} → {assistantStatus.destination || "—"}</p>
              <p>Departure: {formatDateTime(assistantStatus.departure_at)}</p>
              <p>Arrival: {formatDateTime(assistantStatus.arrival_at)}</p>
            </div>}
            <a href={assistantStatusUrl} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline">Verify on Kenya Airways <ExternalLink className="h-4 w-4" /></a>
          </div>}
          {assistantActions.some((action) => action.tool === "search_kq_flights") && assistantOffers.length === 0 && <a href={assistantBookingUrl} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline">Continue on Kenya Airways <ExternalLink className="h-4 w-4" /></a>}
          {assistantSources.length > 0 && <p className="mt-3 text-xs text-muted-foreground">Policy sources: {assistantSources.join(", ")}</p>}
          <form onSubmit={askAssistant} className="mt-4 flex gap-2">
            <input className={fieldClass()} aria-label="Ask about a flight or trip" value={assistantInput} onChange={(event) => setAssistantInput(event.target.value)} placeholder="Tell me where and when you want to travel…" />
            <Button type="submit" disabled={busy || !assistantInput.trim()}><Search />Ask</Button>
          </form>
        </section>

        <div className="grid gap-6 lg:grid-cols-2">
          <section className="rounded-xl border bg-card p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2"><Plane className="h-5 w-5" /><h2 className="text-lg font-semibold">Find KQ flights</h2></div>
            <form onSubmit={submitSearch} className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm">From (airport code)<input required maxLength={3} className={fieldClass()} placeholder="NBO" value={searchOrigin} onChange={(event) => setSearchOrigin(event.target.value.toUpperCase())} /></label>
              <label className="text-sm">To (airport code)<input required maxLength={3} className={fieldClass()} placeholder="LHR" value={searchDestination} onChange={(event) => setSearchDestination(event.target.value.toUpperCase())} /></label>
              <label className="text-sm">Departure date<input required type="date" className={fieldClass()} value={searchDeparture} onChange={(event) => setSearchDeparture(event.target.value)} /></label>
              <label className="text-sm">Return date (optional)<input type="date" min={searchDeparture || undefined} className={fieldClass()} value={searchReturn} onChange={(event) => setSearchReturn(event.target.value)} /></label>
              <label className="text-sm">Adults<input required type="number" min={1} max={9} className={fieldClass()} value={searchAdults} onChange={(event) => setSearchAdults(Number(event.target.value))} /></label>
              <div className="flex items-end"><Button type="submit" disabled={busy} className="w-full"><Search />Search KQ</Button></div>
            </form>
            {searchResult && <div className="mt-4 space-y-3" role="status">
              <p className="text-sm">{searchResult.message}</p>
              <p className="text-xs text-muted-foreground">{searchResult.source ? `Source: ${searchResult.source} · ` : ""}Checked {formatDateTime(searchResult.checked_at)}</p>
              {searchResult.offers.map((offer) => <OfferCard key={offer.offer_id} offer={offer} />)}
              {(!searchResult.available || searchResult.offers.length === 0) && <a href={searchResult.booking_url || KQ_BOOKING_URL} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline">Continue on Kenya Airways <ExternalLink className="h-4 w-4" /></a>}
            </div>}
          </section>

          <section className="rounded-xl border bg-card p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2"><Search className="h-5 w-5" /><h2 className="text-lg font-semibold">Check flight status</h2></div>
            <form onSubmit={submitStatus} className="grid gap-3 sm:grid-cols-2">
              <label className="text-sm">KQ flight number<input required pattern="[Kk][Qq][0-9]{1,4}[A-Za-z]?" className={fieldClass()} placeholder="KQ100" value={statusFlight} onChange={(event) => setStatusFlight(event.target.value.toUpperCase())} /></label>
              <label className="text-sm">Departure date<input required type="date" className={fieldClass()} value={statusDate} onChange={(event) => setStatusDate(event.target.value)} /></label>
              <div className="sm:col-span-2"><Button type="submit" disabled={busy} className="w-full"><Search />Check status</Button></div>
            </form>
            {statusResult && <div className="mt-4 rounded-lg border bg-background p-4" role="status">
              <p className="text-sm">{statusResult.message}</p>
              {statusResult.flight && <div className="mt-3 space-y-1 text-sm">
                <p className="font-semibold">{statusResult.flight.flight_number} · {statusResult.flight.status || "Status not provided"}</p>
                <p>{statusResult.flight.origin || "—"} → {statusResult.flight.destination || "—"}</p>
                <p>Departure: {formatDateTime(statusResult.flight.departure_at)}{statusResult.flight.terminal ? ` · Terminal ${statusResult.flight.terminal}` : ""}{statusResult.flight.gate ? ` · Gate ${statusResult.flight.gate}` : ""}</p>
                <p>Arrival: {formatDateTime(statusResult.flight.arrival_at)}</p>
              </div>}
              <p className="mt-3 text-xs text-muted-foreground">{statusResult.source ? `Source: ${statusResult.source} · ` : ""}Checked {formatDateTime(statusResult.checked_at)}</p>
              <a href={statusResult.official_status_url || KQ_STATUS_URL} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline">Verify on Kenya Airways <ExternalLink className="h-4 w-4" /></a>
            </div>}
          </section>
        </div>

        <section className="rounded-xl border bg-card p-5 shadow-sm">
          <div className="mb-4 flex items-center gap-2"><Plus className="h-5 w-5" /><h2 className="text-lg font-semibold">My trips and reminders</h2></div>
          {user?.role === "passenger" && token ? <>
            <form onSubmit={saveTrip} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <label className="text-sm">From<input required maxLength={3} className={fieldClass()} placeholder="NBO" value={tripOrigin} onChange={(event) => setTripOrigin(event.target.value.toUpperCase())} /></label>
              <label className="text-sm">To<input required maxLength={3} className={fieldClass()} placeholder="MBA" value={tripDestination} onChange={(event) => setTripDestination(event.target.value.toUpperCase())} /></label>
              <label className="text-sm">Departure<input required type="date" className={fieldClass()} value={tripDeparture} onChange={(event) => setTripDeparture(event.target.value)} /></label>
              <label className="text-sm">Return (optional)<input type="date" min={tripDeparture || undefined} className={fieldClass()} value={tripReturn} onChange={(event) => setTripReturn(event.target.value)} /></label>
              <label className="text-sm">Flight number (optional)<input className={fieldClass()} placeholder="KQ100" value={tripFlight} onChange={(event) => setTripFlight(event.target.value.toUpperCase())} /></label>
              <div className="sm:col-span-2 lg:col-span-5"><Button type="submit" disabled={busy}><Plus />Save trip</Button><p className="mt-2 text-xs text-muted-foreground">Do not enter a booking reference, passport details, or payment information.</p></div>
            </form>
            <div className="mt-6 space-y-4">
              {trips.length === 0 && <p className="rounded-lg border border-dashed p-5 text-sm text-muted-foreground">No saved trips yet. Save an itinerary to keep its reminders here.</p>}
              {trips.map((trip) => <article key={trip.trip_id} className="rounded-lg border p-4 bg-background">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold">{trip.label || `${trip.origin} → ${trip.destination}`}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{formatDate(trip.departure_date)}{trip.return_date ? ` – ${formatDate(trip.return_date)}` : " · One way"}{trip.flight_number ? ` · ${trip.flight_number}` : ""}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void triggerTestAlert(trip.trip_id)}
                      disabled={busy}
                      title="Send real email flight alert & advisory"
                    >
                      <Mail className="h-3.5 w-3.5 mr-1 text-primary" />
                      Email Alert
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => void deleteTrip(trip.trip_id)} aria-label="Delete trip"><Trash2 className="h-4 w-4" /></Button>
                  </div>
                </div>
                {trip.reminders.length > 0 && <ul className="mt-4 space-y-2">
                  {trip.reminders.map((reminder) => <li key={reminder.reminder_id} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-muted/50 px-3 py-2 text-sm">
                    <label className="flex items-center gap-2"><input type="checkbox" checked={reminder.completed} onChange={(event) => void updateReminder(trip.trip_id, reminder.reminder_id, event.target.checked)} /><span className={reminder.completed ? "line-through text-muted-foreground" : ""}>{reminder.title} · {formatDateTime(reminder.remind_at)}</span></label>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        className="rounded p-1 text-muted-foreground hover:text-primary hover:bg-muted"
                        onClick={() => void triggerReminderTest(trip.trip_id, reminder.reminder_id)}
                        title="Send this reminder to email now"
                      >
                        <Send className="h-3.5 w-3.5" />
                      </button>
                      <button type="button" className="rounded p-1 text-muted-foreground hover:text-destructive hover:bg-muted" onClick={() => void deleteReminder(trip.trip_id, reminder.reminder_id)} aria-label="Delete reminder"><Trash2 className="h-3.5 w-3.5" /></button>
                    </div>
                  </li>)}
                </ul>}
                <form onSubmit={(event) => void createReminder(event, trip.trip_id)} className="mt-4 grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
                  <label className="sr-only" htmlFor={`reminder-title-${trip.trip_id}`}>Reminder title</label><input id={`reminder-title-${trip.trip_id}`} className={fieldClass()} placeholder="e.g. Check travel documents" value={reminderTitle[trip.trip_id] || ""} onChange={(event) => setReminderTitle((current) => ({ ...current, [trip.trip_id]: event.target.value }))} />
                  <label className="sr-only" htmlFor={`reminder-time-${trip.trip_id}`}>Reminder date and time</label><input id={`reminder-time-${trip.trip_id}`} required type="datetime-local" className={fieldClass()} value={reminderTime[trip.trip_id] || ""} onChange={(event) => setReminderTime((current) => ({ ...current, [trip.trip_id]: event.target.value }))} />
                  <Button type="submit" variant="outline"><Bell />Add reminder</Button>
                </form>
              </article>)}
            </div>
          </> : <div className="rounded-lg border border-dashed p-5 text-sm text-muted-foreground">Sign in or create a passenger account to save trips and reminders. <Link href="/login" className="font-medium text-primary hover:underline">Sign in</Link> · <Link href="/register" className="font-medium text-primary hover:underline">Create account</Link></div>}
        </section>

        <footer className="rounded-lg bg-muted p-4 text-xs text-muted-foreground">Flight options and status depend on provider coverage and may change. This assistant does not book, change, or cancel flights. Complete those actions through Kenya Airways.</footer>
      </div>
    </main>
  );
}
