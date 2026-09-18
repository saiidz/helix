# HELIX — build roadmap and operating plan

**Version:** 0.1 · **Date:** September 17, 2026 · **Status:** local foundation implemented; no hosted launch or trained Helix model.

> One useful assistant. Three dedicated roles. Start with minimal fixed costs, prove outcomes, and expand only when measured demand pays for it.

## 1. Decisions and scope

Helix should let a person speak naturally, retain the context they authorize, retrieve current information, and complete useful work. Its long-term competitive ambition includes Claude, GPT-6 Astra, Grok, Gemini and leading Chinese/open-weight systems. **That is a research/product target, not a capability established by this package.**

The production limit is **three primary reasoning roles**, not a permanent fleet of every external model:

| Role | Dedicated purpose | First useful workflow | Avoid wasting this role on |
|---|---|---|---|
| **Companion** | Conversation, personal assistance, intent, memory and approved app actions | Find the relevant appointment/email, prepare a daily brief, draft the needed response | Heavy repository search or mathematical proof |
| **Engineer** | Code, repositories, debugging, tests, software operations | Reproduce a failure, propose a patch, run independent tests and show the diff | General small talk |
| **Sage** | Deep reasoning, research, mathematics and critique | Compare evidence, challenge an architecture, verify difficult conclusions | Timers, routine summaries and deterministic actions |

Users interact with **one Helix**; the UI shows which role/provider actually handled a request. Providers are replaceable resources, not permission to send private data anywhere. Local-only mode must never silently become cloud mode. More advanced voice/embedding components would be separately disclosed and budgeted; the supplied prototype loads **no** additional model weights.

Three specialized checkpoints are a destination, not a prerequisite for starting. The first experiment can use one compatible local checkpoint under three explicit role profiles. Separate prompts are **not** equivalent to trained specialization. A distinct checkpoint or adapter must earn its place through held-out task gains.

**Launch wedge:** a useful personal assistant paired with verifiable coding help. Broad computer control, automatic spending, full phone-assistant replacement, image/video generation and autonomous production deployment are later, separately gated work. Phone-platform permissions and distribution rules must be verified before promising an OS-level Siri replacement.

### Assumptions, not permissions

No existing Helix repository was found in the connected installation search. No local GPU, AWS account, cloud budget or model-provider credential was confirmed. Accordingly this implementation is a downloadable local project. It does not change SolveLang, UpcomingSounds, existing runners, Stripe, cloud infrastructure or production.

USD and a US-first deployment are planning choices. `us-east-1` is a candidate region, not a selected account or purchased capacity. A proposed $150–$250/month founder infrastructure envelope is **not authorization to spend**. This task made no paid inference calls or infrastructure purchases.

## 2. What has actually been built

The initial repository now contains executable code, original instructions, regression tests, a browser interface and a reproducible economic model.

| Component | Current evidence | Still required |
|---|---|---|
| Three-role router | Deterministic rules, explicit selection and follow-up tests | Calibration against real tasks; routing quality benchmark |
| Browser conversation | Working local text UI, role and provider labels, cost display | Streaming, accessibility review, real model usability tests |
| Inference adapter | Generic local-compatible text adapter tested against a loopback fixture | An actual installed model; native vendor adapters and streaming |
| Privacy boundary | Local endpoints constrained; cloud disabled and gated | Tenant isolation, managed secrets, hosted privacy program |
| Cost controls | Atomic reservations, per-task/month limits, usage reconciliation | Complete tool/audio/hosting costs and provider-bill reconciliation |
| Duplicate/failure handling | Duplicate IDs blocked; ambiguous failures retain cost | External action idempotency and outcome reconciliation |
| Tool policy | Preview identifies permission needs | No action executor is implemented |
| Economics | Monthly cohorts, fees, compensation, follow-on capital, sensitivity | Real demand, measured costs and accountant-reviewed forecasts |

**Default mode is an explicitly labeled simulation of routing, not an AI answer.** The app does not include a model, access the internet for answers, remember prior sessions, read mail, run code, train itself or operate a device. Tests prove specified software behavior, not intelligence or production security. See [STATUS.md](STATUS.md) for the final command results.

