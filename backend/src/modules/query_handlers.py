"""Query handler module to execute the LLM chain with retrieved context."""

import os
import math
import re
from collections import Counter

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage

from ..logger import logger
from .answer_quality import (
    assess_context_coverage,
    build_missing_details_note,
    detail_hints_enabled,
    guard_enabled,
    refusal_response,
    corpus_term_set,
)
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
        metadata={
            "source": f"Kenya Airways — {page_name} (official website)",
            "title": f"Kenya Airways — {page_name}",
            "url": page_url,
        },
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


# Topic keyword expansions, ordered most specific to most generic so the first
# matched topic leads both the vector queries and the lexical ranking query.
# Each entry: (triggers, keywords, skip_if_baggage_intent). Keywords echo
# vocabulary from the source page titles/headings so the expansion anchors
# retrieval on the right page.
TOPIC_QUERY_RULES: list[tuple[tuple[str, ...], str, bool]] = [
    (
        ("pet", "dog", "cat ", "animal", "golf", "ski", "bicycle",
         "special baggage"),
        "Special Baggage pet carriage animal sports equipment acceptance",
        False,
    ),
    (
        ("carry-on", "carry on", "hand baggage", "cabin bag", "in the cabin"),
        "Hand Baggage cabin baggage carry-on size weight allowance",
        False,
    ),
    (
        ("excess baggage", "excess bag", "overweight", "extra bag",
         "too much baggage"),
        "excess baggage charges fees overweight additional piece",
        False,
    ),
    (
        ("visa", "passport", "travel document", "documents", "papers",
         "vaccination", "health requirement"),
        "Visa and Health Information travel requirements passport visa documents",
        False,
    ),
    (
        ("check in", "check-in", "boarding time", "how early", "airport early",
         "boarding pass"),
        "Online Check-in check-in window opening time international domestic counter",
        True,
    ),
    (
        ("pregnan", "heart condition", "medical", "fit to fly", "medif",
         "special assistance", "mobility", "oxygen", "disab"),
        "Medical and Special Needs medical clearance MEDIF condition assistance",
        False,
    ),
    (
        ("refund", "cancel my", "cancellation", "money back"),
        "refund policy cancellation non-refundable ticket money back",
        False,
    ),
    (
        ("change my flight", "change date", "change the date", "rebook",
         "reschedule", "change booking", "modify my flight", "manage booking"),
        "Manage My Booking change flight dates rebooking modify reservation",
        False,
    ),
    (
        ("overbook", "denied boarding", "compensation", "conditions of carriage",
         "liability", "delayed baggage"),
        "Conditions of Carriage denied boarding overbooking compensation liability",
        False,
    ),
    (
        ("allowance", "how many bags", "how many", "bag limit", "baggage",
         "luggage", "checked bag", "kilos", "kilo"),
        "Free Checked Baggage Allowance ROUTING FROM TO BUSINESS CLASS ECONOMY "
        "route cabin pieces kilograms",
        False,
    ),
]

# "check in" also appears in baggage phrasing ("how many kilos can I check
# in"); a baggage intent suppresses the check-in topic so the allowance table
# query keeps the lead.
BAGGAGE_INTENT_TERMS = (
    "kilos", "kilo", "how many", "allowance", "baggage", "luggage",
    "checked bag", "pounds", "kg",
)


RETRIEVAL_EXPANSION_MODE_ENV = "RETRIEVAL_EXPANSION_MODE"
RETRIEVAL_EXPANSION_MODES = ("topic", "conditional", "off")
# A question with this many content words or fewer is treated as under-specified
# (short, paraphrased or a follow-up) and relies on the topic expansion to lead.
UNDERSPECIFIED_MAX_CONTENT_WORDS = 5
_QUESTION_STOPWORDS = frozenset(
    "a an the and or but if of to in on at for from with by as is are was were be "
    "been am do does did can could may might should would will shall i me my we our "
    "you your it its this that these those what which who whom how when where why "
    "there here about any some into than then so not no yes please tell need want "
    "get go going".split()
)


def get_retrieval_expansion_mode() -> str:
    """Return the expansion mode from RETRIEVAL_EXPANSION_MODE.

    conditional (default): topic queries lead only for short or under-specified
    questions; topic: topic queries always lead; off: no expansion.
    """
    mode = (os.getenv(RETRIEVAL_EXPANSION_MODE_ENV) or "conditional").strip().lower()
    if mode not in RETRIEVAL_EXPANSION_MODES:
        raise ValueError(
            f"{RETRIEVAL_EXPANSION_MODE_ENV} must be one of "
            f"{', '.join(RETRIEVAL_EXPANSION_MODES)}, got {mode!r}."
        )
    return mode


