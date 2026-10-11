"""Query handler module to execute the LLM chain with retrieved context."""

from ..logger import logger


def query_chain(
    chain, user_input: str, context: str = "", source_docs: list = None
) -> dict:
    """Executes the LLM chain passing user input and retrieved context."""
    try:
        logger.debug(f"Running chain for input: {user_input}")
        source_docs = source_docs or []

        # Run modern LCEL chain with question and context
        if hasattr(chain, "invoke"):
            result = chain.invoke({"question": user_input, "context": context})
        else:
            result = chain({"question": user_input, "context": context})

        if isinstance(result, dict):
            answer = (
                result.get("result")
                or result.get("answer")
                or result.get("output_text")
                or ""
            )
        else:
            answer = getattr(result, "content", str(result))

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
