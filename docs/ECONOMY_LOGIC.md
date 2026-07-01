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
