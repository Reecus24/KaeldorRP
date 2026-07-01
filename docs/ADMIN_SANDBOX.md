# Kaeldor Admin Sandbox — Source of Truth

Full live control of the simulation without code changes. Admin-only (`admin_user` dependency,
seeded admin = `admin@kaeldor.com`). All tunables live in the `config` collection (`id:"global"`)
under `economy`, `social`, `time_scale`, and the `tuning` block. The engine reads these every tick
via `game_engine.get_config()` → `game_models.apply_tuning(cfg)` → `game_models.TUNE`.

## Storage / Schema
`config/global.tuning`:
| Key | Default | Controls |
|-----|---------|----------|
| upgrade_days | 7 | In-game days a business upgrade takes |
| marketing_days | 3 | In-game days a marketing campaign runs |
| raise_cooldown_days | 7 | Min in-game days between NPC wage-raise requests |
| satisfaction_mult_min / _max | 0.85 / 1.0 | Satisfaction → production multiplier range |
| reputation_mult_min / _max | 0.5 / 1.0 | Business reputation → demand multiplier range |
| worker_cond_min / _max | 0.85 / 1.05 | Worker condition (effectiveness → productivity) range |
| accident_eff_threshold | 0.55 | Below this effectiveness, work-injury risk applies |
| accident_chance | 0.30 | Injury chance per shift below the threshold |
| tax_brackets | [[100,0.10],[250,0.15],[null,0.22]] | Progressive income tax on job gross pay |

Business economics live on `business_types` (and are propagated onto each `businesses` doc):
`product.price`, `material_cost_override`, `daily_demand`, `production_per_worker_hour`,
`base_hourly_wage`, `opening_hours`.

## API (admin-only)
- `GET /api/admin/config` — full config doc (incl. `tuning`).
- `PUT /api/admin/config` — shallow-merges the body into config (send `{tuning:{...}}` or `{time_scale:n}`).
- `GET /api/admin/business-economy` — per-type economy rows.
- `PUT /api/admin/business-economy/{type_id}` — body: price, material_cost, daily_demand,
  production_per_worker_hour, base_hourly_wage, opening_open, opening_close, apply_existing(bool).
  When `apply_existing` is true, changes propagate to every existing business of that type.
- `GET /api/admin/players` — all players + key stats.
- `PUT /api/admin/players/{player_id}` — adjust cash, bank, debt, reputation, legal_reputation,
  criminal_suspicion, social_status, health, energy, skills{id:level}.

## Admin UI (`/admin`)
- **Economy Sandbox** — editable grid for all 10 businesses (price, material $, demand, PPH,
  base $/hr, open–close) + "Apply to existing" toggle.
- **Tuning** — timers, multiplier ranges, effectiveness→accidents, income-tax brackets.
- **Players** — table with inline Edit modal for cash/stats/skills.
- **Config** — time-scale + full JSON editor (advanced).
- **Content tabs** — CRUD for jobs, actions, courses, items, housing, vehicles, businesses, etc.

## Live update
Saves write to Mongo immediately. The offline resolver / metrics call `get_config()` on every
request, which refreshes `TUNE`, so new values take effect on the next tick with NO restart.
`apply_existing` also mutates existing `businesses` docs so live ventures immediately reflect the
new economics.
