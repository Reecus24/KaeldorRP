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

## City Shops — Opening Hours, Stock & Discounts (2026-07-01)
- **City Shops** tab manages the stores players browse in the Shop. Per shop: name, item Category
  (shop sells only items of that category), optional business-type/location link, order, active.
- **Opening Hours** (`opening_hours {open, close}`, HH:MM; use `24:00` for round-the-clock): players
  can only BUY while OPEN (browsing allowed when closed). `is_open_now` computed via
  `employment.is_open_now`.
- **Stock & Discounts** (`items_config {item_id: {capacity, discount_pct}}`): per-item daily stock
  capacity + optional manual discount (0–95%). Effective price = base × (1 − discount/100).
- **Midnight refresh**: stock restocks to capacity at game midnight (00:00). Implemented lazily via
  `_resolve_shop_stock` keyed on `game_day_index`; editing a shop forces a refresh (`last_refresh_day=-1`).
- Endpoints: GET `/shop/stores`, GET `/shop/stores/{id}/items`, POST `/shop/buy` (validates open + stock,
  charges discounted price, decrements stock); admin GET/POST/PUT/DELETE `/admin/city-shops`.
- Migration `migrate_city_shops()` backfills opening_hours/items_config onto pre-existing shops.

## Job Sectors (Job Center reorganization) (2026-07-01)
- **Job Sectors** tab manages the sectors/agencies players browse in the Job Center (mirrors City Shops).
- Per sector: name, `desc`, `icon` (Briefcase/ShoppingBag/UtensilsCrossed/Truck/Building2/Wrench/Shield/Landmark),
  `order`, `active`, and `job_ids` (assign existing jobs via a checkbox picker; picker shows which sector a
  job is already in to avoid accidental double-assignment).
- Seeded 7 sectors: Retail & Sales, Food & Hospitality, Logistics & Transport, Corporate & Office,
  Trades & Manual Labor, Military & Defense, Public Services (cover all seed + army/police/garbage jobs).
- Player endpoints: GET `/jobs/sectors` (adds `job_count`, `open_count`=qualified), GET `/jobs/sectors/{id}`
  (filtered jobs with `qualified`/`reason`). A virtual `unassigned` "General Listings" sector is surfaced
  ONLY if some job isn't assigned to any active sector, so no job is ever unreachable.
- Admin CRUD: GET/POST/PUT/DELETE `/admin/job-sectors`. Migration `migrate_job_sectors()` inserts missing
  seed sectors by id into existing DBs.

## Admin Dashboard Overhaul — grouped nav + customizable layout (2026-07-01)
The flat ~27-tab bar is now organised into **6 Main Tab groups**, each with its own sub-tabs and a
**Dashboard Summary** metrics strip:
- **Overview** — Dashboard (StatsView). Summary: Players, Employed, Businesses, Active Workers, Market Value, Total Debt.
- **Economy** — Economy Sandbox, Businesses, Items, Housing, Vehicles.
- **Gameplay Tuning** — Tuning, Config, Actions, Courses, Jobs, Events.
- **Player Management** — Players, Emp Roles/Traits, Staffing, Training, Staff Events, NPC Archetypes, Personality, Rel. Actions, Gifts, Social Events.
- **City Infrastructure** — City Shops, Job Sectors, Locations.
- **Underworld & Finance** — Illegal actions.

### Metrics endpoint
`GET /api/admin/overview` returns city-wide counters (players, employed, businesses, hiring, active
workers = NPC + player employees, market value = Σ net_worth, cash/bank/debt totals, avg net worth,
avg suspicion, and content counts). Each group's summary strip renders a relevant subset; large money
is shown compact (e.g. `$3.77M`).

### How an admin customizes the layout
1. Click **Customize** (top-right of the tab row). Drag handles appear on each main tab and a panel
   opens with show/hide toggles.
2. **Reorder**: drag a main tab by its ⋮⋮ handle to a new position (powered by @dnd-kit).
3. **Show/Hide**: click a toggle in the customize panel to hide/show a group. *Overview cannot be hidden.*
4. **Reset**: click **Reset** to restore the default order and show all groups.
5. Click **Done** to exit customize mode.

