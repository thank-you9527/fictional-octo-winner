from decimal import Decimal

from .config import RiskConfig
from .models import MarketSnapshot


class TriggerReporter:
    def __init__(self, config: RiskConfig):
        self.c = config
        self.previous: dict[str, MarketSnapshot] = {}

    def reasons(self, current: MarketSnapshot) -> list[str]:
        reasons: list[str] = []
        previous = self.previous.get(current.pair)
        if previous:
            price_delta = abs(current.price - previous.price) / previous.price * 100 if previous.price else Decimal("0")
            volume_delta = abs(current.volume - previous.volume) / previous.volume * 100 if previous.volume else Decimal("0")
            if price_delta >= self.c.price_change_trigger_pct: reasons.append("price_change")
            if volume_delta >= self.c.volume_change_trigger_pct: reasons.append("volume_change")
        if current.spread_pct >= self.c.spread_trigger_pct: reasons.append("spread")
        if abs(current.position_pnl_pct) >= self.c.pnl_trigger_pct: reasons.append("position_pnl")
        self.previous[current.pair] = current
        return reasons

