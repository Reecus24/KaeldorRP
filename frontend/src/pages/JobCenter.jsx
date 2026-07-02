import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api, errMessage } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { SKILL_LABELS, fmtDuration, fmtWindow } from "@/lib/helpers";
import {
    Briefcase, Lock, CheckCircle2, Flame, Brain, Clock, FileText, Hourglass, ChevronRight, ArrowLeft,
    ShoppingBag, UtensilsCrossed, Truck, Building2, Wrench, Shield, Landmark, X,
} from "lucide-react";
import { cn } from "@/lib/utils";

const APP_TONE = { pending: "yellow", accepted: "green", rejected: "red", hired: "cyan", withdrawn: "default", expired: "default" };
const SECTOR_ICONS = { ShoppingBag, UtensilsCrossed, Truck, Building2, Wrench, Shield, Landmark, Briefcase };

function ApplicationsPanel({ apps, onAccept, onRemove, busy }) {
    const live = apps.filter((a) => ["pending", "accepted", "rejected"].includes(a.status));
    if (live.length === 0) return null;
    return (
        <Panel className="p-4" data-testid="npc-applications">
            <div className="font-display font-bold text-white mb-3 flex items-center gap-2"><FileText className="w-4 h-4 text-neon-cyan" /> Your Applications</div>
            <div className="space-y-2">
                {live.map((a) => {
                    const active = ["pending", "accepted"].includes(a.status);
                    return (
                    <div key={a.id} className="flex items-center justify-between gap-3 p-2.5 border border-white/10 rounded-sm" data-testid={`application-${a.id}`}>
                        <div className="min-w-0">
                            <div className="flex items-center gap-2">
                                <span className="font-display font-bold text-white text-sm">{a.title}</span>
                                <Pill tone={APP_TONE[a.status]}>{a.status}</Pill>
                            </div>
                            {a.status === "pending" && <div className="text-[11px] text-muted-foreground flex items-center gap-1"><Hourglass className="w-3 h-3" /> Decision in ~{fmtDuration(a.resolves_in || 0)}</div>}
                            {a.status === "accepted" && (
                                <div className="text-[11px] text-neon-green" data-testid={`application-outcome-${a.id}`}>
                                    {a.outcome_message || `Offer: $${a.wage_offer}/h — accept to start!`}
                                </div>
                            )}
                            {a.status === "rejected" && (
                                <div className="text-[11px] text-neon-red" data-testid={`application-outcome-${a.id}`}>
                                    {a.outcome_message || `Rejected: ${a.reason}`}
                                </div>
                            )}
                        </div>
                        <div className="flex gap-2 shrink-0 items-center">
                            {a.status === "accepted" && <KButton variant="green" loading={busy === a.id} onClick={() => onAccept(a)} data-testid={`accept-offer-${a.id}`}>Accept</KButton>}
                            <button onClick={() => onRemove(a)} disabled={busy === a.id + "d"}
                                className="text-muted-foreground hover:text-neon-cyan hover:bg-neon-cyan/10 border border-white/10 hover:border-neon-cyan/40 transition-colors p-1.5 rounded-sm disabled:opacity-40"
                                title={active ? "Withdraw application" : "Dismiss application"}
                                aria-label={active ? "Withdraw application" : "Dismiss application"}
                                data-testid={`dismiss-application-${a.id}`}>
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                    );
                })}
            </div>
        </Panel>
    );
}