## 3. Architecture that starts small and stays portable

```text
Text / future voice interface
          |
Identity + consent + allowed context
          |
Deterministic task router + budget reservation
          |
   Companion / Engineer / Sage
          |
Local compatible inference OR explicitly allowed provider
          |
Proposed tools -> policy -> user authorization -> execution receipt
          |
Independent checks + honest response + cost reconciliation
```

Keep four concerns separate: model inference, conversation/memory, durable jobs/actions, and billing/policy. A model worker should be disposable; it must not own the only copy of a customer's data or a job's state.

### Inference and model switching

Start with a deterministic router for clear tasks. Do not pay a fourth LLM merely to choose between three roles. Escalate only when a task fails a quality check or a measured specialist advantage warrants the extra cost. Every attempt consumes the same operation's remaining budget; retries and review passes are not free.

Retain one conversation identity above the provider layer. Pass the minimum authorized context to specialists and preserve provenance. Do not make Companion rewrite every correct specialist answer: that adds latency, cost and a chance to distort it. Render verified structured results directly when appropriate.

Model loading is independent of role routing. Do not thrash three large checkpoints in and out of one small GPU for each conversational turn. Keep one warm model initially, schedule bounded specialist work, or use an approved API path when its full cost is lower. Measure model load time, memory, prefill, decode and concurrency rather than inferring feasibility from active parameters alone.

### Memory and retrieval

Start with explicit, inspectable user-approved facts and project notes. Store original sources, timestamps and deletion state. Distinguish user instructions from retrieved evidence; old messages or internet Markdown cannot grant new tool permissions. Use small relevant retrieval results instead of resending full history. Add vector search only when it improves a measured retrieval task; lexical search and structured facts are a valid first step.

For hosting, PostgreSQL can hold accounts, operation state and memory metadata; encrypted object storage can hold artifacts. Tenant scope must be enforced before retrieval and cache access. Memory consent is separate from training consent. Training contribution defaults off.

### Execution and truthful assistance

A tool action must move through a real state machine with a receipt. “I drafted your reply” is different from “I sent it.” A model-generated sentence is not evidence of either action. Reads also need relevant connector scope. Writes need payload-bound authorization, not a blanket “act for me” interpretation.

Engineering runs in disposable constrained workspaces. Reproduce first, modify on a branch/worktree, execute independent checks, inspect the diff, then present the result. Production credentials and host infrastructure are absent by default. Cross-model agreement is not proof; tests themselves can also be incomplete. See [SECURITY.md](docs/SECURITY.md).

## 4. Infrastructure: do not buy idle GPUs first

### Founder budget envelope

The immediate prototype runs on an existing computer. That requires no Helix cloud bill, although hardware, electricity and developer time still cost money. The first hosted founder pilot, **after security hardening**, should target the following allocation:

| Item | Monthly allocation | Status |
|---|---:|---|
| Small CPU gateway | $24 | AWS Lightsail 4-GB Linux pricing reference [S01] |
| Backup/object storage | $10 | Planning allowance; retention-dependent |
| Logs, secrets and domain reserve | $15 | Planning allowance; not a bundle quote |
| Bounded text/tool API experiments | $75 | Maximum proposed budget, not included unlimited usage |
| Bounded voice/evaluation experiments | $25 | Maximum proposed budget |
| Contingency | $30 | Buffer; not permission for automatic top-ups |
| **Pilot envelope** | **$179/month** | **Excludes salary, hardware purchases and tax** |

A $150–$250 envelope is a small invited experiment, **not capacity for an unspecified number of heavy subscribers**. If measured use exceeds it, reduce trial scope or require explicit additional budget. Do not add a permanently running GPU just to claim self-hosting.

### Candidate compute comparison

