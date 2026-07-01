# Kaeldor Social System — Source of Truth

Goal: a gritty, realistic social layer. Relationships give information, referrals, small favors and
consequences — NOT infinite free money or flat stat buffs. Spam is limited by per-action cooldowns
and relationship decay.

## Model
Contacts (`db.contacts`) have: relationship_type (boss, coworker, mentor, landlord, business_contact,
friend, romantic, shady), `relationship_score` (0–100), `trust`, `last_interaction`. Scores decay
toward neutral over time when neglected (realistic drift). Every action has a `cooldown_minutes`
(real/game-time gated) preventing spam.

## Interaction outcomes (grounded)
| Action | Effect | Realism |
|--------|--------|---------|
| small_talk / call_text | small +relationship, minor mood; short cooldown | casual contact |
| hang_out / dinner | larger +relationship, costs cash/time | quality time |
| ask_favor | NO cash. Small stress relief; work contacts nudge job reliability; may share info | favors are help, not payouts |
| ask_loan | Cash you must REPAY — added to `debt`. Amount `40 + trust*3`, costs relationship | a real personal loan |
| ask_reference | One-off boost to a pending job application via referral | word-of-mouth |
| network (event) | Primary value = a NEW business contact OR a small (+4) word-of-mouth business-reputation bump; +1 social status. Diminishing (event cost + cooldown) | mixers, not money printers |
| gift | +relationship scaled by gift value & recipient taste | thoughtful gesture |

## Consequences
- Positive relationships → occasional referrals, tips (via the job tip system), info, small discounts.
- Negative/neglected → decay to neutral; low-score contacts refuse loans/favors (success roll fails).
- Romantic path exists but is costed and cooldown-gated.

## Anti-exploit rules
- No action grants repeatable free cash (loans are debt; favors are non-monetary).
- Networking business-rep bump reduced from +8 to +4 and no longer stacks satisfaction.
- Social status from networking reduced to +1 per success.
- Cooldowns on every action prevent "talk 50 times" farming; decay pulls ungrounded gains back.

## Links to other systems
- Social status feeds job tips and prestige-job requirements (see PLAYER_STATS_LOGIC.md).
- Referrals feed the employment application score.
- Loans feed the Bank/debt system (interest applies).

## Dynamic Meeting Locations & Encounters (Socials 3.0 — DB-driven)
Meeting places are now fully data-driven and admin-editable (no hardcoded lists).

**`locations` collection** (one doc per place):
- `id, name, category, desc, icon, active, order`
- `money_cost, duration_minutes, cooldown_minutes` — visit economics
- `requires_job` (bool), `suspicion_gain` (float, e.g. Backstreets +3)
- `success_base, charisma_factor` — meet-someone probability = `base + charisma_factor·(charisma/10)`, scaled by effectiveness
- `npcs: [{archetype_id, weight}]` — the encounter table (who you can meet + relative weight)

**Player flow**
- `GET /social/locations` → active locations with per-NPC normalized `chance` (%) shown on the card.
- `POST /social/visit/{id}` → validates active / requires_job / cooldown / cost, starts a blocking `social` activity with payload `{location_id}`.
- On completion `social_engine._visit_location` rolls: success → `random.choices` over `npcs` by weight → a new contact is created; the location's `suspicion_gain` is always applied.

**Admin management (Admin ▸ Locations)**
- `GET /admin/locations` → all locations (incl. inactive) + `encounters` (labels + normalized %) + full `archetypes` list.
- `POST /admin/locations`, `PUT /admin/locations/{id}`, `DELETE /admin/locations/{id}`.
- The admin editor assigns NPCs (archetype dropdown) + weight, and shows the live normalized meeting % for full transparency.

Meeting a `shady_dealer` here (e.g. at The Backstreets) is still the ONLY way to unlock the Underworld
(see UNDERWORLD_MARKETS.md).

## Location NPC Filter System (Socials 3.0 addendum)
Each NPC archetype now carries **`tags`** (Criminal / Wealthy / Corporate / Fitness / Social / Drifter)
and numeric **attributes** (`social_status`, `legal_standing`, `wealth`, all 0-100). See `ARCHETYPE_META` in seed_data.py.

Locations gain optional filter fields:
- `include_filtered` (bool) — when true, archetypes matching the filters are auto-added to the encounter pool.
- `category_whitelist` (list of tags) — empty = any; otherwise the archetype must share ≥1 tag.
- `min_attrs` / `max_attrs` ({attr: value}) — archetype attr must be ≥ min and ≤ max.
- `filter_weight` (float) — meeting weight applied to each filter-matched archetype.

**Resolution order (`social_engine.location_pool`)**
1. **Manual NPCs first** — every entry in `location.npcs` is added with its explicit weight and **BYPASSES all filters** (manual priority / dynamic override).
2. **Filtered NPCs** — if `include_filtered`, every archetype passing `_archetype_passes()` (whitelist + min/max thresholds) that isn't already manual is added with `filter_weight`.
3. The combined pool is weight-normalized to % and rolled with `random.choices` on a successful visit.

Example: *The Platinum Lounge* uses `include_filtered` + whitelist `[Wealthy, Corporate]` + `min_attrs {social_status: 60}` → auto-populates Manager/Wholesaler/Boss/Mentor/Business Contact. *The Backstreets* whitelists `[Criminal]` + `max_attrs {legal_standing: 40}` while still manually pinning the Shady Dealer.

**Admin UI (Admin ▸ Locations ▸ editor):** a "Auto-include NPCs matching filters" toggle reveals tag chips, min/max attribute inputs and a filter weight. Location cards show the active filter summary and mark filter-sourced NPCs with `*`.
