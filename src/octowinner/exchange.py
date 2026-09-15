from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import AsyncIterator, Protocol

import httpx
import websockets

from .models import MarketSnapshot, Order, OrderState, now_iso

REST_BASE = "https://api.bitopro.com/v3"
WS_BASE = "wss://stream.bitopro.com:443/ws/v1/pub"


@dataclass(frozen=True)
class Credentials:
    api_key: str
    api_secret: str
    email: str


class VaultAdapter(Protocol):
    def load_bitopro_credentials(self) -> Credentials: ...


class EnvironmentVaultAdapter:
    """Local-only adapter; deliberately imported lazily and never logs values."""
    def load_bitopro_credentials(self) -> Credentials:
        import os
        names = ("BITOPRO_API_KEY", "BITOPRO_API_SECRET", "BITOPRO_EMAIL")
        values = [os.environ.get(n) for n in names]
        if not all(values): raise RuntimeError("BitoPro credentials unavailable")
        return Credentials(*values)  # type: ignore[arg-type]


class BitoProPublicClient:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(base_url=REST_BASE, timeout=10)

    async def ticker(self, pair: str) -> MarketSnapshot:
        data = (await self.client.get(f"/tickers/{pair.lower()}" )).raise_for_status().json()
        return MarketSnapshot(pair.upper(), Decimal(str(data["lastPrice"])), Decimal(str(data["bidPrice"])), Decimal(str(data["askPrice"])), Decimal(str(data["volume24hr"])), observed_at=now_iso())

    async def stream(self, pair: str) -> AsyncIterator[dict]:
        url = f"{WS_BASE}/{pair.lower()}/ticker"
        async for ws in websockets.connect(url, ping_interval=20, ping_timeout=20):
            try:
                async for message in ws: yield json.loads(message)
            except websockets.ConnectionClosed:
                continue


class BitoProPrivateClient:
    def __init__(self, vault: VaultAdapter, client: httpx.AsyncClient | None = None):
        self.vault = vault
        self.client = client or httpx.AsyncClient(base_url=REST_BASE, timeout=10)

    def _headers(self, payload: dict) -> dict[str, str]:
        c = self.vault.load_bitopro_credentials()
        encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
        signature = hmac.new(c.api_secret.encode(), encoded.encode(), hashlib.sha384).hexdigest()
        return {"X-BITOPRO-APIKEY": c.api_key, "X-BITOPRO-PAYLOAD": encoded, "X-BITOPRO-SIGNATURE": signature}

    async def balances(self) -> dict:
        c = self.vault.load_bitopro_credentials()
        payload = {"identity": c.email, "nonce": int(time.time() * 1000)}
        return (await self.client.get("/accounts/balance", headers=self._headers(payload))).raise_for_status().json()

    async def get_order(self, pair: str, order_id: str) -> dict:
        c = self.vault.load_bitopro_credentials()
        payload = {"identity": c.email, "nonce": int(time.time() * 1000)}
        return (await self.client.get(f"/orders/{pair.lower()}/{order_id}", headers=self._headers(payload))).raise_for_status().json()

    async def submit_order(self, order: Order) -> dict:
        c = self.vault.load_bitopro_credentials()
        body = {"action": order.side.value.upper(), "amount": str(order.quantity), "price": str(order.price), "type": "LIMIT", "timeInForce": "GTC"}
        payload = {"identity": c.email, "nonce": int(time.time() * 1000)}
        return (await self.client.post(f"/orders/{order.pair.lower()}", json=body, headers=self._headers(payload))).raise_for_status().json()


class ExecutionGateway(ABC):
    @abstractmethod
    async def submit(self, order: Order) -> Order: ...

    @abstractmethod
    async def reconcile(self, order: Order) -> Order: ...


class PaperGateway(ExecutionGateway):
    async def submit(self, order: Order) -> Order:
        order.transition(OrderState.SUBMITTED)
        order.exchange_order_id = f"paper-{order.client_order_id}"
        order.transition(OrderState.ACKNOWLEDGED)
        return order

    async def reconcile(self, order: Order) -> Order:
        return order


class ReadOnlyGateway(ExecutionGateway):
    async def submit(self, order: Order) -> Order:
        raise PermissionError("READ_ONLY never submits orders")

    async def reconcile(self, order: Order) -> Order:
        return order


class LiveGateway(ExecutionGateway):
    """Not wired by the v0.1 CLI. Human-reviewed integration is intentionally required."""
    async def submit(self, order: Order) -> Order:
        raise PermissionError("LIVE execution is disabled in v0.1")

    async def reconcile(self, order: Order) -> Order:
        raise NotImplementedError("LIVE reconciliation requires human acceptance tests")

