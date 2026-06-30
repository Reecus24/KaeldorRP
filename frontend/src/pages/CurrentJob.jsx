import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, StatBar } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { SKILL_LABELS } from "@/lib/helpers";
import { BadgeCheck, TrendingUp, Briefcase, Clock, Building2 } from "lucide-react";

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

    return (
        <div className="space-y-6">
            <SectionTitle icon={BadgeCheck} kicker="Where you work" title={npc ? job.title : "Your Employment"}
                sub={npc && playerJobs.length > 0 ? "You hold both an NPC job and player-business work — shifts can't overlap." : undefined} />

            {playerJobs.length > 0 && (
                <Panel className="p-5" data-testid="current-player-jobs">
                    <div className="flex items-center gap-2 mb-3">
                        <Building2 className="w-4 h-4 text-neon-purple" />
                        <span className="font-display font-bold text-white">Player-Business Employment</span>
                    </div>
                    <div className="grid sm:grid-cols-2 gap-3">
                        {playerJobs.map((e) => (
                            <div key={e.id} className="p-3 border border-white/10 rounded-sm" data-testid={`cur-emp-${e.id}`}>
                                <div className="flex items-center justify-between mb-1">
                                    <span className="font-display font-bold text-white text-sm">{e.business_name}</span>
                                    <Pill tone="green">${e.wage_per_hour}/h</Pill>
                                </div>
                                <div className="text-[11px] text-muted-foreground capitalize mb-1">{(e.role || "").replace(/_/g, " ")} · {Math.round(e.total_hours_worked || 0)}h worked · perf {Math.round(e.performance)}</div>
                                <div className="text-[10px] text-muted-foreground mb-2">Paid ${e.wage_per_hour}/h at the end of each shift (e.g. ${Math.round(e.wage_per_hour * 4)} for 4h).</div>
                                <Link to="/job-market"><KButton variant="ghost" className="w-full" data-testid={`cur-emp-manage-${e.id}`}>Work shifts / Manage</KButton></Link>
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
