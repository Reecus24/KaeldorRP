import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, Money } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { SKILL_LABELS } from "@/lib/helpers";
import { Briefcase, Lock, CheckCircle2, Flame, Brain } from "lucide-react";
import { cn } from "@/lib/utils";

export default function JobCenter() {
    const { player, act } = useGame();
    const navigate = useNavigate();
    const [jobs, setJobs] = useState(null);
    const [busyId, setBusyId] = useState(null);

    const load = () => api.get("/jobs").then(({ data }) => setJobs(data)).catch(() => setJobs([]));
    useEffect(() => { load(); }, []);

    const currentJobId = player?.job?.job_id;

    const apply = async (j) => {
        setBusyId(j.id);
        const r = await act(() => api.post(`/jobs/${j.id}/apply`), `Hired as ${j.title}!`);
        await load();
        setBusyId(null);
        if (r.ok) navigate("/current-job");
    };

    if (!jobs) return <Spinner />;

    return (
        <div className="space-y-6">
            <SectionTitle icon={Briefcase} kicker="Earn a living" title="Job Center"
                sub="Apply for a job, then work real-time shifts. Build skills and reputation to unlock promotions and better-paying careers." />

            <div className="grid md:grid-cols-2 gap-3">
                {jobs.map((j) => {
                    const isCurrent = j.id === currentJobId;
                    return (
                        <Panel key={j.id} className={cn("p-5", isCurrent && "border-neon-green/40")} data-testid={`job-card-${j.id}`}>
                            <div className="flex items-start justify-between gap-3 mb-2">
                                <div>
                                    <h3 className="font-display font-bold text-white text-lg leading-tight">{j.title}</h3>
                                    <div className="flex items-center gap-2 mt-1">
                                        <Pill tone="cyan">Tier {j.tier}</Pill>
                                        <Pill>{j.category}</Pill>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="font-mono text-neon-green text-lg tnum">${j.hourly_wage}/h</div>
                                    {isCurrent && <Pill tone="green" className="mt-1">Current</Pill>}
                                </div>
                            </div>

                            <p className="text-[11px] text-muted-foreground mb-3">{j.description}</p>

                            <div className="flex flex-wrap gap-3 text-[11px] font-mono text-muted-foreground mb-3">
                                <span className="flex items-center gap-1"><Flame className="w-3 h-3 text-neon-yellow" /> Fatigue {j.fatigue_per_hour}/h</span>
                                <span className="flex items-center gap-1 text-neon-red"><Flame className="w-3 h-3" /> Stress {j.stress_per_hour}/h</span>
                                <span className="flex items-center gap-1"><Brain className="w-3 h-3 text-neon-cyan" /> {Object.keys(j.skill_xp || {}).map((s) => SKILL_LABELS[s] || s).join(", ")}</span>
                            </div>

                            <div className="flex items-center gap-2 text-[11px] font-mono mb-3">
                                <span className="text-muted-foreground">Shifts:</span>
                                {j.shift_options.map((h) => <Pill key={h}>{h}h</Pill>)}
                            </div>

                            {!j.qualified ? (
                                <div className="flex items-center gap-1 text-[11px] text-neon-yellow font-mono">
                                    <Lock className="w-3 h-3" /> {j.reason}
                                </div>
                            ) : isCurrent ? (
                                <KButton variant="green" className="w-full" onClick={() => navigate("/current-job")} data-testid={`goto-current-${j.id}`}>
                                    <CheckCircle2 className="w-3.5 h-3.5" /> Go to Work
                                </KButton>
                            ) : (
                                <KButton className="w-full" loading={busyId === j.id} onClick={() => apply(j)} data-testid={`apply-job-${j.id}`}>
                                    Apply
                                </KButton>
                            )}
                        </Panel>
                    );
                })}
            </div>
        </div>
    );
}
