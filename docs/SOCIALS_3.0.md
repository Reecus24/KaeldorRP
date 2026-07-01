# Socials 3.0 — "The Roleplay Meeting" (source of truth)

## Core principle
NPCs are **not** automatically known. A player starts with an **empty social circle**
(the old auto-seeded "magic circle" of friends/family/mentor/love-interest is gone).
People are met **only** through location-based actions, then relationships are built and,
for professional contacts, converted into **permanent business perks**.

## Meeting people (location actions — Social ▸ Meet People)
Each is a real-time, blocking activity with a money cost and a success roll
(base + charisma). On success you meet one NPC of a place-appropriate archetype.

| Action           | Cost | Meets (weighted)                         |
|------------------|------|------------------------------------------|
| Go to a Bar      | $25  | Bar Regular (50%), Manager (25%), Wholesaler (25%) |
| Go to the Gym    | $15  | Athlete (60%), Gym Coach (40%)           |
| Network at Work  | $0   | Coworker (65%), Manager (35%) — **requires a job** |

Contacts you inherently know are still auto-created: your **Boss** (on taking a job) and
your **Landlord** (on renting). Colleagues, wholesalers, friends, etc. must be met.

## Professional perks (Socials 2.0, unlocked in 3.0)
Perk-granting archetypes carry a `perk` definition:

| Archetype        | Perk type          | Step | Effect                                   |
|------------------|--------------------|------|------------------------------------------|
| Industry Manager | `wage_discount`    | 5%   | Reduces NPC staff wages on all businesses |
| Wholesale Supplier | `material_discount` | 5% | Reduces material cost on all businesses   |

- Unlock via the **Talk Business** (`network_pro`) action on that contact.
- Requires **Trust ≥ 60** and **Relationship ≥ 50**. Each contact grants its perk **once**.
- Perks are **permanent**, **player-level**, and **stack up to a hard cap of 20%** per type
  (`p.social_perks = {"wage_discount": x, "material_discount": y}`).

### Where perks apply (backend)
- `employee_engine.resolve_business` loads the owner's `social_perks` and computes
  `wage_mult = 1 - min(0.20, wage_discount)` and `material_mult = 1 - min(0.20, material_discount)`.
- Wage discount applies to **NPC** wages only (player-employee contracts are unaffected).
- Material discount applies to auto-restock purchase cost and the P&L forecast.
- `_day_rates(..., wage_mult, material_mult)` reflects both in the on-screen projection.

## Removed (too "gamey")
- `give_gift`, `ask_favor`, `ask_loan` actions and the gift picker flow.
- Auto-seeded starter friends/family/mentor/love-interest/business contacts.

## Retained relationship actions
small_talk, call_text, apologize, ask_reference, hang_out, help_problem,
invite_date (romance), meet_shady (underworld), and **network_pro** (professional).
