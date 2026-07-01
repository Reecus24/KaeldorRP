"""
Kaeldor Economy Verification Script
Asserts that wage and revenue logic strictly follows /app/docs/ECONOMY_LOGIC.md
"""
import sys
sys.path.insert(0, '/app/backend')

# Import the actual calculation functions from the engine
from employee_engine import calculate_worker_daily_wage, calculate_total_covered_hours


def test_wage_calculation():
    """Worker at $30/hr for 6 hours MUST cost exactly $180."""
    worker = {
        "hourly_wage": 30.0,
        "schedule": {"start": 8, "end": 14}  # 6 hours
    }
    cost = calculate_worker_daily_wage(worker)
    assert cost == 180.0, f"FAIL: Expected $180, got ${cost}. Wage leak detected!"
    print(f"\u2713 Wage test PASSED: $30/hr \u00d7 6h = ${cost}")


def test_no_schedule_costs_zero():
    """Worker with no schedule MUST cost $0."""
    worker = {"hourly_wage": 30.0, "schedule": None}
    cost = calculate_worker_daily_wage(worker)
    assert cost == 0.0, f"FAIL: Expected $0, got ${cost}. Off-shift worker being charged!"
    print(f"\u2713 No-schedule test PASSED: cost = ${cost}")


def test_off_shift_costs_zero():
    """Worker with empty/zero schedule MUST cost $0."""
    worker = {"hourly_wage": 30.0, "schedule": {"start": 8, "end": 8}}
    cost = calculate_worker_daily_wage(worker)
    assert cost == 0.0, f"FAIL: Expected $0, got ${cost}"
    print(f"\u2713 Zero-hour shift test PASSED: cost = ${cost}")


def test_coverage_hours():
    """Two workers with 6h each = 12h total covered."""
    employees = [
        {"schedule": {"start": 8, "end": 14}},
        {"schedule": {"start": 14, "end": 20}},
    ]
    opening = {"open": 8, "close": 20}
    covered = calculate_total_covered_hours(employees, opening)
    assert covered == 12.0, f"FAIL: Expected 12h, got {covered}h"
    print(f"\u2713 Coverage test PASSED: 6h + 6h = {covered}h covered")


def test_coverage_capped_at_opening():
    """Coverage cannot exceed opening hours even with overlapping shifts."""
    employees = [
        {"schedule": {"start": 8, "end": 20}},
        {"schedule": {"start": 8, "end": 20}},
    ]
    opening = {"open": 8, "close": 20}
    covered = calculate_total_covered_hours(employees, opening)
    assert covered == 12.0, f"FAIL: Expected 12h (capped), got {covered}h"
    print(f"\u2713 Coverage cap test PASSED: overlapping 12h + 12h capped at {covered}h")


def test_overlap_not_doubled():
    """Two workers overlapping 4h (08-12) on a shared window = 4h covered (union, not 8h)."""
    employees = [
        {"schedule": {"start": 8, "end": 12}},
        {"schedule": {"start": 8, "end": 12}},
    ]
    opening = {"open": 8, "close": 20}
    covered = calculate_total_covered_hours(employees, opening)
    assert covered == 4.0, f"FAIL: Expected 4h (union, overlap not doubled), got {covered}h"
    print(f"\u2713 Overlap-union test PASSED: 08-12 + 08-12 = {covered}h (not doubled)")


def test_full_pnl_scenario():
    """Kiosk: 12h open, 1 worker 12h @ $10/hr, pph=10, price=$12, mat=$6.50"""
    pph = 10
    covered_hours = 12
    price = 12.0
    material_cost = 6.5
    hourly_wage = 10.0
    shift_hours = 12

    production = pph * covered_hours  # 120 units
    revenue = production * price       # $1440
    materials = production * material_cost  # $780
    wages = hourly_wage * shift_hours  # $120
    net = revenue - materials - wages  # $540

    assert production == 120, f"FAIL: production={production}"
    assert revenue == 1440.0, f"FAIL: revenue={revenue}"
    assert materials == 780.0, f"FAIL: materials={materials}"
    assert wages == 120.0, f"FAIL: wages={wages}"
    assert net == 540.0, f"FAIL: net={net}"
    print(f"\u2713 Full P&L test PASSED: Revenue ${revenue} - Materials ${materials} - Wages ${wages} = NET ${net}")


