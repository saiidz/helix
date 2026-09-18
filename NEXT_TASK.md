# Next implementation task · HX-002

## Objective

Validate the new memory + scored-routing intelligence layer on the founder Windows PC, then add **streaming responses and cancellation** without introducing paid inference or cloud dependencies.

## Current inputs already known

- Windows founder machine.
- Local Qwen3 4B Q4_K_M served by llama.cpp.
- llama.cpp API available on loopback port 8080.
- Helix app available on loopback port 8765.
- Three Helix roles: Companion, Engineer, Sage.
- Local provider cost currently $0.
- Persistent-memory implementation is now present on the active feature branch.

## Validation loop

1. Pull `feat/codex-inspired-ui-v02`.
2. Run:
   ```powershell
   & ".\.venv\Scripts\python.exe" -m pytest -q
   & ".\.venv\Scripts\python.exe" -m compileall -q helix tests tools
   & ".\.venv\Scripts\python.exe" tools\intelligence_eval.py
   ```
3. Start llama.cpp and Helix.
4. In the UI, add a memory manually and verify it appears.
5. Pin/unpin and delete a memory.
6. Tell Helix: `Remember that my birthday is September 14.`
7. Start another relevant turn and confirm Helix can retrieve that stored fact.
8. Reload the browser and confirm the current conversation restores.
9. Try several ambiguous prompts and confirm the route panel shows a sensible role, confidence, and fast/deep mode.
10. Check `git status` for secrets/runtime files before any merge.

## Next implementation after validation

Add streaming/cancellation:

- stream model output from the local compatible provider;
- show tokens progressively in the chat;
- allow user cancellation;
- preserve idempotency and cost accounting;
- avoid exposing hidden reasoning content;
- give Companion a fast response path;
- keep Sage able to use a larger reasoning budget;
- add tests for disconnects, cancellation, incomplete upstream streams, and uncertain cost accounting.

## Completion criteria

Memory tests and live smoke tests pass on the founder Windows machine, no private memory database or local config is committed, and a streaming implementation is ready in the same engineering loop with zero paid credits.
