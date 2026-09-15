from dataclasses import dataclass
from decimal import Decimal

from .config import RiskConfig
from .models import Order, Portfolio, Side


@dataclass(frozen=True)
class RiskResult:
    approved: bool
    reason: str


class RiskEngine:
    """Deterministic and deliberately receives immutable configuration."""
    def __init__(self, config: RiskConfig):
        self.config = config

    def evaluate(self, order: Order, portfolio: Portfolio, position_price: Decimal = Decimal("0")) -> RiskResult:
        c = self.config
        checks = [
            (not c.kill_switch, "kill switch active"),
            (order.side in {Side.BUY, Side.SELL}, "HOLD is not an order"),
            (order.pair in c.pair_whitelist, "pair not whitelisted"),
            (order.quantity > 0 and order.price > 0, "quantity and price must be positive"),
            (order.notional <= c.max_order_notional, "order notional limit"),
            (portfolio.daily_trades < c.max_daily_trades, "daily trade count limit"),
            (-portfolio.realized_pnl_today < c.daily_loss_limit, "daily loss limit"),
            (portfolio.peak_equity - portfolio.equity < c.total_drawdown_limit, "total drawdown limit"),
        ]
        if order.side is Side.BUY:
            position_value = portfolio.positions.get(order.pair, Decimal("0")) * position_price
            checks += [
                (portfolio.cash >= order.notional, "insufficient balance"),
                (portfolio.cash - order.notional >= c.min_cash, "minimum cash reserve"),
                (position_value + order.notional <= c.max_position_notional, "maximum position limit"),
                (order.notional <= c.total_capital, "total capital limit"),
            ]
        else:
            checks.append((portfolio.positions.get(order.pair, Decimal("0")) >= order.quantity, "insufficient asset balance"))
        for ok, reason in checks:
            if not ok:
                return RiskResult(False, reason)
        return RiskResult(True, "approved")

