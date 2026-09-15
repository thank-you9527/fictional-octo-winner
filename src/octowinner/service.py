from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from .database import Ledger
from .exchange import ExecutionGateway
from .models import Order, OrderState, Portfolio, TERMINAL_STATES
from .risk import RiskEngine


@dataclass
class Health:
    market_data_fresh: bool = True
    exchange_available: bool = True
    database_available: bool = True
    authentication_ok: bool = True
    unresolved_order: bool = False
    reconciliation_match: bool = True
    heartbeat_ok: bool = True

    @property
    def can_open(self) -> bool:
        return (
            self.market_data_fresh
            and self.exchange_available
            and self.database_available
            and self.authentication_ok
            and not self.unresolved_order
            and self.reconciliation_match
            and self.heartbeat_ok
        )


class TradingService:
    def __init__(self, ledger: Ledger, risk: RiskEngine, gateway: ExecutionGateway):
        self.ledger, self.risk, self.gateway = ledger, risk, gateway
        self.health = Health()

    def startup_recovery(self) -> None:
        if self.ledger.pending_orders():
            self.health.unresolved_order = True
            self.ledger.event("PENDING_ORDER_ON_RESTART", "reconciliation required", "CRITICAL")

    async def place(self, order: Order, portfolio: Portfolio) -> Order:
        existing = self.ledger.execute("SELECT state FROM orders WHERE client_order_id=?", (order.client_order_id,)).fetchone()
        if existing: raise ValueError("duplicate client_order_id")
        self.ledger.execute("INSERT INTO orders(client_order_id,pair,side,quantity,price,state) VALUES(?,?,?,?,?,?)", (order.client_order_id, order.pair, order.side, str(order.quantity), str(order.price), order.state))
        if not self.health.can_open:
            order.transition(OrderState.REJECTED); self._save(order); return order
        result = self.risk.evaluate(order, portfolio, order.price)
        order.transition(OrderState.APPROVED if result.approved else OrderState.REJECTED); self._save(order)
        if not result.approved: return order
        try:
            await self.gateway.submit(order); self._save(order)
        except TimeoutError:
            if order.state is OrderState.APPROVED: order.transition(OrderState.SUBMITTED)
            order.transition(OrderState.UNKNOWN)
            self.health.unresolved_order = True
            self._save(order)
        return order

    async def reconcile(self, order: Order) -> Order:
        order = await self.gateway.reconcile(order)
        self._save(order)
        self.health.unresolved_order = order.state not in TERMINAL_STATES
        return order

    def reconcile_balances(self, local: dict[str, Decimal], remote: dict[str, Decimal]) -> bool:
        match = local == remote
        self.health.reconciliation_match = match
        if not match: self.ledger.event("RECONCILIATION_MISMATCH", "local and exchange balances differ", "CRITICAL")
        return match

    def _save(self, order: Order) -> None:
        self.ledger.execute("UPDATE orders SET exchange_order_id=?,filled_quantity=?,state=?,updated_at=CURRENT_TIMESTAMP WHERE client_order_id=?", (order.exchange_order_id, str(order.filled_quantity), order.state, order.client_order_id))