function JobCard({ j, isCurrent, pending, busy, onApply, onGoto }) {
    return (
        <Panel className={cn("p-5", isCurrent && "border-neon-green/40")} data-testid={`job-card-${j.id}`}>
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

            <div className="mb-3" data-testid={`working-hours-${j.id}`}>
                <div className="flex items-center gap-1.5 text-[11px] font-mono text-muted-foreground mb-1">
                    <Clock className="w-3 h-3 text-neon-cyan" /> Working Hours
                </div>
                <div className="flex flex-wrap gap-1.5">
                    {(j.shift_options || []).filter((s) => typeof s === "object" && s !== null).map((s) => (
                        <Pill key={s.id} tone={(s.injury_risk || 0) >= 0.1 ? "red" : "cyan"}>
                            {s.name}: {fmtWindow(s.start_window)} · {s.duration_hours}h
                        </Pill>
                    ))}
                    {(j.shift_options || []).filter((s) => typeof s !== "object").map((s) => (
                        <Pill key={s}>{s}h shift</Pill>
                    ))}
                    {(!j.shift_options || j.shift_options.length === 0) && (
                        <span className="text-[11px] text-muted-foreground/60 font-mono">Flexible hours</span>
                    )}
                </div>
            </div>

            {j.requirements && Object.keys(j.requirements).length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 text-[11px] mb-3" data-testid={`requirements-${j.id}`}>
                    <span className="text-muted-foreground font-mono">Requires:</span>
                    {Object.entries(j.requirements.skills || {}).map(([s, lvl]) => (
                        <Pill key={s} tone="cyan">{(SKILL_LABELS[s] || s)} {lvl}</Pill>
                    ))}
                    {(j.requirements.education || []).map((e) => (
                        <Pill key={e} tone="purple">{e.replace(/_/g, " ")}</Pill>
                    ))}
                    {j.requirements.min_reputation && <Pill>Reputation {j.requirements.min_reputation}+</Pill>}
                    {j.requirements.min_legal_reputation && <Pill tone="yellow">Legal Standing {j.requirements.min_legal_reputation}+</Pill>}
                    {j.requirements.min_social_status && <Pill tone="yellow">Social {j.requirements.min_social_status}+</Pill>}
                    {j.requirements.max_suspicion != null && <Pill tone="red">Suspicion ≤ {j.requirements.max_suspicion}</Pill>}
                    {j.requirements.vehicle && <Pill>Vehicle</Pill>}
                </div>
            )}

            {!j.qualified ? (
                <div className="flex items-center gap-1 text-[11px] text-neon-yellow font-mono">
                    <Lock className="w-3 h-3" /> {j.reason}
                </div>
            ) : isCurrent ? (
                <KButton variant="green" className="w-full" onClick={onGoto} data-testid={`goto-current-${j.id}`}>
                    <CheckCircle2 className="w-3.5 h-3.5" /> Go to Work
                </KButton>
            ) : pending ? (
                <KButton variant="ghost" className="w-full" disabled data-testid={`pending-job-${j.id}`}>
                    <Clock className="w-3.5 h-3.5" /> Application Pending
                </KButton>
            ) : (
                <KButton className="w-full" loading={busy === j.id} onClick={() => onApply(j)} data-testid={`apply-job-${j.id}`}>
                    Apply
                </KButton>
            )}
        </Panel>
    );
}

