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
- Erzähle Konsequenzen erklärter Handlungen treu und ungeschönt.
- Sei streng bei Kausalität und Kontinuität.
- Verfolge Verletzungen, Ressourcen, Versprechen und soziale Auswirkungen persistent.
- Verborgene Informationen bleiben verborgen bis natürlich offenbart.
- Misserfolg schafft neue Komplikationen, keine Sackgassen.
- Erfolg hat plausible Konsequenzen — nicht immer gute.
- Die Welt lebt weiter. NPCs handeln eigenständig. Fraktionen reagieren.
- Kein KI-gefälliges Verhalten. Kein Lob. Keine künstliche Sanftheit. Kein Moralisieren."""

    def _lethality(self):
        return """GEWALT, KAMPF & STERBLICHKEIT:
- Gewalt ist REAL und PERSISTENT. Kein Weichspülen. Kein stilles Abschwächen.
- PCs KÖNNEN sterben. NPCs KÖNNEN sterben. Es gibt KEIN verstecktes Plot-Armor.
- Wenn ein Angriff trifft und der Würfel es bestätigt: beschreibe die Wunde konkret.
- Verletzungszustände (werden im Charakter-Block als injuries_conditions geführt):
  leicht verletzt → schwer verletzt → kampfunfähig → blutend → sterbend → tot
- Jeder Zustand hat mechanische Konsequenzen:
  leicht verletzt: Schmerz, leichte Einschränkung.
  schwer verletzt: Deutliche Einschränkung, Proben erschwert.
  kampfunfähig: Kann nicht kämpfen, kaum handeln.
  blutend: Verschlechtert sich ohne Behandlung. Zeitdruck.
  sterbend: Wenige Minuten ohne Rettung. Bewusstlos oder hilflos.
  tot: Permanent. Kein Zurück.
- Rettung/Stabilisierung ist MÖGLICH aber NICHT automatisch. Erfordert Handlung, Würfel, Ressourcen.
- Wenn jemand erfolgreich tötet, verletzt oder überwältigt: das Ergebnis ist REAL und BLEIBT.
- NPCs haben KEIN Plot-Armor. Ein NPC der tödlich getroffen wird, stirbt.
- Der GM darf NICHT:
  - Gewalt moralisch kommentieren oder wegmoderieren
  - Tödliche Treffer still in "Bewusstlosigkeit" umwandeln
  - NPCs durch unsichtbare Mercy-Logik retten
  - PCs vor den Folgen ihrer Entscheidungen schützen
- Die WELT REAGIERT auf Gewalt:
  Blutspuren, Zeugen, Gerüchte, Angst, Rache, Fraktionsreaktionen, Gesetz, sozialer Fallout.
  Mord hat Konsequenzen. Überfälle haben Konsequenzen. Gewalt bleibt nicht unsichtbar.
- Bei Zustandsänderung IMMER markieren: [ÄNDERUNG: Charakter - neuer Zustand]"""

    def _writing_style(self):
        return """DEUTSCHER SCHREIBSTIL — STRENGE REGELN:
- KURZ. KONKRET. SZENENSPEZIFISCH. Jeder Satz treibt die Szene voran.
- KEINE generischen KI-Floskeln. VERBOTENE Phrasen und Muster:
  "kalte Luft", "feuchter Atem", "Schatten huschen", "ein Knirschen in der Dunkelheit",
  "die Atmosphäre ist angespannt", "etwas liegt in der Luft", "eine Gestalt tritt hervor",
  "die Stille wird unterbrochen", "ein ungutes Gefühl", "die Luft riecht nach [generisch]"
- Schreibe NICHT wie ein KI-Textgenerator. Schreibe wie ein erfahrener Autor:
  - Variierende Satzlängen. Kurze Sätze für Spannung. Längere für Beschreibung.
  - Spezifische Details statt atmosphärischer Allgemeinplätze.
  - Sinneseindrücke die zur KONKRETEN Situation passen, nicht austauschbar sind.
  - Handlung vor Atmosphäre. Was PASSIERT ist wichtiger als wie es sich ANFÜHLT.
- NPC-Dialog: Charakteristisch. Jeder NPC spricht anders (Dialekt, Wortwahl, Länge, Ton).
- WIEDERHOLE DICH NICHT:
  - Benutze nie dieselbe Beschreibung zweimal in einer Sitzung.
  - Wenn du einen Ort schon beschrieben hast: beschreibe was sich VERÄNDERT hat, nicht den Ort erneut.
  - Keine wiederholten Stimmungsbeschreibungen. Einmal reicht.
