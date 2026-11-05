import os

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
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

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.1,
    )


def get_llm_chain():
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are the official Kenya Airways Customer Support Virtual Assistant ('Pride of Africa'). "
                    "Your mission is to provide accurate, warm, polite, and well-structured answers "
                    "based strictly on official airline policy context.\n\n"
                    "### How to Format Your Responses:\n"
                    "1. **Direct Answer First**: Always open with a direct, helpful summary answering the passenger's question.\n"
                    "2. **Stay on the question**: Answer only what the passenger asked. Avoid generic disclaimers, repeated advice, and unrelated booking or check-in suggestions.\n"
                    "3. **Clean Structure**: Use concise bullets or a small table when comparing routes, cabin classes, or weight tiers.\n"
                    "4. **Factual Grounding**: Rely strictly on the provided policy context for airline-specific facts. Never guess or fabricate policies.\n"
                    "5. **Multiple Options**: When the passenger asks generally and the context contains several route or cabin options, list the relevant options with their labels.\n"
                    "6. **Baggage Queries**: For a broad baggage question, mention checked and cabin limits only when both are present in the supplied context.\n"
                    "7. **Next steps**: Give a practical next step only when the context cannot answer the question or the passenger asks what to do.\n"
                    "8. **Context boundaries**: If the supplied context does not support an answer, say what is missing and do not substitute a rule from another route or cabin.\n\n"
                    "### Official Policy Context:\n{context}"
                ),
            ),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{question}"),
        ]
    )

    # Modern LCEL Chain
    chain = prompt | get_chat_model()
    return chain
