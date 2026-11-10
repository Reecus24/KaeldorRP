import { worldLabel } from "@/lib/helpers";
import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { api, errMessage } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, EmptyState } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { realDurationLabel, fmtDuration, money, REL_STATUS, scoreColor, relTime, actionRewards } from "@/lib/helpers";
import { cn } from "@/lib/utils";
import {
    Users, ArrowLeft, ShieldX, ShieldCheck, AlertTriangle, Sparkles, X, Clock, Coins,
    MessageCircle, Phone, Gift, HeartHandshake, HandHelping, Award, Banknote, LifeBuoy,
    Heart, Skull, Coffee, Flower, BookOpen, UtensilsCrossed, Watch, Lock, Handshake,
} from "lucide-react";

const ICONS = {
    MessageCircle, Phone, Gift, HeartHandshake, HandHelping, Award, Banknote, LifeBuoy,
    Heart, Skull, Users, Coffee, Flower, BookOpen, UtensilsCrossed, Watch, Handshake,
};
const SEV = { success: "text-neon-green", info: "text-neon-cyan/90", warning: "text-neon-yellow", danger: "text-neon-red" };

function Tile({ label, value, accent = "#fff" }) {
    return (
        <Panel className="p-3 text-center">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
            <div className="font-display font-bold text-xl" style={{ color: accent }}>{value}</div>
        </Panel>
    );
}

