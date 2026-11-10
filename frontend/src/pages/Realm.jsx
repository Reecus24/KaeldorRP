import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, errMessage } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { Panel, SectionTitle, Spinner, Pill } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { money, realDurationLabel } from "@/lib/helpers";
import { Shield, Swords, ScrollText, ArrowRight, Flag, Heart, Clock3, Backpack } from "lucide-react";

export default function Realm() {
    const { player, state, act } = useGame();
    const [world, setWorld] = useState(null);
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);
    const [tab, setTab] = useState("expeditions");
    const [tactic, setTactic] = useState("balanced");
    const [confirmOath, setConfirmOath] = useState(null);
    const seq = useRef(0);
    const load = useCallback(async () => {
        const request = ++seq.current;
        try { const { data } = await api.get("/realm"); if (request === seq.current) { setWorld(data); setError(""); } }
        catch (e) { if (request === seq.current) setError(errMessage(e)); }
    }, []);
    useEffect(() => { load(); const timer = setInterval(load, 15000); const counter = seq; return () => { clearInterval(timer); counter.current++; }; }, [load]);
    const run = async (path, body, message) => {
        setBusy(true);
        try { await act(() => api.post(path, body || {}), message); await load(); setConfirmOath(null); }
        finally { setBusy(false); }
    };
    if (!world) return error ? <Panel className="p-6" role="alert">{error}<KButton onClick={load}>Try again</KButton></Panel> : <Spinner />;
    const f = world.faction;
    const selectedTactic = world.tactics[tactic] ? tactic : Object.keys(world.tactics)[0];
    const missions = world.missions.filter(m => !m.faction_id || m.faction_id === f?.id);
    return <div className="space-y-6">
        <SectionTitle icon={Swords} kicker="Beyond the village" title="Oaths & Expeditions" sub="A peasant's hands can carry a banner, a blade, or both. Choose what your name will mean." />
        {error && <p role="alert" className="text-neon-red">{error}</p>}
        <div className="realm-banner realm-banner-small">
            <div className="relative z-10 p-6 sm:p-8 max-w-xl">
                <span className="realm-eyebrow">{f ? f.name : "No oath sworn"}</span>
                <h2 className="font-display text-3xl text-white mt-2">{f ? f.rank.name : "Your path is still your own."}</h2>
                <p className="text-sm text-muted-foreground leading-relaxed mt-3">{f ? "Rise through deeds and service. Rank requires renown, completed service hours and real days in your faction." : "Join the royal army or the outlaws of Thornwood. You can also remain independent, learn a trade and take village expeditions."}</p>
                <div className="flex flex-wrap gap-4 mt-5 text-sm">
                    <span className="inline-flex gap-2 items-center text-neon-yellow"><Swords size={16} /> Power {world.combat.power}</span>
                    <span className="inline-flex gap-2 items-center text-neon-green"><Shield size={16} /> Armor {world.combat.armor}</span>
                    <Link to="/inventory" className="inline-flex gap-2 items-center text-neon-cyan underline underline-offset-4"><Backpack size={16} /> Prepare equipment</Link>
                </div>
            </div>
        </div>
        {f && <Panel className="p-5">
            <div className="grid grid-cols-3 gap-3 text-sm">
                <div><div className="realm-eyebrow">Renown</div><strong className="text-xl text-white">{Math.round(f.renown)}</strong></div>
                <div><div className="realm-eyebrow">Service</div><strong className="text-xl text-white">{f.service_hours.toFixed(1)} h</strong></div>
                <div><div className="realm-eyebrow">Oath held</div><strong className="text-xl text-white">{f.days ?? 0} days</strong></div>
            </div>
            {f.next_rank && <div className="border-t border-white/10 mt-4 pt-4 text-sm text-muted-foreground"><span className="text-white">Next: {f.next_rank.name}</span> · {f.next_rank.renown} renown · {f.next_rank.service_hours} completed hours · {f.next_rank.days} real days. All three are required.</div>}
        </Panel>}
        <div className="realm-tabs" role="tablist" aria-label="Oaths and expeditions">
            {[["expeditions", "Expeditions", Swords], ["oaths", "Factions & ranks", Flag], ["reports", "Battle chronicle", ScrollText]].map(([id, name, Icon]) => <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}><Icon size={16} />{name}</button>)}
        </div>
        {tab === "expeditions" && <div className="space-y-5" role="tabpanel">
            <fieldset className="space-y-3"><legend className="realm-eyebrow mb-3">Your approach</legend><div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {Object.entries(world.tactics).map(([key, t]) => <label key={key} className={"tactic-card " + (selectedTactic === key ? "selected" : "")}>
                    <input type="radio" name="tactic" value={key} checked={selectedTactic === key} onChange={() => setTactic(key)} className="mr-2 accent-amber-300" />
                    <strong className="font-display text-white">{t.name}</strong>
                    <span className="block text-xs text-muted-foreground mt-2">Damage ×{t.damage_multiplier} · coin ×{t.reward_multiplier}</span>
                </label>)}
            </div></fieldset>
            <p className="text-sm text-muted-foreground">Power comes from level, endurance, woodcraft and equipped arms. A result is fixed when you depart; rewards arrive when the timer ends. Cancelling forfeits supplies and rewards, and keeps the cooldown.</p>
            {!f && <button onClick={() => setTab("oaths")} className="realm-text-link">Swear an oath to unlock faction orders <ArrowRight size={16} /></button>}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {missions.map(m => { const forecast = m.forecasts[selectedTactic]; return <Panel key={m.id} className="p-5 flex flex-col" data-testid={"expedition-" + m.id}>
                    <div className="flex justify-between items-center gap-3 mb-3"><Pill tone={m.faction_id ? "yellow" : "green"}>{m.faction_id ? "Faction orders" : "Village contract"}</Pill><span className="text-xs inline-flex gap-1 items-center text-muted-foreground"><Clock3 size={13} />{realDurationLabel(m.duration_minutes, state?.time_scale)} real</span></div>
                    <h3 className="font-display text-xl text-white">{m.name}</h3><p className="text-sm text-muted-foreground mt-2 mb-4 flex-1">{m.description}</p>
                    <div className="grid grid-cols-2 gap-3 text-sm py-4 border-y border-white/10">
                        <div><span className="text-muted-foreground">Victory chance</span><strong className="block text-neon-green">{Math.round(forecast.chance * 100)}%</strong></div>
                        <div><span className="text-muted-foreground">Victory spoils</span><strong className="block text-neon-yellow">{money(forecast.gold)} · {m.renown} renown</strong></div>
                        <div><span className="text-muted-foreground">Health lost</span><span className="block text-white">{forecast.win_damage} win / {forecast.loss_damage} retreat</span></div>
                        <div><span className="text-muted-foreground">Departure cost</span><span className="block text-white">{m.energy_cost} energy · {m.fatigue_cost} fatigue</span></div>
                    </div>
                    <p className="text-xs text-muted-foreground mt-3">Victory: {m.xp} XP. {m.min_health} health required. Recovery between runs: {realDurationLabel(m.cooldown_minutes, state?.time_scale)} real.</p>
                    {m.suspicion > 0 && <p className="text-xs text-neon-red mt-2">Every attempt: +{m.suspicion} suspicion, {m.legal_change} legal standing.</p>}
                    {m.supply_labels.length > 0 && <p className="text-xs text-muted-foreground mt-2">Consumed on departure: {m.supply_labels.map(s => s.quantity + " " + s.name + " (own " + s.owned + ")").join(", ")}</p>}
                    <div className="mt-4"><KButton variant="solid" className="w-full" loading={busy} disabled={!!m.reason} onClick={() => run("/realm/expeditions/" + m.id + "/start", { tactic: selectedTactic }, "Your expedition has begun.")}><Swords size={15} /> Depart</KButton>
                        {m.reason && <p className="text-xs text-neon-yellow mt-2" role="status">{m.reason}</p>}</div>
                </Panel>; })}
            </div>
            {!missions.length && <Panel className="p-6">No expeditions are currently posted. Check back with the realm's steward.</Panel>}
        </div>}
        {tab === "oaths" && <div className="space-y-5" role="tabpanel">
            <p className="text-sm text-muted-foreground">One oath at a time. Leaving resets faction renown and service; you may swear a new oath after {world.rejoin_hours} real hours. Rank depends on days and deeds, so it cannot be bought.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">{world.factions.map(faction => <Panel key={faction.id} className="p-6 faction-card">
                <Shield className="text-neon-yellow mb-4" size={30} /><div className="realm-eyebrow">{faction.motto}</div><h2 className="font-display text-2xl text-white mt-2">{faction.name}</h2><p className="text-sm text-muted-foreground leading-relaxed mt-3 mb-5">{faction.description}</p>
                <ol className="rank-ladder">{faction.ranks.map((r, i) => <li key={i}><span className="rank-dot">{i + 1}</span><div><strong className="text-white">{r.name}</strong><div className="text-xs text-muted-foreground mt-1">{r.days} real days · {r.renown} renown · {r.service_hours} h of service</div></div></li>)}</ol>
                {f?.id === faction.id ? <Pill tone="green">Your sworn faction</Pill> : <div className="mt-5"><p className="text-xs text-muted-foreground mb-3">Oath cost: {money(faction.join_cost)} · legal standing ≥ {faction.min_legal}</p>
                    {confirmOath === faction.id ? <div className="space-y-3"><p className="text-sm text-neon-yellow">Swear your oath to {faction.name}?</p><KButton variant="solid" loading={busy} onClick={() => run("/realm/factions/" + faction.id + "/join", {}, "Oath sworn.")}>Confirm oath</KButton> <KButton variant="ghost" onClick={() => setConfirmOath(null)}>Back</KButton></div>
                        : <KButton variant="solid" disabled={!!faction.join_reason || busy} onClick={() => setConfirmOath(faction.id)}>Swear an oath</KButton>}
                    {faction.join_reason && <p className="text-xs text-neon-yellow mt-2">{faction.join_reason}</p>}</div>}
            </Panel>)}</div>
            {f && <Panel className="p-5"><h3 className="font-display text-lg text-white">Lay down your banner</h3><p className="text-sm text-muted-foreground my-3">You lose your current rank, renown and service progress. Your personal level, possessions and trade are kept.</p>
                {confirmOath === "leave" ? <><KButton variant="danger" loading={busy} onClick={() => run("/realm/factions/leave", {}, "Your oath has ended.")}>Confirm leaving faction</KButton> <KButton variant="ghost" onClick={() => setConfirmOath(null)}>Stay</KButton></> : <KButton variant="ghost" disabled={busy || !!state?.activity || ["hospital", "jail"].includes(player?.status)} onClick={() => setConfirmOath("leave")}>Leave faction</KButton>}</Panel>}
        </div>}
        {tab === "reports" && <Panel className="p-5 space-y-5" role="tabpanel">
            {!world.reports.length && <p className="text-muted-foreground">Your chronicle is unwritten. Complete an expedition to record your first battle.</p>}
            {world.reports.map((r, i) => <article key={r.at + i} className="battle-report"><span className={r.won ? "text-neon-green" : "text-neon-red"}><Swords size={20} /></span><div className="flex-1"><div className="flex flex-wrap gap-2 items-center"><h3 className="font-display text-lg text-white">{r.name}</h3><Pill tone={r.won ? "green" : "red"}>{r.won ? "Victory" : "Retreat"}</Pill></div><p className="text-sm text-muted-foreground mt-2">{r.tactic} · {money(r.gold)} · {r.xp} XP · {r.renown} renown</p><p className="text-xs text-muted-foreground mt-1 inline-flex items-center gap-1"><Heart size={12} /> {r.damage} health lost · {new Date(r.at).toLocaleString()}</p></div></article>)}
        </Panel>}
    </div>;
}
