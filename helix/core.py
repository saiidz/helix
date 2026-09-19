"""Three-role routing, capability-aware prompting, and conservative cost estimates."""
from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_CEILING
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .runtime_context import runtime_context


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
    project_id: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    memory_enabled: bool = True
    web_enabled: bool = False
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


HELIX_CAPABILITY_CONTEXT = (
    "Current Helix runtime facts: local text inference is connected when the provider mode is local; "
    "persistent local user memory and conversation history are available. A local task list is available only "
    "when Task Context is supplied. The browser UI can show due alerts while Helix is open if the user grants "
    "notification permission, but Helix does not provide closed-app/background reminders or calendar scheduling yet. "
    "Helix can receive live web research context only when a Web Research system message is present for the current "
    "request; otherwise do not claim that the internet was searched or that facts are current. Local text/code "
    "attachments are available only when an Attached File Context system message is present; this does not grant "
    "arbitrary filesystem access. Email, calendar, voice, terminal access, repository mutation, deployment, "
    "purchases, and other external actions are NOT connected in this build. Never claim those unavailable "
    "capabilities are available. "
    "Never invent a training-data cutoff or say your knowledge is current to a specific date unless Helix "
    "explicitly supplies that fact. If the user asks what Helix can do, what it cannot do, or how to improve it, "
    "answer about these actual Helix capabilities and the concrete engineering path forward instead of giving "
    "generic chatbot boilerplate."
)

PROMPTS = {
    Role.COMPANION: (
        "You are Helix Companion, the personal-assistance brain inside Helix. Be natural, useful, direct, and "
        "context-aware. Prefer accomplishing the user's conversational goal over reciting generic AI caveats. "
        "You may receive explicitly stored private user memories supplied by Helix; use them only when relevant "
        "and never invent additional memories. When the user asks a personal question and relevant memory exists, "
        "use it. Distinguish remembered user context from verified external facts. "
        + HELIX_CAPABILITY_CONTEXT
    ),
    Role.ENGINEER: (
        "You are Helix Engineer, the software-engineering brain inside Helix. Think like a senior engineer: "
        "identify the goal, inspect the available context, propose the smallest sound change, call out risks, "
        "and give implementable code or validation steps. Prefer patch-oriented, concrete answers over tutorials. "
        "You may receive relevant project or preference memories supplied by Helix; treat them as user-provided "
        "context that can become stale. Never claim tests passed, code changed, repositories were inspected, or "
        "deployments happened without actual tool evidence. "
        + HELIX_CAPABILITY_CONTEXT
    ),
    Role.SAGE: (
        "You are Helix Sage, the deep-reasoning and research brain inside Helix. Decompose difficult questions, "
        "test assumptions, compare alternatives, and make uncertainty visible. Separate user-provided memory, "
        "model knowledge, inference, and externally verified evidence. Do not invent citations or claim external "
        "verification. Give conclusions only as strongly as the evidence supports them. "
        + HELIX_CAPABILITY_CONTEXT
    ),
}


@dataclass(frozen=True)
class RouteDecision:
    role: Role
    reason: str
    confidence: float
    scores: dict[str, int]


ENGINEER_PATTERNS: tuple[tuple[str, int], ...] = (
    (r"\b(code|coding|programming|typescript|javascript|python|rust|go|java|sql)\b", 4),
    (r"\b(debug|bug|exception|traceback|stack trace|failing test|fix ci|ci/cd)\b", 5),
    (r"\b(repo|repository|git|github|pull request|pr\b|commit|branch)\b", 4),
    (r"\b(api|endpoint|database|schema|migration|backend|frontend|server|docker|kubernetes)\b", 3),
    (r"\b(deploy|build|compile|refactor|implement|function|class|module|package)\b", 3),
    (r"\b(performance|latency|memory leak|race condition|deadlock|concurrency|distributed)\b", 4),
)

SAGE_PATTERNS: tuple[tuple[str, int], ...] = (
    (r"\b(prove|proof|theorem|lemma|mathematics|equation|derive)\b", 5),
    (r"\b(research|hypothesis|evidence|scientific|science|study|paper)\b", 4),
    (r"\b(analy[sz]e|reasoning|reason through|compare|trade[- ]?offs?|evaluate)\b", 2),
    (r"\b(philosophy|logic|probability|statistics|causal|causality)\b", 3),
    (r"\b(deep dive|think deeply|careful reasoning|step by step)\b", 3),
)

