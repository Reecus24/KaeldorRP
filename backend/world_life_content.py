"""Owner-editable shared days, weather and encounters. No paid AI service."""
LIFE_CONFIG = {
    "daily_events_enabled": True, "travel_event_chance": 0.8,
    "chat_max_length": 1200, "chat_history_limit": 80, "chat_cooldown_seconds": 2,
    "status_max_length": 120, "presence_minutes": 3,
    "phases": [
        {"name": "Night", "from_hour": 0, "to_hour": 5, "description": "Lanterns glow in the dark. Somewhere beyond the road, an owl calls."},
        {"name": "Dawn", "from_hour": 5, "to_hour": 8, "description": "The first light reaches the roofs. Footsteps and distant bells wake the realm."},
        {"name": "Day", "from_hour": 8, "to_hour": 18, "description": "The roads are stirring. Voices, wheels and the sounds of work carry on the air."},
        {"name": "Dusk", "from_hour": 18, "to_hour": 22, "description": "Long shadows cross the paths. People light their hearths and trade the day's stories."},
        {"name": "Night", "from_hour": 22, "to_hour": 24, "description": "Doors close for the night. The last travellers follow the lights toward shelter."},
    ],
}


def choice(key, name, skill, success, setback, coins=(3, 9), difficulty=2, contribution=1, effects=None):
    return {"id": key, "name": name, "description": "Choose your approach and let your experience guide the roll.",
            "regions": [], "skill": skill, "difficulty": difficulty, "duration_minutes": 0,
            "energy_cost": 2, "money_cost": 0, "cooldown_minutes": 0, "requirements": {}, "supplies": {}, "active": True,
            "outcomes": [
                {"id": "success", "name": success, "success": True, "weight": 1, "coins": list(coins), "xp": 10,
                 "effects": effects if effects is not None else {"mood": 3}, "items": {}, "training": {}, "contribution": contribution},
                {"id": "setback", "name": setback, "success": False, "weight": 1, "coins": [0, 2], "xp": 4,
                 "effects": {"fatigue": 2}, "items": {}, "training": {}, "contribution": contribution},
            ]}


def day(key, name, description, choices, regions=(), weight=1, goal_name="Lend a hand together"):
    return {"id": key, "name": name, "description": description, "regions": list(regions), "weight": weight,
            "active": True, "choices": choices, "goal": {"name": goal_name, "target": 2, "reward_coins": 12}}


DAY_EVENTS = [
    day("harvest_tables", "The harvest tables", "Neighbours bring bread, apples and stories to long tables. There is room for two more pairs of hands.", [choice("carry", "Carry baskets to the tables", "fitness", "The feast is ready before the bells.", "A basket spills; the neighbours help you gather it."), choice("welcome", "Welcome the shy newcomers", "charisma", "A quiet family joins the feast.", "Your invitation is awkward, but you make room for them.")]),
    day("broken_well", "The well has fallen silent", "A snapped rope hangs over the old well. People queue with empty buckets, wondering who will fix it.", [choice("repair", "Repair the winding mechanism", "crafting", "The wheel turns and water rises.", "Your first knot slips, but the rope is secured."), choice("water", "Bring water from the stream", "survival", "You find a clean spring and fill the waiting buckets.", "The path is muddy; you return with half the water.")], goal_name="Restore the village water supply"),
    day("market_day", "A market of small wonders", "A caravan unfurls bright cloth beside the road. A trader promises unusual wares; a child swears one crate is moving.", [choice("bargain", "Help neighbours bargain", "sales", "You secure a fair deal for the village.", "The trader smiles and keeps the better end of the bargain."), choice("crate", "Investigate the moving crate", "survival", "A runaway hen becomes the market's most famous guest.", "The crate bursts open and feathers cover your coat.")]),
    day("lost_child", "A red ribbon in the trees", "A family is searching for a child who followed fireflies beyond the path. A ribbon catches on a thorn.", [choice("track", "Follow the small footprints", "survival", "You bring the child safely home.", "You lose the prints, then hear a familiar call."), choice("search", "Organise a search party", "charisma", "Your neighbours cover every path.", "The search is confused at first, but everyone helps.")], goal_name="Bring everyone home"),
    day("travelling_bard", "The bard's unfinished song", "A travelling bard knows the first half of an old legend. The second half, she says, belongs to the people who live here.", [choice("story", "Offer a tale from your travels", "charisma", "Your words become the song's final verse.", "The audience laughs kindly at the muddled ending."), choice("stage", "Build a small stage", "crafting", "The performance brings the square to life.", "The stage creaks, but holds through the final song.")], goal_name="Give the realm a story worth remembering"),
    day("river_debris", "What the river brought", "Broken planks and a sealed wooden chest wash ashore. The ferry keeper asks for help clearing the landing.", [choice("planks", "Salvage the useful planks", "shipbuilding", "The landing is safe and the planks will serve again.", "Some timber is rotten, but the landing is cleared."), choice("chest", "Trace the chest's owner", "survival", "The marks lead you to a grateful merchant.", "The marks are faded; you leave a notice at the dock.")], regions=("reedharbour",), goal_name="Reopen the landing"),
    day("watch_fire", "Smoke on the horizon", "A watchman sees smoke beyond the ridge. It may be charcoal burners, or a warning that should not be ignored.", [choice("scout", "Scout the ridge", "survival", "You return with a clear account of a harmless camp.", "Fog hides the ridge, but your patrol reassures the locals."), choice("watch", "Join the evening watch", "fitness", "Your steady presence lets the tired watch rest.", "Every rustle sounds threatening, but you hold your post.")]),
    day("quiet_kindness", "A quiet day, a small kindness", "No great crisis interrupts the day. An elder mends a cloak outside a doorway and leaves a stool beside them.", [choice("listen", "Sit and listen to an old story", "charisma", "You learn why a familiar road bears its name.", "You miss part of the story, but the company matters."), choice("mend", "Help mend the cloak", "crafting", "The old cloak will survive another winter.", "The stitching is crooked; its owner treasures it anyway.")]),
]


