from typing import Any


def qa_generator_llm(
    context: str,
    client: Any,
    model: str = "AMead10/Llama-3.2-3B-Instruct-AWQ",
):
    generation_prompt = """
Your task is to write a factoid question and an answer given a context.
Your factoid question should be answerable with a specific, concise piece of factual information from the context.
Your factoid question should be formulated in the same style as questions users could ask in a search engine.
This means that your factoid question MUST NOT mention something like "according to the passage" or "context".
Provide your answer as follows:
Output:::
Factoid question: (your factoid question)
Answer: (your answer to the factoid question)
Now here is the context.
Context: {context}\n
Output:::"""
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a question-answer pair generator."},
            {
                "role": "user",
                "content": generation_prompt.format(context=context),
            },
        ],
        model=model,
        temperature=0.5,
        top_p=0.99,
        max_tokens=500,
    )
    return chat_completion.choices[0].message.content
