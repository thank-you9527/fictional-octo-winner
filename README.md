# fictional-octo-winner v0.1

A fail-closed Python skeleton for BitoPro spot trading. **PAPER is the default. LIVE order submission is intentionally disabled in v0.1.** This is experimental software, not financial advice.

## Architecture

`BitoPro WebSocket/REST -> Market Data Collector -> deterministic Trigger/Reporter -> DecisionEngine -> deterministic RiskEngine -> ExecutionGateway -> reconciliation -> SQLite`

- `DecisionEngine` exposes `BUY`, `SELL`, or `HOLD` plus reason/confidence. `MockDecisionEngine` is available; Gemini is an unimplemented adapter boundary. Confidence never sizes positions.
- Immutable `RiskConfig` controls capital, per-order notional, daily count, cash reserve, maximum position, daily loss, total drawdown, pair whitelist, stale-data threshold, and kill switch.
- Spot limit orders only. No leverage, margin/borrowing, futures, perpetuals, withdrawal, or transfer API exists in the codebase.
- Orders use `REQUESTED -> APPROVED -> SUBMITTED -> ACKNOWLEDGED -> PARTIALLY_FILLED/FILLED/CANCELLED`, with `REJECTED` and `UNKNOWN` fail-closed paths. A timeout after submission becomes `UNKNOWN`; it is never retried before reconciliation.
- SQLite separates decisions, orders, fills, market snapshots, portfolio snapshots, account snapshots, and system events. Exchange order/trade IDs are retained.
- Startup pending orders, stale market data, exchange/database/auth failure, failed heartbeat, unresolved orders, and reconciliation mismatch block new positions.

Official endpoints follow the [BitoPro official API documentation](https://github.com/bitoex/bitopro-official-api-docs): REST `https://api.bitopro.com/v3`; public WebSocket `wss://stream.bitopro.com:443/ws/v1/pub`. Verify endpoint schemas against the changelog before any production acceptance test.

## Install and run PAPER

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp config/risk.example.yaml config/risk.local.yaml
octowinner --config config/risk.local.yaml --database trading.sqlite3
octowinner --config config/risk.local.yaml --paper-order BTC_TWD BUY 0.0001 1000000
pytest -q
```

The example starts PAPER with TWD 10,000. Adjust limits deliberately. The CLI paper order exercises validation, persistence, and paper acknowledgement without credentials or network order submission.

## Modes and safety gates

- `PAPER`: local simulated acknowledgement; no credentials required.
- `READ_ONLY`: intended for authenticated balances/reconciliation; its gateway rejects submission.
- `LIVE`: config parsing requires the exact phrase `I ACKNOWLEDGE REAL ORDERS MAY LOSE MONEY`, **and** the v0.1 CLI still exits because `LiveGateway.submit()` is disabled. Enabling it later requires code review and human acceptance testing, not merely changing YAML.

Never commit `.env`; it is ignored. Do not grant withdrawal permissions to a future API key.

## Local vault integration (later)

Implement `VaultAdapter.load_bitopro_credentials()` in `exchange.py` using the existing local AES-256-GCM vault. Return a `Credentials` value only in memory, never log it, and inject the adapter into `BitoProPrivateClient`. `EnvironmentVaultAdapter` exists only as a local development option reading `BITOPRO_API_KEY`, `BITOPRO_API_SECRET`, and `BITOPRO_EMAIL`; no values are requested or included here.

Before READ_ONLY use, test signing against BitoPro's current official examples. Before any future LIVE implementation, create a separate API key without withdrawal permission, restrict it by IP if BitoPro supports that at the time, validate minimum increments/fees, and run a human-observed minimal-order test.

## Reconciliation and operations

Run authenticated balance reconciliation at least daily. Persist exchange balances in `account_snapshots`, compare them with the local ledger, and set `reconciliation_match=False` plus a CRITICAL alert on mismatch. On restart, any non-terminal order locks trading until queried by exchange order ID/trade history. Do not infer failure from a timeout and do not resubmit the same intent.

Heartbeat/watchdog health is modeled in `Health`. A production runner still needs scheduling, durable alert delivery, WebSocket normalization/reconnect metrics, database backup, and process supervision.

## v0.1 acceptance status

Implemented: safety modes/gates, models/state machine, deterministic risk checks/triggers, public BitoPro REST/WebSocket clients, signed private balance/order-query boundaries, PAPER and READ_ONLY gateways, SQLite schema, duplicate protection, restart lock, timeout-to-UNKNOWN, reconciliation lock, and automated risk/state tests.

Human acceptance required / intentionally unfinished:

- Validate every BitoPro response field, signature, precision/minimum, fee, rate-limit, and WebSocket payload against a dedicated account in READ_ONLY.
- Wire the continuous runner, snapshot persistence/report generation, daily scheduler, and alert transport.
- Implement fill pagination/idempotent ingestion and complete exchange-status mapping.
- Connect the local vault and later Gemini adapter; Gemini must remain unable to mutate risk settings or size positions.
- Implement and review LIVE reconciliation before implementing LIVE submission. LIVE deployment is explicitly out of scope.

