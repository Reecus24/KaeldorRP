# Kaeldor UI / Tab Audit Notes

Audit of every sidebar tab against the new architecture (hourly wages, coverage supply chain,
linked stats). Status + action per tab.

| Tab | Status | Notes / Action |
|-----|--------|----------------|
| Dashboard | OK | Stat header shows Energy/Fatigue/Hunger/Mood/Stress/Health. No hygiene refs. |
| Home & Needs | OK | Housing tier, rest recovery, bills. Realistic. |
| Skills | OK | Skills gate jobs (meets_requirements) and feed effectiveness/XP; skill decay added. |
| Social | FIXED | OP rewards removed (loans→debt, favors non-cash, networking→leads). See SOCIAL_SYSTEM_LOGIC.md. |
| Messages | OK | Event feed; functional. |
| Daily Summary | FIXED | Now includes `taxes` (expense) and `savings_interest` (income) buckets. Uses hourly wages. |
| Job Center | FIXED | Job listings now show a "Requires:" chip row (skills, education, Legal Standing, Social, Suspicion, vehicle) plus lock reason. |
| Current Job | OK | Pay uses effectiveness; now shows net pay after tax + tips in the shift event. |
| Player Jobs | OK | Player-as-employee history; hourly wages. |
| Education | OK | Courses raise skills, cost money/time, raise social_status/legal on completion. |
| Shop | OK | Items show buy price + resell (verify buy/sell both visible — resell logic exists). |
| Bank & Loans | OK | Loan interest realistic; savings interest added for debt-free balances. |
| Real Estate | OK | Property grants social_status, rest recovery; sell/deposit refund logic present. |
| Vehicle Dealer | OK | Buy/sell prices; insurance/maintenance/wear present. |
| Buy a Business | OK | Market estimate uses ECONOMY_LOGIC.md coverage formula (1 worker, full opening). |
| My Businesses | OK | Supply-chain UI, Schedule tab (opening hours, shift roster, coverage), P&L correct. |
| Underworld | OK | Illegal jobs; catch risk tied to Criminal Suspicion + police_risk. Rewards scale with risk. |
| Police Record | OK | Reflects Legal Standing (legal_reputation) + record entries. |
| Hospital | OK | Health treatment costs money; discharge events. |
| Jail | OK | Sentences tied to crimes / suspicion; served over real time. |
| Leaderboard | OK | Net-worth based ranking. |
| Admin | ENHANCED | New Economy Sandbox, Tuning, editable Players panels. See ADMIN_SANDBOX.md. |

## Merger proposals (for user review, not executed)
- "Messages" and "Daily Summary" overlap slightly (both surface events). Could merge Daily Summary
  as a pinned card inside Messages. Left separate for now (Daily Summary is a P&L digest, Messages is a live feed).
