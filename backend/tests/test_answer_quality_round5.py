"""Round 5 tests: missing-detail hints, lexical guard, citation-only links, seed."""

from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

import src.modules.answer_quality as aq
import src.modules.query_handlers as qh
from src.modules.answer_quality import (
    assess_context_coverage,
    build_missing_details_note,
    corpus_term_set,
    detail_hints_enabled,
    detect_missing_details,
    guard_enabled,
    question_terms,
)
from src.modules.llm import get_llm_seed
from src.modules.prompts import NOT_FOUND_PHRASE

ALLOWANCE = "Kenya Airways _ Baggage Allowance.html"
BAGGAGE_TEXT = (
    "Free checked baggage allowance: Africa to Europe, business 2 pieces 32kg, "
    "economy 2 pieces 23kg. Domestic: 1 piece 23kg."
)
CORPUS = corpus_term_set(
    [BAGGAGE_TEXT, "In-flight meals are served on selected international routes."]
)


@pytest.fixture(autouse=True)
def _test_corpus(monkeypatch):
    monkeypatch.setattr(aq, "load_corpus_vocabulary", lambda *args, **kwargs: CORPUS)
    monkeypatch.setitem(qh._CORPUS_TERMS_CACHE, "terms", CORPUS)


def doc(text, source=ALLOWANCE):
    return Document(page_content=text, metadata={"source": source})


def test_detect_missing_details_for_underspecified_baggage_question():
    details = detect_missing_details("What is my baggage allowance?")
    assert details["is_baggage_question"] is True
    assert details["cabin_class"] is True
    assert details["route"] is True
    assert "cabin class" in details["missing"] and "route" in details["missing"]


def test_detect_missing_details_when_route_and_cabin_are_stated():
    details = detect_missing_details(
        "What is the checked baggage allowance for a flight from Nairobi to Dubai in economy?"
    )
    assert details["cabin_class"] is False
    assert details["route"] is False
    assert details["missing"] == []


def test_detect_missing_details_uses_earlier_turns_for_cabin():
    history = [
        ("user", "What am I allowed to carry in the cabin when flying business?"),
        ("assistant", "Two pieces."),
    ]
    details = detect_missing_details("What about economy?", history)
    assert details["cabin_class"] is False  # economy in the current turn
    assert details["route"] is True
    details_business = detect_missing_details("And on domestic routes?", history)
    assert details_business["cabin_class"] is False  # business from the history
    assert details_business["route"] is False  # domestic stated now


def test_detect_missing_details_ignores_non_baggage_questions():
    details = detect_missing_details("Can I fly while pregnant?")
    assert details["is_baggage_question"] is False
    assert details["missing"] == []


def test_detect_missing_details_flags_unclear_membership_tier():
    details = detect_missing_details("How much baggage do members get?")
    assert details["passenger_type"] is True
    assert "passenger type" in details["missing"]
    stated = detect_missing_details("How much baggage do Asante Gold members get?")
    assert stated["passenger_type"] is False


def test_missing_details_note_text():
    note = build_missing_details_note("What is my baggage allowance?")
    assert "cabin class or route" in note
    assert "do NOT assume" in note
    assert build_missing_details_note("How many bags in business class?") == "" or (
        "route" in build_missing_details_note("How many bags in business class?")
    )
    assert build_missing_details_note("Can I fly while pregnant?") == ""


def test_question_terms_folds_numbers_and_synonyms():
    terms = question_terms("How many kilos can I check in six bags?")
    assert "six" not in terms
    assert "weight" in terms
    assert "baggage" in terms


def test_guard_refuses_unsupported_topic():
    verdict = assess_context_coverage(
        "Do you serve hot meals in economy on flights to Europe?",
        [BAGGAGE_TEXT],
        corpus_terms=CORPUS,
    )
    assert verdict["refuse"] is True
    assert "hot" in verdict["corpus_absent"]


def test_guard_allows_supported_question():
    verdict = assess_context_coverage(
        "What is my baggage allowance?", [BAGGAGE_TEXT], corpus_terms=CORPUS
    )
    assert verdict["refuse"] is False


def test_guard_allows_missing_route_parameter_only():
    verdict = assess_context_coverage(
        "What is the checked baggage allowance from Nairobi to Dubai in economy?",
        [BAGGAGE_TEXT],
        corpus_terms=CORPUS,
    )
    assert verdict["refuse"] is False
    assert "dubai" in verdict["missing"]


def test_guard_answers_when_corpus_covers_topic_but_retrieval_missed_it():
    verdict = assess_context_coverage(
        "Are meals available on this flight?", [BAGGAGE_TEXT], corpus_terms=CORPUS
    )
    assert verdict["refuse"] is False
    assert "meal" in verdict["present"]


