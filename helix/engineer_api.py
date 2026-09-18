"""Opt-in Engineer Agent routes for the existing loopback HELIX process."""
from __future__ import annotations

import json
import secrets
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .engineer_agent import local_completion, run_agent
from .engineer_tools import ToolError, Workspace


class StartTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str = Field(min_length=1, max_length=6000)
    skills: list[str] = Field(default_factory=list, max_length=3)
    max_steps: int = Field(default=24, ge=1, le=60, strict=True)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approval_id: str = Field(min_length=16, max_length=100)
    decision: Literal["approve", "deny"]


class AgentSession:
    def __init__(self, root: Path, history: Path, model, budget: int):
        self.id = uuid.uuid4().hex
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.events: list[dict] = []
        self.event_id = 0
        self.status = "running"
        self.pending = None
        self.decision_event = threading.Event()
        self.answer = False
        self.model, self.budget = model, budget
        self.workspace = Workspace(root, history, self.approve, self.cancel)
        self.thread: threading.Thread | None = None

    def emit(self, kind: str, value):
        encoded = json.dumps(value, ensure_ascii=False)
        if len(encoded) > 24000:
            value = {"truncated": True, "excerpt": encoded[:24000]}
        with self.lock:
            self.event_id += 1
            self.events.append({"id": self.event_id, "kind": kind, "value": value})
            self.events = self.events[-200:]

    def approve(self, kind: str, preview: str) -> bool:
        with self.lock:
            if self.cancel.is_set():
                return False
            self.answer = False
            self.decision_event.clear()
            self.pending = {"id": secrets.token_urlsafe(24), "kind": kind, "preview": preview}
            self.status = "waiting_for_approval"
        deadline = time.monotonic() + 600
        while not self.decision_event.wait(.1):
            if self.cancel.is_set() or time.monotonic() > deadline:
                break
        with self.lock:
            answer = self.answer and not self.cancel.is_set()
            self.pending = None
            self.status = "running" if not self.cancel.is_set() else "stopping"
            return answer

    def decide(self, identifier: str, decision: str):
        with self.lock:
            if not self.pending or self.pending["id"] != identifier or self.decision_event.is_set() or self.cancel.is_set():
                raise ToolError("Approval is absent, expired, cancelled, or already used")
            self.answer = decision == "approve"
            self.decision_event.set()

    def stop(self):
        with self.lock:
            self.cancel.set()
            self.answer = False
            self.pending = None
            self.decision_event.set()
            if self.thread and self.thread.is_alive():
                self.status = "stopping"

    def snapshot(self, since=0):
        with self.lock:
            return {"id": self.id, "status": self.status, "events": [e for e in self.events if e["id"] > since],
                    "cursor": self.event_id, "approval": None if self.decision_event.is_set() else self.pending,
                    "receipts": list(self.workspace.receipts),
                    "active": bool(self.thread and self.thread.is_alive())}

    def run(self, task: StartTask):
        try:
            result = run_agent(self.workspace, task.task, self.model, self.emit,
                               task.max_steps, self.budget, task.skills)
            self.emit("session_result", result)
            with self.lock:
                self.status = result["status"]
        except Exception as exc:
            self.emit("error", str(exc))
            with self.lock:
                self.status = "failed"
        finally:
            with self.lock:
                self.pending = None
            if self.workspace.receipts:
                try:
                    self.workspace.history.mkdir(parents=True, exist_ok=True, mode=0o700)
                    target = self.workspace.history / "receipts.json"
                    target.write_text(json.dumps(self.workspace.receipts, indent=2), encoding="utf-8")
                    target.chmod(0o600)
                    self.emit("receipt_file", str(target))
                except OSError as exc:
                    self.emit("receipt_error", str(exc))


def install_agent_routes(app, api_key: str, workspace: Path | None, config: Path,
                         model_factory: Callable | None = None, history_root: Path | None = None):
    """No HTTP endpoint can set/change workspace. Operator chooses it at startup."""
    if len(api_key) < 24:
        raise ToolError("Local access key must have at least 24 characters")
    root = workspace.resolve(strict=True) if workspace is not None else None
    history = history_root or Path.home() / ".helix" / "engineer-history"
    if root is not None:
        Workspace(root, history / "validation", lambda *_: False)
    create_model = model_factory or (lambda: local_completion(config))
    state = {"session": None}
    gate = threading.Lock()

    def auth(request: Request, authorization: str = Header(default="")):
        if request.url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise HTTPException(403, "Loopback host required")
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "Cross-origin requests are not allowed")
        if not secrets.compare_digest(authorization, "Bearer " + api_key):
            raise HTTPException(401, "Valid local API key required")

    router = APIRouter(prefix="/api/engineer-agent", dependencies=[Depends(auth)])

    @router.get("/status")
    def status(since: int = 0, session_id: str = ""):
        if since < 0:
            raise HTTPException(422, "Invalid event cursor")
        session = state["session"]
        return {"enabled": root is not None, "workspace": str(root) if root else None,
                "os_sandbox": False, "cloud_fallback": False, "desktop_mouse_control": False,
                "session": session.snapshot(since if session.id == session_id else 0) if session else None}

    @router.post("/start")
    def start(task: StartTask):
        if root is None:
            raise HTTPException(409, "Restart HELIX with --workspace PATH or START_HELIX_AGENT.cmd to enable repository access")
        with gate:
            previous = state["session"]
            if previous and previous.thread and previous.thread.is_alive():
                raise HTTPException(409, "A task is already active; stop it before starting another")
            try:
                model, budget = create_model()
                session = AgentSession(root, history / uuid.uuid4().hex, model, budget)
            except (ValueError, OSError) as exc:
                raise HTTPException(422, str(exc)) from exc
            state["session"] = session
            session.thread = threading.Thread(target=session.run, args=(task,), daemon=True)
            session.thread.start()
        return {"status": "started"}

    @router.post("/decision")
    def decision(payload: Decision):
        session = state["session"]
        if session is None:
            raise HTTPException(409, "No active task")
        try:
            session.decide(payload.approval_id, payload.decision)
        except ToolError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"status": "decision_received"}

    @router.post("/stop")
    def stop():
        session = state["session"]
        if session:
            session.stop()
        return {"status": "stop_requested"}

    app.include_router(router)

    @app.get("/agent", include_in_schema=False)
    def agent_page():
        return FileResponse(Path(__file__).parent / "static" / "agent.html")

    def shutdown():
        session = state["session"]
        if session:
            session.stop()
            if session.thread:
                session.thread.join(timeout=3)
    app.add_event_handler("shutdown", shutdown)
    return state
