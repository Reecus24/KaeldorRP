import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, StatBar } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { SKILL_LABELS } from "@/lib/helpers";
import { BadgeCheck, TrendingUp, Briefcase, Clock } from "lucide-react";

export default function CurrentJob() {
    const { state, player, act } = useGame();
    const [data, setData] = useState(null);
    const [busy, setBusy] = useState(false);

    const load = () => api.get("/jobs/current").then(({ data }) => setData(data)).catch(() => setData({ job: null }));
    useEffect(() => { load(); }, [player?.job?.job_id]);

    const blocked = !!state?.activity || ["jail", "hospital"].includes(player?.status);

    const work = async (hours) => {
        setBusy(true);
        await act(() => api.post("/jobs/work", { hours }), `Clocked in for a ${hours}h shift`);
        await load();
        setBusy(false);
    };
    const promote = async () => {
        setBusy(true);
        await act(() => api.post("/jobs/promote"), "You got promoted!");
        await load();
        setBusy(false);
    };
    const quit = async () => {
        setBusy(true);
        await act(() => api.post("/jobs/quit"), "You quit your job");
        await load();
        setBusy(false);
    };

    if (!data) return <Spinner />;

    if (!data.job) {
        return (
            <div className="space-y-6">
                <SectionTitle icon={BadgeCheck} title="Current Job" sub="You don't have a job yet." />
                <Panel className="p-10 text-center">
                    <Briefcase className="w-10 h-10 mx-auto text-muted-foreground/40 mb-3" />
                    <p className="text-muted-foreground mb-4">Head to the Job Center and get hired.</p>
                    <Link to="/jobs"><KButton>Browse Jobs</KButton></Link>
                </Panel>
            </div>
        );
    }

    const j = data.details || {};
    const job = data.job;
    const promo = data.promotion;

    return (
        <div className="space-y-6">
            <SectionTitle icon={BadgeCheck} kicker="Where you work" title={job.title} />

            <div className="grid md:grid-cols-2 gap-3">
                <Panel className="p-5">
                    <div className="flex items-center justify-between mb-4">
                        <span className="font-display font-bold text-white">Your Position</span>
                        <span className="font-mono text-neon-green text-lg tnum">${j.hourly_wage}/h</span>
                    </div>
                    <div className="space-y-3">
                        <StatBar label="Reliability" value={job.reliability || 50} color="#00F3FF" />
                        <div className="flex items-center justify-between text-sm">
                            <span className="text-muted-foreground">Shifts worked</span>
                            <span className="font-mono text-white tnum">{job.shifts_worked || 0}</span>
                        </div>
                        <div className="flex flex-wrap gap-1">
                            {Object.keys(j.skill_xp || {}).map((s) => <Pill key={s} tone="cyan">{SKILL_LABELS[s] || s}</Pill>)}
                        </div>
                    </div>
                    <KButton variant="danger" className="w-full mt-5" onClick={quit} loading={busy} data-testid="quit-job-button">Quit Job</KButton>
                </Panel>

                <Panel className="p-5">
                    <div className="flex items-center gap-2 mb-4">
                        <Clock className="w-4 h-4 text-neon-cyan" />
                        <span className="font-display font-bold text-white">Work a Shift</span>
                    </div>
                    {blocked ? (
                        <p className="text-sm text-neon-yellow font-mono">You're busy or unavailable. Finish your current activity first.</p>
                    ) : player.energy < 10 ? (
                        <p className="text-sm text-neon-red font-mono">Too exhausted to work. Rest or sleep first.</p>
                    ) : (
                        <>
                            <p className="text-[11px] text-muted-foreground mb-4">
                                Longer shifts pay more but drain energy, raise fatigue and stress. Pay scales with your effectiveness.
                            </p>
                            <div className="grid grid-cols-1 gap-2">
                                {(j.shift_options || [4]).map((h) => (
                                    <KButton key={h} variant="green" onClick={() => work(h)} loading={busy} data-testid={`work-shift-${h}`}>
                                        Work {h}h shift · ~${Math.round((j.hourly_wage || 0) * h * (state?.effectiveness || 1))}
                                    </KButton>
                                ))}
                            </div>
                        </>
                    )}
                </Panel>
            </div>

            {promo && promo.target && (
                <Panel className="p-5 border-neon-purple/30">
                    <div className="flex items-center gap-2 mb-3">
                        <TrendingUp className="w-4 h-4 text-neon-purple" />
                        <span className="font-display font-bold text-white">Promotion: {promo.target.title}</span>
                        <span className="font-mono text-neon-green ml-auto">${promo.target.hourly_wage}/h</span>
                    </div>
                    {promo.eligible ? (
                        <KButton variant="primary" onClick={promote} loading={busy} data-testid="promote-button">Accept Promotion</KButton>
                    ) : (
                        <div className="text-[11px] text-neon-yellow font-mono">Requirements: {promo.reasons.join(" · ")}</div>
                    )}
                </Panel>
            )}
        </div>
    );
}
