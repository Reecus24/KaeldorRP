import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, Money } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { SKILL_LABELS, gameDuration } from "@/lib/helpers";
import { GraduationCap, Lock, CheckCircle2, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

export default function Education() {
    const { state, player, act } = useGame();
    const [courses, setCourses] = useState(null);
    const [busyId, setBusyId] = useState(null);

    const load = () => api.get("/courses").then(({ data }) => setCourses(data)).catch(() => setCourses([]));
    useEffect(() => { load(); }, []);

    const blocked = !!state?.activity || ["jail", "hospital"].includes(player?.status);

    const enroll = async (c) => {
        setBusyId(c.id);
        await act(() => api.post(`/courses/${c.id}/enroll`), `Enrolled in ${c.title}`);
        await load();
        setBusyId(null);
    };

    if (!courses) return <Spinner />;

    return (
        <div className="space-y-6">
            <SectionTitle icon={GraduationCap} kicker="Invest in yourself" title="Education"
                sub="Courses take real time but unlock better jobs, higher pay, business advantages and legal options. Study runs in the background — you can still do other things." />

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
                {courses.map((c) => (
                    <Panel key={c.id} className={cn("p-5 flex flex-col", c.completed && "border-neon-green/40")} data-testid={`course-card-${c.id}`}>
                        <div className="flex items-start justify-between gap-2 mb-1">
                            <h3 className="font-display font-bold text-white leading-tight">{c.title}</h3>
                            {c.completed && <CheckCircle2 className="w-4 h-4 text-neon-green shrink-0" />}
                        </div>
                        <p className="text-[11px] text-muted-foreground mb-3 flex-1">{c.desc}</p>

                        <div className="flex flex-wrap gap-1 mb-3">
                            {Object.entries(c.grants_skills || {}).map(([s, v]) => (
                                <Pill key={s} tone="green">+{v} {SKILL_LABELS[s] || s}</Pill>
                            ))}
                        </div>
                        <div className="text-[11px] text-neon-cyan/80 font-mono mb-3">Unlocks: {c.unlocks}</div>

                        <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground mb-3">
                            <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {gameDuration(c.duration_minutes)}</span>
                            <span className="text-neon-red">Tuition ${c.cost}</span>
                        </div>

                        {c.completed ? (
                            <Pill tone="green" className="justify-center py-2">Completed</Pill>
                        ) : !c.qualified ? (
                            <div className="flex items-center gap-1 text-[11px] text-neon-yellow font-mono"><Lock className="w-3 h-3" /> {c.reason}</div>
                        ) : (
                            <KButton className="w-full" loading={busyId === c.id} disabled={blocked} onClick={() => enroll(c)} data-testid={`enroll-${c.id}`}>
                                {blocked ? "Busy" : "Enroll"}
                            </KButton>
                        )}
                    </Panel>
                ))}
            </div>
        </div>
    );
}