def road(key, name, description, choices, delay=0, weight=1):
    leave = choice("pass", "Leave it be and continue", "survival", "You leave the encounter behind.", "You leave the encounter behind.", (0, 0), 0, 0, {})
    leave.update(energy_cost=0)
    leave["outcomes"] = [{**leave["outcomes"][0], "xp": 0, "effects": {}}]
    return {"id": key, "name": name, "description": description, "regions": [], "weight": weight, "active": True,
            "delay_minutes": delay, "choices": choices + [leave]}


TRAVEL_EVENTS = [
    road("broken_cart", "A cart beside the road", "A wheel lies in the ditch. Its owner looks from the broken axle to your approaching footsteps.", [choice("fix", "Offer to repair the wheel", "crafting", "The cart rolls again; its owner pays you with thanks.", "You brace the axle well enough to reach the next village.", (6, 14))], 1),
    road("road_toll", "Strangers at the crossing", "Two strangers claim this crossing has a new toll. Their mismatched coats bear no lord's colours.", [choice("talk", "Talk your way past", "charisma", "They decide you are more trouble than coin.", "A tense exchange ends with you taking the long way round.", (0, 3)), choice("stand", "Stand your ground", "fitness", "Your confidence sends them back into the trees.", "You escape with bruised pride and a torn sleeve.", (1, 6))], 2),
    road("herbs", "Silver leaves by the path", "A patch of pale leaves catches the light. A healer once described a plant just like this.", [choice("gather", "Gather the leaves carefully", "medicine", "You identify a useful remedy and trade a little of it.", "Most of the leaves are ordinary weeds; you keep only the safe ones.")]),
    road("pilgrim", "The pilgrim and the milestone", "A pilgrim studies a worn milestone upside down. They are quite certain the abbey lies in two directions at once.", [choice("guide", "Guide the pilgrim", "survival", "You share a good road and a better story.", "One wrong turn becomes a memorable detour.")], 1),
    road("old_shrine", "An overgrown shrine", "Beneath ivy stands a small shrine with a bowl of rainwater. Someone has left a fresh flower there.", [choice("restore", "Clear the ivy from the stones", "crafting", "The old carving sees daylight again.", "The roots resist, but the doorway is clear.", (0, 4), effects={"mood": 8, "stress": -5})]),
    road("tracks", "Fresh tracks in the mud", "Unusual tracks cross your path, then vanish among the reeds. You hear a soft splash beyond the bank.", [choice("follow", "Read the tracks", "survival", "You spot an otter family and find a safer ford.", "The tracks fade, leaving only a story to tell.")]),
]

WEATHER = [
    {"id": "clear", "name": "Clear skies", "description": "Warm light falls across the paths; the roads are firm.", "weight": 5, "travel_multiplier": 1, "active": True},
    {"id": "rain", "name": "Soft rain", "description": "Rain taps on cloaks and roof tiles. The roads grow muddy.", "weight": 3, "travel_multiplier": 1.2, "active": True},
    {"id": "mist", "name": "Low mist", "description": "Mist softens the horizon. Travellers keep close to the milestones.", "weight": 2, "travel_multiplier": 1.15, "active": True},
    {"id": "wind", "name": "Wind from the hills", "description": "Banners snap and leaves tumble down the lanes.", "weight": 2, "travel_multiplier": 1.05, "active": True},
    {"id": "storm", "name": "Distant thunder", "description": "Thunder rolls beyond the hills. Sheltered roads are the wiser choice.", "weight": 1, "travel_multiplier": 1.4, "active": True},
]

LIFE_CONTENT = {name: (name, data) for name,data in [("world_day_events",DAY_EVENTS),("world_travel_events",TRAVEL_EVENTS),("world_weather",WEATHER)]}

for encounter in TRAVEL_EVENTS:
    if encounter["id"] == "road_toll":
        for approach in encounter["choices"]:
            for outcome in approach["outcomes"]:
                if not outcome["success"]:
                    outcome["effects"] = {"health": -6, "stress": 4}