export default function JobCenter() {
    const { player, refresh } = useGame();
    const navigate = useNavigate();
    const [sectors, setSectors] = useState(null);
    const [entered, setEntered] = useState(null);   // { sector, jobs }
    const [loadingJobs, setLoadingJobs] = useState(false);
    const [apps, setApps] = useState([]);
    const [busyId, setBusyId] = useState(null);

    const loadSectors = useCallback(() => api.get("/jobs/sectors").then(({ data }) => setSectors(data)).catch(() => setSectors([])), []);
    const loadApps = useCallback(() => api.get("/jobs/applications").then(({ data }) => setApps(data)).catch(() => setApps([])), []);
    useEffect(() => { loadSectors(); loadApps(); }, [loadSectors, loadApps]);
    useEffect(() => { const t = setInterval(loadApps, 10000); return () => clearInterval(t); }, [loadApps]);

    const currentJobId = player?.job?.job_id;

    const enter = async (s) => {
        setLoadingJobs(true);
        try {
            const { data } = await api.get(`/jobs/sectors/${s.id}`);
            setEntered(data);
        } catch { setEntered({ sector: s, jobs: [] }); }
        setLoadingJobs(false);
    };

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
            await Promise.all([loadApps(), refresh()]);
            navigate("/current-job");
        } catch (e) { toast.error(errMessage(e)); }
        setBusyId(null);
    };

    const removeApp = async (a) => {
        const active = ["pending", "accepted"].includes(a.status);
        setBusyId(a.id + "d");
        try {
            if (active) {
                await api.post(`/jobs/applications/${a.id}/withdraw`);
                toast.success("Application withdrawn");
            } else {
                await api.post(`/jobs/applications/${a.id}/dismiss`);
                toast.success("Application dismissed");
            }
            await loadApps();
        } catch (e) { toast.error(errMessage(e)); }
        setBusyId(null);
    };

    if (!sectors) return <Spinner />;
    const appliedJobIds = new Set(apps.filter((a) => ["pending", "accepted"].includes(a.status)).map((a) => a.job_id));

    // ---- Inside a sector ----
    if (entered) {
        const s = entered.sector;
        const Icon = SECTOR_ICONS[s.icon] || Briefcase;
        return (
            <div className="space-y-6">
                <button onClick={() => { setEntered(null); loadSectors(); }} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-white" data-testid="back-to-sectors">
                    <ArrowLeft className="w-4 h-4" /> Back to Sectors
                </button>
                <SectionTitle icon={Icon} kicker={s.desc} title={s.name}
                    sub="Submit an application — employers decide in real time based on your skills, education, reputation and record. Accept the offer to start working shifts." />

                <ApplicationsPanel apps={apps} onAccept={acceptOffer} onRemove={removeApp} busy={busyId} />

                {loadingJobs ? <Spinner /> : entered.jobs.length === 0 ? (
                    <Panel className="p-6 text-center text-sm text-muted-foreground">No open listings in this sector right now.</Panel>
                ) : (
                    <div className="grid md:grid-cols-2 gap-3" data-testid="sector-jobs">
                        {entered.jobs.map((j) => (
                            <JobCard key={j.id} j={j} isCurrent={j.id === currentJobId} pending={appliedJobIds.has(j.id)}
                                busy={busyId} onApply={apply} onGoto={() => navigate("/current-job")} />
                        ))}
                    </div>
                )}
            </div>
        );
    }

    // ---- Sector browser ----
    return (
        <div className="space-y-6">
            <SectionTitle icon={Briefcase} kicker="Earn a living" title="Job Center"
                sub="Kaeldor's employment agencies, organised by sector. Pick a sector to see its open listings, then apply — employers decide in real time." />

            <ApplicationsPanel apps={apps} onAccept={acceptOffer} onRemove={removeApp} busy={busyId} />

            <div className="grid sm:grid-cols-2 gap-3" data-testid="sector-browser">
                {sectors.map((s) => {
                    const Icon = SECTOR_ICONS[s.icon] || Briefcase;
                    return (
                        <Panel key={s.id} className="p-5 flex items-center gap-4 group cursor-pointer hover:border-neon-cyan/40 transition-colors" onClick={() => enter(s)} data-testid={`sector-${s.id}`}>
                            <div className="w-12 h-12 rounded-sm bg-neon-cyan/10 border border-neon-cyan/20 flex items-center justify-center shrink-0">
                                <Icon className="w-6 h-6 text-neon-cyan" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <span className="font-display font-bold text-white">{s.name}</span>
                                <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">{s.desc}</p>
                                <span className="text-[10px] font-mono text-muted-foreground/70 uppercase tracking-wider">
                                    {s.job_count} listing{s.job_count === 1 ? "" : "s"}
                                    {s.open_count > 0 && <span className="text-neon-green"> · {s.open_count} you qualify for</span>}
                                </span>
                            </div>
                            <KButton variant="primary" onClick={(e) => { e.stopPropagation(); enter(s); }} data-testid={`open-listings-${s.id}`}>
                                Open Listings <ChevronRight className="w-3.5 h-3.5" />
                            </KButton>
                        </Panel>
                    );
                })}
            </div>
        </div>
    );
}
