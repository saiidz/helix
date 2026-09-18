# Helix — reproducible economics

> Scenario calculations, not forecasts. All dollar amounts are USD. No money was spent running this model.

## Definitions that prevent misleading ROI claims

`Contribution = net revenue − variable service costs`.
`Service gross margin = (net revenue − all service COGS) / net revenue`.
`Operating profit = net revenue − service COGS − acquisition − compensation − other operating expenses`.
`Modeled return on contributed capital = cumulative profit after the hypothetical tax reserve / ALL capital contributed`.

A 400% markup on COGS is an 80% gross margin, not a 400% investment return. A 400% investment-return hurdle requires cumulative profit equal to four times actual contributed capital. This simulation assigns no sale valuation or terminal goodwill, and includes follow-on financing in its denominator. It is not annualized ROI or IRR; no actual distributions are assumed.

## Candidate subscription economics

Prices and usage are hypotheses. Stripe domestic-card fees of 2.9% + $0.30 and Billing at 0.7% are the sourced fee inputs [S12–S13](SOURCES.md). The scenario deducts a 2% revenue refund allowance while retaining processing charges. Other line items are management assumptions, not supplier quotations.

| Plan | Price | Model + tools | Voice | Storage + direct support | Payment + billing | Total variable COGS | Contribution after refunds | Contribution margin |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Personal | $9.00 | $1.20 | $0.45 | $0.35 | $0.62 | $2.62 | $6.20 | 70.2% |
| Plus | $19.00 | $2.50 | $1.00 | $0.65 | $0.98 | $5.13 | $13.49 | 72.4% |
| Pro | $39.00 | $6.00 | $2.00 | $1.20 | $1.70 | $10.90 | $27.32 | 71.5% |

At the assumed 60% / 30% / 10% plan mix: billed ARPU **$15.00**, net ARPU **$14.70**, variable COGS **$4.21**, contribution **$10.49** per paid user-month. The resulting **71.4% contribution margin** is before fixed hosting, acquisition, founder pay and other overhead. Do not advertise it as net profit.

Base steady-state break-even is approximately **348 paying users** with the included $3,000 founder-compensation allowance, $200 overhead, $100 fixed hosting, and replacement acquisition at 5% churn × $20 CAC. This is not break-even during active growth, and changes at staffing thresholds.

## Monthly cohort assumptions

New users arrive at the start of the modeled month and pay a full month. Existing users churn before renewal. Users are fractional cohort expectations. No free-user subsidy, annual prepayment, enterprise windfall, borrowed capital or terminal valuation is included. Add those costs before offering a free tier.

| Scenario | New paid / month Y1 | Y2 | Y3 | Monthly churn | CAC / new paid |
|---|---:|---:|---:|---:|---:|
| Conservative | 10 | 20 | 30 | 8% | $30.00 |
| Base | 30 | 80 | 150 | 5% | $20.00 |
| Upside | 50 | 150 | 300 | 3% | $15.00 |

The model starts with an assumed $10,000 contribution, expenses $1,000 at setup, and injects more capital whenever cash would fall below $1,000. Founder compensation is $3,000/month: an allowance, **not a market-rate fully staffed engineering team**. Each full 1,000 active subscribers adds $3,000/month of staffing and $100/month of fixed service cost. Ongoing direct support is also in variable COGS. The 20% profit-tax reserve is a hypothetical cash reserve, not a jurisdiction-specific tax computation. Sales tax/VAT is assumed collected on top of listed prices and remitted separately. New hardware, unexpected litigation, debt, unusual disputes and enterprise compliance are not funded; a real launch budget must add them when applicable.

## The 400% hurdle at 12, 24 and 36 months

| Scenario | Month | Active paid | Cumulative net revenue | All capital required | Cumulative profit after reserve | Return on contributed capital | 400% hurdle? |
|---|---:|---:|---:|---:|---:|---:|---|
| Conservative | 12 | 79 | $8,688.00 | $38,997.24 | $-37,997.24 | -97.4% | No |
| Conservative | 24 | 187 | $34,513.24 | $67,359.42 | $-66,359.42 | -98.5% | No |
| Conservative | 36 | 306 | $80,582.23 | $84,868.67 | $-83,868.67 | -98.8% | No |
| Base | 12 | 276 | $28,813.54 | $28,228.70 | $-27,228.70 | -96.5% | No |
| Base | 24 | 884 | $141,054.09 | $30,213.59 | $-5,895.05 | -19.5% | No |
| Base | 36 | 1,857 | $398,664.78 | $30,213.59 | $54,659.96 | 180.9% | No |
| Upside | 12 | 510 | $51,472.12 | $16,773.61 | $-12,851.70 | -76.6% | No |
| Upside | 24 | 1,885 | $280,140.26 | $16,773.61 | $44,723.92 | 266.6% | No |
| Upside | 36 | 4,369 | $863,247.30 | $16,773.61 | $216,089.28 | 1288.3% | Yes, in this scenario only |

These results do **not** establish the likelihood of growth. Winning and retaining the assumed customers is an unproven business hypothesis. Infrastructure affordability cannot establish customer demand or investment returns. Positive returns also do not imply the cash can all be distributed while funding continued growth.

## Cost sensitivity

| Stress | Variable COGS / paid month | Contribution | Contribution margin |
|---|---:|---:|---:|
| normal | $4.21 | $10.49 | 71.4% |
| model and tool costs double | $6.28 | $8.43 | 57.3% |
| voice costs triple | $5.75 | $8.96 | 60.9% |
| both stresses | $7.82 | $6.88 | 46.8% |

The model-cost doubling stress is intentionally broader than any one supplier promotion. Google’s Gemini 3.8 Flash schedule includes a promotional period; do not capitalize a temporary price as a permanent advantage [S11](SOURCES.md).

## Why idle GPUs hurt

**Unverified arithmetic scenario:** $0.81/hour full-instance rate and 200 aggregate output tokens/second while busy. These are not a fresh EC2 quote or measured Helix throughput.

| Productive utilization | Compute-only $ / million output tokens |
|---|---:|
| 10% | $11.25 |
| 25% | $4.50 |
| 50% | $2.25 |
| 75% | $1.50 |

Formula: `hourly rate × 1,000,000 / (3,600 × busy tokens/second × utilization)`.
This isolates the idle-time penalty. Full cost also includes prefill, loading, retries, storage, CPU, network and operations. A stopped worker can still incur storage costs. At $0.81/hour, 50 paid hours cost $40.50; 730 hours cost $591.30, before extras. Scale-to-zero changes paid hours; batching changes productive throughput. Neither guarantees a specific cost or latency.

## Run or change the scenario

```bash
python tools/economics.py --config config/economics.json --json evidence/economics-results.json --md docs/ECONOMICS.md
```

Edit `config/economics.json`, not the generated tables. The JSON output retains every monthly cohort, cost and capital-injection result. A no-growth/no-revenue test and cash-identity tests prevent a misleading denominator or missing loss. Treat all results as a decision aid for spending gates, not an investment promise.
