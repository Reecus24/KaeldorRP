import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, StatBar } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { gameDuration } from "@/lib/helpers";
import { Skull, AlertTriangle, Clock, Lock } from "lucide-react";

const HERO = "https://images.unsplash.com/photo-1688377051459-aebb99b42bff?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1ODB8MHwxfHNlYXJjaHwzfHxjeWJlcnB1bmslMjBuZW9uJTIwZGFzaGJvYXJkJTIwZWxlbWVudHN8ZW58MHx8fHwxNzgyNzg4NTY4fDA&ixlib=rb-4.1.0&q=85";

export default function Underworld() {
    const { state, player, act } = useGame();
    const [acts, setActs] = useState(null);
    const [busyId, setBusyId] = useState(null);

    const load = () => api.get("/illegal-actions").then(({ data }) => setActs(data)).catch(() => setActs([]));
    useEffect(() => { load(); }, []);

    const blocked = !!state?.activity || ["jail", "hospital"].includes(player?.status);

    const commit = async (a) => {
        setBusyId(a.id);
        await act(() => api.post(`/illegal-actions/${a.id}/commit`), `You started ${a.name}...`);
        await load();
        setBusyId(null);
    };

    if (!acts) return <Spinner />;

    return (
        <div className="space-y-6">
            <div className="relative overflow-hidden rounded-sm border border-neon-red/20">
                <img src={HERO} alt="" className="absolute inset-0 w-full h-full object-cover opacity-25" />
                <div className="absolute inset-0 bg-gradient-to-r from-[#050505] via-[#050505]/85 to-[#050505]/40" />
                <div className="relative p-6">
                    <SectionTitle icon={Skull} kicker="Off the books" title="The Underworld"
                        sub="Fast money with real consequences. Get caught and you'll pay fines, lose reputation, and do time. Every job raises suspicion." />
                </div>
            </div>

            <Panel className="p-4 border-neon-red/30 flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-neon-red shrink-0" />
                <div className="flex-1">
                    <div className="text-sm text-white font-medium">Criminal Suspicion</div>
                    <div className="text-[11px] text-muted-foreground">Higher suspicion means a much higher chance of getting caught. Lay low or bribe to lower it.</div>
                </div>
                <div className="w-40"><StatBar value={player.criminal_suspicion} color="#FF0055" invert /></div>
            </Panel>

            <div className="grid md:grid-cols-2 gap-3">
                {acts.map((a) => (
                    <Panel key={a.id} className="p-5 flex flex-col" data-testid={`illegal-card-${a.id}`}>
                        <div className="flex items-start justify-between gap-2 mb-1">
                            <h3 className="font-display font-bold text-white leading-tight">{a.name}</h3>
                            <Pill tone="red">{Math.round(a.police_risk * 100)}% bust risk</Pill>
                        </div>
                        <p className="text-[11px] text-muted-foreground mb-3 flex-1">{a.desc}</p>

                        <div className="grid grid-cols-2 gap-2 text-[11px] font-mono mb-3">
                            <span className="text-neon-green">Reward ${a.reward_min}–${a.reward_max}</span>
                            <span className="text-neon-yellow">+{a.suspicion_gain} suspicion</span>
                            <span className="text-neon-red">Fine ${a.fine_amount}</span>
                            <span className="text-neon-red">Jail {gameDuration(a.jail_minutes)}</span>
                        </div>

                        <div className="flex items-center gap-1 text-[11px] text-muted-foreground font-mono mb-3">
                            <Clock className="w-3 h-3" /> {gameDuration(a.duration_minutes)} · {Math.round(a.failure_chance * 100)}% fail chance
                        </div>

                        {!a.available ? (
                            <div className="flex items-center gap-1 text-[11px] text-neon-yellow font-mono"><Lock className="w-3 h-3" /> {a.reason}</div>
                        ) : (
                            <KButton variant="danger" className="w-full" loading={busyId === a.id} disabled={blocked} onClick={() => commit(a)} data-testid={`commit-${a.id}`}>
                                {blocked ? "Busy" : "Do It"}
                            </KButton>
                        )}
                    </Panel>
                ))}
            </div>
        </div>
    );
}
