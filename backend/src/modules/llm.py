import os

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

load_dotenv()


def get_llm_chain():
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are an expert customer support assistant for an airline. "
                    "Answer the passenger's question accurately based ONLY on the provided context below. "
                    "If the answer cannot be found, say 'The document does not contain information on this topic.'\n\n"
                    "Context:\n{context}"
                ),
            ),
            ("human", "{question}"),
        ]
    )

    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.2,
    )

    # Modern LCEL Chain
    chain = prompt | llm
    return chain