def test_guard_refuses_unknown_destination():
    verdict = assess_context_coverage(
        "Does Kenya Airways fly to Hobart?", [BAGGAGE_TEXT], corpus_terms=CORPUS
    )
    assert verdict["refuse"] is True


def test_guard_refuses_without_context():
    assert (
        assess_context_coverage(
            "What is my baggage allowance?", [], corpus_terms=CORPUS
        )["refuse"]
        is True
    )


def test_guard_fails_open_without_corpus_vocabulary(monkeypatch):
    monkeypatch.setattr(aq, "load_corpus_vocabulary", lambda *args, **kwargs: None)
    verdict = assess_context_coverage(
        "Do you serve hot meals in economy on flights to Europe?", [BAGGAGE_TEXT]
    )
    assert verdict["refuse"] is False
    assert "unavailable" in verdict["reason"]


def test_question_terms_normalizes_hyphens_and_contractions():
    terms = question_terms("What's the Wi-Fi price? Don't quote the checked-in fee.")
    assert "wifi" in terms or "internet" in terms
    assert "check" in terms
    assert "not" not in terms


def test_query_chain_guard_returns_not_found_without_calling_the_model(monkeypatch):
    monkeypatch.delenv("ANSWERABILITY_GUARD", raising=False)

    class ExplodingChain:
        def invoke(self, payload):
            raise AssertionError("the model must not be called for an unsupported topic")

    result = qh.query_chain(
        ExplodingChain(),
        "Do you serve hot meals in economy on flights to Europe?",
        context=BAGGAGE_TEXT,
        source_docs=[doc(BAGGAGE_TEXT)],
    )
    assert result["response"] == NOT_FOUND_PHRASE
    assert result["source_links"] == []
    assert result["refused_by_guard"] is True


def test_query_chain_honours_guard_off(monkeypatch):
    monkeypatch.setenv("ANSWERABILITY_GUARD", "off")

    class FakeChain:
        def invoke(self, payload):
            self.payload = payload
            return SimpleNamespace(content="Meals are not listed here [1].")

    chain = FakeChain()
    result = qh.query_chain(
        chain,
        "Do you serve hot meals in economy on flights to Europe?",
        context=BAGGAGE_TEXT,
        source_docs=[doc(BAGGAGE_TEXT)],
    )
    assert result["response"].startswith("Meals are not listed here")
    assert [link["file"] for link in result["source_links"]] == [ALLOWANCE]


def test_query_chain_passes_missing_details_note(monkeypatch):
    monkeypatch.delenv("ANSWER_DETAIL_HINTS", raising=False)

    class FakeChain:
        def invoke(self, payload):
            self.payload = payload
            return "Two pieces [1]."

    chain = FakeChain()
    qh.query_chain(
        chain,
        "What is my baggage allowance?",
        context=BAGGAGE_TEXT,
        source_docs=[doc(BAGGAGE_TEXT)],
    )
    assert "do NOT assume" in chain.payload["missing_details"]


def test_query_chain_disables_hints_when_asked(monkeypatch):
    monkeypatch.setenv("ANSWER_DETAIL_HINTS", "0")

    class FakeChain:
        def invoke(self, payload):
            self.payload = payload
            return "Two pieces [1]."

    chain = FakeChain()
    qh.query_chain(
        chain,
        "What is my baggage allowance?",
        context=BAGGAGE_TEXT,
        source_docs=[doc(BAGGAGE_TEXT)],
    )
    assert chain.payload["missing_details"] == ""


def test_guard_and_hint_flags(monkeypatch):
    monkeypatch.delenv("ANSWERABILITY_GUARD", raising=False)
    monkeypatch.delenv("ANSWER_DETAIL_HINTS", raising=False)
    assert guard_enabled() is True
    assert detail_hints_enabled() is True
    monkeypatch.setenv("ANSWERABILITY_GUARD", "off")
    monkeypatch.setenv("ANSWER_DETAIL_HINTS", "false")
    assert guard_enabled() is False
    assert detail_hints_enabled() is False


def test_seed_parsing(monkeypatch):
    monkeypatch.delenv("LLM_SEED", raising=False)
    assert get_llm_seed() == 42
    monkeypatch.setenv("LLM_SEED", "123")
    assert get_llm_seed() == 123
    monkeypatch.setenv("LLM_SEED", "off")
    assert get_llm_seed() is None
    monkeypatch.setenv("LLM_SEED", "none")
    assert get_llm_seed() is None
    monkeypatch.setenv("LLM_SEED", "not-a-number")
    assert get_llm_seed() is None


def test_lexical_ranking_is_stable_for_equal_scores():
    docs = [doc("same words here", f"page{index}.html") for index in range(6)]
    first = [d.metadata["source"] for d in qh.rank_documents_lexically("same words", docs, 4)]
    second = [d.metadata["source"] for d in qh.rank_documents_lexically("same words", docs, 4)]
    assert first == second