The layout (order + hidden list) is **saved per admin account** in the backend via
`PUT /api/admin/layout` (stored on `users.admin_layout`) and reloaded on next visit via
`GET /api/admin/layout`, so it follows the admin across devices/sessions.

## Live City Feed (Overview tab) (2026-07-01)
- **Overview ▸ Live Feed** sub-tab shows a real-time, city-wide activity ticker aggregated from the
  `events` collection across ALL players (purchases, job applications/hirings, crimes & legal, finance/
  market moves, social, health, housing, vehicles, education).
- Endpoint `GET /api/admin/feed?limit=50&types=shop,crime` — most recent events (sorted by `ts` desc,
  capped 100), each enriched with `player_name`. Optional `types` CSV filter.
- UI: pulsing "LIVE · auto-refresh 6s" indicator (polls every 6s), category filter chips
  (All / Purchases / Work & Hiring / Crime & Legal / Finance / Social), colored per-type icons and
  relative timestamps. Read-only — a monitoring view for the Game Master.

## Live Feed — Game Master enhancements (2026-07-01)
- **Actionable player links**: every player name in the Live Feed is a clickable button
  (`data-testid feed-player-<playerId>`). Clicking it jumps to **Player Management ▸ Players**,
  pre-fills the search with that player's name, highlights their row and auto-opens the Edit modal
  for immediate action (edit cash/bank/debt/reputation/suspicion/health…).
- **Player search**: the Players table now has a name search box (`player-search`) with a result count.
- **Danger highlighting**: events with `severity == "danger"` (arrests, hospitalization, collapse,
  bankruptcy, etc.) render with a red **Danger Red `#FF4444`** pulsing border/glow (`.danger-pulse`
  keyframe in index.css), a red AlertTriangle icon and a "DANGER" pill, so critical incidents stand
  out from standard events at a glance.

## Skill Decay Rate tuning (2026-07-01)
- **Admin ▸ Gameplay Tuning ▸ Tuning** now has a **"Player Progression ▸ Skill Decay Rate"** field
  bound to `tuning.skill_decay_per_hour` (XP lost per idle game-hour for skills above L2).
- **0 disables** skill decay entirely. Saving via the Tuning panel writes to `game_config.tuning` and
  the engine reads it live from `TUNE` on the next resolve — no restart needed.
- Note: `GET /admin/config` now returns the full effective `tuning` (defaults merged), so newly added
  tuning knobs always appear in the UI even for older config documents.

## Criminal Suspicion tuning (2026-07-01)
- **Admin ▸ Gameplay Tuning ▸ Tuning ▸ Criminal Suspicion** adds two fields:
  - **Suspicion Decay Rate** (`tuning.suspicion_decay_per_hour`, default 1.5): suspicion lost per clean
    game-hour. **0 = suspicion never cools down.** Applied in `game_engine.decay_needs`.
  - **Suspicion Gain Multiplier** (`tuning.suspicion_gain_mult`, default 1.0): multiplies the suspicion
    gained from illegal acts (bust/fail/success) in `game_engine._resolve_illegal`.
- Changes persist to `game_config.tuning` and apply live from `TUNE` on the next resolve tick.

## Financial Markets — refresh cadence & management (2026-07-01)
**How often prices refresh.** Stock & crypto prices follow a **lazy, real-time geometric random walk**
(`market_engine`). Prices advance whenever the market is read, in proportion to the **real hours
elapsed** since each asset's `last_update` (throttled to a 36-second minimum step). They do NOT wait for
the 24h day rollover — but because per-minute movement is tiny at default volatility, changes look
gradual over minutes and only become large over hours.

**Why Sandbox tuning "looked" like it had no effect.** The drift/volatility knobs
(`stock_drift`, `stock_volatility`, `crypto_drift`, `crypto_volatility` in Gameplay Tuning ▸ Tuning) ARE
correctly persisted to `game_config` and consumed by the engine — verified: volatility 0.5 moved prices
30–1000% in one step. The confusion was that a full step only materialises after real time passes, so a
tester editing a value and refreshing within seconds saw almost no change.

**New: Admin ▸ Underworld & Finance ▸ Markets panel.**
- Shows every live asset (symbol, name, current price, base-price anchor) grouped into Stocks / Crypto,
  plus the active drift/volatility values.
