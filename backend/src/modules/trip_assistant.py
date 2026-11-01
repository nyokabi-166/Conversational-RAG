"""Local tool-calling orchestration for passenger trip questions."""

import json
import os
from datetime import date
from typing import Any

from langchain_chroma import Chroma
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from src.modules.flight_services import get_flight_status as lookup_flight_status
from src.modules.flight_services import search_kq_flights as lookup_kq_flights
from src.modules.llm import get_chat_model
from src.modules.load_vesctorstore import PERSIST_DIR
from src.rag_pipeline import MiniLMEmbeddings
from src.schemas.trips import FlightSearchRequest, FlightStatusRequest

SYSTEM_PROMPT = """You are a careful Kenya Airways trip assistant.
Use get_kq_flight_status for any current flight status and search_kq_flights for
requests to find flight options. Never invent flight status, schedules, fares,
availability, or booking success. Ask concise follow-up questions when required
flight details are missing. If a provider has no verified KQ data, explain that
and direct the passenger to the supplied official Kenya Airways link. You cannot
book, change, or cancel flights. Tell passengers to review and complete those
actions on Kenya Airways. For policy claims, use only supplied indexed policy
context. If none is supplied, direct the passenger to the policy chat. Do not
pretend live flight tools are policy evidence.
"""


@tool
def get_kq_flight_status(flight_number: str, departure_date: str) -> str:
    """Get current status for a KQ flight using its number (e.g. KQ100) and date (YYYY-MM-DD)."""
    request = FlightStatusRequest(
        flight_number=flight_number, departure_date=date.fromisoformat(departure_date)
    )
    result = lookup_flight_status(request.flight_number, request.departure_date)
    return json.dumps(result, default=str)


@tool
def search_kq_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = "",
    adults: int = 1,
    travel_class: str = "ECONOMY",
) -> str:
    """Search for KQ-only flight offers using three-letter airport codes and travel dates."""
    request = FlightSearchRequest(
        origin=origin,
        destination=destination,
        departure_date=date.fromisoformat(departure_date),
        return_date=date.fromisoformat(return_date) if return_date else None,
        adults=adults,
        travel_class=travel_class,
    )
    return json.dumps(lookup_kq_flights(request), default=str)


TOOLS = {
    get_kq_flight_status.name: get_kq_flight_status,
    search_kq_flights.name: search_kq_flights,
}
POLICY_TERMS = (
    "baggage",
    "bag allowance",
    "carry-on",
    "carry on",
    "luggage",
    "refund",
    "cancel",
    "cancellation",
    "change my booking",
    "change booking",
    "check-in",
    "check in",
    "travel document",
    "documents",
    "visa",
    "special assistance",
    "policy",
    "fare rules",
)


def _action_result(tool_name: str, raw_result: Any) -> dict:
    try:
        parsed = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
    except (TypeError, json.JSONDecodeError):
        parsed = {"message": "The provider returned an unreadable response."}
    return {"tool": tool_name, "result": parsed}


def answer_trip_question(message: str, history: list) -> dict:
    """Run one bounded model/tool cycle and return auditable provider actions."""
    context = ""
    sources = []
    needs_policy_context = any(term in message.lower() for term in POLICY_TERMS)
    if needs_policy_context and os.path.exists(PERSIST_DIR) and os.listdir(PERSIST_DIR):
        store = Chroma(
            persist_directory=PERSIST_DIR,
            embedding_function=MiniLMEmbeddings(),
        )
        documents = store.similarity_search(message, k=4)
        context = "\n\n---\n\n".join(document.page_content for document in documents)
        sources = list(
            dict.fromkeys(
                document.metadata.get("source", "Policy document")
                for document in documents
                if document.metadata
            )
        )
    model = get_chat_model().bind_tools(
        [get_kq_flight_status, search_kq_flights], parallel_tool_calls=False
    )
    messages = [
        SystemMessage(
            content=(
                f"{SYSTEM_PROMPT}\n\nIndexed policy context:\n"
                f"{context or '[No relevant policy context found.]'}"
            )
        )
    ]
    for entry in history[-8:]:
        if not isinstance(entry, dict) or entry.get("role") not in {
            "user",
            "assistant",
        }:
            continue
        content = entry.get("content")
        if not isinstance(content, str):
            continue
        messages.append(
            HumanMessage(content=content)
            if entry["role"] == "user"
            else AIMessage(content=content)
        )
    messages.append(HumanMessage(content=message))

    actions = []
    for _ in range(3):
        response = model.invoke(messages)
        tool_calls = getattr(response, "tool_calls", []) or []
        if not tool_calls:
            return {
                "response": str(response.content or ""),
                "actions": actions,
                "sources": sources,
            }
        messages.append(response)
        for call in tool_calls:
            name = call.get("name")
            tool_instance = TOOLS.get(name)
            if tool_instance is None:
                result = {"error": "Unsupported tool request."}
                raw_result = json.dumps(result)
            else:
                try:
                    raw_result = tool_instance.invoke(call.get("args") or {})
                    result = _action_result(name, raw_result)["result"]
                except Exception as exc:  # tool input validation / provider adapter
                    result = {"error": str(exc)}
                    raw_result = json.dumps(result)
            actions.append({"tool": name or "unknown", "result": result})
            messages.append(
                ToolMessage(
                    content=(
                        raw_result
                        if isinstance(raw_result, str)
                        else json.dumps(raw_result)
                    ),
                    tool_call_id=call.get("id", "tool-call"),
                )
            )
    final = model.invoke(messages)
    return {
        "response": str(final.content or ""),
        "actions": actions,
        "sources": sources,
    }
