from emergentintegrations.llm.chat import LlmChat, UserMessage
import os
import uuid
import logging
import json
import re
import random

logger = logging.getLogger(__name__)

GERMAN = """SPRACHE: Du antwortest IMMER auf Deutsch. Alle Erzählungen, NPC-Dialoge, Szenenbeschreibungen, Konsequenzen, Regelauflösungen und Zusammenfassungen müssen in natürlichem, flüssigem Deutsch geschrieben sein."""


class GameMasterEngine:
    def __init__(self):
        self.api_key = os.environ.get('EMERGENT_LLM_KEY')

    def _chat(self, prefix, system):
        return LlmChat(api_key=self.api_key, session_id=f"{prefix}-{uuid.uuid4().hex[:8]}", system_message=system).with_model("openai", "gpt-5.2")

    def _rules(self):
        return """GRUNDREGELN DES SPIELLEITERS:
- Erzähle niemals die inneren Gedanken eines Spielers als Tatsachen.
- Entscheide niemals die gewählte Handlung eines Spielers.
- Erzähle Konsequenzen erklärter Handlungen treu.
- Sei streng bei Kausalität und Kontinuität.
- Verfolge Verletzungen, Ressourcen, Versprechen und soziale Auswirkungen.
- Verborgene Informationen bleiben verborgen bis natürlich offenbart.
- Misserfolg schafft neue Komplikationen, keine Sackgassen.
- Erfolg hat plausible Konsequenzen.
- Die Welt fühlt sich lebendig an, selbst wenn Spieler zögern.
- NPCs haben eigene Motive, Persönlichkeiten und Erinnerungen.
- Ergebnisse nicht abschwächen um nett zu sein. Spieler nicht immer beschützen.
- Kein KI-gefälliges Verhalten, kein übertriebenes Lob, keine künstliche Sanftheit.
- Atmosphärisch, streng, konsequent, immersiv."""

    def _tone(self, t):
        return {"grimdark": "Ton: Grimdark. Hart, unversöhnlich, moralisch grau. Leid ist alltäglich. Hoffnung selten. Viszerale Details, bedrückende Atmosphäre, Gewicht jeder Entscheidung.",
                "realistic": "Ton: Realistisch. Logische Ursache und Wirkung. Keine dramatischen Zufälle. Sensorisches Detail, praktische Konsequenz.",
                "heroic": "Ton: Heroisch. Mut wird belohnt. Große Momente möglich. Einsatz und Kosten bleiben, Triumph fühlt sich verdient an.",
                "mysterious": "Ton: Mysteriös. Das Unbekannte, Unheimliche, Halbgesehene. Staunen und Unbehagen. Mehr andeuten als offenbaren."
                }.get(t, "Ton: Realistisch. Logische Ursache und Wirkung.")

    def _ctx(self, campaign, scene, npcs, events, pcs=None):
        c = f"KAMPAGNE: {campaign.get('name','?')}\nWELT: {campaign.get('world_summary','')}\n"
        if scene:
            c += f"\nSZENE:\n  Ort: {scene.get('location','?')}\n  Zeit: {scene.get('time_of_day','?')}\n  {scene.get('description','')}\n"
            if scene.get('active_threats'): c += f"  Bedrohungen: {', '.join(scene['active_threats'])}\n"
            if scene.get('unresolved_hooks'): c += f"  Offene Fäden: {', '.join(scene['unresolved_hooks'])}\n"
            c += f"  Spannung: {scene.get('tension_level',1)}/10\n"
        if pcs:
            c += "\nSPIELERCHARAKTERE:\n"
            for p in pcs:
                c += self._pc_block(p)
        if npcs:
            c += "\nNPCs:\n"
            for n in npcs[:15]:
                c += f"  - {n['name']} ({n.get('role','?')}, {n.get('faction','-')}): {n.get('personality_traits','')}. Motivation: {n.get('motivation','?')}. Status: {n.get('status','lebendig')}. Vertrauen: {n.get('trust_level',0)}\n"
        if events:
            c += "\nLETZTE EREIGNISSE:\n"
            for e in events[-15:]:
                c += f"  - [{e.get('event_type','?')}] {e.get('summary','')}\n"
        return c

    def _pc_block(self, p):
        b = f"  [{p.get('character_name','?')}] (Spieler: {p.get('discord_user_id','')})\n"
        for k, l in [('short_description','Beschreibung'), ('personality_traits','Persönlichkeit'), ('background','Hintergrund'),
                      ('strengths','Stärken'), ('weaknesses','Schwächen'), ('skills','Fähigkeiten'),
                      ('injuries_conditions','Verletzungen'), ('inventory','Inventar'), ('faction_ties','Fraktion'),
                      ('reputation','Ruf'), ('current_location','Ort'), ('goals','Ziele'), ('fears','Ängste'),
                      ('gm_secrets','[GM GEHEIM]'), ('obligations_notes','Verpflichtungen')]:
            if p.get(k): b += f"    {l}: {p[k]}\n"
        return b

    # ── Message-Driven Response ──

    async def message_driven_response(self, campaign, scene, npcs, events, pcs, msg, active_pc, history):
        tone = campaign.get('tone', 'realistic')
        pre_roll = random.randint(1, 20)
        pc_detail = self._pc_block(active_pc) if active_pc else ""
        pc_name = active_pc.get('character_name', '?') if active_pc else 'Unbekannt'

        system = f"""Du bist der Spielleiter einer privaten Tabletop-Rollenspiel-Sitzung.
{GERMAN}
{self._rules()}
{self._tone(tone)}
{self._ctx(campaign, scene, npcs, events, pcs)}

DER HANDELNDE CHARAKTER:
{pc_detail}

REAKTIONSLOGIK:
Du erhältst eine Spielernachricht aus dem IC-Kanal. Entscheide ob eine Spielleiter-Reaktion angemessen ist.

Antworte NUR wenn die Nachricht:
- Eine Handlung mit unsicherem Ausgang beschreibt
- Eine Weltreaktion auslöst (Umgebung, Geräusche, Wetter, Gerüche)
- Eine NPC-Reaktion erfordert
- Gefahr, Spannung oder Eskalation erzeugt
- Einen Szenenwechsel bewirkt
- Eine Regelauflösung erfordert (Kampf, Überzeugung, Heimlichkeit)
- Wichtige Konsequenzen offenbart
- Eine dramatische Situation schafft

Antworte NICHT wenn:
- Nur innerer Monolog ohne Handlung
- Einfache Beschreibung ohne Konsequenz
- Keine fiktional sinnvolle Weltreaktion angemessen
- Der Spieler nur Position beschreibt ohne zu handeln

Wenn KEINE Antwort nötig: antworte exakt [KEINE_ANTWORT]

Wenn Antwort nötig:
- Erzähle Weltreaktion, Konsequenzen, NPC-Verhalten oder Szenenveränderung
- Bei unsicherem Ausgang: verwende den vorgewürfelten Wert {pre_roll} (1W20) und erzähle das Ergebnis narrativ
- Zeige sichtbare Würfelergebnisse so: [Wurf: 1W20 = {pre_roll}]
- 1-4 Absätze, lebendig aber prägnant
- Ende mit offener Situation
- Wenn der Charakter einen wichtigen neuen Ort betritt, markiere: [NEUER_ORT: Ortsname]
- Wenn sich der Zustand eines Charakters ändert (Verletzung, Inventar, Ruf, Beziehung, Wissen), markiere: [ÄNDERUNG: Charakter - Was sich geändert hat]
  Beispiele: [ÄNDERUNG: Erik - Verletzung: Schnittwunde am Arm], [ÄNDERUNG: Maria - Inventar: Schwert verloren], [ÄNDERUNG: Erik - Ruf: Von den Wachen als Verdächtiger notiert]"""

        hist = ""
        for m in history[-12:]:
            pf = pc_name if m.get('role') == 'user' else "SPIELLEITER"
            hist += f"{pf}: {m.get('content','')}\n\n"
        prompt = f"{hist}{pc_name}: {msg}" if hist else f"{pc_name}: {msg}"

        chat = self._chat("msg", system)
        resp = await chat.send_message(UserMessage(text=prompt))
        return None if "[KEINE_ANTWORT]" in resp else resp

    # ── Campaign Generation ──

    async def generate_campaign(self, prompt):
        system = f"""{GERMAN}
Du bist ein erfahrener Rollenspiel-Kampagnendesigner. Erstelle eine Kampagne basierend auf dem Konzept.
Antworte NUR mit einem JSON-Objekt (kein Markdown):
{{"title":"Titel auf Deutsch","tone":"grimdark|realistic|heroic|mysterious","world_summary":"Weltbeschreibung 2-3 Sätze","current_threat":"Aktuelle Bedrohung","starting_location":"Startort mit Beschreibung","factions":["Fraktion 1: Beschreibung","Fraktion 2: Beschreibung"],"hooks":["Haken 1","Haken 2"],"opening_pressure":"Erste narrative Spannung","opening_scene":"Eröffnungsszene 3-5 atmosphärische Sätze"}}"""
        chat = self._chat("cgen", system)
        resp = await chat.send_message(UserMessage(text=f"Kampagne für: {prompt}"))
        try:
            return json.loads(resp)
        except Exception:
            m = re.search(r'\{[\s\S]*\}', resp)
            if m:
                try: return json.loads(m.group())
                except Exception: pass
            return {"title": prompt.title(), "tone": "realistic", "world_summary": resp[:500], "opening_scene": resp[:300]}

    # ── Character Creation ──

    async def generate_character_questions(self, campaign):
        system = f"""{GERMAN}
Erstelle 10 Charaktererstellungsfragen passend zum Setting.
Kampagne: {campaign.get('name','')}
Welt: {campaign.get('world_summary','')}
Ton: {campaign.get('tone','realistic')}

Antworte NUR mit einem JSON-Array:
[{{"prompt":"Frage auf Deutsch","field":"feldname"}}]

PFLICHTFELDER in dieser Reihenfolge: character_name, background, appearance, personality_traits, strengths, weaknesses, goals, fears, inventory, gm_secrets
Passe Fragen an das Setting an. Mache sie atmosphärisch und immersiv, nicht wie ein Formular.
Biete bei jeder Frage 2-3 Vorschläge passend zum Setting an, oder erlaube freie Eingabe."""
        chat = self._chat("cq", system)
        resp = await chat.send_message(UserMessage(text=f"Fragen für: {campaign.get('name','')}"))
        try:
            return json.loads(resp)
        except Exception:
            m = re.search(r'\[[\s\S]*\]', resp)
            if m:
                try: return json.loads(m.group())
                except Exception: pass
            return [
                {"prompt": "Wie heißt dein Charakter?", "field": "character_name"},
                {"prompt": "Was ist der Hintergrund deines Charakters?", "field": "background"},
                {"prompt": "Beschreibe das Aussehen.", "field": "appearance"},
                {"prompt": "Welche Persönlichkeitszüge hat dein Charakter?", "field": "personality_traits"},
                {"prompt": "Was sind die Stärken?", "field": "strengths"},
                {"prompt": "Was sind die Schwächen?", "field": "weaknesses"},
                {"prompt": "Was sind die Ziele?", "field": "goals"},
                {"prompt": "Wovor hat dein Charakter Angst?", "field": "fears"},
                {"prompt": "Was hat dein Charakter bei sich?", "field": "inventory"},
                {"prompt": "Hat dein Charakter ein Geheimnis? (Nur der Spielleiter kennt es)", "field": "gm_secrets"},
            ]

    async def confirm_character_step(self, campaign, field, answer, accumulated):
        system = f"""{GERMAN}
Du bist der Spielleiter bei der Charaktererstellung. Kampagne: {campaign.get('name','')}.
Bestätige die Antwort des Spielers kurz und atmosphärisch (1-2 Sätze). Kein Lob, kein Überschwang. Sachlich-immersiv."""
        chat = self._chat("cconf", system)
        context = ", ".join([f"{k}: {v}" for k, v in accumulated.items()]) if accumulated else "Noch leer"
        resp = await chat.send_message(UserMessage(text=f"Bisheriger Charakter: {context}\nFeld: {field}\nAntwort: {answer}"))
        return resp

    async def generate_relationship(self, campaign, pc1, pc2):
        system = f"""{GERMAN}
Du bist der Spielleiter. Erstelle eine bedeutungsvolle Verbindung zwischen zwei Spielercharakteren.
Kampagne: {campaign.get('name','')}, Ton: {campaign.get('tone','realistic')}

Charakter 1: {pc1.get('character_name','?')} - {pc1.get('background','')} - {pc1.get('personality_traits','')}
Charakter 2: {pc2.get('character_name','?')} - {pc2.get('background','')} - {pc2.get('personality_traits','')}

Schlage 3 mögliche Verbindungen vor (z.B. gemeinsame Vergangenheit, Schuld, Misstrauen, Familienbande, Eid, Geheimnis).
Format: Nummerierte Liste auf Deutsch. Atmosphärisch, zum Setting passend."""
        chat = self._chat("rel", system)
        resp = await chat.send_message(UserMessage(text="Erstelle Beziehungsvorschläge."))
        return resp

    async def generate_opening_scene(self, campaign, pcs):
        pc_names = ", ".join([p.get('character_name', '?') for p in pcs])
        system = f"""{GERMAN}
Du bist der Spielleiter. Schreibe die Eröffnungsszene der Kampagne.
{self._tone(campaign.get('tone','realistic'))}
Kampagne: {campaign.get('name','')}
Welt: {campaign.get('world_summary','')}
Startort: {campaign.get('starting_location', campaign.get('world_summary','')[:100])}
Bedrohung: {campaign.get('current_threat','')}
Spielercharaktere: {pc_names}

Schreibe 3-5 atmosphärische Absätze. Beschreibe den Ort, die Stimmung, die unmittelbare Situation.
Ende mit einer klaren Situation die zum Handeln einlädt. Erzähle keine Spieleraktionen."""
        chat = self._chat("open", system)
        resp = await chat.send_message(UserMessage(text=f"Eröffnungsszene für {campaign.get('name','')}."))
        return resp

    # ── Standard Methods (German) ──

    async def narrate(self, campaign, scene, npcs, events, action, history, pcs=None):
        system = f"""Du bist der Spielleiter einer privaten Rollenspiel-Sitzung.
{GERMAN}\n{self._rules()}\n{self._tone(campaign.get('tone','realistic'))}
{self._ctx(campaign, scene, npcs, events, pcs)}
Erzähle das Ergebnis der Spielerhandlung. 2-6 Absätze, lebendig, prägnant. Offenes Ende."""
        hist = "\n".join([f"{'SPIELER' if m.get('role')=='user' else 'SL'}: {m.get('content','')}" for m in history[-10:]])
        chat = self._chat("gm", system)
        return await chat.send_message(UserMessage(text=f"{hist}\nSPIELER HANDLUNG: {action}" if hist else f"SPIELER HANDLUNG: {action}"))

    async def resolve_check(self, campaign, scene, roll_result, difficulty, context, pc=None):
        pc_info = f"\nCharakter: {pc.get('character_name','?')}, Fähigkeiten: {pc.get('skills','')}, Verletzungen: {pc.get('injuries_conditions','')}" if pc else ""
        system = f"""Du erzählst das Ergebnis einer Probe.
{GERMAN}\n{self._tone(campaign.get('tone','realistic'))}
{self._ctx(campaign, scene, [], [])}{pc_info}
Versuch: {context}. Schwierigkeit: {difficulty}. Wurf: {roll_result['total']} ({roll_result['expression']}). Kritisch: {roll_result['is_critical']}. Patzer: {roll_result['is_fumble']}.
1-2 Absätze. Erfolg=Ziel mit Konsequenzen. Misserfolg=Komplikationen."""
        chat = self._chat("check", system)
        return await chat.send_message(UserMessage(text=f"Probe auflösen: {context}"))

    async def generate_recap(self, campaign, events, pcs=None):
        pc_info = "Charaktere: " + ", ".join([p.get('character_name','?') for p in (pcs or [])])
        system = f"""{GERMAN}\nSitzungszusammenfassung schreiben.
Kampagne: {campaign.get('name','')}. Ton: {campaign.get('tone','realistic')}. {pc_info}
Maximal 300 Wörter. Vergangenheit, dritte Person. Wichtige Entscheidungen und offene Fäden hervorheben."""
        ev_text = "\n".join([f"- [{e.get('event_type','?')}] {e.get('summary','')}" for e in events[-30:]])
        chat = self._chat("recap", system)
        return await chat.send_message(UserMessage(text=f"Ereignisse:\n{ev_text}"))
