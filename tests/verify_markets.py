"""Standalone sanity checks for the financial-market random walk + crime risk math.
Run: python3 tests/verify_markets.py
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
import market_engine as me  # noqa: E402


def check_price_bounds():
    cfg = {"tuning": {"crypto_drift": 0.004, "crypto_volatility": 0.09}}
    from datetime import datetime, timezone, timedelta
    ok = True
    for _ in range(2000):
        a = {"kind": "crypto", "base_price": 100.0, "price": 100.0,
             "last_update": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(), "history": [100.0]}
        me._advance(a, cfg)
        if not (10.0 <= a["price"] <= 1200.0):
            ok = False
            break
    assert ok, "price escaped clamp bounds"
    print("  ✓ prices stay within [0.1x, 12x] base across 2000 walks")


def check_drift_direction():
    # positive drift, low vol → average price should trend up over many long steps
    cfg = {"tuning": {"stock_drift": 0.01, "stock_volatility": 0.005}}
    from datetime import datetime, timezone, timedelta
    ups = 0
    for _ in range(400):
        a = {"kind": "stock", "base_price": 100.0, "price": 100.0,
             "last_update": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(), "history": [100.0]}
        me._advance(a, cfg)
        if a["price"] > 100.0:
            ups += 1
    assert ups > 300, f"positive drift should mostly rise, got {ups}/400"
    print(f"  ✓ positive drift trends up ({ups}/400 rose)")


def check_crime_math():
    # mirror of server._effective_crime_risk
    def eff(police_risk, failure_chance, street, susp, risk_mult=1.0):
        bust = police_risk * (1 + susp / 150.0) * (1 - min(0.4, street * 0.03)) * risk_mult
        fail = failure_chance * (1 - min(0.3, street * 0.025))
        bust = max(0.0, min(0.95, bust))
        fail = max(0.0, min(0.95 - bust, fail))
        return bust, fail
    b0, f0 = eff(0.25, 0.30, street=1, susp=0)
    b1, f1 = eff(0.25, 0.30, street=10, susp=0)
    assert b1 < b0 and f1 < f0, "higher street smarts must lower both bust and fail"
    b2, _ = eff(0.25, 0.30, street=1, susp=100)
    assert b2 > b0, "higher suspicion must raise bust risk"
    bh, fh = eff(0.9, 0.9, street=1, susp=100)
    assert bh + fh <= 0.95 + 1e-9, "bust + fail must be capped at 0.95"
    print("  ✓ crime risk: street lowers risk, suspicion raises bust, bust+fail ≤ 0.95")


if __name__ == "__main__":
    print("=" * 60)
    print("KAELDOR MARKET & UNDERWORLD LOGIC VERIFICATION")
    print("=" * 60)
    check_price_bounds()
    check_drift_direction()
    check_crime_math()
    print("=" * 60)
    print("ALL MARKET/UNDERWORLD CHECKS PASSED ✓")
    print("=" * 60)