- "Player Jobs" (you as an NPC's employee) could live as a tab inside "Job Center". Left separate to avoid churn.

## Remaining polish (low priority)
- Surface player Effectiveness value + its live pay impact on the Current Job screen (currently implicit).
- Show tax withholding breakdown on the Current Job pay preview (currently only in the completion event).

## Inventory Refactor & Asset Consolidation (2026-07-01)
- **New sidebar tab "Inventory"** (`/inventory`, `Backpack` icon) added under the Economy section, between Shop and Bank.
- **Central asset hub** (`/app/frontend/src/pages/Inventory.jsx`) consolidates:
  - **Equipment** panel (5 slots, equip/unequip) — moved out of Shop.
  - **Items** panel (consumables use / equippables equip) — moved out of Shop.
  - **Your Garage** panel (owned vehicles + sell/resale) — moved out of Vehicle Dealer.
- **Shop** (`Shop.jsx`) is now purchase-only (category-grouped item cards → "Buy to Inventory"); the inventory/equipment sections were removed.
- **Vehicle Dealer** (`VehicleDealer.jsx`) is now purchase-only ("For Sale" listings); the "Your Garage" owned-vehicles section was removed (now in Inventory).
- Backend unchanged — same endpoints (`/inventory`, `/equipment`, `/inventory/{id}/use|equip`, `/equipment/{slot}/unequip`, `/vehicles`, `/vehicles/{id}/sell`); this is a pure frontend re-org.

## City Shops enhancement — Opening Hours + Stock/Discount (2026-07-01)
- **Shop browser** (`Shop.jsx`): each store card now shows an Open/Closed pill + opening-hours range + a
  "Sale" pill when any item is discounted.
- **Inside a shop**: an Open/Closed status pill + hours; when CLOSED a red banner is shown and every buy
  button is disabled/labelled "Closed" (items still visible, grayed out). Each item shows "X in stock"
  (or "Out of stock"), a −N% sale badge with struck-through base price when discounted. Buy sends `store_id`.

## Job Center → Sector Browser (2026-07-01)
- **`JobCenter.jsx`** rebuilt into a two-level flow mirroring City Shops:
  - **Sector browser**: "Your Applications" panel + grid of sector cards (icon, description,
    "X listings · Y you qualify for", "Open Listings" button).
  - **Sector detail**: "Back to Sectors" + applications panel + the reusable `JobCard`s for only that
    sector's jobs (same requirements chips + real-time apply/accept/withdraw flow as before).
- No change to the apply/offer/accept backend flow; `/jobs` (flat list) retained for compatibility.

## Job Center → Dismiss Applications (2026-07-01)
- **`JobCenter.jsx` (`ApplicationsPanel`)**: each finished application (rejected / withdrawn / expired /
  hired — i.e. any non-active status) now shows a neon-cyan themed "x" **Dismiss** button
  (`data-testid="dismiss-application-<id>"`) that clears the entry from "Your Applications".
  Active applications (pending/accepted) keep only Accept/Withdraw (no dismiss).
- **Backend** (`routes/player.py`): `POST /api/jobs/applications/{app_id}/dismiss` — deletes the
  application record when its status is terminal; returns **400** for pending/accepted
  ("Withdraw an active application instead of dismissing it."), **404** if not found.
- Verified: curl (dismiss rejected → 200 + gone from list; re-dismiss → 404; dismiss pending → 400) and
  UI screenshot (x visible on rejected card, click removes it with "Application dismissed" toast).

## Action Card gains + Admin Markets panel (2026-07-01)
- `ActionCard.jsx`: added `skillChips()` — renders `action.skill_xp` as cyan "+N <Skill> XP" chips next to
  the existing stat `effects` chips. data-testid `action-gains-<actionId>` wraps the chip row.
- Admin `MarketsPanel` (Underworld & Finance ▸ Markets): per-asset price/base editors (`market-price-<id>`,
  `market-base-<id>`, `market-save-<id>`), drift/volatility readout, `market-reroll` button.

## Unread message red notification badges (2026-07-01)
- **World Chat button** (`ChatWidget.jsx`): added a solid red circle badge (#EF4444, white bold text,
  ring + glow, pulsing) at the button's top-right showing the count of unread world-chat messages
  (`chat-unread-badge`). Unread = world messages from other players newer than the viewer's last-seen
  timestamp (persisted per-player in localStorage `kaeldor_chat_seen_<id>`). Opening the widget marks all
  seen and hides the badge. The green online-count pill is retained (it shows people online, not unread).
- **Messages sidebar tab** (`Layout.jsx`): existing `msgUnread` badge restyled from `bg-neon-red/text-black`
  to vibrant `#EF4444` + white text + red glow (`nav-messages-badge`), hidden when 0.
- **Notification bell** restyled to the same vibrant-red + white-text badge for consistency.

## Job Center working hours on cards (2026-07-01)
- `JobCenter.jsx` JobCard now shows a "Working Hours" block (clock icon) listing every shift's window +
  duration BEFORE the Apply button — e.g. "Day Shift: 07:00–16:00 · 6h", using fmtWindow(start_window).
  High-risk shifts render red. Legacy int shift_options fall back to "Nh shift"; empty → "Flexible hours".
  data-testid `working-hours-<jobId>`. Verified: 3 blocks render per sector card (English only).

## Notification badge moved to LEFT of label (2026-07-01)
- World Chat button (`ChatWidget.jsx`): red unread badge changed from an absolute top-right corner badge
  to an inline element rendered FIRST (left of the MessageSquare icon / "World Chat" label), vertically
  centered via the button's flex + gap-2.
- Messages sidebar tab (`Layout.jsx`): `nav-messages-badge` moved from the row's right edge (after the
  flex-1 label) to sit right after the icon, before the label (left side).
- Both remain vibrant #EF4444 + white text; consistent left-side placement everywhere unread badges show.

## Fix: Social "Meet People" cooldown countdown (2026-07-02)
Location cards in Social ▸ Meet People (`Social.jsx` MeetPeople component) previously only showed the
static label "On cooldown" with no timer. Fixed: the backend already returns `cooldown_remaining`
(seconds) per location; the card now anchors it to an absolute end timestamp on load (`_cdEnd`) and a 1s
ticker renders a live countdown via `fmtDuration` (m:s / h:m:s — same format as work/activity timers),
inside the button and as a "Available in <time>" line (`data-testid location-cooldown-<id>`). When a
cooldown elapses the list auto-reloads so the "Go" button re-enables.

## Fix: Application outcome reason in "Your Applications" (2026-07-02)
The player JobCenter "Your Applications" list now shows the full custom outcome message for resolved
applications (`data-testid application-outcome-<id>`), matching the admin-tunable `success_response` /
`failure_response` (with {title}/{wage}/{reason}). Backend stores `outcome_message` on the application in
`resolve_npc_applications`; the UI falls back to the short reason if it's absent (older apps).
