# Kaeldor RPG — Product Requirements & Build Log

## Original Problem Statement
Browser-based **persistent, real-time life-simulation RPG** ("Kaeldor RPG"). A life-sim + business tycoon + persistent browser MMO. Player starts ordinary (little money, cheap apartment, low skills) and over real-time days/weeks can work, study, build skills, buy vehicles/homes, start businesses, follow legal or risky illegal paths, get rich or go bankrupt.

**Hard design rule:** NO action points, NO daily action limits, NO "end turn". Always playable. Balance comes from real-time action durations, fatigue, money, risk, cooldowns, health, stress, consequences, and opportunity cost. Offline time counts; jobs/education/business/legal/recovery continue while offline.

## Session Update — 2026-07-02 (Standardized 4-Shift System + Registration/Auto-Start, NPC Transparency, Hiring Tuning)

### Add-on same session — Admin JSON editor: pretty-print, validation & key-order fix
- **Bug:** Job Editor (and all content JSON editors) "scattered" keys after save/re-open. Root cause: backend used MongoDB `$set`, which keeps the *original* document field order and ignores the admin's reordering.
- **Fix:** `POST/PUT /admin/content/{ctype}` now use `replace_one` so the doc is stored in exactly the submitted key order; fields managed by other panels but absent from the payload are retained (appended) so nothing is dropped. Verified via curl (reordered key persisted first; shift_options/acceptance_base_chance preserved).
- **Frontend JsonModal:** already pretty-printed (`stringify(obj,null,2)`); added live validity indicator (green "Valid JSON" / red parse error), red border + **disabled Save** while invalid/non-object, and a **Format ⧉** button. Verified via screenshots.
- **Docs:** ADMIN_SANDBOX.md updated.



### Add-on same session — God Mode: Market CRUD + Character Origins (iteration_39)
- **Stocks/Crypto full CRUD:** `POST /admin/market` (symbol, name, kind stock|crypto, base_price → id `stk_/cry_<sym>`, price=prev=base, history=[price]) and `DELETE /admin/market/{id}`. `market_engine` reads `db.market_assets` dynamically so new assets advance next tick and deleted ones stop — verified live in player market. Admin Markets panel: "Add New Asset" form (`market-create`) + per-asset delete (`market-delete-<id>`).
- **Character Origins (dynamic start presets):** new `character_backgrounds` DB collection (hardcoded presets migrated via CONTENT_MAP + `migrate_backgrounds.py`). Full admin CRUD `GET/POST/PUT/DELETE /admin/backgrounds` (name, desc, order, active, starting cash/bank/debt, stats{health,energy,fatigue,hunger,mood,stress}, skill bonuses, starting inventory). `new_player(user,name,bg_id,bg)` applies all attributes; `POST /character/create` + public `GET /backgrounds` read from DB (fallback to hardcoded if empty). New admin tab **Character Origins** under Player Management (`origin-*` testids). Character-create screen pulls origins live.
- **Verified end-to-end:** custom origin with cash 999/bank 5000/skills/inventory → new character got exactly those. testing_agent iteration_39: backend 17/17, frontend 100%, no issues, cleanup verified.
- **Docs:** ADMIN_SANDBOX.md updated (market CRUD + Character Origins).



### Add-on same session — Shop Price % + Admin-only Application Reason Management (iteration_38)
- **Shop "Price %" multiplier (replaces Discount):** per-item `items_config.<item>.price_pct` (default 100). Final price = base × price_pct/100 (100=base, 90=−10%, 150=+50%). `core._shop_price`; `_norm_items_config` migrates legacy `discount_pct`→`price_pct`; economy shop listing/buy use it; on_sale = any price_pct<100. Existing shop docs migrated. Admin editor shows "Price %" column with live "base $X → $Y" preview (`cfg-price-<id>`). Verified e2e: $4 coffee @150% → $6 in player shop.
- **Application reasons are Admin-only** (players see only the final success/failure response). Reverted the player-facing reason line from JobCenter.
- **Per-job editable reason strings:** each job stores `reason_strings:{accept:{},reject:{}}`; `evaluate_application` returns a `reason_key` (dominant factor) and resolves the display string from job overrides → `employment.DEFAULT_ACCEPT_REASONS`/`DEFAULT_REJECT_REASONS`. Only non-default overrides persisted. Job Editor ▸ Applications ▸ Job Tuning shows Accept/Reject reason inputs (`jobapps-accept-<key>`, `jobapps-reject-<key>`).
- **Recent Applications monitor:** `GET /admin/applications?status=&limit=` (player_name, job, status, reason, outcome_message) + `PUT /admin/applications/{app_id} {reason, outcome_message?}` to manually override. UI: `jobapps-tab-monitor` → `applications-monitor` with status filters and per-row reason override.
- **Docs:** ADMIN_SANDBOX.md updated (Price % + reason management).
- **Verified:** testing_agent iteration_38 — backend 11/11 + frontend 100%. Economy/market suites green. (Cosmetic-only: React hydration warning on the shop add-item <option> from Emergent build tooling, not app code.)



