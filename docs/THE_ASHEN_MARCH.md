# Kaeldor · The Ashen March

A persistent medieval fantasy life game. New characters begin as unemployed peasants with 80 coins, three travel breads, level-one skills and a rented village hayloft. The economy keeps its supply chains, wages, operating reserves and explicit personal-funds consent. Businesses are now stalls, inns, forges and guild workshops; mounts require fodder, stable dues and care. Letters require a courier seal or scribal kit. Exchange assets represent commodities and rare relics.

## Progression and play

The default world clock is real time. Skilled trades require seven real days since character creation, court work 21, guild leadership 45; skill and other requirements still apply. A starter can gather firewood, work the fields, study, take village contracts or swear a faction oath. Personal standing uses days, level and completed deeds together. There is no login streak or paid rank shortcut.

| Faction rank | Real days in faction | Earned renown | Completed service hours |
| --- | ---: | ---: | ---: |
| Recruit / Forest Runner | 0 | 0 | 0 |
| Man-at-Arms / Raider | 7 | 60 | 6 |
| Sergeant / Outlaw Veteran | 21 | 220 | 24 |
| Knight-Captain / Band Captain | 45 | 600 | 70 |
| Marshal / Thornlord | 90 | 1500 | 180 |

Choose the Crownwardens (army) or Thornbound (bandits), or remain independent. One oath at a time. Leaving resets that faction's renown and service and starts a 72-real-hour rejoin cooldown. Personal possessions and experience remain. Disabled or deleted factions issue no orders, and their members can still leave.

Expeditions are timed PvE encounters, not real-time action combat. Ten defaults include sparring, wolf hunts, patrols, caravan escorts/raids, an ogre assault and a wyrm. Choose a tactic and see victory odds, health loss on victory/retreat, energy, fatigue, supplies, rewards and cooldown before departure. Power uses player level, endurance, woodcraft and owned, equipped arms; armor reduces damage. Unequipped or unowned gear cannot contribute.

Departure consumes supplies and energy and reserves the cooldown immediately. It snapshots the mission, tactic, computed rewards/damage and server-side outcome. Later edits and equipment swaps do not reroll it. The public state hides the pending result. Completion is processed once under the existing player lease, including while offline. Injury can cause admission to the infirmary at the actual battle deadline. Cancelling or collapse before completion forfeits the reward and supplies, while keeping the cooldown. Defeat gives partial XP, no coin or renown. Completed faction missions give service hours; outlaw attempts also change suspicion and legal standing. The latest 20 reports are retained.

## Owner controls

**Owner Sandbox → Fantasy Realm** edits `realm_ranks`, `factions` and `expeditions`. The generic JSON editor supports creating, copying, editing, disabling and deleting entries. All fields are persisted; safe IDs, finite numbers, whole supply quantities, ascending faction ranks and required fields are validated server-side. Existing collections intentionally emptied by the Owner stay empty after restart.

**Gameplay Tuning → Config → realm** edits the power coefficients, victory-chance formula and bounds, tactics, defeat XP fraction and oath cooldown. Zero is valid for costs, rewards, damage, coefficients and cooldowns. A tactic has `name`, `chance_bonus` (−1…1), `damage_multiplier` and `reward_multiplier` (0…10). Additional authored fields are preserved.

- Expedition `duration_minutes` and `cooldown_minutes`: game minutes, converted at departure using the world clock. `gold`, `xp`, `renown`, `win_damage`, `loss_damage`, `energy_cost`, `fatigue_cost`, `min_health`, `suspicion`, `legal_change`: per encounter. `supplies`: map of item IDs to integer quantities, consumed on departure. `faction_id: null` allows independent contracts; otherwise `min_rank` is the zero-based rank index.
- Faction `ranks`: thresholds in real `days`, earned `renown`, completed game `service_hours`. All must be met. Rank edits affect existing membership on its next read; departing missions retain their reward amounts. `join_cost` and `min_legal` apply on joining.
- `realm_ranks`: personal titles require `min_days`, `min_level`, `min_deeds`. Deeds are completed activities, shifts, courses and expeditions. These titles are descriptive; individual jobs/workshops retain their own `requirements`, including `min_age_days` in real days.
- Items: `slot: weapon` or `armor`, plus nonnegative `combat_power` and `combat_armor`. Add new items to a shop's `items_config` to make them purchasable. Names and descriptions are editable too; update a description if its written bonus changes.
- Existing content editors still control jobs, activities, shops, crafts, housing, mounts, stories, economy and healing. Starter values are in Peasant Origins. Invalid or inactive origins cannot be selected through a direct API call.

## Upgrade of an existing world

`ashen_march_v1` runs once on startup. Before changing a catalogue entry, it retains the original in `realm_backups`. It converts only values that still equal the previous defaults, recursively preserving Owner changes, zeroes, empty arrays, deleted entries, custom names and prices. Stable internal IDs retain compatibility with inventory, courses, market holdings and saved references. Thus identifiers such as `smartphone`, `driving_license`, `stock` and `crypto` remain technical aliases for the courier seal, horsemanship, commodities and relics; they are not new modern-world mechanics.

Player money, owned assets, skills, job progress and accepted story progress are not reset. Untouched cached job/mount/product names and accepted story definitions are converted. Custom Owner prose is deliberately retained and can be rewritten in the Sandbox. New equipment and new collections have their own one-time seed receipts. Demo accounts are no longer created unless `SEED_DEMO_PLAYERS=1` is explicitly set.

The UI uses forest, parchment and brass colours, serif headings, a bundled original SVG landscape, themed icons and a new village overview. The public entry point no longer loads the Emergent runtime or its analytics. Navigation, care alerts, mobile needs disclosure and accessible controls remain available.

## Verification

Run the existing deterministic gameplay suites plus `backend/tests/test_realm.py`. Realm tests cover defaults and invalid authoring, real-day rank gates, actual gear ownership/slots, valid zero balance values, departure snapshots, single versus repeated offline resolution at 1×/12×, wounds and discharge, migration preservation and concurrent starts. Run the frontend suite/build and the economy/market verification scripts. Browser review must cover registration as a peasant, oath/expedition flow, inventory, shops, Owner editing and narrow layouts against an isolated database.
