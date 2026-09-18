# HELIX Engineer Agent — reviewed local execution preview

Updated 2026-09-18. This is an opt-in development-branch implementation, not a claim that HELIX now has every Codex capability, that a live local model is reliable, or that the founder Windows PC has been deployed.

## What was added

The new `/agent` page and terminal entry use the existing local Engineer model to perform a bounded inspect → propose → approve → execute → verify loop. The main chat, read-only Projects, and `/engineer` single-file workbench keep their existing behavior. No new paid API, cloud fallback, orchestration framework, daemon, or fourth reasoning role is introduced.

The operator explicitly chooses one directory when starting HELIX. The model cannot change that directory through HTTP. Within it, the new agent can list paths, search text, read file slices, propose exact replacements across multiple files, create a text file in an existing directory, request commands, observe exit codes/output, and continue investigating a failure. Runtime decisions come from structured JSON actions, not from executing model-generated prose.

| Capability | Delivered scope |
| --- | --- |
| Repository access | Actual selected local directory, not just browser-uploaded snapshots. UTF-8 text/code up to 350,000 bytes per file. Reads are chunked and include full-byte SHA-256 hashes. Listing/search are bounded and can report truncation. |
| Multi-file edits | Up to eight files in one reviewed change set, one unique exact replacement per file. Full review includes a diff and JSON-escaped replacement. No file-deletion tool. New files require existing parents. |
| Execution / repair | Explicitly approved command argv, working directory, timeout, captured output, exit status, and a bounded agent loop. Python uses HELIX's interpreter. Installed test/build/Git tools may be proposed through the same command approval. |
| Skills / project conventions | Root AGENTS.md plus explicit repository skills at `.agents/skills/NAME/SKILL.md`. The agent is instructed to inspect relevant nested AGENTS.md. Skill files persist on disk; up to three are enabled by name for a task. References may be read, scripts may be proposed as separately approved commands. This is not full Agent Skills/MCP interoperability or automatic skill installation. |
| Approvals | Separate approve/deny requests for edits and commands. HTTP approval identifiers are random, single-use, task-scoped, and checked by the host. Model JSON cannot grant approval. |
| Recovery / evidence | Original bytes and a hash manifest are saved before writes; changed files are read back. Actual edit/command receipts are saved separately from model summaries. Partial failures are explicitly reported. |
| Interface | Dark default, light mode, mobile layout, task/skill fields, activity log, complete action previews, and Stop. Existing chat and workbench designs are not replaced. |

## Critical safety boundary: NOT an OS sandbox

The path restrictions apply to HELIX's built-in read/edit tools, **not to an approved executable**. An approved Python, PowerShell, test runner, build script, Git hook/helper or other program runs with the account's privileges. It may read/write outside the repository, use the network, access user-readable secrets, or start applications. A restricted working directory and `shell=False` do not isolate a process. There is no unattended approval mode in this preview.

Run as a standard Windows user, not Administrator. Use disposable copies for the first test. Do not enable execution against an untrusted repository until it has an actual OS isolation boundary. An instruction prompt and approval dialog are not a security sandbox. Only approve an action whose exact content and effects you understand.

The tool refuses path traversal, Windows alternate data stream syntax, common device names, symlinks/junctions/reparse points, hard-linked files, common secret/runtime filenames and generated directories. Filename filtering is not secret-content detection. There is not yet full `.gitignore` semantics. Large repositories may need narrower tasks/directories. Other local processes can race filesystem checks; this is not protection against a hostile process running under your account.

Commands have no implicit shell, do not inherit common API-token environment variables, have closed stdin, and require a visible argv approval. Explicit shells can still be requested. Windows `.cmd`/`.bat` wrappers are not executed implicitly; using them requires an explicit reviewed interpreter invocation. Process-group/tree termination is best-effort, not an OS containment guarantee. Detached descendants and externally launched applications can outlive a command.

The API uses the existing local key, loopback host/origin checks, and one active agent task at a time. The browser retains the key only in tab memory. No workspace-setting endpoint is exposed. Stop cancels pending approval and prevents the next model action; already completed writes stay applied. A synchronous in-flight model call may finish before the task stops. Closing the browser tab alone does not stop the task; use Stop or shut down HELIX.

## Start on Windows

Stop only the old HELIX web server; keep the local model server running. Update the development branch, run the existing repository validation gate, and then start the opt-in launcher:

```powershell
cd "C:\Users\Administrator\OneDrive\Desktop\helix"
.\START_HELIX_AGENT.cmd
```

This launcher requires the existing `.venv` and `config/local.json`. It chooses the HELIX repository as the workspace and serves the agent at:

```text
http://127.0.0.1:8765/agent
```

