# Reviewed learning from chats

## Implemented scope

HELIX can turn selected saved chats into reviewed personal memory. This release
is **not automatic background learning, shared learning across users, or model
weight training**. It introduces no additional model calls, paid services or
third-party dependencies.

The normal `python -m helix` launcher installs a separate `/learning` page and
prints its address. The existing main chat, Engineer workbench, Engineer Agent,
provider settings and command-approval policy are unchanged. The Agent does not
consume these memories yet. Normal chat can retrieve approved entries through
its existing MemoryStore when Memory is enabled and the lexical query matches;
this is not guaranteed semantic recall or better model reasoning.

## Use

After updating the development branch, passing the existing Windows validation
gate, and restarting HELIX, open `http://127.0.0.1:8765/learning` (or the configured
port). Connect with the local access key printed at startup. The page retains
the key only in JavaScript memory, not localStorage or a URL.

1. Enable reviewed chat learning and save the setting. Default is off.
2. Explicitly select a saved conversation and click **Review selected chat**.
3. Inspect or edit each suggestion and choose **Approve memory** or **Dismiss**.

Enabling alone scans nothing. Reviewing a selected conversation authorizes
inspection of its last 100 user messages, including historical messages and
messages written with the chat Memory toggle off. It is not a temporary-chat
feature. No assistant responses, attached files, project files, web pages or
other conversations are candidate sources. The first release recognizes short,
single-line English statements such as `I prefer concise explanations.`,
`My project uses Python.`, `My timezone is America/New_York.`, or `My name is Alex.`
It does not infer personality or extract arbitrary facts from long conversations.

Suggestions remain outside usable memory until approved. Approval creates a
`reviewed_chat` entry in the original SQLite memory table, with source-chat and
source-message provenance in the review queue. An edited approval is still a
user assertion, not independently verified evidence. Duplicate approval is
rejected; concurrent approval can create only one memory.

## Consent, privacy and deletion

All learning-data routes require the existing local bearer key. Store queries
are owner-scoped and tested with two owners, but the running application is
still single-owner: this is **not authenticated multi-tenant separation**. Do
not expose this prototype publicly or share the local key as user accounts.

Off blocks new reviews and approvals; existing approved memories remain usable
until forgotten. Dismiss keeps a content-free fingerprint/tombstone to prevent
the same suggestion returning during another review. Forget removes that queue
entry and the memory created by this feature. Delete a source conversation and
SQLite cascades remove its queue entries and derived reviewed memories. A memory
that the owner independently re-saved through the existing manual-memory API is
preserved; learning cleanup must not delete separately authorized manual data.
Deleting an approved memory through the old Memory UI also hides and clears its
review-queue copy, without changing the old MemoryStore's soft-delete policy.

**Forget all learning data** clears this owner's queue and derived memories and
returns consent to off. It does not delete original chats, manual memories,
backups, exported files, or guarantee forensic erasure from SQLite/WAL/disk.
Exports contain private personal-memory records, not a training dataset. Keep
exports out of Git. Storage uses the existing local SQLite database; no new
at-rest encryption is claimed. Existing normal-chat external-inference consent
still governs whether retrieved memories could be included in an external model
request; the learning module itself makes no external request.

Candidate rules reject common secret/sensitive markers, code-like text,
multiline/long statements and common instruction-override markers. These are
best-effort filters, **not a reliable PII detector or a prompt-injection security
boundary**. Human review remains required. Learned text cannot grant tool
permissions; this feature does not touch executable tools or the Agent runtime.
Never connect learned text to automatic shell access or safety-policy changes.

## Files changed

- `helix/learning.py`: consent, bounded selected-chat extraction, approval,
  provenance, deletion, export and owner-scoped SQLite queries.
- `helix/learning_api.py`: authenticated local endpoints and page route.
- `helix/static/learning.html`, `learning.css`, `learning.js`: dark/light review UI.
- `helix/__main__.py`: install learning routes against the existing memory DB.
- `tests/test_chat_learning.py`: targeted unit/API/regression tests.
- This document records scope, results and next gates.

## Validation performed

`python -m pytest tests/test_chat_learning.py -q`: **55 passed** in the local Linux
test environment. Tests use the original `helix/memory.py` from parent commit
`91bc79504c9e491ea422f2d1afba59aa057fa7e3`, with its Git blob verified as
`0b3e841872d70aeabd5b0ec45136b475ce0e9a85`. Coverage includes opt-in, no implicit
scan, pending exclusion from retrieval, reviewed edits, replay and duplicate
protection, source deletion, preserving manual data, owner scoping, authenticated
API routes, malformed consent, extraction bounds, and concurrent approval.

`node --check helix/static/learning.js` and Python compilation passed.

**11 offline Chromium interface checks passed**, using simulated fetch transport
to real in-process FastAPI learning routes and the original MemoryStore. They
cover connection, default-off consent, selected-chat review, edited approval,
dark/light rendering, 390px layout, dismissal, forgetting, disconnect, and no page
JavaScript errors. This is not live browser networking: managed browser policy
blocked navigation to the local test server. Preview screenshots use synthetic
fixture conversations, not user data.

The full repository suite, original server/launcher integration, live inference,
and native Windows installation have **not** been verified by these checks.
No claim is made that any model trained or that this build is deployed.

## Next build order (planned, not implemented here)

1. Resolve the Windows update/startup failure, run the full app tests and live
   smoke checks, resolve PR conflicts, then merge only after validation.
2. Add an operator-controlled emergency stop and enforceable process isolation
   for code execution: least-privilege worker, scoped files, network policy,
   process-tree cancellation, restart controls outside model authority, and
   tested recovery. Do not claim that a prompt or folder picker is a sandbox.
3. Integrate review into the main chat UI. Add explicit per-chat/temporary-chat
   exclusions, correction and supersession, project-scoped retrieval, clearer
   memory-used evidence, and measured semantic retrieval. Automatic suggestions
   may be queued only with consent; promotion remains reviewed.
4. Add verified engineering feedback: failing test -> approved fix -> passing
   tests, storing reproducible outcomes rather than the model's own claims.
   Extend repository indexing and native document readers with scoped access.
5. Add authenticated user accounts and tested tenant isolation before public
   hosting; private memories are never shared as global knowledge by default.
6. Only later, build an optional model-improvement pipeline with distinct training
   consent, reviewed/redacted licensed examples, held-out evaluations, versioned
   checkpoints, human release approval and rollback. Never train the live model
   continuously on arbitrary chats. No paid GPU or cloud budget is authorized.
