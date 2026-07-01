import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api, errMessage } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, StatBar, EmptyState } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { realDurationLabel, REL_STATUS, scoreColor, relTime } from "@/lib/helpers";
import { cn } from "@/lib/utils";
import {
    Users, Heart, Briefcase, Building2, Home, Skull, UsersRound, ScrollText, UserPlus,
    MessageCircle, Phone, ChevronRight, Sparkles, HeartHandshake,
} from "lucide-react";

const SEV = { success: "text-neon-green", info: "text-neon-cyan/90", warning: "text-neon-yellow", danger: "text-neon-red" };

const TABS = [
    { key: "all", label: "All", icon: Users },
    { key: "friend", label: "Friends", icon: HeartHandshake, cats: ["friend"] },
    { key: "work", label: "Work", icon: Briefcase, cats: ["work"] },
    { key: "romance", label: "Romance", icon: Heart, cats: ["romance"] },
    { key: "business", label: "Business", icon: Building2, cats: ["business"] },
    { key: "housing", label: "Housing", icon: Home, cats: ["housing"] },
    { key: "underworld", label: "Underworld", icon: Skull, cats: ["underworld"] },
    { key: "family", label: "Family", icon: UsersRound, cats: ["family"] },
    { key: "meet", label: "Meet People", icon: UserPlus },
    { key: "events", label: "Event Log", icon: ScrollText },
];

function Tab({ active, onClick, icon: Icon, children, testid }) {
    return (
        <button onClick={onClick} data-testid={testid}
            className={cn("inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono uppercase tracking-wider rounded-sm border transition-colors",
                active ? "border-neon-cyan text-neon-cyan bg-neon-cyan/10" : "border-white/12 text-muted-foreground hover:text-white hover:border-white/25")}>
            {Icon && <Icon className="w-3.5 h-3.5" />}{children}
        </button>
    );
}

function ContactCard({ c, onQuick, busyKey }) {
    const meta = REL_STATUS[c.status] || { label: c.status, tone: "default" };
    return (
        <Panel className={cn("p-4 flex flex-col", c.status === "angry" && "border-neon-red/40", c.status === "romantic" && "border-neon-purple/40", c.decaying && "border-neon-yellow/30")} data-testid={`contact-card-${c.id}`}>
            <div className="flex items-start justify-between gap-2 mb-2">
                <div className="min-w-0">
                    <h3 className="font-display font-bold text-white text-base leading-tight truncate">{c.name}</h3>
                    <div className="text-[11px] text-muted-foreground font-mono mt-0.5">{c.archetype_label || c.relationship_type.replace(/_/g, " ")} · Age {c.age}</div>
                </div>
                <Pill tone={meta.tone} className="shrink-0">{meta.label}</Pill>
            </div>
            {c.perk && (
                <div className="mb-2">
                    <Pill tone={c.perk_granted ? "green" : "cyan"} className="!text-[9px]">
                        {c.perk_granted ? `✓ ${c.perk.label} active` : `Perk: ${c.perk.label}`}
                    </Pill>
                </div>
            )}

            <div className="mb-2">
                <div className="flex justify-between items-center mb-1">
                    <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Relationship</span>
                    <span className="font-mono text-[11px] tnum" style={{ color: scoreColor(c.relationship_score) }}>{c.relationship_score}</span>
                </div>
                <div className="h-2 w-full bg-white/5 border border-white/10 rounded-sm overflow-hidden">
                    <div className="h-full rounded-sm transition-all" style={{ width: `${(c.relationship_score + 100) / 2}%`, backgroundColor: scoreColor(c.relationship_score), boxShadow: `0 0 8px ${scoreColor(c.relationship_score)}88` }} />
                </div>
            </div>

            <div className="grid grid-cols-3 gap-2 text-center text-[10px] mb-2">
                <div><div className="text-muted-foreground uppercase">Trust</div><div className="font-mono text-neon-cyan">{c.trust}</div></div>
                <div><div className="text-muted-foreground uppercase">Respect</div><div className="font-mono text-neon-green">{c.respect}</div></div>
                {c.romance_capable
                    ? <div><div className="text-muted-foreground uppercase">Attract</div><div className="font-mono text-neon-purple">{c.attraction}</div></div>
                    : <div><div className="text-muted-foreground uppercase">Mood</div><div className="font-mono text-white">{c.mood}</div></div>}
            </div>

            {c.traits?.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-2">
                    {c.traits.map((t) => <Pill key={t} tone="purple" className="!text-[9px]">{t.replace(/_/g, " ")}</Pill>)}
                </div>
            )}

            <div className="text-[10px] text-muted-foreground font-mono mb-3 flex items-center gap-1">
                <span className={c.decaying ? "text-neon-yellow" : ""}>Last contact {relTime(c.last_interaction_seconds)}</span>
            </div>

            <div className="flex gap-2 mt-auto">
                <KButton variant="ghost" className="flex-1 !px-2" loading={busyKey === c.id + "small_talk"} onClick={() => onQuick(c.id, "small_talk")} data-testid={`quick-talk-${c.id}`}>
                    <MessageCircle className="w-3.5 h-3.5" /> Talk
                </KButton>
                <KButton variant="ghost" className="flex-1 !px-2" loading={busyKey === c.id + "call_text"} onClick={() => onQuick(c.id, "call_text")} data-testid={`quick-call-${c.id}`}>
                    <Phone className="w-3.5 h-3.5" /> Call
                </KButton>
                <Link to={`/social/${c.id}`} className="shrink-0">
                    <KButton variant="primary" className="!px-3" data-testid={`open-contact-${c.id}`}><ChevronRight className="w-4 h-4" /></KButton>
                </Link>
            </div>
        </Panel>
    );
}

