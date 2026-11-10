"""Tests for the DeepInfra embedding provider (no network, no model downloads)."""

import math
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

import src.rag_pipeline as rp
from src.rag_pipeline import MiniLMEmbeddings

API_KEY = "test-key-123-not-real"
BACKEND_DIR = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def ok_response(count, dims=384, reverse=False, scale=2.0):
    rows = [
        {"index": i, "embedding": [scale * (i + 1)] + [0.0] * (dims - 1)}
        for i in range(count)
    ]
    if reverse:
        rows.reverse()
    return FakeResponse(200, {"data": rows})


@pytest.fixture(autouse=True)
def deepinfra_env(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "deepinfra")
    monkeypatch.setenv("DEEPINFRA_API_KEY", API_KEY)
    monkeypatch.delenv("DEEPINFRA_EMBED_MODEL", raising=False)
    monkeypatch.setattr(rp.time, "sleep", lambda seconds: None)


def test_provider_defaults_to_local_and_rejects_unknown(monkeypatch):
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    assert rp.get_embedding_provider() == "local"
    monkeypatch.setenv("EMBEDDING_PROVIDER", " DeepInfra ")
    assert rp.get_embedding_provider() == "deepinfra"
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    with pytest.raises(ValueError):
        rp.get_embedding_provider()


def test_deepinfra_mode_never_loads_local_model(monkeypatch):
    def boom(name):
        raise AssertionError("local model must not be loaded in deepinfra mode")

    monkeypatch.setattr(rp, "SentenceTransformer", boom)
    monkeypatch.setattr(rp, "_deepinfra_post", lambda payload, key: ok_response(1))
    embedder = MiniLMEmbeddings()
    assert embedder.model is None
    assert len(embedder.embed_query("hello")) == 384


def test_batches_of_64_preserve_order_and_normalise(monkeypatch):
    calls = []

    def fake_post(payload, key):
        calls.append((len(payload["input"]), payload["model"], key))
        return ok_response(len(payload["input"]), reverse=True)

    monkeypatch.setattr(rp, "_deepinfra_post", fake_post)
    vectors = MiniLMEmbeddings().embed_documents([f"t{i}" for i in range(130)])
    assert [size for size, _, _ in calls] == [64, 64, 2]
    assert calls[0][1] == "sentence-transformers/all-MiniLM-L6-v2"
    assert len(vectors) == 130
    for vector in vectors:
        assert len(vector) == 384
        assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0, rel_tol=1e-6)
    # Rows came back reversed; sorting by "index" must restore the input order.
    assert vectors[0][0] == pytest.approx(1.0)


def test_custom_model_name_is_used(monkeypatch):
    monkeypatch.setenv("DEEPINFRA_EMBED_MODEL", "my/other-model")
    seen = []
    monkeypatch.setattr(
        rp,
        "_deepinfra_post",
        lambda payload, key: seen.append(payload["model"]) or ok_response(1),
    )
    MiniLMEmbeddings().embed_query("x")
    assert seen == ["my/other-model"]


def test_retries_on_429_503_and_network_errors_then_succeeds(monkeypatch):
    outcomes = [
        FakeResponse(429),
        FakeResponse(503),
        httpx.ConnectError("boom"),
        ok_response(1),
    ]
    attempts = []

    def fake_post(payload, key):
        attempts.append(1)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    sleeps = []
    monkeypatch.setattr(rp.time, "sleep", sleeps.append)
    monkeypatch.setattr(rp, "_deepinfra_post", fake_post)
    assert len(MiniLMEmbeddings().embed_query("hello")) == 384
    assert len(attempts) == 4
    assert sleeps == [1, 2, 4]


def test_gives_up_after_retries_without_leaking_the_key(monkeypatch):
    attempts = []

    def always_503(payload, key):
        attempts.append(1)
        return FakeResponse(503)

    monkeypatch.setattr(rp, "_deepinfra_post", always_503)
    with pytest.raises(RuntimeError) as exc:
        MiniLMEmbeddings().embed_query("hello")
    assert len(attempts) == rp.DEEPINFRA_EMBED_MAX_RETRIES + 1
    assert "503" in str(exc.value)
    assert API_KEY not in str(exc.value)


def test_auth_error_is_not_retried_and_hides_key(monkeypatch):
    attempts = []

    def unauthorized(payload, key):
        attempts.append(1)
        return FakeResponse(401)

    monkeypatch.setattr(rp, "_deepinfra_post", unauthorized)
    with pytest.raises(RuntimeError) as exc:
        MiniLMEmbeddings().embed_query("hello")
    assert len(attempts) == 1
    assert "401" in str(exc.value)
    assert API_KEY not in str(exc.value)


def test_wrong_dimension_is_rejected(monkeypatch):
    monkeypatch.setattr(rp, "_deepinfra_post", lambda p, k: ok_response(1, dims=3))
    with pytest.raises(RuntimeError, match="384"):
        MiniLMEmbeddings().embed_query("hello")


def test_wrong_vector_count_and_bad_json_are_rejected(monkeypatch):
    monkeypatch.setattr(rp, "_deepinfra_post", lambda p, k: ok_response(1))
    with pytest.raises(RuntimeError, match="vectors"):
        MiniLMEmbeddings().embed_documents(["a", "b"])
    monkeypatch.setattr(rp, "_deepinfra_post", lambda p, k: FakeResponse(200, None))
    with pytest.raises(RuntimeError, match="unexpected response"):
        MiniLMEmbeddings().embed_query("hello")


def test_missing_api_key_gives_clear_error(monkeypatch):
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DEEPINFRA_API_KEY"):
        MiniLMEmbeddings().embed_query("hello")


def test_empty_input_makes_no_request(monkeypatch):
    monkeypatch.setattr(
        rp, "_deepinfra_post", lambda p, k: pytest.fail("no request expected")
    )
    assert MiniLMEmbeddings().embed_documents([]) == []


def test_deepinfra_mode_does_not_import_torch_in_a_fresh_process():
    code = (
        "import os, sys\n"
        "os.environ['EMBEDDING_PROVIDER'] = 'deepinfra'\n"
        "os.environ['DEEPINFRA_API_KEY'] = 'x'\n"
        "import src.rag_pipeline as rp\n"
        "class R:\n"
        "    status_code = 200\n"
        "    def json(self):\n"
        "        return {'data': [{'index': 0, 'embedding': [1.0] + [0.0] * 383}]}\n"
        "rp._deepinfra_post = lambda payload, key: R()\n"
        "assert len(rp.MiniLMEmbeddings().embed_query('hi')) == 384\n"
        "bad = [m for m in ('torch', 'sentence_transformers') if m in sys.modules]\n"
        "print('IMPORTED:' + ','.join(bad))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-500:]
    assert "IMPORTED:" in result.stdout
    assert result.stdout.strip().endswith("IMPORTED:"), result.stdout
