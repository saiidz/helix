# Next implementation task · HX-001

## Objective
Prove that a real, already available local model works through Helix and produces useful text responses within measured hardware and cost constraints. Do not confuse three role prompts with three trained specialties.

## Required inputs
Actual development machine/OS, RAM/VRAM, exact installed compatible model ID, loopback serving endpoint, and license terms. The user has now selected a Windows PC and created `saiidz/helix`; CPU, RAM, GPU/VRAM, storage and installed model details remain unknown. Do not guess that existing production servers or runners are available for this task.

## Authorized-scope template
Work only in this Helix project and a local test model endpoint. No cloud/API spending, model downloads, private training data, production credentials, paid subscriptions, repository publication or external fallback unless separately approved.

## Implementation
1. Inspect the specific model server's current API and supported context/usage fields.
2. Configure `config/local.json`; keep it uncommitted if it contains environment-specific details. Never insert provider secrets into JSON.
3. Run a small fixed prompt set directly and through the adapter. Log revision, backend, quantization, hardware, first-token/full-response timings, memory and actual token usage.
4. Add tests for any adapter incompatibility. Preserve failure/cost accounting and cloud denial.
5. Evaluate conversation, coding and reasoning cases separately; identify limitations without inventing scores.
6. Record evidence in `STATUS.md` and a model card. Do not claim coding tools or personal-data access before those executors exist.

## Completion
A reproducible run command, exact local profile, successful actual model responses, measured latency/memory, adapter tests, documented limitations and no unapproved external traffic. The full browser test must also pass on a machine whose browser policy permits the loopback app. Then proceed to HX-002 streaming and cancellation.
