export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

export interface UserProfile {
  user_id: string;
  identifier: string;
  role: string;
  full_name: string | null;
}

export interface TokenResponse extends UserProfile {
  access_token: string;
  token_type: string;
}

export interface Citation {
  chunk_id: string;
  document_source: string;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  response: string;
  sources?: string[];
  citations?: Citation[];
}

export interface HistorySummary {
  conversation_id: string;
  session_id: string;
  created_at: string;
  system_variant: string;
  message_count: number;
  last_message: string | null;
}

export interface HistoryMessage {
  message_id: string;
  conversation_id: string;
  role: string;
  content: string;
  created_at: string;
  retrieval_metadata?: Array<{
    document_source: string;
    chunk_id: string;
  }>;
}

export interface HistoryDetail {
  conversation_id: string;
  session_id: string;
  created_at: string;
  system_variant: string;
  messages: HistoryMessage[];
}

export interface DocumentRecord {
  upload_id: string;
  filename: string;
  file_size_bytes: number | null;
  chunk_count: number;
  status: string;
  uploaded_at: string;
}

export interface UploadResponse {
  message: string;
  files_indexed: string[];
  chunk_counts: Array<{ filename: string; chunk_count: number }>;
  uploaded_by: string;
}

export interface StaffAccountRecord {
  staff_id: string;
  username: string;
  full_name: string | null;
  role: string;
  created_at: string;
}

export interface FlightStatusResult {
  available: boolean;
  source: string | null;
  checked_at: string;
  message: string;
  official_status_url: string;
  flight: null | {
    flight_number: string;
    flight_date: string;
    status: string | null;
    origin: string | null;
    destination: string | null;
    departure_at: string | null;
    arrival_at: string | null;
    terminal: string | null;
    gate: string | null;
  };
}

export interface FlightOfferResult {
  offer_id: string;
  price: string;
  currency: string;
  validating_airline: string;
  bookable_at_source: boolean;
  segments: Array<{
    carrier_code: string;
    flight_number: string;
    origin: string;
    destination: string;
    departure_at: string | null;
    arrival_at: string | null;
  }>;
}

export interface FlightSearchResult {
  available: boolean;
  source: string | null;
  checked_at: string;
  message: string;
  booking_url: string;
  offers: FlightOfferResult[];
}

export interface TripReminder {
  reminder_id: string;
  trip_id: string;
  title: string;
  remind_at: string;
  completed: boolean;
}

export interface SavedTrip {
  trip_id: string;
  origin: string;
  destination: string;
  departure_date: string;
  return_date: string | null;
  flight_number: string | null;
  label: string | null;
  created_at: string;
  reminders: TripReminder[];
}

export interface TripAssistantResult {
  response: string;
  actions: Array<{ tool: string; result: Record<string, unknown> }>;
  sources: string[];
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const headers = new Headers(options.headers);
  const isFormData =
    typeof FormData !== "undefined" && options.body instanceof FormData;

  if (options.body && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
    });
  } catch {
    throw new Error(
      `Could not reach the backend at ${API_BASE_URL}. Check that the API is running.`,
    );
  }

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : await response.text();

  if (!response.ok) {
    const detail =
      payload && typeof payload === "object"
        ? "detail" in payload
          ? payload.detail
          : "error" in payload
            ? payload.error
            : null
        : null;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg || String(item)).join(" ")
      : typeof detail === "string"
        ? detail
        : `Request failed (${response.status}).`;
    throw new Error(message);
  }

  return payload as T;
}
