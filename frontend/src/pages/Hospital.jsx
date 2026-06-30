import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, StatBar } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { fmtDuration } from "@/lib/helpers";
import { Stethoscope, HeartPulse } from "lucide-react";

export default function Hospital() {
    const { player, act, tick } = useGame();
    const [info, setInfo] = useState(null);
    const [busy, setBusy] = useState(false);

    const load = () => api.get("/hospital/status").then(({ data }) => setInfo(data)).catch(() => {});
    useEffect(() => { load(); }, [player?.status]);

    const inHospital = player?.status === "hospital";
    let remaining = 0;
    if (inHospital && player?.hospital_until) remaining = Math.max(0, (new Date(player.hospital_until).getTime() - Date.now()) / 1000);
    // eslint-disable-next-line no-unused-expressions
    tick;

    const treat = async () => {
        setBusy(true);
        await act(() => api.post("/hospital/treat"), "Treated — health restored");
        await load();
        setBusy(false);
    };

    if (!info || !player) return <Spinner />;

    return (
        <div className="space-y-6">
            <SectionTitle icon={Stethoscope} kicker="Patch yourself up" title="Hospital"
                sub="Push too hard and your health collapses. Pay for treatment to restore it instantly, or recover slowly over time." />

            <Panel className="p-6">
                <div className="flex items-center gap-2 mb-4"><HeartPulse className="w-5 h-5 text-neon-red" /><span className="font-display font-bold text-white">Health</span></div>
                <StatBar value={player.health} color="#FF3B6B" />
                <div className="font-mono text-sm text-white mt-2 tnum">{Math.round(player.health)} / 100</div>

                {inHospital && (
                    <div className="mt-5 p-4 bg-[#050505] border border-neon-red/30 rounded-sm">
                        <div className="text-sm text-neon-red font-medium mb-1">You're admitted to hospital.</div>
                        <div className="font-mono text-2xl text-white tnum neon-text">{fmtDuration(remaining)}</div>
                        <div className="text-[11px] text-muted-foreground mt-1">until discharge — or pay to leave now.</div>
                    </div>
                )}

                <KButton variant="green" className="mt-5" loading={busy} onClick={treat} disabled={player.health >= 100 && !inHospital} data-testid="treat-button">
                    {inHospital ? `Pay $${info.treat_cost} to discharge & heal` : `Pay $${info.treat_cost} for full treatment`}
                </KButton>
            </Panel>
        </div>
    );
}
