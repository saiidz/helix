"""Authenticated loopback-only founder prototype, not a multi-tenant SaaS deployment."""
from __future__ import annotations
import hashlib
import hmac
import json
import secrets
import threading
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .core import (ChatRequest, Settings, dollars_to_micro, input_estimate, make_messages,
                   microdollars, policy_preview, select_role)
from .ledger import BudgetExceeded, DuplicateRequest, Ledger
from .providers import ProviderError, complete


def create_app(settings: Settings, api_key: str, ledger_path: Path,
               allowed_hosts: list[str] | None = None) -> FastAPI:
    if len(api_key) < 24:
        raise ValueError("Use a random API key of at least 24 characters")
    app = FastAPI(title="Helix foundation", version=__version__, docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or ["127.0.0.1", "localhost", "[::1]"])
    ledger = Ledger(ledger_path)
    gate = threading.BoundedSemaphore(2)
    assets = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=assets), name="static")

    @app.middleware("http")
    async def limits(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "Cross-origin requests are not allowed"}, status_code=403)
        if request.method == "POST":
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 64000:
                    return JSONResponse({"detail": "Request too large"}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "frame-ancestors 'none'; object-src 'none'; base-uri 'none'")
        return response

    def auth(authorization: str = Header(default="")):
        if not secrets.compare_digest(authorization, f"Bearer {api_key}"):
            raise HTTPException(401, "Valid local API key required")

    def resolve(req: ChatRequest):
        role, reason = select_role(req)
        profile = settings.profile(role)
        if profile.kind == "cloud":
            if not settings.allow_external or not req.allow_external:
                raise HTTPException(403, "External inference requires operator enablement and request consent")
            if not profile.contract_verified or not profile.price_valid_until or profile.price_valid_until < date.today():
                raise HTTPException(403, "Cloud provider contract and nonexpired pricing verification required")
        messages = make_messages(role, req)
        inputs = input_estimate(messages)
        if inputs + req.max_output_tokens > profile.context_tokens:
            raise HTTPException(413, "Context estimate exceeds this profile; reduce conversation length")
        estimate = microdollars(profile, inputs, req.max_output_tokens)
        limit = dollars_to_micro(min(req.max_cost_usd, settings.task_budget_usd))
        if estimate > limit:
            raise HTTPException(402, "Task estimate exceeds the spending limit")
        return role, reason, profile, messages, inputs, estimate

    @app.get("/")
    def index():
        return FileResponse(assets / "index.html")

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__, "mode": "founder_prototype",
                "models_loaded_by_this_app": 0}

    @app.get("/api/models", dependencies=[Depends(auth)])
    def models():
        return {"profiles": [{"role": p.role, "kind": p.kind, "model_id": p.model_id} for p in settings.profiles],
                "external_enabled": settings.allow_external}

    @app.post("/api/route", dependencies=[Depends(auth)])
    def route(req: ChatRequest):
        role, reason, p, _, inputs, amount = resolve(req)
        return {"role": role, "reason": reason, "provider_mode": p.kind, "model_id": p.model_id,
                "estimated_input_tokens": inputs, "max_output_tokens": req.max_output_tokens,
                "reserved_model_cost_usd": amount / 1000000,
                "estimate_method": "conservative bytes plus framing; not an exact tokenizer",
                "provider_called": False}

    @app.post("/api/chat", dependencies=[Depends(auth)])
    def chat(req: ChatRequest, idempotency_key: str = Header(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")):
        role, reason, p, messages, _, estimate = resolve(req)
        fingerprint = hmac.new(api_key.encode(), req.model_dump_json().encode(), hashlib.sha256).hexdigest()
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "Two requests are already running; try again after completion")
        try:
            try:
                ledger.reserve(idempotency_key, fingerprint, role, p.model_id, estimate,
                               dollars_to_micro(settings.monthly_budget_usd))
            except DuplicateRequest as exc:
                raise HTTPException(409, str(exc)) from exc
            except BudgetExceeded as exc:
                raise HTTPException(402, str(exc)) from exc
            try:
                result = complete(p, messages, req.max_output_tokens)
                actual = None
                if result.input_tokens is not None and result.output_tokens is not None:
                    actual = microdollars(p, result.input_tokens, result.output_tokens)
                ledger.finish(idempotency_key, actual)
            except Exception as exc:
                ledger.hold_uncertain_failure(idempotency_key)
                if isinstance(exc, ProviderError):
                    raise HTTPException(502, str(exc)) from exc
                raise HTTPException(500, "Request failed; cost reservation retained for reconciliation") from exc
            return {"text": result.text, "role": role, "reason": reason,
                    "model_id": p.model_id, "provider_mode": p.kind,
                    "model_cost_usd": (estimate if actual is None else actual) / 1000000,
                    "usage_reported_by_provider": actual is not None,
                    "answer_verified": False, "actions_executed": [], "request_id": idempotency_key}
        finally:
            gate.release()

    @app.get("/api/meter", dependencies=[Depends(auth)])
    def meter():
        return ledger.summary()

    @app.get("/api/policy/{action}", dependencies=[Depends(auth)])
    def policy(action: str):
        return policy_preview(action)

    return app
