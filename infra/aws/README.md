# AWS deployment design — not provisioned

No infrastructure code has been applied, no account selected and no spending authorized.

## Founder after hardening
One modest CPU host for HTTPS gateway/application, bounded provider calls and a small data store. AWS Lightsail's $24/month 4-GB Linux bundle is the initial budgeting reference; it is not a GPU. Founder-only state can remain on that host with encrypted tested backups. Do not promise multi-AZ durability or production uptime for this layout.

## Private paid beta
Separate stateless gateway/API, authenticated tenant data, object storage and durable jobs. Prefer PostgreSQL for transactional state; S3 for artifacts/backups; SQS for interruptible work. Choose managed database capacity after a concrete quote and restore test. Put OAuth secrets in a secrets service, not in prompts or GPU images.

## First optional GPU
An EC2 launch template and Auto Scaling Group with minimum/desired zero, maximum one initially. GPU worker claims durable jobs, loads a pinned model, emits readiness, checkpoints useful state and terminates after a measured idle window. The scaler must respond to backlog/oldest job age even when no workers exist. Scale down only after draining leases. Add service-level/global spend caps, not only AWS Budget alerts.

G6/L4 (24GB) and G6e/L40S (48GB) are candidates. Obtain an exact regional quote, GPU quota and capacity test. An available instance is not necessarily economical, and an inexpensive instance is not necessarily available. Spot is for retry-safe jobs; warm/API paths serve latency-sensitive voice with explicit external consent. Do not put secrets or customer state in GPU disk images.

## Scale out before making the model bigger
Use independent replicas where a model fits on one GPU. Keep state outside replicas. Split Companion's warm latency pool from queued Engineer/Sage jobs. Add larger models/tensor parallelism only after benchmarking. Kubernetes/EKS, Dynamo and multi-region are later decisions, not prerequisites.

## Approval checklist before the first apply
Named AWS account and region; spending owner; monthly and per-job caps; no automatic paid fallback; provider/model licenses; secrets/network policy; restore test; billing reconciliation; scale-zero recovery; real model load test; latency target; unit-economics comparison. Terraform/CloudFormation and actual apply remain unimplemented.
