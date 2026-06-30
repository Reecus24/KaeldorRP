# Kaeldor RPG — Product Requirements & Build Log

## Original Problem Statement
Browser-based **persistent, real-time life-simulation RPG** ("Kaeldor RPG"). A life-sim + business tycoon + persistent browser MMO. Player starts ordinary (little money, cheap apartment, low skills) and over real-time days/weeks can work, study, build skills, buy vehicles/homes, start businesses, follow legal or risky illegal paths, get rich or go bankrupt.

**Hard design rule:** NO action points, NO daily action limits, NO "end turn". Always playable. Balance comes from real-time action durations, fatigue, money, risk, cooldowns, health, stress, consequences, and opportunity cost. Offline time counts; jobs/education/business/legal/recovery continue while offline.

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
- Admin dashboard: stats, content CRUD (jobs/actions/courses/items/housing/vehicles/business_types/illegal_actions/random_events) via JSON editor, config editor (time_scale + full JSON), players table.
- Dark neo-noir UI: Unbounded/Manrope/JetBrains Mono, neon accents, control-room grid, live countdowns, terminal event log, full data-testid coverage.
- **Verified:** 26/27 backend tests pass (1 expected skip); frontend core flows confirmed by testing agent. No critical bugs.

## Backlog / Next Tasks
- **P1 Business depth:** NPC employees + wages, hire/fire, inventory, set prices, business loans, multi-location expansion, profit/loss charts.
- **P1 Social system:** NPC contacts (friend/coworker/landlord/boss/partner/business/shady), relationship decay, gifts, effects on opportunities.
- **P2 Travel/City map** with travel-time blocking activities; richer random-event chains.
- **P2 Multiplayer:** chat, player marketplace, player-owned companies hiring players, factions/gangs, contracts.
- **P2 Polish:** brute-force login lockout + password reset (auth playbook), split `server.py` into routers, persist player only on mutation, add favicon (clears cosmetic 404), differentiate "Busy" vs disabled button styling, tighten CORS origins for production.

## Credentials
See `/app/memory/test_credentials.md`. Admin: admin@kaeldor.com / admin123.
