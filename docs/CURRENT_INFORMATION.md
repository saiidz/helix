# Current date and internet verification

## What this change does

Every normal chat request now gets a fresh host-local date and timezone-aware
timestamp in the primary system message, for Companion, Engineer and Sage.
The year is not hardcoded. The host's operating-system clock and timezone must
be correct; a future cloud deployment will need explicit user-timezone handling.
The separate opt-in execution agent is not changed by this chat fix.

The same context distinguishes permission to research this request from proof
that research succeeded. An old assistant statement about a 2024 cutoff is not
a source for the current date or runtime capabilities. No model training cutoff
is configured by this change, and no weights are trained or replaced.

The existing read-only web connector and Web Auto / On / Off controls are
preserved. Web On requests research; Web Off must not make a web request. Auto
uses the existing browser-side heuristic, not an exhaustive freshness classifier.
An explicit request with Web On is the appropriate first connectivity test.
Sources, empty-result notices and failures continue to come from the backend.
No source means no claim of current verification. Recently retrieved material
can still describe old events. Sources remain untrusted data, not tool authority.

This change does not enable paid APIs, cloud inference, terminal access, PC
control, public hosting, or background crawling. It is not the Emergency
Lockdown implementation. Existing execution-sandbox limitations remain.

## Activate on the founder Windows PC

Keep the local model endpoint running. Update the existing development branch
without discarding local changes, then restart only the HELIX app process.
Do not start the execution-agent launcher for this check.

```powershell
cd "C:\Users\Administrator\OneDrive\Desktop\helix"
git status --short
git fetch origin
git switch feat/codex-inspired-ui-v02
git pull --ff-only
.\DEV_LOOP_WINDOWS.cmd
```

If Git reports local conflicts or the full validation gate fails, stop and
resolve that specific problem; do not reset or force-push. Use the normal
`START_HELIX.cmd` launcher after validation if the app is not already started.
The directory name does not require running PowerShell as Administrator.

## Explicit connector check

```powershell
.\.venv\Scripts\python.exe tools\check_web.py
```

This sends a small, public test query through the existing free connector. It
makes no model call and reads no local private configuration. Exit 0 requires
both search results and readable page content. Exit 1 means the check failed;
exit 2 means invalid input, no results, or only partial retrieval. The output
identifies the check time and sources, not a global guarantee of internet access.
It checks this checkout, not an already-running older backend. Provider blocking,
rate limits, DNS problems, or restricted page formats can still prevent retrieval.

## Live acceptance checks still required

Ask the normal chat for today's date with Web Off. Compare it with the Windows
clock. Select Web On and ask for current information with supporting sources.
Verify source dates and answer content; a source list alone does not prove a
claim is correct. Test Web Off again and confirm no fresh-search claim is made.
Repeat the cutoff/capability question in an existing conversation containing the
old 2024 answer. The live model must distinguish its unverified training cutoff
from current runtime date and source-backed knowledge.

Focused fixture tests do not establish these Windows/live-model results. PR #1
remains subject to its full regression, integration and founder-machine gates.
