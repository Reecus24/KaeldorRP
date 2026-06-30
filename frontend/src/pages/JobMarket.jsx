import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { api, errMessage } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, EmptyState } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { scheduleLabel } from "@/lib/helpers";
import { cn } from "@/lib/utils";
import { Store, Briefcase, Send, Clock, X, CheckCircle2, XCircle, LogOut, Building2, Star, GraduationCap } from "lucide-react";

function ApplyModal({ biz, onClose, onApplied }) {
    const roles = biz.roles || [];
    const [role, setRole] = useState(roles[0]?.role || "");
    const [message, setMessage] = useState("");
    const [busy, setBusy] = useState(false);
    const submit = async () => {
        setBusy(true);
        try {
            await api.post(`/jobs/market/${biz.business_id}/apply`, { role, message });
            toast.success(`Applied to ${biz.name}`);
            onApplied();
        } catch (e) { toast.error(errMessage(e)); }
        setBusy(false);
    };
    const sel = roles.find((r) => r.role === role);
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-testid="market-apply-modal">
            <div className="absolute inset-0 bg-black/75" onClick={onClose} />
            <Panel className="relative w-full max-w-md p-5 space-y-3">
                <div className="flex items-center justify-between">
                    <span className="font-display font-bold text-white">Apply to {biz.name}</span>
                    <button onClick={onClose}><X className="w-5 h-5 text-muted-foreground" /></button>
                </div>
                <div>
                    <div className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1">Role you're applying for</div>
                    <select value={role} onChange={(e) => setRole(e.target.value)} data-testid="apply-role"
                        className="w-full bg-white/5 border border-white/12 rounded-sm px-3 py-2 text-sm text-white focus:outline-none focus:border-neon-cyan/50">
                        {roles.map((r) => <option key={r.role} value={r.role} className="bg-[#0d0d12]">{r.label} · {r.recommended} needed</option>)}
                    </select>
                    {sel?.desc && <p className="text-[11px] text-muted-foreground mt-1">{sel.desc}</p>}
                </div>
                <p className="text-[11px] text-neon-cyan/80">The owner sets your hourly wage based on your skills and role fit. From ${biz.base_hourly_wage}/h.</p>
                <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={3} placeholder="Why should they hire you?" data-testid="apply-message"
                    className="w-full bg-white/5 border border-white/12 rounded-sm px-3 py-2 text-sm text-white placeholder:text-muted-foreground/50 focus:outline-none focus:border-neon-cyan/50 resize-none" />
                <KButton variant="primary" className="w-full" loading={busy} disabled={!role} onClick={submit} data-testid="apply-submit"><Send className="w-3.5 h-3.5" /> Submit Application</KButton>
            </Panel>
        </div>
    );
}

function MarketTab() {
    const [list, setList] = useState(null);
    const [applyTo, setApplyTo] = useState(null);
    const load = useCallback(() => api.get("/jobs/market").then(({ data }) => setList(data)).catch(() => setList([])), []);
    useEffect(() => { load(); }, [load]);
    if (!list) return <Spinner />;
    if (list.length === 0) return <EmptyState icon={Store} title="No openings right now" sub="No player-owned businesses are hiring. Check back later, or open your own and hire!" />;
    return (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {list.map((b) => (
                <Panel key={b.business_id} className="p-4 flex flex-col" data-testid={`market-biz-${b.business_id}`}>
                    <div className="flex items-start justify-between mb-1">
                        <span className="font-display font-bold text-white">{b.name}</span>
                        <Pill tone="cyan"><Star className="w-3 h-3 mr-0.5" />{b.reputation}</Pill>
                    </div>
                    <div className="text-[11px] text-muted-foreground mb-2">{b.type} · owned by <span className="text-neon-purple">{b.owner_name}</span></div>
                    <div className="text-xs text-muted-foreground mb-1">From <span className="text-neon-green font-mono">${b.base_hourly_wage}/h</span></div>
                    {(b.roles || []).length > 0 && (
                        <div className="text-[11px] text-muted-foreground mb-3">Hiring: {(b.roles || []).map((r) => r.label).join(", ")}</div>
                    )}
                    <div className="mt-auto">
                        {b.my_status === "employed" ? <Pill tone="green" className="w-full justify-center py-1.5">You work here</Pill>
                            : b.my_status === "offered" ? <Pill tone="green" className="w-full justify-center py-1.5">Offer received — see My Jobs</Pill>
                            : b.my_status === "pending" ? <Pill tone="yellow" className="w-full justify-center py-1.5">Application pending</Pill>
                            : <KButton variant="primary" className="w-full" onClick={() => setApplyTo(b)} data-testid={`apply-biz-${b.business_id}`}><Briefcase className="w-3.5 h-3.5" /> Apply</KButton>}
                    </div>
                </Panel>
            ))}
            {applyTo && <ApplyModal biz={applyTo} onClose={() => setApplyTo(null)} onApplied={() => { setApplyTo(null); load(); }} />}
        </div>
    );
}

