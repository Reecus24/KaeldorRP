from emergentintegrations.llm.chat import LlmChat, UserMessage
import os
import uuid
import logging

logger = logging.getLogger(__name__)


class GameMasterEngine:
    def __init__(self):
        self.api_key = os.environ.get('EMERGENT_LLM_KEY')

    def _base_rules(self):
        return """CORE GM RULES:
- Never narrate player internal thoughts as facts.
- Never decide a player's chosen action for them.
- Narrate consequences of declared actions faithfully.
- Be strict about causality and continuity.
- Track injuries, resources, promises, and social fallout.
- Hidden information stays hidden unless revealed naturally.
- Failure creates new complications, not dead ends.
- Success has plausible consequences too.
- The world feels active even when players hesitate.
- NPCs have distinct motives, personalities, and memory.
- Do not soften outcomes to be nice. Do not always protect players."""

    def _tone_guide(self, tone: str) -> str:
        guides = {
            "grimdark": "Tone: Grimdark. The world is harsh, unforgiving, and morally grey. Suffering is common. Hope is rare and hard-won. Describe visceral details, oppressive atmospheres, and the weight of every choice.",
            "realistic": "Tone: Realistic. Events follow logical cause and effect. People behave as real people would. No dramatic conveniences. Ground descriptions in sensory detail and practical consequence.",
            "heroic": "Tone: Heroic. The world rewards courage and conviction. Grand moments are possible. Still maintain stakes and cost, but allow triumph to feel earned and meaningful.",
            "mysterious": "Tone: Mysterious. Lean into the unknown, the uncanny, the half-seen. Descriptions should evoke wonder and unease. Leave questions unanswered. Hint more than reveal."
        }
        return guides.get(tone, guides["realistic"])

    def _build_context(self, campaign, scene, npcs, recent_events):
        ctx = f"CAMPAIGN: {campaign.get('name', 'Unnamed')}\n"
        ctx += f"WORLD: {campaign.get('world_summary', 'Not yet defined')}\n"
        if scene:
            ctx += f"\nCURRENT SCENE:\n"
            ctx += f"  Location: {scene.get('location', 'Unknown')}\n"
            ctx += f"  Time: {scene.get('time_of_day', 'Unknown')}\n"
            ctx += f"  Description: {scene.get('description', '')}\n"
            threats = scene.get('active_threats', [])
            if threats:
                ctx += f"  Active Threats: {', '.join(threats)}\n"
            hooks = scene.get('unresolved_hooks', [])
            if hooks:
                ctx += f"  Unresolved Hooks: {', '.join(hooks)}\n"
            ctx += f"  Tension Level: {scene.get('tension_level', 1)}/10\n"
        if npcs:
            ctx += "\nKNOWN NPCs:\n"
            for npc in npcs[:15]:
                ctx += f"  - {npc['name']} ({npc.get('role', 'Unknown')}"
                if npc.get('faction'):
                    ctx += f", {npc['faction']}"
                ctx += f"): {npc.get('personality_traits', '')}. "
                ctx += f"Motivation: {npc.get('motivation', 'Unknown')}. "
                ctx += f"Status: {npc.get('status', 'alive')}. "
                ctx += f"Trust: {npc.get('trust_level', 0)}\n"
        if recent_events:
            ctx += "\nRECENT EVENTS (chronological):\n"
            for ev in recent_events[-15:]:
                ctx += f"  - [{ev.get('event_type', 'event')}] {ev.get('summary', '')}\n"
        return ctx

    async def narrate(self, campaign, scene, npcs, recent_events, action, chat_history):
        tone = campaign.get('tone', 'realistic')
        system = f"""You are the Game Master (GM) for a private tabletop roleplay session.
{self._base_rules()}
{self._tone_guide(tone)}

{self._build_context(campaign, scene, npcs, recent_events)}

INSTRUCTIONS:
- Narrate the outcome of the player's declared action.
- Describe what happens in the world, what the player perceives, and what consequences unfold.
- Stay in character as the omniscient narrator. Do NOT break the fourth wall.
- Keep responses between 2-6 paragraphs. Be vivid but concise.
- End with an open situation that invites the player's next decision."""

        history_text = ""
        for msg in chat_history[-10:]:
            prefix = "PLAYER" if msg.get('role') == 'user' else "GM"
            history_text += f"{prefix}: {msg.get('content', '')}\n\n"

        prompt = f"{history_text}PLAYER ACTION: {action}" if history_text else f"PLAYER ACTION: {action}"

        chat = LlmChat(
            api_key=self.api_key,
            session_id=f"gm-{uuid.uuid4().hex[:8]}",
            system_message=system
        ).with_model("openai", "gpt-5.2")

        response = await chat.send_message(UserMessage(text=prompt))
        return response

    async def npc_speak(self, campaign, npc, scene, recent_events, dialogue_or_intent, chat_history):
        tone = campaign.get('tone', 'realistic')
        system = f"""You are roleplaying as the NPC "{npc['name']}" in a tabletop RPG session.
{self._tone_guide(tone)}

NPC PROFILE:
  Name: {npc['name']}
  Role: {npc.get('role', 'Unknown')}
  Faction: {npc.get('faction', 'None')}
  Personality: {npc.get('personality_traits', 'Not defined')}
  Motivation: {npc.get('motivation', 'Unknown')}
  Secrets: {npc.get('secrets', 'None')}
  Trust toward players: {npc.get('trust_level', 0)} (-100 hostile to +100 loyal)
  Status: {npc.get('status', 'alive')}
  Voice/Style: {npc.get('voice_style', 'Default')}

{self._build_context(campaign, scene, [], recent_events)}

INSTRUCTIONS:
- Respond in-character as {npc['name']}.
- Stay consistent with the NPC's personality, motives, and knowledge.
- The NPC does NOT know things they shouldn't know.
- Include brief action/body language descriptions in *italics* between dialogue.
- Keep the response concise (1-3 paragraphs)."""

        history_text = ""
        for msg in chat_history[-6:]:
            prefix = "PLAYER" if msg.get('role') == 'user' else npc['name'].upper()
            history_text += f"{prefix}: {msg.get('content', '')}\n\n"

        prompt = f"{history_text}PLAYER SAYS/DOES: {dialogue_or_intent}" if history_text else f"PLAYER SAYS/DOES: {dialogue_or_intent}"

        chat = LlmChat(
            api_key=self.api_key,
            session_id=f"npc-{uuid.uuid4().hex[:8]}",
            system_message=system
        ).with_model("openai", "gpt-5.2")

        response = await chat.send_message(UserMessage(text=prompt))
        return response

    async def resolve_check(self, campaign, scene, roll_result, difficulty, context):
        tone = campaign.get('tone', 'realistic')
        system = f"""You are the Game Master narrating the result of a skill/situation check.
{self._tone_guide(tone)}

{self._build_context(campaign, scene, [], [])}

INSTRUCTIONS:
- The player attempted: {context}
- Difficulty: {difficulty}
- Roll result: {roll_result['total']} (expression: {roll_result['expression']})
- Critical success: {roll_result['is_critical']}
- Critical failure: {roll_result['is_fumble']}
- Narrate the outcome in 1-2 paragraphs.
- Success means achieving the goal with plausible consequences.
- Failure means complications, not dead ends.
- Critical results should be dramatic and memorable."""

        chat = LlmChat(
            api_key=self.api_key,
            session_id=f"check-{uuid.uuid4().hex[:8]}",
            system_message=system
        ).with_model("openai", "gpt-5.2")

        response = await chat.send_message(UserMessage(text=f"Resolve this check: {context} (rolled {roll_result['total']} against {difficulty})"))
        return response

    async def generate_recap(self, campaign, events):
        system = f"""You are the Game Master writing a session recap.
Campaign: {campaign.get('name', 'Unnamed')}
Tone: {campaign.get('tone', 'realistic')}

INSTRUCTIONS:
- Summarize the session events concisely but usefully.
- Highlight key decisions, consequences, and unresolved threads.
- Keep it under 300 words.
- Write in past tense, third person."""

        events_text = "\n".join([f"- [{e.get('event_type', 'event')}] {e.get('summary', '')} | {e.get('details', '')[:100]}" for e in events[-30:]])

        chat = LlmChat(
            api_key=self.api_key,
            session_id=f"recap-{uuid.uuid4().hex[:8]}",
            system_message=system
        ).with_model("openai", "gpt-5.2")

        response = await chat.send_message(UserMessage(text=f"Events to summarize:\n{events_text}"))
        return response