| Path | Reference | Recommended use | Main limitation |
|---|---|---|---|
| AWS CPU + bounded APIs | $24 CPU-host reference plus usage | Cheapest architectural starting point without buying a GPU | Provider dependence; privacy/contract checks |
| AWS EC2 G6 | L4, 24 GB/GPU [S03] | Benchmark a first optional quantized worker | Obtain current region/instance quote; no price assumed verified |
| AWS EC2 G6e | L40S, 48 GB/GPU [S04] | Upgrade when measured memory/context/concurrency requires it | More memory can increase idle cost |
| Runpod Serverless | Displayed 24-GB L4-class group: $0.69/hour [S26] | Controlled, non-sensitive burst comparison | A class can contain different GPU types; loading/storage/worker billing matter |
| Modal | L4 $0.000222/GPU-second, approximately $0.7992/GPU-hour [S08] | Burst experiments and a portability comparison | CPU/RAM/storage extra; GPU-only rate is not full-server price |
| Lambda | Configuration-specific GPU rentals [S27] | Scheduled larger experiments when justified | Check GPU count and commitment; per-GPU is not total instance price |

For illustration, Modal's listed L4 plus one physical CPU core and 16 GiB of RAM totals approximately **$0.9742/hour while those resources are billed**, before storage and other charges. Compare a complete workload bill, not a GPU-only number against an EC2 whole-instance number. Promotional credits do not establish sustainable economics.

Exact AWS G6/G6e rates were not freshly verified. The economics sensitivity uses **$0.81/hour as an explicitly unverified arithmetic input**, not an AWS quote. At that input, 50 paid hours are $40.50 versus $591.30 for 730 hours, before storage/network. Re-price before provisioning. Availability, account quotas, cold starts and usable throughput need measurement.

### Demand-based expansion gates

| Stage | Design | Upgrade only when |
|---|---|---|
| **Local proof** | Current single-owner app; no cloud GPU | Real model compatibility and useful workflow evidence exist |
| **Invited pilot** | Hardened small CPU service, scoped data store, budgeted providers | Users repeatedly complete useful tasks and cost traces are complete |
| **First optional GPU** | One EC2 or serverless worker; durable queue; minimum zero for queued jobs | Measured all-in cost/success is at least 25% below the API path at the expected load, with adequate quality/latency |
| **First warm pool** | Independent replicas for popular roles; consented fallback | Sustained demand and latency losses justify idle capacity; break-even analysis includes idle time |
| **Growth** | Stateless API replicas, PostgreSQL, S3, SQS, isolated sandbox workers, role pools | Load tests and queues show the specific bottleneck; paid demand funds headroom |
| **Large service** | Committed baseline, elastic burst; additional regions if required | Reliability, latency or customer data requirements justify the duplicated infrastructure |

Prefer replicas before multi-GPU model parallelism when the model fits one GPU. Introduce EKS/Kubernetes or distributed-inference frameworks only after their operational benefit exceeds their complexity. AWS Fargate is not the GPU execution path [S07]. The proposed first AWS GPU design is an EC2 Auto Scaling Group with durable queued jobs; it has **not** been provisioned.

Spot is appropriate for restartable evaluations, indexing and bounded jobs. Its advertised “up to 90%” discount is not a guarantee [S05]; interruption handling must not depend on always receiving a warning [S06]. Warm conversational voice cannot honestly promise an instant response from a cold, unloaded GPU. Use a warm permitted path or disclose the wait, rather than hiding external routing.

Savings commitments are later decisions based on measured baseline demand. Add queue-age alerts, readiness probes, job leases, request deadlines, limited maximum workers and global cost reservations. Budget alerts alone are not a hard spending stop.

## 5. Pricing, margin and the 400% objective

Use three **candidate**, not announced, consumer prices: **Personal $9, Plus $19, Pro $39**. Start with one paid tier during the beta rather than building a large billing catalog. Included access must map to understandable workload allowances. Expensive voice, coding jobs and research use visible budgets. No fake unlimited plan, silent model downgrades or automatic paid overages.

US domestic-card processing and Stripe Billing add 2.9% + $0.30 and 0.7% respectively [S12–S13]. Price optional services and abuse prevention before launching cheap tiers. A local user supplies inference, not free sync, storage, support or cloud fallback.

