"""Query handler module to execute the LLM chain with retrieved context."""

import math
import re
from collections import Counter

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage

from ..logger import logger
from .policy_sources import is_verified_policy_source

KQ_BOOKING_PAGE = "https://www.kenya-airways.com/en-us/book-a-flight/"
KQ_STATUS_PAGE = "https://www.kenya-airways.com/en/book-manage/flight-status/"
KQ_MANAGE_PAGE = "https://www.kenya-airways.com/en/book-manage/"
KQ_CHECKIN_PAGE = "https://www.kenya-airways.com/en/book-manage/post-booking/check-in/"


def get_kq_booking_guidance(user_input: str, conversation_history: list = None):
    """Return a direct KQ hand-off only when the passenger asks for flight help."""
    question = user_input.casefold()
    previous_assistant_messages = [
        content.casefold()
        for role, content in conversation_history or []
        if role == "assistant" and isinstance(content, str)
    ]
    is_waiting_for_flight_intent = (
        previous_assistant_messages
        and "are you looking to **book a new flight**"
        in previous_assistant_messages[-1]
    )
    if is_waiting_for_flight_intent:
        short_answer = question.strip(" .!?\t\n")
        if short_answer in {"book", "booking", "new flight", "book a new flight"}:
            question = "book a flight"
        elif short_answer in {"status", "flight status", "check status"}:
            question = "flight status"
        elif short_answer in {
            "manage",
            "manage booking",
            "existing booking",
            "change",
            "cancel",
        }:
            question = "manage booking"
    asks_status = any(
        term in question
        for term in (
            "flight status",
            "status of kq",
            "status of my flight",
            "check my flight",
            "check flight status",
            "is my flight delayed",
            "has my flight landed",
            "flight arrival time",
        )
    )

    asks_manage = any(
        term in question
        for term in (
            "change booking",
            "change my booking",
            "manage booking",
            "manage my booking",
            "manage existing booking",
            "cancel my booking",
            "cancel my flight",
        )
    )
    asks_checkin = any(
        term in question
        for term in ("online check-in", "online check in", "check in for my flight")
    )

    asks_find_flights = any(
        term in question
        for term in (
            "find a flight",
            "find flights",
            "search flights",
            "available flights",
            "flight availability",
            "flight prices",
            "flight fares",
            "book me a flight",
            "i want to book",
            "i need to book",
            "new flight booking",
            "book a new flight",
            "new booking",
            "book a ticket",
            "buy a ticket",
        )
    )
    asks_how_to_book = any(
        term in question
        for term in (
            "how to book",
            "how do i book",
            "how can i book",
            "instructions on how to book",
            "booking a flight",
            "book a flight",
            "book flights",
        )
    )

    if asks_status:
        page_url = KQ_STATUS_PAGE
        page_name = "Flight Status"
        answer = (
            "For the current status of a Kenya Airways flight, check the "
            f"[official KQ Flight Status page]({page_url}). I can’t access KQ’s "
            "live status system from this chat."
        )
    elif asks_manage:
        page_url = KQ_MANAGE_PAGE
        page_name = "Manage Booking"
        answer = (
            "To change or manage an existing booking, continue on Kenya Airways’ "
            f"[Manage Booking page]({page_url}). You’ll need the booking details "
            "requested there; don’t share your booking reference or personal "
            "documents in this chat."
        )
    elif asks_checkin:
        page_url = KQ_CHECKIN_PAGE
        page_name = "Online Check-in"
        answer = (
            f"Use Kenya Airways’ [online check-in page]({page_url}) for current "
            "check-in availability and instructions."
        )
    elif asks_find_flights or asks_how_to_book:
        page_url = KQ_BOOKING_PAGE
        page_name = "Book a Flight"
        answer = (
            "I can help with KQ travel policies, but I can’t see live fares or "
            "availability. Search and complete the booking on Kenya Airways’ "
            f"[Book a Flight page]({page_url}). Enter your route, dates, and "
            "passenger details there to see current options."
        )
    else:
        asks_general_flight_help = any(
            term in question
            for term in (
                "help me with my flight",
                "help with my flight",
                "help me plan my trip",
                "help me plan a trip",
                "help with my trip",
                "plan my flight",
            )
        )
        if not asks_general_flight_help:
            return None
        page_name = "Flight help"
        answer = (
            "Sure. Are you looking to **book a new flight**, **check a flight’s "
            "status**, or **manage an existing booking**? I’ll point you to the "
            "right Kenya Airways page."
        )
        page_url = "https://www.kenya-airways.com/en/book-manage/"

    document = Document(
        page_content=f"Official Kenya Airways {page_name} page: {page_url}",
        metadata={"source": f"Kenya Airways — {page_name} (official website)"},
    )
    return {"answer": answer, "document": document}