function MyJobsTab() {
    const { refresh } = useGame();
    const [data, setData] = useState(null);
    const [busy, setBusy] = useState(null);
    const load = useCallback(() => api.get("/jobs/employment").then(({ data }) => setData(data)).catch(() => setData({ employments: [], applications: [] })), []);
    useEffect(() => { load(); }, [load]);

    const clockOut = async (emp) => {
        setBusy(emp.id);
        try { await api.post(`/jobs/employment/${emp.id}/clock-out`); toast.success("You clocked out early"); await Promise.all([load(), refresh()]); }
        catch (e) { toast.error(errMessage(e)); }
        setBusy(null);
    };
    const respondTraining = async (emp, action) => {
        setBusy(emp.id + "t");
        try { await api.post(`/jobs/employment/${emp.id}/training/${action}`); toast.success(action === "accept" ? "Training completed!" : "Training declined"); await Promise.all([load(), refresh()]); }
        catch (e) { toast.error(errMessage(e)); }
        setBusy(null);
    };
    const respondSchedule = async (emp, action) => {
        setBusy(emp.id + "sc");
        try { await api.post(`/jobs/employment/${emp.id}/schedule/${action}`); toast.success(action === "accept" ? "New schedule accepted" : "Schedule change declined"); await Promise.all([load(), refresh()]); }
        catch (e) { toast.error(errMessage(e)); }
        setBusy(null);
    };
    const quit = async (emp) => {
        setBusy(emp.id + "q");
        try { await api.post(`/jobs/employment/${emp.id}/quit`); toast.success("You quit the job"); await Promise.all([load(), refresh()]); } catch (e) { toast.error(errMessage(e)); }
        setBusy(null);
    };
    const withdraw = async (app) => {
        setBusy(app.id + "w");
        try { await api.post(`/jobs/employment/applications/${app.id}/withdraw`); toast.success("Application withdrawn"); await load(); }
        catch (e) { toast.error(errMessage(e)); }
        setBusy(null);
    };
    const respond = async (app, action) => {
        setBusy(app.id);
        try { await api.post(`/jobs/employment/applications/${app.id}/${action}`); toast.success(action === "accept" ? "Job accepted!" : "Offer declined"); await Promise.all([load(), refresh()]); }
        catch (e) { toast.error(errMessage(e)); }
        setBusy(null);
    };

    if (!data) return <Spinner />;
    const offers = data.applications.filter((a) => a.status === "offered");
    const pending = data.applications.filter((a) => a.status === "pending");

    return (
        <div className="space-y-5">
            {offers.length > 0 && (
                <Panel className="p-4 border-neon-green/30" data-testid="job-offers">
                    <div className="font-display font-bold text-white mb-3">Job Offers</div>
                    <div className="space-y-2">
                        {offers.map((a) => (
                            <div key={a.id} className="flex items-center justify-between gap-3 p-2.5 border border-white/10 rounded-sm" data-testid={`offer-${a.id}`}>
                                <div><span className="font-display font-bold text-white text-sm">{a.business_name}</span>
                                    <div className="text-[11px] text-neon-green">{(a.role || "").replace(/_/g, " ")} · ${a.wage_offer}/h</div>
                                    <div className="text-[10px] text-neon-purple flex items-center gap-1 mt-0.5"><Clock className="w-3 h-3" /> {scheduleLabel(a.schedule)}</div>
                                </div>
                                <div className="flex gap-2">
                                    <KButton variant="green" loading={busy === a.id} onClick={() => respond(a, "accept")} data-testid={`offer-accept-${a.id}`}><CheckCircle2 className="w-3.5 h-3.5" /> Accept</KButton>
                                    <KButton variant="ghost" onClick={() => respond(a, "decline")} data-testid={`offer-decline-${a.id}`}>Decline</KButton>
                                </div>
                            </div>
                        ))}
                    </div>
                </Panel>
            )}

            <div>
                <div className="font-display font-bold text-white mb-1">Your Jobs</div>
                <p className="text-[11px] text-muted-foreground mb-3">Player-business jobs run on a fixed schedule — you auto-work during your hours (even offline) and can't start other physical activities while on shift. Clock out early to free up (you forfeit the rest of today's pay and lose reliability).</p>
                {data.employments.length === 0 ? (
                    <EmptyState icon={Briefcase} title="Not employed by any player yet" sub="Browse the Job Market and apply to a player-owned business." />
                ) : (
                    <div className="grid sm:grid-cols-2 gap-3">
                        {data.employments.map((e) => (
                            <Panel key={e.id} className="p-4" data-testid={`employment-${e.id}`}>
                                <div className="flex items-start justify-between mb-1">
                                    <span className="font-display font-bold text-white">{e.business_name}</span>
                                    <Pill tone="green">${e.wage_per_hour}/h</Pill>
                                </div>
                                <div className="flex items-center gap-2 mb-2 flex-wrap">
                                    <span className="text-[11px] text-muted-foreground capitalize">{(e.role || "").replace(/_/g, " ")}</span>
                                    {e.on_shift
                                        ? <Pill tone="green" data-testid={`emp-onshift-${e.id}`}>On shift now</Pill>
                                        : <Pill tone="yellow" data-testid={`emp-offshift-${e.id}`}>Off shift</Pill>}
                                    {e.raise_due && <Pill tone="yellow" data-testid={`raise-due-${e.id}`}>Raise due</Pill>}
                                </div>
                                <div className="text-[11px] text-neon-purple flex items-center gap-1 mb-2"><Clock className="w-3 h-3" /> {scheduleLabel(e.schedule)}</div>
                                {e.training_offer && (
                                    <div className="border border-neon-cyan/30 rounded-sm p-2 mb-2" data-testid={`training-offer-${e.id}`}>
                                        <div className="text-[11px] text-white mb-1.5 flex items-center gap-1"><GraduationCap className="w-3.5 h-3.5 text-neon-cyan" /> Training offered: {e.training_offer.label} <span className="text-neon-green">(+{e.training_offer.skill_gain} {e.training_offer.skill})</span></div>
                                        <div className="flex gap-2">
                                            <KButton variant="green" className="!py-1 !px-2 !text-[11px] flex-1" loading={busy === e.id + "t"} onClick={() => respondTraining(e, "accept")} data-testid={`training-accept-${e.id}`}>Accept</KButton>
                                            <KButton variant="ghost" className="!py-1 !px-2 !text-[11px]" onClick={() => respondTraining(e, "decline")} data-testid={`training-decline-${e.id}`}>Decline</KButton>
                                        </div>
                                    </div>
                                )}
                                {e.pending_schedule && (
                                    <div className="border border-neon-yellow/30 rounded-sm p-2 mb-2" data-testid={`sched-proposal-${e.id}`}>
                                        <div className="text-[11px] text-white mb-1.5 flex items-center gap-1"><Clock className="w-3.5 h-3.5 text-neon-yellow" /> New schedule proposed: {scheduleLabel(e.pending_schedule)}</div>
                                        <div className="flex gap-2">
                                            <KButton variant="green" className="!py-1 !px-2 !text-[11px] flex-1" loading={busy === e.id + "sc"} onClick={() => respondSchedule(e, "accept")} data-testid={`sched-accept-${e.id}`}>Accept</KButton>
                                            <KButton variant="ghost" className="!py-1 !px-2 !text-[11px]" onClick={() => respondSchedule(e, "decline")} data-testid={`sched-decline-${e.id}`}>Decline</KButton>
                                        </div>
                                    </div>
                                )}
                                <div className="grid grid-cols-4 gap-2 text-center text-[10px] mb-3">
                                    <div><div className="text-muted-foreground uppercase">Perf</div><div className="font-mono text-neon-cyan">{Math.round(e.performance)}</div></div>
                                    <div><div className="text-muted-foreground uppercase">Reliab</div><div className="font-mono text-neon-green">{Math.round(e.reliability)}</div></div>
                                    <div><div className="text-muted-foreground uppercase">Hours</div><div className="font-mono text-neon-purple">{Math.round(e.total_hours_worked || 0)}h</div></div>
                                    <div><div className="text-muted-foreground uppercase">Earned</div><div className="font-mono text-white">${Math.round(e.total_wages_earned)}</div></div>
                                </div>
                                {e.today && e.today.hours > 0 && (
                                    <div className="text-[10px] text-muted-foreground mb-3 border-l-2 border-neon-purple/40 pl-2" data-testid={`emp-today-${e.id}`}>
                                        Today: {e.today.hours}h worked · earned <span className="text-neon-green">${Math.round(e.today.wage)}</span>
                                    </div>
                                )}
                                {e.on_shift ? (
                                    <KButton variant="danger" className="w-full mb-2" loading={busy === e.id} onClick={() => clockOut(e)} data-testid={`clock-out-${e.id}`}><LogOut className="w-3.5 h-3.5" /> Clock Out Early</KButton>
                                ) : (
                                    <div className="text-[10px] text-muted-foreground mb-2 text-center">Off shift — auto-work resumes at your next scheduled start.</div>
                                )}
                                <KButton variant="ghost" className="w-full" loading={busy === e.id + "q"} onClick={() => quit(e)} data-testid={`quit-${e.id}`}><LogOut className="w-3.5 h-3.5" /> Quit Job</KButton>
                            </Panel>
                        ))}
                    </div>
                )}
            </div>

            {pending.length > 0 && (
                <Panel className="p-4" data-testid="pending-apps">
                    <div className="font-display font-bold text-white mb-2">Pending Applications</div>
                    {pending.map((a) => (
                        <div key={a.id} className="flex items-center justify-between gap-2 text-sm py-1.5 border-b border-white/5 last:border-0">
                            <span className="flex items-center gap-2 text-muted-foreground"><Clock className="w-3.5 h-3.5 text-neon-yellow" /> {a.business_name} — <span className="capitalize">{(a.role || "").replace(/_/g, " ")}</span>, awaiting response</span>
                            <KButton variant="ghost" className="!py-1 !px-2 text-[11px]" loading={busy === a.id + "w"} onClick={() => withdraw(a)} data-testid={`withdraw-app-${a.id}`}>Withdraw</KButton>
                        </div>
                    ))}
                </Panel>
            )}
        </div>
    );
}

