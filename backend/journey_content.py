"""Owner-editable defaults for personal ambitions, branching stories and city occasions."""


def req(metric, target, label, href="/journey", since_start=False):
    return dict(metric=metric, target=target, label=label, href=href, since_start=since_start)


JOURNEY_GOALS = [
    {"id": "entrepreneur", "name": "Build something of your own", "description": "From your first savings to a business with customers.", "active": True,
     "milestones": [
         {"id": "runway", "name": "Make room for a plan", "requirements": [req("funds", 500, "Keep $500 available", "/jobs")], "rewards": {"xp": 30}},
         {"id": "connections", "name": "Meet your city", "requirements": [req("contacts", 2, "Get to know two people", "/social")], "rewards": {"xp": 50}},
         {"id": "open", "name": "Open your doors", "requirements": [req("businesses", 1, "Own a business", "/business-market")], "rewards": {"cash": 250, "xp": 100}},
         {"id": "customers", "name": "Find your first customers", "requirements": [req("business_revenue", 500, "Reach $500 in business sales", "/businesses")], "rewards": {"reputation": 3, "xp": 100}},
     ]},
    {"id": "professional", "name": "Become the person people rely on", "description": "Build experience, learn a specialty and establish a reputation.", "active": True,
     "milestones": [
         {"id": "shift", "name": "Your first payday", "requirements": [req("shifts", 1, "Complete a work shift", "/jobs")], "rewards": {"xp": 40}},
         {"id": "learn", "name": "Invest in yourself", "requirements": [req("courses", 1, "Finish a course", "/education")], "rewards": {"cash": 80, "xp": 60}},
         {"id": "reliable", "name": "A familiar face", "requirements": [req("shifts", 5, "Complete five shifts", "/current-job"), req("contacts", 2, "Meet two contacts", "/social")], "rewards": {"xp": 100, "reputation": 3}},
     ]},
    {"id": "independent", "name": "Find your own way", "description": "Make connections and build the freedom to choose your next move.", "active": True,
     "milestones": [
         {"id": "local", "name": "Learn the streets", "requirements": [req("actions", 3, "Finish three activities", "/home")], "rewards": {"xp": 30}},
         {"id": "story", "name": "A story worth telling", "requirements": [req("stories_completed", 1, "Finish a story", "/journey")], "rewards": {"xp": 60}},
         {"id": "freedom", "name": "Your next move is yours", "requirements": [req("funds", 1000, "Keep $1,000 available", "/jobs"), req("contacts", 3, "Meet three contacts", "/social")], "rewards": {"xp": 100, "social_status": 3}},
     ]},
]

STORY_ARCS = [{
    "id": "first_delivery", "name": "A favour on Mercer Street", "active": True,
    "description": "Maya's neighbourhood shop has lost its courier. A small favour could become your first business connection.",
    "contact": "Maya · Mercer Street", "start": "hello", "requirements": [],
    "nodes": [
        {"id": "hello", "title": "An unfinished delivery", "text": "Maya has orders waiting and nobody to deliver them. She asks what you can bring to the table.", "choices": [
            {"id": "hands", "label": "Offer your time", "detail": "Prove you can follow through with a small task first.", "next": "prove", "outcome": "Maya puts your name on her list. She wants to see you finish something before handing over the orders."},
            {"id": "organise", "label": "Offer to organise a courier", "detail": "Put down a $20 booking deposit and arrange outside help.", "cost": 20, "next": "partner", "outcome": "You reserve a courier. Maya is interested in your practical approach."},
        ]},
        {"id": "prove", "title": "Keep your word", "text": "Finish any activity after taking this task. You can eat, train or meet someone; Maya values follow-through.", "choices": [
            {"id": "done", "label": "Return with your task complete", "requirements": [req("actions", 1, "Finish one new activity", "/home", True)], "next": "route", "rewards": {"xp": 20}, "outcome": "You did what you said you would. Maya trusts you with the delivery."},
        ]},
        {"id": "partner", "title": "A dependable partner", "text": "The courier has a spare slot. Pay for the service, or use your existing driving experience to handle the route yourself.", "choices": [
            {"id": "hire", "label": "Book the courier", "cost": 25, "next": "promise", "outcome": "The courier confirms. You remain responsible for the customer's expectations."},
            {"id": "drive", "label": "Take the route yourself", "requirements": [req("skill:driving", 2, "Driving level 2", "/home")], "next": "promise", "outcome": "Your experience saves the courier fee."},
        ]},
        {"id": "route", "title": "Choose your approach", "text": "The direct route takes confidence behind the wheel. A local courier can help; preparing on foot also works.", "choices": [
            {"id": "drive", "label": "Use your driving experience", "requirements": [req("skill:driving", 2, "Driving level 2", "/home")], "next": "promise", "rewards": {"xp": 15}, "outcome": "You find a reliable route through the side streets."},
            {"id": "hire", "label": "Pay a local courier", "cost": 25, "next": "promise", "outcome": "The courier takes the heavy work. You handle the customer."},
            {"id": "prepare", "label": "Prepare a route on foot", "requirements": [req("actions", 1, "Finish one more activity to prepare", "/home", True)], "next": "promise", "outcome": "You take the slower, inexpensive route and arrive prepared."},
        ]},
        {"id": "promise", "title": "Set expectations", "text": "The customer asks for an extra stop. You can keep the original deal or spend $15 arranging the detour.", "choices": [
            {"id": "honest", "label": "Keep the agreed delivery", "next": "finish", "rewards": {"cash": 85, "reputation": 2}, "outcome": "You explain the limits clearly. The customer accepts the original plan and pays $85."},
            {"id": "extra", "label": "Arrange the extra stop", "cost": 15, "next": "finish", "rewards": {"cash": 105, "social_status": 2}, "outcome": "The extra stop is covered. You receive $105 and a warm recommendation."},
        ]},
        {"id": "finish", "title": "Something to build on", "text": "Maya asks how you would like to be paid for the organising work. She will remember the way you handled this job.", "choices": [
            {"id": "capital", "label": "Take a small cash bonus", "next": None, "rewards": {"cash": 35, "xp": 40}, "outcome": "You leave with seed money and your first completed delivery story."},
            {"id": "learn", "label": "Ask for a lesson in running a shop", "next": None, "rewards": {"skills": {"management": 60}, "xp": 60}, "outcome": "Maya walks you through stock and staffing. You gain management experience."},
        ]},
    ],
}]

