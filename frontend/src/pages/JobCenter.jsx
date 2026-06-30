import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api, errMessage } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, Money } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { SKILL_LABELS, fmtDuration } from "@/lib/helpers";
import { Briefcase, Lock, CheckCircle2, Flame, Brain, Clock, FileText, XCircle, Hourglass } from "lucide-react";
import { cn } from "@/lib/utils";

const APP_TONE = { pending: "yellow", accepted: "green", rejected: "red", hired: "cyan", withdrawn: "default", expired: "default" };

function ApplicationsPanel({ apps, onAccept, onWithdraw, busy }) {
    const live = apps.filter((a) => ["pending", "accepted", "rejected"].includes(a.status));
    if (live.length === 0) return null;
    return (
        <Panel className="p-4" data-testid="npc-applications">
            <div className="font-display font-bold text-white mb-3 flex items-center gap-2"><FileText className="w-4 h-4 text-neon-cyan" /> Your Applications</div>
            <div className="space-y-2">
                {live.map((a) => (
                    <div key={a.id} className="flex items-center justify-between gap-3 p-2.5 border border-white/10 rounded-sm" data-testid={`application-${a.id}`}>
                        <div className="min-w-0">
                            <div className="flex items-center gap-2">
                                <span className="font-display font-bold text-white text-sm">{a.title}</span>
                                <Pill tone={APP_TONE[a.status]}>{a.status}</Pill>
                            </div>
                            {a.status === "pending" && <div className="text-[11px] text-muted-foreground flex items-center gap-1"><Hourglass className="w-3 h-3" /> Decision in ~{fmtDuration(a.resolves_in || 0)}</div>}
                            {a.status === "accepted" && <div className="text-[11px] text-neon-green">Offer: ${a.wage_offer}/h — accept to start!</div>}
                            {a.status === "rejected" && <div className="text-[11px] text-neon-red">Rejected: {a.reason}</div>}
                        </div>
                        <div className="flex gap-2 shrink-0">
                            {a.status === "accepted" && <KButton variant="green" loading={busy === a.id} onClick={() => onAccept(a)} data-testid={`accept-offer-${a.id}`}>Accept</KButton>}
                            {(a.status === "pending" || a.status === "accepted") && <KButton variant="ghost" loading={busy === a.id + "w"} onClick={() => onWithdraw(a)} data-testid={`withdraw-${a.id}`}>Withdraw</KButton>}
                        </div>
                    </div>
                ))}
            </div>
        </Panel>
    );
}

export default function JobCenter() {
    const { player, refresh } = useGame();
    const navigate = useNavigate();
    const [jobs, setJobs] = useState(null);
    const [apps, setApps] = useState([]);
    const [busyId, setBusyId] = useState(null);

    const loadJobs = useCallback(() => api.get("/jobs").then(({ data }) => setJobs(data)).catch(() => setJobs([])), []);
    const loadApps = useCallback(() => api.get("/jobs/applications").then(({ data }) => setApps(data)).catch(() => setApps([])), []);
    useEffect(() => { loadJobs(); loadApps(); }, [loadJobs, loadApps]);
    useEffect(() => { const t = setInterval(loadApps, 10000); return () => clearInterval(t); }, [loadApps]);

    const currentJobId = player?.job?.job_id;

    const apply = async (j) => {
        setBusyId(j.id);
        try {
            const { data } = await api.post(`/jobs/${j.id}/apply`, { message: null });
            toast.success(`Application submitted — decision in ~${data.resolves_in_minutes} min.`);
            await loadApps();
        } catch (e) { toast.error(errMessage(e)); }
        setBusyId(null);
    };

    const acceptOffer = async (a) => {
        setBusyId(a.id);
        try {
            await api.post(`/jobs/applications/${a.id}/accept`);
            toast.success(`You're now a ${a.title}!`);
            await Promise.all([loadApps(), loadJobs(), refresh()]);
            navigate("/current-job");
        } catch (e) { toast.error(errMessage(e)); }
        setBusyId(null);
    };

    const withdraw = async (a) => {
        setBusyId(a.id + "w");
        try { await api.post(`/jobs/applications/${a.id}/withdraw`); await loadApps(); } catch (e) { toast.error(errMessage(e)); }
        setBusyId(null);
    };

    if (!jobs) return <Spinner />;
    const appliedJobIds = new Set(apps.filter((a) => ["pending", "accepted"].includes(a.status)).map((a) => a.job_id));

    return (
        <div className="space-y-6">
            <SectionTitle icon={Briefcase} kicker="Earn a living" title="Job Center"
                sub="Submit an application — employers decide in real time based on your skills, education, reputation and record. Accept the offer to start working shifts." />

            <ApplicationsPanel apps={apps} onAccept={acceptOffer} onWithdraw={withdraw} busy={busyId} />

            <div className="grid md:grid-cols-2 gap-3">
                {jobs.map((j) => {
                    const isCurrent = j.id === currentJobId;
                    const pending = appliedJobIds.has(j.id);
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
                            ) : pending ? (
                                <KButton variant="ghost" className="w-full" disabled data-testid={`pending-job-${j.id}`}>
                                    <Clock className="w-3.5 h-3.5" /> Application Pending
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
