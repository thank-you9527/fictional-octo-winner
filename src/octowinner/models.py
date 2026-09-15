from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Mode(StrEnum):
    PAPER = "PAPER"
    READ_ONLY = "READ_ONLY"
    LIVE = "LIVE"


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class OrderState(StrEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


TERMINAL_STATES = {OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED}
TRANSITIONS = {
    OrderState.REQUESTED: {OrderState.APPROVED, OrderState.REJECTED},
    OrderState.APPROVED: {OrderState.SUBMITTED, OrderState.REJECTED},
    OrderState.SUBMITTED: {OrderState.ACKNOWLEDGED, OrderState.UNKNOWN, OrderState.REJECTED},
    OrderState.ACKNOWLEDGED: {OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CANCELLED, OrderState.UNKNOWN},
    OrderState.PARTIALLY_FILLED: {OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CANCELLED, OrderState.UNKNOWN},
    OrderState.UNKNOWN: {OrderState.ACKNOWLEDGED, OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED},
}


@dataclass(frozen=True)
class MarketSnapshot:
    pair: str
    price: Decimal
    bid: Decimal
    ask: Decimal
    volume: Decimal
    position_pnl_pct: Decimal = Decimal("0")
    observed_at: str = field(default_factory=now_iso)

    @property
    def spread_pct(self) -> Decimal:
        return (self.ask - self.bid) / self.price * 100 if self.price else Decimal("0")


@dataclass(frozen=True)
class Decision:
    action: Side
    reason: str
    confidence: Decimal


@dataclass
class Order:
    pair: str
    side: Side
    quantity: Decimal
    price: Decimal
    client_order_id: str = field(default_factory=lambda: str(uuid4()))
    state: OrderState = OrderState.REQUESTED
    exchange_order_id: str | None = None
    filled_quantity: Decimal = Decimal("0")

    @property
    def notional(self) -> Decimal:
        return self.quantity * self.price

    def transition(self, target: OrderState) -> None:
        if target not in TRANSITIONS.get(self.state, set()):
            raise ValueError(f"invalid order transition: {self.state} -> {target}")
        self.state = target


@dataclass(frozen=True)
class Portfolio:
    cash: Decimal
    positions: dict[str, Decimal]
    realized_pnl_today: Decimal = Decimal("0")
    equity: Decimal = Decimal("0")
    peak_equity: Decimal = Decimal("0")
    daily_trades: int = 0

