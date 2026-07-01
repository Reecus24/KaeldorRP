"""Kaeldor financial markets — stocks (open to all) and crypto (Underworld-gated).

A lightweight geometric-random-walk price simulator. Prices advance lazily whenever
the market is read, based on REAL elapsed time (1 game hour = 1 real hour), using
volatility/drift pulled live from the Admin Sandbox (game_config.tuning). No scheduler.
"""
import math
import random
from datetime import datetime, timezone, timedelta

HISTORY_LEN = 40
MIN_STEP_HOURS = 0.01  # ignore near-instant refreshes


def _now():
    return datetime.now(timezone.utc)


def _parse(ts):
    if not ts:
        return _now()
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return _now()


def _params(cfg, kind):
    t = (cfg or {}).get("tuning") or {}
    if kind == "crypto":
        return float(t.get("crypto_drift", 0.004)), float(t.get("crypto_volatility", 0.09))
    return float(t.get("stock_drift", 0.0015)), float(t.get("stock_volatility", 0.03))


def _advance(asset, cfg):
    """Advance one asset's price by the real time elapsed since last update."""
    drift, vol = _params(cfg, asset.get("kind", "stock"))
    last = _parse(asset.get("last_update"))
    dt_h = (_now() - last).total_seconds() / 3600.0
    if dt_h < MIN_STEP_HOURS:
        return False
    dt_h = min(dt_h, 24.0)  # cap so a long absence can't explode the price
    price = float(asset.get("price", asset.get("base_price", 1.0)))
    z = random.gauss(0.0, 1.0)
    factor = math.exp((drift - 0.5 * vol * vol) * dt_h + vol * math.sqrt(dt_h) * z)
    base = float(asset.get("base_price", price))
    new_price = max(base * 0.1, min(base * 12.0, price * factor))
    dp = 6 if new_price < 5 else 2
    asset["prev_price"] = price
    asset["price"] = round(new_price, dp)
    hist = asset.get("history") or []
    hist.append(asset["price"])
    asset["history"] = hist[-HISTORY_LEN:]
    asset["last_update"] = _now().isoformat()
    return True


async def get_market(db, cfg, kind):
    """Return the current list of assets of a kind, advancing prices first (persisted)."""
    assets = await db.market_assets.find({"kind": kind}, {"_id": 0}).to_list(100)
    assets.sort(key=lambda a: a.get("symbol", ""))
    out = []
    for a in assets:
        if _advance(a, cfg):
            await db.market_assets.update_one(
                {"id": a["id"]},
                {"$set": {"price": a["price"], "prev_price": a["prev_price"],
                          "history": a["history"], "last_update": a["last_update"]}})
        prev = a.get("prev_price", a["price"]) or a["price"]
        change = (a["price"] - prev) / prev if prev else 0.0
        day_change = 0.0
        hist = a.get("history") or []
        if len(hist) >= 2 and hist[0]:
            day_change = (a["price"] - hist[0]) / hist[0]
        out.append({
            "id": a["id"], "symbol": a["symbol"], "name": a["name"], "kind": a["kind"],
            "price": a["price"], "change": round(change, 4), "trend": round(day_change, 4),
            "history": hist, "desc": a.get("desc", ""),
        })
    return out


async def price_map(db):
    """asset_id -> current price (no advance), for valuing portfolios cheaply."""
    assets = await db.market_assets.find({}, {"_id": 0, "id": 1, "price": 1, "kind": 1, "symbol": 1, "name": 1}).to_list(100)
    return {a["id"]: a for a in assets}


async def force_advance(db, cfg):
    """Admin: advance every asset by a full one-hour step immediately (ignores the MIN_STEP gate)
    so tuning changes produce visible movement right away instead of waiting for real hours."""
    assets = await db.market_assets.find({}, {"_id": 0}).to_list(100)
    for a in assets:
        a["last_update"] = (_now() - timedelta(hours=1)).isoformat()  # backdate → full step
        _advance(a, cfg)
        await db.market_assets.update_one(
            {"id": a["id"]},
            {"$set": {"price": a["price"], "prev_price": a["prev_price"],
                      "history": a["history"], "last_update": a["last_update"]}})
    return len(assets)



async def portfolio_view(db, p):
    """Holdings with live valuation + P&L."""
    port = p.get("portfolio") or {}
    pm = await price_map(db)
    holdings = []
    total_value = 0.0
    total_cost = 0.0
    for aid, h in port.items():
        qty = h.get("qty", 0)
        if qty <= 0:
            continue
        a = pm.get(aid)
        if not a:
            continue
        price = a["price"]
        value = qty * price
        cost = qty * h.get("avg_cost", price)
        total_value += value
        total_cost += cost
        holdings.append({
            "id": aid, "symbol": a["symbol"], "name": a["name"], "kind": a["kind"],
            "qty": round(qty, 8), "avg_cost": round(h.get("avg_cost", price), 6),
            "price": price, "value": round(value, 2),
            "pnl": round(value - cost, 2), "pnl_pct": round((value - cost) / cost, 4) if cost else 0.0,
        })
    holdings.sort(key=lambda x: x["value"], reverse=True)
    return {
        "holdings": holdings,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_value - total_cost, 2),
    }


async def portfolio_value(db, p):
    return (await portfolio_view(db, p))["total_value"]
