import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, StatBar } from "@/components/game/primitives";
import { Lock, FileWarning } from "lucide-react";

export default function Legal() {
    const { player } = useGame();
    if (!player) return <Spinner />;
    const record = player.criminal_record || [];
    const meta = player.stats_meta || {};

    return (
        <div className="space-y-6">
            <SectionTitle icon={Lock} kicker="Your rap sheet" title="Police Record"
                sub="Crime pays — until it doesn't. Track your suspicion, convictions and standing with the law." />

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <Panel className="p-4"><div className="text-[11px] uppercase text-muted-foreground">Suspicion</div><div className="font-display text-2xl text-neon-yellow tnum">{Math.round(player.criminal_suspicion)}</div></Panel>
                <Panel className="p-4"><div className="text-[11px] uppercase text-muted-foreground">Legal Standing</div><div className="font-display text-2xl text-neon-cyan tnum">{Math.round(player.legal_reputation)}</div></Panel>
                <Panel className="p-4"><div className="text-[11px] uppercase text-muted-foreground">Times Jailed</div><div className="font-display text-2xl text-neon-red tnum">{meta.times_jailed || 0}</div></Panel>
                <Panel className="p-4"><div className="text-[11px] uppercase text-muted-foreground">Crimes Committed</div><div className="font-display text-2xl text-white tnum">{meta.crimes_committed || 0}</div></Panel>
            </div>

            <Panel className="p-5">
                <div className="mb-4"><StatBar label="Criminal Suspicion" value={player.criminal_suspicion} color="#FF0055" invert /></div>
                <div className="font-mono text-[11px] uppercase tracking-[0.25em] text-muted-foreground mb-3">Convictions & Incidents</div>
                {record.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Clean record. For now.</p>
                ) : (
                    <div className="space-y-2">
                        {record.slice().reverse().map((r, i) => (
                            <div key={i} className="flex items-center gap-3 p-3 bg-[#050505] border border-white/8 rounded-sm" data-testid={`record-${i}`}>
                                <FileWarning className="w-4 h-4 text-neon-red shrink-0" />
                                <div className="flex-1">
                                    <div className="text-sm text-white">{r.type}</div>
                                    <div className="text-[11px] text-muted-foreground font-mono">{new Date(r.date).toLocaleString()}</div>
                                </div>
                                <Pill tone="red">Fined ${r.fine || 0}</Pill>
                            </div>
                        ))}
                    </div>
                )}
            </Panel>
        </div>
    );
}