def build_retrieval_query(user_input: str, conversation_history: list = None) -> str:
    """Add recent passenger questions to resolve follow-up references."""
    previous_questions = [
        content for role, content in conversation_history or [] if role == "user"
    ][-2:]
    if not previous_questions:
        return user_input
    return "\n".join([*previous_questions, user_input])


def build_retrieval_queries(user_input: str, conversation_history: list = None) -> list:
    """Add a table-oriented search for baggage allowance questions."""
    primary_query = build_retrieval_query(user_input, conversation_history)
    normalized_question = user_input.casefold()
    asks_about_allowance = any(
        term in normalized_question
        for term in ("allowance", "how many bags", "bag limit")
    )
    asks_about_baggage = any(
        term in normalized_question for term in ("baggage", "luggage", "checked bag")
    )
    asks_about_carry_on = any(
        term in normalized_question for term in ("carry-on", "carry on", "hand baggage")
    )
    if asks_about_carry_on:
        hand_baggage_query = (
            "Hand Baggage cabin baggage carry-on size weight allowance "
            f"{primary_query}"
        )
        return [hand_baggage_query, primary_query]
    if asks_about_baggage and asks_about_allowance:
        table_query = (
            "Free Checked Baggage Allowance ROUTING FROM TO BUSINESS CLASS ECONOMY "
            f"route cabin pieces kilograms {primary_query}"
        )
        return [table_query, primary_query]
    return [primary_query]


def rank_documents_lexically(query: str, documents: list, limit: int = 4) -> list:
    """Rank a modest curated corpus with BM25 to complement vector similarity."""
    stop_words = {
        "about",
        "and",
        "are",
        "does",
        "for",
        "from",
        "how",
        "into",
        "is",
        "may",
        "my",
        "of",
        "the",
        "this",
        "to",
        "what",
        "when",
        "with",
        "you",
        "your",
    }

    def tokenize(text: str) -> list:
        return [
            token
            for token in re.findall(r"[a-z0-9]+", text.casefold())
            if len(token) > 2 and token not in stop_words
        ]

    query_terms = tokenize(query)
    if not query_terms or not documents:
        return []

    tokenized_documents = [tokenize(doc.page_content) for doc in documents]
    average_length = sum(map(len, tokenized_documents)) / max(len(documents), 1)
    document_frequencies = Counter(
        term for terms in tokenized_documents for term in set(terms)
    )
    term_frequencies = [Counter(terms) for terms in tokenized_documents]
    scores = []
    for index, frequencies in enumerate(term_frequencies):
        document_length = len(tokenized_documents[index])
        score = 0.0
        for term in query_terms:
            frequency = frequencies[term]
            if not frequency:
                continue
            inverse_frequency = math.log(
                1
                + (len(documents) - document_frequencies[term] + 0.5)
                / (document_frequencies[term] + 0.5)
            )
            denominator = frequency + 1.5 * (
                1 - 0.75 + 0.75 * document_length / max(average_length, 1)
            )
            score += inverse_frequency * frequency * 2.5 / denominator
        if score:
            scores.append((score, index))

    scores.sort(reverse=True)
    return [documents[index] for _, index in scores[:limit]]