function MeetPeople() {
    const { state, refresh } = useGame();
    const [locs, setLocs] = useState(null);
    const [busy, setBusy] = useState(null);
    const busyActivity = !!state?.activity;

    const load = useCallback(() => api.get("/social/locations").then(({ data }) => setLocs(data)).catch(() => setLocs([])), []);
    useEffect(() => { load(); }, [load]);

    const visit = async (l) => {
        setBusy(l.id);
        try {
            await api.post(`/social/visit/${l.id}`);
            toast.success(`Heading to ${l.name}`);
            await Promise.all([load(), refresh()]);
        } catch (e) { toast.error(errMessage(e)); }
        setBusy(null);
    };

    if (!locs) return <Spinner />;
    return (
        <div className="space-y-3">
            <p className="text-sm text-muted-foreground">Head out to a place to meet new people. Each visit takes real time and shows who you might run into. Meet a Manager or Wholesaler, then network (Talk Business) to unlock permanent business perks.</p>
            <div className="grid sm:grid-cols-2 gap-3">
                {locs.map((l) => (
                    <Panel key={l.id} className="p-4 flex flex-col" data-testid={`location-${l.id}`}>
                        <div className="flex items-center justify-between mb-1">
                            <span className="font-display font-bold text-white">{l.name}</span>
                            <span className="font-mono text-[11px] text-muted-foreground">{realDurationLabel(l.duration_minutes, state?.time_scale || 1)}{l.money_cost ? ` · $${l.money_cost}` : ""}</span>
                        </div>
                        <p className="text-[11px] text-muted-foreground mb-2 flex-1">{l.desc}</p>
                        <div className="flex flex-wrap gap-1 mb-3" data-testid={`encounters-${l.id}`}>
                            {l.encounters.map((e) => (
                                <span key={e.archetype_id} className="font-mono text-[10px] px-1.5 py-0.5 rounded-sm border border-neon-cyan/25 text-neon-cyan/90">
                                    {e.label} {Math.round(e.chance * 100)}%
                                </span>
                            ))}
                        </div>
                        <KButton variant="primary" className="w-full" disabled={busyActivity || !l.available} loading={busy === l.id}
                            onClick={() => visit(l)} data-testid={`visit-btn-${l.id}`}>
                            {busyActivity ? "Busy" : !l.available ? (l.reason || "Unavailable") : <><Sparkles className="w-3.5 h-3.5" /> Go</>}
                        </KButton>
                    </Panel>
                ))}
            </div>
        </div>
    );
}

