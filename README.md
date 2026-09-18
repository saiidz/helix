# Helix · foundation 0.1.0

**Companion · Engineer · Sage** — one interface, at most three primary model roles, explicit privacy and spending limits.

This is a **working local routing/control prototype**, not a newly trained model or a production service. Default responses are deterministic demonstrations and are labeled `demo`. No paid provider is enabled, no weights are included, and no tools execute real-world actions.

Start with [HELIX_ROADMAP.md](HELIX_ROADMAP.md). The [economics model](docs/ECONOMICS.md) separates margins from investment return. See [STATUS.md](STATUS.md) for exactly what was tested.

## Windows quick start

Read [docs/WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md). On Windows with Python 3.13 installed, run `SETUP_WINDOWS.cmd`, then `START_HELIX.cmd`. `CHECK_PC.cmd` prints a read-only hardware summary for choosing the first real local model. The launchers do not require PowerShell execution-policy changes and do not push to GitHub. The default is still demo mode, not a trained model.

## Run the zero-provider-cost demonstration

From this directory, using Python 3.13 (the tested version):

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m helix
```

Open `http://127.0.0.1:8765`. Paste the random local access key printed in your terminal and select **Check connection & costs**. Ask a conversational question, a coding question, or a research question to see role routing. The key is kept in the page's memory, not local storage. Page refresh clears the displayed conversation. Downloading dependencies needs internet; the demo makes no model calls.

The server binds only to loopback. **Do not publish this server or expose it through a tunnel as a customer service.** It has one owner/key and is not a multi-tenant authentication system.

## Connect a model you already run locally

The generic adapter supports an **OpenAI-compatible text Chat Completions endpoint** on a literal loopback address. It is not a universal adapter for native Responses, Anthropic Messages, Gemini Live or arbitrary APIs.

1. Run your chosen compatible local inference server separately, with its supported model already installed. This package does not download models or manage GPU memory.
2. Copy `config/local.example.json` to `config/local.json`.
3. Replace the three `REPLACE_WITH_...` IDs with the server's exact installed model IDs and correct endpoint ports. The same checkpoint may fill multiple roles during the first experiment; that does **not** make it three specialized models.
4. Set conservative context limits and replace illustrative local shadow-cost rates with your measured accounting assumptions.
5. Run:

```bash
python -m helix --config config/local.json
```

The sample endpoint is `http://127.0.0.1:11434/v1`; it is a configurable example, not proof that a server or model exists on your machine. No external fallback occurs automatically. Local operation still consumes hardware, electricity and time.

## Tests and calculations

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python tools/economics.py
```

Results and UI smoke-test evidence are under `evidence/`. Unit tests and a loopback fixture-provider test establish control behavior, **not model intelligence**. Dependency versions match the test environment; they are not a complete transitive lock or security attestation.

## Implemented

- Three validated role profiles; deterministic routing and explicit role selection.
- Local browser UI and a generic text-inference adapter.
- Per-task estimates, atomic monthly cost reservations and reported-usage reconciliation.
- Idempotency collision handling: a repeated request receives `409` and is not called again.
- Cloud disabled by default; operator and per-request consent, allowlisted hosts, contract verification and nonexpired price metadata required before cloud use.
- Local endpoint restrictions, authentication, same-origin checks, bounded payload/context, concurrency limit, response-size cap and no automatic provider retries.
- SQLite ledger stores cost/status metadata, not raw prompts or answers.
- Tool-policy **preview** only; no email/calendar/terminal/deployment executor.
- Reproducible scenario economics including follow-on capital and compensation.

## Important operating limits

The byte-based token estimate is deliberately conservative but **not a provider billing guarantee**. Actual reported usage can exceed a reservation and is recorded, not hidden. Uncertain failures retain a reservation until reviewed; the prototype does not refund/retry them automatically. The ledger measures configured model/shadow costs, not the complete AWS bill.

Conversation is sent to the operator-configured local model in local mode. That server has its own logs and security behavior. The app cannot guarantee that a separately configured model server never contacts an external service. Cloud configuration requires operator review; the UI itself always requests `allow_external=false`.

There is no real-time voice, wake word, personal-data connector, persistent semantic memory, model training, autonomous coding sandbox, payment collection, AWS deployment, automatic GPU scaling or performance comparison yet. Those are gated roadmap work, not hidden completed features.
