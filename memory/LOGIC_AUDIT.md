# Kaeldor RPG — Logik-Audit-Report (2026-06)

Systematischer Scan aller 12 Fokusbereiche. Status: ✅ Gefixt · 🔧 In Arbeit · ⏳ Offen (freigegeben) · ❓ Braucht Entscheidung

## ✅ Bereits gefixt & getestet
| Bereich | Problem | Lösung | Status |
|---|---|---|---|
| Bank/Economy (P0) | Kreditlimit `(bank+cash)*3` → Borrow erhöht bank → Limit wächst → **unbegrenztes Geld-Drucken**. UI zeigte Gesamtlimit statt verfügbar. | Netto-vermögensbasiertes Credit-System (`credit_profile`): Limit invariant unter Borrow. Klar getrennt: limit/used/available. Denial bei Strafregister, missed-payment-Tracking, Live-Preview im UI. | ✅ getestet (iter_9, 51/51) |
| Wirtschaft/UI | Auto-Verkauf zeigte keine Auszahlung | Resale-Wert + Schätzung am Button + echter Betrag im Toast | ✅ |
| Wirtschaft/UI | Business-Verkauf-Toast generisch | Zeigt echten Verkaufsbetrag | ✅ |
| UI/Testing | `Pill` verschluckte `data-testid` | Prop wird weitergereicht | ✅ |
| Jobs (vorher) | Beförderung shift- statt stundenbasiert | Stundenbasiert + Migration | ✅ (iter_8) |

## 🔴 P0 — keine weiteren Exploits gefunden
Verifiziert: Resale ≤ Kaufpreis, `charge()` konsistent, Selbst-Bewerbung blockiert, keine Endlos-Farm-Aktion, deposit/withdraw blähen Kredit nicht mehr auf.

## 🟡 P1 — Logik-Lücken (vom User in dieser Reihenfolge freigegeben)
**Paket 2 — Transparenz**
- #11 Strukturiertes Transaktions-Log (Typ, Betrag, Saldo) + Ansicht — ❓/⏳
- #12 Confirm-Dialoge für irreversible Verkäufe + Pre-Sale-Schätzwert (Business) — ⏳

**Paket 3 — Realismus**
- #3 Kaution-Rückzahlung bei Umzug — ⏳
- #4 Haus-Verkauf-Endpoint — ⏳
- #5 `criminal_suspicion` Cooldown über Zeit — ⏳
- #6 Natürliche Gesundheits-Regeneration — ⏳
- #8 Klinik-Rechnung beim Kollaps — ⏳
- #13 Stress baut sich auch im Schlaf ab — ⏳

**Paket 4 — Items/Inventar**
- #1 „Benutzen"-Flow (Consumables nicht mehr sofort bei Kauf) — ❓
- #2 Persistentes Equipment (Kleidung/Gear) — ❓

**Paket 5 — Schulden-/Konsequenz-System**
- #7 Inkasso/Pfändung/Kreditsperre bei hoher Schuld — ❓
- #9 Fahrzeug-Reparatur pro Fahrzeug + Zustand-Konsequenzen — ❓

## 🟢 P2 — Polish (gesammelt, später)
- Bank-Sparzinsen; Sprit/Versicherung auch bei ungenutztem Auto; Knast-Events & -Bedürfnisse; qty>1 Consumable-Clamp-Verschwendung; Versicherung an Unfälle koppeln; Profanity-Filter nur Basisliste; frühere Bankrott-Warnung.

## ✔️ Geprüft & OK
Player Employment (Transparenz), Business-P&L, Real-Time/Offline-Mathematik, Social-Konsequenzen, Chat/Device-Gating/Unread, Jobs (Ablehnungsgründe, Lohn nach Skills/Rep).
