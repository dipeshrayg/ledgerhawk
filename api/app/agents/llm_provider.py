"""Unified LLM provider interface. Every agent that wants live-LLM
enhancement calls `call_llm()` and MUST have a deterministic fallback for
when it returns None -- no key configured, network failure, malformed
response, anything. This is what makes zero-key demo mode not a special
case: it's just the path every agent already has to support.
"""
from __future__ import annotations

import httpx

from app.config import settings

GEMINI_MODEL = "gemini-2.0-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"


def call_llm(prompt: str, system: str = "") -> str | None:
    try:
        if settings.llm_mode == "gemini":
            return _call_gemini(prompt, system)
        if settings.llm_mode == "groq":
            return _call_groq(prompt, system)
    except Exception:
        return None
    return None


def _call_gemini(prompt: str, system: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={settings.gemini_api_key}"
    text = f"{system}\n\n{prompt}" if system else prompt
    body = {"contents": [{"parts": [{"text": text}]}]}
    resp = httpx.post(url, json=body, timeout=25)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _call_groq(prompt: str, system: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    body = {"model": GROQ_MODEL, "messages": messages}
    resp = httpx.post(url, json=body, headers=headers, timeout=25)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
