"""Authenticated reviewed-learning routes for the existing local-only launcher."""
from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .learning import ChatLearning
from .memory import MemoryStore


class LearningSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool


class LearningApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str | None = Field(default=None, min_length=6, max_length=280)


def install_learning_routes(app: FastAPI, api_key: str, memory_path: Path) -> ChatLearning:
    if len(api_key) < 24:
        raise ValueError("Use a random local API key of at least 24 characters")
    learning = ChatLearning(MemoryStore(memory_path))

    def auth(authorization: str = Header(default="")):
        if not secrets.compare_digest(authorization, f"Bearer {api_key}"):
            raise HTTPException(401, "Valid local API key required")

    def run(action, *args):
        try:
            return action(*args)
        except PermissionError as exc:
            raise HTTPException(409, str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/learning", include_in_schema=False)
    def page():
        return FileResponse(Path(__file__).parent / "static" / "learning.html")

    @app.get("/api/learning", dependencies=[Depends(auth)])
    def state():
        return {"settings": learning.settings(), "items": learning.list_candidates()}

    @app.put("/api/learning/settings", dependencies=[Depends(auth)])
    def settings(body: LearningSettings):
        return learning.set_enabled(body.enabled)

    @app.post("/api/learning/conversations/{conversation_id}/review", dependencies=[Depends(auth)])
    def review(conversation_id: str):
        return run(learning.review_conversation, conversation_id)

    @app.post("/api/learning/{candidate_id}/approve", dependencies=[Depends(auth)])
    def approve(candidate_id: str, body: LearningApproval):
        return {"memory": run(learning.approve, candidate_id, body.content)}

    @app.post("/api/learning/{candidate_id}/dismiss", dependencies=[Depends(auth)])
    def dismiss(candidate_id: str):
        run(learning.dismiss, candidate_id)
        return {"dismissed": True}

    @app.delete("/api/learning/items/{candidate_id}", dependencies=[Depends(auth)])
    def forget(candidate_id: str):
        run(learning.forget, candidate_id)
        return {"forgotten": True}

    @app.delete("/api/learning", dependencies=[Depends(auth)])
    def clear():
        learning.clear()
        return {"cleared": True, "enabled": False}

    @app.get("/api/learning/export", dependencies=[Depends(auth)])
    def export():
        return JSONResponse(learning.export(), headers={
            "Cache-Control": "no-store", "Content-Disposition": 'attachment; filename="helix-chat-memory.json"',
        })

    return learning
