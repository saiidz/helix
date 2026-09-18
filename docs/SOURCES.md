# Sources, verification and evidence limits

Research checkpoint: **September 17, 2026**. USD unless otherwise noted. These are selected primary sources, not an exhaustive crawl. Pricing pages are mutable; re-quote before enabling a paid provider. A model's marketing statement is not a Helix benchmark result.

| ID | Primary source | Used for / limitation |
|---|---|---|
| S01 | [AWS Lightsail pricing](https://aws.amazon.com/lightsail/pricing/) | US Linux public-IPv4 bundle reference: 4 GB / 2 vCPU / 80 GB at $24/month. Backup, excess transfer and other services can add charges. |
| S02 | [AWS EC2 On-Demand](https://aws.amazon.com/ec2/pricing/on-demand/) | Purchasing/billing mechanics. Exact region-specific G6/G6e rates were **not** revalidated; the $0.81 sensitivity input is only an assumption. |
| S03 | [AWS G6](https://aws.amazon.com/ec2/instance-types/g6/) | NVIDIA L4, 24 GB per GPU; family capability, not a Helix throughput measurement. |
| S04 | [AWS G6e](https://aws.amazon.com/ec2/instance-types/g6e/) | NVIDIA L40S, 48 GB per GPU; greater memory does not establish better cost/task. |
| S05 | [AWS Spot](https://aws.amazon.com/ec2/spot/) | Discounts are advertised as **up to** 90%, not a guaranteed planning discount or available capacity. |
| S06 | [AWS Spot interruption notices](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-instance-termination-notices.html) | Interruption handling; notices are best-effort. Durable work must survive losing a worker. |
| S07 | [AWS Fargate task differences](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-tasks-services.html) | Fargate does not supply GPU resources. Use EC2-backed workers for this GPU design. |
| S08 | [Modal pricing](https://modal.com/pricing) | L4 $0.000222/GPU-second; CPU, RAM and storage are separate. Ignore promotional credits in sustainable economics. |
| S09 | [OpenAI API](https://openai.com/api/) and [Astra model documentation](https://developers.openai.com/api/docs/models/gpt-6-astra) | Reference text prices: Astra $10 input / $50 output per million, GPT-5.6 Luna $0.20 / $1.20. Cache, long-context and tools require their own accounting. |
| S10 | [Anthropic model pricing](https://platform.claude.com/docs/en/about-claude/pricing) | Sonnet 5 $2/$10, Opus 5 $5/$25, Fable 5.1 $10/$50 per million input/output. These are comparator prices, not capabilities or implemented integrations. |
| S11 | [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) | Gemini 3.8 Flash promotional text input/output $0.75/$3.75 per million through December 31, 2026; listed January 1, 2027 rates $1.50/$7.50. Search/audio are separate. Recheck the schedule before contracting. |
| S12 | [Stripe payments pricing](https://stripe.com/pricing) | US domestic cards 2.9% + $0.30; international/FX, disputes, taxes and optional products can add cost. |
| S13 | [Stripe Billing pricing](https://stripe.com/billing/pricing) | Pay-as-you-go Billing 0.7% of applicable Billing volume, in addition to payment processing. |
| S14 | [vLLM automatic prefix caching](https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/) | Reuses shared-prefix work; it does not eliminate output generation cost. Benchmark isolation, compatibility and hit rates. |
| S15 | [Codex AGENTS.md](https://github.com/openai/codex/blob/main/AGENTS.md) | Representative project instructions: concrete validation and security constraints. No wholesale copying. |
| S16 | [OpenHands AGENTS.md](https://github.com/OpenHands/OpenHands/blob/main/AGENTS.md) | Representative repository-local contributor/agent workflow. Treat instructions as project-specific rather than universal authority. |
| S17 | [mini-swe-agent AGENTS.md](https://github.com/SWE-agent/mini-swe-agent/blob/main/AGENTS.md) | Representative small-agent project instructions; useful contrast to complex orchestration. |
| S18 | [Goose AGENTS.md](https://github.com/aaif-goose/goose/blob/main/AGENTS.md) | Representative multi-component project guidance. Inspect only applicable sections. |
| S19 | [Codex AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md/) | Instruction discovery/scope as an integration reference; do not assume all agent runtimes implement identical precedence. |
| S20 | [Claude Code memory](https://code.claude.com/docs/en/memory) | Distinguishes project instructions and memory features; Helix must implement its own scope and trust model. |
| S21 | [OpenAI services agreement](https://openai.com/policies/services-agreement/) | Contains restrictions on competitive model development using outputs, with specified exceptions. No general permission to distill hosted competitors is assumed. Review each provider and intended use separately. |
| S22 | [gpt-oss announcement](https://openai.com/index/introducing-gpt-oss/) | Candidate reasoning foundation; 20b is positioned for roughly 16 GB-class deployment. Actual KV memory, backend support and latency remain test items. |
| S23 | [Qwen3.5-9B model card](https://huggingface.co/Qwen/Qwen3.5-9B) | Companion candidate to evaluate, not selected production weights. |
| S24 | [Qwen3-Coder-30B-A3B model card](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct) | Engineer candidate; total stored weights still matter even with sparse activation. |
| S25 | [Grok 4.6 documentation](https://docs.x.ai/developers/models/grok-4.6) and [voice documentation](https://docs.x.ai/developers/models/speech-to-speech) | Grok text/voice comparator. Reference Grok 4.6 text pricing $2/$6 per million input/output; voice needs separate metering. |
| S26 | [Runpod current pricing](https://www.runpod.io/pricing) and [serverless product](https://www.runpod.io/product/serverless) | Displayed serverless 24 GB L4-class group $0.69/hour; a group is not a guarantee of a specific GPU. Recheck worker type, loading/idle billing, storage and region. |
| S27 | [Lambda pricing](https://lambda.ai/pricing) | Configuration and GPU-count-sensitive rental comparison. A per-GPU price in an eight-GPU configuration is not the total instance price. No single-GPU launch quote is assumed. |

## Prior research used as input, not ground truth

Two user Library reports were located and read during this task:

- **Helix: Low-Cost, Scalable AI Assistant Infrastructure and Business Plan**.
- **Helix: A Slow-Start, Low-Cost, Demand-Driven Universal AI Service**.

The first report labeled profit divided by technical COGS as strict ROI. This package corrects that: it is a markup/technical-return measure, not investor return. The reports' growth trajectories, staffing omissions and model-version statements were not accepted as measured facts. A report's future-dated planning table does not establish current pricing.

## What was not established

No exhaustive GitHub search; no claim these are the world's best instruction files. No paid comparative evaluations, GPU benchmark, verified hardware inventory, trained Helix checkpoint, user-retention observation, exact EC2 quote, security certification, legal approval or investment-return forecast. The connected repository search found no accessible repository matching `helix`; other installations or names may exist.

Record exact model revisions, repository commits, licenses, access dates and evaluated tool configurations before using any material for reproducible training or publishing benchmark results. The branch-based public links above are reading references, **not a frozen training corpus**.
