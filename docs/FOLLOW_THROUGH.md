# HELIX Follow-Through — build plan and local prototype

Checkpoint: September 19, 2026. Feature branch: `feat/helix-follow-through-v01`, stacked on `feat/helix-product-v04`. No automatic merge or deployment. The founder-machine gate still applies.

## Product contract

Turn a user-selected request into a reviewed, persistent goal with a completion rule, current next step, optional explicit deadlines, provenance and correction history. Keep exactly Companion, Engineer and Sage. A successful model response, a tool receipt and a completed goal are different facts.

This slice is a **local tracker**, not a monitoring service or autonomous assistant. There is no email/calendar connection, notification scheduler, verification engine, automatic source ingestion or new execution authority.

## Implemented in this slice

- `Track this` on saved user messages and a manual source-text form. Nothing is captured automatically. The user reviews the source, goal and completion rule before saving.
- Authenticated outcome CRUD, bounded list pagination, private JSON export and deletion.
- Current next action, waiting party, explicit offset-aware deadline/check date and timezone label. Natural-language dates are not silently inferred.
- Needs you / Waiting / Closed views. A past check date changes the computed view; it does not schedule or send a notification.
- Revisioned corrections and source provenance. Old deadlines remain in history, not active model context.
- User-reported resolution with a required note; every record has `completion_verified: false`. No model or API caller can create a `verified_complete` state.
- Explicit selection via Use in chat shares only that record's latest reviewed fields with Companion, Engineer **chat**, or Sage. Raw historical source text and unrelated personal memories are not added by this feature. Starting or switching a conversation clears this selection.
- Selected outcomes do not attach to or authorize terminal Engineer jobs. While a tracker is selected, the main chat stays advisory rather than silently starting a contextless Agent job. Clear the selection to use existing job escalation; its approvals and lockdown remain unchanged.
- Native modal, keyboard focus handling, mobile entry, and existing dark/light theme tokens.

## Design and storage

`follow_through.py` owns schema, validation, optimistic versions and transactions. `follow_through_api.py` installs routes inside the existing server authentication and cross-origin/body-limit middleware. The tracker uses the same SQLite file as MemoryStore, with prefixed tables, owner-scoped queries and foreign keys.

Creation is idempotent by owner and request identifier. Reusing an identifier with changed content returns 409. Corrections and deletion require the expected revision; conflicting writes return 409 rather than overwriting another window. State and event writes commit together. There is no retrying external side effect because this slice has no external executor.

A linked source is checked against a saved **user** message in the authenticated owner's conversation; assistant text or invented source text cannot masquerade as that message. Manual input remains clearly user-provided, not independently verified. Source copies are immutable; corrections update the reviewed goal fields.

Conversation deletion cascades to its linked trackers and their events in the same database transaction. Deleting a tracker preserves its original chat message. Export includes source text and the complete history, and must be handled as private data. In-app history is capped at the latest 100 revisions with an explicit truncation label.

This inherits HELIX's single-owner, loopback/local-key boundary. A user_id filter is not multi-tenant authentication. SQLite is not newly encrypted by this change. Deletion removes live records but is not a secure-erasure guarantee for free pages, journals, backups, screenshots or prior exports. Real-client/public pilots remain gated on privacy and deployment hardening.

## Build phases and completion gates

| Phase | Scope | Gate |
| --- | --- | --- |
| 0. Local prototype — this branch | Reviewed capture, state/history, current-context selection, export/delete, UI | Offline regressions plus actual browser smoke; founder Windows/live-model check before merge |
| 1. Workflow validation | Small consented pilot on real approval/deliverable obligations; supervised drafts | Less total supervision than existing reminders; inspect false positives and closures |
| 2. Read-only connection | One provider, selected sources, explicit OAuth review, incremental sync, stale/catch-up state | No duplicates, cross-account leaks, or assumption that an acknowledgment is approval |
| 3. Durable monitoring | Persisted check jobs, worker availability, quiet hours, bounded retries and cancellation | No promise of monitoring while the host is off; restart/reconciliation tests |
| 4. Controlled actions | Reuse Engineer receipts/jobs where appropriate; exact payload approvals and narrow verifiers | OS execution containment, ambiguous-response reconciliation, no duplicate side effects, no unsupported verified completion |

Do not add billing, additional model roles, cloud capacity, training, unattended PC control or broad connectors as part of this local slice. Existing Engineer jobs are retained, not replaced by a second job framework.

## Validation

Run from the repository root:

```text
python -m pytest
python -m compileall -q helix tests tools
node --check helix/static/app.js
node --check helix/static/follow_through.js
python -m tools.intelligence_eval
```

Optional real-browser smoke:

```text
python -m pip install -r requirements-browser.txt
python -m tools.follow_through_smoke
```

The smoke uses an installed Google Chrome/Chromium executable when available; otherwise install Playwright Chromium in the test environment. It starts a loopback demo app using a temporary database and synthetic data. It exercises capture, review, correction, reload, provenance/history, user-reported closure, context clearing, dark/light desktop and 390px mobile rendering. It produces `.ci-artifacts/follow-through/` screenshots and a JSON report. It does not call a real model. Browser dependencies are optional development dependencies, not runtime requirements.

CI retains the existing Ubuntu/Windows regressions, read-only token and no-paid-capacity restriction, adds the feature branch, and runs browser smoke on Ubuntu. A one-day **tracked-source-only** artifact allows exact-revision review; no working directory, credential or runtime database is archived. Source snapshot availability does not imply validation passed. Browser evidence is separate.

## Founder-machine acceptance before merge

Run the normal reviewed launcher from the repository directory as a standard user. Create a tracker from a saved user message, correct it, reload/restart and confirm persistence. Inspect both themes. Try an ambiguous date, a stale second-window edit, a user-reported closure and explicit reopen. Select a tracker, switch Companion/Engineer chat/Sage and confirm the latest reviewed fields are used. Clear context before starting an existing Engineer job; verify its exact approvals and lockdown still behave as before.

No evidence of local fixture tests should be presented as proof that Qwen interpreted every case correctly. Measure that separately. No public exposure, merge or deployment is authorized by this document.
