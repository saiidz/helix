"""Reproducible Helix operating scenarios. Standard library only; no API or purchases.

The monthly cash model includes replacement/new-user CAC, founder compensation,
additional staffing, service costs, refunds, payment fees and a hypothetical tax
reserve. Follow-on capital is counted in the return denominator. No terminal
valuation, loan financing, hardware resale, or growth beyond explicit inputs.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path


def validate(cfg: dict) -> None:
    if not math.isclose(sum(p['mix'] for p in cfg['plans']), 1):
        raise ValueError('Plan mix must sum to one')
    for k in ('card_percent', 'billing_percent', 'refund_fraction', 'profit_tax_reserve_fraction'):
        if not 0 <= cfg[k] < 1:
            raise ValueError(f'{k} must lie in [0, 1)')
    for k in ('initial_capital', 'minimum_cash_reserve', 'setup_expense',
              'founder_compensation_monthly', 'other_opex_monthly',
              'service_fixed_monthly', 'service_fixed_per_1000_active',
              'additional_staff_per_1000_active', 'card_fixed'):
        if not math.isfinite(cfg[k]) or cfg[k] < 0:
            raise ValueError(f'{k} must be finite and nonnegative')
    if cfg['initial_capital'] <= 0:
        raise ValueError('Positive initial capital required for a return calculation')
    for p in cfg['plans']:
        for k in ('price', 'mix', 'model_tools', 'voice', 'storage', 'direct_support'):
            if not math.isfinite(p[k]) or p[k] < 0:
                raise ValueError(f'{p["name"]}.{k} must be finite and nonnegative')
        if p['price'] == 0:
            raise ValueError('Only paid plans are included in this scenario')
    for s in cfg['scenarios']:
        if not 0 <= s['monthly_churn'] < 1 or s['cac_per_new_paid'] < 0:
            raise ValueError('Invalid churn or CAC')
        if len(s['new_paid_per_month_by_year']) != 3 or any(n < 0 for n in s['new_paid_per_month_by_year']):
            raise ValueError('Exactly three nonnegative annual acquisition assumptions required')


def unit_economics(cfg: dict, model_multiplier: float = 1, voice_multiplier: float = 1) -> dict:
    validate(cfg)
    rows = []
    for p in cfg['plans']:
        fees = p['price'] * (cfg['card_percent'] + cfg['billing_percent']) + cfg['card_fixed']
        costs = (p['model_tools'] * model_multiplier + p['voice'] * voice_multiplier
                 + p['storage'] + p['direct_support'] + fees)
        net = p['price'] * (1 - cfg['refund_fraction'])
        rows.append({**p, 'fees': fees, 'net_revenue': net, 'variable_cogs': costs,
                     'contribution': net - costs, 'contribution_margin': (net - costs) / net})
    blend = {key: sum(p['mix'] * p[key] for p in rows)
             for key in ('price', 'net_revenue', 'variable_cogs', 'contribution')}
    blend['contribution_margin'] = blend['contribution'] / blend['net_revenue']
    return {'plans': rows, 'blended': blend}


def simulate(cfg: dict, scenario: dict) -> list[dict]:
    unit = unit_economics(cfg)['blended']
    active = 0.0
    total_capital = float(cfg['initial_capital'])
    cash = total_capital - cfg['setup_expense']
    cumulative_profit_before_tax = -float(cfg['setup_expense'])
    cumulative_tax_reserve = 0.0
    cumulative_revenue = cumulative_cogs = cumulative_opex = 0.0
    output = []
    for month in range(1, 37):
        new = scenario['new_paid_per_month_by_year'][(month - 1) // 12]
        churned = active * scenario['monthly_churn']
        active = active - churned + new
        # Fractional users are cohort expected values, not claims about actual people.
        revenue = active * unit['net_revenue']
        service_fixed = cfg['service_fixed_monthly'] + math.floor(active / 1000) * cfg['service_fixed_per_1000_active']
        cogs = active * unit['variable_cogs'] + service_fixed
        acquisition = new * scenario['cac_per_new_paid']
        staffing = math.floor(active / 1000) * cfg['additional_staff_per_1000_active']
        opex = cfg['founder_compensation_monthly'] + cfg['other_opex_monthly'] + staffing + acquisition
        pre_tax = revenue - cogs - opex
        cumulative_profit_before_tax += pre_tax
        # Conservative accounting reserve on newly positive cumulative profit. No tax
        # refund is credited after a later loss. This is not a tax-law computation.
        tax = max(0.0, cfg['profit_tax_reserve_fraction'] * max(0.0, cumulative_profit_before_tax)
                  - cumulative_tax_reserve)
        cumulative_tax_reserve += tax
        profit = pre_tax - tax
        cash += profit
        injected = max(0.0, cfg['minimum_cash_reserve'] - cash)
        total_capital += injected
        cash += injected
        cumulative_revenue += revenue
        cumulative_cogs += cogs
        cumulative_opex += opex
        cumulative_profit = cumulative_profit_before_tax - cumulative_tax_reserve
        output.append({
            'month': month, 'active_paid': active, 'new_paid': new, 'churned': churned,
            'revenue': revenue, 'cogs': cogs, 'opex': opex, 'tax_reserve': tax,
            'operating_profit_after_reserve': profit, 'cash': cash,
            'capital_injected_this_month': injected, 'total_capital_contributed': total_capital,
            'cumulative_revenue': cumulative_revenue, 'cumulative_cogs': cumulative_cogs,
            'cumulative_opex': cumulative_opex, 'cumulative_tax_reserve': cumulative_tax_reserve,
            'cumulative_profit': cumulative_profit,
            'modeled_return_on_contributed_capital': cumulative_profit / total_capital,
            'cumulative_service_gross_margin': (cumulative_revenue - cumulative_cogs) / cumulative_revenue if cumulative_revenue else None,
        })
        if not math.isclose(cash, total_capital + cumulative_profit, abs_tol=1e-6):
            raise AssertionError('Cash/capital/profit identity failed')
    return output


def report(cfg: dict) -> dict:
    unit = unit_economics(cfg)
    u = unit['blended']
    minimum_fixed = cfg['service_fixed_monthly'] + cfg['founder_compensation_monthly'] + cfg['other_opex_monthly']
    replacement = 0.05 * 20  # Explicit base steady-state churn and CAC assumption.
    b = math.ceil(minimum_fixed / (u['contribution'] - replacement))
    return {
        'assumptions': cfg, 'units': unit,
        'base_steady_state_break_even_paid': b,
        'break_even_note': 'No growth acquisition, base 5% monthly churn and $20 replacement CAC; before extra staffing thresholds.',
        'scenarios': {s['name']: simulate(cfg, s) for s in cfg['scenarios']},
        'sensitivities': {label: unit_economics(cfg, m, v)['blended'] for label, m, v in [
            ('normal', 1, 1), ('model_and_tool_costs_double', 2, 1),
            ('voice_costs_triple', 1, 3), ('both_stresses', 2, 3)]},
        'gpu_sensitivity': [
            {'utilization': u, 'compute_only_usd_per_million_output_tokens':
             cfg['gpu_sensitivity']['assumed_full_instance_hourly'] * 1e6 /
             (3600 * cfg['gpu_sensitivity']['busy_aggregate_output_tokens_per_second'] * u)}
            for u in cfg['gpu_sensitivity']['utilizations']
        ],
    }


def money(x: float) -> str:
    return f'${x:,.2f}'


def markdown(r: dict) -> str:
    u = r['units']['blended']
    lines = ['# Helix — reproducible economics', '',
        '> Scenario calculations, not forecasts. All dollar amounts are USD. No money was spent running this model.', '',
        '## Definitions that prevent misleading ROI claims', '',
        '`Contribution = net revenue − variable service costs`.',
        '`Service gross margin = (net revenue − all service COGS) / net revenue`.',
        '`Operating profit = net revenue − service COGS − acquisition − compensation − other operating expenses`.',
        '`Modeled return on contributed capital = cumulative profit after the hypothetical tax reserve / ALL capital contributed`.', '',
        'A 400% markup on COGS is an 80% gross margin, not a 400% investment return. A 400% investment-return hurdle requires cumulative profit equal to four times actual contributed capital. This simulation assigns no sale valuation or terminal goodwill, and includes follow-on financing in its denominator. It is not annualized ROI or IRR; no actual distributions are assumed.', '',
        '## Candidate subscription economics', '',
        'Prices and usage are hypotheses. Stripe domestic-card fees of 2.9% + $0.30 and Billing at 0.7% are the sourced fee inputs [S12–S13](SOURCES.md). The scenario deducts a 2% revenue refund allowance while retaining processing charges. Other line items are management assumptions, not supplier quotations.', '',
        '| Plan | Price | Model + tools | Voice | Storage + direct support | Payment + billing | Total variable COGS | Contribution after refunds | Contribution margin |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for p in r['units']['plans']:
        lines.append(f'| {p["name"]} | {money(p["price"])} | {money(p["model_tools"])} | {money(p["voice"])} | {money(p["storage"]+p["direct_support"])} | {money(p["fees"])} | {money(p["variable_cogs"])} | {money(p["contribution"])} | {p["contribution_margin"]:.1%} |')
    lines += ['', f'At the assumed 60% / 30% / 10% plan mix: billed ARPU **{money(u["price"])}**, net ARPU **{money(u["net_revenue"])}**, variable COGS **{money(u["variable_cogs"])}**, contribution **{money(u["contribution"])}** per paid user-month. The resulting **{u["contribution_margin"]:.1%} contribution margin** is before fixed hosting, acquisition, founder pay and other overhead. Do not advertise it as net profit.', '',
        f'Base steady-state break-even is approximately **{r["base_steady_state_break_even_paid"]} paying users** with the included $3,000 founder-compensation allowance, $200 overhead, $100 fixed hosting, and replacement acquisition at 5% churn × $20 CAC. This is not break-even during active growth, and changes at staffing thresholds.', '',
        '## Monthly cohort assumptions', '',
        'New users arrive at the start of the modeled month and pay a full month. Existing users churn before renewal. Users are fractional cohort expectations. No free-user subsidy, annual prepayment, enterprise windfall, borrowed capital or terminal valuation is included. Add those costs before offering a free tier.', '',
        '| Scenario | New paid / month Y1 | Y2 | Y3 | Monthly churn | CAC / new paid |',
        '|---|---:|---:|---:|---:|---:|']
    for s in r['assumptions']['scenarios']:
        a,b,c = s['new_paid_per_month_by_year']
        lines.append(f'| {s["name"]} | {a} | {b} | {c} | {s["monthly_churn"]:.0%} | {money(s["cac_per_new_paid"])} |')
    lines += ['', 'The model starts with an assumed $10,000 contribution, expenses $1,000 at setup, and injects more capital whenever cash would fall below $1,000. Founder compensation is $3,000/month: an allowance, **not a market-rate fully staffed engineering team**. Each full 1,000 active subscribers adds $3,000/month of staffing and $100/month of fixed service cost. Ongoing direct support is also in variable COGS. The 20% profit-tax reserve is a hypothetical cash reserve, not a jurisdiction-specific tax computation. Sales tax/VAT is assumed collected on top of listed prices and remitted separately. New hardware, unexpected litigation, debt, unusual disputes and enterprise compliance are not funded; a real launch budget must add them when applicable.', '',
        '## The 400% hurdle at 12, 24 and 36 months', '',
        '| Scenario | Month | Active paid | Cumulative net revenue | All capital required | Cumulative profit after reserve | Return on contributed capital | 400% hurdle? |',
        '|---|---:|---:|---:|---:|---:|---:|---|']
    for name, series in r['scenarios'].items():
        for n in (12,24,36):
            x=series[n-1]
            lines.append(f'| {name} | {n} | {x["active_paid"]:,.0f} | {money(x["cumulative_revenue"])} | {money(x["total_capital_contributed"])} | {money(x["cumulative_profit"])} | {x["modeled_return_on_contributed_capital"]:.1%} | {"Yes, in this scenario only" if x["modeled_return_on_contributed_capital"] >= 4 else "No"} |')
    lines += ['', 'These results do **not** establish the likelihood of growth. Winning and retaining the assumed customers is an unproven business hypothesis. Infrastructure affordability cannot establish customer demand or investment returns. Positive returns also do not imply the cash can all be distributed while funding continued growth.', '',
        '## Cost sensitivity', '',
        '| Stress | Variable COGS / paid month | Contribution | Contribution margin |', '|---|---:|---:|---:|']
    for label, x in r['sensitivities'].items():
        lines.append(f'| {label.replace("_", " ")} | {money(x["variable_cogs"])} | {money(x["contribution"])} | {x["contribution_margin"]:.1%} |')
    lines += ['', 'The model-cost doubling stress is intentionally broader than any one supplier promotion. Google’s Gemini 3.8 Flash schedule includes a promotional period; do not capitalize a temporary price as a permanent advantage [S11](SOURCES.md).', '',
        '## Why idle GPUs hurt', '',
        '**Unverified arithmetic scenario:** $0.81/hour full-instance rate and 200 aggregate output tokens/second while busy. These are not a fresh EC2 quote or measured Helix throughput.', '',
        '| Productive utilization | Compute-only $ / million output tokens |', '|---|---:|']
    for x in r['gpu_sensitivity']:
        lines.append(f'| {x["utilization"]:.0%} | {money(x["compute_only_usd_per_million_output_tokens"])} |')
    lines += ['', 'Formula: `hourly rate × 1,000,000 / (3,600 × busy tokens/second × utilization)`.',
        'This isolates the idle-time penalty. Full cost also includes prefill, loading, retries, storage, CPU, network and operations. A stopped worker can still incur storage costs. At $0.81/hour, 50 paid hours cost $40.50; 730 hours cost $591.30, before extras. Scale-to-zero changes paid hours; batching changes productive throughput. Neither guarantees a specific cost or latency.', '',
        '## Run or change the scenario', '',
        '```bash', 'python tools/economics.py --config config/economics.json --json evidence/economics-results.json --md docs/ECONOMICS.md', '```', '',
        'Edit `config/economics.json`, not the generated tables. The JSON output retains every monthly cohort, cost and capital-injection result. A no-growth/no-revenue test and cash-identity tests prevent a misleading denominator or missing loss. Treat all results as a decision aid for spending gates, not an investment promise.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('config/economics.json'))
    parser.add_argument('--json', type=Path, default=Path('evidence/economics-results.json'))
    parser.add_argument('--md', type=Path, default=Path('docs/ECONOMICS.md'))
    args = parser.parse_args()
    r = report(json.loads(args.config.read_text()))
    for p in (args.json, args.md): p.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(r, indent=2) + '\n')
    args.md.write_text(markdown(r))
    print(f'Wrote {args.json} and {args.md}')


if __name__ == '__main__':
    main()
