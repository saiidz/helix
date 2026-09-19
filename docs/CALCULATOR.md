# Exact local arithmetic

## Scope

Normal chat, streaming chat and route preview now recognize self-contained
arithmetic before model or web resolution. Examples: `1+1`, `0.1+0.2`,
`Calculate: (2+3)/4`, and the reported long expression. The same calculator
serves all three existing roles; it is not a fourth model. Natural-language
word problems, code and contextual follow-ups keep the existing model path.

Supported syntax: decimal/integer literals, unary signs, parentheses, `+`, `-`,
`*`, `/`, and their multiplication/division/minus Unicode variants. Normal
precedence applies; multiplication and division associate left to right. No
implicit multiplication, powers, functions, percentages, variables, scientific
notation or comma-grouped literals are supported by this first calculator.
Recognized expressions with invalid operators return a calculation error, not
a model guess. Inputs containing letters (including scientific notation) or
commas are outside this fast path and retain the ordinary model path.

The calculator parses a small arithmetic grammar with iterative stacks. It does
not use eval, exec, Python's AST compiler, a shell, subprocesses or networking.
Fractions are exact, including decimal input. Fraction output is exact; a
nonterminating decimal approximation is explicitly marked rounded to 24 places.
Bounds: 512 expression characters, 128 tokens, 24 nested parentheses, 100 digits
per literal and 2048 bits per numerator/denominator intermediate.

## Chat and permissions

Existing auth dependencies, host/origin/body restrictions, idempotency ledger,
request concurrency gate and conversation/project checks remain in place. The
calculator receives no model/provider or web capability. Even with Web On, a
self-contained arithmetic expression is computed locally without a web query.
Other questions retain their existing Web Auto/On/Off behavior.

Successful API results identify `exact-arithmetic-v1`, report zero model cost,
`provider_called: false`, and `answer_verified: true` scoped only to the supplied
arithmetic. This is deterministic calculation, not verification of broader facts.
Invalid expressions have `answer_verified: false`; no model fallback guesses.
General model answers keep their original unverified state.

The current app.js footer hardcodes `unverified`; this backend-focused change
does not replace that conservative footer. The body explicitly identifies the
calculator and exact/rounded result, and metadata identifies the tool. Updating
the UI's footer to consume verification scope remains follow-up UI work. Do not
relabel every model answer as verified.

Calculations and normal conversation-history writes complete before the bounded
NDJSON response is returned. Closing the stream does not undo saved history,
but cannot leave a calculator job or held semaphore running. Existing history
writes are not converted into a cross-store transaction by this change.
No execution-agent, paid-provider, deployment or emergency-lockdown permissions
are changed. This is not an operating-system sandbox or kill switch.

## Regression example

Input:
`9879878978979879879879-8546545645646546546*545646465464654/4564631641654*465464654/48949648`

Exact:
`4610910773116753869545459649956672820779/27929639013578179724`

Rounded to 24 decimal places:
`165090238755865370728.216339891147987977342708`

## Validation and release gate

Focused checks:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_calculator.py tests/test_calculator_chat.py
```

The recorded 112 passes are Linux component tests: arithmetic, real SQLite
ledger, response service, NDJSON frames and fixture history/project stores.
They are not a full application, native Windows or live-browser test. The
server source was retrieved and its original Git blob hash verified before a
14-line additive integration. Python compilation and structural inspection
confirmed the calculator runs inside the existing authenticated handlers.

Before merge or deployment, run the unchanged full repository/Windows gate.
The previously reported generic engineering-loop failure has not been diagnosed
or bypassed by this calculator change. In the real UI, test `1+1`, `0.1+0.2`,
the long expression, `8/4*2`, `1/0`, both themes, Web On/Off, restored history and
an ordinary non-arithmetic question. The latter must still use its normal model.
After a successful full gate, restart the normal HELIX app, not the execution
agent. No model upgrade or internet connection is needed for arithmetic.