def count_content_words(text: str) -> int:
    words = re.findall(r"[a-z0-9']+", (text or "").casefold())
    return sum(1 for word in words if len(word) > 2 and word not in _QUESTION_STOPWORDS)


def is_underspecified_question(user_input: str) -> bool:
    return count_content_words(user_input) <= UNDERSPECIFIED_MAX_CONTENT_WORDS


def build_retrieval_queries(user_input: str, conversation_history: list = None) -> list:
    """Add topic keyword queries so retrieval matches the right source page.

    Topics are detected on the combined query (previous questions + current
    question) so follow-up turns inherit the topic of the turn they extend.
    """
    primary_query = build_retrieval_query(user_input, conversation_history)
    search_text = primary_query.casefold()
    baggage_intent = any(term in search_text for term in BAGGAGE_INTENT_TERMS)
    topic_queries = []
    for triggers, keywords, skip_if_baggage_intent in TOPIC_QUERY_RULES:
        if skip_if_baggage_intent and baggage_intent:
            continue
        if any(trigger in search_text for trigger in triggers):
            topic_queries.append(f"{keywords} {primary_query}")
    if not topic_queries:
        return [primary_query]
    mode = get_retrieval_expansion_mode()
    if mode == "off":
        return [primary_query]
    if mode == "conditional" and not is_underspecified_question(user_input):
        # A detailed question carries its own vocabulary: its own query leads the
        # lexical ranking and the interleaved vector search; topic queries only add.
        return [primary_query, *topic_queries]
    return [*topic_queries, primary_query]


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


# Stems of the whole knowledge base, refreshed whenever retrieval sees a different
# index. The answerability guard uses it to spot question words no page contains.
_CORPUS_TERMS_CACHE: dict = {"key": None, "terms": None}


def get_corpus_terms() -> set[str] | None:
    return _CORPUS_TERMS_CACHE["terms"]


def _remember_corpus_terms(documents: list[Document]) -> None:
    key = (len(documents), sum(len(doc.page_content) for doc in documents))
    if _CORPUS_TERMS_CACHE["key"] != key:
        _CORPUS_TERMS_CACHE["terms"] = corpus_term_set(
            [doc.page_content for doc in documents]
        )
        _CORPUS_TERMS_CACHE["key"] = key


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

    _remember_corpus_terms(indexed_documents)

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
    # Candidates are merged round-robin across queries so one query cannot flood
    # every slot: a misfired topic query costs at most interleaved positions,
    # while its correct matches still surface early.
    candidate_count = max(limit * 4, 20)
    candidate_lists = []
    for retrieval_query in retrieval_queries:
        try:
            candidates = vectorstore.similarity_search(
                retrieval_query, k=candidate_count
            )
        except TypeError:
            candidates = vectorstore.similarity_search(retrieval_query, k=4)
        candidate_lists.append(candidates)
    longest = max((len(c) for c in candidate_lists), default=0)
    for depth in range(longest):
        for candidates in candidate_lists:
            if depth >= len(candidates):
                continue
            add_if_new(candidates[depth])
            if len(source_docs) >= limit:
                return source_docs
    return source_docs


def _display_source_name(source: str) -> str:
    """File name of a stored source without folders or the upload id prefix."""
    name = str(source or "").replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    return re.sub(r"^[0-9a-f]{32}_", "", name).strip()


_TITLE_BRAND_PREFIX = re.compile(r"^\s*kenya airways(?:\s+plc)?\s*\|\s*", re.IGNORECASE)


def _clean_page_title(title: str) -> str:
    """'Kenya Airways | Baggage Allowance' -> 'Baggage Allowance' for display."""
    return _TITLE_BRAND_PREFIX.sub("", title or "").strip()


def _page_info(doc: Document) -> dict:
    """Title and web address for a chunk: chunk metadata first, then the catalog."""
    from src.modules.load_vesctorstore import source_catalog_entry

    meta = doc.metadata or {}
    file_name = _display_source_name(meta.get("source") or meta.get("filename") or "")
    entry = source_catalog_entry(file_name)
    return {
        "file": file_name,
        "title": _clean_page_title(meta.get("title") or entry.get("title") or "")
        or file_name
        or "Policy document",
        "url": meta.get("url") or entry.get("url") or "",
    }


def format_policy_context(source_docs: list[Document]) -> str:
    """Number the retrieved chunks so the answer can cite them as [1], [2], ..."""
    return "\n\n---\n\n".join(
        f"[{number}] Page: {_page_info(doc)['title']}\n{doc.page_content}"
        for number, doc in enumerate(source_docs, start=1)
    )


_CITATION_PATTERN = re.compile(r"\s*\[(\d{1,2})\]")


