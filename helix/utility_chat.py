"""Deterministic local utilities that should not be delegated to the LLM."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import threading
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from .core import ChatRequest
from .ledger import BudgetExceeded, DuplicateRequest, Ledger
from .memory import MemoryStore


CLOCK_MODEL_ID = "helix/host-clock"

_TIME_PATTERNS = (
    r"^\s*(?:what(?:'s| is)\s+)?(?:the\s+)?time(?:\s+is\s+it)?(?:\s+now)?\s*[?!.]*\s*$",
    r"^\s*what\s+time\s+is\s+it(?:\s+now)?\s*[?!.]*\s*$",
    r"^\s*current\s+time\s*[?!.]*\s*$",
    r"^\s*time\s+now\s*[?!.]*\s*$",
)
_DATE_PATTERNS = (
    r"^\s*(?:what(?:'s| is)\s+)?(?:today'?s\s+)?date\s*[?!.]*\s*$",
    r"^\s*what\s+(?:day|date)\s+is\s+it(?:\s+today)?\s*[?!.]*\s*$",
    r"^\s*current\s+date\s*[?!.]*\s*$",
    r"^\s*today'?s\s+date\s*[?!.]*\s*$",
)
_BOTH_PATTERNS = (
    r"^\s*(?:what(?:'s| is)\s+)?(?:the\s+)?(?:current\s+)?date\s+(?:and|&)\s+time\s*[?!.]*\s*$",
    r"^\s*(?:what(?:'s| is)\s+)?(?:the\s+)?(?:current\s+)?time\s+(?:and|&)\s+date\s*[?!.]*\s*$",
)


def _match(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.match(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def detect_clock_request(text: str) -> str | None:
    """Return time/date/both only for local-now questions.

    Location-qualified questions intentionally fall through to research/model
    handling until HELIX has a timezone/place tool.
    """
    cleaned = " ".join(text.strip().split())
    if len(cleaned) > 120 or re.search(r"\b(in|at)\s+[A-Z][\w -]{1,40}$", cleaned):
        return None
    if _match(_BOTH_PATTERNS, cleaned):
        return "both"
    if _match(_TIME_PATTERNS, cleaned):
        return "time"
    if _match(_DATE_PATTERNS, cleaned):
        return "date"
    return None


def clock_result(kind: str, now: datetime | None = None) -> dict:
    current = now or datetime.now().astimezone()
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("Host clock must be timezone-aware")
    hour = current.strftime("%I").lstrip("0") or "0"
    time_text = f"{hour}:{current.strftime('%M %p')} {current.tzname() or current.strftime('%z')}"
    date_text = current.strftime("%A, %B %d, %Y").replace(" 0", " ")
    if kind == "time":
        text = time_text
    elif kind == "date":
        text = date_text
    elif kind == "both":
        text = f"{time_text}\n{date_text}"
    else:
        raise ValueError("Unsupported clock request")
    return {
        "text": text,
        "kind": kind,
        "timestamp": current.isoformat(),
        "timezone": current.tzname() or current.strftime("%z"),
    }


class UtilityChat:
    def __init__(
        self,
        *,
        api_key: str,
        ledger: Ledger,
        memory: MemoryStore,
        gate: threading.BoundedSemaphore,
        monthly_limit: int,
    ):
        self.api_key = api_key
        self.ledger = ledger
        self.memory = memory
        self.gate = gate
        self.monthly_limit = monthly_limit

    def preview(self, req: ChatRequest) -> dict | None:
        kind = detect_clock_request(req.messages[-1].content)
        if kind is None:
            return None
        role = req.role.value if req.role is not None else "companion"
        return {
            "role": role,
            "reason": "Local time/date request; deterministic host clock, no model or web call",
            "routing_confidence": 1.0,
            "routing_scores": {name: int(name == role) for name in ("companion", "engineer", "sage")},
            "reasoning_mode": "fast",
            "provider_mode": "local_utility",
            "model_id": CLOCK_MODEL_ID,
            "provider_called": False,
            "estimated_input_tokens": 0,
            "max_output_tokens": req.max_output_tokens,
            "reserved_model_cost_usd": 0,
            "estimate_method": "No model invocation",
            "memory_matches": 0,
            "memory_used": [],
            "memory_saved": None,
            "files_used": [],
            "knowledge_used": [],
            "knowledge_learned": 0,
            "web_enabled": False,
            "web_used": False,
            "web_sources": [],
            "web_error": None,
            "web_skipped_reason": "Host clock answers local current time/date directly",
            "project": None,
            "project_files_used": [],
            "task_saved": None,
            "conversation_id": req.conversation_id,
            "actions_executed": [],
            "utility_kind": kind,
        }

    def reply(self, req: ChatRequest, request_id: str, *, stream: bool = False):
        data = self.preview(req)
        if data is None:
            return None
        if not self.gate.acquire(blocking=False):
            raise HTTPException(429, "Two requests are already running; try again after completion")

        reserved = finished = False
        try:
            fingerprint = hmac.new(
                self.api_key.encode(),
                req.model_dump_json().encode(),
                hashlib.sha256,
            ).hexdigest()
            try:
                self.ledger.reserve(
                    request_id,
                    fingerprint,
                    data["role"],
                    CLOCK_MODEL_ID,
                    0,
                    self.monthly_limit,
                )
                reserved = True
            except DuplicateRequest as exc:
                raise HTTPException(409, str(exc)) from exc
            except BudgetExceeded as exc:
                raise HTTPException(402, str(exc)) from exc

            result = clock_result(data.pop("utility_kind"))
            data.update(
                text=result["text"],
                clock=result,
                answer_verified=True,
                verification_method="host_clock",
                verification_scope="Current date/time reported by the HELIX host operating system",
                model_cost_usd=0,
                usage_reported_by_provider=False,
                request_id=request_id,
                tools_used=["clock"],
            )
            if req.conversation_id:
                self.memory.save_message(req.conversation_id, "user", req.messages[-1].content)
                self.memory.save_message(req.conversation_id, "assistant", data["text"])
            self.ledger.finish(request_id, 0)
            finished = True
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(500, "Clock request failed; no model or web call was made") from exc
        finally:
            try:
                if reserved and not finished:
                    self.ledger.hold_uncertain_failure(request_id)
            finally:
                self.gate.release()

        if not stream:
            return data

        meta = {
            key: value for key, value in data.items()
            if key not in {"text", "answer_verified", "verification_method", "verification_scope", "clock"}
        }
        frames = [
            dict(meta, type="meta"),
            {"type": "delta", "text": data["text"]},
            {
                "type": "done",
                "model_cost_usd": 0,
                "usage_reported_by_provider": False,
                "answer_verified": True,
                "verification_method": "host_clock",
                "verification_scope": data["verification_scope"],
                "clock": data["clock"],
            },
        ]
        return StreamingResponse(
            (json.dumps(frame, separators=(",", ":")) + "\n" for frame in frames),
            media_type="application/x-ndjson",
            headers={"X-Accel-Buffering": "no"},
        )