def retrieve_policy_documents(
    vectorstore,
    user_input: str,
    conversation_history: list = None,
    limit: int = 8,
) -> list[Document]:
    """Use hybrid search and collapse duplicates before building the context."""
    retrieval_queries = build_retrieval_queries(user_input, conversation_history)
    indexed = vectorstore.get(include=["documents", "metadatas"])
    indexed_documents = []
    indexed_keys = set()
    for content, metadata in zip(
        indexed.get("documents") or [], indexed.get("metadatas") or []
    ):
        if not content:
            continue
        metadata = metadata or {}
        if not is_verified_policy_source(metadata.get("source")):
            continue
        content_key = " ".join(content.split()).casefold()
        if content_key in indexed_keys:
            continue
        indexed_keys.add(content_key)
        indexed_documents.append(Document(page_content=content, metadata=metadata))

    source_docs = []
    seen_chunks = set()

    def add_if_new(doc: Document) -> None:
        if not is_verified_policy_source(doc.metadata.get("source", "")):
            return
        content_key = " ".join(doc.page_content.split()).casefold()
        if content_key and content_key not in seen_chunks:
            seen_chunks.add(content_key)
            source_docs.append(doc)

    for doc in rank_documents_lexically(
        retrieval_queries[0], indexed_documents, limit=4
    ):
        add_if_new(doc)

    # Extra candidates let the filter skip stale PDFs and repeated chunks without
    # allowing them to occupy all top-k results and hide a relevant HTML table.
    candidate_count = max(limit * 4, 20)
    for retrieval_query in retrieval_queries:
        try:
            candidates = vectorstore.similarity_search(
                retrieval_query, k=candidate_count
            )
        except TypeError:
            candidates = vectorstore.similarity_search(retrieval_query, k=4)
        for doc in candidates:
            add_if_new(doc)
            if len(source_docs) >= limit:
                return source_docs
    return source_docs


def format_policy_context(source_docs: list[Document]) -> str:
    """Format retrieved chunks with their source names for grounded answering."""
    return "\n\n---\n\n".join(
        f"Source: {doc.metadata.get('source', 'Policy document')}\n"
        f"{doc.page_content}"
        for doc in source_docs
    )


def query_chain(
    chain,
    user_input: str,
    context: str = "",
    source_docs: list = None,
    conversation_history: list = None,
) -> dict:
    """Executes the LLM chain passing user input and retrieved context."""
    try:
        logger.debug(f"Running chain for input: {user_input}")
        source_docs = source_docs or []
        chat_history = []
        for role, content in conversation_history or []:
            if role == "user":
                chat_history.append(HumanMessage(content=content))
            elif role == "assistant":
                chat_history.append(AIMessage(content=content))

        # Run modern LCEL chain with question and context
        if hasattr(chain, "invoke"):
            result = chain.invoke(
                {
                    "question": user_input,
                    "context": context,
                    "chat_history": chat_history,
                }
            )
        else:
            result = chain(
                {
                    "question": user_input,
                    "context": context,
                    "chat_history": chat_history,
                }
            )

        if isinstance(result, dict):
            answer = (
                result.get("result")
                or result.get("answer")
                or result.get("output_text")
                or ""
            )
        else:
            answer = getattr(result, "content", result)

        if isinstance(answer, list):
            answer = "".join(
                item.get("text", "")
                for item in answer
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            )
        elif not isinstance(answer, str):
            answer = str(answer or "")
        answer = answer.strip()
        if not answer:
            logger.error("The language model returned an empty answer.")
            return {"error": "The language model returned an empty answer."}

        # Extract source filenames / metadata from retrieved documents
        sources = []
        for doc in source_docs:
            if hasattr(doc, "metadata") and doc.metadata:
                src = doc.metadata.get("source") or doc.metadata.get("filename")
                if src and src not in sources:
                    sources.append(src)

        response = {
            "response": answer,
            "sources": sources,
        }
        logger.debug(f"Chain response generated: {response}")
        return response
    except Exception as e:
        logger.error(f"Error running chain: {e}")
        return {"error": str(e)}