def extract_citation_numbers(answer: str) -> list[int]:
    """Context numbers cited in the answer, in order of first appearance."""
    seen: list[int] = []
    for match in _CITATION_PATTERN.finditer(answer or ""):
        number = int(match.group(1))
        if number not in seen:
            seen.append(number)
    return seen


def strip_citation_markers(answer: str) -> str:
    """Remove [n] markers (kept for source links) from the passenger-facing text."""
    cleaned = _CITATION_PATTERN.sub("", answer or "")
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def build_source_links(
    source_docs: list[Document], cited_numbers: list[int], answer: str = "", max_links: int = 4
) -> list[dict]:
    """Pages the answer actually cited; an uncited answer gets no links.

    Older builds fell back to the top two retrieved pages, which made ungrounded
    answers look sourced. That fallback was removed: a link is only attached when
    the answer itself cites the passage.
    """
    from src.modules.prompts import NOT_FOUND_PHRASE

    if NOT_FOUND_PHRASE.casefold() in (answer or "").casefold():
        return []
    selected = [source_docs[n - 1] for n in cited_numbers if 1 <= n <= len(source_docs)]
    if not selected:
        logger.warning(
            "Answer has no [n] citations; returning no source links "
            "(%d retrieved chunks available).",
            len(source_docs or []),
        )
        return []
    links: list[dict] = []
    seen: set[str] = set()
    for doc in selected:
        info = _page_info(doc)
        if not info["file"] or info["file"] in seen:
            continue
        seen.add(info["file"])
        links.append(info)
        if len(links) >= max_links:
            break
    return links


def links_for_saved_sources(rows: list, max_links: int = 4) -> list[dict]:
    """Rebuild source links for saved history from stored (document_source, chunk_text).

    Saved retrieval rows hold only the source file name, so the title and web
    address come from the packaged source catalog. Official booking hand-offs are
    not in the catalog; their address is read back from the stored chunk text.
    """
    from src.modules.load_vesctorstore import source_catalog_entry

    links: list[dict] = []
    seen: set[str] = set()
    for source, chunk_text in rows:
        file_name = _display_source_name(source)
        if not file_name or file_name in seen:
            continue
        entry = source_catalog_entry(file_name)
        url = entry.get("url") or ""
        title = entry.get("title") or ""
        if not url:
            match = re.search(r"https?://[^\s)]+", chunk_text or "")
            url = match.group(0) if match else ""
            title = file_name.removesuffix(" (official website)")
        if not url:
            continue
        seen.add(file_name)
        links.append({"file": file_name, "title": title or file_name, "url": url})
        if len(links) >= max_links:
            break
    return links


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

        # Deterministic answerability guard: refuse before generating when the
        # retrieved pages contain none of the question's distinctive terms. Skipped
        # for legacy context-only calls (no source documents attached).
        if guard_enabled() and source_docs:
            coverage = assess_context_coverage(
                user_input,
                [doc.page_content for doc in source_docs],
                corpus_terms=get_corpus_terms(),
            )
            if coverage["refuse"]:
                logger.info(
                    "Refused by lexical answerability guard (%s): %s",
                    coverage["reason"],
                    ", ".join(coverage["missing"][:5]) or "no terms",
                )
                response = refusal_response(source_docs)
                response["coverage"] = coverage
                logger.debug(f"Chain response generated: {response}")
                return response
        elif guard_enabled() and not context:
            response = refusal_response([])
            response["coverage"] = {
                "reason": "no retrieved context",
                "coverage": 0.0,
            }
            logger.info("Refused by lexical answerability guard: no retrieved context")
            return response

        missing_details = (
            build_missing_details_note(user_input, conversation_history)
            if detail_hints_enabled()
            else ""
        )

        # Run modern LCEL chain with question and context
        if hasattr(chain, "invoke"):
            result = chain.invoke(
                {
                    "question": user_input,
                    "context": context,
                    "chat_history": chat_history,
                    "missing_details": missing_details,
                }
            )
        else:
            result = chain(
                {
                    "question": user_input,
                    "context": context,
                    "chat_history": chat_history,
                    "missing_details": missing_details,
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

        # Pages the answer actually used, from its [n] citations
        cited = extract_citation_numbers(answer)
        source_links = build_source_links(source_docs, cited, answer)
        answer = strip_citation_markers(answer)
        retrieved_sources = []
        for doc in source_docs:
            if hasattr(doc, "metadata") and doc.metadata:
                src = doc.metadata.get("source") or doc.metadata.get("filename")
                if src and src not in retrieved_sources:
                    retrieved_sources.append(src)

        response = {
            "response": answer,
            "sources": [link["file"] for link in source_links],
            "source_links": source_links,
            "retrieved_sources": retrieved_sources,
        }
        logger.debug(f"Chain response generated: {response}")
        return response
    except Exception as e:
        logger.error(f"Error running chain: {e}")
        return {"error": str(e)}
