"""Three-role routing, validated configuration, and conservative cost estimates."""
from __future__ import annotations

import ipaddress
import json
import re
from datetime import date
from decimal import Decimal, ROUND_CEILING
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Role(StrEnum):
    COMPANION = "companion"
    ENGINEER = "engineer"
    SAGE = "sage"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Message(StrictModel):
    role: str = Field(pattern=r"^(user|assistant)$")
    content: str = Field(min_length=1, max_length=12000)


class ChatRequest(StrictModel):
    messages: list[Message] = Field(min_length=1, max_length=32)
    role: Role | None = None
    previous_role: Role | None = None
    conversation_id: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    memory_enabled: bool = True
    allow_external: bool = False
    max_output_tokens: int = Field(default=512, ge=1, le=2048)
    max_cost_usd: Decimal = Field(default=Decimal("0.10"), ge=0, le=10)

    @model_validator(mode="after")
    def last_user(self):
        if self.messages[-1].role != "user":
            raise ValueError("Last message must be from the user")
        return self


class Profile(StrictModel):
    role: Role
    kind: str = Field(pattern=r"^(demo|local|cloud)$")
    model_id: str = Field(min_length=1, max_length=128)
    base_url: str | None = None
    api_key_env: str | None = None
    input_usd_per_million: Decimal = Field(default=Decimal(0), ge=0, le=10000)
    output_usd_per_million: Decimal = Field(default=Decimal(0), ge=0, le=10000)
    context_tokens: int = Field(default=16384, ge=1024, le=2000000)
    price_valid_until: date | None = None
    contract_verified: bool = False

    @model_validator(mode="after")
    def endpoint_safety(self):
        if self.kind == "demo":
            if self.base_url is not None:
                raise ValueError("Demo profiles cannot have an endpoint")
            return self

        if not self.base_url:
            raise ValueError("Endpoint required")

        u = urlsplit(self.base_url)
        if not u.hostname or u.username or u.password or u.query or u.fragment:
            raise ValueError("Invalid endpoint; credentials/query/fragment are prohibited")

        try:
            addr = ipaddress.ip_address(u.hostname)
        except ValueError:
            addr = None

        if self.kind == "local":
            if u.scheme != "http" or addr is None or not addr.is_loopback:
                raise ValueError("Local endpoint must use HTTP on a literal loopback address")
        elif u.scheme != "https" or addr is not None:
            raise ValueError("Cloud endpoint must use HTTPS and an approved DNS hostname")

        return self


class Settings(StrictModel):
    profiles: list[Profile] = Field(min_length=3, max_length=3)
    allow_external: bool = False
    approved_cloud_hosts: list[str] = Field(default_factory=list)
    monthly_budget_usd: Decimal = Field(default=Decimal("10"), ge=0, le=10000)
    task_budget_usd: Decimal = Field(default=Decimal("0.10"), ge=0, le=10)

    @model_validator(mode="after")
    def exactly_three(self):
        if {p.role for p in self.profiles} != set(Role):
            raise ValueError("Exactly one profile for each of Companion, Engineer, Sage is required")

        for p in self.profiles:
            if p.kind == "cloud" and urlsplit(p.base_url).hostname not in self.approved_cloud_hosts:
                raise ValueError("Cloud endpoint hostname is not operator-approved")

        return self

    @classmethod
    def from_file(cls, path: Path) -> "Settings":
        return cls.model_validate_json(path.read_text())

    def profile(self, role: Role) -> Profile:
        return next(p for p in self.profiles if p.role == role)


PROMPTS = {
    Role.COMPANION: (
        "You are Helix Companion, a conversational personal assistant. Understand the user's "
        "intent, communicate clearly, and distinguish evidence from guesses. You may receive "
        "explicitly stored private user memories supplied by Helix; use them only when relevant "
        "and never invent additional memories. This prototype has no calendar, email, reminder, "
        "browser, or other action tools. Never claim to have performed an action or accessed "
        "private data that Helix did not provide."
    ),
    Role.ENGINEER: (
        "You are Helix Engineer, focused on programming, debugging and software operations. "
        "Provide implementable code and explicit validation steps. You may receive relevant "
        "project or preference memories supplied by Helix; treat them as user-provided context "
        "that may become stale. This prototype has no terminal, repository or deployment tools. "
        "Never claim tests passed or code was changed without actual tool evidence."
    ),
    Role.SAGE: (
        "You are Helix Sage, focused on research, mathematics and careful reasoning. Separate "
        "facts, assumptions and conclusions. You may receive relevant user memories supplied by "
        "Helix; distinguish those private user facts from externally verified evidence. This "
        "prototype has no browsing or calculation tools. Do not invent citations or claim "
        "external verification. State uncertainty where evidence is missing."
    ),
}


def select_role(req: ChatRequest) -> tuple[Role, str]:
    """Cheap starter rules, NOT a learned or quality-validated routing policy."""
    if req.role is not None:
        return req.role, "explicit role selected"

    text = req.messages[-1].content.lower()

    if re.search(r"\b(code|coding|debug|repo|repository|typescript|python|sql|deploy|ci|api|bug|function|git)\b", text):
        return Role.ENGINEER, "technical task keyword"

    if re.search(r"\b(prove|theorem|research|hypothesis|mathematics|reasoning|analy[sz]e|science)\b", text):
        return Role.SAGE, "reasoning or research keyword"

    if req.previous_role and re.match(r"^(and\b|why\b|continue\b|what about\b|fix it\b|explain that\b)", text):
        return req.previous_role, "follow-up role continuity"

    return Role.COMPANION, "conversational default"


def make_messages(role: Role, req: ChatRequest) -> list[dict]:
    messages = [{"role": "system", "content": PROMPTS[role]}] + [
        m.model_dump() for m in req.messages
    ]

    directive = "/think" if role == Role.SAGE else "/no_think"

    for message in reversed(messages):
        if message["role"] == "user":
            message["content"] = f"{directive}\n{message['content']}"
            break

    return messages


def input_estimate(messages: list[dict]) -> int:
    """Intentionally conservative byte-based estimate plus framing overhead."""
    return len(json.dumps(messages, ensure_ascii=False).encode("utf-8")) + 64 * len(messages)


def microdollars(profile: Profile, inputs: int, outputs: int) -> int:
    """Prices per million tokens become microdollars/token; round UP to a whole unit."""
    if inputs < 0 or outputs < 0:
        raise ValueError("Token counts cannot be negative")

    total = profile.input_usd_per_million * inputs + profile.output_usd_per_million * outputs
    return int(total.to_integral_value(rounding=ROUND_CEILING))


def dollars_to_micro(value: Decimal) -> int:
    return int((value * 1000000).to_integral_value(rounding=ROUND_CEILING))


def policy_preview(action: str) -> dict:
    """A preview only. No tool executor exists in this build."""
    if action in {"read_calendar", "read_email", "search_repository"}:
        decision = "requires_connector_read_scope"
    elif action in {"send_email", "create_calendar_event", "deploy", "purchase", "delete"}:
        decision = "requires_explicit_confirmation_and_connector_scope"
    elif action == "draft_text":
        decision = "allowed_without_side_effect"
    else:
        decision = "deny_unknown_action"

    return {"action": action, "decision": decision, "executed": False}
