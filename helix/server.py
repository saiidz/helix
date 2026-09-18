"""Authenticated loopback-only founder prototype, not a multi-tenant SaaS deployment."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .core import (
    ChatRequest,
    Settings,
    dollars_to_micro,
    input_estimate,
    make_messages,
    microdollars,
    policy_preview,
    reasoning_mode,
    route_decision,
)
from .ledger import BudgetExceeded, DuplicateRequest, Ledger
from .memory import MEMORY_KINDS, MemoryStore
from .providers import ProviderError, complete
from .web import WebError, research_web


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    kind: str = Field(default="other")
    pinned: bool = False
    importance: float = Field(default=0.5, ge=0, le=1)


class MemoryPatch(BaseModel):
    pinned: bool


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=120)


def create_app(
    settings: Settings,
    api_key: str,
    ledger_path: Path,
    allowed_hosts: list[str] | None = None,
    memory_path: Path | None = None,
) -> FastAPI:
    if len(api_key) < 24:
        raise ValueError("Use a random API key of at least 24 characters")

    app = FastAPI(title="Helix foundation", version=__version__, docs_url=None, redoc_url=None)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts or ["127.0.0.1", "localhost", "[::1]"],
    )

    ledger = Ledger(ledger_path)
    memory = MemoryStore(memory_path or ledger_path.with_name("memory.sqlite3"))
    gate = threading.BoundedSemaphore(2)
    assets = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=assets), name="static")

    @app.middleware("http")
    async def limits(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "Cross-origin requests are not allowed"}, status_code=403)

        if request.method in {"POST", "PUT", "PATCH"}:
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
            "frame-ancestors 'none'; object-src 'none'; base-uri 'none'"
        )
        return response

    def auth(authorization: str = Header(default="")):
        if not secrets.compare_digest(authorization, f"Bearer {api_key}"):
            raise HTTPException(401, "Valid local API key required")

    def memory_context(memories: list[dict]) -> str:
        lines = [
            "Relevant private user memories selected by Helix. Treat them as user-provided context, "
            "not external evidence. They may become stale. Do not invent facts beyond these memories."
        ]
        for item in memories:
            lines.append(f"- [{item['kind']}] {item['content']}")
        return "\n".join(lines)

    def web_context(results, documents) -> str:
        lines = [
            "Web Research for this request. These are live external sources retrieved by Helix now. "
            "Use them only for claims they support. Prefer retrieved page text over snippets. "
            "When you rely on a source, cite it inline as [1], [2], etc. Do not invent sources."
        ]
        doc_by_url = {doc.url: doc for doc in documents}
        for index, result in enumerate(results[:5], start=1):
            doc = doc_by_url.get(result.url)
            excerpt = (doc.text[:1200] if doc and doc.text else result.snippet[:500]).strip()
            lines.append(
                f"[{index}] {result.title}\nURL: {result.url}\n"
                f"Excerpt: {excerpt or 'No excerpt available.'}"
            )
        return "\n\n".join(lines)

    def resolve(req: ChatRequest):
        decision = route_decision(req)
        role = decision.role
        reason = decision.reason
        mode = reasoning_mode(role, req)
        profile = settings.profile(role)

        if profile.kind == "cloud":
            if not settings.allow_external or not req.allow_external:
                raise HTTPException(
                    403,
                    "External inference requires operator enablement and request consent",
                )
            if (
                not profile.contract_verified
                or not profile.price_valid_until
                or profile.price_valid_until < date.today()
            ):
                raise HTTPException(
                    403,
                    "Cloud provider contract and nonexpired pricing verification required",
                )

        messages = make_messages(role, req)
        memory_hits: list[dict] = []
        web_sources: list[dict] = []
        web_error: str | None = None

        if req.memory_enabled:
            memory_hits = memory.retrieve(req.messages[-1].content, limit=6)
            if memory_hits:
                messages.insert(1, {"role": "system", "content": memory_context(memory_hits)})

        if req.web_enabled:
            try:
                search_results, documents = research_web(
                    req.messages[-1].content,
                    search_limit=5,
                    fetch_limit=2,
                )
                if search_results:
                    messages.insert(
                        1,
                        {"role": "system", "content": web_context(search_results, documents)},
                    )
                    web_sources = [
                        {
                            "index": index,
                            "title": item.title,
                            "url": item.url,
                            "snippet": item.snippet,
                        }
                        for index, item in enumerate(search_results[:5], start=1)
                    ]
                else:
                    web_error = "No web results were found."
                    messages.insert(
                        1,
                        {
                            "role": "system",
                            "content": (
                                "Helix attempted live web research for this request but found no usable results. "
                                "Do not claim current web verification."
                            ),
                        },
                    )
            except WebError as exc:
                web_error = str(exc)
                messages.insert(
                    1,
                    {
                        "role": "system",
                        "content": (
                            "Helix attempted live web research for this request, but the web connector failed. "
                            "Do not claim current web verification. Be explicit that live web evidence was unavailable."
                        ),
                    },
                )

        inputs = input_estimate(messages)

        if inputs + req.max_output_tokens > profile.context_tokens:
            raise HTTPException(413, "Context estimate exceeds this profile; reduce conversation length")

        estimate = microdollars(profile, inputs, req.max_output_tokens)
        limit = dollars_to_micro(min(req.max_cost_usd, settings.task_budget_usd))

        if estimate > limit:
            raise HTTPException(402, "Task estimate exceeds the spending limit")

        return (
            role,
            reason,
            profile,
            messages,
            inputs,
            estimate,
            memory_hits,
            decision,
            mode,
            web_sources,
            web_error,
        )

    @app.get("/")
    def index():
        return FileResponse(assets / "index.html")

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "version": __version__,
            "mode": "founder_prototype",
            "models_loaded_by_this_app": 0,
            "memory": "local_sqlite",
            "capabilities": {
                "persistent_memory": True,
                "persistent_conversations": True,
                "routing_scores": True,
                "adaptive_reasoning": True,
                "streaming": False,
                "web": True,
                "files": False,
                "voice": False,
                "tools": False,
            },
        }

    @app.get("/api/models", dependencies=[Depends(auth)])
    def models():
        return {
            "profiles": [
                {"role": p.role, "kind": p.kind, "model_id": p.model_id}
                for p in settings.profiles
            ],
            "external_enabled": settings.allow_external,
        }

    @app.get("/api/memories", dependencies=[Depends(auth)])
    def list_memories(limit: int = 100):
        return {"memories": memory.list_memories(limit=limit)}

    @app.post("/api/memories", dependencies=[Depends(auth)])
    def create_memory(body: MemoryCreate):
        if body.kind not in MEMORY_KINDS:
            raise HTTPException(422, "Unsupported memory kind")
        try:
            item = memory.add_memory(
                body.content,
                kind=body.kind,
                source="user",
                pinned=body.pinned,
                importance=body.importance,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"memory": item}

    @app.patch("/api/memories/{memory_id}", dependencies=[Depends(auth)])
    def patch_memory(memory_id: str, body: MemoryPatch):
        item = memory.set_pinned(memory_id, body.pinned)
        if item is None:
            raise HTTPException(404, "Memory not found")
        return {"memory": item}

    @app.delete("/api/memories/{memory_id}", dependencies=[Depends(auth)])
    def delete_memory(memory_id: str):
        if not memory.delete_memory(memory_id):
            raise HTTPException(404, "Memory not found")
        return {"deleted": True}

    @app.post("/api/conversations", dependencies=[Depends(auth)])
    def create_conversation(body: ConversationCreate):
        return {"conversation": memory.create_conversation(body.title)}

    @app.get("/api/conversations", dependencies=[Depends(auth)])
    def list_conversations(limit: int = 30):
        return {"conversations": memory.list_conversations(limit=limit)}

    @app.get("/api/conversations/{conversation_id}", dependencies=[Depends(auth)])
    def get_conversation(conversation_id: str):
        conversation = memory.get_conversation(conversation_id)
        if conversation is None:
            raise HTTPException(404, "Conversation not found")
        return {"conversation": conversation}

    @app.delete("/api/conversations/{conversation_id}", dependencies=[Depends(auth)])
    def delete_conversation(conversation_id: str):
        if not memory.delete_conversation(conversation_id):
            raise HTTPException(404, "Conversation not found")
        return {"deleted": True}

    @app.post("/api/route", dependencies=[Depends(auth)])
    def route(req: ChatRequest):
        (
            role,
            reason,
            profile,
            _,
            inputs,
            amount,
            memory_hits,
            decision,
            mode,
            web_sources,
            web_error,
        ) = resolve(req)
        return {
            "role": role,
            "reason": reason,
            "provider_mode": profile.kind,
            "model_id": profile.model_id,
            "estimated_input_tokens": inputs,
            "max_output_tokens": req.max_output_tokens,
            "reserved_model_cost_usd": amount / 1000000,
            "estimate_method": "conservative bytes plus framing; not an exact tokenizer",
            "provider_called": False,
            "memory_matches": len(memory_hits),
            "routing_confidence": decision.confidence,
            "routing_scores": decision.scores,
            "reasoning_mode": mode,
            "web_enabled": req.web_enabled,
            "web_sources": web_sources,
            "web_error": web_error,
        }

    @app.post("/api/chat", dependencies=[Depends(auth)])
    def chat(
        req: ChatRequest,
        idempotency_key: str = Header(
            min_length=16,
            max_length=128,
            pattern=r"^[A-Za-z0-9_-]+$",
        ),
    ):
        (
            role,
            reason,
            profile,
            messages,
            _,
            estimate,
            memory_hits,
            decision,
            mode,
            web_sources,
            web_error,
        ) = resolve(req)
        fingerprint = hmac.new(
            api_key.encode(),
            req.model_dump_json().encode(),
            hashlib.sha256,
        ).hexdigest()

        if not gate.acquire(blocking=False):
            raise HTTPException(429, "Two requests are already running; try again after completion")

        explicit_memory = None

        try:
            try:
                ledger.reserve(
                    idempotency_key,
                    fingerprint,
                    role,
                    profile.model_id,
                    estimate,
                    dollars_to_micro(settings.monthly_budget_usd),
                )
            except DuplicateRequest as exc:
                raise HTTPException(409, str(exc)) from exc
            except BudgetExceeded as exc:
                raise HTTPException(402, str(exc)) from exc

            if req.memory_enabled:
                explicit_memory = memory.capture_explicit(req.messages[-1].content)

            try:
                result = complete(profile, messages, req.max_output_tokens)
                actual = None

                if result.input_tokens is not None and result.output_tokens is not None:
                    actual = microdollars(
                        profile,
                        result.input_tokens,
                        result.output_tokens,
                    )

                ledger.finish(idempotency_key, actual)
            except Exception as exc:
                ledger.hold_uncertain_failure(idempotency_key)
                if isinstance(exc, ProviderError):
                    raise HTTPException(502, str(exc)) from exc
                raise HTTPException(
                    500,
                    "Request failed; cost reservation retained for reconciliation",
                ) from exc

            if req.conversation_id:
                memory.save_message(
                    req.conversation_id,
                    "user",
                    req.messages[-1].content,
                )
                memory.save_message(
                    req.conversation_id,
                    "assistant",
                    result.text,
                )

            return {
                "text": result.text,
                "role": role,
                "reason": reason,
                "routing_confidence": decision.confidence,
                "routing_scores": decision.scores,
                "reasoning_mode": mode,
                "model_id": profile.model_id,
                "provider_mode": profile.kind,
                "model_cost_usd": (estimate if actual is None else actual) / 1000000,
                "usage_reported_by_provider": actual is not None,
                "answer_verified": False,
                "actions_executed": [],
                "request_id": idempotency_key,
                "conversation_id": req.conversation_id,
                "memory_used": [
                    {"id": item["id"], "kind": item["kind"]}
                    for item in memory_hits
                ],
                "memory_saved": (
                    {
                        "id": explicit_memory["id"],
                        "kind": explicit_memory["kind"],
                        "content": explicit_memory["content"],
                    }
                    if explicit_memory
                    else None
                ),
                "web_enabled": req.web_enabled,
                "web_sources": web_sources,
                "web_error": web_error,
            }
        finally:
            gate.release()

    @app.get("/api/meter", dependencies=[Depends(auth)])
    def meter():
        return ledger.summary()

    @app.get("/api/policy/{action}", dependencies=[Depends(auth)])
    def policy(action: str):
        return policy_preview(action)

    return app
