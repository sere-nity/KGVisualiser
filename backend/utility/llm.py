import openai
import os
from fastapi import HTTPException

# Build a prompt for LLM from question and context
def build_prompt(question, context, context_type="PDF"):
    return f"""User question: {question}\n\nRelevant data from the uploaded {context_type}:\n{context}\n\nAnswer:"""

def chat_with_llm(question, context, context_type, model="gpt-4.1-nano"):
    """
    Shared utility to build prompt and call OpenAI LLM for both PDF and CSV chat endpoints.
    """
    prompt = build_prompt(question, context, context_type=context_type)
    openai.api_key = os.getenv("OPENAI_API_KEY")
    if not openai.api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    response = openai.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500
    )
    print("response", response)
    answer = response.choices[0].message.content
    return answer