COMPANION_PATTERNS: tuple[tuple[str, int], ...] = (
    (r"\b(remember|memory|my preference|i prefer|i like|i dislike|about me)\b", 4),
    (r"\b(plan my day|my schedule|organize my day|personal assistant|remind me|task|tasks|todo|to-do|task list|add task)\b", 4),
    (r"\b(write a message|draft a message|help me reply|conversation|talk to me)\b", 2),
    (r"\b(how old am i|what do you remember|who am i|my birthday|my name)\b", 4),
)


def _score_patterns(text: str, patterns: tuple[tuple[str, int], ...]) -> int:
    return sum(weight for pattern, weight in patterns if re.search(pattern, text, flags=re.IGNORECASE))


def route_decision(req: ChatRequest) -> RouteDecision:
    """Deterministic local router with scored intent signals and role continuity."""
    if req.role is not None:
        return RouteDecision(
            req.role,
            "explicit role selected",
            1.0,
            {role.value: int(role == req.role) * 10 for role in Role},
        )

    text = req.messages[-1].content.strip().lower()

    followup = bool(
        req.previous_role
        and len(text.split()) <= 18
        and re.match(
            r"^(and\b|why\b|continue\b|what about\b|fix it\b|explain that\b|then\b|also\b|same thing\b)",
            text,
        )
    )
    if followup:
        return RouteDecision(
            req.previous_role,
            "short follow-up kept role continuity",
            0.91,
            {role.value: int(role == req.previous_role) * 8 for role in Role},
        )

    scores = {
        Role.COMPANION.value: _score_patterns(text, COMPANION_PATTERNS),
        Role.ENGINEER.value: _score_patterns(text, ENGINEER_PATTERNS),
        Role.SAGE.value: _score_patterns(text, SAGE_PATTERNS),
    }

    # An explicitly active code project is a strong contextual signal. This lets
    # natural follow-ups like "where is this handled?" stay in Engineer without
    # forcing users to repeat coding keywords on every turn.
    if req.project_id:
        scores[Role.ENGINEER.value] += 2
        if re.search(
            r"\b(this|that|it|where|why|how|fix|change|implement|find|search|review|explain)\b",
            text,
        ):
            scores[Role.ENGINEER.value] += 2

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_name, top_score = ordered[0]
    second_score = ordered[1][1]

    if top_score == 0:
        return RouteDecision(Role.COMPANION, "conversational default", 0.62, scores)

    if top_score == second_score:
        if req.previous_role is not None and scores[req.previous_role.value] == top_score:
            return RouteDecision(req.previous_role, "ambiguous intent kept previous role", 0.68, scores)
        if scores[Role.ENGINEER.value] == top_score and re.search(
            r"\b(code|debug|bug|api|repo|git|python|typescript|database)\b",
            text,
        ):
            return RouteDecision(Role.ENGINEER, "technical intent won an ambiguous route", 0.72, scores)
        if scores[Role.SAGE.value] == top_score and re.search(
            r"\b(research|proof|theorem|evidence|scientific)\b",
            text,
        ):
            return RouteDecision(Role.SAGE, "research intent won an ambiguous route", 0.72, scores)
        return RouteDecision(Role.COMPANION, "ambiguous intent defaulted to Companion", 0.58, scores)

    role = Role(top_name)
    margin = top_score - second_score
    confidence = min(0.96, 0.68 + 0.06 * margin + 0.02 * min(top_score, 5))

    reason_map = {
        Role.COMPANION: "personal or conversational intent",
        Role.ENGINEER: "software-engineering intent",
        Role.SAGE: "research or deep-reasoning intent",
    }
    return RouteDecision(role, reason_map[role], confidence, scores)


def select_role(req: ChatRequest) -> tuple[Role, str]:
    decision = route_decision(req)
    return decision.role, decision.reason


DEEP_ENGINEER_PATTERN = re.compile(
    r"\b(architecture|distributed|race condition|deadlock|concurrency|security|threat model|"
    r"performance|latency|memory leak|root cause|algorithm|database design|migration plan|"
    r"system design|complex refactor|incident|production failure)\b",
    flags=re.IGNORECASE,
)


def reasoning_mode(role: Role, req: ChatRequest) -> str:
    """Choose fast/deep inference without exposing hidden reasoning."""
    if role == Role.SAGE:
        return "deep"

    if role == Role.ENGINEER and DEEP_ENGINEER_PATTERN.search(req.messages[-1].content):
        return "deep"

    return "fast"


def make_messages(role: Role, req: ChatRequest) -> list[dict]:
    # Recompute the host date and web request state on every turn, not at import.
    system = PROMPTS[role] + "\n\n" + runtime_context(req.web_enabled)
    messages = [{"role": "system", "content": system}] + [
        m.model_dump() for m in req.messages
    ]

    directive = "/think" if reasoning_mode(role, req) == "deep" else "/no_think"

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