- Antwortlänge: Standard 2-4 Sätze. Kampf/Enthüllung maximal 6-8 Sätze. KEINE Textwände."""

    def _background_enforcement(self):
        return """CHARAKTER-HINTERGRUND-KONSISTENZ — STRENGE REGELN:
- Etablierte Charakterfakten sind KANON. Sie werden AKTIV benutzt.
- Der Hintergrund, Beruf, soziale Stellung, Fähigkeiten und Schwächen eines PCs sind BINDEND:
  - Ein Bauer kann nicht plötzlich fechten. Ein Adliger kennt keine Diebessprache.
  - Fähigkeiten kommen aus dem Background. Nicht aus spontanen Behauptungen.
  - Wenn ein PC etwas versucht das sein Hintergrund nicht stützt: höhere Schwierigkeit oder Fehlschlag.
- Neue spontane Behauptungen mitten in der Szene sind NICHT automatisch wahr:
  - "Ich kann reiten" zählt nur wenn der Hintergrund Reiterfahrung enthält.
  - "Ich kenne Gift" erfordert medizinischen oder kriminellen Hintergrund.
  - Bei zweifelhaften Behauptungen: Würfelprobe mit hohem SG, oder direkt ablehnen.
- Der GM referenziert aktiv den Background:
  - Beruf beeinflusst was der PC weiß, kann und wo er Kontakte hat.
  - Sozialer Status bestimmt wie NPCs reagieren.
  - Schwächen und Ängste werden AKTIV ins Spiel eingebaut, nicht ignoriert.
  - Verpflichtungen und Schulden werden EINGEFORDERT.
