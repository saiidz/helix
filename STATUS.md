# Helix implementation status

Checkpoint: **September 18, 2026** · active branch **feat/codex-inspired-ui-v02**.

## Founder-machine baseline already demonstrated

- [x] llama.cpp installed and running on Windows.
- [x] Qwen3 4B Q4_K_M loaded locally.
- [x] OpenAI-compatible local endpoint responded on `127.0.0.1:8080/v1`.
- [x] Helix produced real local generated answers.
- [x] Local model provider cost configured at $0.
- [x] Repository pushed to `saiidz/helix`.

## Implemented in the current branch

### Intelligence
- [x] Companion / Engineer / Sage with Auto routing.
- [x] Scored multi-signal router with confidence and visible routing reason.
- [x] Fast/deep inference policy: routine Companion/Engineer requests stay fast; Sage and complex engineering can escalate.
- [x] Capability-aware prompts that avoid invented knowledge cutoffs and generic chatbot boilerplate.
- [x] Zero-credit deterministic intelligence evaluation script.

### Memory and history
- [x] SQLite private user memory.
- [x] Explicit `Remember that …` capture.
- [x] Relevant-memory retrieval.
- [x] Memory add/pin/unpin/delete UI.
- [x] Persistent conversations.
- [x] Recent-conversation sidebar with restore/delete.
- [x] Conversation deletion also cleans conversation-scoped attachments.

### Speed / response UX
- [x] Reused HTTP connection pool for local provider calls.
- [x] Token-by-token streamed visible output.
- [x] Hidden `reasoning_content` is not forwarded.
- [x] Stop/cancel generation in the UI.
- [x] Ledger keeps conservative accounting for uncertain interrupted/failed requests.

### Internet and sourced learning
- [x] Web Auto / On / Off modes.
- [x] Auto research for clearly fresh/current prompts.
- [x] Zero-key DuckDuckGo HTML starter search adapter.
- [x] Direct text-page retrieval with SSRF-oriented public-network checks.
- [x] Concurrent page fetches and short-lived search/fetch cache.
- [x] Numbered web sources returned to the model and surfaced in the UI.
- [x] Local sourced-knowledge cache with provenance URLs.
- [x] Cached knowledge can be reused on later questions.
- [x] Users can inspect and clear learned web knowledge.
- [x] Knowledge cache is retrieval memory, not automatic weight training.

### Files
- [x] Browser-selected local text/code attachments.
- [x] Conversation-scoped local attachment storage.
- [x] Relevant attachment retrieval with bounded context.
- [x] Attached content is marked as untrusted data in model context.
- [x] UI upload/list/remove attachment chips.
- [x] No arbitrary filesystem access.

### Read-only projects
- [x] Local project metadata + source-file snapshot store.
- [x] Browser folder import with text/code extension filtering.
- [x] Server-side binary/unsafe-path rejection.
- [x] Batched project imports to reduce request overhead.
- [x] Project file tree/list in the Projects drawer.
- [x] Active project persisted locally and shown in the composer.
- [x] Project-aware relevance retrieval injected as untrusted context.
- [x] Auto routing biases natural project follow-ups toward Engineer.
- [x] No shell execution or project mutation authority.

### UI / reliability
- [x] Codex-like neutral dark default using Helix blue/cyan/violet accents.
- [x] Consistent optional light mode.
- [x] Backend capability negotiation through `/health`.
- [x] Graceful fallback for stale backend processes instead of raw `Not Found` chat failures.
- [x] Live role/confidence/reasoning state.
- [x] Runtime/model/cost/memory/web/files/knowledge status.

## Local validation required before merge

- [ ] Pull the newest feature branch.
- [ ] Run full pytest suite.
- [ ] Run `compileall`.
- [ ] Run `tools/intelligence_eval.py`.
- [ ] Start the real local Qwen/llama.cpp endpoint.
- [ ] Confirm streamed text arrives progressively.
- [ ] Press **Stop** mid-generation and confirm the UI recovers.
- [ ] Confirm memory add/pin/delete and `Remember that …` recall.
- [ ] Reload and restore multiple conversations from the sidebar.
- [ ] Test **Web Auto**, **Web On**, and **Web Off**.
- [ ] Ask a current-information question and verify visible source links.
- [ ] Ask a related question with live web off and verify sourced cached knowledge is available.
- [ ] Inspect and clear learned web knowledge.
- [ ] Attach a small `.py`, `.md`, or `.txt` file and ask Helix about it.
- [ ] Remove the attachment and verify it is no longer listed.
- [ ] Switch Dark ↔ Light and visually inspect both.
- [ ] Verify `.helix`, `config/local.json`, model weights, and secrets remain untracked.
- [ ] Do not merge PR #1 until these founder-machine checks pass.

## Still roadmap work

- [ ] Full project/repository workspace with read-only code search.
- [ ] Controlled editing/diffs/tests and sandboxed terminal tools.
- [ ] Binary/PDF/image ingestion and multimodal models.
- [ ] Voice / wake word / speech pipeline.
- [ ] Email/calendar/personal connectors and proactive tasks.
- [ ] Dedicated model selection/benchmarking per role.
- [ ] Multi-user auth, account isolation, export/delete, encryption controls.
- [ ] Production search provider strategy and stronger network sandbox.
- [ ] Cloud GPU autoscaling/subscriptions.
- [ ] Fine-tuning/distillation/training pipeline.
- [ ] Reproducible frontier benchmark evidence against commercial and leading open models.

## Safety interpretation

User memory, conversation history, attachments, and sourced web knowledge are different stores. None is automatically treated as training data.

The current application is still a **single-owner local prototype**. Do not expose it as a public multi-user service yet.
