# HELIX Useful v0.3 — first usable engineering slice

This branch starts moving HELIX from feature plumbing toward a coherent product.
The first slice deliberately reuses the existing reviewed Engineer Agent instead
of adding another agent or model.

## What changes for the user

The main HELIX command center now contains **Engineer Jobs**. When HELIX was
started with an explicit workspace, the drawer can start one bounded engineering
job, show its live inspect/edit/test activity, present the exact edit or command
for approval, stop the task, and review recent local job history.

The separate /agent page still exists for compatibility, but it is no longer the
only way to use the reviewed engineering loop.

Job metadata and bounded events are stored locally in the engineer-jobs SQLite
database under the HELIX home data directory (or the test-specific path).
Finished history survives UI/app restarts. **Execution does not resume after a
process restart.** Any job that was queued/running/waiting/stopping when a new
process opens the store is marked interrupted rather than falsely shown as
still running.

## Safety boundary

This does **not** solve the OS sandbox problem. Command execution remains
unsandboxed and retains the existing exact-action approval warning. The agent
cannot select a workspace through HTTP; the operator still chooses it at process
startup. No unattended approval, desktop control, paid inference, push, merge or
deployment authority is added.

Persistent history can contain task text, model tool actions and command/result
metadata. It stays local and should be treated as private engineering history.
Exact pending approval previews are kept in the live process and are not added as
a separate durable preview record.

## Next v0.3 gates

1. Full Windows/Linux regression on this branch.
2. Founder-machine smoke test from the main app using a disposable repository.
3. Add independent Emergency Lockdown + real execution containment before
   enabling unattended engineering.
4. Add structured Git branch/diff/commit/PR flows after containment, rather than
   widening raw command authority.
5. Build held-out real-repository task evaluation around verified outcomes.

Do not call this autonomous or production-safe yet.
