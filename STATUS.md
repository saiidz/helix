# Helix implementation status

Checkpoint: **September 18, 2026** · active feature branch **feat/codex-inspired-ui-v02**.

## Working baseline already proven on the founder Windows PC

- [x] Local llama.cpp server loaded a real Qwen3 4B Q4_K_M checkpoint.
- [x] Local model API responded through `http://127.0.0.1:8080/v1`.
- [x] Helix connected to the local model and returned real generated answers.
- [x] Companion / Engineer / Sage profiles all point to local inference in the founder configuration.
- [x] Qwen thinking behavior was measured: `/no_think` returns visible fast answers, while thinking can consume the output budget before final content.
- [x] Local model cost ledger remains $0 provider cost for the founder local configuration.
- [x] GitHub repository `saiidz/helix` was initialized and pushed.

## In the current PR branch

- [x] Reworked the browser experience into a Helix command center rather than a generic chat landing page.
- [x] Added visible Auto / Companion / Engineer / Sage routing state.
- [x] Added runtime/model/cost/capability status.
- [x] Added richer chat rendering and interaction states.
- [x] Added SQLite-backed private user memory.
- [x] Added memory types, pinning, importance, source, timestamps, and soft deletion.
- [x] Added conservative explicit capture for `Remember that …`.
- [x] Added relevant-memory retrieval and injection into model context.
- [x] Added SQLite conversation persistence.
- [x] Added conversation APIs and memory APIs.
- [x] Added a Memory management drawer in the UI.
- [x] Added new unit/integration tests for memory and conversation persistence.

## Validation still required before merge

- [ ] Pull the active branch onto the founder Windows PC.
- [ ] Run the complete Python test suite.
- [ ] Run compileall.
- [ ] Start the real local Qwen/llama.cpp server.
- [ ] Smoke-test memory add / pin / delete.
- [ ] Smoke-test `Remember that my birthday is …` then ask about that fact in a later turn.
- [ ] Reload the browser and confirm the conversation restores.
- [ ] Verify no secret, `config/local.json`, model weight, or `.helix` database is staged.
- [ ] Visually inspect desktop command-center layout before merging PR #1.

## Not yet implemented

- [ ] Streaming token-by-token responses and cancellation.
- [ ] Internet retrieval / browsing.
- [ ] File ingestion and retrieval.
- [ ] Dedicated trained/selected model per role.
- [ ] Voice / wake word.
- [ ] Email/calendar/personal connectors.
- [ ] Terminal/repository/deployment executors.
- [ ] Proactive assistant automations.
- [ ] Multi-user authentication and strict account-level memory isolation.
- [ ] Cloud autoscaling and subscriptions.
- [ ] Training/fine-tuning/distillation pipeline.
- [ ] Frontier benchmark evidence against Astra, Claude, Gemini, Grok, and leading open/Chinese models.

## Safety interpretation

User memory is application state for helping that user. It is not automatically training data.

The current memory schema includes `user_id`, but the application remains a single-owner local prototype. Do not deploy it as a multi-user service until authentication, authorization, encryption, account deletion/export, rate limits, abuse controls, and tenant-isolation tests exist.
