"""Deterministic helpers for answer quality.

Two jobs:

1. ``detect_missing_details`` spots baggage questions that do not say the cabin
   class or route, so the prompt can forbid the model from assuming them.
2. ``assess_context_coverage`` is the lexical answerability guard. It refuses only
   when a distinctive question term appears nowhere in the whole knowledge base
   (after normalization, stemming and synonym folding). A retrieval miss no longer
   causes a refusal: the corpus vocabulary decides what the pages can answer.

Both functions are pure and deterministic; no model calls are made.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.modules.prompts import NOT_FOUND_PHRASE

# ---------------------------------------------------------------------------
# Shared vocabulary
# ---------------------------------------------------------------------------

_STOPWORDS = set(
    """a an the and or but if then than so of to in on at by for from with without
    about is are was were be been being am do does did done have has had having can
    could should would will shall may might must i me my we our you your he she it
    they them their this that these those there here what which who whom whose when
    where why how much many more most other some any no not yes please tell know need
    want get got give show help allowed allow possible able while after before during
    over under between into onto per via around happen happens happened take""".split()
)

# Framing words describe how the question is phrased, not what it is about
# ("according to the legal page", "someone else", "against my allowance"). Keeping
# them out of the vocabulary prevents retrieval misses from becoming refusals.
_STOPWORDS |= set(
    """page pages site website web say says said mention mentions mentioned
    according accord someone somebody anyone anybody else also same just only still
    already even ever very really against among within upon toward towards bring
    brings list listed overview topic topics cover covers covered besides beside use
    used uses link links define defines defined defin compare compared comparison
    compar rely relied relying reli example examples exampl found find quick quickly
    position posit watch noted versus versu sit sitting old don dont situation situ
    short built available availability avail""".split()
)

# Words that are true of every airline question, so they cannot show whether the
# retrieved pages actually cover the topic.
_GENERIC_TERMS = {
    "flight",
    "fly",
    "flying",
    "travel",
    "travelling",
    "traveling",
    "trip",
    "journey",
    "passenger",
    "kenya",
    "airway",
    "kq",
    "airline",
    "economy",
    "business",
    "premium",
    "first",
    "coach",
    "cabin",
    "domestic",
    "international",
    "route",
    "region",
    "africa",
    "europe",
    "america",
    "asia",
    "middle",
    "east",
    "return",
    "price",
    "free",
    "pay",
    "rule",
}

# Places that can appear as a route parameter in an answerable question even when
# the page itself talks about a whole region. Lower-case input is still recognised.
_PLACE_TERMS = {
    "nairobi",
    "mombasa",
    "kisumu",
    "malindi",
    "dubai",
    "london",
    "mumbai",
    "bangkok",
    "guangzhou",
    "accra",
    "monrovia",
    "abidjan",
    "dakar",
    "johannesburg",
    "cape",
    "cairo",
    "amsterdam",
    "paris",
    "newyork",
    "new",
    "york",
    "boston",
    "toronto",
    "zanzibar",
    "kigali",
    "entebbe",
    "dar",
    "salaam",
}

_NUMBER_WORDS = set(
    """zero one two three four five six seven eight nine ten eleven twelve thirteen
    fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty
    sixty seventy eighty ninety hundred thousand million billion""".split()
)

# Fold question words onto the vocabulary the pages use. Keys are stems. Mappings
# here are deliberately topical: only add a synonym when the two words really ask
# the same thing, otherwise the guard would answer a question the corpus cannot.
_SYNONYMS = {
    "notification": "report",
    "notified": "report",
    "notify": "report",
    "reliable": "guarantee",
    "reliability": "guarantee",
    "approval": "approve",
    "approved": "approve",
    "approv": "approve",
    "perk": "benefit",
    "perks": "benefit",
    "transferable": "transfer",
    "transferred": "transfer",
    "transferring": "transfer",
    "strict": "restrict",
    "stricter": "restrict",
    "incorrect": "wrong",
    "erroneous": "wrong",
    "euro": "eur",
    "euros": "eur",
    "failure": "fail",
    "failed": "fail",
    "payer": "pay",
    "payers": "pay",
    "disposal": "dispose",
    "disposed": "dispose",
    "dispos": "dispose",
    "aids": "aid",
    "bag": "baggage",
    "bags": "baggage",
    "suitcase": "baggage",
    "suitcases": "baggage",
    "luggage": "baggage",
    "baggages": "baggage",
    "kilo": "weight",
    "kilos": "weight",
    "kilogram": "weight",
    "kilograms": "weight",
    "kg": "weight",
    "kgs": "weight",
    "weigh": "weight",
    "weighs": "weight",
    "heavy": "weight",
    "paper": "document",
    "papers": "document",
    "paperwork": "document",
    "document": "document",
    "documents": "document",
    "documentation": "document",
    "doc": "document",
    "docs": "document",
    "refund": "refund",
    "refunds": "refund",
    "reimbursement": "refund",
    "rebook": "rebooking",
    "rebooking": "rebooking",
    "reschedule": "rebooking",
    "change": "rebooking",
    "pet": "pet",
    "pets": "pet",
    "dog": "pet",
    "dogs": "pet",
    "cat": "pet",
    "cats": "pet",
    "animal": "pet",
    "animals": "pet",
    "internet": "internet",
    "wifi": "internet",
    "meal": "meal",
    "meals": "meal",
    "food": "meal",
    "catering": "meal",
    "fee": "price",
    "fees": "price",
    "cost": "price",
    "costs": "price",
    "price": "price",
    "prices": "price",
    "charge": "price",
    "charges": "price",
    "pregnant": "pregnancy",
    "pregnancy": "pregnancy",
    "medical": "medical",
    "health": "medical",
    "deni": "denied",
    "deny": "denied",
    "overbook": "denied",
    "overbooking": "denied",
    "overbooked": "denied",
    "early": "hour",
    "internationally": "international",
}


def _stem(word: str) -> str:
    w = word.casefold().strip("'-")
    w = _SYNONYMS.get(w, w)
    if w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"
    for suffix in (
        "ations",
        "ation",
        "isons",
        "ison",
        "ions",
        "ion",
        "ments",
        "ment",
        "ables",
        "able",
        "ings",
        "ing",
        "ers",
        "er",
        "ed",
        "es",
        "s",
    ):
        margin = 2 if suffix in {"s", "es"} else 3
        if suffix == "s" and w.endswith("ss"):
            continue
        if len(w) > len(suffix) + margin and w.endswith(suffix):
            w = w[: -len(suffix)]
            break
    w = re.sub(r"([bcdfghjklmnpqrstvwxyz])\1$", r"\1", w)
    return _SYNONYMS.get(w, w)


def _is_stopword(stem: str) -> bool:
    return stem in _STOPWORDS or stem + "e" in _STOPWORDS


def _is_generic(stem: str) -> bool:
    return stem in _GENERIC_TERMS or stem + "e" in _GENERIC_TERMS


def _is_number_token(token: str) -> bool:
    lowered = token.casefold()
    return any(ch.isdigit() for ch in lowered) or lowered in _NUMBER_WORDS


_CONTRACTIONS = (
    (r"n['’]t\b", " not"),
    (r"['’]re\b", " are"),
    (r"['’]ve\b", " have"),
    (r"['’]ll\b", " will"),
    (r"['’]d\b", " would"),
    (r"['’]m\b", " am"),
    (r"['’]s\b", " "),
)


def _expand_contractions(text: str) -> str:
    lowered = (text or "").casefold()
    for pattern, replacement in _CONTRACTIONS:
        lowered = re.sub(pattern, replacement, lowered)
    return re.sub(r"['’]", " ", lowered)


def _split_hyphens(words: list[str]) -> list[str]:
    """'lithium-battery' -> lithium, battery. Tiny parts ('Wi-Fi') are joined instead."""
    out: list[str] = []
    for word in words:
        if "-" not in word.strip("-"):
            out.append(word)
            continue
        parts = [part for part in word.split("-") if part]
        if parts and all(len(part) >= 3 for part in parts):
            out.extend(parts)
        elif parts and all(len(part) <= 2 for part in parts):
            out.append("".join(parts))
        else:
            out.extend(parts)
    return out


def _words(text: str) -> list[str]:
    expanded = _expand_contractions(text)
    return _split_hyphens(re.findall(r"[a-z0-9][a-z0-9'-]*", expanded))


def _keep_term(stem: str, raw: str = "") -> bool:
    if raw and (
        raw in _STOPWORDS or raw in _GENERIC_TERMS or raw in _NUMBER_WORDS
    ):
        return False
    return (
        bool(stem)
        and len(stem) > 2
        and not _is_stopword(stem)
        and not _is_generic(stem)
        and stem not in _NUMBER_WORDS
    )


def question_terms(question: str) -> list[str]:
    """Distinctive stems of a question, in first-seen order (no numbers)."""
    terms: list[str] = []
    for word in _words(question):
        if _is_number_token(word):
            continue
        stem = _stem(word)
        if _keep_term(stem, word) and stem not in terms:
            terms.append(stem)
    return terms


def _place_like(stem: str) -> bool:
    # Only known route/region names count as the "route parameter". A capital
    # letter alone is not enough: loyalty programmes and brands are topics.
    return stem in _PLACE_STEMS or stem in _REGION_STEMS


def _canonical(term: str) -> str:
    """Matching form: fold a trailing silent 'e' ('piece'/'pieces' -> 'piec')."""
    if term.endswith("e") and len(term) >= 4 and not term.endswith(("ee", "ie")):
        return term[:-1]
    return term


def _text_term_set(texts: list[str]) -> set[str]:
    found: set[str] = set()
    for text in texts:
        for word in _words(text):
            if _is_number_token(word):
                continue
            found.add(_canonical(_stem(word)))
    return found


def corpus_term_set(texts: list[str]) -> set[str]:
    """Stems of every word in the knowledge base (used by the corpus-wide check)."""
    return _text_term_set(texts)


_VOCAB_PATH = Path(__file__).with_name("corpus_vocabulary.json")
_VOCAB_CACHE: dict = {"key": None, "terms": None}


def load_corpus_vocabulary(path: str | Path | None = None) -> set[str] | None:
    """Load the packaged corpus vocabulary, or None when it is unavailable.

    The vocabulary is a build artefact of the indexed pages. Returning None lets
    the guard fail open instead of refusing every question when the file is
    missing (for example on a partial deployment).
    """
    target = Path(path) if path is not None else _VOCAB_PATH
    try:
        key = (str(target), target.stat().st_mtime_ns)
    except OSError:
        return None
    if _VOCAB_CACHE["key"] == key:
        return _VOCAB_CACHE["terms"]
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        terms = {str(term) for term in payload["terms"] if term}
    except (OSError, ValueError, KeyError, TypeError):
        return None
    _VOCAB_CACHE["key"] = key
    _VOCAB_CACHE["terms"] = terms
    return terms


def _prefix_set(terms: set[str]) -> set[str]:
    return {term[:5] for term in terms if len(term) >= 6}


def _supported(term: str, terms: set[str], prefixes: set[str]) -> bool:
    """Exact stem match, or a shared 5-letter root for longer words (approve/approval)."""
    form = _canonical(term)
    return any(
        candidate in terms
        or (len(candidate) >= 6 and candidate[:5] in prefixes)
        for candidate in {term, form}
    )


def _result(terms, present, missing, coverage, refuse, reason, **extra) -> dict:
    return {
        "terms": terms,
        "present": present,
        "missing": missing,
        "coverage": coverage,
        "refuse": refuse,
        "reason": reason,
        **extra,
    }


def assess_context_coverage(
    question: str, contexts: list[str], corpus_terms: set[str] | None = None
) -> dict:
    """Decide whether the knowledge base can answer `question`.

    The decision uses the whole corpus vocabulary, not the retrieved chunks: a
    retrieval miss is a ranking problem, not evidence that the pages are silent.
    A question is refused only when (1) nothing was retrieved, or (2) one of its
    distinctive terms appears nowhere in the corpus. Questions that only name a
    destination are refused only when none of those places occurs in the corpus.
    Place names never count as core topic terms, so an unstated route parameter
    does not by itself make an answerable question look unsupported.

    ``corpus_terms`` may be supplied by the caller (the app caches it from the
    index); otherwise the packaged vocabulary file is used. If neither is
    available the guard fails open.
    """
    terms = question_terms(question)
    if not contexts:
        return _result(terms, [], terms, 0.0 if terms else None, True, "no retrieved context")
    if not terms:
        return _result([], [], [], None, False, "no distinctive terms")

    vocabulary = corpus_terms if corpus_terms else load_corpus_vocabulary()
    if not vocabulary:
        return _result(
            terms, terms, [], None, False, "corpus vocabulary unavailable; guard skipped"
        )

    prefixes = _prefix_set(vocabulary)
    place_terms = [term for term in terms if _place_like(term)]
    core_terms = [term for term in terms if term not in place_terms]
    present = [t for t in terms if _supported(t, vocabulary, prefixes)]
    missing = [t for t in terms if not _supported(t, vocabulary, prefixes)]
    coverage = round(len(present) / len(terms), 2) if terms else None

    if not core_terms:
        # Only a destination/proper noun: refuse only when the corpus never mentions
        # any of those places (e.g. "Do you fly to Hobart?").
        places_present = [t for t in place_terms if _supported(t, vocabulary, prefixes)]
        return _result(
            terms,
            places_present,
            [t for t in place_terms if t not in places_present],
            coverage,
            not places_present,
            "destination named in the question is absent from the corpus"
            if not places_present
            else "destination supported",
        )

    absent = [t for t in core_terms if not _supported(t, vocabulary, prefixes)]
    if absent:
        return _result(
            terms,
            present,
            missing,
            coverage,
            True,
            "terms absent from the whole knowledge base",
            corpus_absent=absent,
        )
    return _result(
        terms,
        present,
        missing,
        coverage,
        False,
        "only the route parameter is not mentioned in the retrieved pages"
        if missing
        else "all distinctive terms supported",
    )


# ---------------------------------------------------------------------------
# Missing-detail detector
# ---------------------------------------------------------------------------

_BAGGAGE_TERMS = (
    "baggage",
    "luggage",
    "bag",
    "bags",
    "suitcase",
    "carry-on",
    "carry on",
    "cabin bag",
    "hand baggage",
    "hand luggage",
    "checked bag",
    "checked baggage",
    "excess baggage",
    "allowance",
    "kilos",
    "kg",
)
_CABIN_TERMS = (
    "business class",
    "economy class",
    "premium economy",
    "first class",
    "business",
    "economy",
    "premium",
    "first",
    "cabin class",
)
_REGION_TERMS = (
    "domestic",
    "international",
    "africa",
    "europe",
    "america",
    "asia",
    "middle east",
    "nairobi",
    "mombasa",
    "kisumu",
    "malindi",
    "dubai",
    "london",
    "mumbai",
    "bangkok",
    "guangzhou",
    "accra",
    "monrovia",
    "abidjan",
    "dakar",
    "johannesburg",
    "cairo",
    "amsterdam",
    "paris",
    "new york",
    "toronto",
    "zanzibar",
    "kigali",
    "entebbe",
    "domestic",
    "international",
)
_PLACE_STEMS = {_stem(term) for term in _PLACE_TERMS}
_REGION_STEMS = {_stem(term) for term in _REGION_TERMS}

_MISSING_LABELS = {
    "cabin_class": "cabin class",
    "route": "route",
    "passenger_type": "passenger type",
}


def is_baggage_question(question: str, history: list | None = None) -> bool:
    text = " ".join(
        [*(content for role, content in (history or []) if role == "user"), question or ""]
    ).casefold()
    if any(term in text for term in _BAGGAGE_TERMS):
        return True
    # "What am I allowed to carry in the cabin?" is a baggage question without
    # the word baggage; require both the cabin and a carrying verb.
    return bool(
        re.search(r"\b(?:carry|bring|take|allow|bag)\b[^.?!]*\bcabin\b", text)
        or re.search(r"\bcabin\b[^.?!]*\b(?:carry|bring|take|allow|bag)\b", text)
    )


def detect_missing_details(question: str, history: list | None = None) -> dict:
    """Which baggage-critical details the passenger has not stated yet.

    Route and cabin class are the two parameters the allowance tables depend on.
    Passenger type is only reported when the question itself raises a passenger
    category (infant, student, elite frequent flyer, group), because the standard
    allowance already assumes an adult and the only extra rule is the elite
    frequent-flyer piece.
    """
    prior = " ".join(
        content for role, content in (history or []) if role == "user"
    )
    text = f"{prior} {question or ''}".casefold()
    baggage = is_baggage_question(question, history)
    if not baggage:
        return {
            "is_baggage_question": False,
            "cabin_class": False,
            "route": False,
            "passenger_type": False,
            "missing": [],
        }

    cabin_stated = any(term in text for term in _CABIN_TERMS)
    # Lower-case place words are matched against the list; any capitalised word
    # after "from"/"to" also counts as a stated destination ("to Hobart").
    named_destination = bool(
        re.search(r"\b(?:from|to)\s+[A-Z][a-z]+", question or "")
    )
    route_stated = (
        any(term in text for term in _REGION_TERMS) or named_destination
    )
    specific_passenger = any(
        term in text
        for term in (
            "infant",
            "baby",
            "child",
            "kid",
            "student",
            "senior",
            "asante",
            "silver",
            "gold",
            "platinum",
            "staff",
            "group",
        )
    )
    # A generic "member"/"frequent flyer" without the tier is the only case where
    # the passenger category changes the allowance but the category is unclear.
    passenger_unclear = not specific_passenger and (
        "frequent flyer" in text or "member" in text
    )

    details = {
        "is_baggage_question": True,
        "cabin_class": not cabin_stated,
        "route": not route_stated,
        "passenger_type": passenger_unclear,
    }
    details["missing"] = [
        _MISSING_LABELS[key] for key in _MISSING_LABELS if details[key]
    ]
    return details


def build_missing_details_note(question: str, history: list | None = None) -> str:
    """Prompt note for a baggage question that omits route or cabin class."""
    details = detect_missing_details(question, history)
    missing = details["missing"]
    if not missing:
        return ""
    joined = " or ".join(missing)
    return (
        f"The passenger has not said their {joined}; do NOT assume "
        f"{'them' if len(missing) > 1 else 'it'}: summarise the main cases from the "
        "context, then ask for the missing detail."
    )


def refusal_response(source_docs: list | None = None) -> dict:
    """Standard shape for a guarded refusal (never carries links)."""
    return {
        "response": NOT_FOUND_PHRASE,
        "sources": [],
        "source_links": [],
        "retrieved_sources": [
            doc.metadata.get("source", "")
            for doc in (source_docs or [])
            if getattr(doc, "metadata", None)
        ],
        "refused_by_guard": True,
    }


def guard_enabled() -> bool:
    import os

    return os.getenv("ANSWERABILITY_GUARD", "lexical").strip().lower() != "off"


def detail_hints_enabled() -> bool:
    import os

    return os.getenv("ANSWER_DETAIL_HINTS", "1").strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }
