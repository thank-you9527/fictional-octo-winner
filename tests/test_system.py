from dataclasses import replace
from decimal import Decimal as D

import pytest

from octowinner.config import RiskConfig
from octowinner.database import Ledger
from octowinner.exchange import ExecutionGateway, PaperGateway
from octowinner.models import Mode, Order, OrderState, Portfolio, Side
from octowinner.risk import RiskEngine
from octowinner.service import TradingService


@pytest.fixture
def cfg():
    return RiskConfig(Mode.PAPER, "TWD", D("10000"), D("1000"), 5, D("3000"), D("2500"), D("500"), D("1000"), frozenset({"BTC_TWD"}), 30, D("1"), D("50"), D("1"), D("3"), False, "")

@pytest.fixture
def portfolio(): return Portfolio(D("10000"), {"BTC_TWD": D("0.1")}, D("0"), D("10000"), D("10000"), 0)

def test_order_state_machine_and_partial_fill():
    o = Order("BTC_TWD", Side.BUY, D(".01"), D("100")); o.transition(OrderState.APPROVED); o.transition(OrderState.SUBMITTED); o.transition(OrderState.ACKNOWLEDGED); o.transition(OrderState.PARTIALLY_FILLED); o.transition(OrderState.FILLED)
    with pytest.raises(ValueError): o.transition(OrderState.SUBMITTED)

@pytest.mark.parametrize("change,reason", [({"cash":D("10")},"insufficient balance"), ({"realized_pnl_today":D("-500")},"daily loss limit")])
def test_risk_rejections(cfg, portfolio, change, reason):
    p = replace(portfolio, **change); r = RiskEngine(cfg).evaluate(Order("BTC_TWD", Side.BUY, D("1"), D("100")), p, D("100")); assert not r.approved and r.reason == reason

def test_kill_switch(cfg, portfolio):
    r = RiskEngine(replace(cfg, kill_switch=True)).evaluate(Order("BTC_TWD", Side.BUY, D("1"), D("100")), portfolio); assert not r.approved

@pytest.mark.asyncio
async def test_duplicate_order(tmp_path, cfg, portfolio):
    s=TradingService(Ledger(tmp_path/"x.db"),RiskEngine(cfg),PaperGateway()); o=Order("BTC_TWD",Side.BUY,D("1"),D("100")); await s.place(o,portfolio)
    with pytest.raises(ValueError): await s.place(o,portfolio)

class TimeoutGateway(ExecutionGateway):
    async def submit(self, order): order.transition(OrderState.SUBMITTED); raise TimeoutError
    async def reconcile(self, order): order.transition(OrderState.FILLED); return order

@pytest.mark.asyncio
async def test_timeout_requires_reconciliation_no_resubmit(tmp_path,cfg,portfolio):
    s=TradingService(Ledger(tmp_path/"x.db"),RiskEngine(cfg),TimeoutGateway()); o=await s.place(Order("BTC_TWD",Side.BUY,D("1"),D("100")),portfolio); assert o.state is OrderState.UNKNOWN and s.health.unresolved_order
    await s.reconcile(o); assert o.state is OrderState.FILLED and not s.health.unresolved_order

def test_restart_pending_and_stale_market_data(tmp_path,cfg):
    l=Ledger(tmp_path/"x.db"); l.execute("INSERT INTO orders(client_order_id,pair,side,quantity,price,state) VALUES('x','BTC_TWD','BUY','1','1','SUBMITTED')")
    s=TradingService(l,RiskEngine(cfg),PaperGateway()); s.startup_recovery(); assert not s.health.can_open
    s.health.unresolved_order=False; s.health.market_data_fresh=False; assert not s.health.can_open

def test_reconciliation_mismatch_blocks(tmp_path,cfg):
    s=TradingService(Ledger(tmp_path/"x.db"),RiskEngine(cfg),PaperGateway()); assert not s.reconcile_balances({"TWD":D("1")},{"TWD":D("2")}); assert not s.health.can_open

