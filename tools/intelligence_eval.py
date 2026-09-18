"""Zero-credit local intelligence checks for Helix routing and reasoning policy."""
from __future__ import annotations

from dataclasses import dataclass

from helix.core import ChatRequest, Role, reasoning_mode, route_decision


@dataclass(frozen=True)
class Case:
    prompt: str
    expected_role: Role
    expected_mode: str


CASES = (
    Case("Help me organize my day and remember my preferences.", Role.COMPANION, "fast"),
    Case("Write a Python helper that validates JSON.", Role.ENGINEER, "fast"),
    Case("Debug a distributed race condition in this worker architecture.", Role.ENGINEER, "deep"),
    Case("Research the evidence for this scientific hypothesis.", Role.SAGE, "deep"),
    Case("Prove this theorem carefully.", Role.SAGE, "deep"),
)


def request(prompt: str) -> ChatRequest:
    return ChatRequest(messages=[{"role": "user", "content": prompt}])


def main() -> int:
    failures = 0

    print("Helix intelligence eval")
    print("=======================")

    for index, case in enumerate(CASES, start=1):
        req = request(case.prompt)
        decision = route_decision(req)
        mode = reasoning_mode(decision.role, req)

        role_ok = decision.role == case.expected_role
        mode_ok = mode == case.expected_mode
        status = "PASS" if role_ok and mode_ok else "FAIL"

        print(
            f"{index}. {status} | role={decision.role.value} "
            f"mode={mode} confidence={decision.confidence:.2f} "
            f"scores={decision.scores}"
        )
        print(f"   {case.prompt}")

        if not role_ok or not mode_ok:
            failures += 1
            print(
                f"   expected role={case.expected_role.value} "
                f"mode={case.expected_mode}"
            )

    if failures:
        print(f"\n{failures} intelligence case(s) failed.")
        return 1

    print("\nAll intelligence cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
