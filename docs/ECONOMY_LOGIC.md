# Kaeldor Economy Logic — Source of Truth

This document defines the ONLY valid formulas the business engine may use. Any code that
computes wages, production, or profit MUST route through the canonical functions in
`employee_engine.py` (`calculate_worker_daily_wage`, `calculate_total_covered_hours`).
Do not introduce alternate wage/production paths.

## Wage Calculation (ONLY valid formula)
```
daily_wage_cost_per_worker = hourly_wage * scheduled_shift_hours
total_daily_wages = SUM(each_worker.hourly_wage * each_worker.shift_hours)
```

### Rules:
- A worker who is OFF-SHIFT costs exactly $0.
- A worker with NO schedule costs exactly $0.
- A worker is ONLY paid for hours within their assigned shift block (clipped to opening hours).
- There is NO flat daily wage. There is NO 24h assumption. There is NO "backup_wage_day".
- `daily_wage` may only exist as a stored NPC generation attribute; it is NEVER used to charge a business.

## Revenue / Production Calculation (ONLY valid formula)
```
units_produced_per_hour = production_per_worker_hour (pph)
total_daily_production = pph * effective_worker_hours * satisfaction_mult   (* level multiplier)
effective_worker_hours = SUM over opening hours of MIN(active_workers_that_hour, staff_slots)
daily_revenue = min(total_daily_production, daily_demand) * sale_price
```

### Rules:
- Production scales with WORKER-HOURS, capped per hour by `staff_slots` (= base_slots + level - 1).
- 1 worker over a 12h opening = 12 effective worker-hours.
- 2 workers on a 2-slot business, both 08:00-20:00 (concurrent) = 24 worker-hours → **2x output** (additive).
- 2 workers doing 6h each (non-overlapping) = 12 worker-hours (full time coverage, single-worker output).
- On a 1-slot business, 2 overlapping workers are capped at 1 concurrent → 12 worker-hours (NOT doubled),
  and the shift planner rejects the overlap anyway.
- Uncovered hours within the opening window = 0 production.
- `covered_hours` (UNION of shifts) is reported separately for the coverage% display only.

## Real-time clock
- `time_scale = 1.0` → **1 in-game hour = 1 real-world hour**.
- The world clock is hard-synced to German local time (Europe/Berlin, CEST/UTC+2 in summer, DST-aware).
- All time-based systems (shift resolution, revenue accrual, skill decay, upgrade/marketing timers,
  suspicion decay) integrate over elapsed game-hours, so they run correctly at this 1:1 pace.

## Overlap Constraint
```
max_simultaneous_workers_at_any_hour <= business.staff_slots   (staff_slots = base_slots + level - 1)
```
- The shift planner MUST reject any assignment where workers_at_hour > slots.

## Net Profit Formula
```
net_profit_per_day = daily_revenue - material_costs - total_daily_wages
material_costs = units_sold * material_cost_per_unit
```

## Example: Kiosk (12h open, 08:00-20:00, pph=10, price=$12, materials=$6.50)
NOTE: The live seed uses a rebalanced pph (5.5) so a Level-1 kiosk nets ~$220/day. The
examples below use pph=10 purely to illustrate the FORMULAS; the shape (A == B, C == half of A)
is what matters and is enforced by the engine regardless of the pph value.

### Scenario A: 1 worker, full 12h shift, $10/hr
- Production: 10 * 12 = 120 units
- Revenue: 120 * $12 = $1,440
- Materials: 120 * $6.50 = $780
- Wages: $10 * 12h = $120
- NET: $1,440 - $780 - $120 = **$540/day**

### Scenario B: 2 workers, 6h each (split shift), $10/hr
- Production: 10 * (6+6) = 120 units (same as A — full coverage)
- Revenue: 120 * $12 = $1,440
- Materials: 120 * $6.50 = $780
- Wages: ($10*6) + ($10*6) = $120
- NET: **$540/day** (identical to A)

### Scenario C: 1 worker, only 6h shift, $10/hr
- Production: 10 * 6 = 60 units
- Revenue: 60 * $12 = $720
- Materials: 60 * $6.50 = $390
- Wages: $10 * 6h = $60
- NET: **$270/day** (half coverage = half profit)

## 00:00 Daily Deduction Cycle & Ledger Refactor (2026-07-01)
**Timing change.** Fixed **RENT** and **VEHICLE costs** (fuel + insurance + maintenance) are NO LONGER
prorated hourly. They are now charged as a single lump **once per day at the 00:00 game-day boundary**
via `game_engine._charge_daily_fixed(db, p, cfg, days, housing_doc)`, invoked from `resolve_player`
right before the daily summary flush. `days = cur_day - last_day`, so N offline days charge N× rent +
N× vehicle in one pass.

**Still hourly (continuous flows) in `accrue_recurring`:** utility **bills**, **loan interest**,
**savings interest**, skill decay, and vehicle **condition wear** (wear is physical, not a cash cost).

**Boundary = in-game 00:00.** The cycle fires at the game clock's midnight (`game_day_index`, anchored to
`world_start_game`). At `time_scale=1` (1 game hour = 1 real hour) this tracks real time; align
`world_start_game` to a CEST-midnight anchor if you need 00:00 to coincide with real CEST.

