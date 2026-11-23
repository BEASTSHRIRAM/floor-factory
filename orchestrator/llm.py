"""Optional LLM flavour for THE FLOOR's orchestrator.

Used ONLY for narration text (bid colour, review narration, shift summaries).
All decisions — bids, awards, verdicts, payroll — are deterministic code
(ARCHITECTURE §1: "Money math is code, not LLM"). If GROQ_API_KEY is not set,
or the Groq call fails for any reason, the caller's fallback string is used.
This module must never raise into the engine.
"""
from __future__ import annotations

import os

import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"


def llm_available() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


def narrate(system_hint: str, user_prompt: str, fallback: str) -> str:
    """One short Groq completion, or `fallback` verbatim. Never raises."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return fallback
    try:
        resp = httpx.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": os.environ.get("GROQ_MODEL", DEFAULT_MODEL),
                "messages": [
                    {"role": "system", "content": system_hint},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 70,
                "temperature": 0.7,
            },
            timeout=6.0,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        return text or fallback
    except Exception:  # noqa: BLE001 — narration is decoration, never a blocker
        return fallback
