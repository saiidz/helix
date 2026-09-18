# Helix · local-first AI command center

**Companion · Engineer · Sage** — one Helix identity, at most three primary model roles, explicit privacy boundaries, and measurable cost controls.

Helix is currently a **single-owner local prototype**. It can route requests across the three Helix roles and connect to an operator-supplied OpenAI-compatible local model server such as llama.cpp. Cloud fallback remains disabled by default.

## Current local stack

- Helix UI + FastAPI gateway on loopback only.
- Companion, Engineer, and Sage routing.
- Local model adapter with no automatic paid fallback.
- SQLite cost ledger.
- **Private local user memory** in SQLite.
- **Persistent local conversations** across browser reloads/restarts.
- Explicit memory capture with phrases such as `Remember that …`.
- Memory management UI: add, pin/unpin, and delete.
- Relevant memories are selectively injected into model context.
- Command-center UI showing runtime, route, model, cost, and capability state.

Memory is private application state. It is **not training data**.

## Windows local model setup

This repository does not ship model weights.

The current founder machine uses a local llama.cpp-compatible endpoint. A typical setup is:

```powershell
llama-server -hf ggml-org/Qwen3-4B-GGUF:Q4_K_M
```

Then configure the uncommitted `config/local.json` to point all three starter roles at the loopback endpoint and start Helix:

```powershell
& ".\.venv\Scripts\python.exe" -m helix --config ".\config\local.json"
```

The application binds to:

```text
http://127.0.0.1:8765
```

The local model server remains separate, typically on port `8080`.

## Memory behavior

Helix currently stores local memory under `.helix/`, which is excluded from Git.

Memory v0.2 intentionally uses conservative behavior:

- users can add memories manually;
- users can pin/unpin or delete them;
- saying `Remember that …` explicitly stores a memory;
- Helix retrieves only a small relevant set for each request;
- pinned memories may be included broadly;
- memory rows include a future-facing `user_id` boundary, while this build still supports only one local owner.

Broader silent memory inference is intentionally deferred until review, undo, expiry, and account-isolation controls are stronger.

## Conversations

The browser keeps the current conversation identifier locally. Messages for that conversation are stored in the local Helix SQLite memory database and can be restored after reload/restart.

This is **not** yet a multi-user SaaS conversation system.

## Run tests

```powershell
& ".\.venv\Scripts\python.exe" -m pytest -q
```

New memory tests cover:

- add/list/retrieve/delete;
- explicit memory capture and de-duplication;
- persistent conversation messages;
- memory API behavior;
- injection of relevant private memory into model context.

Run the suite on the Windows founder machine before merging the current feature branch.

## Important boundaries

Helix still has **no connected web browser, email, calendar, terminal, deployment executor, voice runtime, payment system, or multi-tenant authentication**.

The command center surfaces those modules as roadmap capabilities but does not pretend they are active.

The local model can still be wrong. A remembered user fact is user-provided context, not independently verified evidence.

## Project docs

- [HELIX_ROADMAP.md](HELIX_ROADMAP.md)
- [STATUS.md](STATUS.md)
- [NEXT_TASK.md](NEXT_TASK.md)
- [docs/SECURITY.md](docs/SECURITY.md)
- [docs/ECONOMICS.md](docs/ECONOMICS.md)
