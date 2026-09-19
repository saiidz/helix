# HELIX Emergency Lockdown — v0.3 safety gate

This slice adds a persistent, fail-closed Emergency Lockdown for reviewed
Engineer actions. It is a safety control, **not an OS sandbox**.

## Activation

The main HELIX header and Engineer Jobs drawer expose an Emergency Lockdown
button. The Windows checkout also includes:

```powershell
.\EMERGENCY_LOCKDOWN.cmd
```

The external script writes the same local safety state and does not require the
HELIX browser or model to be responsive.

Lockdown blocks new Engineer jobs and approvals. The Workspace tool layer checks
it before reads, edits and commands, again after approval, before file
replacement, and while a command is running. A running command is terminated
when the lock is observed. Pending approvals become invalid.

The lock persists across HELIX restarts. Safety-state read failures also disable
Engineer actions rather than granting authority.

Already completed file writes or external effects are not rolled back.

## Reset

There is intentionally **no HTTP unlock endpoint**. Reset only from a separate
interactive local terminal:

```powershell
.\RESET_HELIX_LOCKDOWN.cmd
```

The reset command prints a generation-specific phrase that must be typed exactly.
The normal Engineer command runner has stdin disconnected, so the supported reset
flow cannot run through that tool.

## Remaining containment limitation

Engineer commands are still processes under the same OS user. A user-approved
program can access user-readable host files/network outside the repository.
Therefore this lockdown is not an independent security boundary against arbitrary
same-user native code. Real execution containment remains the next gate before
unattended autonomy, production credentials, or broader computer control.

Do not market this as zero-risk or as a complete sandbox.
