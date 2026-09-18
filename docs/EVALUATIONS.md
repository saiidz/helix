# Evaluation and promotion protocol

## Two independent comparison tracks

**Track A — foundation model:** same permitted inputs, tools, task budget, context and timeout. Freeze model revision and decoding settings. Compare model capability rather than orchestration advantages.

**Track B — full product:** compare Helix with the appropriate Claude/Claude Code, Astra/Codex, Grok/voice, Gemini/Live and selected open-system experiences. Log tool permissions, user intervention, provider mix and total money/time. Do not call an external-model-assisted Helix result an improvement in Helix's own weights.

## Candidate registry

`config/baselines.json` records the requested families. All entries are **not run**, not rankings. Model names that could not be independently resolved remain discovery tasks rather than fabricated identifiers. At most three Helix primary roles run in production; the offline comparator registry does not require simultaneously hosting all candidates.

## Initial datasets (targets, not supplied completed evaluations)

| Suite | Minimum initial target | Verifier |
|---|---:|---|
| Companion actions and permissions | 100 tasks | Expected action graph, exact recipients/resources, no unauthorized side effect |
| Conversational follow-ups and ambiguity | 100 tasks | Blinded human scoring plus required-context checks |
| Memory | 50 tasks | Known source facts, deletion and cross-tenant canaries |
| Engineer | 100 repository tasks | Independent tests, patch review, regression checks, reproduction |
| Sage | 100 reasoning/research tasks | Executable check where possible; independent source-supported review otherwise |
| Voice | 30 scenarios plus continuous load tests | Turn latency, interruption handling, transcription errors, action correctness |

Begin with small development fixtures, then acquire genuinely unseen tasks with rights to use them. Never put the final holdout in teacher prompts, training data, retrieval indexes or public examples. Separate repositories and task families, not only randomly split nearly duplicate rows. Add temporal holdouts for current-documentation work.

## Metrics

`HCST = total inference + tools + retries + allocated service cost / number of verified successful tasks`.

Also measure quality at a fixed budget, time to first token, end-to-end completion latency, human interventions, unsupported action claims, wrong-recipient actions, privacy violations, cold starts, retries and failure recovery. Report cached/uncached and short/long-context cases separately. Voice cost uses minutes/audio units, not text-only rates.

Use paired task comparisons and uncertainty intervals (for example paired bootstrap intervals) before publishing a win. Report total task count, all failures, versions and conditions. Passing tests is necessary for coding, not proof of correctness, security or freedom from hidden regressions. Reviewers sharing a base model can share errors; model agreement is not independent truth.

## Promotion gates

Safety/privacy regressions block promotion. A model/routing change needs either higher verified success at the same budget, lower all-in HCST at comparable success, or an explicitly approved user-value improvement. For initial self-hosting, aim for at least 25% lower measured cost/success than the enabled API path while meeting latency and quality floors; this is a management threshold, not an achieved result.

A proposed frontier-competitive gate is at least 95% of the strongest baseline's success rate on selected workflows at no more than 70% of its all-in task cost, with paired uncertainty reported. Universal superiority requires broader evidence and is not the launch promise.

Current regression tests validate software controls only. No model-quality benchmark, frontier comparison or GPU throughput test has been run in this package.
