# Test-phase evidence instead of console formatting

The Windows parameter-ID regression used `--tb=no` in a child pytest process,
then required `AssertionError` in its console output. The child's deliberate
assertion did fail, but local console summaries may omit the exception message.
CI-style output includes more detail. The original test therefore passed with
`CI=true` and failed with `CI`/`BUILD_NUMBER` absent and `COLUMNS=80` on the same
Linux interpreter, reproducing the founder's error without changing Windows.

The child now records setup, call and teardown outcomes and exception types
using pytest's public `pytest_runtest_makereport` hook. It does not replace
reports, catch failures or alter the child exit code. The regression requires
successful setup/teardown and an actual call-phase `AssertionError`, independently
of console text. Tests cover `--tb=no`, `short` and `line` with local and CI-style
output. A setup-error fixture proves an infrastructure error cannot satisfy the
assertion-failure check. Only phase/type metadata is written to the temporary
report, not long fixture values, source code, node IDs or environment contents.

The parameter-ID hook and full 350,001-unit payloads are unchanged. This changes
no application code, dependencies, runtime permissions or release gate.

Validation is recorded in `evidence/parameter-report-validation.json`: 16 focused
tests passed in each of two Linux runs. Native Windows and the full repository
remain separate gates; do not infer them from these component results.

After updating the existing feature branch, rerun from the HELIX directory:

```powershell
.\.venv\Scripts\python.exe -m pytest -x -q --tb=short
```

Do not skip the regression or weaken application tests to continue. A dependency
deprecation warning is not the assertion failure reported here.
