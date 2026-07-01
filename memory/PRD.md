# Kaeldor RPG — Product Requirements & Build Log

## Original Problem Statement
Browser-based **persistent, real-time life-simulation RPG** ("Kaeldor RPG"). A life-sim + business tycoon + persistent browser MMO. Player starts ordinary (little money, cheap apartment, low skills) and over real-time days/weeks can work, study, build skills, buy vehicles/homes, start businesses, follow legal or risky illegal paths, get rich or go bankrupt.

**Hard design rule:** NO action points, NO daily action limits, NO "end turn". Always playable. Balance comes from real-time action durations, fatigue, money, risk, cooldowns, health, stress, consequences, and opportunity cost. Offline time counts; jobs/education/business/legal/recovery continue while offline.

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
