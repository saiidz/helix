"""Local calculator fast path; called only inside authenticated chat endpoints."""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict
from typing import TYPE_CHECKING

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from .calculator import CalculationError, expression_from_message, result_for
from .ledger import BudgetExceeded, DuplicateRequest

if TYPE_CHECKING:
    from .core import ChatRequest

MODEL_ID = "exact-arithmetic-v1"


class CalculatorChat:
    """Reuse the app's request gate, ledger, history, and project validation.

    No provider, web connector, arbitrary filesystem, or process capability is
    accepted by this service. Prose and contextual questions return None and
    continue through the original chat implementation unchanged.
    """

    def __init__(self, *, api_key, ledger, memory, projects, gate, monthly_limit):
        self.api_key = api_key
        self.ledger = ledger
        self.memory = memory
        self.projects = projects
        self.gate = gate
        self.monthly_limit = monthly_limit

    def preview(self, req: ChatRequest) -> dict | None:
        expression = expression_from_message(req.messages[-1].content)
        if expression is None:
            return None
        project = self.projects.get(req.project_id) if req.project_id else None
        if req.project_id and project is None:
            raise HTTPException(404, "Project not found")
        if req.conversation_id and self.memory.get_conversation(req.conversation_id) is None:
            raise HTTPException(404, "Conversation not found")
        role = req.role or "companion"
        return {
            "role": role, "reason": "Self-contained arithmetic; local calculator, no model or web call",
            "routing_confidence": 1.0,
            "routing_scores": {name: int(name == role) for name in ("companion", "engineer", "sage")},
            "reasoning_mode": "fast", "provider_mode": "local", "model_id": MODEL_ID,
            "provider_called": False, "estimated_input_tokens": 0,
            "max_output_tokens": req.max_output_tokens, "reserved_model_cost_usd": 0,
            "estimate_method": "No model invocation", "memory_matches": 0,
            "memory_used": [], "memory_saved": None, "files_used": [],
            "knowledge_used": [], "knowledge_learned": 0,
            "web_enabled": req.web_enabled, "web_used": False, "web_sources": [], "web_error": None,
            "web_skipped_reason": "Self-contained arithmetic requires no web research",
            "project": project, "project_files_used": [], "task_saved": None,
            "conversation_id": req.conversation_id, "actions_executed": [],
            "calculator_expression": expression,
        }

    def reply(self, req: ChatRequest, request_id: str, *, stream: bool = False):
        data = self.preview(req)
        if data is None:
            return None
        if not self.gate.acquire(blocking=False):
            raise HTTPException(429, "Two requests are already running; try again after completion")
        reserved = finished = False
        try:
            fingerprint = hmac.new(self.api_key.encode(), req.model_dump_json().encode(), hashlib.sha256).hexdigest()
            try:
                self.ledger.reserve(request_id, fingerprint, data["role"], MODEL_ID, 0, self.monthly_limit)
                reserved = True
            except DuplicateRequest as exc:
                raise HTTPException(409, str(exc)) from exc
            except BudgetExceeded as exc:
                raise HTTPException(402, str(exc)) from exc
            try:
                calculation = result_for(data.pop("calculator_expression"))
                data.update(text=calculation.text, calculation=asdict(calculation), answer_verified=True,
                            verification_method="deterministic_exact_arithmetic",
                            verification_scope="The supplied arithmetic expression only", calculator_error=None)
            except CalculationError as exc:
                data.update(text=f"Calculation not performed: {exc}", calculation=None,
                            answer_verified=False, verification_method=None, calculator_error=str(exc))
            data.update(model_cost_usd=0, usage_reported_by_provider=False, request_id=request_id,
                        tools_used=["calculator"])
            if req.conversation_id:
                self.memory.save_message(req.conversation_id, "user", req.messages[-1].content)
                self.memory.save_message(req.conversation_id, "assistant", data["text"])
            self.ledger.finish(request_id, 0)
            finished = True
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(500, "Calculator request failed; no model or web call was made") from exc
        finally:
            try:
                if reserved and not finished:
                    self.ledger.hold_uncertain_failure(request_id)
            finally:
                self.gate.release()
        if not stream:
            return data
        # Work and history persistence are already complete. Disconnecting cannot
        # leak a held semaphore or leave a background calculation running.
        meta = {key: value for key, value in data.items()
                if key not in {"text", "answer_verified", "verification_method", "verification_scope", "calculation"}}
        frames = [dict(meta, type="meta"), {"type": "delta", "text": data["text"]},
                  {"type": "done", "model_cost_usd": 0, "usage_reported_by_provider": False,
                   "answer_verified": data["answer_verified"], "verification_method": data["verification_method"],
                   "verification_scope": data.get("verification_scope"), "calculation": data["calculation"]}]
        return StreamingResponse((json.dumps(frame, separators=(",", ":")) + "\n" for frame in frames),
                                 media_type="application/x-ndjson", headers={"X-Accel-Buffering": "no"})
