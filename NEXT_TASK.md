# Next implementation task · HX-003

## Objective

Validate the now-useful local stack — streaming, memory, web grounding, sourced learning, files, and conversation history — on the founder Windows PC. After the branch is green, move Engineer toward a **read-only project workspace** without introducing paid inference or unsafe shell authority.

## Run the local engineering loop

```powershell
cd "C:\Users\Administrator\OneDrive\Desktop\helix"
git fetch origin
git switch feat/codex-inspired-ui-v02
git pull --ff-only
.\DEV_LOOP_WINDOWS.cmd
```

Keep the separate llama.cpp/Qwen server running on port 8080.

## Founder smoke test

1. Send a normal prompt and confirm response text streams progressively.
2. Start a longer prompt and press **Stop**.
3. Save a memory and verify later recall.
4. Create several chats, reload, and switch between recent conversations.
5. Leave Web on **Auto** and ask a clearly current question.
6. Confirm source links appear.
7. Cycle Web to **On** and **Off** and verify the behavior is explicit.
8. Turn live web off and ask a related question; inspect whether sourced cached knowledge is reused.
9. Open Memory and inspect/clear learned web knowledge.
10. Attach a small code/text file and ask Engineer to review or explain it.
11. Remove the file.
12. Switch Dark/Light modes.
13. Run `git status --short` and verify runtime/private files are ignored.

## Next build after validation

### Engineer read-only workspace
- explicit local project selection/import;
- project-scoped file index;
- code-aware relevance retrieval;
- repository tree/search view;
- diff planning without mutation;
- project memory and architecture notes;
- no automatic shell execution.

### Then controlled engineering actions
Only after the read-only workspace is stable:

- sandboxed command execution;
- allowlisted read/test/build commands;
- diff preview before writes;
- explicit approval boundary for destructive actions;
- Git status/diff/test evidence;
- no silent deployment or credential use.

## Completion gate

PR #1 is locally green and the live Qwen smoke tests above pass. Until then, do not merge or advertise streaming/web/files as production-validated.