export default function ContactDetail() {
    const { cid } = useParams();
    const navigate = useNavigate();
    const { state, refresh } = useGame();
    const [detail, setDetail] = useState(null);
    const [gifts, setGifts] = useState([]);
    const [busy, setBusy] = useState(null);
    const [giftOpen, setGiftOpen] = useState(false);
    const busyActivity = !!state?.activity;

    const load = useCallback(async () => {
        try {
            const { data } = await api.get(`/social/contacts/${cid}`);
            setDetail(data);
        } catch (e) {
            if (e?.response?.status === 404) navigate("/social");
        }
    }, [cid, navigate]);

    useEffect(() => {
        load();
        api.get("/social/gifts").then(({ data }) => setGifts(data)).catch(() => {});
    }, [load]);

    useEffect(() => {
        const t = setInterval(load, 8000);
        return () => clearInterval(t);
    }, [load]);

    const interact = async (actionId, giftId) => {
        setBusy(actionId);
        try {
            const { data } = await api.post(`/social/contacts/${cid}/interact`, { action_id: actionId, gift_id: giftId || null });
            if (data.started) toast.success("Plans made — check your activity timer.");
            else toast[data.severity === "warning" ? "message" : "success"](data.message);
            setGiftOpen(false);
            await Promise.all([load(), refresh()]);
        } catch (e) { toast.error(errMessage(e)); }
        setBusy(null);
    };

    const toggleBlock = async () => {
        setBusy("block");
        try {
            const { data } = await api.post(`/social/contacts/${cid}/block`);
            toast.success(data.status === "blocked" ? "Contact blocked" : "Contact unblocked");
            await load();
        } catch (e) { toast.error(errMessage(e)); }
        setBusy(null);
    };

    if (!detail) return <Spinner />;
    const c = detail.contact;
    const meta = REL_STATUS[c.status] || { label: c.status, tone: "default" };
    const blocked = c.status === "blocked";

    return (
        <div className="space-y-6">
            <Link to="/social" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-neon-cyan font-mono" data-testid="back-to-social">
                <ArrowLeft className="w-3.5 h-3.5" /> All contacts
            </Link>

            <SectionTitle icon={Users} kicker={`${c.archetype_label || worldLabel(c.relationship_type)} · Age ${c.age} · Known ${relTime(Math.floor((Date.now() - new Date(c.known_since).getTime()) / 1000))}`}
                title={c.name}
                right={<Pill tone={meta.tone} className="text-sm py-1">{meta.label}</Pill>} />

            {/* STAT TILES */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Tile label="Relationship" value={c.relationship_score} accent={scoreColor(c.relationship_score)} />
                <Tile label="Trust" value={c.trust} accent="#D1B579" />
                <Tile label="Respect" value={c.respect} accent="#8EB89B" />
                {c.romance_capable
                    ? <Tile label="Attraction" value={c.attraction} accent="#B6A0CC" />
                    : <Tile label="Their Mood" value={c.mood} accent="#fff" />}
            </div>

            {c.traits?.length > 0 && (
                <div className="flex flex-wrap gap-1.5 items-center">
                    <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-mono mr-1">Personality</span>
                    {c.traits.map((t) => <Pill key={t} tone="purple">{worldLabel(t)}</Pill>)}
                </div>
            )}

            {/* WARNINGS */}
            {detail.warnings?.length > 0 && (
                <Panel className="p-4 border-neon-yellow/40 space-y-1.5" data-testid="contact-warnings">
                    {detail.warnings.map((w, i) => (
                        <div key={i} className="flex items-center gap-2 text-sm text-neon-yellow"><AlertTriangle className="w-4 h-4 shrink-0" /> {w}</div>
                    ))}
                </Panel>
            )}

            {/* OPPORTUNITIES */}
            <Panel className="p-4 border-neon-green/20" data-testid="contact-opportunities">
                <div className="font-display font-bold text-white mb-2 flex items-center gap-2"><Sparkles className="w-4 h-4 text-neon-green" /> Opportunities</div>
                <ul className="space-y-1">
                    {detail.opportunities.map((o, i) => <li key={i} className="text-sm text-muted-foreground flex gap-2"><span className="text-neon-green">›</span> {o}</li>)}
                </ul>
            </Panel>

            {/* ACTIONS */}
            {blocked ? (
                <Panel className="p-5 text-center space-y-3">
                    <div className="text-sm text-muted-foreground">You've blocked {c.name}. Unblock to interact again.</div>
                    <KButton variant="ghost" loading={busy === "block"} onClick={toggleBlock} data-testid="unblock-button"><ShieldCheck className="w-3.5 h-3.5" /> Unblock</KButton>
                </Panel>
            ) : (
                <div>
                    <div className="font-display font-bold text-white mb-3">Interactions</div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {detail.actions.map((a) => {
                            const Icon = ICONS[a.icon] || Sparkles;
                            const isActivity = a.timing === "activity";
                            const onCd = a.cooldown_remaining > 0;
                            const disabled = !a.available || (isActivity && busyActivity);
                            const isGift = a.kind === "give_gift";
                            return (
                                <Panel key={a.id} className="p-4 flex flex-col" data-testid={`rel-action-${a.id}`}>
                                    <div className="flex items-center gap-2 mb-1">
                                        <Icon className="w-4 h-4 text-neon-cyan shrink-0" />
                                        <span className="font-display font-bold text-white text-sm">{a.label}</span>
                                    </div>
                                    <p className="text-[11px] text-muted-foreground mb-2 flex-1">{a.desc}</p>
                                    {actionRewards(a).length > 0 && (
                                        <div className="flex flex-wrap gap-1 mb-2" data-testid={`rel-action-rewards-${a.id}`}>
                                            {actionRewards(a).map((r, i) => (
                                                <span key={i} className={cn("text-[10px] font-mono px-1.5 py-0.5 rounded-sm border",
                                                    r.tone === "green" ? "text-neon-green border-neon-green/30 bg-neon-green/5" : "text-neon-red border-neon-red/30 bg-neon-red/5")}>
                                                    {r.label}
                                                </span>
                                            ))}
                                        </div>
                                    )}
                                    {a.kind === "network_pro" && c.perk && !c.perk_granted && (
                                        <div className="flex items-center gap-1 text-[10px] text-neon-purple font-mono mb-2" data-testid={`rel-action-unlock-${a.id}`}>
                                            <Sparkles className="w-3 h-3" /> Unlock: {c.perk.label} (+{Math.round((c.perk.step || 0.05) * 100)}%, permanent)
                                        </div>
                                    )}
                                    <div className="flex items-center gap-3 text-[10px] text-muted-foreground font-mono mb-2">
                                        {isActivity && <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {realDurationLabel(a.duration_minutes, state?.time_scale || 1)}</span>}
                                        {a.money_cost > 0 && <span className="flex items-center gap-1 text-neon-red"><Coins className="w-3 h-3" /> ¤ {a.money_cost}</span>}
                                    </div>
                                    {!a.available && a.reason && (
                                        <div className="flex items-center gap-1 text-[10px] text-neon-yellow font-mono mb-2">
                                            <Lock className="w-3 h-3" /> {onCd ? `Cooldown ${fmtDuration(a.cooldown_remaining)}` : a.reason}
                                        </div>
                                    )}
                                    <KButton variant={isActivity ? "primary" : "ghost"} className="w-full" disabled={disabled} loading={busy === a.id}
                                        onClick={() => (isGift ? setGiftOpen(true) : interact(a.id))} data-testid={`rel-action-btn-${a.id}`}>
                                        {isActivity && busyActivity ? "Busy" : isGift ? "Choose Gift" : isActivity ? "Plan" : "Do it"}
                                    </KButton>
                                </Panel>
                            );
                        })}
                    </div>
                    <div className="mt-4">
                        <KButton variant="danger" loading={busy === "block"} onClick={toggleBlock} data-testid="block-button"><ShieldX className="w-3.5 h-3.5" /> Block {c.name}</KButton>
                    </div>
                </div>
            )}

            {/* HISTORY */}
            <div>
                <div className="font-display font-bold text-white mb-2">History</div>
                <Panel className="p-0 overflow-hidden bg-[#101A16]" data-testid="contact-history">
                    {(!detail.history || detail.history.length === 0) ? (
                        <div className="px-4 py-8 text-center text-muted-foreground text-sm font-mono">No history yet.</div>
                    ) : detail.history.map((h, i) => (
                        <div key={i} className="px-4 py-2.5 font-mono text-xs border-b border-white/5">
                            <span className="text-muted-foreground/50">{new Date(h.ts).toLocaleString()} </span>
                            <span className="text-foreground">{h.text}</span>
                        </div>
                    ))}
                </Panel>
            </div>

            {/* GIFT MODAL */}
            {giftOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-testid="gift-modal">
                    <div className="absolute inset-0 bg-black/75" onClick={() => setGiftOpen(false)} />
                    <Panel className="relative w-full max-w-md p-5 max-h-[85vh] flex flex-col">
                        <div className="flex items-center justify-between mb-3">
                            <span className="font-display font-bold text-white">Give {c.name} a gift</span>
                            <button onClick={() => setGiftOpen(false)}><X className="w-5 h-5 text-muted-foreground" /></button>
                        </div>
                        <div className="space-y-2 overflow-y-auto">
                            {gifts.map((g) => {
                                const GIcon = ICONS[g.icon] || Gift;
                                return (
                                    <button key={g.id} onClick={() => interact("give_gift", g.id)} disabled={busy === "give_gift"}
                                        className="w-full text-left p-3 border border-white/12 rounded-sm hover:border-neon-cyan/50 transition-colors disabled:opacity-50 flex items-center gap-3" data-testid={`gift-opt-${g.id}`}>
                                        <GIcon className="w-5 h-5 text-neon-purple shrink-0" />
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center justify-between">
                                                <span className="font-display font-bold text-white text-sm">{g.label}</span>
                                                <span className="font-mono text-neon-red text-xs">¤ {g.cost}</span>
                                            </div>
                                            <div className="text-[11px] text-muted-foreground">{g.desc}</div>
                                        </div>
                                    </button>
                                );
                            })}
                        </div>
                    </Panel>
                </div>
            )}
        </div>
    );
}
