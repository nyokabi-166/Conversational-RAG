"""Tests for expansion modes, numbered context, citations, source links, prompts."""

from types import SimpleNamespace

import pytest
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

import src.modules.query_handlers as qh
from src.modules.llm import get_llm_temperature
from src.modules.load_vesctorstore import _HTMLTextExtractor
from src.modules.prompts import (
    BASELINE_SYSTEM_PROMPT,
    NOT_FOUND_PHRASE,
    RAG_SYSTEM_PROMPT,
    STYLE_RULES,
)

UUID = "0123456789abcdef0123456789abcdef"
ALLOWANCE = f"{UUID}_Kenya Airways _ Baggage Allowance.html"
CHECKIN = "Kenya Airways PLC _ Online Check-in.html"


def doc(text, source):
    return Document(page_content=text, metadata={"source": source})


SPECIFIC = "What is the carry-on allowance for Economy class on flights from Nairobi to London?"
SHORT = "What is my baggage allowance?"


def test_expansion_mode_defaults_to_conditional_and_validates(monkeypatch):
    monkeypatch.delenv("RETRIEVAL_EXPANSION_MODE", raising=False)
    assert qh.get_retrieval_expansion_mode() == "conditional"
    monkeypatch.setenv("RETRIEVAL_EXPANSION_MODE", " Topic ")
    assert qh.get_retrieval_expansion_mode() == "topic"
    monkeypatch.setenv("RETRIEVAL_EXPANSION_MODE", "wild")
    with pytest.raises(ValueError):
        qh.get_retrieval_expansion_mode()


def test_underspecified_gate():
    assert qh.is_underspecified_question(SHORT)
    assert qh.is_underspecified_question("what documents do i need for a flight")
    assert not qh.is_underspecified_question(SPECIFIC)


def test_conditional_mode_orders_queries_by_specificity(monkeypatch):
    monkeypatch.setenv("RETRIEVAL_EXPANSION_MODE", "topic")
    topic_specific = qh.build_retrieval_queries(SPECIFIC, None)
    topic_short = qh.build_retrieval_queries(SHORT, None)
    primary_specific, primary_short = topic_specific[-1], topic_short[-1]
    assert len(topic_specific) > 1 and len(topic_short) > 1

    monkeypatch.setenv("RETRIEVAL_EXPANSION_MODE", "conditional")
    conditional_specific = qh.build_retrieval_queries(SPECIFIC, None)
    conditional_short = qh.build_retrieval_queries(SHORT, None)
    assert conditional_specific[0] == primary_specific  # detailed question leads
    assert conditional_short[0] != primary_short  # short question: expansion leads
    assert conditional_short[-1] == primary_short

    monkeypatch.setenv("RETRIEVAL_EXPANSION_MODE", "off")
    assert qh.build_retrieval_queries(SPECIFIC, None) == [primary_specific]


def test_context_is_numbered_with_clean_titles_from_catalog():
    context = qh.format_policy_context([doc("Economy: 23 kg", ALLOWANCE), doc("Opens 24h", CHECKIN)])
    assert context.startswith("[1] Page: Baggage Allowance\nEconomy: 23 kg")
    assert "[2] Page: Online Check-in\nOpens 24h" in context
    assert "Kenya Airways |" not in context


def test_citations_are_extracted_and_stripped():
    answer = "Economy gets 23 kg [1][2]. Business gets 32 kg [3]. Repeat [1]."
    assert qh.extract_citation_numbers(answer) == [1, 2, 3]
    assert qh.strip_citation_markers(answer) == "Economy gets 23 kg. Business gets 32 kg. Repeat."


