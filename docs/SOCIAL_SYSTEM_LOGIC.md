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
