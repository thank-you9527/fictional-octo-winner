from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import yaml

from .models import Mode

LIVE_PHRASE = "I ACKNOWLEDGE REAL ORDERS MAY LOSE MONEY"


@dataclass(frozen=True)
class RiskConfig:
    mode: Mode
    quote_currency: str
    total_capital: Decimal
    max_order_notional: Decimal
    max_daily_trades: int
    min_cash: Decimal
    max_position_notional: Decimal
    daily_loss_limit: Decimal
    total_drawdown_limit: Decimal
    pair_whitelist: frozenset[str]
    market_data_stale_seconds: int
    price_change_trigger_pct: Decimal
    volume_change_trigger_pct: Decimal
    spread_trigger_pct: Decimal
    pnl_trigger_pct: Decimal
    kill_switch: bool
    live_acknowledgement: str

    @classmethod
    def load(cls, path: str | Path) -> "RiskConfig":
        raw = yaml.safe_load(Path(path).read_text())
        decimals = {"total_capital", "max_order_notional", "min_cash", "max_position_notional", "daily_loss_limit", "total_drawdown_limit", "price_change_trigger_pct", "volume_change_trigger_pct", "spread_trigger_pct", "pnl_trigger_pct"}
        for key in decimals:
            raw[key] = Decimal(str(raw[key]))
        raw["mode"] = Mode(raw.get("mode", "PAPER"))
        raw["pair_whitelist"] = frozenset(raw["pair_whitelist"])
        cfg = cls(**raw)
        if cfg.mode is Mode.LIVE and cfg.live_acknowledgement != LIVE_PHRASE:
            raise ValueError("LIVE mode requires the exact acknowledgement phrase")
        return cfg

