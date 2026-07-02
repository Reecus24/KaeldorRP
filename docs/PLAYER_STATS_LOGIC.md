# Kaeldor Player Stats Logic — Source of Truth

Defines how every player standing stat is computed and what it is linked to. Any code that
reads/writes these stats MUST follow this document. UI text is 100% English.

Model fields (game_models.new_player): `reputation` (50), `legal_reputation` (75),
`criminal_suspicion` (0), `social_status` (10). All clamped 0–100.
UI labels: legal_reputation → "Legal Standing", criminal_suspicion → "Criminal Suspicion",
reputation → "Reputation", social_status → "Social Status".

---
## 1. EFFECTIVENESS (derived, not stored)
`effectiveness(p)` in game_engine.py — a 0.30–1.10 multiplier from current condition:
```
eff = (0.5 + 0.5*energy/100) * (0.6 + 0.4*(1-fatigue/100)) * (0.7 + 0.3*health/100)
if hunger > 80: eff *= 0.80
if stress > 80: eff *= 0.85
eff = clamp(eff, 0.30, 1.10)
```
Linked to:
- Job pay: `pay = hourly_wage * hours * eff`
- Action money reward: `reward * eff`
- Skill XP gain: `xp * eff` (and job xp `* hours * eff`)
- Accident risk: if `eff < 0.55`, 30% chance of a work injury (-8 health)
- Reliability drift: eff ≥ 0.7 → +2, eff < 0.5 → −3
- NPC worker productivity (business side): `cond = clamp(0.85 + 0.15*eff, 0.85, 1.05)`

---
## 2. REPUTATION (0–100, start 50) — "how known/trusted you are in the city"
Grows: +0.5 per completed job shift; social events; small on some crimes (negative).
Linked to:
- Job APPLICATION success (`evaluate_application`): `rep_bonus = (reputation-50)/250`.
- Job REWARDS (tips): customer-facing jobs (retail, food, logistics, office/management, trade)
  earn a reputation+status tip on top of wages:
  ```
  tip_rate = clamp((reputation-50)/100 * 0.15 + (social_status-10)/100 * 0.05, 0, 0.20)
  tip = round(base_pay * tip_rate, 2)   # base_pay = hourly_wage*hours*eff
  ```
- Business demand (business-side `reputation` field is SEPARATE, see ECONOMY_LOGIC.md).

---
## 3. LEGAL STANDING = legal_reputation (0–100, start 75) — "clean record ↔ criminal record"
Lowered by crime (−4 to −15). Raised by finishing courses (+2), lawful conduct, release (+5).
Linked to:
- Job APPLICATION: soft penalty when < 50 (`crime_pen`), and any job with `min_legal_reputation`
  is HARD-BLOCKED below that value ("Requires a clean record (Legal Standing N+)").
- Global hard block: cannot apply to ANY legal job while legal_reputation < 25.
- Promotions: blocked below `promotion_req.min_legal_reputation` (default 35).
- High-tier jobs declare explicit floors (office 50, managers 55–60).

---
## 4. CRIMINAL SUSPICION (0–100, start 0) — "police heat on you right now"
Decays passively: −1.5 per game-hour. Raised by crimes.
Linked to:
- JAIL/arrest risk on illegal jobs: `catch = police_risk * (1 + suspicion/150) * (1 - street*0.03)`.
- Job APPLICATION: employers run background checks — `susp_pen = suspicion/400` reduces the
  acceptance score, and jobs with `max_suspicion` are HARD-BLOCKED above it
  ("Lay low — you're under too much police attention (Suspicion must be ≤ N)").

---
## 5. SOCIAL STATUS (0–100, start 10) — "class / prestige / connections"
Raised by: housing tier (on purchase), courses (+4), premium clothing, social events.
Linked to (NEW — was previously vanity-only):
- Job REWARDS: contributes to the tip_rate above.
- Job APPLICATION: `status_bonus = (social_status-10)/300` improves acceptance for prestige roles.
- HARD requirement: prestige/management jobs declare `min_social_status`
  ("Requires social standing N+ — build status via housing, education & connections").

---
## Requirement keys supported by `meets_requirements(p, req)`
`skills{}`, `education[]`, `vehicle`, `min_reputation`, `min_legal_reputation`,
`min_social_status`, `max_suspicion`. Each returns a clear English reason when unmet.

## Examples
- Store Manager needs: management 5, management_course, `min_legal_reputation` 60, `min_social_status` 20.
  A player with a criminal record (legal 45) is blocked: "Requires a clean record (Legal Standing 60+)".
- A famous, well-housed barista (rep 90, status 40) working a 6h shift at $16/h with eff 1.0:
  base_pay = 16*6*1.0 = $96; tip_rate = (40/100*0.15)+(30/100*0.05)= 0.06+0.015 = 0.075;
  tip = $7.20; total ≈ $103.20.

## Student Welfare — needs frozen during education (2026-07-01)
While a player's `current_activity.kind == "course"` (actively studying), `decay_needs` applies a
**safety net** at the end of each tick: Health = Energy = Mood = 100, and Hunger = Fatigue = Stress = 0.
This guarantees long courses (e.g. multi-day) can never starve or collapse a student. Other modifiers
(equipment floors, suspicion cooldown, etc.) still run first; the welfare clamp is applied last.
Implementation: `game_engine.decay_needs(..., studying=<kind=='course'>)`, flag computed in `resolve_player`.

## Skill Decay — admin-tunable (2026-07-01)
"Use-it-or-lose-it": skills above **level 2** slowly lose XP while idle (working/training re-adds XP, so
actively used skills never degrade). The rate is an admin knob:
- Config key: `tuning.skill_decay_per_hour` (default **0.35** XP lost per idle game-hour).
- Read live from `game_models.TUNE` in `game_engine._decay_skills`.
- **Set to 0 to disable skill decay entirely.**
- Tune it in **Admin ▸ Gameplay Tuning ▸ Tuning ▸ Player Progression ▸ "Skill Decay Rate"**; changes
  apply on the next resolve tick (get_config refreshes TUNE every request).

## Criminal Suspicion — admin-tunable (2026-07-01)
- **Decay**: while not committing crimes, suspicion cools down by `tuning.suspicion_decay_per_hour`
  (default 1.5) per game-hour. Set to **0** to make suspicion permanent (never cools).
- **Gain**: suspicion gained from illegal acts is scaled by `tuning.suspicion_gain_mult` (default 1.0).
  Higher = harsher heat from crimes. Both are edited in Admin ▸ Gameplay Tuning ▸ Tuning ▸ Criminal Suspicion.

## Housing Mood Bonus now linked to Mood (2026-07-02)

Previously each housing tier defined a `mood_bonus` that was never applied (audit Point 5). Now
`decay_needs` receives the current home's `mood_bonus` (loaded in `resolve_player` before decay) and uses
it to shift the mood **baseline** the player's mood drifts toward:
```
baseline = clamp(mood_baseline(60) + housing.mood_bonus, 0, 100)
if mood < baseline:      mood += 0.5/gh  (capped at baseline)
elif mood > baseline+20: mood -= 0.3/gh
```
So a high-end home (e.g. penthouse `mood_bonus` +30 → baseline 90) pulls mood up over time, while a
cramped studio (negative bonus → baseline < 60) drags the mood ceiling down. Effect is continuous and
compounds over a day; verified a penthouse resident trends ~5–8 mood points higher than a no-bonus home
over 10 game-hours. Falls back to baseline 60 when no housing/bonus is set.
