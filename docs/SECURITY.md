# Security and action authority

## Current boundary

The supplied app is a **single-owner loopback prototype**. It is not safe to expose directly as a public SaaS. Passing its regression tests does not constitute a penetration test. The random bearer key, same-origin checks and local endpoint allowlist reduce specific risks; they do not replace identity, tenant authorization, quotas or an operational security program.

## Required before private hosted beta

Use real account/session authentication, rotating scoped tokens, encrypted transport, a secrets manager, database migrations, tenant-scoped row access, audited connectors, independent request/compute budgets, rate limits, deletion/export controls and tested backups. Separate public gateway, user-data services, privileged connector workers and untrusted code sandboxes. Do not put customer data or production credentials on an opportunistic GPU host by default.

## Action state machine

`proposed → policy_checked → user_authorized → dispatched → independently_observed → completed`

- Each write has an immutable operation ID, normalized resource, exact action payload, scope and expiry.
- Approval applies to that payload, not to any later action the model decides to substitute.
- A timeout after dispatch becomes `outcome_unknown`, not `failed_safe_to_retry`.
- Query the provider or reconcile receipts before retrying. Exactly-once effects cannot be promised when the external service does not support them.
- The assistant may say “drafted” before a send; it may say “sent” only after observing a provider receipt/status. Similar distinctions apply to reminders, calendar changes, purchases and deployments.
- Read permission is itself scoped; reading every email is not implied by permission to check one appointment.

## Untrusted execution

Customer repositories and retrieved Markdown may contain malicious instructions or build scripts. Run code in disposable constrained environments without host mounts, the Docker socket, cloud instance credentials or broad egress. Apply time, memory, process, disk and network budgets. A container alone is not an adequate hostile-tenant boundary; evaluate a stronger VM/microVM sandbox before public code execution.

Never fetch URLs supplied by a model through an unrestricted privileged network client. Block metadata/private-network targets, validate each redirect, cap response sizes, and separate browser/retrieval access from internal service credentials. Prompt wording alone does not prevent SSRF or prompt injection.

## Privacy

Memory opt-in and training contribution are separate. Keep customer data out of training by default. Scope cache entries, embedding searches and model/tool context by tenant; test cross-tenant canaries. Redact credentials from logs. Make memories inspectable, attributable, editable and deletable; coordinate deletion with archives/backups. Distinguish local model execution from cloud sync or externally routed inference in the UI.

## Spending

Budget alerts are not instantaneous spending stops. Before cloud launch, add provider-level quotas, job deadlines, max worker count, per-tenant/global atomic reservations, billing reconciliation and a tested kill switch. Include reasoning tokens, retry attempts, audio, search, storage, egress and idle compute. No automatic top-ups or paid fallback without a disclosed policy and the user's consent.
