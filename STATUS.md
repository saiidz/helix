# Helix implementation status

Checkpoint: **September 17, 2026** · package **0.1.0**.

## Completed in this task

- [x] Read the two existing Helix research reports and correct the technical-markup/investment-return confusion.
- [x] Check the connected GitHub installation for an existing `helix` repository; none returned. No unrelated repository was modified.
- [x] Create the main Markdown roadmap, source register, original project instructions and AWS/evaluation/security/runbook documents.
- [x] Implement a local single-owner FastAPI gateway, three role profiles, browser assets and a compatible text adapter.
- [x] Implement atomic spending reservations, idempotency rejection, uncertain-failure handling and provider usage reconciliation.
- [x] Keep default mode free of external inference calls and label simulated responses as demo.
- [x] Implement and run the reproducible 36-month economics model, including follow-on capital.
- [x] Run **55 automated tests: passed in 0.91 seconds**. See `evidence/tests-final.txt`.
- [x] Run `python -m compileall -q helix tools tests`: passed.
- [x] Test the HTTP adapter against a real loopback HTTP fixture server, not an AI model.
- [x] Render and inspect desktop/mobile static layouts; no horizontal overflow at 1440px and 390px. See `evidence/ui-preview.json` and PNGs.

## Explicitly not completed

- [ ] Live browser end-to-end integration: system Chromium blocked the loopback URL with `net::ERR_BLOCKED_BY_ADMINISTRATOR`. Browser policy was not changed. Static previews do not count as this test passing.
- [ ] Real model installation, GPU benchmark or generated-answer quality evaluation.
- [ ] Native vendor adapters for OpenAI Responses, Claude Messages, Gemini Live or full voice APIs.
- [ ] Web retrieval, email/calendar connectors, long-term semantic memory, voice/wake word, app actions or coding execution.
- [ ] Multi-tenant SaaS security, billing integration, cloud provisioning or GPU autoscaling.
- [ ] Training/fine-tuning, broad GitHub data ingestion, comparative model benchmarks or claims of superiority.
- [ ] GitHub push/PR, production deployment, model-provider payment or infrastructure purchase.

## Evidence interpretation

Tested Python: **3.13.5**. Main dependency versions are pinned in requirements files to the test environment, not claimed to be the newest or independently security-audited. Browser preview utilities require optional Playwright plus Chromium; they are not runtime dependencies.

The first test run passed 46 checks. Eight economics checks and one database-connection lifecycle check brought the final suite to 55. The final count is the release evidence. A fixture provider response is not a learned-model answer. A source citation or roadmap checkbox is not proof of an implemented feature.

Cloud-related price references are dated inputs, not live account quotations. No model/contract is activated by the comparator registry. Commercial projections are scenario arithmetic, not observed revenue or promised returns.

## Next gate

**HX-001 — connect and measure one genuine local model** using the exact machine, compatible serving endpoint, checkpoint and license. Preserve all local-only and no-spend defaults. Then add streaming/cancellation and first read-only useful workflows, with tests, rather than adding a large unmeasured model fleet.


## Windows preparation addendum

The user selected a Windows PC for initial development and supplied `saiidz/helix`. The connector confirmed that repository was public and empty at inspection. A private repository is recommended before uploading the commercial project; visibility was not changed.

Added three Windows launchers, a Windows/GitHub onboarding guide and expanded ignore rules for credentials, runtime state and model weights. The original roadmap and application remain in place. See `evidence/windows-preparation.txt` for the new Python-suite run. Windows launchers remain unexecuted on Windows here. No remote commit or push was performed.