for event_id, name, description, offset, skill, business_text in [
    ("street_festival", "Mercer Street Festival", "Stalls need supplies and local organisers need a hand.", 0, "cooking", "Supply the festival through your business"),
    ("repair_week", "Neighbourhood Repair Week", "Residents are repairing shops and homes together.", 24, "crafting", "Coordinate a repair contract through your business"),
    ("trade_fair", "Kaeldor Trade Fair", "Local businesses are meeting their next partners.", 48, "sales", "Represent your business at the fair"),
]:
    STORY_ARCS.append({
        "id": event_id + "_order", "name": name + ": a local opportunity", "description": description,
        "active": True, "event_only": True, "contact": "City noticeboard", "start": "plan", "requirements": [],
        "nodes": [
            {"id": "plan", "title": "Choose your contribution", "text": description + " Choose the approach that suits your character.", "choices": [
                {"id": "business", "label": business_text, "cost": 60, "requirements": [req("businesses", 1, "Own a business", "/businesses")], "next": "deliver", "rewards": {"cash": 140}, "outcome": "Your business arranges the supplies. The organiser pays $140 against the $60 order cost."},
                {"id": "specialist", "label": "Use your specialist knowledge", "requirements": [req("skill:" + skill, 3, skill.title() + " level 3", "/home")], "next": "deliver", "rewards": {"cash": 60, "skills": {skill: 25}}, "outcome": "Your specialist advice solves the organiser's immediate problem."},
                {"id": "help", "label": "Help with the preparation", "next": "help", "outcome": "You volunteer to get things ready. Complete an activity, then return to the organiser."},
            ]},
            {"id": "help", "title": "Make a contribution", "text": "Finish an activity after volunteering. There is no deadline once you have accepted this opportunity.", "choices": [
                {"id": "done", "label": "Report back", "requirements": [req("actions", 1, "Finish a new activity", "/home", True)], "next": "deliver", "rewards": {"cash": 40}, "outcome": "Your help earns a $40 thank-you."},
            ]},
            {"id": "deliver", "title": "A place in the neighbourhood", "text": "The work is done. Decide what you would like to take away from the experience.", "choices": [
                {"id": "reputation", "label": "Build your local reputation", "next": None, "rewards": {"xp": 40, "reputation": 2}, "outcome": "People remember your contribution."},
                {"id": "experience", "label": "Learn from the organisers", "next": None, "rewards": {"xp": 40, "skills": {skill: 40}}, "outcome": "You leave with practical experience for your next opportunity."},
            ]},
        ],
    })

CITY_EVENTS = [
    {"id": eid, "name": name, "description": desc, "active": True, "offset_hours": offset,
     "duration_hours": 24, "repeat_hours": 72, "arc_ids": [eid + "_order"]}
    for eid, name, desc, offset in [
        ("street_festival", "Mercer Street Festival", "Food, deliveries and local connections. Pick a contribution that suits you.", 0),
        ("repair_week", "Neighbourhood Repair Week", "Help local shops and homes get back into shape.", 24),
        ("trade_fair", "Kaeldor Trade Fair", "Turn your skills or your business into new opportunities.", 48),
    ]
]
