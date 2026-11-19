import os

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.modules.prompts import RAG_SYSTEM_PROMPT
from langchain_openai import ChatOpenAI

load_dotenv()

DEFAULT_DEEPINFRA_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEEPINFRA_BASE_URL = "https://api.deepinfra.com/v1/openai"
DEFAULT_LLM_PROVIDER = "openrouter"


def get_model_provider() -> str:
    """Return the active generation provider; OpenRouter is the default."""
    provider = os.getenv("LLM_PROVIDER", DEFAULT_LLM_PROVIDER).strip().lower()
    if provider not in {"openrouter", "deepinfra"}:
        raise RuntimeError(
            "Unsupported LLM_PROVIDER. Choose 'openrouter' or 'deepinfra'."
        )
    return provider


def get_model_name() -> str:
    """Return the model selected for the active provider."""
    if get_model_provider() == "deepinfra":
        return (
            os.getenv("DEEPINFRA_MODEL", DEFAULT_DEEPINFRA_MODEL).strip()
            or DEFAULT_DEEPINFRA_MODEL
        )
    return (
        os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL).strip()
        or DEFAULT_OPENROUTER_MODEL
    )


def get_llm_temperature() -> float:
    """Sampling temperature for chat, RAG and evaluation (0 = most repeatable)."""
    try:
        return float(os.getenv("LLM_TEMPERATURE", "0"))
    except ValueError:
        return 0.0


DEFAULT_LLM_SEED = "42"


def get_llm_seed() -> int | None:
    """Sampling seed; supported by DeepInfra/OpenAI-compatible providers.

    Seed support is best-effort (the provider may ignore it). The A5 probe on
    DeepInfra showed seeded runs agreed 2/2 while unseeded runs differed 0/2, so
    42 is the default; set LLM_SEED=none/off to disable.
    """
    raw = os.getenv("LLM_SEED", DEFAULT_LLM_SEED).strip().casefold()
    if raw in {"", "none", "off"}:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def get_chat_model():
    """Create the shared model client for chat, RAG, and evaluation."""
    provider = get_model_provider()
    if provider == "deepinfra":
        api_key = os.getenv("DEEPINFRA_API_KEY", "").strip()
        model_name = get_model_name()
        if not api_key:
            raise RuntimeError(
                "DEEPINFRA_API_KEY is not configured. Add it to the backend environment."
            )
        base_url = DEEPINFRA_BASE_URL
    else:
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        model_name = get_model_name()
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not configured. Add it to the backend environment."
            )
        base_url = OPENROUTER_BASE_URL

    options = {
        "model": model_name,
        "api_key": api_key,
        "base_url": base_url,
        "temperature": get_llm_temperature(),
        "request_timeout": 120,
        "max_retries": 1,
    }
    seed = get_llm_seed()
    if seed is not None:
        options["seed"] = seed
    return ChatOpenAI(**options)


def get_llm_chain():
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", RAG_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{question}"),
        ]
    )

    # Modern LCEL Chain
    chain = prompt | get_chat_model()
    return chain
