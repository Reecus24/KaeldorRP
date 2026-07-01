# Underworld & Financial Markets (source of truth)

## Underworld access (gatekeeping)
The Underworld tab is fully locked until the player has a **trusted criminal contact**.
- Meet a **Shady Contact** via Socials 3.0: Social ▸ Meet People ▸ **Prowl the Backstreets**
  (`go_to_streets` action; also raises suspicion slightly).
- Access unlocks when a `shady_contact` reaches **Relationship ≥ 40 and Trust ≥ 30**
  (`UW_MIN_SCORE` / `UW_MIN_TRUST` in `server.py`).
- Gated endpoints: `GET /illegal-actions`, `POST /illegal-actions/{id}/commit`,
  `GET /market/crypto`, `POST /market/buy|sell` (for crypto assets).
- `GET /underworld/status` → `{access, reason, contact, min_score, min_trust}`.

## Crime risk profiles (two distinct outcomes)
Every crime resolves into one of three outcomes (`game_engine._resolve_illegal`):
1. **BUST** (`bust_risk`) — caught by law enforcement → fine + jail + suspicion + legal-rep hit.
   Effective odds = `police_risk × (1 + suspicion/150) × (1 − min(0.4, street×0.03)) × risk_mult`.
2. **FAIL** (`fail_chance`) — the job flops (lock didn't open, mark walked away).
   **Reward = $0, no jail.** Minor suspicion + stress only.
   Effective odds = `failure_chance × (1 − min(0.3, street×0.025))`, capped so bust+fail ≤ 0.95.
3. **SUCCESS** — the remaining probability → payout (`reward_min..reward_max`) + suspicion.
`GET /illegal-actions` returns the live `bust_risk` and `fail_chance` per action so the UI
shows the true odds. The Underworld crime cards render Fail vs Bust as two separate panels.

## Financial markets (`market_engine.py`)
Lightweight geometric-random-walk simulator; prices advance lazily on each read based on
**real elapsed time** (1 game hour = 1 real hour). No scheduler.
- Per read: `price *= exp((drift − ½·vol²)·dt_h + vol·√dt_h·Z)`, clamped to `[0.1×, 12×]` base.
- **Stocks** (`kind:"stock"`) — open to all, traded in the **Bank**. Assets: KAEL, NOVA, HELX, ORB.
- **Crypto** (`kind:"crypto"`) — Underworld-gated, traded in the **Underworld**. Assets: BTK, ETK, KLD, DGZ.
- Player holdings in `p.portfolio = {asset_id: {qty, avg_cost}}`; valued into net worth as `investments`.
- Endpoints: `GET /market/stocks`, `GET /market/crypto`, `GET /market/portfolio`,
  `POST /market/buy`, `POST /market/sell` (`{asset_id, qty}`).

## Admin Sandbox controls (Admin ▸ Tuning)
Stored in `game_config.tuning`, live on next read:
| Key | Meaning | Default |
|-----|---------|---------|
| `stock_drift` | Stock expected return per real hour | 0.0015 |
| `stock_volatility` | Stock hourly volatility | 0.03 |
| `crypto_drift` | Crypto expected return per real hour | 0.004 |
| `crypto_volatility` | Crypto hourly volatility | 0.09 |