- Reputation ist dynamisch: Taten verändern wie die Welt den PC sieht."""

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
        # Status and health FIRST — most critical for gameplay decisions
        status = p.get('status', 'active')
        injuries = p.get('injuries_conditions', '')
        if status != 'active' or injuries:
            b += f"    ZUSTAND: {status.upper()}"
            if injuries: b += f" | Verletzungen: {injuries}"
            b += "\n"
        for k, l in [('background','Hintergrund'), ('personality_traits','Persönlichkeit'),
                      ('strengths','Stärken'), ('weaknesses','Schwächen'), ('skills','Fähigkeiten'),
                      ('short_description','Beschreibung'), ('inventory','Inventar'), ('faction_ties','Fraktion'),
                      ('reputation','Ruf'), ('current_location','Ort'), ('goals','Ziele'), ('fears','Ängste'),
                      ('gm_secrets','[GM GEHEIM]'), ('obligations_notes','Verpflichtungen')]:
            if p.get(k): b += f"    {l}: {p[k]}\n"
        return b

    # ── Smart Memory Context ──

    def format_smart_context(self, ctx):
        """Format the smart context dict into a focused prompt section."""
        c = ctx.get("campaign", {})
        parts = [f"KAMPAGNE: {c.get('name','?')}\nWELT: {c.get('world_summary','')}"]

        # Scene memory (short-term state)
        sm = ctx.get("scene_memory") or ctx.get("scene")
        if sm:
            parts.append(f"\nAKTUELLE SZENE:\n  Ort: {sm.get('location','?')}\n  Atmosphäre: {sm.get('atmosphere', sm.get('description',''))}\n  Zeit: {sm.get('time_of_day','?')}\n  Spannung: {sm.get('tension_level',1)}/10")
            if sm.get('immediate_danger'): parts.append(f"  Unmittelbare Gefahr: {sm['immediate_danger']}")
            if sm.get('current_objectives'): parts.append(f"  Aktuelle Ziele: {', '.join(sm['current_objectives'])}")
            if sm.get('unresolved_actions'): parts.append(f"  Offene Aktionen: {', '.join(sm['unresolved_actions'])}")
            if sm.get('present_npcs'): parts.append(f"  Anwesende NPCs: {', '.join(sm['present_npcs'])}")
            if sm.get('active_threats'): parts.append(f"  Bedrohungen: {', '.join(sm['active_threats'])}")

        # Player characters
        pcs = ctx.get("pcs", [])
        if pcs:
            parts.append("\nSPIELERCHARAKTERE:")
            for p in pcs:
                parts.append(self._pc_block(p))

        # NPCs with relationships
        npcs = ctx.get("npcs", [])
        rels = ctx.get("relationships", [])
        if npcs:
            parts.append("\nANWESENDE / RELEVANTE NPCs:")
            for n in npcs[:10]:
                line = f"  {n['name']} ({n.get('role','?')}, {n.get('faction','-')}): {n.get('personality_traits','')}. Motivation: {n.get('motivation','?')}. Status: {n.get('status','lebendig')}. Vertrauen: {n.get('trust_level',0)}"
                # Add relationship info
                npc_rels = [r for r in rels if r.get('entity_a') == n['name'] or r.get('entity_b') == n['name']]
                if npc_rels:
                    rel_notes = "; ".join([f"{r.get('relationship_type','?')}({r.get('value',0)}) mit {r.get('entity_b') if r.get('entity_a')==n['name'] else r.get('entity_a')}: {r.get('notes','')}" for r in npc_rels[:3]])
                    line += f"\n    Beziehungen: {rel_notes}"
                parts.append(line)

        # Unresolved events (persistent memory)
        unresolved = ctx.get("unresolved_events", [])
        if unresolved:
            parts.append("\nUNGELÖSTE EREIGNISSE & KONSEQUENZEN:")
            for e in unresolved[:20]:
                vis = "[GEHEIM] " if e.get('visibility') == 'gm_only' else ""
                parts.append(f"  - {vis}[{e.get('event_type','?')}] {e.get('subject','')}: {e.get('detail','')}")

        # GM knowledge (hidden)
        gm_k = ctx.get("gm_knowledge", [])
        if gm_k:
            parts.append("\n[NUR FÜR DEN SPIELLEITER - NICHT OFFENBAREN OHNE GRUND]:")
            for k in gm_k[:10]:
                parts.append(f"  - [{k.get('category','?')}] {k.get('content','')}")

        # Public + PC-specific knowledge
        pub_k = ctx.get("public_knowledge", [])
        pc_k = ctx.get("pc_knowledge", [])
        if pub_k or pc_k:
            parts.append("\nBEKANNTES WISSEN:")
            for k in (pub_k + pc_k)[:10]:
                parts.append(f"  - {k.get('content','')}")

        # Location lore
        lore = ctx.get("lore", [])
        if lore:
            parts.append("\nORTSBEZOGENES WISSEN:")
            for l in lore[:3]:
                parts.append(f"  - {l.get('title','')}: {l.get('content','')[:150]}")

        # Recent summaries (long-term memory)
        sums = ctx.get("summaries", [])
        if sums:
            parts.append("\nLETZTE SITZUNGSZUSAMMENFASSUNGEN:")
            for s in sums:
                parts.append(f"  [{s.get('created_at','')}] {s.get('summary','')[:200]}")

        # Recent events (medium-term)
        rev = ctx.get("recent_events", [])
        if rev:
            parts.append("\nJÜNGSTE EREIGNISSE:")
            for e in rev[-10:]:
                parts.append(f"  - [{e.get('event_type','?')}] {e.get('summary','')}")

        # PC-PC relationships
        pc_names = [p.get('character_name','') for p in pcs]
        pc_rels = [r for r in rels if r.get('entity_a') in pc_names and r.get('entity_b') in pc_names]
        if pc_rels:
            parts.append("\nBEZIEHUNGEN ZWISCHEN SPIELERCHARAKTEREN:")
            for r in pc_rels:
                parts.append(f"  {r.get('entity_a','')} ↔ {r.get('entity_b','')}: {r.get('relationship_type','')}, {r.get('notes','')}")

        # Sandbox: Inventory
        inv = ctx.get("inventory", [])
        if inv:
            parts.append("\nINVENTAR:")
            by_owner = {}
            for i in inv:
                owner = i.get('owner_name', '?')
                if owner not in by_owner: by_owner[owner] = []
                loc = f" [{i.get('location','?')}]" if i.get('location') != 'getragen' else ""
                qty = f" x{i['quantity']}" if i.get('quantity', 1) > 1 else ""
                cond = f" ({i['condition']})" if i.get('condition') not in ('gut', 'neu', '') else ""
                by_owner[owner].append(f"{i['item_name']}{qty}{cond}{loc}")
            for owner, items in by_owner.items():
                parts.append(f"  {owner}: {', '.join(items[:15])}")

        # Sandbox: Finances
        fins = ctx.get("finances", [])
        if fins:
            parts.append("\nFINANZEN:")
            for f in fins:
                parts.append(f"  {f.get('pc_id','?')}: {f.get('balance',0)} {f.get('currency','')}")
                if f.get('debts'): parts.append(f"    Schulden: {f['debts']}")
                if f.get('recurring_costs'): parts.append(f"    Laufende Kosten: {f['recurring_costs']}")

        # Sandbox: Properties
        props = ctx.get("properties", [])
        if props:
            parts.append("\nBESITZ / MIETOBJEKTE:")
            for p in props:
                rent = f" (Miete: {p['rent_cost']} {p.get('rent_currency','')})" if p.get('rent_cost') else ""
                parts.append(f"  {p.get('name','?')} ({p.get('property_type','?')}, {p.get('status','?')}){rent}: {p.get('description','')[:80]}")

        return "\n".join(parts)

    # ── Memory Event Extraction ──

    async def extract_memory_events(self, narrative, campaign_name=""):
        """Extract structured memory events from a GM narrative."""
        system = """Analysiere diese Spielleiter-Erzählung und extrahiere wichtige Zustandsänderungen als strukturierte Ereignisse.