def test_engine_pnl_matches_formula():
    """The ACTUAL engine _day_rates must equal the source-of-truth formula for a synthetic kiosk."""
    import employee_engine as ee
    b = {
        "production_per_worker_hour": 10.0, "daily_demand": 999,
        "product": {"price": 12.0},
        "recipe": [{"id": "a", "qty": 1, "cost": 6.5}],
        "opening_hours": {"open": "08:00", "close": "20:00"},
        "level": 1, "marketing_level": 0, "reputation": 100.0, "satisfaction": 100.0,
    }
    workers = [{"schedule": {"start": 8, "end": 14}, "wage_per_hour": 10.0, "productivity": 1.0},
               {"schedule": {"start": 14, "end": 20}, "wage_per_hour": 10.0, "productivity": 1.0}]
    r = ee._day_rates(b, workers)
    # rep 100 -> demand mult 1.0, sat 100 -> mult 1.0, level 1
    assert r["covered_hours"] == 12.0, f"FAIL covered={r['covered_hours']}"
    assert r["sold_day"] == 120.0, f"FAIL sold={r['sold_day']}"
    assert r["rev_day"] == 1440.0, f"FAIL rev={r['rev_day']}"
    assert r["material_day"] == 780.0, f"FAIL mat={r['material_day']}"
    assert r["wages_day"] == 120.0, f"FAIL wages={r['wages_day']}"
    assert r["net_day"] == 540.0, f"FAIL net={r['net_day']}"
    print(f"\u2713 Engine _day_rates test PASSED: covered {r['covered_hours']}h, NET ${r['net_day']} (matches doc Scenario A/B)")


def test_engine_worker_scaling():
    """Two CONCURRENT workers on a 2-slot business must produce ~2x a single worker (additive)."""
    import employee_engine as ee
    b = {
        "production_per_worker_hour": 10.0, "daily_demand": 99999,
        "product": {"price": 12.0},
        "recipe": [{"id": "a", "qty": 1, "cost": 6.5}],
        "opening_hours": {"open": "08:00", "close": "20:00"},
        "level": 1, "marketing_level": 0, "reputation": 100.0, "satisfaction": 100.0,
    }
    one = [{"schedule": {"start": 8, "end": 20}, "wage_per_hour": 10.0, "productivity": 1.0}]
    two = [{"schedule": {"start": 8, "end": 20}, "wage_per_hour": 10.0, "productivity": 1.0},
           {"schedule": {"start": 8, "end": 20}, "wage_per_hour": 10.0, "productivity": 1.0}]
    r1 = ee._day_rates(b, one, slots=2)
    r2 = ee._day_rates(b, two, slots=2)
    assert r1["worker_hours"] == 12.0, f"FAIL 1-worker hours={r1['worker_hours']}"
    assert r2["worker_hours"] == 24.0, f"FAIL 2-worker hours={r2['worker_hours']}"
    assert abs(r2["sold_day"] - 2 * r1["sold_day"]) < 0.1, f"FAIL not additive: {r1['sold_day']} vs {r2['sold_day']}"
    print(f"\u2713 Worker-scaling test PASSED: 1 worker -> {r1['sold_day']} units, 2 concurrent workers -> {r2['sold_day']} units (2x)")


def test_one_slot_no_double():
    """On a 1-slot business, two overlapping workers do NOT double output (capped at 1 concurrent)."""
    import employee_engine as ee
    b = {"production_per_worker_hour": 10.0, "daily_demand": 99999, "product": {"price": 12.0},
         "recipe": [{"id": "a", "qty": 1, "cost": 6.5}], "opening_hours": {"open": "08:00", "close": "20:00"},
         "level": 1, "marketing_level": 0, "reputation": 100.0, "satisfaction": 100.0}
    two = [{"schedule": {"start": 8, "end": 20}, "wage_per_hour": 10.0, "productivity": 1.0},
           {"schedule": {"start": 8, "end": 20}, "wage_per_hour": 10.0, "productivity": 1.0}]
    r = ee._day_rates(b, two, slots=1)
    assert r["worker_hours"] == 12.0, f"FAIL 1-slot overlap hours={r['worker_hours']}"
    print(f"\u2713 1-slot cap test PASSED: 2 overlapping workers on 1 slot -> {r['worker_hours']} worker-hours (not doubled)")


if __name__ == "__main__":
    print("=" * 60)
    print("KAELDOR ECONOMY VERIFICATION")
    print("=" * 60)
    test_wage_calculation()
    test_no_schedule_costs_zero()
    test_off_shift_costs_zero()
    test_coverage_hours()
    test_coverage_capped_at_opening()
    test_overlap_not_doubled()
    test_full_pnl_scenario()
    test_engine_pnl_matches_formula()
    test_engine_worker_scaling()
    test_one_slot_no_double()
    print("=" * 60)
    print("ALL TESTS PASSED \u2713 \u2014 Economy logic is correct.")
    print("=" * 60)
