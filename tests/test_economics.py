import copy
import json
from pathlib import Path
import pytest
from tools.economics import unit_economics, simulate, report

@pytest.fixture
def cfg():
    return json.loads(Path('config/economics.json').read_text())

def test_blended_units_and_fees(cfg):
    r=unit_economics(cfg)
    assert r['blended']['price'] == pytest.approx(15)
    assert r['blended']['net_revenue'] == pytest.approx(14.7)
    assert r['blended']['variable_cogs'] == pytest.approx(4.205)
    assert r['plans'][0]['fees'] == pytest.approx(.624)

def test_capital_not_omitted_and_identity(cfg):
    rows=simulate(cfg,cfg['scenarios'][0])
    assert rows[-1]['total_capital_contributed'] > cfg['initial_capital']
    for row in rows:
        assert row['cash'] >= cfg['minimum_cash_reserve'] - 1e-6
        assert row['cash'] == pytest.approx(row['total_capital_contributed']+row['cumulative_profit'])
        assert row['modeled_return_on_contributed_capital'] == pytest.approx(row['cumulative_profit']/row['total_capital_contributed'])

def test_zero_revenue_is_loss_not_roi(cfg):
    scenario={'new_paid_per_month_by_year':[0,0,0], 'monthly_churn':.05, 'cac_per_new_paid':20}
    end=simulate(cfg,scenario)[-1]
    assert end['cumulative_revenue']==0
    assert end['cumulative_tax_reserve']==0
    assert -1 < end['modeled_return_on_contributed_capital'] < 0

def test_higher_costs_reduce_contribution(cfg):
    assert unit_economics(cfg,2,3)['blended']['contribution'] < unit_economics(cfg)['blended']['contribution']

def test_bad_mix_rejected(cfg):
    cfg['plans'][0]['mix']=.9
    with pytest.raises(ValueError): unit_economics(cfg)

def test_bad_churn_rejected(cfg):
    cfg['scenarios'][0]['monthly_churn']=1
    with pytest.raises(ValueError): unit_economics(cfg)

def test_initial_zero_rejected(cfg):
    cfg['initial_capital']=0
    with pytest.raises(ValueError): unit_economics(cfg)

def test_compute_sensitivity(cfg):
    r=report(cfg)
    assert r['gpu_sensitivity'][0]['compute_only_usd_per_million_output_tokens'] == pytest.approx(11.25)
    assert r['base_steady_state_break_even_paid'] == 348
