import argparse
import asyncio
from decimal import Decimal

from .config import RiskConfig
from .database import Ledger
from .exchange import PaperGateway, ReadOnlyGateway
from .models import Mode, Order, Portfolio, Side
from .risk import RiskEngine
from .service import TradingService


async def run(args):
    cfg = RiskConfig.load(args.config)
    if cfg.mode is Mode.LIVE:
        raise SystemExit("LIVE is intentionally disabled in v0.1")
    service = TradingService(Ledger(args.database), RiskEngine(cfg), PaperGateway() if cfg.mode is Mode.PAPER else ReadOnlyGateway())
    service.startup_recovery()
    print(f"mode={cfg.mode} healthy={service.health.can_open} database={args.database}")
    if args.paper_order:
        pair, side, quantity, price = args.paper_order
        order = Order(pair.upper(), Side(side.upper()), Decimal(quantity), Decimal(price))
        portfolio = Portfolio(cfg.total_capital, {}, equity=cfg.total_capital, peak_equity=cfg.total_capital)
        result = await service.place(order, portfolio)
        print(f"client_order_id={result.client_order_id} state={result.state}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config/risk.example.yaml")
    p.add_argument("--database", default="trading.sqlite3")
    p.add_argument("--paper-order", nargs=4, metavar=("PAIR", "SIDE", "QUANTITY", "PRICE"))
    asyncio.run(run(p.parse_args()))