The reproducible scenario assumes a 60% / 30% / 10% tier mix. It produces **$15 billed ARPU**, **$14.70 after a 2% refund reserve**, **$4.205 variable service costs**, and **$10.495 contribution per paid user-month**. That is about **71.4% contribution margin before fixed service costs, acquisition, founder compensation and other overhead**—not a claim of 80% net profit.

The base steady-state break-even is around **348 paying customers** under the specific modeled cost, replacement-CAC and compensation assumptions. Growth acquisition costs and staffing thresholds can move break-even substantially. See [ECONOMICS.md](docs/ECONOMICS.md) and edit [config/economics.json](config/economics.json), not the generated numbers.

### Correct return definition

```text
Contribution margin = (net revenue − variable service costs) / net revenue
Operating profit = net revenue − service COGS − acquisition − payroll − overhead
Modeled capital return = cumulative profit after tax reserve / ALL capital contributed
```

A 400% markup on compute costs is **not** a 400% investment return. The latter hurdle requires $4 of cumulative profit for each $1 actually invested, including later cash injections. No speculative company valuation is included here. Returns are not annualized and are not actual shareholder distributions.

| Scenario | 12-month return | 24-month return | 36-month return | Total capital needed by month 36 |
|---|---:|---:|---:|---:|
| Conservative | −97.4% | −98.5% | −98.8% | $84,869 |
| Base | −96.5% | −19.5% | **180.9%** | $30,214 |
| Upside | −76.6% | 266.6% | **1,288.3%** | $16,774 |

These are **illustrative acquisition/churn scenarios, not probabilities or forecasts**. The upside case assumes 50, 150 and 300 new paying users every month in years 1, 2 and 3, with 3% monthly churn and $15 acquisition cost. Those assumptions are unproven; it is not evidence that 400% is likely. The base case does not achieve the goal within 36 months.

The model includes a $3,000/month founder-compensation allowance, service cost, paid acquisition, incremental staffing, follow-on cash injections and a hypothetical 20% reserve on positive cumulative profit. It does not pretend that allowance funds a full market-rate engineering team. Real taxes, staff costs and legal obligations need separate review. Infrastructure can start around $179/month while the **business** still needs much more capital to fund labor and customer acquisition.

**Management rule:** validate profitable work before scaling acquisition. Target at least 65% full service gross margin in the limited beta and 75%+ only after demonstrated optimization. The present assumptions do not prove the higher target. Test doubled model/tool costs and tripled voice consumption before declaring pricing safe.

## 6. Model selection and competitive evidence

Maintain a versioned registry, not an unsupported “best model” list. Requested baselines include:

- GPT-6 Astra and Codex; Claude and Claude Code.
- Grok text/voice; Gemini Pro/Flash/Live where available and eligible.
- Relevant Qwen, DeepSeek, GLM, Kimi, MiniMax, Mistral and other open-weight candidates.

[config/baselines.json](config/baselines.json) explicitly marks every comparison **not run**. Exact releases that were not independently resolved remain verification tasks, not invented API IDs. There is no claim of beating every Chinese model, every benchmark or every future release.

Initial local candidates to evaluate include Qwen3.5-9B for Companion, Qwen3-Coder-30B-A3B or a verified Devstral release for Engineer, and gpt-oss-20b for Sage [S22–S24]. Do not buy a machine based solely on nominal parameter count: total weights, quantization format, KV cache, context and backend support determine memory and responsiveness. Pin weights and licenses before downloading/training.

Use two separate scoreboards: **model under matched conditions**, and **complete assistant doing the job**. Track verified success, human intervention, regressions, latency and **all-in cost per successful task**. Identify every external provider used. A Helix response produced by Astra does not prove a Helix checkpoint outperformed Astra.

Public prices establish comparator cost inputs, not quality. For example, the official references currently list Astra at $10/$50 and Claude Sonnet 5 at $2/$10 per million input/output tokens [S09–S10]. Gemini 3.8 Flash lists a temporary $0.75/$3.75 price through December 31, 2026 and a scheduled increase afterward [S11]. Long context, cache, tool calls, reasoning tokens and voice can change the effective bill.

