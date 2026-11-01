"""Query handler module to execute the LLM chain with retrieved context."""

import math
import re
from collections import Counter

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage

from ..logger import logger

KQ_BOOKING_PAGE = "https://www.kenya-airways.com/en-us/book-a-flight/"


def get_kq_booking_guidance(user_input: str):
    """Return verified, actionable booking guidance for direct booking how-to asks."""
    question = user_input.casefold()
    if any(
        term in question
        for term in (
            "change booking",
            "change my booking",
            "manage booking",
            "flight status",
            "check my flight",
            "cancel my booking",
            "cancel flight",
        )
    ):
        return None

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
    if not asks_how_to_book:
        return None

    content = (
        "Official Kenya Airways online booking instructions: On the Book a Flight "
        "page, enter the departure and arrival city or airport. Choose one-way, "
        "return, or multi-city; enter travel dates, cabin class, and passenger count; "
        "then select Search Flights. Compare the available fares and continue on the "
        "Kenya Airways website to complete the booking. Official source: "
        f"{KQ_BOOKING_PAGE}"
    )
    answer = (
        f"To book a Kenya Airways flight, go to [Book a Flight]({KQ_BOOKING_PAGE}). "
        "Enter your departure and arrival cities or airports, choose one-way, return, "
        "or multi-city, then add your travel dates, cabin class, and passenger count. "
        "Select **Search Flights**, compare the available fares, and continue on the "
        "Kenya Airways website to complete your booking. This assistant does not "
        "purchase tickets or take payment."
    )
    source = Document(
        page_content=content,
        metadata={"source": "Kenya Airways — Book a Flight (official website)"},
    )
    return {"answer": answer, "document": source}


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
