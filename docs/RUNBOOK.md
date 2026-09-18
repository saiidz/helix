# Founder prototype runbook

## Startup and inspection
Run `python -m helix` from the project root. Use the displayed loopback URL and random key. `GET /health` should report `founder_prototype` and zero models loaded by this app. Authenticate in the UI to inspect configured profiles. Default models are demos, not downloaded weights.

## Budget rejection
A `402` means the task estimate or monthly ledger exceeds its configured cap. Inspect `/api/route` and `/api/meter` with the same authentication. Do not raise caps or enable a cloud provider automatically. The sample local profile prices are shadow-accounting assumptions.

## Duplicate request
A `409` means the operation ID was already seen, whether completed or uncertain. This prototype does not replay saved answers, because it does not store them. It does not execute a duplicate provider call. Investigate before issuing a new ID after an uncertain external response.

## Provider timeout or failure
A reservation remains in the ledger because the provider may have spent resources. Review the separate provider logs/usage before reconciling. There is no automatic refund or retry tool. Stop the process and copy the SQLite database before manual maintenance; never edit it blindly while requests are running.

## Secret exposure
Stop the process, revoke any affected provider credential, set a new local key or allow startup to generate one, and inspect what was exposed. Do not paste secrets into issues, prompts, screenshots or support logs. The demo uses no provider secret.

## Rollback
Keep versioned configuration and source. Stop the app, restore a known-good code/configuration version, preserve the cost ledger and rerun tests. No migration tool or production rollback automation is supplied.

## Not a cloud deployment recipe
Do not change the bind address, open router ports or put a public tunnel in front of this single-key app to onboard customers. The hosted-beta gate in `HELIX_ROADMAP.md` must be completed first.
