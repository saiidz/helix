# Knowledge freshness — 2026-09-18

## What this update actually changes

HELIX uses local model inference plus web retrieval and a local SQLite research cache. This is not model-weight training and does not establish a new model knowledge cutoff. No claim that all world knowledge is current to this document's date is justified.

The research cache now:

- Excludes cached answer context for explicit freshness requests and common volatile subjects (for example latest/current/today, news, weather, prices, availability, and current officeholders). This is a conservative English-language heuristic, not a complete detector for changing facts.
- Excludes page entries after seven days and snippets after one day. Legacy `web` entries use the shorter window because the old schema did not distinguish pages from snippets. These are retention defaults, not guarantees of factual accuracy.
- Rejects missing, malformed, timezone-ambiguous, and future retrieval timestamps.
- Preserves source URLs and reports `source_type`, `cache_status`, `age_seconds`, and `expires_at` through the existing knowledge listing. UI presentation of these new fields is not yet implemented.
- Keeps expired history available for inspection and clearing, but not as automatic answer context.
- Does not renew `updated_at` when an entry is read or identical research is learned again. A snippet cannot overwrite or refresh a previously stored full page.

`eligible` means eligible as previously retrieved evidence, **not verified current**. A page fetched today may itself contain old information. Publication dates and event dates must still be evaluated against the question.

## Internet and cost boundaries

The existing Web Auto / On / Off setting is unchanged. This patch does not enable network access against Web Off, add paid APIs, crawl in the background, retrain a model, or modify the user's local databases remotely. Freshness detection excludes unsafe-to-reuse cached context; it does not itself start a search. Select Web On for explicit current-source research when the existing Auto classifier does not recognize a request.

The existing web adapter retains a five-minute response cache and does not expose original fetch timestamps. Consequently this patch conservatively refuses to renew identical persisted content, even if an actual re-fetch returned unchanged text. Live research can still use that text for the active request. A timestamped adapter with explicit revalidation is a future improvement; do not relabel the whole saved cache as newly verified.

## Verification recorded in this change

Executed in an isolated Linux Python environment:

```text
python -m pytest -q tests/test_knowledge_freshness.py
28 passed
python -m compileall -q helix/freshness.py helix/knowledge.py tests/test_knowledge_freshness.py
```

The tests use offline result/document fixtures matching the existing web adapter's attributes. They validate cache logic and SQLite behavior; they are **not** evidence of live web availability, full-repository compatibility, Windows execution, local model inference, or deployment.

## Deployment gate

At inspection on 2026-09-18, PR #1 was open with merge conflicts; the GitHub Actions runs endpoint returned zero runs. Branding from PR #2 is already on `main` and must be preserved during conflict resolution. No remote terminal connection to the founder's Windows machine was available in this session. This change must not be described as deployed or globally current knowledge.

After stopping only the existing HELIX app in its own terminal (leave the llama.cpp model server running), the owner can validate the updated development branch with:

```powershell
cd "C:\Users\Administrator\OneDrive\Desktop\helix"
git fetch origin
if ($LASTEXITCODE -ne 0) { throw "Fetch failed" }
git switch feat/codex-inspired-ui-v02
if ($LASTEXITCODE -ne 0) { throw "Branch switch failed; preserve local changes" }
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "Pull failed; do not force reset" }
.\DEV_LOOP_WINDOWS.cmd
```

The existing loop runs the full test suite, compilation and intelligence evaluation before launching HELIX. It does not merge automatically or stop an existing app instance. Required manual checks remain streaming/Stop, Web modes and source links, persistence, attachments, projects/tasks, approved branding, and both themes. A successful local start is separate evidence from a successful GitHub push.