export default function JobMarket() {
    const [tab, setTab] = useState("mine");
    return (
        <div className="space-y-6">
            <SectionTitle icon={Store} kicker="Work for other players" title="Player Job Market"
                sub="Apply to businesses run by real players and accept offers. Each job has fixed working hours — you auto-work on schedule (even offline), and your skills and condition decide how much the business gains." />
            <div className="flex gap-2">
                <button onClick={() => setTab("market")} data-testid="jm-tab-market"
                    className={cn("inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono uppercase tracking-wider rounded-sm border transition-colors",
                        tab === "market" ? "border-neon-cyan text-neon-cyan bg-neon-cyan/10" : "border-white/12 text-muted-foreground hover:text-white")}>
                    <Building2 className="w-3.5 h-3.5" /> Job Market
                </button>
                <button onClick={() => setTab("mine")} data-testid="jm-tab-mine"
                    className={cn("inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono uppercase tracking-wider rounded-sm border transition-colors",
                        tab === "mine" ? "border-neon-cyan text-neon-cyan bg-neon-cyan/10" : "border-white/12 text-muted-foreground hover:text-white")}>
                    <Briefcase className="w-3.5 h-3.5" /> My Jobs
                </button>
            </div>
            {tab === "market" ? <MarketTab /> : <MyJobsTab />}
        </div>
    );
}