The proposed initial competitiveness target is **at least 95% of the strongest eligible baseline's success rate on selected workflows at no more than 70% of its all-in task cost**, with paired uncertainty intervals. It is a release target, not an achieved metric or universal intelligence claim. See [EVALUATIONS.md](docs/EVALUATIONS.md).

## 7. Learning without copying the internet or inheriting its mistakes

Use existing open weights plus evidence-backed retrieval and tools first. Do not pretrain three foundation models from scratch or bulk-download all public code for the launch. Access to source code is not an automatic right to train on it. More data, agents or critique passes do not guarantee better generalization.

The initial Markdown review sampled Codex, OpenHands, mini-swe-agent and Goose plus official instruction guides [S15–S20]. It informs original Helix `AGENTS.md`, a thin `CLAUDE.md` pointer, security/evaluation rules and a lesson template. It was **not** an exhaustive search of GitHub or a transfer of those systems' model intelligence.

Build a bounded evidence pipeline: select relevant repositories; pin commits; review licenses; scan for secrets/personal data; retain provenance; reproduce a causal lesson; write a fresh exercise and independent test. Reject unsupported “experience” text. Never allow downloaded instructions to override Helix policy or spend money.

Teacher runs require a permitted intended use. Hosted competitors are not assumed to allow competitive distillation; provider agreements may restrict it [S21]. Customer memory does not imply training permission. Retain separate consent and license records. Test sets remain excluded from all teachers, retrieval and tuning.

After real usage reveals a repeatable weakness, consider a small, capped adapter/fine-tune experiment. Budget the full loop: eligible examples, generation, filtering, teacher calls, training, evaluation and rollback. A $25/$100/$250 experiment cap is a decision limit—not an estimate that a useful training run will cost that amount. Begin only when throughput and data sizing support a quote. Reject any new checkpoint that improves coding by breaking conversation, calibration or permissions.

## 8. Ninety-day implementation sequence

These are **planning windows and acceptance gates**, not promised delivery dates. Hardware, access, staffing and measured results determine the actual pace. Funding is not assumed merely because a day number is listed.

| Window | Release objective | Concrete work | Exit gate |
|---|---|---|---|
| **Foundation — started now** | Reproducible local control layer | Router, browser UI, text adapter, ledger, guardrails, tests, original Markdown, economic scenarios | Tests and local UI smoke test pass; simulated and real modes are distinguishable |
| **Days 1–14** | First genuine local conversation | Connect one verified checkpoint; streaming/cancel; versioned model card; cost/latency harness; provider-native adapters only as needed | 30 held-out pilot conversations, measured latency/memory, honest tool limitations, no silent external fallback |
| **Days 15–30** | Useful but constrained work | Read-only calendar/mail connector with minimal scopes; daily brief/draft; repository read/test sandbox; patch review | 20 real tasks with source/action evidence; zero unauthorized writes; failed jobs are recoverable |
| **Days 31–60** | Memory, bounded actions and voice | Opt-in source-backed memory/deletion; payload-bound approval; interruption-capable voice prototype; durable job IDs; broader holdout | Tenant/privacy canaries pass; voice economics measured; duplicate actions prevented/reconciled |
| **Days 61–90** | Paid private-beta decision | One subscription tier, visible budget; verified billing events; account isolation; backups/restore; invite cohort; demand-based worker test if justified | Retention, willingness to pay, service margin, quality and security gates pass before expansion |

### First implementation backlog, in order

1. **HX-001: real-model validation.** Pin one local model, exact runtime and hardware. Run identical prompts through direct serving and Helix. Record first-token/full-response latency, RAM/VRAM, usage and limitations. No automatic weight download or cloud spend.
2. **HX-002: streaming and cancellation.** Add bounded streaming, explicit canceled/unknown states, usage reconciliation and tests for disconnects. Never treat cancellation as evidence that the provider incurred zero cost.
3. **HX-003: durable action protocol.** Add read-only connector contracts first; then exact-payload approval and receipts. Test repeated and delayed provider responses before enabling any real write.
4. **HX-004: safe engineering workspace.** Make a small sample repository task reproducible, run independent tests and return a patch/diff. No user production access needed.
5. **HX-005: held-out evaluation runner.** Populate rights-reviewed cases, matched-budget runs and reproducible scores. Keep external baselines and local Helix performance separate.
6. **HX-006: hosted-beta identity and billing.** Multi-tenant data, session security, invoice/webhook idempotency, cost ledger and tested restore precede any public endpoint.