Antworte NUR mit einem JSON-Array. Jedes Ereignis:
{"type":"injury|death|kill|item_lost|item_gained|clue|faction_change|trust_change|oath|debt|damage|secret|relationship|threat|status|combat|arrest|reputation","subject":"Wer/Was betroffen","detail":"Was genau passiert ist","visibility":"public|gm_only"}
Typen: injury=Verletzung/Zustandsverschlechterung, death=Tod eines Charakters/NPCs, kill=Jemand hat getötet, item_lost=Gegenstand verloren, item_gained=Gegenstand erhalten, clue=Hinweis entdeckt, faction_change=Fraktionsänderung, trust_change=Vertrauensänderung, oath=Eid/Versprechen, debt=Schuld, damage=Ortsschaden, secret=Geheimnis offenbart, relationship=Beziehungsänderung, threat=Bedrohungseskalation, status=Statusänderung, combat=Kampfhandlung, arrest=Verhaftung/Festnahme, reputation=Rufänderung
WICHTIG: Erfasse JEDE Verletzung, jeden Tod, jeden Kampf als eigenes Ereignis. Gewaltakte und ihre Konsequenzen sind kritisch.
Wenn keine wichtigen Änderungen: antworte []"""
        chat = self._chat("mem", system)
        resp = await chat.send_message(UserMessage(text=f"Erzählung:\n{narrative}"))
        try:
            return json.loads(resp)
        except Exception:
            m = re.search(r'\[[\s\S]*\]', resp)
            if m:
                try: return json.loads(m.group())
                except Exception: pass
            return []

    # ── Auto Scene Summarization ──

    async def auto_summarize_scene(self, campaign, events, pcs=None):
        """Generate structured scene summary for long-term memory."""
        pc_info = ", ".join([p.get('character_name','?') for p in (pcs or [])])
        events_text = "\n".join([f"- [{e.get('event_type','?')}] {e.get('subject','')}: {e.get('detail', e.get('summary',''))}" for e in events[-30:]])
        system = f"""{GERMAN}
Erstelle eine strukturierte Szenenzusammenfassung für das Langzeitgedächtnis.
Kampagne: {campaign.get('name','')}. Charaktere: {pc_info}.
Antworte als JSON:
{{"summary":"Zusammenfassung der Szene (3-5 Sätze)","key_consequences":["Konsequenz 1","Konsequenz 2"],"pc_changes":["Charakteränderung 1"],"npc_changes":["NPC-Änderung 1"],"world_changes":["Weltänderung 1"],"unresolved_hooks":["Offener Faden 1"],"mood":"Stimmung der Szene in einem Wort"}}"""
        chat = self._chat("sum", system)
        resp = await chat.send_message(UserMessage(text=f"Ereignisse:\n{events_text}"))
        try:
            return json.loads(resp)
        except Exception:
            m = re.search(r'\{[\s\S]*\}', resp)
            if m:
                try: return json.loads(m.group())
                except Exception: pass
            return {"summary": resp[:300]}

    # ── Update Scene Memory ──

    async def suggest_scene_update(self, narrative, current_scene):
        """Suggest updates to scene memory based on the latest narrative."""
        current = json.dumps(current_scene or {}, ensure_ascii=False)[:500]
        system = f"""Analysiere die Erzählung und schlage Aktualisierungen für den Szenenzustand vor.
