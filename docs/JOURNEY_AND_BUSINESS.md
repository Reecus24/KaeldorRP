# Journey and business comfort

Player entry point: **Your Journey** in Life navigation and on the dashboard.
Owner entry point: **Stories & Goals** in the Owner Sandbox.

## Content and persistence

- Three default ambitions connect money, employment, education, contacts and business ownership.
- Mercer Street's delivery story has branching solutions: preparation, driving experience or paid help.
- Three recurring city occasions open distinct stories with business, specialist and beginner approaches.
- An accepted story has no deadline. Players can review it while another activity is running.
  Hospital/jail prevent executing choices; progress is retained until release.
- Tracked ambitions and accepted stories snapshot their definitions. Template changes affect new starts.
  A player's choice history remains visible after completion.
- Costs, inventory consumption, skill gains, reputation changes and claim markers are saved together
  in the player document, under the same request lease as other player actions. A node/milestone ID
  accompanies every claim; stale/replayed requests cannot advance a different step.
- New collections have seed receipts. Disabling or deleting their defaults, including emptying an
  entire collection, survives a restart. Startup does not silently restore the deleted content.

## Authoring

The workshop provides name/description/enabled controls, duplication, schedule controls and a
read-through preview. **Edit all fields · JSON** preserves access to complete definitions.
Templates remain available even when a collection has been emptied.

Collections registered in CONTENT_MAP:

- journey_goals: id, name, description, active, milestones.
  A milestone has id, name, requirements, rewards.
- story_arcs: id, name, description, contact, active, event_only, start, nodes.
  A node has id, title, text, choices. A choice has id, label, detail, cost,
  consume_items, requirements, rewards, outcome and next (node ID, or null to finish).
- city_events: id, name, description, active, offset_hours, duration_hours,
  repeat_hours, arc_ids. All schedule fields use **real hours** relative to
  world_start_real. Events recur; each linked story is claimable once per occurrence.

Requirements are lists of objects with metric, target, label, href and optional since_start.
Supported metrics: funds (cash + bank), bank, shifts, actions, courses, businesses,
business_revenue (sales from currently owned businesses), contacts, level, reputation,
stories_completed, skill:SKILL_NAME, item:ITEM_ID.
since_start uses progress since the current chapter/milestone began, and supports the
monotonic counters shifts/actions/courses/stories_completed. Other requirements inspect
current holdings/values. Requirements are not consumed; use cost or consume_items for payment.

Rewards support cash, xp, skills (skill XP by ID), items (whole quantities by ID),
reputation, legal_reputation, social_status and criminal_suspicion.
Reputation values can be negative; cash/XP/items cannot. Skill XP follows the existing
game rule that also awards half as much character XP.
Story graphs must be acyclic and all next references must exist. IDs and numeric values
are validated. Entirely new effect types require implementation and matching validation.

Global settings:

- journey.max_active_stories: whole number, 1–20; existing runs are not cancelled if lowered.
- journey.city_events_enabled: hides new city offers; accepted event stories remain playable.

## Business operations

The overview distinguishes projected daily profit, actual business cash, operating reserve
and available payout. The reserve is:

    (forecast materials + forecast wages) × reserve days + outstanding business debt

Payouts transfer only cash above that reserve. Owners may deliberately set reserve days to zero;
outstanding debt is still retained. This is a planning estimate, not a solvency guarantee.
Each company has its own reserve_days; missing values use the current Owner default.

Owner-editable business_comfort settings (all in **game days**):

- default_reserve_days: initial/default operating buffer, 1.
- max_reserve_days: maximum allowed per-company reserve, 30.
- stock_warning_days: material coverage below which the overview suggests checking supplies, 0.5.
- finished_stock_days: limit for desired finished-goods buffer, 1; prevents endless overproduction.

Per-company controls retain auto-restocking and stock target (product-equivalent units).
Manual replenishment provides a quote with ingredient costs and funding sources. It applies
the same supplier discount as automatic buying. Personal funds require explicit opt-in;
the backend rejects a shortfall without it. Quotes are recalculated at confirmation.

Automatic restocking purchases balanced recipe quantities, supports free ingredients and
keeps cash needed for the elapsed interval's wages. Daily forecasts are recomputed from
current staff rather than stale stored projections; social wage discounts apply only to NPC
staff and never reduce contractual player wages.

The first release's city events open authored opportunities; they do not silently multiply
the whole city's prices, demand or crime risk. Economic simulation and cross-player business
transfers retain their existing multi-document transaction limitations.

Owner and employee requests acquire the same ordered business leases around their full
read/resolve/mutate/save operations. A worker's automatic progression cannot overwrite
an owner's payout or material purchase. This is serialization, not a multi-document
transaction or a guarantee of rollback after process failure.
