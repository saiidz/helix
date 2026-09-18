from concurrent.futures import ThreadPoolExecutor
import pytest
from helix.ledger import Ledger, BudgetExceeded, DuplicateRequest, LedgerError


def test_budget_and_duplicate(tmp_path):
    l=Ledger(tmp_path/"l.db")
    l.reserve("id1","hash","sage","m",70,100)
    with pytest.raises(BudgetExceeded): l.reserve("id2","hash","sage","m",70,100)
    with pytest.raises(DuplicateRequest): l.reserve("id1","hash","sage","m",1,100)
    l.finish("id1",20)
    l.reserve("id2","hash","sage","m",70,100)
    assert l.summary()["model_cost_usd"] == 0.00009


def test_uncertain_failures_stay_charged(tmp_path):
    l=Ledger(tmp_path/"l.db")
    l.reserve("a","hash","sage","m",80,100)
    l.hold_uncertain_failure("a")
    assert l.summary()["model_cost_usd"] == 0.00008
    assert l.summary()["counts"]["failed_cost_uncertain"] == 1


def test_concurrent_requests_cannot_overspend(tmp_path):
    l=Ledger(tmp_path/"l.db")
    def one(n):
        try:
            l.reserve(str(n),str(n),"sage","m",70,100)
            return True
        except BudgetExceeded: return False
    with ThreadPoolExecutor(8) as pool:
        assert sum(pool.map(one,range(8))) == 1


def test_reports_overestimate_instead_of_hiding_actual(tmp_path):
    l=Ledger(tmp_path/"l.db")
    l.reserve("a","hash","sage","m",20,100)
    l.finish("a",120)
    assert l.summary()["model_cost_usd"] == 0.00012
    with pytest.raises(BudgetExceeded): l.reserve("b","hash","sage","m",1,100)
    with pytest.raises(LedgerError): l.finish("a",0)


def test_estimated_usage_not_marked_verified(tmp_path):
    l=Ledger(tmp_path/"l.db")
    l.reserve("a","hash","sage","m",20,100)
    l.finish("a",None)
    with l.connect() as c:
        assert c.execute("SELECT usage_verified,charged FROM requests").fetchone() == (0,20)


def test_ledger_connections_are_closed(tmp_path):
    import sqlite3
    ledger=Ledger(tmp_path/"closed.db")
    with ledger.connect() as connection:
        connection.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
