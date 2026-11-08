"""OpenAI client with an on-disk cache, so each call is paid for only once."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / ".cache" / "llm"

load_dotenv(ROOT / ".env")


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    cached: bool


def model_name() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _cache_key(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(max_retries=5)
    return _client


def chat(messages: list[dict], response_format: dict | None = None, temperature: float = 0.0) -> LLMResponse:
    payload = {"model": model_name(), "messages": messages, "temperature": temperature}
    if response_format:
        payload["response_format"] = response_format

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{_cache_key(payload)}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return LLMResponse(**{**data, "cached": True})

    start = time.perf_counter()
    resp = _get_client().chat.completions.create(**payload)
    latency = time.perf_counter() - start

    data = {
        "content": resp.choices[0].message.content or "",
        "input_tokens": resp.usage.prompt_tokens,
        "output_tokens": resp.usage.completion_tokens,
        "latency_s": round(latency, 3),
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return LLMResponse(**data, cached=False)


def cost_usd(input_tokens: int, output_tokens: int) -> float | None:
    """Estimated cost from the prices in .env (USD per 1M tokens). None if not configured."""
    p_in, p_out = os.getenv("PRICE_INPUT_PER_M"), os.getenv("PRICE_OUTPUT_PER_M")
    if not p_in or not p_out:
        return None
    return input_tokens / 1e6 * float(p_in) + output_tokens / 1e6 * float(p_out)
