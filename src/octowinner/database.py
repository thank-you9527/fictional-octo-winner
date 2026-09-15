from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, pair TEXT, action TEXT, reason TEXT, confidence TEXT, snapshot_id INTEGER);
CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, client_order_id TEXT NOT NULL UNIQUE, exchange_order_id TEXT, exchange_trade_id TEXT, pair TEXT NOT NULL, side TEXT NOT NULL, quantity TEXT NOT NULL, price TEXT NOT NULL, filled_quantity TEXT NOT NULL DEFAULT '0', state TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS fills (id INTEGER PRIMARY KEY, client_order_id TEXT NOT NULL, exchange_order_id TEXT, exchange_trade_id TEXT UNIQUE, quantity TEXT, price TEXT, fee TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS market_snapshots (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, pair TEXT, price TEXT, bid TEXT, ask TEXT, volume TEXT, position_pnl_pct TEXT, trigger_reason TEXT);
CREATE TABLE IF NOT EXISTS portfolio_snapshots (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, source TEXT, cash TEXT, equity TEXT, positions_json TEXT);
CREATE TABLE IF NOT EXISTS account_snapshots (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, source TEXT, balances_json TEXT);
CREATE TABLE IF NOT EXISTS system_events (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, severity TEXT, event_type TEXT, message TEXT, metadata_json TEXT);
CREATE INDEX IF NOT EXISTS idx_orders_state ON orders(state);
CREATE INDEX IF NOT EXISTS idx_orders_exchange_id ON orders(exchange_order_id);
"""


class Ledger:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        with self.conn:
            return self.conn.execute(sql, params)

    def event(self, kind: str, message: str, severity: str = "INFO", metadata: dict | None = None) -> None:
        self.execute("INSERT INTO system_events(severity,event_type,message,metadata_json) VALUES(?,?,?,?)", (severity, kind, message, json.dumps(metadata or {})))

    def pending_orders(self):
        return self.execute("SELECT * FROM orders WHERE state NOT IN ('FILLED','CANCELLED','REJECTED')").fetchall()

