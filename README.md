# Helix · local-first AI command center

**Companion · Engineer · Sage** — one Helix identity with three specialized roles, local memory, live web grounding, sourced learning, files, streaming, and explicit privacy/cost boundaries.

Helix is currently a **single-owner local prototype**. The founder build runs an OpenAI-compatible local model through llama.cpp and does not require a paid model API. Cloud fallback remains disabled by default.

## Current feature branch

The active branch is `feat/codex-inspired-ui-v02` and is still awaiting founder-machine validation before merge.

Implemented on that branch:

- real local Qwen/llama.cpp inference;
- scored Auto routing across Companion / Engineer / Sage;
- adaptive fast/deep reasoning policy;
- token-by-token streamed responses plus **Stop**;
- reused HTTP connections to reduce local inference overhead;
- private local user memory and persistent conversation history;
- recent-conversation sidebar with restore/delete;
- live web research with **Web Auto / On / Off** controls;
- source links under grounded answers;
- local sourced-knowledge cache learned from explicit web research;
- inspect + clear controls for learned web knowledge;
- local text/code attachments selected by the user in the browser;
- relevant file snippets injected as untrusted context;
- **read-only project workspaces**: create a project, explicitly import a source folder, browse the indexed file tree, and keep that project active as Engineer context;
- project folder imports are batched for lower HTTP overhead and binaries/unsafe paths are rejected;
- dark Codex-like default UI plus optional Helix-branded light mode;
- local cost ledger and no automatic paid-provider fallback.

## What “learn” means in this build

Helix does **not** silently retrain Qwen on arbitrary internet content.

When web research is used:

1. Helix searches the public web.
2. It fetches a small number of text pages.
3. The current answer receives numbered source context.
4. Useful retrieved text is stored locally with its source URL.
5. Later related questions can retrieve that sourced knowledge even with live web turned off.

That local knowledge can be inspected and cleared. It is retrieval memory, **not model-weight training**, and private user memory is not training data.

## Internet modes

The UI exposes three modes:

- **Auto** — use live research for clearly fresh/current questions such as “latest”, “today”, “news”, or explicit web lookup requests.
- **On** — use web research for every request.
- **Off** — never use live web research.

The starter zero-key search adapter uses DuckDuckGo HTML and direct text-page retrieval. It blocks private/loopback/link-local targets, credentials, nonstandard ports, redirects, JavaScript execution, and oversized responses. This is suitable for local prototyping, not a production search SLA.

## Local files

Helix can attach browser-selected **text/code files** to a conversation. It does not get arbitrary filesystem access.

Supported in this build:

- common source-code and text formats;
- local SQLite storage under the ignored `.helix` runtime area;
- per-conversation listing/removal;
- relevance-based file context for later questions;
- prompt-injection boundary: attached content is treated as untrusted user data.

Binary files, PDFs, images, repository mutation, and terminal execution are still separate roadmap work.

## Read-only projects

Projects are explicit local snapshots, not silent filesystem access.

- Click **Projects** and create a project.
- Import a folder using the browser folder picker.
- Helix accepts supported source/text files only and skips likely binaries.
- The active project is shown in the composer.
- Natural follow-ups inside an active project bias Auto routing toward Engineer.
- Relevant project files are inserted as untrusted context with file paths.
- Helix may analyze and propose diffs, but it still cannot mutate the project or run commands.

This provides a useful engineering workspace before any shell/write authority is introduced.

## Windows quick run

Keep llama.cpp running separately, for example:

```powershell
llama-server -hf ggml-org/Qwen3-4B-GGUF:Q4_K_M
```

Then from the Helix directory:

```powershell
git fetch origin
git switch feat/codex-inspired-ui-v02
git pull --ff-only
.\DEV_LOOP_WINDOWS.cmd
```

The engineering loop runs tests, compile checks, the local routing/intelligence evaluation, private-file checks, verifies the llama.cpp endpoint, and then launches Helix.

Helix app: `http://127.0.0.1:8765`

Local model endpoint used by the founder build: `http://127.0.0.1:8080/v1`

## Tests

Run directly with:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest -q
& ".\.venv\Scripts\python.exe" -m compileall -q helix tests tools
& ".\.venv\Scripts\python.exe" tools\intelligence_eval.py
```

The branch contains tests for routing, adaptive reasoning, provider transport, visible-only streaming, memory, conversations, guarded web primitives, sourced knowledge, file storage/retrieval, and server APIs.

**Do not treat those tests as passed on the founder PC until the local run completes.**

## Current boundaries

Still not connected:

- voice / wake word;
- email and calendar;
- binary/PDF/image ingestion;
- arbitrary local filesystem access;
- terminal / shell execution;
- repository mutation or deployment;
- autonomous purchases/actions;
- multi-user authentication and tenant isolation;
- training/fine-tuning/distillation;
- production cloud autoscaling/subscriptions.

The local model can be wrong. Web citations show retrieved sources, not a guarantee that every source is correct.

## Project docs

- [HELIX_ROADMAP.md](HELIX_ROADMAP.md)
- [STATUS.md](STATUS.md)
- [NEXT_TASK.md](NEXT_TASK.md)
- [docs/SECURITY.md](docs/SECURITY.md)
- [docs/ECONOMICS.md](docs/ECONOMICS.md)
