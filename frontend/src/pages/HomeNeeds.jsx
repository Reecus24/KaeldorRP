import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel } from "@/components/game/primitives";
import ActionCard from "@/components/game/ActionCard";
import { Home } from "lucide-react";

const GROUPS = [
    { key: "rest", label: "Rest & Recovery" },
    { key: "food", label: "Food" },
    { key: "hygiene", label: "Hygiene" },
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

    const load = () => api.get("/actions").then(({ data }) => setActions(data)).catch(() => setActions([]));
    useEffect(() => { load(); }, []);

    const blocked = !!state?.activity || ["jail", "hospital"].includes(player?.status);

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
                sub="Manage your body and mind. Neglect food, sleep or hygiene and your performance — and health — will suffer." />

            {blocked && (
                <Panel className="p-4 border-neon-yellow/30">
                    <p className="text-sm text-neon-yellow font-mono">
                        {player?.status === "jail" ? "You're in jail — wait it out or post bail." :
                         player?.status === "hospital" ? "You're recovering in hospital." :
                         "You're busy with another activity. Finish or cancel it first."}
                    </p>
                </Panel>
            )}

            {GROUPS.map((g) => {
                const items = actions.filter((a) => a.category === g.key);
                if (items.length === 0) return null;
                return (
                    <div key={g.key}>
                        <div className="font-mono text-[11px] uppercase tracking-[0.25em] text-neon-cyan/70 mb-3">{g.label}</div>
                        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                            {items.map((a) => (
                                <ActionCard key={a.id} action={a} onStart={start} blocked={blocked} loading={loadingId === a.id} />
                            ))}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
