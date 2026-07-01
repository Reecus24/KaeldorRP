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
total_daily_production = pph * total_covered_hours * satisfaction_mult   (* level multiplier)
total_covered_hours = UNION of all workers' shift durations (clipped to & capped at opening_hours)
daily_revenue = min(total_daily_production, daily_demand) * sale_price
```

### Rules:
- Production ONLY happens during hours where at least 1 worker is on-shift.
- If 2 workers cover 6h each (non-overlapping), total_covered_hours = 12h.
- If 2 workers overlap for 4h on a 1-slot business, production during overlap = pph * 1 (not doubled).
  (Enforced by using the UNION of shift intervals, not the sum.)
- Uncovered hours within opening window = 0 production.
- The per-tick offline resolver charges/produces the time-integral of these daily rates over the
  elapsed game-window; over a full day it equals the formulas above exactly.

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
