import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, StatBar } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { realDurationLabel } from "@/lib/helpers";
import { MarketPanel } from "@/components/game/MarketPanel";
import { Skull, AlertTriangle, Clock, Lock, XCircle, Gavel, Gem as Bitcoin, Users, Flame, Star } from "lucide-react";

const HERO = "https://images.unsplash.com/photo-1688377051459-aebb99b42bff?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1ODB8MHwxfHNlYXJjaHwzfHxjeWJlcnB1bmslMjBuZW9uJTIwZGFzaGJvYXJkJTIwZWxlbWVudHN8ZW58MHx8fHwxNzgyNzg4NTY4fDA&ixlib=rb-4.1.0&q=85";

function LockedScreen({ status }) {
    return (
        <div className="space-y-6">
            <div className="relative overflow-hidden rounded-sm border border-neon-red/20">
                <img src={HERO} alt="" className="absolute inset-0 w-full h-full object-cover opacity-20" />
                <div className="absolute inset-0 bg-gradient-to-r from-[#101A16] via-[#101A16]/90 to-[#101A16]/50" />
                <div className="relative p-6">
                    <SectionTitle icon={Skull} kicker="Off the books" title="The Underworld"
                        sub="This door is closed to strangers." />
                </div>
            </div>
            <Panel className="p-8 text-center border-neon-red/30 max-w-2xl mx-auto" data-testid="underworld-locked">
                <Lock className="w-10 h-10 text-neon-red mx-auto mb-4" />
                <h3 className="font-display font-bold text-white text-lg mb-2">Underworld Locked</h3>
                <p className="text-sm text-muted-foreground mb-5">{status?.reason}</p>
                <div className="text-[11px] text-muted-foreground font-mono mb-5">
                    Requires a Shady Contact at Trust ≥ {status?.min_trust} and Relationship ≥ {status?.min_score}.
                </div>
                <Link to="/social">
                    <KButton variant="danger" data-testid="goto-social-btn"><Users className="w-4 h-4" /> Go to Social → Meet People</KButton>
                </Link>
            </Panel>
        </div>
    );
}

function CrimeCard({ a, blocked, busy, onCommit }) {
    const bust = Math.round((a.bust_risk ?? a.police_risk) * 100);
    const fail = Math.round((a.fail_chance ?? a.failure_chance) * 100);
    return (
        <Panel className="p-5 flex flex-col" data-testid={`illegal-card-${a.id}`}>
            <div className="flex items-start justify-between gap-2 mb-1">
                <h3 className="font-display font-bold text-white leading-tight">{a.name}</h3>
                <span className="font-mono text-neon-green text-sm">¤ {a.reward_min}–¤ {a.reward_max}</span>
            </div>
            <p className="text-[11px] text-muted-foreground mb-3 flex-1">{a.desc}</p>

            {/* Two distinct risk profiles */}
            <div className="grid grid-cols-2 gap-2 mb-3">
                <div className="rounded-sm border border-neon-yellow/30 bg-neon-yellow/5 p-2.5" data-testid={`fail-profile-${a.id}`}>
                    <div className="flex items-center gap-1 text-neon-yellow text-[11px] font-bold mb-1">
                        <XCircle className="w-3.5 h-3.5" /> Fail {fail}%
                    </div>
                    <div className="text-[10px] text-muted-foreground leading-tight">Job flops. No reward, but you walk away clean — no dungeon.</div>
                </div>
                <div className="rounded-sm border border-neon-red/30 bg-neon-red/5 p-2.5" data-testid={`bust-profile-${a.id}`}>
                    <div className="flex items-center gap-1 text-neon-red text-[11px] font-bold mb-1">
                        <Gavel className="w-3.5 h-3.5" /> Bust {bust}%
                    </div>
                    <div className="text-[10px] text-muted-foreground leading-tight">
                        Caught: ¤ {a.fine_amount} fine · {realDurationLabel(a.jail_minutes, 1)} dungeon · +{a.suspicion_gain} suspicion.
                    </div>
                </div>
            </div>

            <div className="flex items-center gap-1 text-[11px] text-muted-foreground font-mono mb-3">
                <Clock className="w-3 h-3" /> Takes {realDurationLabel(a.duration_minutes, 1)}
            </div>

            {!a.available ? (
                <div className="flex items-center gap-1 text-[11px] text-neon-yellow font-mono"><Lock className="w-3 h-3" /> {a.reason}</div>
            ) : (
                <KButton variant="danger" className="w-full" loading={busy} disabled={blocked} onClick={() => onCommit(a)} data-testid={`commit-${a.id}`}>
                    {blocked ? "Busy" : "Do It"}
                </KButton>
            )}
        </Panel>
    );
}

