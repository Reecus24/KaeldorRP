# Kaeldor Creative Enhancements (Lead Designer Phase)

Each enhancement follows the existing architecture (hourly wages, coverage-based supply chain,
stat linkage) and is verified against `/app/tests/verify_economy.py` (no business-economy regression).

## 1. Income Tax on Wages
- Real-life basis: progressive income tax withheld from paychecks.
- Implementation: `_tax_rate_for(gross)` in game_engine.py reads admin-tunable `tax_brackets`
  ([[100,0.10],[250,0.15],[null,0.22]]). Applied to each job shift's gross pay (wage+tips).
- Affected files: game_engine.py (job completion), game_models.py (LEDGER_KEYS "taxes"), Admin tuning.
- Balance: ~10–22% of shift pay; shown on Daily Summary as an expense and in the shift event.

## 2. Savings Interest
- Real-life basis: bank deposits earn interest.
- Implementation: in `accrue_recurring`, a debt-free `bank` balance earns
  `savings_interest_daily` (default 0.08%/day) pro-rated by elapsed game-hours. Ledger "savings_interest".
- Affected files: game_engine.py. Interconnects Bank + Daily Summary.
- Balance: tiny but positive; only when debt == 0 (pay debt first — realistic).

## 3. Skill Decay (use-it-or-lose-it)
- Real-life basis: unused skills atrophy.
- Implementation: `_decay_skills(p, gh)` gently removes XP from skills above level 2 while idle;
  working/training re-adds XP so active skills never degrade. A level can drop (retains partial XP).
- Affected files: game_engine.py. Encourages varied, active play.
- Balance: 0.35 xp/game-hour idle; negligible for active players.

## 4. Income Tax + Legal interconnection (foundation laid)
- The tax system is the hook for future tax-evasion → Criminal Suspicion. Brackets are admin-tunable now.

## Pre-existing realistic systems (verified present, documented for completeness)
These were already implemented and remain intact:
- **Utility bills & rent** per housing tier (`accrue_recurring`, bills_per_day).
- **Vehicle insurance, maintenance & wear** — vehicles carry insurance/maintenance costs and
  `condition` decays with time; affects value.
- **Loan interest & credit tracking** — debt accrues daily interest; repayment history tracked.
- **Hospital billing** — treatment costs money (config `hospital_treat_cost`).

## Balance / regression
`python3 /app/tests/verify_economy.py` passes after all enhancements (they touch player-side
cash flow, not the business `_day_rates` formulas).
