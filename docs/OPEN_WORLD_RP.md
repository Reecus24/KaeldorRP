# Kaeldor: a shared map and text role-playing world

The main screen is now the world atlas. The previous village overview remains at
`/village`; existing needs, jobs, businesses, faction expeditions and social tools
remain available. This is a map/text RP, with server-owned travel and checks. There
is no real-time 2D/3D movement layer.

## Playing together

Use separate accounts on the same running backend. **Together & chat** shows
companions' saved locations, online/away status, expected travel arrivals and
short player-written scene statuses. Markers on the atlas show who is at a place;
the header keeps your own location visible on other pages. Presence refreshes on
polling, not through a real-time socket. An offline traveller's arrival is marked
as awaiting their refresh until their server-owned activity has been settled.

Three conversation channels support speech, emotes and out-of-character planning:

- **At this location** can only be read/sent from the character's current region.
  Travellers must arrive first. It is a location conversation history, so a newly
  arriving character can read earlier posts there.
- **World / OOC** shares the existing World Chat stream.
- **Private** is a private planning channel available across locations without
  equipment. Only the two participants can query the conversation through the
  player API. Existing player blocks and chat mutes apply. The same threads are
  available under **Messages → Private RP**, with unread counts.

### Days that belong to everyone

At each game midnight, a new date becomes eligible for a shared weather roll and
one village event per visited location. They are generated lazily on the first
request, then stored under unique date/location IDs. Concurrent visitors see the
same result. Reloading, Owner definition edits and restarts do not reroll that
day. There is no backlog of automatic offline rewards or injuries from unvisited
days. Weather and time-of-day descriptions are shared atmosphere; NPCs can tell
you about today's local event when you ask about news.

The initial catalogue has eight village events, six road encounters and five
weather profiles. An event offers skill-based choices with disclosed chances,
coin ranges, XP, costs and effects. Each character chooses once per location/day.
The default village goal takes two contributions; both successful and unsuccessful
efforts normally contribute. Each contributor can claim the configured shared
reward once, at that location before the next game day. A cancelled timed choice
stays used and contributes nothing. Goal target zero disables the shared goal.

### Journeys with consequences

Departure draws an individual road encounter using the Owner's encounter chance
and weighted eligible pool. Weather multiplies base game minutes; an encounter
can add a delay. A zero-minute route remains instant. The journey snapshots its
duration, weather and encounter, so later balancing cannot change it mid-trip.
The departure countdown is authoritative; the pre-departure estimate includes
weather and warns about possible encounter delays.

On arrival, the encounter is presented as a story from that journey. Choose an
approach or leave it behind; settle it before starting another trip. These are
arrival encounters, not an interrupting combat screen halfway down a road. Choices
use the existing chronological action/injury engine and cannot be claimed twice.
Travel itself is remembered in **Journal → The roads you remember**; chosen checks
and their rolls appear in the dice chronicle. Characters travel independently.

### Owner controls for the living world

**Sandbox → Open World → Day Picker / Travel Picker / Weather Picker** provides
weight editing, enable/disable controls, contextual probabilities, preview-only
random rolls, new entries and complete JSON editing of choices and consequences.
Weight zero and empty catalogues remain disabled. A preview never changes a live
scene. Road event `regions` select destinations; day event `regions` select where
they can appear. An empty region list means anywhere.

**Gameplay Tuning → Config → world_life** controls `daily_events_enabled`,
`travel_event_chance` (0–1), RP message length/history/cooldown, scene status length,
presence minutes and time-of-day descriptions. Presence zero shows everyone away;
status length zero allows clearing but no new status text. Empty phase lists and
empty weather pools do not resurrect defaults. Daily flag changes apply when new
day snapshots are created. All new catalogues are registered in `CONTENT_MAP`;
future content uses the same validation, seeding and snapshot rules.

Characters share the same world catalogue, clock, NPC routines, player-founded
groups and world chat. The map lists other characters at your location. Select an
adjacent destination and travel; the activity bar shows the real countdown.
Finishing travel changes your location, including while offline. Cancelling keeps
you at the origin. Disabling a region moves stranded characters to an available
region on their next world request. An intentionally empty map stays empty.

