"""OpenAI-compatible local/cloud text transport with streaming support."""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from typing import Iterator

import httpx

from .core import Profile


class ProviderError(Exception):
    pass


@dataclass
class Completion:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass
class StreamChunk:
    text: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    done: bool = False


_CLIENT_LOCK = threading.Lock()
_CLIENT: httpx.Client | None = None


def _client() -> httpx.Client:
    """Reuse one connection pool so local llama.cpp calls avoid reconnect overhead."""
    global _CLIENT

    if _CLIENT is None:
        with _CLIENT_LOCK:
            if _CLIENT is None:
                _CLIENT = httpx.Client(
                    timeout=httpx.Timeout(90, connect=5),
                    trust_env=False,
                    follow_redirects=False,
                    limits=httpx.Limits(
                        max_keepalive_connections=8,
                        max_connections=16,
                        keepalive_expiry=30,
                    ),
                )
    return _CLIENT


def count(value):
    # A bool is an int subclass; reject it and other malformed usage values.
    return value if type(value) is int and 0 <= value <= 10000000 else None


def _headers(profile: Profile) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if profile.api_key_env:
        value = os.environ.get(profile.api_key_env)
        if not value:
            raise ProviderError("Configured provider credential is missing")
        headers["Authorization"] = f"Bearer {value}"
    return headers


def _url(profile: Profile) -> str:
    return profile.base_url.rstrip("/") + "/chat/completions"


def complete(profile: Profile, messages: list[dict], max_output: int) -> Completion:
    if profile.kind == "demo":
        return Completion(
            f"Demo mode — routed to Helix {profile.role.value.title()}. "
            "No AI model was called and no action was performed. "
            "Connect a local OpenAI-compatible text endpoint to receive generated answers.",
            0,
            0,
        )

    payload = {
        "model": profile.model_id,
        "messages": messages,
        "max_tokens": max_output,
        "stream": False,
    }

    try:
        with _client().stream(
            "POST",
            _url(profile),
            headers=_headers(profile),
            json=payload,
        ) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > 1000000:
                    raise ProviderError("Provider response exceeded size limit")
                chunks.append(chunk)

        data = json.loads(b"".join(chunks))
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise ProviderError(
                "Text response required; native tool/multimodal responses are not supported"
            )

        usage = data.get("usage") or {}
        if not isinstance(usage, dict):
            usage = {}

        return Completion(
            content,
            count(usage.get("prompt_tokens")),
            count(usage.get("completion_tokens")),
        )
    except ProviderError:
        raise
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProviderError(
            "Provider request failed or returned an unsupported response; not retried"
        ) from exc


def stream_complete(
    profile: Profile,
    messages: list[dict],
    max_output: int,
) -> Iterator[StreamChunk]:
    """Yield visible text only; hidden/reasoning fields are intentionally ignored."""
    if profile.kind == "demo":
        result = complete(profile, messages, max_output)
        yield StreamChunk(text=result.text)
        yield StreamChunk(
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            done=True,
        )
        return

    payload = {
        "model": profile.model_id,
        "messages": messages,
        "max_tokens": max_output,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    total_bytes = 0
    input_tokens = None
    output_tokens = None

    try:
        with _client().stream(
            "POST",
            _url(profile),
            headers=_headers(profile),
            json=payload,
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue

                total_bytes += len(line.encode("utf-8", errors="ignore"))
                if total_bytes > 1000000:
                    raise ProviderError("Provider stream exceeded size limit")

                if line.startswith("data:"):
                    line = line[5:].strip()

                if line == "[DONE]":
                    break

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                usage = data.get("usage") or {}
                if isinstance(usage, dict):
                    input_tokens = count(usage.get("prompt_tokens")) or input_tokens
                    output_tokens = count(usage.get("completion_tokens")) or output_tokens

                choices = data.get("choices") or []
                if not choices:
                    continue

                delta = choices[0].get("delta") or {}
                # Do not forward reasoning_content / thinking traces.
                text = delta.get("content")
                if isinstance(text, str) and text:
                    yield StreamChunk(text=text)

        yield StreamChunk(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            done=True,
        )
    except ProviderError:
        raise
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProviderError(
            "Provider stream failed or returned an unsupported response; not retried"
        ) from exc
