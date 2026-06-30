import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { fmtDuration, money } from "@/lib/helpers";
import { Lock, Scale } from "lucide-react";

export default function Jail() {
    const { player, act, tick } = useGame();
    const [info, setInfo] = useState(null);
    const [busy, setBusy] = useState(false);

    const load = () => api.get("/jail/status").then(({ data }) => setInfo(data)).catch(() => {});
    useEffect(() => { load(); }, [player?.status]);

    const inJail = player?.status === "jail";
    let remaining = 0;
    if (inJail && player?.jail_until) remaining = Math.max(0, (new Date(player.jail_until).getTime() - Date.now()) / 1000);
    // eslint-disable-next-line no-unused-expressions
    tick;

    const bail = async () => {
        setBusy(true);
        await act(() => api.post("/jail/bail"), "You posted bail");
        await load();
        setBusy(false);
    };

    if (!player) return <Spinner />;

    return (
        <div className="space-y-6">
            <SectionTitle icon={Lock} kicker="Behind bars" title="Jail"
                sub="Get caught breaking the law and you'll do time here. You can wait it out, or post bail to walk free early." />

            {!inJail ? (
                <Panel className="p-10 text-center">
                    <Scale className="w-10 h-10 mx-auto text-neon-green/60 mb-3" />
                    <div className="font-display text-lg text-white">You're a free citizen</div>
                    <div className="text-sm text-muted-foreground mt-1">Keep it that way... or don't.</div>
                </Panel>
            ) : (
                <Panel className="p-8 text-center border-neon-red/40">
                    <Lock className="w-10 h-10 mx-auto text-neon-red mb-3 animate-pulse-dot" />
                    <div className="font-display font-bold text-xl text-white">Locked Up</div>
                    <div className="font-mono text-4xl text-neon-red mt-4 tnum neon-text">{fmtDuration(remaining)}</div>
                    <div className="text-sm text-muted-foreground mt-2">remaining sentence</div>
                    <KButton variant="danger" className="mt-6" loading={busy} disabled={info && player.cash + player.bank < info.bail_cost} onClick={bail} data-testid="bail-button">
                        Post Bail · {info ? money(info.bail_cost) : "…"}
                    </KButton>
                </Panel>
            )}
        </div>
    );
}
