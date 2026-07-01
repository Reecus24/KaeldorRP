import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, StatBar } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { SKILL_LABELS, scheduleLabel, computeGameTime, shiftWindowOpen, fmtWindow } from "@/lib/helpers";
import { BadgeCheck, TrendingUp, Briefcase, Clock, Building2, LogOut, AlertTriangle } from "lucide-react";

export default function CurrentJob() {
    const { state, player, act } = useGame();
    const [data, setData] = useState(null);
    const [busy, setBusy] = useState(false);

    const load = () => api.get("/jobs/current").then(({ data }) => setData(data)).catch(() => setData({ job: null }));
    useEffect(() => { load(); }, [player?.job?.job_id]);

    const blocked = !!state?.activity || ["jail", "hospital"].includes(player?.status) || !!player?.on_shift;

    const work = async (shift) => {
        setBusy(true);
        await act(() => api.post("/jobs/work", { shift_id: shift.id }), `Clocked in for ${shift.name}`);
        await load();
        setBusy(false);
    };
    const clockOut = async (e) => {
        setBusy(true);
        await act(() => api.post(`/jobs/employment/${e.id}/clock-out`), "You clocked out early");
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

    const npc = data.npc;
    const playerJobs = data.player_jobs || [];

    if (!npc && playerJobs.length === 0) {
        return (
            <div className="space-y-6">
                <SectionTitle icon={BadgeCheck} title="Current Job" sub="You don't have a job yet." />
                <Panel className="p-10 text-center">
                    <Briefcase className="w-10 h-10 mx-auto text-muted-foreground/40 mb-3" />
                    <p className="text-muted-foreground mb-4">Get hired at the Job Center, or work for a real player in the Job Market.</p>
                    <div className="flex gap-2 justify-center">
                        <Link to="/jobs"><KButton>Browse Jobs</KButton></Link>
                        <Link to="/job-market"><KButton variant="ghost">Player Job Market</KButton></Link>
                    </div>
                </Panel>
            </div>
        );
    }

    const j = npc?.details || {};
    const job = npc?.job;
    const promo = npc?.promotion;
    const gt = computeGameTime(state);
    const gameHour = gt ? gt.getUTCHours() : 0;

    return (
        <div className="space-y-6">
            <SectionTitle icon={BadgeCheck} kicker="Where you work" title={npc ? job.title : "Your Employment"}
                sub={npc && playerJobs.length > 0 ? "You hold both an NPC job and player-business work — shifts can't overlap." : undefined} />

            {playerJobs.length > 0 && (
                <Panel className="p-5" data-testid="current-player-jobs">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <Building2 className="w-4 h-4 text-neon-purple" />
                        <span className="font-display font-bold text-white">Player-Business Employment</span>
                        <Pill tone="cyan">Auto-work on schedule</Pill>
                    </div>
                    <p className="text-[11px] text-muted-foreground mb-3">
                        You work automatically during your scheduled hours — wages and business output accrue in real time, even while offline.
                        You can't start other physical activities (sleep, travel, courses, other shifts) while on shift. Clock out early to free up,
                        but you forfeit the rest of today's pay and take a reliability hit.
                    </p>
                    <div className="grid sm:grid-cols-2 gap-3">
                        {playerJobs.map((e) => (
                            <div key={e.id} className="p-3 border border-white/10 rounded-sm" data-testid={`cur-emp-${e.id}`}>
                                <div className="flex items-center justify-between mb-1">
                                    <span className="font-display font-bold text-white text-sm">{e.business_name}</span>
                                    <Pill tone="green">${e.wage_per_hour}/h</Pill>
                                </div>
                                <div className="text-[11px] text-muted-foreground capitalize mb-1">{(e.role || "").replace(/_/g, " ")} · {Math.round(e.total_hours_worked || 0)}h worked · perf {Math.round(e.performance)}</div>
                                <div className="flex items-center gap-1.5 mb-2 flex-wrap">
                                    <Pill tone="purple"><Clock className="w-3 h-3 mr-0.5" />{scheduleLabel(e.schedule)}</Pill>
                                    {e.on_shift
                                        ? <Pill tone="green" data-testid={`cur-emp-onshift-${e.id}`}>On shift now</Pill>
                                        : <Pill tone="yellow" data-testid={`cur-emp-offshift-${e.id}`}>Off shift</Pill>}
                                </div>
                                {e.today && e.today.hours > 0 && (
                                    <div className="text-[10px] text-muted-foreground mb-2 border-l-2 border-neon-purple/40 pl-2" data-testid={`cur-emp-today-${e.id}`}>
                                        Today: {e.today.hours}h · earned <span className="text-neon-green">${Math.round(e.today.wage)}</span>
                                    </div>
                                )}
                                {e.on_shift ? (
                                    <KButton variant="danger" className="w-full" loading={busy} onClick={() => clockOut(e)} data-testid={`clock-out-${e.id}`}>
                                        <LogOut className="w-3.5 h-3.5" /> Clock Out Early
                                    </KButton>
                                ) : (
                                    <Link to="/job-market"><KButton variant="ghost" className="w-full" data-testid={`cur-emp-manage-${e.id}`}>Manage in Player Jobs</KButton></Link>
                                )}
                            </div>
                        ))}
                    </div>
                </Panel>
            )}

            {npc && (
            <>
            <div className="grid md:grid-cols-2 gap-3">
                <Panel className="p-5">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-2">
                            <span className="font-display font-bold text-white">Your Position</span>
                            <Pill tone="purple">Tier {j.tier || 1}</Pill>
                        </div>
                        <span className="font-mono text-neon-green text-lg tnum">${j.hourly_wage}/h</span>
                    </div>
                    <div className="space-y-3">
                        <StatBar label="Reliability" value={job.reliability || 50} color="#00F3FF" />
                        <div className="flex items-center justify-between text-sm">
                            <span className="text-muted-foreground">Hours worked</span>
                            <span className="font-mono text-white tnum" data-testid="hours-worked">{Math.round(job.hours_worked || 0)}h</span>
                        </div>
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
                            <p className="text-[11px] text-muted-foreground mb-3">
                                Each shift has its own hours, time window, pay & risk. Night and hazardous shifts pay more but can cause a work accident (health loss). A shift can only start inside its time window.
                            </p>
                            <div className="grid grid-cols-1 gap-2">
                                {(j.shift_options || []).filter((s) => typeof s === "object" && s !== null).map((s) => {
                                    const open = shiftWindowOpen(s.start_window, gameHour);
                                    const est = Math.round((j.hourly_wage || 0) * s.duration_hours * (state?.effectiveness || 1) * (s.pay_multiplier || 1));
                                    const highRisk = (s.injury_risk || 0) >= 0.1;
                                    return (
                                        <div key={s.id} className={cn("border rounded-sm p-3", open ? "border-white/12" : "border-white/8 opacity-60")} data-testid={`shift-option-${s.id}`}>
                                            <div className="flex items-center justify-between gap-2 mb-1.5 flex-wrap">
                                                <span className="font-display font-bold text-white text-sm">{s.name}</span>
                                                <span className="font-mono text-neon-green tnum">~${est}</span>
                                            </div>
                                            <div className="flex items-center gap-1.5 flex-wrap mb-2.5">
                                                <Pill tone="cyan">{s.duration_hours}h</Pill>
                                                <Pill><Clock className="w-3 h-3 mr-0.5" />{fmtWindow(s.start_window)}</Pill>
                                                {Number(s.pay_multiplier) !== 1 && <Pill tone="green">×{s.pay_multiplier} pay</Pill>}
                                                {Number(s.xp_multiplier) !== 1 && <Pill tone="purple">×{s.xp_multiplier} XP</Pill>}
                                                {highRisk
                                                    ? <Pill tone="red"><AlertTriangle className="w-3 h-3 mr-0.5" />High risk</Pill>
                                                    : (s.injury_risk > 0 ? <Pill tone="yellow">Low risk</Pill> : null)}
                                            </div>
                                            {open ? (
                                                <KButton variant="green" className="w-full" onClick={() => work(s)} loading={busy} data-testid={`work-shift-${s.id}`}>
                                                    Start {s.name}
                                                </KButton>
                                            ) : (
                                                <div className="text-[11px] text-neon-yellow font-mono" data-testid={`shift-closed-${s.id}`}>
                                                    Opens {fmtWindow(s.start_window)} · now {String(gameHour).padStart(2, "0")}:00
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </>
                    )}
                </Panel>
            </div>

            {promo && promo.target && (
                <Panel className="p-5 border-neon-purple/30" data-testid="promotion-panel">
                    <div className="flex items-center gap-2 mb-3 flex-wrap">
                        <TrendingUp className="w-4 h-4 text-neon-purple" />
                        <span className="font-display font-bold text-white">Promotion: {promo.target.title}</span>
                        <Pill tone="cyan">Tier {promo.target.tier}</Pill>
                        <span className="font-mono text-neon-green ml-auto">${promo.target.hourly_wage}/h</span>
                    </div>

                    <div className="mb-3">
                        <div className="flex justify-between items-center text-[11px] font-mono mb-1.5">
                            <span className="uppercase tracking-wider text-muted-foreground">Hours worked toward promotion</span>
                            <span className="text-white tnum" data-testid="promo-hours">{Math.round(promo.have_hours)} / {promo.need_hours}h</span>
                        </div>
                        <div className="h-2.5 w-full bg-white/5 border border-white/10 overflow-hidden rounded-sm">
                            <div className="h-full transition-all duration-500 rounded-sm"
                                style={{ width: `${Math.min(100, (promo.have_hours / (promo.need_hours || 1)) * 100)}%`, backgroundColor: "#B026FF", boxShadow: "0 0 10px #B026FF88" }} />
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-1.5 mb-3">
                        <Pill tone={promo.hours_met ? "green" : "yellow"}>{promo.need_hours}h worked</Pill>
                        {Object.entries(promo.requirements?.skills || {}).map(([s, l]) => <Pill key={s} tone="cyan">{SKILL_LABELS[s] || s} Lv {l}</Pill>)}
                        {(promo.requirements?.education || []).map((e) => <Pill key={e}>{e.replace(/_/g, " ")}</Pill>)}
                        {promo.requirements?.reputation && <Pill>Rep {promo.requirements.reputation}</Pill>}
                        <Pill tone={promo.reliability >= (promo.requirements?.min_reliability || 55) ? "green" : "yellow"}>Reliability {promo.reliability}</Pill>
                    </div>

                    {promo.eligible ? (
                        <KButton variant="primary" onClick={promote} loading={busy} data-testid="promote-button">Accept Promotion</KButton>
                    ) : (
                        <div className="space-y-1" data-testid="promotion-blocked">
                            {promo.hours_met && <div className="text-[11px] text-neon-cyan font-mono">You have enough hours, but you still need:</div>}
                            {promo.reasons.map((r, i) => <div key={i} className="text-[11px] text-neon-yellow font-mono">• {r}</div>)}
                        </div>
                    )}
                </Panel>
            )}
            </>
            )}
        </div>
    );
}
