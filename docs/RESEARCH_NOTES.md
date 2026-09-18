# What to learn from experienced agent projects

The initial review sampled **four public agent repositories** and two official instruction/memory guides [S15–S20](SOURCES.md). It did not search every GitHub repository or establish a globally best prompt. A popular repository can still contain instructions specific to its own architecture.

## Original Helix patterns

| Evidence source | Reusable design lesson | Helix implementation |
|---|---|---|
| Codex project instructions | Put concrete validation and protected security behavior close to the code. | Root `AGENTS.md` has executable tests and a prohibition on weakening security tests. |
| OpenHands project guidance | Repository-local workflow knowledge belongs with the project. | Keep task-specific runbooks and architecture decisions scoped instead of injecting the whole archive. |
| mini-swe-agent | A small agent system is a useful reference when complexity has a cost. | Start with deterministic routing and a small adapter, then justify added loops with measurements. |
| Goose project guidance | Multi-component projects need navigation to relevant instructions. | Thin `CLAUDE.md` pointer and topic docs prevent competing copies of rules. |
| Official Codex/Claude guides | Instructions and memory need explicit scope and discovery rules. | Treat remembered evidence, retrieved documents and authorized policy as different trust classes. |

These are original design conclusions, not copied prompt text or claims that instruction files confer the authors' model capabilities.

## Bounded public-code/experience pipeline

1. Search selected agent and engineering repositories for `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, ADRs, incident reviews, runbooks and test-related lessons.
2. Record repository, exact commit, path, author/license metadata, retrieval date and source hash. Do not treat a default-branch URL as a frozen dataset.
3. Reject secrets, personal information, unclear provenance and material without a reviewed intended-use license. License review is necessary but not a blanket legal conclusion.
4. Extract a causal lesson and its supporting test, issue, code or incident. Stars alone are not an evidence score.
5. Write an original exercise and independent checker. Reproduce the lesson in a sandbox.
6. Only eligible examples enter a versioned training/development set; keep final evaluation tasks isolated.

## Reusable lesson template

```markdown
# Lesson: <specific failure or principle>
Status: hypothesis | reproduced | independently verified
Source: <repository, commit, path, license review>
Context: <versions, environment, relevant constraints>
Observed failure: <reproduction and evidence>
Cause: <supported explanation, not speculation>
Remedy: <minimal change and trade-offs>
Verification: <test, expected result, actual result>
Counterexample: <when this lesson does not apply>
Training eligibility: denied | pending | approved for specified use
Holdout exclusion: <checks that prevent evaluation contamination>
```

No automated global crawler or teacher-data collection was executed. Closed-provider outputs are not training-eligible by default; check the applicable contract before any distillation [S21](SOURCES.md).
