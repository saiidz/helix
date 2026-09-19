"""Deterministic local utilities that should not be delegated to the LLM."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import threading
from datetime import datetime

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from .core import ChatRequest
from .ledger import BudgetExceeded, DuplicateRequest, Ledger
from .memory import MemoryStore


CLOCK_MODEL_ID = "helix/host-clock"
PROFILE_MODEL_ID = "helix/profile-memory"

_TIME_PATTERNS = (
    r"^\s*(?:what(?:'s| is)\s+)?(?:the\s+)?time(?:\s+is\s+it)?(?:\s+(?:now|rn))?\s*[?!.]*\s*$",
    r"^\s*what\s+time\s+is\s+it(?:\s+(?:now|rn))?\s*[?!.]*\s*$",
    r"^\s*current\s+time\s*[?!.]*\s*$",
    r"^\s*time\s+(?:now|rn)\s*[?!.]*\s*$",
)
_DATE_PATTERNS = (
    r"^\s*(?:what(?:'s| is)\s+)?(?:today'?s\s+)?date\s*[?!.]*\s*$",
    r"^\s*what\s+(?:day|date)\s+is\s+(?:it\s+)?(?:today)?\s*[?!.]*\s*$",
    r"^\s*current\s+date\s*[?!.]*\s*$",
    r"^\s*today'?s\s+date\s*[?!.]*\s*$",
    r"^\s*(?:date|day)\s+today\s*[?!.]*\s*$",
)
_BOTH_PATTERNS = (
    r"^\s*(?:what(?:'s| is)\s+)?(?:the\s+)?(?:current\s+)?date\s+(?:and|&)\s+time\s*[?!.]*\s*$",
    r"^\s*(?:what(?:'s| is)\s+)?(?:the\s+)?(?:current\s+)?time\s+(?:and|&)\s+date\s*[?!.]*\s*$",
)
_PROFILE_PATTERNS = (
    r"^\s*who\s+am\s+i\s*[?!.]*\s*$",
    r"^\s*what\s+do\s+you\s+(?:know|remember)\s+about\s+me\s*[?!.]*\s*$",
    r"^\s*tell\s+me\s+(?:about\s+)?myself\s*[?!.]*\s*$",
    r"^\s*describe\s+me\s*[?!.]*\s*$",
)
_NAME_PATTERNS = (
    r"^\s*what(?:'s|\s+is)\s+my\s+name\s*[?!.]*\s*$",
    r"^\s*do\s+you\s+(?:know|remember)\s+my\s+name\s*[?!.]*\s*$",
)


def _match(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.match(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _normalize_short_query(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    # Common conversational typos should not defeat deterministic utilities.
    cleaned = re.sub(
        r"^(?:wha|wat|wht|wats|whats)\b",
        "what",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def detect_clock_request(text: str) -> str | None:
    """Return time/date/both only for local-now questions.

    Location-qualified or event-specific questions intentionally fall through
    to web/model handling until HELIX has a timezone/place utility.
    """
    cleaned = _normalize_short_query(text)
    if len(cleaned) > 120:
        return None
    if re.search(r"\b(?:in|at)\s+[A-Za-z][\w .'-]{1,40}\s*[?!.]*$", cleaned, flags=re.IGNORECASE):
        return None
    if re.search(r"\b(game|meeting|appointment|flight|event|show|movie|class|work)\b", cleaned, flags=re.IGNORECASE):
        return None
    if _match(_BOTH_PATTERNS, cleaned):
        return "both"
    if _match(_TIME_PATTERNS, cleaned):
        return "time"
    if _match(_DATE_PATTERNS, cleaned):
        return "date"

    # Short semantic fallback catches harmless typos/word-order variation while
    # still requiring explicit current-time/date intent.
    words = set(re.findall(r"[a-z']+", cleaned.lower()))
    if len(words) <= 8:
        if "time" in words and words & {"what", "now", "rn", "current", "it"}:
            return "time"
        if words & {"date", "day"} and words & {"what", "today", "current", "it"}:
            return "date"
    return None


def detect_profile_request(text: str) -> str | None:
    cleaned = _normalize_short_query(text)
    if len(cleaned) > 160:
        return None
    if _match(_NAME_PATTERNS, cleaned):
        return "name"
    if _match(_PROFILE_PATTERNS, cleaned):
        return "profile"
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


def profile_result(kind: str, memories: list[dict]) -> dict:
    if kind == "name":
        name_memories = [
            item for item in memories
            if re.search(r"\b(?:my\s+name|name\s+is|called)\b", item["content"], flags=re.IGNORECASE)
        ]
        if name_memories:
            return {
                "text": "You told me: " + name_memories[0]["content"],
                "used": name_memories[:1],
                "found": True,
            }
        return {
            "text": (
                "I don't have your name saved in HELIX yet. "
                "You can say: “Remember that my name is …”"
            ),
            "used": [],
            "found": False,
        }

    if memories:
        lines = ["Here’s what you’ve explicitly saved about yourself in HELIX:"]
        for item in memories[:6]:
            lines.append(f"- {item['content']}")
        return {"text": "\n".join(lines), "used": memories[:6], "found": True}

    return {
        "text": (
            "I don't have a profile memory saved for you yet. "
            "Tell me something like “Remember that my name is …” or add profile memories in Memory."
        ),
        "used": [],
        "found": False,
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
        text = req.messages[-1].content
        clock_kind = detect_clock_request(text)
        profile_kind = None if clock_kind is not None else detect_profile_request(text)
        if clock_kind is None and profile_kind is None:
            return None

        role = req.role.value if req.role is not None else "companion"
        if clock_kind is not None:
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
                "utility_type": "clock",
                "utility_kind": clock_kind,
            }

        memories = self.memory.self_profile_memories(limit=8) if req.memory_enabled else []
        return {
            "role": role,
            "reason": (
                "Self-profile question; explicit local profile memory, no model or web call"
                if req.memory_enabled
                else "Self-profile question; memory is disabled for this request"
            ),
            "routing_confidence": 1.0,
            "routing_scores": {name: int(name == role) for name in ("companion", "engineer", "sage")},
            "reasoning_mode": "fast",
            "provider_mode": "local_memory",
            "model_id": PROFILE_MODEL_ID,
            "provider_called": False,
            "estimated_input_tokens": 0,
            "max_output_tokens": req.max_output_tokens,
            "reserved_model_cost_usd": 0,
            "estimate_method": "No model invocation",
            "memory_matches": len(memories),
            "memory_used": [{"id": item["id"], "kind": item["kind"]} for item in memories[:6]],
            "memory_saved": None,
            "files_used": [],
            "knowledge_used": [],
            "knowledge_learned": 0,
            "web_enabled": False,
            "web_used": False,
            "web_sources": [],
            "web_error": None,
            "web_skipped_reason": "Identity answer uses explicit local memory only",
            "project": None,
            "project_files_used": [],
            "task_saved": None,
            "conversation_id": req.conversation_id,
            "actions_executed": [],
            "utility_type": "profile",
            "utility_kind": profile_kind,
            "utility_memory_enabled": req.memory_enabled,
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
                    data["model_id"],
                    0,
                    self.monthly_limit,
                )
                reserved = True
            except DuplicateRequest as exc:
                raise HTTPException(409, str(exc)) from exc
            except BudgetExceeded as exc:
                raise HTTPException(402, str(exc)) from exc

            utility_type = data.pop("utility_type")
            utility_kind = data.pop("utility_kind")
            utility_memory_enabled = data.pop("utility_memory_enabled", True)
            if utility_type == "clock":
                result = clock_result(utility_kind)
                data.update(
                    text=result["text"],
                    clock=result,
                    answer_verified=True,
                    verification_method="host_clock",
                    verification_scope="Current date/time reported by the HELIX host operating system",
                    tools_used=["clock"],
                )
            else:
                if not utility_memory_enabled:
                    result = {
                        "text": (
                            "Memory is off for this request, so I’m not using your stored profile. "
                            "Turn Memory on if you want me to answer from it."
                        ),
                        "used": [],
                        "found": False,
                    }
                    method = "local_memory_disabled"
                    scope = "Stored profile memory was not accessed because memory is disabled"
                    tools = []
                else:
                    memories = self.memory.self_profile_memories(limit=8)
                    result = profile_result(utility_kind, memories)
                    method = "local_memory"
                    scope = "Explicit user profile/preference memories stored locally; not externally verified"
                    tools = ["memory"]
                data.update(
                    text=result["text"],
                    profile_memory_found=result["found"],
                    memory_used=[
                        {"id": item["id"], "kind": item["kind"]}
                        for item in result["used"]
                    ],
                    memory_matches=len(result["used"]),
                    answer_verified=False,
                    verification_method=method,
                    verification_scope=scope,
                    tools_used=tools,
                )

            data.update(
                model_cost_usd=0,
                usage_reported_by_provider=False,
                request_id=request_id,
            )
            if req.conversation_id:
                self.memory.save_message(req.conversation_id, "user", req.messages[-1].content)
                self.memory.save_message(req.conversation_id, "assistant", data["text"])
            self.ledger.finish(request_id, 0)
            finished = True
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                500,
                "Local utility request failed; no model or web call was made",
            ) from exc
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
            if key not in {
                "text", "answer_verified", "verification_method",
                "verification_scope", "clock",
            }
        }
        done = {
            "type": "done",
            "model_cost_usd": 0,
            "usage_reported_by_provider": False,
            "answer_verified": data["answer_verified"],
            "verification_method": data["verification_method"],
            "verification_scope": data["verification_scope"],
        }
        if "clock" in data:
            done["clock"] = data["clock"]
        frames = [
            dict(meta, type="meta"),
            {"type": "delta", "text": data["text"]},
            done,
        ]
        return StreamingResponse(
            (json.dumps(frame, separators=(",", ":")) + "\n" for frame in frames),
            media_type="application/x-ndjson",
            headers={"X-Accel-Buffering": "no"},
        )
