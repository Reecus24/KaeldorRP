# Kaeldor development rules

## Owner-controlled gameplay

- Every new gameplay feature must expose its balance values through the Owner Sandbox. Use `game_models.DEFAULT_CONFIG` for simulation rates, thresholds, durations and probabilities; use a registered `seed_data.CONTENT_MAP` collection for activities, items and other editable content.
- Consume persisted settings in the engine and API. Never expose a setting that the actual calculation ignores. Preserve valid zero values; do not replace them with defaults through `value or default`.
- New settings must be visible in the generic Sandbox settings editor or have a dedicated editor. Explain units, ranges and whether changes affect existing activities or only newly started ones.
- Seed data supplies defaults only. Startup, migrations and deploys must preserve owner edits, intentionally empty lists and zero values. Backfill only missing fields. Do not silently rebalance existing content on restart.
- Validate finite numbers, safe identifiers and structural invariants on the backend. Keep advanced JSON editing available for future fields.

## Player experience and verification

- Keep player-facing UI in English and preserve the KAELDOR identity. State, countdowns and action availability must agree with server rules. Explain blocked actions and distinguish real time from game time.
- Test timing with a controlled clock: one offline interval and repeated polling must produce equivalent needs and activity outcomes. Cover configurable nondefault values and zero settings.
- Run `tests/verify_economy.py` and `tests/verify_markets.py` after engine/economy changes. Use `PYTHONPATH=backend` outside `/app`.
- Run deterministic tests against fakes or an isolated local database. Existing integration tests may contain old Emergent URLs; never run them against a live world by accident.
- Test both desktop and mobile for UI changes. Do not commit credentials or generated dependencies.