export default function Social() {
    const { events, refresh } = useGame();
    const [data, setData] = useState(null);
    const [tab, setTab] = useState("all");
    const [busyKey, setBusyKey] = useState(null);

    const load = useCallback(() => api.get("/social/contacts").then(({ data }) => setData(data)).catch(() => setData({ contacts: [], summary: {} })), []);
    useEffect(() => { load(); }, [load]);

    const onQuick = async (cid, actionId) => {
        setBusyKey(cid + actionId);
        try {
            const { data: res } = await api.post(`/social/contacts/${cid}/interact`, { action_id: actionId });
            toast[res.severity === "warning" ? "message" : "success"](res.message);
            await Promise.all([load(), refresh()]);
        } catch (e) { toast.error(errMessage(e)); }
        setBusyKey(null);
    };

    if (!data) return <Spinner />;
    const s = data.summary || {};
    const tabMeta = TABS.find((t) => t.key === tab);
    const visible = tabMeta?.cats ? data.contacts.filter((c) => tabMeta.cats.includes(c.category)) : data.contacts;
    const socialEvents = (events || []).filter((e) => e.type === "social" || (e.type === "housing" && /landlord|eviction/i.test(e.message)) || (e.type === "job" && /FIRED|fired/.test(e.message)));

    return (
        <div className="space-y-6">
            <SectionTitle icon={Users} kicker="Your people" title="Social Circle"
                sub="You start with no one. Meet people at the Bar, the Gym or through Work, then build professional ties — a Manager can unlock a permanent staff wage discount, a Wholesaler a material cost discount."
                right={
                    <div className="hidden sm:flex gap-2">
                        <Pill tone="cyan">{s.total || 0} contacts</Pill>
                        {s.close > 0 && <Pill tone="green">{s.close} close</Pill>}
                        {s.romantic > 0 && <Pill tone="purple">{s.romantic} romantic</Pill>}
                        {s.angry > 0 && <Pill tone="red">{s.angry} angry</Pill>}
                    </div>
                } />

            <div className="flex flex-wrap gap-2">
                {TABS.map((t) => <Tab key={t.key} active={tab === t.key} onClick={() => setTab(t.key)} icon={t.icon} testid={`social-tab-${t.key}`}>{t.label}</Tab>)}
            </div>

            {tab === "meet" ? (
                <MeetPeople />
            ) : tab === "events" ? (
                <Panel className="p-0 overflow-hidden bg-[#050505]" data-testid="social-event-log">
                    {socialEvents.length === 0 ? (
                        <div className="px-4 py-8 text-center text-muted-foreground text-sm font-mono">No social events yet. Interact with people and check back.</div>
                    ) : socialEvents.map((e, i) => (
                        <div key={e.id || i} className="px-4 py-2.5 font-mono text-xs border-b border-white/5">
                            <span className="text-muted-foreground/50">{new Date(e.ts).toLocaleString()} </span>
                            <span className={SEV[e.severity] || "text-foreground"}>{e.message}</span>
                        </div>
                    ))}
                </Panel>
            ) : visible.length === 0 ? (
                <EmptyState icon={Users} title="Nobody here yet" sub="Use the Meet People tab to go to the Bar, the Gym or Network at Work and grow your circle." />
            ) : (
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {visible.map((c) => <ContactCard key={c.id} c={c} onQuick={onQuick} busyKey={busyKey} />)}
                </div>
            )}
        </div>
    );
}