- **Set** — directly overwrite an asset's live `price` and/or `base_price` (the random-walk anchor and the
  ±band centre). `PUT /api/admin/market/{asset_id}`.
- **Re-roll Now** — force an immediate full one-hour price step on all assets so tuning changes are
  visible instantly instead of waiting for real hours. `POST /api/admin/market/refresh`.
- These edits hit the same `market_assets` collection the player market reads, so changes are live
  immediately (verified: admin set KAEL→250, player market showed ~250).

## Action Card gains display (2026-07-01)
Home & Needs action cards now render BOTH stat effects (`effects`) and skill gains (`skill_xp`, shown as
cyan "+N Skill XP" chips) via `ActionCard.jsx`, so players see exactly what each action improves
(e.g. Gym Workout → +16 Fitness XP). Data already existed on the action docs; it was simply not rendered.

## Job Applications — Hiring Difficulty & Responses (2026-07-02)

Admin ▸ Gameplay Tuning ▸ **Applications** tunes how hard each job is to get and the roleplay messages
players see. Every job stores four DB fields (backfilled with defaults on existing jobs):

| Field                   | Type          | Meaning |
|-------------------------|---------------|---------|
| `acceptance_base_chance`| float 0.0–1.0 | Baseline hire probability BEFORE stat modifiers. Higher = easier to get hired. Default `0.5`. |
| `skill_weight`          | float 0.0–10.0| Multiplier on how much the candidate's skill-above-requirement raises the hire chance. Default `1.0`. |
| `success_response`      | string        | Message shown when the application is ACCEPTED. |
| `failure_response`      | string        | Message shown when the application is REJECTED. |

**How the hire chance is computed** (`employment.evaluate_application`):
```
score = clamp(acceptance_base_chance
              + skill_bonus * skill_weight
              + edu_bonus + rep_bonus*1.5 + reliability_bonus*2 + reference_bonus*2 + status_bonus
              - crime_penalty*2 - suspicion_penalty*2 - health_penalty,
              0.03, 0.97)
accepted = random() < score
```
So raising `acceptance_base_chance` makes a job easier for everyone; raising `skill_weight` makes it
reward skilled candidates far more (and punish unskilled ones by comparison).

**Response placeholders.** Both messages support `{title}`, `{wage}` and `{reason}`:
- `success_response` example: `"Welcome to {title}! Your offer is ${wage}/h."`
- `failure_response` example: `"{title} passed on you — {reason}."`
`{reason}` is only meaningful in the failure message (the engine picks the dominant rejection factor,
e.g. "your criminal record", "poor reputation", "low sales skill").

**Endpoints:** `GET /admin/job-applications` (list), `PUT /admin/job-applications/{job_id}` (save).
Changes are live immediately — the next application resolution uses the new values.

## City Shops — Inventory Item Management (2026-07-02)

Admin ▸ City Infrastructure ▸ **City Shops** now manages each shop's item list explicitly.

- **Assigned items:** each shop stores an optional `item_ids` list. When present, the shop sells exactly
  those items. Shops with no `item_ids` fall back to the legacy category (`store_type`) mapping, so
  existing shops keep working until first edited.
- **Add Item:** in the shop editor (existing shop only), the "+ Add item…" dropdown lists the GLOBAL item
  set (any item, any category). Selecting one calls `POST /admin/city-shops/{shop_id}/items {item_id}`.
  The first explicit add auto-initializes `item_ids` from the shop's current category items so nothing is
  lost when switching to explicit mode.
- **Remove:** the trash icon on each item row calls `DELETE /admin/city-shops/{shop_id}/items/{item_id}`
  and also clears that item's per-shop `items_config` (capacity/discount) and `stock`.
- **New shops:** created with `item_ids` unset → pre-filled from the chosen Category. Add/remove of
  individual items is available after the first save (needs a persisted shop id).
- **Persistence & player view:** both endpoints set `last_refresh_day=-1` to force a stock refresh, so
  changes appear in the player-facing Shop (`GET /shop/stores/{id}/items`) immediately.
- **Per-item Stock & Discount** editing is unchanged and now applies to the assigned-item rows.