### Add-on same session — Application Reason UI, City Shop Item Management, Social Cooldown Timer (P0)
- **Application outcome in "Your Applications":** `resolve_npc_applications` now stores `outcome_message` on the application (formatted from the job's admin-tunable `success_response`/`failure_response` with {title}{wage}{reason}). JobCenter shows it (`data-testid application-outcome-<id>`), falling back to the short reason for legacy apps.
- **City Shops explicit item management:** shops now carry an optional `item_ids` list (falls back to legacy `store_type` category when unset). New `core.shop_item_docs(shop)` drives both `_resolve_shop_stock` and the player shop listing (`/shop/stores/{id}/items`). Admin ▸ City Infrastructure ▸ City Shops editor gains an "Add item" dropdown (global item list) + per-row Remove (trash). Endpoints `POST /admin/city-shops/{id}/items`, `DELETE /admin/city-shops/{id}/items/{item_id}`; first explicit add seeds item_ids from current category items so nothing is lost; PUT no longer wipes item_ids when omitted. Changes reflect in the player Shop immediately.
- **P0 fix — Social "Meet People" cooldown timer:** location cards (`Social.jsx`) now anchor `cooldown_remaining` to an absolute end and render a live countdown via `fmtDuration` (m:s / h:m:s), inside the disabled button and as an "Available in <time>" line (`data-testid location-cooldown-<id>`); list auto-reloads when a cooldown elapses.
- **Docs:** ADMIN_SANDBOX.md (shop inventory management), UI_AUDIT_NOTES.md (cooldown + application reason).
- **Verified:** testing_agent iteration_37 — backend 10/10 + frontend 100% (admin add/remove item, player shop reflection, 403s, live cooldown countdown, application UI). Cosmetic-only React hydration warning on the add-item <option> comes from Emergent build tooling, not app code.


**403 admin dashboard:** verified already fixed — admin user has `role:"admin"` and `admin_user` checks `role`; `GET /api/admin/config` returns 200 with the admin Bearer token (header-priority auth from prior session in place).
**Standardized 4-shift system:** all NPC jobs now use fixed-start shifts on one clock — Early 08:00-13:00 (5h), Late 13:00-18:00 (5h), Full 08:00-18:00 (10h), Night 22:00-08:00 (10h). Night pays ×1.45 / XP ×1.20 with ~2× injury risk; included for all jobs except office desk jobs (`office_assistant`, `store_manager`). Built via `_std_shifts` in seed_data.py; each shift has `start_hour`, `duration_hours`, derived `start_window`. DB migrated (`backend/migrate_shifts.py`).
**Shift Registration + Auto-Start:** players must SIGN UP before a shift begins — `POST /api/jobs/register-shift {shift_id}` stores `player.registered_shift` with `start_real` (computed via new `game_engine.game_to_real`). One registration at a time (409 on duplicate); `POST /api/jobs/cancel-shift` clears it. `game_engine.maybe_autostart_shift` (called in `resolve_player`) auto-clocks-in when the game clock reaches start_hour; if the player is busy/confined/exhausted at that moment the shift is MISSED (reliability −4/−5, warning notification). Retroactive `started_at=start_real` lets offline catch-up complete+pay the shift. `/jobs/work` kept as a backward-compat alias that now registers. `registered_shift` added to `new_player`.
**NPC interaction transparency:** ContactDetail interaction cards now show reward pills (e.g. "+3 Relationship", "+1 Trust", "-8 Suspicion") derived from each action's `on_success`, plus an "Unlock: <perk>" hint for `network_pro` on perk contacts (helpers.js `actionRewards`).
**Admin Applications tuning:** new Admin ▸ Gameplay Tuning ▸ **Applications** tab. Each job stores `acceptance_base_chance` (0-1), `skill_weight` (0-10), `success_response`, `failure_response` (placeholders {title}{wage}{reason}). `employment.evaluate_application` uses base_chance + skill_bonus×skill_weight; `resolve_npc_applications` uses the custom messages. Endpoints `GET/PUT /api/admin/job-applications`. `admin_update_job_shifts` now persists `start_hour`.
**Docs:** `/app/docs/ECONOMY_LOGIC.md` (4-shift table + registration/auto-start rules) and `/app/docs/ADMIN_SANDBOX.md` (hiring difficulty & response tuning) updated.
**Verification:** testing_agent iteration_36 — backend 10/10 pytest PASS (register/cancel/duplicate/invalid, 4 standard shifts, admin get/put/validation/403), frontend PASS (sign-up→registered→cancel flow, reward pills render, admin editor opens with 4 fields + save/reset). verify_economy.py + verify_markets.py still green.


## Session Update — 2026-07-01 (Inventory Refactor & Asset Consolidation)
**New "Inventory" sidebar tab** (`/inventory`, Backpack icon) is now the central hub for physical assets: Equipment (5 slots), Items (consumables use / equippables equip), and Your Garage (owned vehicles + sell). Pure frontend re-org — backend endpoints unchanged (`/inventory`, `/equipment`, `/vehicles`, `/vehicles/{id}/sell`).
**Shop** is now purchase-only (category-grouped buy cards → "Buy to Inventory"); inventory/equipment panels removed.
**Vehicle Dealer** is now purchase-only ("For Sale" only); "Your Garage" owned-vehicles section removed (moved to Inventory).
**Docs:** `/app/docs/UI_AUDIT_NOTES.md` updated.
**Verification:** testing_agent iteration_26 — frontend 7/7 PASS (new tab, buy→appears in Inventory, equip/unequip, consumable use, vehicle buy→sell), zero console errors.


## Session Update — 2026-07-01 (NPC Filter System for Dynamic Locations)
**NPC categorization:** every archetype now carries `tags` (Criminal/Wealthy/Corporate/Fitness/Social/Drifter) + numeric attributes `social_status`, `legal_standing`, `wealth` (0-100), defined via `ARCHETYPE_META` in seed_data.py.
**Location filters:** locations gain `include_filtered`, `category_whitelist`, `min_attrs`, `max_attrs`, `filter_weight`. `social_engine.location_pool()` builds the encounter pool = manual NPCs (ALWAYS included, BYPASS filters — dynamic override) + archetypes passing `_archetype_passes()` (whitelist tag match + min/max attribute thresholds) when `include_filtered`. Rolled by normalized weight on visit.
**Admin UI:** Locations editor gains a filter section (Auto-include toggle, tag chips, min/max attribute inputs, filter weight); cards show a filter summary and mark filter-sourced NPCs with `*`. `GET /admin/locations` returns `tag_options`/`attr_options` + archetype tags/attrs. New seeded showcase: "The Platinum Lounge" (Wealthy/Corporate, social_status≥60).
**Docs:** `/app/docs/SOCIAL_SYSTEM_LOGIC.md` updated with the filtering logic.
**Verification:** testing_agent iteration_25 — backend 12/12 pytest PASS + frontend PASS (admin/player parity confirmed). Filter engine unit-checked (manual bypass + tag/attr filtering).


## Session Update — 2026-07-01 (Underworld Overhaul + Financial Sandbox)
**Underworld gatekeeping:** the tab is fully locked until the player has a TRUSTED criminal contact. Meet a Shady Contact via Socials 3.0 (new `go_to_streets` "Prowl the Backstreets" location action), unlock at Relationship≥40 & Trust≥30 (`UW_MIN_SCORE`/`UW_MIN_TRUST`). Gated: `/illegal-actions`, `/illegal-actions/commit`, `/market/crypto`, crypto trades. New `GET /underworld/status`.
**Crime risk profiles:** crimes now expose live effective `bust_risk` (caught → fine+jail+suspicion) vs `fail_chance` (job flops → $0, NO jail), computed to mirror `_resolve_illegal` (street smarts lowers both; suspicion raises bust; bust+fail capped 0.95). Underworld crime cards render Fail vs Bust as two distinct panels.
**Financial markets (`market_engine.py`):** geometric-random-walk prices advancing lazily on read by real elapsed time (1 game hr=1 real hr), clamped [0.1×,12×] base. Stocks (KAEL/NOVA/HELX/ORB) traded in Bank (open); Crypto (BTK/ETK/KLD/DGZ) traded in Underworld (gated). `p.portfolio={asset_id:{qty,avg_cost}}`, valued into net worth as `investments`. Endpoints: `/market/stocks|crypto|portfolio|buy|sell`. Shared `MarketPanel.jsx` UI with sparklines + positions/P&L.
**Admin Sandbox:** Tuning tab gains Stock Market + Crypto Market sections (`stock_drift`, `stock_volatility`, `crypto_drift`, `crypto_volatility`).
**Docs/tests:** `/app/docs/UNDERWORLD_MARKETS.md`; new `/app/tests/verify_markets.py` (price bounds, drift direction, crime math) PASS; `verify_economy.py` still green.
**Verification:** testing_agent iteration_23 — backend 15/15 pytest PASS + frontend 8/8 PASS, zero console errors.


## Session Update — 2026-07-01 (Phase 4: Inventory & Equipment + Active Perks panel)
**Equipment system:** players have 5 slots — outfit, accessory, phone, computer, work_gear (`p.equipment = {slot: item_id}`). Equippable items carry `slot` + `equip` bonus dict; aggregated into `p.equip_bonus` (floors→max, *_mult→product, rest→sum) via `_recompute_equip_bonus` on equip/unequip. Endpoints: `GET /equipment`, `POST /inventory/{id}/equip`, `POST /equipment/{slot}/unequip`. `GET /inventory` now returns `usable`(consumable only)/`equippable`/`equipped` flags; `use` restricted to consumables.
**Passive bonuses wired into formulas:** `work_effectiveness`→effectiveness() (cap raised to 1.25, also lifts pay+XP+tips), `tip_rate`→job tips, `social_success`→social interaction chance, `energy_drain_mult`/`health_regen`/`*_floor` (mood/social_status/reputation)→decay_needs(). All additive/floor — no infinite stacking.
**Items:** consumables (energy_drink, protein_bar, coffee, painkillers, + new first_aid_kit, sleeping_pills); apparel (nice_clothes, business_suit); accessory (luxury_watch); device (smartphone→phone slot, laptop→computer slot, keep SMS/email ownership gate); gear (toolbelt, athletic_gear). Removed legacy 'gift' item + 'wearable'/'gear-passive-by-owning'.
**Active Perks panel:** BusinessManage Overview shows social-contact perks (−wage% / −material%) from `player.social_perks`, or an empty hint. Reflects the Socials 3.0 perks already applied to the P&L.
**Shop UI:** rebuilt as "Shop & Inventory" with an Equipment slot grid (equip/unequip), equip-bonus pills, per-category shop groups.
**Verification:** testing_agent iteration_22 — backend 7/7 pytest PASS + frontend flows PASS, zero console errors; verify_economy.py still green.


## Session Update — 2026-07-01 (Socials 3.0 + staffing fix + rebalance + day-clock fix)
**Day-clock bug FIXED:** `fmtGameClock(helpers.js)` now derives the day index from `state.world_start_game` (1:1 real-time anchor) instead of a hard-coded 2050 epoch → always positive "Day N" (was "DAY -16124"). Verified header shows "Day 1".
**Staffing slot enforcement:** `employee_engine.business_metrics` caps per-role `active_working = min(active_raw, recommended)` and adds `overstaffed`/`active_raw`. UI (BusinessManage) shows "Working now X/Y" (never > slots) + overstaffed warning ("extra wages wasted"). Production was already slot-capped via `effective_worker_hours`.
**Economy rebalance:** kiosk `pph` 5.5→2.7 (L2+Mkt2, 2 cashiers ≈ $550/day net), cleaning_co `pph` 0.61→0.42 (L1, 2 cleaners ≈ $352/day net). Applied to template + existing businesses via `migrate_socials3.py`. Reputation floor normalized (<50 → 50). NET/day clarified as a *projection* vs lifetime "Total rev". `verify_economy.py` still green.
**Socials 3.0 "Roleplay Meeting":** players start with an EMPTY circle (magic auto-seed removed; only Boss on job-accept & Landlord on rent auto-created). Meet NPCs via location actions — Go to a Bar (Regular/Manager/Wholesaler), Go to the Gym (Athlete/Coach), Network at Work (Coworker/Manager, needs a job). New archetypes: manager, wholesaler, bar_regular, gym_coach, athlete. **Professional perks:** `network_pro` ("Talk Business") on Manager/Wholesaler at Trust≥60 & Relationship≥50 grants a PERMANENT player-level discount — Manager `wage_discount` (NPC wages), Wholesaler `material_discount` — +5% each, stacking to a 20% cap (`p.social_perks`). Wired into `resolve_business` (wage_mult/material_mult, `_auto_restock cost_mult`, `_day_rates`). Removed gamey actions: give_gift, ask_favor, ask_loan. Docs: `/app/docs/SOCIALS_3.0.md`.
**Bottleneck text:** BusinessManage `pnl-footer` → "<sold> / <demand> units sold today. Hire more staff to reach full market potential."
**Verification:** verify_economy.py PASS; perk unlock verified via script; testing_agent iteration_21 frontend 8/8 PASS.


## Session Update — 2026-07-01 (Business overhaul + P1 features)
**Economy rebalance (targets = L1 net/day, 1 NPC worker, ±15%):** kiosk~$220, online_shop~$300, cleaning_co~$350, delivery~$450, bistro/pet_shop/gym~$500, auto_repair/clothing~$800, real_estate~$1100. Achieved by tuning `production_per_worker_hour` only (prices/material costs unchanged). Verified: market estimates within ±20% of targets.
**Reputation vs Satisfaction (de-duplicated):** Reputation = market reach → multiplies DEMAND (0.5–1.0×), rises with marketing/upgrades & staying in stock. Satisfaction = team morale → multiplies PRODUCTION (0.85–1.0×), driven by shift coverage + worker quality. Starting satisfaction=80. Tooltips added.
**Marketing** = brand: +25% demand AND +10% price premium per level (premium stays visible even when capacity-bound). Marketing button restyled cyan (was purple).
**Activity timers:** `business.activity={type,started_at,ends_at,duration_days,completed}`. Upgrade=7 in-game days (−50% income during build → +1 level & staff slot). Marketing=3 days (boost applies on completion). One activity at a time (2nd → HTTP 400). Progress banner + disabled buttons in UI.
**Staff slots:** max_staff_slots = base_slots + level−1; per-role targets scaled so they sum to slots ("Active Staff: X/Y"). Roster terminology/endpoints removed.
**P1 features:** Housing deposit refund on move-out + on switching rentals; property resale at 60% (POST /housing/sell, /housing/move-out); Shop items go to INVENTORY only, explicit "Use" applies effect (gear not consumable); passive health regen (~0.8/gh) + suspicion decay (~1.5/gh) + sleep −20 stress; NET worth breakdown tooltip (Header + Dashboard) = "Cash + Bank − Debt + 50% Asset Resell Value" (property valued at 50%).
**UI cleanup:** OwnedBusinesses cards show only info + "Manage Business" (no Upgrade/Marketing/Sell/Collect). "Production" → "Sales Capacity" label for retail (kiosk/clothing/pet_shop/online_shop). Context-aware P&L footer. Effective price shown in P&L. UI is 100% English.
**Verification:** testing_agent iteration_16 (backend 100%) + iteration_17 (frontend 100%, backend estimates 100%).


## User Choices (v1)
- Auth: JWT email + password (Google login deferred).
- Priorities (fully): core loop, economy, education & skills, legal/illegal paths. Business: **basic foundation** only (buy/run, income/expenses/debt/reputation/bankruptcy); deep employees/marketing/expansion deferred.
- Theme: dark neo-noir + clean dashboard MMO.
- Time: **configurable** `time_scale`. v1 default = 1 game hour = 5 real minutes (`time_scale=12`). `time_scale=1` => true real-time.
- Admin: seeded `admin@kaeldor.com` + full content editors + balancing/time-scale config. Pre-seeded content so the game is playable immediately.

## Architecture
- **Backend** FastAPI (`/app/backend`): `server.py` (routes+auth), `game_engine.py` (real-time resolver), `game_models.py` (player factory + DEFAULT_CONFIG), `seed_data.py` (default content + seeding). MongoDB via motor.
- **Frontend** React (`/app/frontend/src`): `context/AuthContext` (JWT, token in localStorage), `context/GameContext` (polls `/api/game/state` every 5s + 1s ticker for smooth timers), `components/game/*` (Layout, ActivityPanel, EventLog, ActionCard, primitives, controls), `pages/*` (one per required page).
- **Real-time engine** (`resolve_player`) runs on every state read / action: completes finished activities (offline-safe), decays needs by elapsed game-hours, accrues rent/bills/vehicle costs + loan interest, accrues business income, releases jail/hospital, handles health-collapse -> hospital.
- Time math: `real_seconds = game_minutes / time_scale * 60`; `game_hours_elapsed = real_minutes * time_scale / 60`.

## User Personas
- **The Grinder** — works shifts, manages needs, climbs careers legally.
- **The Tycoon** — studies finance/management, buys & scales businesses.
- **The Outlaw** — runs underworld jobs, juggles suspicion vs reward and jail risk.

## Core Requirements (static)
Stats (cash/bank/debt/net worth, energy/fatigue/hunger/hygiene/mood/stress/health, reputation/legal_reputation/criminal_suspicion/social_status, level/XP); 12 skills; needs decay & consequences; real-time actions (duration/cost/reward/effects/xp/risk/cooldown/blocking/offline/result); jobs as shifts w/ promotions; education courses; basic businesses; legal/illegal paths w/ jail/hospital/record; housing; vehicles; leaderboard; admin content editors. Multiplayer-ready DB (per-player docs, businesses collection, leaderboard).

## Implemented (2026-06-30)
- JWT auth (register/login/logout/me) + seeded admin; character creation w/ 5 backgrounds.
- Full player state + real-time resolver with offline progress, needs decay, recurring bills, loan interest, effectiveness model.
- Actions (16 seeded), Jobs (13 + apply/work-shift/quit/promote + random work events), Education (9 courses), Shop (7 items), Bank (deposit/withdraw/loan/repay), Real Estate (6 homes, rent/buy), Vehicles (7, buy/sell, daily costs + condition), Businesses (10 types, buy/collect/upgrade/marketing/inject/sell + passive P&L + bankruptcy + random events), Underworld (8 illegal actions w/ catch/fail/jail/fine), Police Record, Jail (bail), Hospital (treat), Leaderboard.
- Admin dashboard: stats, content CRUD via JSON editor, config editor (time_scale + full JSON), players table.
- Dark neo-noir UI w/ live countdowns, terminal event log, full data-testid coverage.

## Updated — Real-Time Default (2026-06)
- Default `time_scale = 1` (TRUE REAL-TIME: 1 game hour = 1 real hour). Durations re-tuned (small actions 8–35m, shifts 2–8h, sleep 8h, courses 12h–10 days, jail 6h–1.5d). Admin can still set 12× test mode. Real-time mode indicator in top bar + Admin config; cards show real wait times.

## Added — NPC Employee + Hiring System (2026-06)
- `employee_engine.py` resolves staffing fully offline: applicant generation over real time, hire/reject/recruit, morale/energy/experience drift, skill-ups, sick days, quitting, theft, training completion, wage payment (unpaid wages drop morale + cause quits), manager bonuses, random staff events, staffing-driven revenue/satisfaction/reputation, bankruptcy.
- Seeded: 14 roles, 12 traits, per-type staffing requirements (10), 4 training options, 8 staff-event templates — all admin-editable (5 new Admin tabs).
- New endpoints: business detail/employees/applicants/events, hire/reject/recruit/fire/raise/train, training-options. Owned list returns staffing `metrics`.
- New `BusinessManage` page (/businesses/:id) with Overview/Finances/Employees/Applicants/Training/Events tabs. Verified by testing agent (backend 17/20, 3 skipped for funds; frontend 100%). No blocking bugs.

## Added — Social Contacts & Relationships System (2026-06, P1 done)
- New `social_engine.py`: per-player NPC `contacts` collection. Each contact has relationship_score (-100..100), trust, respect, attraction (romance), mood, personality traits, status (active/distant/angry/close/romantic/ex_partner/blocked), decay_rate, last_interaction_at, known_since, and a history log.
- Offline resolution in `resolve_social()` (hooked into `resolve_player`): relationship decay over real time (close bonds slower, angry bonds worsen), mood/status drift, aggregate mood/stress effect on player, partner expenses, weighted random social events, angry-boss firing risk, angry-landlord eviction warnings. Lazy-seeds a social circle on first state read.
- 12 seeded NPC archetypes, 14 personality traits, 13 relationship actions, 6 gift types, 13 social-event templates — all admin-editable (5 new Admin tabs: NPC Archetypes, Personality, Rel. Actions, Gifts, Social Events).
- Interactions: instant (small_talk, call_text, give_gift, apologize, ask_favor, ask_reference, ask_loan — per-contact real-time cooldowns, don't block) + activity (hang_out, help_problem, invite_date, meet_shady) + discovery (network_business, meet_new_people — grow the circle). No action points; balanced by cooldowns/money/risk.
- Integrations: job apply/promote → boss + coworker contacts (angry boss can fire you); rent → landlord (angry landlord eviction warnings); buy business → business contact (networking boosts biz reputation); shady contact `meet_shady` → temporary crime police-risk reduction buff applied in `_resolve_illegal`; ask_reference → reputation + job reliability; ask_loan → cash.
- New endpoints: GET /api/social/contacts, /social/contacts/{cid}, /social/gifts, /social/discover-actions; POST /social/contacts/{cid}/interact, /social/discover/{action_id}, /social/contacts/{cid}/block.
- Frontend: `Social.jsx` (/social) with tabs All/Friends/Work/Romance/Business/Housing/Underworld/Family/Meet People/Event Log + `ContactDetail.jsx` (/social/:cid). Nav entry added.
- Verified by testing agent iteration_3 (backend 19 passed / 5 skipped for live-state, 0 failed; frontend 100% selectors). Minor validation-order fix applied (gift selection validated before cooldown). No blocking bugs.

### Backlog (P1/P2)
- **P1 Player housing market / real-estate upgrades** (furniture, perks).
- **P2 Vehicle mechanics** (fuel, insurance, repairs, accidents).
- **P2 Travel/City map** with travel-time blocking activities; richer random-event chains.
- **P2 Multiplayer:** chat, player marketplace, player-owned companies hiring players, factions/gangs, contracts.
- **P2 Polish:** brute-force login lockout + password reset (auth playbook), split `server.py` into routers, persist player only on mutation, add favicon (clears cosmetic 404), differentiate "Busy" vs disabled button styling, tighten CORS origins for production.

## Credentials
See `/app/memory/test_credentials.md`. Admin: admin@kaeldor.com / admin123.

## Added — Multiplayer Comms + Player Employment (2026-06)
- **Phase A** (done): in-game clock exposure, Daily Summary ledger (continuous accrual — midnight tick summarizes, does NOT re-charge), notifications system.
- **Phase B** (done): World Chat, SMS/Email threads, device gating (SMS needs Smartphone, Email needs Laptop), player presence. Seeded demo players (mara/dovan/kiri).
- **Phase C — Player Employment & Job Applications (done & verified, iter_6 + iter_7)**:
  - NPC job applications: `POST /jobs/{job_id}/apply` → real-time resolution (`employment.resolve_npc_applications`, hooked in `resolve_player`) → accepted (stat-based wage offer) or rejected (human reason); accept/withdraw; criminal-record (legal_rep<25) 403; duplicate 409; offer expiry.
  - Player Job Market (`/job-market`): `GET /jobs/market`, apply to player-owned hiring businesses, `GET /jobs/employment` (My Jobs/offers), accept/decline offers, real-time shifts (`/jobs/employment/{id}/work`) → wages paid + business cash/satisfaction/reputation/revenue boost (`employment.complete_player_shift`), quit.
  - Owner Player Hiring tab (`/businesses/:id`): toggle-hiring, list applicants with stat snapshot + recommended wage, send/update offer, reject, list/raise/fire player employees.
  - Logic fixes (iter_7): owner notified + applicant event on offer **decline** (status 'declined' vs 'withdrawn'); **fire** writes fired-employee event log; **re-offer** sends 'Offer updated' (not duplicate 'Job offer!'); invalid shift hours (∉{2,4,6,8}) now 400; `applicant_snapshot` top_skills construct cleaned up.
  - Tests: `tests/test_phase_c_employment.py` (18) + `tests/test_phase_c_fixes.py` (13) = 31/31 PASS. time_scale stays 1.0.

### Next: Phase D — Dashboard "Life Inbox"
- Surface social/relationship/job events to a Dashboard card with real-time expiry + one-tap actions (Respond, Ignore, Send Money...) and consequence routing. NOT STARTED.

## Added — Credit/Debt System Overhaul (2026-06, P0 economy fix)
- **Fixed P0 exploit:** old loan limit `max(500,(bank+cash)*3+finance*500)` grew every time you borrowed (loan adds to bank) → unbounded money-printing; UI also showed total limit instead of borrowable.
- New `credit_profile()` (server.py): limit derived from **net worth** (cash+bank−debt+assets, invariant under a loan) + finance skill + income (job + profitable businesses) + job stability + reputation; penalties for low rep, criminal record (<40 halved, <25 frozen), and missed payments (`credit_missed`, tracked offline, decays on clean days, resets on full repay).
- Clear separation: `credit_limit` / `credit_used` (=debt) / `credit_available`. Loans validated against `credit_available`; blocked path returns 403. Repay restores available.
- Bank.jsx: credit summary box (limit/used/available + sentence), live loan preview (new loan, current/total debt, interest %/day, daily interest after), over-limit disables Borrow.
- Also fixed (low-risk): vehicle & business sell now show payout (button estimate + toast amount); `Pill` forwards data-testid.
- Verified iter_9: 14 credit tests + 37 Phase C regression = 51/51 PASS; frontend 100%. time_scale stays 1.0.

## Logic Audit (see /app/memory/LOGIC_AUDIT.md)
- Full 12-area audit done. P0 credit exploit fixed. Queued P1 packages (user-approved order): (2) Transaction log + confirm dialogs, (3) realism fixes (deposit refund, house sell, suspicion cooldown, health regen, hospital bill, sleep-destress), (4) inventory/use + equipment, (5) debt consequences + vehicle repair rework.

## Player-Business + Inventory Package — PHASE 1 DONE (2026-06, verified iter_10)
User-approved decisions: (1a) player-employee role chosen from business staffing roles → counts to coverage; (2b) HOURLY wage is source of truth; (3b) inventory buy→use deferred to Phase 4.
- **Player employees fully integrated** (`employee_engine.business_metrics`/`resolve_business`): active player employee in a matched staffing role adds PLAYER_PRESENCE=0.6 FTE to coverage; metrics expose `player_have`, `player_employee_count`, `unmatched_player_count`.
- **Hourly wage model** (`wage_per_hour` source of truth): offers/raises/market base all hourly; shift pay = wage_per_hour×hours; migration converts legacy per-shift→/4.
- **Per-shift business output + net impact** (`employment.complete_player_shift`): revenue = wph×hours×output_mult×productivity (role-fit skill, reliability, health/mood/fatigue). Good hire → +net, bad hire → −net. Owner gets "+$rev − $wage = net ±$N" notification; `emp.last_shift` stored.
- **Finance log clarity** (#6): history entries tagged `kind` accrual (forecast rate + real amount) vs shift (booking). Legacy entries backfilled.
- **Current Job** (#5): `GET /jobs/current` → {npc, player_jobs}; player employment shown under Current Job + non-overlap note.
- **Withdraw application** (#4): `/jobs/employment/applications/{id}/withdraw` → withdrawn + owner notified; terminal (offer/accept 400).
- UI: BusinessManage (role dropdown, hourly, pending/offer/employee separation, fit pills, net-impact, Employees-tab player subsection, Finances forecast/booking), JobMarket (role dropdown, hourly, withdraw, net-impact), CurrentJob (player_jobs).
- Tests: 48/48 backend (test_phase1_player_employment 11 + Phase C regression 37). New fixtures/fast-forward helper in test_phase1_player_employment.py.

### Remaining phases (user-approved order)
- **Phase 2**: #3 Role/Job-listings editor, #2 internal Training (offer→accept/decline→cost/skill/log).
- **Phase 3**: spell out EXP + skill tooltips (NPC employees) — player-facing done in 1.1.
- **Phase 4**: #9 real inventory (buy→inventory→use + "buy & use now"), #10 equipment slots framework, Admin item editor.
- **Phase 5 (P2)**: #11 custom products — datamodel + admin groundwork only.

## PHASE 1.1 — Scheduled Working Hours & Business Overhaul — DONE (2026-06-30, verified iter_11)
User decisions: (1a) auto-shifts ONLY for player-business jobs (NPC Job Center keeps manual "Work a Shift"); (2c) OWNER assigns a shift PRESET per employee at offer time (owner-edit-later = P2); (3a) clock-out penalty = reliability −10, owner notified, prorated pay only, NO reputation malus; (4a) UI transparency included.
- **Schedule presets** (`employment.SHIFT_PRESETS`): Early 08–16, Late 14–22, Night 22–06 (wraps), PT-Morning 08–12, PT-Evening 18–22. Stored on `player_employment.schedule` + offer/application; `clocked_out_until` (game-time ISO).
- **Auto-work (continuous accrual)** `employment.accrue_player_employment` (called in `resolve_player`): computes game-hour overlap with schedule window since last resolve; credits wage→employee cash, net (rev−wage)→business cash/revenue_total/satisfaction/reputation + booking history; tracks `emp.today` (date/hours/wage/revenue/net) + `last_impact`. Offline-safe. Productivity = perf×role_fit×reliability (good employee → real profit, prod>0.56 ⇒ net>0).
- **Activity gating**: `p['on_shift']` set during active window; `ensure_free()` blocks any blocking physical activity (sleep/eat/travel/course/NPC shift/illegal/social) with 409 while on shift; remote/read flows allowed. Status → "working".
- **Clock Out Early** `POST /jobs/employment/{id}/clock-out` → `employment.clock_out_early`: sets clocked_out_until=end-of-window (stops accrual till next day), reliability −10, owner notification, player event + business finance/event log; role becomes uncovered unless NPC backup.
- **Roster vs Active coverage** (`employee_engine.business_metrics`/`resolve_business`): player counts to roster always, to active only while on-shift; per-role status string; business output only from active coverage.
- **NPC backup** (`b.backup_roles`, `POST /businesses/{id}/backup`, BackupBody): default OFF; when role has no active worker & backup enabled → covers role + charges `backup_wage_day` (role wage midpoint); never double-pays when a player is active.
- **UI transparency**: `business_detail.costs` (upgrade/marketing/sell preview); BusinessManage action cards show cost/level→level/effect; "Market"→"Run Marketing"; Sell confirm modal w/ payout breakdown; Roster/Active coverage panel + NPC backup toggle per role; offer schedule dropdown; employee schedule + on-shift + "Today +$rev −$wage = net" line.
- **Worker UX**: CurrentJob + JobMarket(My-Jobs default) show schedule, on-shift, today earnings, Clock Out Early; ActivityPanel right-rail "ON SHIFT" state w/ clock-out; removed manual `POST /jobs/employment/{id}/work` + `player_shift` activity kind.
- **Tooltips** (`primitives.InfoTip`): Stats/needs (Layout strip), Dashboard standing + XP, Skills page.
- Endpoints added: `GET /shift-presets`, `POST /jobs/employment/{id}/clock-out`, `POST /businesses/{id}/backup`. Migration adds default schedule to legacy employment.
- Tests: engine smoke 14/14 (`tests/smoke_phase11.py`), HTTP 8/8 (`tests/test_phase11_player_employment.py`), UI smoke PASS → backend 100% / frontend (after fixes) green. time_scale stays 1.0.
- NEXT: Phase 2 (Owner tools: job-listings editor, internal training). P2: owner-side schedule editing with player accept/decline.


## HYGIENE REMOVAL + BUSINESS SUPPLY-CHAIN REWRITE — DONE (2026-07-01, verified iter_13)
User decisions: 1b (named ingredient recipes), 2a (auto-restock + manual buy button), 3a (NO auto-bankruptcy), 4a (keep marketing/reputation as demand boost), 5a (migrate existing businesses). Plus: rename business; clear demo debts.

### Hygiene — fully removed
- Removed `hygiene` from `NEED_STATS`, player factory, decay config (`game_models.py`), `need_keys`/decay/mood-penalty/job-decay (`game_engine.py`), `cond` formula (`employment.py`), sleep/jog effects + the whole `shower` action (`seed_data.py`).
- Frontend: removed from `helpers.js` NEED_META + STAT_INFO, HomeNeeds category+sub, ActionCard POSITIVE_GOOD, Dashboard nav desc.
- DB migration run: deleted `shower` action, `$unset effects.hygiene` from actions/items, `$unset hygiene` from all player docs. No hygiene-only items existed.

### Business — transparent SUPPLY-CHAIN model (replaces rent/base_revenue/base_expenses/PLAYER_PRESENCE/backup/auto-bankruptcy)
- Each business type has `product{name,price}`, `recipe[{id,name,qty,cost}]`, `production_per_worker_hour`, `daily_demand` (`seed_data.BUSINESS_TYPES`). Runtime: `materials{}`, `products`, `restock_target`, `auto_restock`.
- `employee_engine.resolve_business(db,cfg,now,b)`: idempotent on business's own `last_resolved_at` (single writer → NO clobber-race). Per window: gather ALL workers (NPC+player) via `gather_workers` → identical `worker_productivity(skill,reliability,condition)`; auto-restock from business cash; produce = min(capacity, materials); sell = min(products, demand×marketing×reputation×level); wages debited (shortfall → business debt, NO bankruptcy). Player wages `$inc`'d to `player_employment.earnings_pending`/`personal_hours_pending` (atomic-drained by `employment.sweep_player_earnings` in the employee's own resolve → race-safe). `_day_rates` = transparent steady-state P&L (rev/materials/wages/net, components rounded so tile == breakdown).
- `employment.py`: removed `accrue_player_employment`/`_accrue_one`; added `resolve_worked_businesses` + `sweep_player_earnings`; projections now return `units_per_hour`/`margin_per_unit`/`productivity`/`rev_per_hour`/`net_per_hour` (NOT wage-coupled). NPCs get a `schedule`+`wage_per_hour` on hire → same engine as players.
- New endpoints: `POST /businesses/{id}/rename`, `/buy-materials`, `/restock-settings`. `buy_business` seeds starting materials; `migrate_business_supply_chain()` on startup patches business_types + existing businesses + NPC schedules.
- Frontend `BusinessManage.jsx`: Overview has "Supply Chain — how this business makes money" panel (Recipe → Materials/unit + Margin/unit, Daily P&L breakdown, Inventory pills + auto-restock + Buy-Materials, Rename modal); Staffing (roster/active, no backup); Finances history uses rev/material/wages/net. `money2()` (cents) for per-unit values. `OwnedBusinesses.jsx` uses `metrics.net_day`.
- Tests: iter_13 backend 9/9 + UI all green. Demo debts cleared to 0. Dovan's kiosk (id 249566f3664b40a9b9934c150c713de2) net ≈ -$15/day is EXPECTED (Mara wage $22.5/h > her $20.6/h margin output) — transparent economics.

### NEXT (backlog, user-approved order)
- Phase 3: remaining transparency/labels (tooltips/UI clarity).
- Phase 4: real inventory (buy→inventory→use), equipment slots, admin item editor.
- Phase D: Dashboard Life Inbox / relationship-driven events.
- Logic Audit P1 (`/app/memory/LOGIC_AUDIT.md`): housing deposit refund, house selling, suspicion decay, natural health regen, clinic bill, sleep stress-relief.
- Phase 5 (P2): custom business products (admin data models).

## 2026-07-01 — Business Hours & Staff Scheduling (MAJOR: replaced fixed-8h model; fixes P0 "Ghost Workers")
- Each business now has `opening_hours {open,close}` (per type in seed_data; migrated onto existing businesses). Business only produces & sells while OPEN.
- Production is COVERAGE-based: capacity = production_per_worker_hour × covered_opening_hours × satisfaction_mult × (1+0.6·(level−1)). Covered hours = union of worker shifts clipped to opening (capped at opening length). Overlapping shifts add wages but NOT capacity.
- Wages are per-worker per-hour: wage = hourly_wage × worker_hours_in_range (clipped to opening).
- On hire, NPC auto-gets `first_uncovered_shift` (full opening if unstaffed, else largest gap). Migration re-slotted existing NPCs into equal non-overlapping blocks.
- Rebalanced production_per_worker_hour for all 10 types → L1 net/day targets within ±1% (kiosk 220, delivery 450, bistro/gym/pet_shop 500, clothing/auto_repair 800, online_shop 300, cleaning_co 350, real_estate 1100).
- New endpoints: PATCH /businesses/{id}/opening-hours, PATCH /businesses/{id}/employees/{emp_id}/shift (validate within opening, start<end).
- metrics adds: opening_hours, is_open_now, open_hours, covered_hours, coverage_hours_pct, roster[], daily_wage_total; staffing status now includes "Closed".
- Frontend: new **Schedule tab** in BusinessManage (24h timeline, opening-hours editor, per-NPC shift dropdowns, coverage indicator, daily wages). Employees tab shows $/hr + shift range. Player employees read-only (edit via Player Hiring).
- Verified: testing_agent iteration_18 — backend 9/10 (1 skip covered E2E), frontend 100%, no issues.

## 2026-07-01 — Scheduling follow-up fixes
- Applicants UI now shows hourly wage ($/hr) instead of $/day (fallback daily_wage/8). Raise event message also $/hr.
- Wage-raise requests rate-limited: 7 in-game-day cooldown per NPC (`last_raise_request`, falls back to hire_date). Event roll frequency changed from `0.04*gh+0.015` (per-poll spam) to `0.05*gh` (elapsed-time based) — no more per-tick spam.
- Overstaffing allowed: `max_hire_slots = base_slots*3 + (level-1)`. Production stays coverage-capped (overlap doesn't multiply); wages = Σ(hourly×shift_hours). Verified: 3 NPCs on 1-slot kiosk (08-12/12-16/16-20), covered 12/12h, net ~$218, 4th hire rejected. UI "Staff: X/max_hire_slots hired".

## 2026-07-01 — P0 wage/scheduling bug fixes
- ROOT CAUSE of "more staff = less money": auto-hire (`first_uncovered_shift`) returned the FULL opening window (overlap) when already covered → extra worker added 12h of wages with 0 extra coverage. Also unscheduled workers defaulted to a paid 08–16 shift (shift_bounds default) — a wage leak.
- FIX: `first_uncovered_shift` returns None when fully covered; hire stores schedule=null (unscheduled = $0). Helpers (`worker_shift_hours`, `worker_hours_in_range`, `on_shift_now`, `coverage_intervals`) now treat null schedule as 0/absent. `gather_workers` no longer defaults NPC schedule.
- OVERLAP GUARD (BUG 1): PATCH /employees/{id}/shift validates `peak_concurrent(all shifts) <= concurrent_slots` (= base_slots + level-1); rejects with "Shift overlaps with {name} — only N worker(s) can be active at the same time." Added `peak_concurrent`, `find_overlapping` helpers; metrics exposes `concurrent_slots`.
- Wage formula confirmed correct: wages = Σ(hourly × clipped shift_hours); production = pph × union_covered_hours × sat × level_mult (coverage-based, not headcount). Verified E2E: shrink NPC1 to 6h halves net; hiring NPC2 into uncovered hours RAISES net; overlap rejected; 3rd hire while covered = unscheduled $0 (net unchanged).
- Frontend Schedule tab: unscheduled workers show "Unscheduled · $0" pill + no timeline block; "Max N on shift at once" indicator.

## 2026-07-01 — Economy refactor: single source of truth
- Created /app/docs/ECONOMY_LOGIC.md (only-valid wage/production/net formulas).
- Added canonical functions in employee_engine.py: `calculate_worker_daily_wage(worker, opening)` and `calculate_total_covered_hours(employees, opening)`. `_day_rates` now routes wages+coverage through them; resolve_business accrual is their time-integral (wage_per_hour × on-shift hours; pph × union-covered × mult). No flat daily wage, no ×24, no ×8 in the calc path.
- Added /app/tests/verify_economy.py (8 assertions incl. live engine _day_rates) — ALL PASS. Run: `python3 /app/tests/verify_economy.py`.
- Grep audit: 0 hits for ×24, ×8 production, or daily_wage in calc path. Remaining daily_wage = NPC generation attribute + hourly-rate derivation (compliant); market `wage_day` = hours×rate display value; `backup_wage_day` = legacy field $unset cleanup.
- No economy regression: all 10 L1 market estimates within ±1% of targets.

## 2026-07-01 — Master Audit (Priorities 1–5) COMPLETE
- P1 Admin Sandbox: config.tuning + business_types economics, live via get_config→apply_tuning→TUNE. Endpoints GET/PUT admin/config, admin/business-economy(/{type}), admin/players(/{id}). Admin UI: Economy Sandbox, Tuning, editable Players.
- P2 Player Stats linked: Legal Standing & Social Status gate high-tier jobs (meets_requirements +min_legal_reputation/min_social_status/max_suspicion), Suspicion → hiring penalty + jail risk, Reputation+Social → job tips. Doc PLAYER_STATS_LOGIC.md.
- P3 Social overhaul: ask_loan→debt, ask_favor→non-cash, networking→leads/+4 rep. Doc SOCIAL_SYSTEM_LOGIC.md.
- P4 UI audit: Job Center requirements chip row, Daily Summary taxes+savings, net-after-tax shift events. Doc UI_AUDIT_NOTES.md.
- P5 Creative: Income Tax (tunable brackets), Savings Interest, Skill Decay. Doc CREATIVE_ENHANCEMENTS.md.
- Verified: verify_economy.py PASSES; testing_agent iteration_19 backend 11/11, frontend 100%, 0 issues.
- Docs source-of-truth: /app/docs/{ECONOMY,PLAYER_STATS,SOCIAL_SYSTEM,ADMIN_SANDBOX,CREATIVE_ENHANCEMENTS,UI_AUDIT_NOTES,MASTER_AUDIT_COMPLETE}.md

## 2026-07-01 — Realistic Shop Overhaul + Admin City Shops Sandbox (COMPLETE ✓)
- Replaced the flat item Shop with a **City Shops** browser. Items carry a `store_type` category (grocery/pharmacy/clothing/electronics/hardware); each shop stocks only its own category.
- Seeded 5 shops (seed_data.CITY_SHOPS): Kaeldor Fresh Foods (grocery, linked to Street Kiosk biz type), MediCare Pharmacy, Vantage Apparel, Circuit City, Ironworks Hardware & Sports.
- Player endpoints: GET /shop/stores (adds item_count + business_type_name), GET /shop/stores/{id}/items (category-filtered), POST /shop/buy (charges cash+bank via charge(), adds to inventory).
- Admin CRUD: GET/POST/PUT/DELETE /admin/city-shops (CityShopBody: name, category, icon, desc, business_type_id, location_id, active, order). Admin UI "City Shops" tab (CityShopsPanel in Admin.jsx) — list + editor + delete; new/edited shops go live in player Shop tab immediately.
- Frontend Shop.jsx overhauled: City Shops browser grid → enter shop → category items with effect/equip pills → Buy to Inventory.
- VERIFIED: verify_economy.py + verify_markets.py PASS; backend curl (stores/items/buy/admin CRUD) all OK; testing_agent iteration_27 frontend 100%, 0 bugs.
- Minor non-blocking notes from QA: admin tab testid contains a space (`admin-tab-city shops`); window.confirm used for delete. Left as-is (cosmetic).

## 2026-07-01 — City Shops Enhancement: Opening Hours + Stock + Discounts (COMPLETE ✓)
- Each city shop now has opening_hours (players can only BUY while OPEN; closed shops show grayed items + banner), per-item daily stock capacity that depletes on purchase and RESTOCKS at game midnight (game_day_index), and optional manual discount % (sale events).
- All configurable per-shop in Admin ▸ City Shops (opening-hours inputs + per-item Stock/Discount table). No auto price dynamics (user choice). Buy sends store_id, validates open + stock, charges discounted price.
- Backend: _resolve_shop_stock, _eff_price; CityShopBody + opening_hours/items_config; migrate_city_shops(). Frontend Shop.jsx (Open/Closed/Sale pills, stock, sold-out) + Admin CityShopsPanel.
- Verified: verify_economy + verify_markets PASS; testing_agent iteration_28 frontend 100%, 0 bugs.

## 2026-07-01 — Job Center Reorganization: Sector/Agency Browser (COMPLETE ✓)
- Job Center rebuilt into a sector browser (mirrors City Shops): sector cards (name/desc/icon/"Open Listings"/qualify count) → open a sector → filtered jobs with the same real-time apply flow.
- Seeded 7 sectors covering all 19 DB jobs: Retail & Sales, Food & Hospitality, Logistics & Transport, Corporate & Office, Trades & Manual Labor, Military & Defense, Public Services. Virtual "General Listings" fallback surfaces any unassigned job.
- Backend: JOB_SECTORS seed + CONTENT_MAP; GET /jobs/sectors, GET /jobs/sectors/{id} (unassigned handling); admin CRUD /admin/job-sectors; migrate_job_sectors(). Frontend JobCenter.jsx (JobCard reused) + Admin JobSectorsPanel (job-assignment checkbox picker).
- Verified: testing_agent iteration_29 backend 100% (12/12) + frontend 100% (5/5), 0 bugs. (Created /app/backend/tests/test_job_sectors.py.)

## 2026-07-01 — Admin Dashboard Overhaul: grouped nav + drag-reorder + summaries (COMPLETE ✓)
- ~27 flat admin tabs regrouped into 6 Main Tab groups (Overview, Economy, Gameplay Tuning, Player Management, City Infrastructure, Underworld & Finance), each with sub-tabs + a Dashboard Summary metrics strip.
- Drag-and-drop reorder of main tabs (@dnd-kit) in a "Customize" mode + show/hide toggles (Overview locked) + Reset. Layout persisted per-admin in backend (users.admin_layout via GET/PUT /admin/layout).
- New GET /admin/overview returns city-wide metrics (players, employed, active workers, market value=Σnet_worth, cash/bank/debt, content counts); compact money format ($3.77M) in summary cards.
- Backend curl-verified; testing_agent iteration_30 frontend 100%, 0 bugs (real DnD reorder + reload persistence + regression of City Shops/Job Sectors panels confirmed). Docs: docs/ADMIN_SANDBOX.md updated with layout-customization instructions.
- Backlog: Admin.jsx now ~1095 lines — consider splitting into src/pages/admin/ modules (P2 refactor).

## 2026-07-01 — Admin Live City Feed (COMPLETE ✓)
- Overview ▸ Live Feed sub-tab: real-time city-wide activity ticker from the events collection across all players, enriched with player names.
- GET /admin/feed?limit&types (CSV filter). Frontend LiveCityFeed: 6s auto-refresh, LIVE indicator, filter chips (All/Purchases/Work/Crime/Finance/Social), per-type colored icons + relative time.
- Verified: backend curl (name join + type filter) + screenshots (render + filter switch). Read-only monitoring view.

## 2026-07-01 — Live Feed Game Master enhancements (COMPLETE ✓)
- Clickable player names in the Live Feed → quick-jump to Player Management: pre-fills player search, highlights row, auto-opens Edit modal (immediate cash/stats edit). Added a name search box + X/Y count to PlayersTable.
- Danger highlighting: events with severity=="danger" (arrests, hospitalization, collapse, bankruptcy) pulse in Danger Red #FF4444 with AlertTriangle icon + "DANGER" pill (.danger-pulse keyframe). Standard events unaffected.
- Wiring: Admin() onFeedPlayerClick + renderAdminLeaf ctx (focusPlayer). Verified: testing_agent iteration_31 frontend 100%, 0 bugs (quick-jump, danger pulse on 10 crime/health danger events, search, save+revert, auto-refresh). Docs: ADMIN_SANDBOX.md updated.

## 2026-07-01 — MAJOR Backend Refactor + logic/admin additions (COMPLETE ✓)
- **Backend modularized**: server.py (~3600 lines) → `core.py` (shared api router + db + auth + all helpers/bodies, exported via __all__) + `routes/{player,economy,business,social,admin}.py` + slim `server.py` entry point. API paths UNCHANGED (no frontend change). Split done via AST script + shared-router pattern (no circular imports). Fixed a duplicate `ShiftBody` collision (renamed employee one → EmployeeShiftBody). See docs/ARCHITECTURE.md.
- **Student Welfare**: while studying (current_activity.kind=="course"), decay_needs holds Health/Energy/Mood=100 & Hunger/Fatigue/Stress=0 (safety net). docs/PLAYER_STATS_LOGIC.md.
- **Daily Summary**: added loan_interest to expense total (taxes + savings interest already included). Verified housing rent (only when NOT owned) & business rent = NONE (no ghost rent). docs/MASTER_AUDIT_COMPLETE.md.
- **Admin Tuning knobs (new)**: Skill Decay Rate (tuning.skill_decay_per_hour, 0=off), Suspicion Decay Rate (suspicion_decay_per_hour, 0=never), Suspicion Gain Multiplier (suspicion_gain_mult). Read live from TUNE; editable in Admin ▸ Gameplay Tuning ▸ Tuning. get_config now returns full effective tuning; /admin/config PUT shallow-merges sub-dicts (partial save no longer wipes other knobs).
- Verified: verify_economy + verify_markets PASS; unit tests (welfare, skill/suspicion decay, gain mult) green; testing_agent iteration_32 = backend + frontend 100%, 0 bugs (refactor regression across all 5 modules + 3 tuning fields save/persist without wiping).

## 2026-07-01 — UNIVERSAL SHIFT & RISK ENGINE (COMPLETE ✓)
Replaced static NPC job shifts (flat hour list `[2,4,6]`) with rich, admin-configurable, individual per-job shift options.
- **Schema:** each job's `shift_options` is now a list of dicts `{id, name, duration_hours, start_window:{min_hour,max_hour}, injury_risk (0-1), pay_multiplier, xp_multiplier}`. Hand-tuned per job in `seed_data.JOB_SHIFTS` (13 core jobs, 2–3 shifts each; night/hazard shifts pay more but riskier). `_shift()` helper + override loop set `JOBS[*].shift_options`.
- **Hard time-window gating:** a shift can only START while the current GAME hour is inside `start_window`. `min_hour > max_hour` = overnight window wrapping midnight (e.g. 21→03). Helper `shift_window_open()` in core.py; mirrored client-side in `helpers.js` (`shiftWindowOpen`, `fmtWindow`).
- **work_shift (`routes/player.py`):** accepts `{shift_id}` (window-enforced) or legacy `{hours}` (matched by duration, NO window enforcement — backward compat for existing API/tests). Payload carries shift_name/pay_multiplier/xp_multiplier/injury_risk.
- **Resolution (`game_engine.py`):** pay_multiplier scales wages, xp_multiplier scales skill XP. `injury_risk` roll on completion → health loss (6–16) + stress; per user decision the SHIFT STILL COMPLETES (no early abort, full pay). Event: "Finished <shift name> shift as <job> (+$net after $tax)".
- **Admin editor:** new Admin ▸ Gameplay Tuning ▸ **Job Shifts** panel (`JobShiftsPanel`) — grid of job cards → per-job form (name/id/hours/start/end/injury/pay×/XP×, add/remove/save). Endpoints `GET /admin/job-shifts`, `PUT /admin/job-shifts/{job_id}` (validates: non-empty, unique ids, hours 1–16, window 0–24).
- **Player UI (`CurrentJob.jsx`):** "Work a Shift" now renders shift cards with hours/window/×pay/×XP/risk pills; open shift → green Start button, closed shift → "Opens HH:00–HH:00 · now HH:00" (disabled). Uses live game clock.
- **Migration:** `migrate_job_shift_options()` converts legacy int arrays on startup (seed jobs → JOB_SHIFTS; non-seed jobs e.g. army/police/garbageman → generic day shifts).
- **Verified:** verify_economy + verify_markets PASS; testing_agent iteration_33 = backend 13/13 pytest + frontend 100%, 0 bugs (window gating, multipliers, admin CRUD validation, legacy path, live-clock UI gating). New reusable test: `/app/backend/tests/test_job_shifts_engine.py`.
- **Backlog note:** `Admin.jsx` now ~1370 lines — split into `src/pages/admin/` modules (P1 refactor, still deferred).

## 2026-07-01 — Job Center Dismiss, Single-Encounter Fix & 00:00 Ledger Refactor
- **Dismiss Applications (JobCenter):** every application card now has a neon-cyan "x" (`dismiss-application-<id>`). Pending/accepted → withdraw; rejected/terminal → `POST /api/jobs/applications/{id}/dismiss` (deletes record; 400 on active, 404 if missing). Verified curl + UI.
- **P0 Single-NPC-encounter fix:** players could meet 2 NPCs on one location visit due to concurrent `/game/state` polls both completing the same visit. `_do_meet_at` already rolls once; added an ATOMIC per-visit claim (`social_visit_claims`, keyed on activity `started_at`) so only one resolver spawns a contact. Stress-tested: 12 concurrent completions → exactly 1 contact. Doc: `SOCIAL_SYSTEM_LOGIC.md`.
- **00:00 Daily Ledger refactor:** RENT + VEHICLE (fuel/ins/maint) moved from hourly proration to a single daily charge at the 00:00 game-day boundary (`_charge_daily_fixed`), atomically claimed to prevent double-charge/duplicate summaries. Bills/interest stay hourly. New `business_income` ledger key logged on business collect. `_flush_daily_summary` now stores an `events` log (day's significant events). DailySummary UI reorganized: Income (Total Wages, Business Dividends/Profits, Social, Savings), Expenses (Housing Rent, Vehicle Expenses, Utilities, Social Spending, Taxes, Loan Interest) with subtotals + Event Log. Verified via unit + full-resolver tests + UI screenshot. Doc: `ECONOMY_LOGIC.md`.
- **Note:** 00:00 boundary = in-game midnight (game clock anchored to `world_start_game`); align that anchor to CEST-midnight if real-CEST coincidence is required.

## 2026-07-01 — Vehicle Categories, Job Visibility, Action Gains & Markets Debug
- **Vehicle Dealer categorization:** Sector/Box browser (mirrors Job Center). Vehicles carry `category_id` → `vehicle_categories` collection. Player: `GET /vehicle-categories` + `/vehicle-categories/{id}` (filtered listings + "Other" catch-all). Admin: full CRUD `/admin/vehicle-categories` + assignment. Seed: 4 categories (Bikes & Scooters, Compact & Economy, Vans & Utility, Luxury). Migration backfills. Tested 100% (iteration_34).
- **Progressive job visibility:** jobs have `visible_in_listings` (default True). `list_job_sectors`/`job_sector_detail` filter hidden jobs; promotions unaffected (look up by id). Admin toggle in Job Sectors tab ("Job Center Visibility"). `PUT /admin/jobs/{id}/visibility`. Tested 100%.
- **Action Card gains (UI):** `ActionCard.jsx` now renders `skill_xp` as cyan XP chips + stat `effects`. Data existed; was unrendered. Verified via screenshot.
- **Markets "stagnation" debug:** NOT a sync bug — drift/volatility persist & are consumed (vol 0.5 → 30-1000% moves). Root cause: lazy real-time random walk; movement scales with elapsed real hours (36s min step), so quick edits look frozen. Added Admin ▸ Markets panel (set price/base per asset, "Re-roll Now" forces a full step) + `GET /admin/market`, `POST /admin/market/refresh`, `PUT /admin/market/{id}`. Sync verified (admin KAEL→250, player showed ~250). Docs: ADMIN_SANDBOX.md.

## 2026-07-02 — FINAL LOGIC REPAIR: Linking Audit Findings (COMPLETE ✓, iteration_40)
Wired four tracked-but-unused stats into real outcomes. Backend-only. All strings English. Doc: `/app/docs/FINAL_LOGIC_FIXES.md`.
- **Effectiveness → Crime:** `game_engine._resolve_illegal` now scales illegal-job failure chance by live `effectiveness()` (`fail *= clamp(1.6-0.6*eff, 0.6, 1.6)`) and crime skill XP by `eff`. `core._effective_crime_risk` mirrors it so Underworld cards show true odds. Bust risk unchanged.
- **Reputation → Bank loan pricing + job gates:** new `game_engine.effective_loan_rate(p,cfg)` = `base * clamp(1.0-(rep-50)/125, 0.7, 1.4)` (rep50=base, rep100≈−30%, rep0≈+40%); used in `accrue_recurring` (charging) + `credit_profile.interest_daily` (display). `min_reputation` added to manager tier (store_manager 60, restaurant_manager 55, logistics_manager 60), synced to DB by `migrate_business_supply_chain`.
- **Legal Standing → Proactive police:** new `game_engine.maybe_police_event` (called in resolve_player). With `legal_reputation<40`, per-gh chance = `TUNE['police_event_per_hour'](0.03)*(40-legal)/40`, integrated over elapsed gh, only while free. Outcomes escalate with suspicion: detention (susp≥60 & legal<20), stop-and-search fine (susp≥40), else warning. New admin-tunable knob `police_event_per_hour`.
- **Social Status → VIP banking:** `credit_profile` adds `social_c = max(0,social-10)*20` to the limit + returns `vip` (social≥60) and `factors.social_standing`. `min_social_status` job gates unchanged.
- **Verification:** `python3 /app/backend/tests/test_logic_links.py` PASS (loan pricing, eff→crime factor, legal→police frequency); `verify_economy.py` + `verify_markets.py` still green; testing_agent iteration_40 backend 14/14 (100%), 0 issues, no regressions.

### NEXT (backlog, priority order)
- **P1 Admin.jsx refactor** (~2000 lines) → split into `src/pages/admin/` subcomponents (preserve @dnd-kit DnD).
- **P1 Race-based resource multipliers**: each Origin/Race gets a `resource_multipliers` map linked to `employee_engine` production + Admin editor.
- **P2** Phase 5 custom business products (admin data models); "Clear all" for dismissed applications; browser tab title flash on unread messages.
- **P3** "Business Insights" panel (best next move per venture).

## 2026-07-02 — Admin Refactor + P2/P3 Features + Most Wanted (COMPLETE ✓, iteration_41, 13/13 backend + full FE)
- **P1 Admin.jsx refactor:** split 1983-line `Admin.jsx` → 282 lines + 6 files under `src/pages/admin/` (shared, EconomyPanels, PlayerPanels, CityPanels, JobPanels, OverviewPanels). Mechanical byte-identical split; all 6 tab groups, DnD reorder, JSON editors, City Shops price% verified — no behavior change.
- **P2 Clear-all applications:** `POST /api/jobs/applications/dismiss-all` (removes finished statuses rejected/withdrawn/expired/hired, keeps pending/accepted, idempotent). Frontend "Clear all (N)" button in JobCenter "Your Applications" header, shown only when ≥1 rejected app (data-testid=clear-all-applications).
- **P2 Tab-title flash:** `GameContext` useEffect sets `document.title` = `(N) Kaeldor` on unread messages; alternates title when tab backgrounded; resets to `Kaeldor` at 0. Verified live ("(8) Kaeldor").
- **P3 Business Insights:** `employee_engine.business_insight(b,m)` → single highest-impact next move w/ $/day estimate (staff coverage / marketing / restock / trim / morale / healthy fallback). Injected into `GET /api/businesses/{id}` as `insight`. Frontend `BusinessInsight` panel in BusinessManage Overview (data-testid=business-insight-panel + insight-title/detail/gain/cta), CTA scrolls/navigates to relevant tab.
- **Enhancement Most Wanted:** `GET /api/underworld/most-wanted` → top-15 board ranked by police HEAT (`0.7*suspicion + 0.3*max(0,40-legal)*2.5`, clamped 0-100), wanted level heat//20+1 (1-5 stars), returns my_rank/my_heat/total_wanted. Frontend `MostWantedBoard`/`WantedStars` as a 3rd Underworld tab (tab-wanted), gated behind Underworld access.

### REMAINING
- **P2 Custom business products (groundwork)** — NOT STARTED. Needs a scope decision (data model design) before build. See open question to user.
- **P2/P3 backlog:** (all above P2/P3 items now done except custom products).
