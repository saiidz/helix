# Windows pytest environment-variable failure

The Engineer file-boundary test includes `b"x" * (MAX_FILE + 1)` with
`MAX_FILE = 350000`. Pytest 9.0.2 expands long str/bytes parameters into test
IDs by default. It writes the node ID plus execution phase to
`PYTEST_CURRENT_TEST`, exceeding Windows' environment-variable size limit.
Setup and teardown can both report this error for a single case.

`tests/conftest.py` uses pytest's public `pytest_make_parametrize_id` hook to
summarize auto-generated labels for strings/bytes longer than 128 units.
Labels retain the argument name, value type, length, and a short SHA-256 digest.
Original payloads, assertions, marks, and test selection are unchanged.
Explicit IDs and normal short labels are preserved. No production code,
Windows settings, environment limits, execution permissions, or dependencies
are changed by this fix.

Regression checks run an isolated child pytest process with a simulated
Windows environment-write limit. Without the hook, a 350,044-character node ID
causes the same ValueError. With the hook, all six fixture cases pass; IDs are
at most 78 characters and both observed payloads remain 350,001 units long.
Another child test deliberately fails to prove real assertion failures remain
visible. These are focused Linux checks, not native Windows/full-app evidence.

After updating the development branch, rerun the complete gate on Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest -x -q --tb=short
```

Do not skip failed tests, change the test payload size, clear PATH, alter Windows
limits, or merge on the basis of this focused check. Other integration failures
may become visible once this test-setup error is removed.
