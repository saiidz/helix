# Windows startup recovery and regression gates

This change repairs startup diagnostics and a repository-search regression. It
does not implement a sandbox, emergency lockdown, model training or deployment.
The native founder PC and live local-model answers still require verification.

## What changed

- `DEV_LOOP_WINDOWS.cmd` now reports the exact failed stage and a nonzero exit.
  It checks tracked changes before updating, names the remote branch explicitly,
  and never resets, stashes, force-pushes, merges a PR or kills another process.
  Git still refuses conflicting untracked files instead of overwriting them.
- Full pytest, compileall and offline intelligence evaluation remain required.
  The evaluation runs as `python -m tools.intelligence_eval` from the repo root.
  `pip check` and a private-file tracking gate are added, not substituted for tests.
- `tools/check_startup.py` validates required files, Python 3.13, local model
  configuration and launcher imports. Full mode checks app-port availability and
  the configured servers' model lists; no hardcoded port 8080 assumption remains.
  `--offline` performs no socket probes. Neither mode generates a model response.
- Model-list probes use literal loopback HTTP, no proxy environment, redirects,
  authorization headers, cloud providers or demo providers. Responses are bounded.
  Each unique endpoint is probed once per invocation. Three roles may share a model.
  Model IDs must match those advertised by the server; configure a server alias
  consistently when using one. List availability is not model-quality evidence.
- Local configuration errors are summarized without dumping values. Do not share
  local config, access keys, raw chat history or unreviewed test output publicly.
- `START_HELIX.cmd` preserves the child launcher's actual exit code outside batch
  parentheses. Auto startup refuses failed preflight and failed key generation;
  it retains the existing browser auto-connect behavior. That browser opener is
  timer-based, not a verified browser/backend handshake, and port preflight is
  only a point-in-time check. No race-free process supervision is claimed.
- Agent startup checks readiness but still requires explicit startup and per-action
  approvals. Approved commands remain unsandboxed. Use a standard Windows account.
- `CHECK_HELIX.cmd` offers the same readiness diagnostic without fetching, changing
  Git, installing packages, starting HELIX or terminating an occupied-port process.
- Project retrieval now ranks lexical relevance before README/manifest/recency
  preferences. These preferences only break ties. Existing retrieval limits,
  project scope, import protections and original regression tests are unchanged.

## Use on the founder PC

Stop only the old HELIX web app in its own terminal with Ctrl+C; keep the local
model server running. Update the development branch with fast-forward-only Git
operations and stop on any error. Do not discard local changes to make an update
succeed. Then run:

```powershell
.\DEV_LOOP_WINDOWS.cmd
```

This validates and starts normal chat, not the execution Agent. To diagnose
without updating or starting the app:

```powershell
.\CHECK_HELIX.cmd
```

A port-in-use failure deliberately does not kill anything. A model-list failure
is not success and does not fall back to demo or cloud. Missing dependencies
should be handled with the existing `SETUP_WINDOWS.cmd`; no install is silently
performed by the checker. `HELIX_NO_PAUSE=1` skips interactive pauses for native
batch tests only; it does not bypass validation or permissions.

## Validation evidence and limits

The first full hosted Linux run (35420631462, job 105837519223) exposed
`tests/test_projects.py::test_project_create_import_retrieve_delete`: the README
outranked a matching implementation. The exact original project module and test
were reconstructed locally and their Git blob hashes checked before editing.
The original test reproduced the failure locally; its assertions were unchanged.

After repair, 52 focused checks passed locally on Python 3.13.5, covering the
original project tests, six ranking regressions, configuration rejection,
loopback HTTP fixtures, redirects, response bounds, private-file tracking and
startup failure reporting. Three native cmd.exe tests were skipped on Linux;
one full-application import test was excluded from the partial local checkout.
Python compilation passed for the changed modules and new tests.

The new GitHub workflow runs the complete repository on standard Windows and
Linux runners, with read-only repository permissions, no persistent checkout
credentials, no model keys and no deployment or merge steps. It runs only for
this public repository to avoid enabling paid/private capacity. The latest
workflow results, not this document, establish whether a particular commit is
green. Native startup regression tests run separately before the full suite so
an unrelated full-suite failure cannot hide their evidence. Full-suite output
includes test names and timed stack dumps to diagnose stalls; a timeout is failure.

CI is not the user's Windows installation, an actual downloaded model, a GUI
end-to-end smoke test, or a sandbox validation. Merge conflicts and the founder
Windows/live-model acceptance gate remain separate from a passing CI run.