Aktueller Zustand: {current}
Antworte als JSON mit nur den Feldern die sich geändert haben:
{{"location":"","summary":"","present_npcs":[],"immediate_danger":"","tension_level":0,"atmosphere":"","time_of_day":""}}
Leere Felder weglassen. Nur geänderte Werte."""
        chat = self._chat("scn", system)
        resp = await chat.send_message(UserMessage(text=f"Erzählung:\n{narrative[:1500]}"))
        try:
            return json.loads(resp)
        except Exception:
            m = re.search(r'\{[\s\S]*\}', resp)
            if m:
                try: return json.loads(m.group())
                except Exception: pass
            return {}

    # ── Scene Turn Response (combined multi-player, short output) ──

    async def scene_turn_response(self, campaign, player_actions, smart_ctx, resolved_last_turn=None, last_gm_response=""):
        """Respond to combined player actions in a shared scene. Strict action lifecycle."""
        tone = campaign.get('tone', 'realistic')
        pre_roll = random.randint(1, 20)
        pre_roll_2 = random.randint(1, 20)

        world_context = self.format_smart_context(smart_ctx) if smart_ctx else ""

        # Build action list with discord IDs for section headers
        player_names = [a.get('pc_name', '?') for a in player_actions]
        is_multi = len(player_actions) > 1

        # Build NEW actions block
        new_actions = ""
        for a in player_actions:
            new_actions += f"  {a.get('pc_name', '?')}: {a.get('message', '')}\n"

        # Build RESOLVED context
        resolved_block = ""
        if resolved_last_turn:
            resolved_block = "BEREITS AUFGELÖST (letzte Runde — NICHT erneut erzählen):\n"
            for a in resolved_last_turn:
                resolved_block += f"  {a.get('pc_name', '?')}: {a.get('message', '')}\n"

        last_gm_block = ""
        if last_gm_response:
            truncated = last_gm_response[:400] + ("..." if len(last_gm_response) > 400 else "")
            last_gm_block = f"DEINE LETZTE ANTWORT (bereits erzählt — NICHT wiederholen):\n  {truncated}\n"

        # Multi-player formatting instructions
        multi_format = ""
        if is_multi:
            names_str = " und ".join([f"**{n}**" for n in player_names])
            multi_format = f"""
MULTI-SPIELER FORMATIERUNG:
- Zwei Spieler haben gehandelt: {names_str}
- Schreibe für JEDEN Spieler einen eigenen Abschnitt.
- Beginne jeden Abschnitt mit dem Charakternamen als Fettdruck-Überschrift: **Name**:
- Trenne die Abschnitte mit einer Leerzeile.
- Jeder Abschnitt: 2-4 Sätze, Konsequenz der Handlung dieses Charakters.
- Am Ende optional EIN kurzer gemeinsamer Satz falls die Situation es erfordert.
- KEIN langer gemeinsamer Absatz der beide Handlungen vermischt.

STRUKTUR-VORLAGE:
**{player_names[0]}**: [Konsequenz der Handlung, 2-4 Sätze]

**{player_names[1]}**: [Konsequenz der Handlung, 2-4 Sätze]

[Optional: Ein kurzer gemeinsamer Satz zur Gesamtlage]
"""
        else:
            multi_format = """
SOLO-SPIELER FORMATIERUNG:
- Nur EIN Spieler hat gehandelt.
- Schreibe 2-5 Sätze als direkte Konsequenz.
- KEINEN Abschnittsheader nötig bei nur einem Spieler.
"""

        system = f"""Du bist der Spielleiter einer privaten Rollenspiel-Sitzung.
{GERMAN}
{self._rules()}
{self._lethality()}
{self._background_enforcement()}
{self._writing_style()}
{self._tone(tone)}

{world_context}

{multi_format}
NPC-DIALOG FORMATIERUNG:
- NPC-Sprache IMMER in Anführungszeichen: „Dialog hier."
- Vor oder nach dem Dialog kurze Handlungsbeschreibung in *Kursiv*: *Er mustert dich kalt.*
- Dialog und Erzählung NICHT in einem Satz vermischen.

ABSCHLUSS-PROMPT:
- Am Ende EIN kurzer Satz als offene Situation. KEINE Aufzählung von Optionen.
- KEIN „Was tut ihr: Option A / Option B / Option C"
- Ende mit einer Situation die zum Handeln einlädt.