def test_source_links_use_cited_pages_and_dedupe():
    docs = [doc("a", ALLOWANCE), doc("b", ALLOWANCE), doc("c", CHECKIN)]
    links = qh.build_source_links(docs, [2, 3, 1, 9], "answer")
    assert [link["file"] for link in links] == ["Kenya Airways _ Baggage Allowance.html", CHECKIN]
    assert links[0]["title"] == "Baggage Allowance"
    assert links[0]["url"].startswith("https://www.kenya-airways.com/")
    assert links[1]["url"].startswith("https://www.kenya-airways.com/")


def test_source_links_hide_when_the_answer_has_no_citations():
    docs = [doc("a", ALLOWANCE), doc("b", CHECKIN), doc("c", "Other.html")]
    assert qh.build_source_links(docs, [], "uncited answer") == []
    assert qh.build_source_links(docs, [1], NOT_FOUND_PHRASE) == []


def test_query_chain_returns_clean_answer_and_links():
    class FakeChain:
        def invoke(self, payload):
            assert payload["context"] == "CTX"
            return SimpleNamespace(content="Economy gets 23 kg [1]. Check-in opens early [2].")

    result = qh.query_chain(
        FakeChain(), "q", context="CTX", source_docs=[doc("a", ALLOWANCE), doc("b", CHECKIN)]
    )
    assert result["response"] == "Economy gets 23 kg. Check-in opens early."
    assert result["sources"] == ["Kenya Airways _ Baggage Allowance.html", CHECKIN]
    assert [link["title"] for link in result["source_links"]] == ["Baggage Allowance", "Online Check-in"]
    assert set(result["retrieved_sources"]) == {ALLOWANCE, CHECKIN}


def test_prompts_share_style_and_differ_in_grounding():
    assert STYLE_RULES in RAG_SYSTEM_PROMPT and STYLE_RULES in BASELINE_SYSTEM_PROMPT
    assert "{context}" in RAG_SYSTEM_PROMPT and "{context}" not in BASELINE_SYSTEM_PROMPT
    assert "{missing_details}" in RAG_SYSTEM_PROMPT
    assert "format example, do not reuse facts" in RAG_SYSTEM_PROMPT
    assert NOT_FOUND_PHRASE in RAG_SYSTEM_PROMPT and NOT_FOUND_PHRASE not in BASELINE_SYSTEM_PROMPT
    rendered = ChatPromptTemplate.from_messages(
        [("system", RAG_SYSTEM_PROMPT), ("human", "{question}")]
    ).format_messages(context="[1] x", question="q", missing_details="None.")
    assert "[1] x" in rendered[0].content
    assert "None." in rendered[0].content
    ChatPromptTemplate.from_messages(
        [("system", BASELINE_SYSTEM_PROMPT), ("human", "{question}")]
    ).format_messages(question="q")


def test_temperature_defaults_to_zero_and_can_be_overridden(monkeypatch):
    monkeypatch.delenv("LLM_TEMPERATURE", raising=False)
    assert get_llm_temperature() == 0.0
    monkeypatch.setenv("LLM_TEMPERATURE", "0.3")
    assert get_llm_temperature() == 0.3
    monkeypatch.setenv("LLM_TEMPERATURE", "abc")
    assert get_llm_temperature() == 0.0


def test_html_extractor_drops_chrome_and_newsletter_footer():
    html = (
        "<html><head><title>Kenya Airways | Baggage Allowance</title>"
        '<link rel="canonical" href="https://www.kenya-airways.com/en-ke/plan/baggage/"></head>'
        "<body><nav>Menu Book Manage</nav><main><h1>Baggage</h1><p>Economy gets 23 kg.</p></main>"
        "<div>Get the Latest Offers</div><div>Text</div><div>Subscribe</div></body></html>"
    )
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    text = extractor.get_text()
    assert "Economy gets 23 kg." in text
    for junk in ("Menu Book Manage", "Get the Latest Offers", "Subscribe"):
        assert junk not in text
    assert extractor.title == "Kenya Airways | Baggage Allowance"
    assert extractor.canonical_url == "https://www.kenya-airways.com/en-ke/plan/baggage/"