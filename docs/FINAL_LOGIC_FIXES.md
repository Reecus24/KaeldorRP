# Final Logic Repair — Linking Audit Findings (2026-07-02)

This closes the loop on stats that were tracked but not fully wired into outcomes. All UI text and
code strings remain English. Admin-tunable knobs live in `game_models.DEFAULT_CONFIG["tuning"]`.

## 1. Effectiveness → Crime
- **Where:** `game_engine._resolve_illegal` (resolution) + `core._effective_crime_risk` (UI odds mirror).
- **What:** the player's live `effectiveness()` (energy/fatigue/health/hunger/stress) now scales the
  illegal-job **failure chance** via `fail *= clamp(1.6 - 0.6*eff, 0.6, 1.6)` — a sharp operator (eff≈1.0)
  flops less, a tired/hungry one (eff≈0.3) flops ~40% more. Crime **skill XP** is also scaled by `eff`
  (`xp * eff`), so a botched, distracted job teaches you less. Bust (police) risk is unchanged (driven
  by police_risk, suspicion and street_smarts). The Underworld crime cards show the true live odds.

## 2. Reputation → Bank loan pricing + high-tier job gates
- **Loan pricing:** new `game_engine.effective_loan_rate(p, cfg)` prices the daily interest by reputation:
  `base * clamp(1.0 - (rep-50)/125, 0.7, 1.4)`. Reputation 50 = base rate; rep 100 ≈ −30%; rep 0 ≈ +40%.
  Used both when charging interest (`accrue_recurring`) and in the Bank UI (`credit_profile.interest_daily`).
- **Job gates:** `min_reputation` added to the manager tier (store_manager 60, restaurant_manager 55,
  logistics_manager 60). `core.meets_requirements` already enforced `min_reputation`; the seed values are
  synced to existing DBs by `migrate_business_supply_chain` on startup.

## 3. Legal Standing → Proactive police events
- **Where:** new `game_engine.maybe_police_event`, called each resolve.
- **What:** with a criminal record (`legal_reputation < 40`) the player is randomly stopped by police.
  Per-game-hour chance = `TUNE["police_event_per_hour"] (0.03) * (40 - legal)/40`, integrated over
  elapsed game-hours. Only fires while free (not confined / mid-activity / on shift).
  Outcomes escalate with suspicion:
  - `susp ≥ 60 & legal < 20` (35%): short detention (2h game-time), +suspicion, −legal.
  - `susp ≥ 40` (50%): stop-and-search citation (fine ≈ $50 + susp×2), suspicion cools a little.
  - else: warning only, minor suspicion cool-down. Always +8 stress.

## 4. Social Status → VIP banking (+ existing job gates)
- **Banking:** `core.credit_profile` adds a `social_c = max(0, social-10) * 20` term to the credit limit
  (connections raise your ceiling) and returns a `vip` flag (`social_status ≥ 60`) plus `factors.social_standing`.
- **Jobs:** `min_social_status` already gates the manager tier via `meets_requirements` (unchanged).

## Verification
- `python3 /app/backend/tests/test_logic_links.py` — reputation loan pricing, effectiveness→crime factor,
  legal→police frequency (clean record never fires; heavy record fires ~25% over 12 game-hours).
- `python3 /app/tests/verify_economy.py` + `verify_markets.py` — still green (no economy regression).