AKTIONS-LEBENSZYKLUS (STRIKT):
- Unter NEUE AKTIONEN stehen die Handlungen die du JETZT auflösen musst.
- Unter BEREITS AUFGELÖST stehen Handlungen der LETZTEN Runde — FERTIG erzählt.
- Aufgelöste Handlungen NICHT erneut erzählen. VORWÄRTS erzählen.

WÜRFEL UND PROBEN:
- Bei unsicherem Ausgang: verwende den vorgewürfelten Wert {pre_roll} (oder {pre_roll_2} für zweiten Charakter) als 1W20-Ergebnis.
- Zeige das Ergebnis IMMER transparent:
  **Wurf:** 1W20 = [Wert]
  **Schwierigkeit:** [SG]
  **Ergebnis:** [Kategorie]
- Ergebniskategorien: Kritischer Erfolg / Erfolg / Teilerfolg / Fehlschlag / Kritischer Fehlschlag
- NATÜRLICHE 20 = Kritischer Erfolg. NATÜRLICHE 1 = Kritischer Fehlschlag.
- Die Erzählung MUSS zum Würfelergebnis passen.

SANDBOX-WELT:
- Die Welt ist OFFEN. Kein erzwungener Plot. Kein Railroading.
- Spieler dürfen arbeiten, handeln, mieten, bauen, Beziehungen pflegen.
- Finanzen und Besitz der Spieler beachten (siehe INVENTAR/FINANZEN/BESITZ oben).
- Bei Handel/Kauf/Verkauf: [TRANSAKTION: Charakter, Typ, Betrag, Beschreibung]
- Bei Inventaränderung: [INVENTAR: Charakter, +/-Gegenstand, Ort]

Bei Ortswechsel: [NEUER_ORT: Name]
Bei Zustandsänderung: [ÄNDERUNG: Charakter - Was]

Wenn KEINE Reaktion der Welt angemessen ist: [KEINE_ANTWORT]"""

        prompt = ""
        if resolved_block:
            prompt += resolved_block + "\n"
        if last_gm_block:
            prompt += last_gm_block + "\n"
        prompt += f"NEUE AKTIONEN (jetzt auflösen):\n{new_actions}"

        chat = self._chat("scene", system)
        resp = await chat.send_message(UserMessage(text=prompt))
        return None if "[KEINE_ANTWORT]" in resp else resp

    # ── Message-Driven Response (with Smart Memory) ──

    async def message_driven_response(self, campaign, scene, npcs, events, pcs, msg, active_pc, history, smart_ctx=None):
        tone = campaign.get('tone', 'realistic')
        pre_roll = random.randint(1, 20)
        pc_detail = self._pc_block(active_pc) if active_pc else ""
        pc_name = active_pc.get('character_name', '?') if active_pc else 'Unbekannt'

        # Use smart context if available, otherwise fall back to basic context
        if smart_ctx:
            world_context = self.format_smart_context(smart_ctx)
        else:
            world_context = self._ctx(campaign, scene, npcs, events, pcs)

        system = f"""Du bist der Spielleiter einer privaten Tabletop-Rollenspiel-Sitzung.
{GERMAN}
{self._rules()}
{self._lethality()}
{self._background_enforcement()}
{self._writing_style()}
{self._tone(tone)}

{world_context}

DER HANDELNDE CHARAKTER:
{pc_detail}

GEDÄCHTNIS-ANWEISUNGEN:
- Du ERINNERST dich an alle oben aufgeführten Ereignisse, Verletzungen, Schulden, Versprechen und Beziehungen.
- NPCs erinnern sich an frühere Interaktionen.
- Verletzungen beeinflussen Handlungsfähigkeit. Verlorene Gegenstände sind weg.
- Beziehungswerte beeinflussen NPC-Verhalten.

REAKTIONSLOGIK:
Antworte NUR wenn die Nachricht eine fiktional sinnvolle Weltreaktion erfordert.
Wenn KEINE Antwort nötig: [KEINE_ANTWORT]

Wenn Antwort nötig:
- 2-5 Sätze, konkret, knapp, konsequent
- Bei unsicherem Ausgang: verwende Vorwurf {pre_roll} (1W20), erzähle knapp
- Zeige: [Wurf: 1W20 = {pre_roll}]
- Bei Ortswechsel: [NEUER_ORT: Ortsname]
- Bei Zustandsänderung: [ÄNDERUNG: Charakter - Was]"""

        hist = ""
        chat_msgs = (smart_ctx or {}).get("recent_chat", history[-6:]) if smart_ctx else history[-6:]
        for m in chat_msgs:
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
