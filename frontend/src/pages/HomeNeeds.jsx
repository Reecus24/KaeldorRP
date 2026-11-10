import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel } from "@/components/game/primitives";
import ActionCard from "@/components/game/ActionCard";
import { Home } from "lucide-react";

const GROUPS = [
    { key: "rest", label: "Rest & Recovery" },
    { key: "food", label: "Food" },
    { key: "health", label: "Health & Fitness" },
    { key: "leisure", label: "Leisure & Mind" },
    { key: "hustle", label: "Side Hustles" },
    { key: "errand", label: "Errands" },
    { key: "maintenance", label: "Maintenance" },
];

export default function HomeNeeds() {
    const { state, player, act } = useGame();
    const [actions, setActions] = useState(null);
    const [loadingId, setLoadingId] = useState(null);
    const { hash } = useLocation();
    const actionsLoaded = actions !== null;

    const load = useCallback(() => api.get("/actions").then(({ data }) => setActions(data)).catch(() => setActions((current) => current || [])), []);
    // Cooldowns and requirements can change while this page remains open.
    useEffect(() => { load(); }, [load, player?.last_resolved_at]);
    useEffect(() => {
        if (hash && actionsLoaded) document.getElementById(hash.slice(1))?.scrollIntoView({ block: "start" });
    }, [hash, actionsLoaded]);

    const blocked = !!state?.activity || !!player?.on_shift || ["jail", "hospital"].includes(player?.status);

    const start = async (a) => {
        setLoadingId(a.id);
        await act(() => api.post(`/actions/${a.id}/start`), `Started: ${a.name}`);
        await load();
        setLoadingId(null);
    };

    if (!actions) return <Spinner />;

    return (
        <div className="space-y-6">
            <SectionTitle icon={Home} kicker="Take care of yourself" title="Home & Needs"
                sub="Manage your body and mind. Neglect food, sleep or rest and your performance — and health — will suffer." />
            <p className="text-xs text-muted-foreground" data-testid="needs-timing-note">
                Activity rewards apply when the timer finishes. Hunger can still rise while you wait.
            </p>
            <nav className="flex flex-wrap gap-2" aria-label="Needs categories">
                {GROUPS.filter((group) => actions.some((action) => action.category === group.key)).map((group) => (
                    <a key={group.key} href={`#${group.key}`} className="px-3 py-2 border border-white/15 rounded-sm text-sm text-muted-foreground hover:text-neon-cyan hover:border-neon-cyan/40">{group.label}</a>
                ))}
            </nav>

            {blocked && (
                <Panel className="p-4 border-neon-yellow/30">
                    <p className="text-sm text-neon-yellow font-mono">
                        {player?.status === "jail" ? "You're in jail — wait it out or post bail." :
                         player?.status === "hospital" ? "You're recovering in hospital." :
                         player?.on_shift ? "You're on shift — finish work or clock out before starting an activity." :
                         "You're busy with another activity. Finish or cancel it first."}
                    </p>
                </Panel>
            )}

            {GROUPS.map((g) => {
                const items = actions.filter((a) => a.category === g.key);
                if (items.length === 0) return null;
                return (
                    <section key={g.key} id={g.key} className="scroll-mt-20">
                        <h2 className="font-display font-bold text-base text-white mb-4">{g.label} <span className="font-mono text-xs font-normal text-muted-foreground ml-2">{items.length} options</span></h2>
                        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                            {items.map((a) => (
                                <ActionCard key={a.id} action={a} onStart={start} blocked={blocked} loading={loadingId === a.id} />
                            ))}
                        </div>
                    </section>
                );
            })}
        </div>
    );
}