The default world contains seven locations, six named NPCs, fourteen actions,
seven professions, five NPC quests and four founding charters. These are examples,
not an exhaustive list of what characters may become.

## Owner map editor

Open **Sandbox → Open World → Map & Routes**. The player atlas and the editor use
the same saved geometry; there is no separate hard-coded river or forest layer.

- **Places & routes:** create places, drag markers, edit coordinates (0–100%),
  names, descriptions and icons. Arrow keys move a focused marker by 1%; Shift
  moves by 5%. Save each location, including its outgoing routes. Routes are
  directed: add the return route at the other location for two-way travel. An
  arrow marks a one-way path. Times are game minutes; zero means instant travel.
- **Landscape:** add, move, resize or remove forests, mountain ranges, lakes and
  rivers. Each river bend is draggable. Width zero hides a feature; removing all
  terrain is valid. These shapes are decorative, while routes control travel.
- **Map style:** change the title, palette, compass and starting location for new
  characters. **Save map** saves landscape and style together. Location drafts
  are saved separately. The player map picks up saved edits on its next refresh.

Changes remain drafts until saved. Discard or reload restores the saved version.
Concurrent edits to the same location or appearance return a conflict rather than
silently overwriting another Owner's work. Keep IDs stable; hide a location with
the visibility toggle instead of deleting references used by NPCs and activities.
Advanced JSON remains available for locations and map appearance. Settings live in
`world_map`; places and route durations live in `world_regions`, and the starting
location in `world.start_region`. Existing journeys retain their departure rules.
Startup preserves zero values, empty terrain and Owner extensions.

## Free actions and the storyteller

In Explore, describe what your character intends to do. Choose a matching local
check to start it with your own narrative, or submit a new situation to the Owner.
The Owner opens **Sandbox → Open World → Storyteller Desk**, selects the proposal
and defines skill, difficulty, costs, duration and outcomes. Advanced JSON exposes
every rule. Approval grants no money or skills: it creates one check for that
player at the proposal's location. The player can review the odds before starting.
The check is consumed at start and cannot be repeated, including after cancelling.
A declined proposal can include the storyteller's explanation.

There is no automatic AI adjudicator yet. Free prose never directly grants powers,
items or money. Owners can turn recurring ideas into reusable World Actions.

## Dice and learning

Success probability is:

`clamp(base_success + (skill_level - difficulty) × chance_per_skill, min_success, max_success)`

These four values are under **Gameplay Tuning → Config → world**. Outcomes are split
into successful and unsuccessful pools; weights distribute probability within each
pool. A zero-weight outcome never occurs. If only one pool has positive weight,
that pool receives the whole probability. All weights zero is invalid.

The server uses `SystemRandom` to pick one outcome, then rolls the inclusive integer
coin range. The action snapshots its selected outcome, costs, reward, XP, effects
and odds at departure. Pending dice are hidden from the public player state.
Completion applies the result once through the existing chronological activity
engine. The chronicle shows the sampled roll and original probabilities; it is an
audit trail, not a cryptographic fairness proof. Cancelling forfeits paid costs and
keeps the cooldown. Injuries use the existing infirmary timeline.

Skill XP uses the existing configurable level thresholds. Qualifications can
require both skill levels and successful lesson counts. Teachers must be at the
same location when a lesson starts. Choosing a profession changes your title; it
does not restrict other qualifications or substitute for actual training.

## Character creation

The default creation mode is a single random roll on submission. Existing
characters are not reset. **Origin Picker** controls weighted origins, inclusive
age/coin/skill/need ranges, inventory, prior lesson counts and optional weighted
starting professions. Skills are absolute levels, not bonus levels. Starting
professions are drawn only from choices whose qualifications the rolled character
already meets; otherwise the character starts without a profession. No origin
or profession forces a paid job contract. Weight zero excludes an entry.

Set `world.random_creation` to false to use the previous selectable origins. The
old **Peasant Origins** editor affects that mode; **Origin Picker** affects random
mode. An empty or wholly disabled picker blocks new creation rather than restoring
defaults. Concurrent creation requests cannot reroll an existing character.

## NPCs and memory

