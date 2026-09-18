# HELIX Engineer workbench and included build plan

Updated 2026-09-18. This is a development-branch preview, not evidence of deployment to the founder PC. It extends the existing local app without granting the main chat a shell or unrestricted filesystem access.

## Open the preview

After updating `feat/codex-inspired-ui-v02` and restarting HELIX with its normal `python -m helix` launcher, open:

```text
http://127.0.0.1:8765/engineer
```

The launcher prints this address. The equivalent static entry is `/static/engineer.html`, including when an app is constructed directly with `server.create_app`. Main-chat navigation and its read-only Projects module are unchanged by this preview.

Expand **Local connection** and paste the existing HELIX local access key printed by the terminal. This is not a cloud-provider key. It is kept only in the workbench tab. Choose files or a folder, select one file, enable relevant skills, and choose **Analyze** or **Draft change**.

## What this addition implements

- Explicit browser-selected text/code files and folder browsing. No silent disk scan or server-side arbitrary path reader. File contents stay in tab memory until the user sends an analysis/draft request to the local HELIX backend.
- Code explanations, debugging, review, refactoring suggestions, test generation, and new-file drafts through the existing Engineer model. These are model outputs, not verified tests.
- Four built-in advisory skills: Debug carefully, Code review, Safe refactor, and Test design.
- Markdown `SKILL.md` import, display-only name/description metadata, inspectable instructions, and explicit enable/disable. Imported skills start disabled. This is an instructions-only subset, not full Agent Skills execution: no bundled scripts, resource loader, automatic installation, or automatic skill selection.
- Complete single-file draft validation, exact target-path checking, changed-line and complete-file previews, explicit approval, and browser write permission before an existing selected file can be saved.
- SHA-256 stale-content checks before saving, read-back verification after saving, original-file backup download, and an in-tab restore action. A file already changed since selection is rejected. This is not an OS-level compare-and-swap transaction; other software can still race the read/write operation.
- Read-only upload/download fallback when native file handles are unavailable. New-file drafts are downloaded, not silently written into a folder.
- Dark charcoal default, light mode, responsive layout, plain-text rendering of all model/file/skill content, and stop-request control.

## Boundaries and current limits

Files must be supported UTF-8 text/code, at most 350,000 bytes each. Selection is bounded to 400 files and 12 MB total, with directory depth/enumeration limits. Hidden/generated directories and common credential/runtime filenames are excluded. Filename exclusions are NOT a content secret scanner; users must review files before sending them.

Each model request covers one selected file: analysis includes up to 10,000 characters, explicitly marked as an excerpt when truncated. Direct-edit drafts require a complete original file of at most 6,000 characters. The existing model output cap is 2,048 tokens; malformed/truncated JSON produces no applicable change. At most three skills are enabled per request, with 6,000 characters per skill and twelve imported skills per tab.

Files, imported skills, handles, and recovery originals are session-only. Opening another selection, clearing, or refreshing can discard recovery; download originals before important changes. Do not treat this as version control. A failed save is reported as uncertain and retains the draft/original for inspection; there is no automatic retry.

The workbench sends `allow_external=false`, `web_enabled=false`, `memory_enabled=false`, and `max_cost_usd=0`. It does not save a chat conversation or upload selected files into persistent Projects. Applicable drafts require a real local provider, not the demo provider. The normal chat's Web Auto/On/Off controls are unaffected.

Stop aborts the browser request; the synchronous local backend may still finish inference. It never triggers a write.

Not implemented: terminal execution, running generated tests, bundled skill scripts, whole-repository autonomous editing, multi-file transactions, Git commits/push/merge, deployment, PDF/Office/image extraction, or persistent skill management.

## What is included in the HELIX development plan

| Area | Scope and status |
| --- | --- |
| Companion | Existing development branch: local chat, private memory, conversation history, task list, and planning context. |
| Engineer | Existing read-only Projects plus this new file/skills/review-and-save workbench preview. |
| Sage | Existing research/reasoning role using the configured model; not a separate trained frontier model. |
| Internet and freshness | Existing normal-chat web research, source links, sourced local knowledge, and freshness handling. This is retrieval, not model retraining. |
| Interface | Existing streaming/Stop and dark/light main UI; workbench has a separate dark/light page. |
| Cost and privacy | Local-model-first founder build with no new paid API, hosted service, or subscription required by this addition. Cloud fallback stays disabled. Hardware/electricity and any separately approved future hosted services are not supplied by the code. |
| Next engineering stage | Planned, not delivered here: bounded test/command sandbox, persistent skill management, broader file formats, multi-file change sets, and controlled Git/CI/deployment with clear authorization. |
| Later integrations | Voice, email/calendar, and multi-user/cloud subscriptions remain separate roadmap work, not active included connections. |

This is a development scope, not a priced HELIX subscription tier or a promise of unlimited compute.

## Validation performed for this change

In an isolated Linux development environment:

- `node --test tests/engineer_workbench.test.mjs`: **40 passed**, using Node 22.16.0. Includes unsafe paths, binary/UTF-8 rejection, inert skill import, context limits, no-cloud/no-spend request settings, exact-target draft validation, approval/permission checks, stale-file rejection, draft integrity, write failure, and save/restore with synthetic file handles.
- `python -m pytest -q tests/test_engineer_workbench.py`: **1 passed**, executing the same 40 Node checks through pytest. This is not 41 independent feature tests. Without Node, this wrapper explicitly skips; Node is a development-test dependency, not a HELIX runtime dependency.
- `node --check helix/static/engineer.js`: passed.
- Python compile checks for the changed launcher and pytest wrapper: passed.
- Eight offline Chromium DOM-fixture checks passed: page initialization; local-only draft request and read-only fallback; draft download; dark/light/mobile layout; disabled-by-default imported skill; explicit approval and save/restore through synthetic handles; stale-file refusal; no uncaught UI JavaScript errors.

Managed Chromium blocked navigation in this environment. The UI fixture loaded the DOM/scripts directly with mocked inference, hashing support, and file handles. It does NOT establish real module serving, production CSP compatibility, browser-native permissions, Windows I/O, or live-model quality. No browser policy was changed. These limitations must not be represented as a full end-to-end pass.

The entire repository test suite was not run in this isolated checkout. Existing main-branch merge conflicts and founder validation gates are not resolved by these tests.

## Required Windows gate before merge/deployment claims

Run the existing `DEV_LOOP_WINDOWS.cmd` full test/compile/evaluation gate. In a supported desktop browser, open `/engineer`, use a disposable small text/code file, verify a real local-model draft, deny write permission once, approve a reviewed change, inspect the actual file, restore it, and test an externally changed file. Check both themes and the upload/download fallback. Verify static module loading and CSP in the real app. Re-test existing chat, web, memory, files, and Projects. Keep PR #1 unmerged until its validation gate and conflicts are resolved.
