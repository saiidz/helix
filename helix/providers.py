"""Demo and OpenAI-compatible text transport; native proprietary APIs are future work."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass

import httpx

from .core import Profile


class ProviderError(Exception):
    pass


@dataclass
class Completion:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


def count(value):
    # A bool is an int subclass; reject it and other malformed usage values.
    return value if type(value) is int and 0 <= value <= 10000000 else None


def complete(profile: Profile, messages: list[dict], max_output: int) -> Completion:
    if profile.kind == "demo":
        return Completion(
            f"Demo mode — routed to Helix {profile.role.value.title()}. "
            "No AI model was called and no action was performed. "
            "Connect a local OpenAI-compatible text endpoint to receive generated answers.", 0, 0)
    headers = {"Content-Type": "application/json"}
    if profile.api_key_env:
        value = os.environ.get(profile.api_key_env)
        if not value:
            raise ProviderError("Configured provider credential is missing")
        headers["Authorization"] = f"Bearer {value}"
    url = profile.base_url.rstrip("/") + "/chat/completions"
    payload = {"model": profile.model_id, "messages": messages,
               "max_tokens": max_output, "stream": False}
    try:
        # No implicit proxy, redirects, tools, retries, or arbitrary destination from users.
        with httpx.Client(timeout=httpx.Timeout(90, connect=5), trust_env=False,
                          follow_redirects=False) as client:
            with client.stream("POST", url, headers=headers, json=payload) as response:
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
            raise ProviderError("Text response required; native tool/multimodal responses are not supported")
        usage = data.get("usage") or {}
        if not isinstance(usage, dict):
            usage = {}
        return Completion(content, count(usage.get("prompt_tokens")), count(usage.get("completion_tokens")))
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        # Do not leak upstream response bodies or secrets into client errors.
        raise ProviderError("Provider request failed or returned an unsupported response; not retried") from exc