NPCs have editable personalities, aims, home regions and game-clock schedules.
Schedule entries use `from_hour`, `to_hour`, and `region`; overnight ranges are
supported, and the first matching entry wins. No match means the home region.

**Dialogue currently uses written responses, not a language model.** There are no
AI service calls, API charges, model downloads or provider credentials. The future
self-hosted model can replace the small boundary in `npc_dialogue.py`. It must
remain separate from authoritative checks and rewards.

Memories are stored per NPC and player: first meeting, visit count and the latest
configured number of conversation turns. Completed quest facts are kept separately
and remain available after conversation history is trimmed. A memory-turn limit
of zero retains no dialogue text on subsequent conversations. No player's private
conversation is used in another player's NPC dialogue. Owners can inspect and
edit memories through **Characters & Memories**.

NPC quests are accepted and turned in at that NPC's current location. Acceptance
snapshots the objective and reward; only subsequent matching actions count.
Successful-only objectives ignore failed checks. Claiming twice cannot pay twice.
If an Owner disables the quest giver, re-enable that NPC before turning in an
already accepted quest. Removing an offer does not erase accepted progress.

## Founding factions and businesses

**Our mark** lets qualified players establish named factions, trading houses,
smithies and shipyards. Each has a location, founder, purpose and open/closed
membership. Other players can join or leave; only the founder edits the charter.
Characters may belong to multiple independent groups. These memberships are
separate from the Crownwarden/Thornbound service oath.

Members of a smithy, shipyard or trading house can take appropriate commissions
there, including at another permitted founding location. Each member still needs
their own qualifications. Commission rewards go to the worker. These player-led
charters do not yet have a shared treasury, automatic production, territory control
or pooled construction resources. Existing managed businesses continue to provide
staffing, inventory, restocking and operating cash through **Managed businesses**.

Founding cost and the charter are saved together in the founder's player document.
Members are stored with their own character. The shared roster exposes only names
and IDs, not another character's funds, inventory or memories.

## Owner controls and extension

| Sandbox area | Editable content |
| --- | --- |
| Map & Routes | Locations, coordinates from 0–100%, directed links, travel game minutes, prerequisites |
| People & Routines | Names, roles, personality, goals, greetings and schedules |
| Actions & Dice | Regions, skills, difficulties, durations, costs, supplies, outcome weights and effects |
| NPC Quests | Giver, objective action, count, success requirement, prerequisites and coin reward |
| Learned Professions | Cumulative skill, training and profession prerequisites |
| Skills | Stable skill IDs and visible names; new skills accrue XP without engine changes |
| Founding Charters | Group kind, cost, permitted regions and qualifications |
| Origin Picker | Weights, ranges, prior training, inventory and possible starting titles |
| Characters & Memories | Current region/title, skill levels/XP, lesson counts and NPC conversations |
| Config → world | Success formula, start region, creation mode and player limits |

Use stable IDs for references. Disabling content prevents new offers; deleting it
does not resurrect it on restart. Seed receipts preserve intentionally empty
collections. Valid zero values remain zero. Started actions and accepted quests
keep their snapshots. Structural validation rejects invalid ranges, unsafe IDs,
non-finite numbers, duplicate outcome IDs and impossible probability settings.
Circular profession prerequisites fail closed with an explanatory message.

In Characters & Memories, skills are merged by ID to retain existing core skills;
training and memories are replaced exactly, so `{}` clears them. Elapsed play is
settled before applying Owner changes. A title edit never bypasses qualifications.

Adding a profession or NPC is content work. Introducing an entirely new effect
type or simulation system still requires code; arbitrary JSON cannot implement a
new game mechanic by itself.

## Verification and preview limits

The isolated backend suite covers weighted boundaries and zero settings, learning
gates, NPC memory isolation, creation races, proposal permissions, single-use
approval, quest replay, shared founding access, persistence and 1×/12× offline
versus repeated injury/recovery resolution. Browser checks cover the map, dialogue,
Owner approval, custom completion, learning gates, founding and mobile layouts.

The current localhost preview uses isolated demonstration data. Public hosting and
production MongoDB operation have not been deployed or load-tested in this change.
Long-term progression, commission earnings and retention need real playtesting.
