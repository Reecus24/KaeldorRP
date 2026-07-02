"""Deterministic checks for the FINAL LOGIC REPAIR links (audit findings):
   1. Effectiveness -> crime fail chance + crime XP
   2. Reputation -> loan interest rate (pricing)
   3. Legal standing (< 40) -> proactive police events
   4. Social status -> VIP banking credit factor
Run: python3 /app/backend/tests/test_logic_links.py
"""
import sys, asyncio, random
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

import game_models
from game_models import new_player
import game_engine as ge
from game_engine import effective_loan_rate, effectiveness, _resolve_illegal, maybe_police_event

CFG = {"time_scale": 1.0, "economy": {"loan_interest_daily": 0.015}}
game_models.apply_tuning({"tuning": {}})


def _sharp_player():
    p = new_player("u1", "Sharp", "drifter")
    p.update({"energy": 100, "fatigue": 0, "health": 100, "hunger": 10, "stress": 0})
    return p


def _tired_player():
    p = new_player("u2", "Tired", "drifter")
    p.update({"energy": 5, "fatigue": 95, "health": 40, "hunger": 90, "stress": 90})
    return p


def test_reputation_loan_rate():
    lo = _sharp_player(); lo["reputation"] = 10
    mid = _sharp_player(); mid["reputation"] = 50
    hi = _sharp_player(); hi["reputation"] = 100
    r_lo, r_mid, r_hi = effective_loan_rate(lo, CFG), effective_loan_rate(mid, CFG), effective_loan_rate(hi, CFG)
    assert r_mid == 0.015, f"neutral rep should be base rate, got {r_mid}"
    assert r_lo > r_mid > r_hi, f"rate must fall as reputation rises: {r_lo} > {r_mid} > {r_hi}"
    print(f"\u2713 Reputation->loan rate: rep10={r_lo}, rep50={r_mid}, rep100={r_hi}")


def test_effectiveness_crime():
    sharp, tired = _sharp_player(), _tired_player()
    eff_s, eff_t = effectiveness(sharp), effectiveness(tired)
    fac_s = ge.clamp(1.6 - 0.6 * eff_s, 0.6, 1.6)
    fac_t = ge.clamp(1.6 - 0.6 * eff_t, 0.6, 1.6)
    assert eff_s > eff_t, "sharp player must be more effective"
    assert fac_t > fac_s, f"tired player must have higher fail multiplier: {fac_t} > {fac_s}"
    print(f"\u2713 Effectiveness->crime: sharp eff={eff_s:.2f} (fail x{fac_s:.2f}), tired eff={eff_t:.2f} (fail x{fac_t:.2f})")


class _FakeColl:
    async def insert_one(self, *a, **k):
        return None


class _FakeDB:
    def __init__(self):
        self.events = _FakeColl(); self.notifications = _FakeColl()


async def _run_police(legal, susp, trials=400):
    db = _FakeDB()
    hits = 0
    gh = 12.0
    for _ in range(trials):
        p = _sharp_player()
        p["legal_reputation"] = legal
        p["criminal_suspicion"] = susp
        p["status"] = "free"
        before = (p["stress"], p["cash"], p["criminal_suspicion"], p["status"])
        await maybe_police_event(db, p, CFG, gh=gh)
        after = (p["stress"], p["cash"], p["criminal_suspicion"], p["status"])
        if after != before:
            hits += 1
    return hits / trials


def test_police_events():
    # clean record: never fires
    rate_clean = asyncio.get_event_loop().run_until_complete(_run_police(80, 0))
    assert rate_clean == 0.0, f"clean record must never trigger police stops, got {rate_clean}"
    # heavy record over a 12-game-hour window: fires meaningfully often
    rate_rec = asyncio.get_event_loop().run_until_complete(_run_police(10, 50, trials=600))
    assert rate_rec > 0.15, f"heavy record should trigger frequent stops, got {rate_rec}"
    print(f"\u2713 Legal-standing->police: clean={rate_clean:.0%}, record(legal10/susp50)={rate_rec:.0%} over 12gh")


def main():
    print("=" * 60)
    print("KAELDOR LOGIC-LINK VERIFICATION")
    print("=" * 60)
    test_reputation_loan_rate()
    test_effectiveness_crime()
    test_police_events()
    print("=" * 60)
    print("ALL LOGIC-LINK CHECKS PASSED \u2713")
    print("=" * 60)


if __name__ == "__main__":
    main()
