"""
Live answer steering.

Hosted LLM APIs (Groq, OpenRouter) don't expose hidden activations, so instead of
adding activation vectors we steer through the prompt: every axis is a 0-100 dial
between two poles, translated into style instructions. When the user moves a dial
mid-answer, the client aborts the stream and asks for a continuation of the text
written so far under the new settings, which makes the change feel live.
"""
import json
import logging

import requests
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

# key -> (low pole, high pole, instruction near low pole, instruction near high pole)
AXES = {
    "depth": (
        "brief",
        "thorough",
        "Be very brief: two or three short sentences, only the core point.",
        "Be thorough: explain the reasoning, cover nuances and include supporting details from the context.",
    ),
    "level": (
        "beginner",
        "expert",
        "Explain for a complete beginner: plain everyday words, define any term you use, give a simple analogy.",
        "Write for an expert: use precise technical vocabulary and skip basic explanations.",
    ),
    "tone": (
        "friendly",
        "formal",
        "Use a warm, friendly, encouraging conversational tone, like a helpful tutor.",
        "Use a formal, neutral, academic tone.",
    ),
    "format": (
        "prose",
        "steps",
        "Write in flowing paragraphs.",
        "Write as numbered points (1., 2., 3.), one idea per line.",
    ),
    "grounding": (
        "strict",
        "broad",
        "Stay strictly within the provided context; add nothing from outside it.",
        "You may add helpful general background knowledge beyond the context, but clearly say "
        "'Beyond your document:' before any such outside information.",
    ),
}

DEFAULT_STEERING = {key: 50 for key in AXES}


def normalize_steering(raw) -> dict:
    """Clamp incoming dial values to 0-100, falling back to neutral for bad input."""
    steering = dict(DEFAULT_STEERING)
    if isinstance(raw, dict):
        for key in AXES:
            try:
                steering[key] = max(0, min(100, int(round(float(raw.get(key, 50))))))
            except (TypeError, ValueError):
                pass
    return steering


def steering_instructions(steering: dict) -> str:
    """Turn dial values into style lines. Values near the middle add no instruction."""
    lines = []
    for key, (low, high, low_text, high_text) in AXES.items():
        value = steering.get(key, 50)
        distance = abs(value - 50)
        if distance < 12:
            continue
        strength = "Strongly: " if distance >= 35 else "Somewhat: " if distance < 22 else ""
        lines.append(f"- {strength}{low_text if value < 50 else high_text}")
    return "\n".join(lines)


def build_steered_prompt(
    question: str,
    context: str,
    conversation_history: str,
    steering: dict,
    partial_answer: str = "",
) -> str:
    style = steering_instructions(steering) or "- Use a balanced, clear style."
    prompt = (
        "You are a careful study assistant. Answer using the provided context. "
        "If the context does not support the answer, say that plainly instead of guessing. "
        "Do not use markdown: no bold, stars, headings or bullet symbols.\n\n"
        f"Style to follow:\n{style}\n\n"
        f"{conversation_history}"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
    )
    if partial_answer.strip():
        prompt += (
            "You already started answering. Here is your answer so far:\n"
            f"<<<\n{partial_answer}\n>>>\n\n"
            "Continue the answer from exactly where it stops. Do not repeat or restate anything already "
            "written and do not start over. If it stops mid-sentence, finish that sentence first. "
            "From this point on, follow the style above (it may differ from the earlier part). "
            "Output only the continuation text:"
        )
    else:
        prompt += "Answer:"
    return prompt


def _groq_stream(prompt: str):
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
            "max_tokens": 1024,
            "stream": True,
        },
        stream=True,
        timeout=15,
    )
    if not response.ok:
        raise RuntimeError(f"Groq error {response.status_code}: {response.text[:200]}")

    def tokens():
        try:
            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0]["delta"].get("content")
                except (ValueError, KeyError, IndexError):
                    continue
                if delta:
                    yield delta
        finally:
            response.close()

    return tokens()


def _openrouter_stream(prompt: str, model_id: str):
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=settings.OPENROUTER_API_KEY)
    stream = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=1024,
        stream=True,
        timeout=15,
    )

    def tokens():
        try:
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        finally:
            stream.close()

    return tokens()


def stream_llm(prompt: str):
    """
    Open a token stream: Groq first, then OpenRouter free models.
    Provider selection happens before the first token, so a failed provider never
    leaves half an answer behind.
    """
    providers = []
    if settings.GROQ_API_KEY:
        providers.append((f"Groq/{settings.GROQ_MODEL}", lambda: _groq_stream(prompt)))
    if settings.OPENROUTER_API_KEY:
        for model_id in settings.OPENROUTER_FREE_MODELS:
            providers.append((f"OpenRouter/{model_id}", lambda m=model_id: _openrouter_stream(prompt, m)))

    for name, open_stream in providers:
        try:
            tokens = open_stream()
            first = next(tokens, None)
            if first is None:
                logger.warning(f"{name} returned an empty stream, trying next provider")
                continue
            logger.info(f"Streaming answer from {name}")

            def chained(first=first, tokens=tokens):
                yield first
                yield from tokens

            return chained()
        except Exception as e:
            logger.warning(f"{name} stream failed ({type(e).__name__}): {e}")
            continue

    raise RuntimeError("AI service is temporarily unavailable, please try again.")