## 9. Go/no-go scorecard

| Dimension | Proposed go condition | Stop or revise when |
|---|---|---|
| Usefulness | Invitees repeatedly complete the chosen daily/engineering jobs; gather at least 10 genuine payment commitments | People like the demo but do not use/pay for the workflows |
| Quality | Held-out success, source quality and error recovery meet the declared workflow floor | Cheaper routing saves tokens but causes more failed tasks |
| Safety/privacy | Zero critical unauthorized-write or cross-tenant failures in the release suite; independent review before hosted launch | Any critical leak, wrong-recipient write or unbounded executor remains |
| Economics | At least 65% full service gross margin in the defined beta cohort; p95 heavy-user cost constrained | Pricing depends on unlimited subsidies, hidden downgrade or expired promotions |
| Retention | Target at least 50% four-week activated-user retention in a named invite cohort; report sample size | No repeated value; do not buy growth to hide churn |
| Speed | Establish separate text/voice interactive SLOs from real hardware, measure p50/p95 and cold/warm cases | “Fast” depends on mock replies or an unloaded GPU |
| Expansion | Qualified demand and load tests support the next worker; cost/success beats the alternative | Scaling is based only on signups or enthusiasm |
| Evidence | Every published benchmark records versions, task set, attempts, cost and uncertainty | Only cherry-picked wins or teacher-contaminated tests are available |

## 10. Continue from the actual project

The package is ready for local inspection, execution and development:

```bash
python -m venv .venv
# Activate the environment for your operating system.
python -m pip install -r requirements-dev.txt
python -m pytest
python tools/economics.py
python -m helix
```

Open the printed loopback address and use its random local access key. Read [README.md](README.md) before switching from demo to an actual compatible endpoint. The existing code intentionally cannot send mail, deploy, purchase or create cloud workers.

**Current external gates:** confirm the actual development machine or compatible local endpoint; choose the correct repository destination; approve any future provider/cloud budget; obtain the required connector scopes; complete production security and billing before launch. None of those gates blocks the local code, tests or planning already supplied.

The next technical gate is **HX-001: a real model producing useful, measured conversations through this control layer**. The next business gate is someone repeatedly choosing and paying for a verified workflow. Neither is satisfied by a name, a prompt file or an optimistic GPU spreadsheet.

---

## Source index and companion documents

[SOURCES.md](docs/SOURCES.md) provides the full primary-source register S01–S27, research limitations and prior-report corrections. Key direct references for this standalone roadmap are [AWS Lightsail](https://aws.amazon.com/lightsail/pricing/), [EC2](https://aws.amazon.com/ec2/pricing/on-demand/), [Modal](https://modal.com/pricing), [Runpod](https://www.runpod.io/pricing), [OpenAI](https://openai.com/api/), [Anthropic](https://platform.claude.com/docs/en/about-claude/pricing), [Gemini](https://ai.google.dev/gemini-api/docs/pricing), [Stripe](https://stripe.com/pricing), [Billing](https://stripe.com/billing/pricing) and [OpenAI services terms](https://openai.com/policies/services-agreement/).

Read [ECONOMICS.md](docs/ECONOMICS.md), [EVALUATIONS.md](docs/EVALUATIONS.md), [SECURITY.md](docs/SECURITY.md), [RESEARCH_NOTES.md](docs/RESEARCH_NOTES.md), [RUNBOOK.md](docs/RUNBOOK.md) and [AWS design](infra/aws/README.md) for implementation detail. Everything marked planned remains planned until matching evidence is recorded in `STATUS.md`.