export default function Underworld() {
    const { state, player, act } = useGame();
    const [data, setData] = useState(null);
    const [status, setStatus] = useState(null);
    const [wanted, setWanted] = useState(null);
    const [busyId, setBusyId] = useState(null);
    const [tab, setTab] = useState("crime");

    const load = async () => {
        const [{ data: st }, { data: acts }] = await Promise.all([
            api.get("/underworld/status"),
            api.get("/illegal-actions"),
        ]);
        setStatus(st);
        setData(acts);
        api.get("/underworld/most-wanted").then(({ data: w }) => setWanted(w)).catch(() => {});
    };
    useEffect(() => { load().catch(() => { setData({ access: false, actions: [] }); setStatus({ access: false }); }); }, []);

    const blocked = !!state?.activity || ["jail", "hospital"].includes(player?.status);

    const commit = async (a) => {
        setBusyId(a.id);
        await act(() => api.post(`/illegal-actions/${a.id}/commit`), `You started ${a.name}...`);
        await load();
        setBusyId(null);
    };

    if (!data || !status) return <Spinner />;
    if (!status.access) return <LockedScreen status={status} />;

    const acts = data.actions || [];

    return (
        <div className="space-y-6">
            <div className="relative overflow-hidden rounded-sm border border-neon-red/20">
                <img src={HERO} alt="" className="absolute inset-0 w-full h-full object-cover opacity-25" />
                <div className="absolute inset-0 bg-gradient-to-r from-[#101A16] via-[#101A16]/85 to-[#101A16]/40" />
                <div className="relative p-6">
                    <SectionTitle icon={Skull} kicker={`Vouched for by ${status.contact}`} title="The Underworld"
                        sub="Fast money with real consequences. Watch the two risk profiles: a job can simply FAIL (no reward, no dungeon) or get you BUSTED (fine, dungeon, suspicion)." />
                </div>
            </div>

            <Panel className="p-4 border-neon-red/30 flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-neon-red shrink-0" />
                <div className="flex-1">
                    <div className="text-sm text-white font-medium">Criminal Suspicion</div>
                    <div className="text-[11px] text-muted-foreground">Higher suspicion sharply raises your Bust chance. Lay low or bribe to lower it.</div>
                </div>
                <div className="w-40"><StatBar value={player.criminal_suspicion} color="#DE8274" invert /></div>
            </Panel>

            <div className="flex gap-2">
                <KButton variant={tab === "crime" ? "danger" : "ghost"} onClick={() => setTab("crime")} data-testid="tab-crime"><Skull className="w-4 h-4" /> Jobs</KButton>
                <KButton variant={tab === "crypto" ? "danger" : "ghost"} onClick={() => setTab("crypto")} data-testid="tab-crypto"><Bitcoin className="w-4 h-4" /> Relic Exchange</KButton>
                <KButton variant={tab === "wanted" ? "danger" : "ghost"} onClick={() => setTab("wanted")} data-testid="tab-wanted"><Flame className="w-4 h-4" /> Most Wanted</KButton>
            </div>

            {tab === "crime" ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {acts.map((a) => (
                        <CrimeCard key={a.id} a={a} blocked={blocked} busy={busyId === a.id} onCommit={commit} />
                    ))}
                </div>
            ) : tab === "crypto" ? (
                <div>
                    <div className="flex items-center gap-1.5 mb-3">
                        <Bitcoin className="w-4 h-4 text-neon-yellow" />
                        <span className="font-display font-bold text-white">Relic Exchange</span>
                        <span className="text-[11px] text-muted-foreground">— unregulated, wildly volatile. High risk, high reward.</span>
                    </div>
                    <MarketPanel endpoint="/market/crypto" kind="crypto" accent="#D9B66B" />
                </div>
            ) : (
                <MostWantedBoard wanted={wanted} />
            )}
        </div>
    );
}

function WantedStars({ level }) {
    return (
        <span className="inline-flex gap-0.5" title={`Wanted level ${level}/5`}>
            {[1, 2, 3, 4, 5].map((i) => (
                <Star key={i} className={`w-3 h-3 ${i <= level ? "text-neon-red fill-neon-red" : "text-white/15"}`} />
            ))}
        </span>
    );
}

function MostWantedBoard({ wanted }) {
    if (!wanted) return <Spinner />;
    const board = wanted.board || [];
    return (
        <div className="space-y-4" data-testid="most-wanted-board">
            <Panel className="p-4 border-neon-red/30 bg-neon-red/[0.03] flex items-center gap-3">
                <Flame className="w-5 h-5 text-neon-red shrink-0" />
                <div className="flex-1">
                    <div className="text-sm text-white font-medium">Realm Most Wanted</div>
                    <div className="text-[11px] text-muted-foreground">
                        Ranked by watch HEAT — a blend of criminal suspicion and a fallen legal standing.
                        {wanted.my_rank ? <span className="text-neon-red"> You are #{wanted.my_rank} of {wanted.total_wanted} (heat {wanted.my_heat}).</span>
                            : <span className="text-neon-green"> You're off the radar — keep it that way.</span>}
                    </div>
                </div>
            </Panel>

            {board.length === 0 ? (
                <Panel className="p-8 text-center text-muted-foreground text-sm" data-testid="most-wanted-empty">
                    The streets are quiet. Nobody's drawing watch heat right now.
                </Panel>
            ) : (
                <div className="space-y-2">
                    {board.map((r, i) => (
                        <Panel key={r.id} data-testid={`wanted-row-${i}`}
                            className={`p-3 flex items-center gap-3 ${r.is_you ? "border-neon-red/50 bg-neon-red/[0.05]" : ""}`}>
                            <div className={`w-7 text-center font-mono font-bold ${i < 3 ? "text-neon-red" : "text-muted-foreground"}`}>#{i + 1}</div>
                            <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <span className="font-display font-bold text-white truncate">{r.name}</span>
                                    {r.is_you && <Pill tone="danger">You</Pill>}
                                    <span className="text-[10px] font-mono text-muted-foreground">Lvl {r.level}</span>
                                </div>
                                <div className="flex items-center gap-3 text-[11px] text-muted-foreground font-mono mt-0.5">
                                    <span>Susp {r.suspicion}</span>
                                    <span>Legal {r.legal_standing}</span>
                                    <span>{r.crimes} crimes</span>
                                    {r.jailed > 0 && <span className="text-neon-red">{r.jailed}× jailed</span>}
                                </div>
                            </div>
                            <div className="flex flex-col items-end gap-1 shrink-0">
                                <WantedStars level={r.wanted_level} />
                                <span className="font-mono text-[11px] text-neon-red flex items-center gap-1"><Flame className="w-3 h-3" /> {r.heat}</span>
                            </div>
                        </Panel>
                    ))}
                </div>
            )}
        </div>
    );
}
