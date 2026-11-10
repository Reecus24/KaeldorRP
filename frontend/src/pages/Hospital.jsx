import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, StatBar } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { fmtDuration, money, needWarningThreshold } from "@/lib/helpers";
import { HeartPulse as Stethoscope, HeartPulse } from "lucide-react";

export default function Hospital() {
    const { player, state, act, confinementRemaining } = useGame();
    const [info, setInfo] = useState(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(false);

    const load = useCallback(() => api.get("/hospital/status").then(({ data }) => { setInfo(data); setError(false); }).catch(() => setError(true)), []);
    useEffect(() => { load(); }, [load, player?.status, player?.last_resolved_at]);

    const inHospital = player?.status === "hospital";
    const inJail = player?.status === "jail";
    const remaining = confinementRemaining.hospital;

    const treat = async () => {
        setBusy(true);
        await act(() => api.post("/hospital/treat"), "Treated — health restored");
        await load();
        setBusy(false);
    };

    if (!info && error) return <Panel className="p-6" role="alert"><p className="text-muted-foreground mb-3">Treatment details could not be loaded.</p><KButton onClick={load}>Try again</KButton></Panel>;
    if (!info || !player) return <Spinner />;
    const canAfford = player.cash + player.bank >= info.treat_cost;

    return (
        <div className="space-y-6">
            <SectionTitle icon={Stethoscope} kicker="Patch yourself up" title="Infirmary"
                sub="Push too hard and your health collapses. Pay for treatment to restore it instantly, or recover slowly over time." />

            <Panel className="p-6">
                <div className="flex items-center gap-2 mb-4"><HeartPulse className="w-5 h-5 text-neon-red" /><span className="font-display font-bold text-white">Health</span></div>
                <StatBar value={player.health} color="#8EB89B" warningThreshold={needWarningThreshold("health", state?.needs_rules)} showDirection />
                <div className="font-mono text-sm text-white mt-2 tnum">{Math.round(player.health)} / 100</div>

                {inHospital && (
                    <div className="mt-5 p-4 bg-[#101A16] border border-neon-red/30 rounded-sm">
                        <div className="text-sm text-neon-red font-medium mb-1">You're admitted to infirmary.</div>
                        <div className="font-mono text-2xl text-white tnum neon-text" data-testid="hospital-timer">
                            {remaining > 0 ? fmtDuration(remaining) : "Checking discharge…"}
                        </div>
                        <div className="text-sm text-muted-foreground mt-2">real time until discharge — or pay for full treatment now.</div>
                        {info.discharge_health != null && <div className="text-sm text-muted-foreground mt-2">Normal discharge restores health to at least {info.discharge_health}/100. Paid treatment restores 100/100.</div>}
                    </div>
                )}

                <KButton variant="green" className="mt-5" loading={busy} onClick={treat} disabled={inJail || !canAfford || (player.health >= 100 && !inHospital)} data-testid="treat-button">
                    {inHospital ? `Pay ¤ ${info.treat_cost} to discharge & heal` : `Pay ¤ ${info.treat_cost} for full treatment`}
                </KButton>
                {inJail && <p className="text-sm text-neon-yellow mt-3">You must leave dungeon before visiting the infirmary.</p>}
                {!canAfford && <p className="text-sm text-neon-yellow mt-3">Treatment costs {money(info.treat_cost)}. Available in cash and bank: {money(player.cash + player.bank)}.{inHospital ? " You can continue recovering until discharge." : ""}</p>}
            </Panel>
        </div>
    );
}