Paste the local access key printed by HELIX into **Connection**, then give it a narrowly scoped first task. Review each action before approving it. An example task is: "Inspect the tests for this module, reproduce the failure, propose the smallest fix, then re-run the relevant test. Do not commit, push or deploy."

Choose a different project explicitly through the launcher arguments, from the HELIX directory:

```powershell
.\.venv\Scripts\python.exe -m helix --config config/local.json --workspace "C:\path\to\project"
```

Without `--workspace`, the normal app still starts but agent repository/execution access remains disabled. `START_ENGINEER.cmd` provides a terminal-only session for the HELIX repository. Advanced terminal use:

```powershell
.\.venv\Scripts\python.exe -m helix.engineer_agent --config config/local.json --workspace "C:\path\to\project" --skill debugging
```

The terminal requires a real interactive input stream for approvals. There is no bypass/auto-approve argument. Default limit is 24 agent steps, configurable up to 60. An individual command defaults to 120 seconds, with a maximum of 600 seconds and 32,000 captured output bytes. A human approval expires after ten minutes. Small model contexts receive explicitly truncated observations while retaining file hashes and continuation offsets where possible.

## Recovery

Each task stores recovery data under:

```text
<your home>/.helix/engineer-history/<session>/<change-set>/
```

`manifest.json` identifies original backup files and before/after hashes. `receipts.json` records actual actions and outcomes without persisting command output. The originals may contain private source code: protect and manage this directory accordingly. POSIX permission modes are not a Windows ACL guarantee.

A multi-file change is **not an atomic transaction**. If a later write fails, earlier files may already be changed. The result reports `partial_or_uncertain`, changed paths and the recovery directory. There is no automatic rollback that might overwrite concurrent human edits. Inspect the manifest, compare the current file with its recorded after hash, and manually restore only the intended originals. New-file entries have no original backup. The existing single-file workbench's in-tab restore is separate from these persistent agent recovery copies.

## Cost and model boundary

The agent requires a `local` Engineer profile with zero configured input/output prices. Demo/cloud profiles are refused. The existing Settings validator and transport enforce a literal loopback HTTP endpoint, no proxy environment inheritance, and no redirects. No model weights are trained or upgraded by adding these tools. Agent success still depends on the configured local model, available context, repository, and verification. Normal chat's existing web research controls are unchanged; this agent has no separate web/browser tool. Explicitly approved programs may themselves use the network.

## Validation recorded

Performed in an isolated Linux checkout of the new modules, not a complete clone of the existing app:

- `python -m pytest -q tests/test_engineer_agent.py tests/test_engineer_api.py`: **76 passed**.
- Real filesystem tests cover hashes, stale-file refusal, denial, backups, exact multi-file changes, partial failure and unsupported paths.
- Real subprocess tests cover output, exit codes, environment filtering, timeout, output limits and cancellation. A deterministic model fixture reproduces a failing unit test, applies a repair and then records a passing unit test. This proves the tested execution loop, not autonomous live-model reasoning.
- Authenticated ASGI router tests cover access-key/origin/host checks, disabled-by-default workspace access, replay/wrong approvals, stop, one active task, event cursors and static asset routes. These are not a full test of the existing HELIX server.
- **Eight DOM fixture checks passed** for connection/state, pending edits, dark/light layout, mobile overflow, command warning, denial, inert output and no uncaught JavaScript errors.
- Python compilation and `node --check helix/static/agent.js` passed.

The managed Chromium environment blocked navigation to the local HTTP server with `ERR_BLOCKED_BY_ADMINISTRATOR`. No browser policy was changed. The DOM checks used simulated fetch responses and directly loaded assets; they do not prove real browser HTTP/CSP integration. Screenshots are explicitly labeled offline UI previews. Native Windows filesystem/process behavior, full existing app regression tests, the real local model and deployment remain unverified.

## Remaining gates and capability gaps

Before any merge/deployment claim: run `DEV_LOOP_WINDOWS.cmd` and the full repository suite; resolve PR #1's existing merge conflicts without losing branding; then test `/agent` with a disposable repository, a real model, denial, stale-file conflict, approved test execution, Stop, recovery, actual CSP/static module loading and both themes. Regression-test existing chat/web/memory/Projects/workbench behavior.

Not delivered: OS-level Windows/container sandboxing; desktop screenshots/mouse/keyboard or browser automation; unattended whole-PC control; native MCP connectors; managed GitHub/CI/PR/deployment integration; resilient task resume; automatic recovery rollback; binary/PDF/Office extraction. Git commands can be requested through explicit command approval, but this is not managed GitHub integration. These require additional implementation and validation rather than simply a more permissive prompt.