**Concurrency-safe.** The boundary is claimed atomically:
`players.update_one({id, last_summary_day: last_day}, {$set:{last_summary_day: cur_day}})`. Only the
resolver whose `modified_count == 1` charges rent/vehicle and writes the summary, so concurrent
`/api/game/state` polls can never double-charge or create duplicate summaries.

**Daily Summary (the Ledger).** `_flush_daily_summary` writes one `daily_summaries` doc per boundary:
- Income buckets summed: `wages_earned` (Total Wages) + `business_income` (Business Dividends/Profits,
  logged on `POST /businesses/{id}/collect`) + `crime_income` + `social_income` + `savings_interest`.
- Expense buckets summed: `rent` + `bills` (Utilities) + `vehicle_costs` + `living_costs` (Social
  Spending) + `fines` + `medical` + `taxes` + `loan_interest`.
- `events`: up to 25 significant events (severity success/warning/danger, or type job/legal/crime/social/
  housing/health/business/finance) pulled from the `events` collection for the covered window — powers
  the UI "Event Log".
- New ledger key `business_income` added to `game_models.LEDGER_KEYS`.

**Verified.** Unit checks: mid-day resolve charges NO rent/vehicle (only bills); 00:00 charges rent+vehicle
once; owned home skips rent; 3 offline days = 3× costs; full `resolve_player` crossing writes a summary
with correct income/expense totals, net cash, and event log. `verify_economy.py` + `verify_markets.py` pass.

## Standardized 4-Shift System + Registration & Auto-Start (2026-07-02)

Player jobs (NPC employers) use a fixed-start shift model. Each `job.shift_options` entry is:
`{id, name, start_hour, duration_hours, start_window:{min_hour,max_hour}, injury_risk, pay_multiplier, xp_multiplier}`.
`start_window` is derived (min_hour=start_hour, max_hour=(start_hour+duration)%24) for display only.

**Standard shifts (same clock across every job):**
| Shift        | Start | End   | Hours |
|--------------|-------|-------|-------|
| Early Shift  | 08:00 | 13:00 | 5     |
| Late Shift   | 13:00 | 18:00 | 5     |
| Full Shift   | 08:00 | 18:00 | 10    |
| Night Shift  | 22:00 | 08:00 | 10 (wraps midnight) |

Night pays ×1.45 / XP ×1.20 with ~2× injury risk. Night is included for all jobs by default except
pure office desk jobs (`office_assistant`, `store_manager`). Admins can add/edit/remove shifts and toggle
Night per-job via Admin ▸ Gameplay Tuning ▸ Job Shifts (`PUT /admin/job-shifts/{job_id}`).

**Registration (sign-up before start).** Players cannot start a shift on demand. They call
`POST /jobs/register-shift {shift_id}` which stores `player.registered_shift` with the computed
`start_real` (the real UTC datetime at which the game clock next reaches `start_hour`). If the start
hour has already passed today, the next occurrence is tomorrow. Only ONE registration at a time;
`POST /jobs/cancel-shift` clears it. The button is only offered before the start time — you can never
join a shift after it has begun.

**Auto-Start.** `game_engine.maybe_autostart_shift` runs inside `resolve_player` on every heartbeat.
When `now >= start_real` it consumes the registration and:
- If the player is confined (jail/hospital), already has a `current_activity`, or is on a player-business
  shift → the shift is MISSED (no auto-start), a warning event/notification fires, and reliability −5.
- If energy < 10 → MISSED, reliability −4.
- Otherwise the work activity auto-starts with `started_at = start_real` (retroactive, so an offline
  catch-up correctly completes and pays out the shift). Reliability/pay/XP resolve as before.

`/jobs/work` is kept as a backward-compatible alias that now registers instead of instant-starting.

## Vehicle Maintenance now affects Condition (2026-07-02)

Previously the 00:00 `maintenance_per_day` fee was a pure cash sink with no effect on condition (audit
Point 3). Now maintenance is meaningful:
- At the 00:00 daily charge (`_charge_daily_fixed`), if the combined rent+vehicle bill is covered without
  slipping into debt, every vehicle is flagged `maintained = True` for the next 24h; if the player can't
  pay (bill pushes into debt), vehicles are flagged `maintained = False`.
- Continuous wear (`accrue_recurring`) now reads that flag:
  - **Maintained:** `vehicle_decay_maintained` = 0.05 condition/game-hour (≈1.2/day — nearly stable).
  - **Unmaintained:** `vehicle_decay_unmaintained` = 0.6 condition/game-hour (≈14/day — accelerated).
  Both rates are overridable via `config.economy.vehicle_decay_maintained/_unmaintained`.
- Unknown/legacy vehicles default to `maintained=True` (grace) until the next midnight sets the real flag.
- Condition is still hard-reset to 100 only by the explicit `repairs_vehicle` activity; maintenance just
  keeps a paid-for vehicle from degrading. Skipping payment (or being broke) visibly rots the car.
