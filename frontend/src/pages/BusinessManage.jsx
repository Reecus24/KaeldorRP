import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api, errMessage } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, StatBar, Money, EmptyState, InfoTip } from "@/components/game/primitives";
import { KButton, KInput } from "@/components/game/controls";
import { money, money2, fmtDuration, realDurationLabel, scheduleLabel, SHIFT_PRESETS } from "@/lib/helpers";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
    Boxes, ArrowLeft, Users, UserPlus, GraduationCap, ScrollText, LineChart, LayoutGrid,
    TrendingUp, TrendingDown, AlertTriangle, Megaphone, ArrowUpCircle, Smile, Gauge,
    Heart, BadgeDollarSign, Sparkles, X, Clock, ShieldCheck, Hammer,
} from "lucide-react";

const pad2 = (n) => String(n).padStart(2, "0");

const SEV = { success: "text-neon-green", info: "text-neon-cyan/90", warning: "text-neon-yellow", danger: "text-neon-red" };

function Tab({ active, onClick, icon: Icon, children, testid }) {
    return (
        <button onClick={onClick} data-testid={testid}
            className={cn("inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono uppercase tracking-wider rounded-sm border transition-colors",
                active ? "border-neon-cyan text-neon-cyan bg-neon-cyan/10" : "border-white/12 text-muted-foreground hover:text-white hover:border-white/25")}>
            {Icon && <Icon className="w-3.5 h-3.5" />}{children}
        </button>
    );
}

function Tile({ label, value, accent = "#fff", sub, info, testid }) {
    return (
        <Panel className="p-3" data-testid={testid}>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground flex items-center gap-1">{label}{info && <InfoTip text={info} testid={testid ? `${testid}-info` : undefined} />}</div>
            <div className="font-display font-bold text-lg" style={{ color: accent }}>{value}</div>
            {sub && <div className="text-[10px] text-muted-foreground">{sub}</div>}
        </Panel>
    );
}

function TraitPills({ traits }) {
    if (!traits || !traits.length) return <span className="text-[10px] text-muted-foreground/50 font-mono">no traits</span>;
    return <div className="flex flex-wrap gap-1">{traits.map((t) => <Pill key={t} tone="purple" className="!text-[9px]">{t.replace(/_/g, " ")}</Pill>)}</div>;
}

function WageInput({ value, onChange, testid }) {
    return (
        <input type="number" value={value} onChange={(e) => onChange(e.target.value)} data-testid={testid}
            className="w-20 bg-white/5 border border-white/12 rounded-sm px-2 py-1 text-sm text-white font-mono focus:outline-none focus:border-neon-cyan/50" />
    );
}

// live productivity -> $/h for a player applicant (recomputed as role/wage change)
function calcProj(projection, role, wph) {
    if (!projection || !wph) return null;
    const prod = (projection.by_role && (projection.by_role[role] ?? projection.by_role._default)) || 1.0;
    const uph = projection.units_per_hour || 0;
    const margin = projection.margin_per_unit || 0;
    const rev = uph * prod * margin;
    return { rev_per_hour: rev, wage_per_hour: wph, net_per_hour: rev - wph, productivity: prod, units_per_hour: uph, margin_per_unit: margin };
}

function ProjLine({ proj, label = "Projected output", testid }) {
    if (!proj) return null;
    const rev = proj.rev_per_hour, wage = proj.wage_per_hour, net = proj.net_per_hour;
    const uph = proj.units_per_hour, margin = proj.margin_per_unit, prod = proj.productivity;
    return (
        <div className="text-[11px] mt-1" data-testid={testid}>
            <span className="text-muted-foreground">{label}:</span>{" "}
            <span className="text-neon-green">≈ +${Math.round(rev)}/h</span>
            <span className="text-muted-foreground"> − </span>
            <span className="text-neon-red">${Math.round(wage)}/h</span>
            <span className="text-muted-foreground"> = net </span>
            <span className={net >= 0 ? "text-neon-green font-bold" : "text-neon-red font-bold"}>{net >= 0 ? "+$" : "-$"}{Math.abs(Math.round(net))}/h</span>
            {uph != null && margin != null && (
                <span className="text-muted-foreground/60"> · makes ≈{(uph * (prod || 1)).toFixed(1)} units/h × ${margin} margin</span>
            )}
        </div>
    );
}

function PlayerHiring({ bizId, hiringOpen, onReloadDetail, roles = [] }) {
    const [apps, setApps] = useState(null);
    const [emps, setEmps] = useState([]);
    const [wages, setWages] = useState({});
    const [roleSel, setRoleSel] = useState({});
    const [schedSel, setSchedSel] = useState({});
    const [trainSel, setTrainSel] = useState({});
    const [schedChangeSel, setSchedChangeSel] = useState({});
    const [trainOpts, setTrainOpts] = useState([]);
    const [busy, setBusy] = useState(null);
    const load = useCallback(async () => {
        const [a, e] = await Promise.all([
            api.get(`/businesses/${bizId}/player-applications`),
            api.get(`/businesses/${bizId}/player-employees`),
        ]);
        setApps(a.data); setEmps(e.data);
    }, [bizId]);
    useEffect(() => { load(); }, [load]);
    useEffect(() => { api.get("/training-options").then(({ data }) => setTrainOpts(data)).catch(() => {}); }, []);

    const roleLabel = (r) => (r || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    const setW = (k, v) => setWages((w) => ({ ...w, [k]: v }));
    const toggle = async () => {
        setBusy("toggle");
        try { const { data } = await api.post(`/businesses/${bizId}/toggle-hiring`); toast.success(data.hiring_open ? "Hiring is now OPEN" : "Hiring closed"); await onReloadDetail(); }
        catch (e) { toast.error(errMessage(e)); }
        setBusy(null);
    };
    const offer = async (a) => {
        const w = parseFloat(wages[a.id] ?? a.recommended_wage);
        const role = roleSel[a.id] ?? a.role;
        const schedule = schedSel[a.id] ?? a.schedule?.preset ?? "early";
        setBusy(a.id);
        try { await api.post(`/businesses/${bizId}/player-applications/${a.id}/offer`, { wage_per_hour: w, role, schedule }); toast.success(`Offer sent to ${a.applicant_name}`); await load(); }
        catch (e) { toast.error(errMessage(e)); }
        setBusy(null);
    };
    const reject = async (a) => { setBusy(a.id + "r"); try { await api.post(`/businesses/${bizId}/player-applications/${a.id}/reject`); await load(); } catch (e) { toast.error(errMessage(e)); } setBusy(null); };
    const raise = async (emp) => {
        const w = parseFloat(wages["e" + emp.id] ?? Math.round((emp.wage_per_hour + 2) * 100) / 100);
        setBusy(emp.id);
        try { await api.post(`/businesses/${bizId}/player-employees/${emp.id}/raise`, { wage_per_hour: w }); toast.success("Raise given"); await load(); }
        catch (e) { toast.error(errMessage(e)); }
        setBusy(null);
    };
    const fire = async (emp) => { setBusy(emp.id + "f"); try { await api.post(`/businesses/${bizId}/player-employees/${emp.id}/fire`); toast.success(`${emp.employee_name} let go`); await load(); } catch (e) { toast.error(errMessage(e)); } setBusy(null); };
    const offerTraining = async (emp) => {
        const opt = trainSel[emp.id] ?? (trainOpts[0] && trainOpts[0].id);
        if (!opt) return;
        setBusy(emp.id + "t");
        try { await api.post(`/businesses/${bizId}/player-employees/${emp.id}/offer-training`, { option_id: opt }); toast.success("Training offered"); await Promise.all([load(), onReloadDetail()]); }
        catch (e) { toast.error(errMessage(e)); }
        setBusy(null);
    };
    const proposeSchedule = async (emp) => {
        const preset = schedChangeSel[emp.id] ?? "early";
        setBusy(emp.id + "s");
        try { await api.post(`/businesses/${bizId}/player-employees/${emp.id}/propose-schedule`, { schedule: preset }); toast.success("Schedule change proposed"); await load(); }
        catch (e) { toast.error(errMessage(e)); }
        setBusy(null);
    };

    if (!apps) return <Spinner />;
    const pending = apps.filter((a) => a.status === "pending");
    const offered = apps.filter((a) => a.status === "offered");
    const roleOptions = (a) => Array.from(new Set([...roles, a.role].filter(Boolean)));

    const AppCard = (a) => (
        <Panel key={a.id} className="p-3" data-testid={`player-app-${a.id}`}>
            <div className="flex items-center gap-2 flex-wrap">
                <span className="font-display font-bold text-white text-sm">{a.applicant_name}</span>
                <Pill tone="cyan">Lv {a.stats?.level}</Pill>
                <Pill tone="green">Rep {a.stats?.reputation}</Pill>
                {a.stats?.role_fit && <Pill tone={a.stats.role_fit >= 1.05 ? "green" : a.stats.role_fit >= 0.85 ? "cyan" : "yellow"}>{a.stats.fit_label || "fit"}</Pill>}
                {a.stats?.criminal_warning && <Pill tone="red">⚠ Record</Pill>}
                {a.status === "offered" && <Pill tone="yellow">Offered ${a.wage_offer}/h</Pill>}
            </div>
            <div className="text-[11px] text-muted-foreground mt-1">Applied for: <span className="capitalize text-white">{roleLabel(a.role)}</span> · {a.stats?.education_count} course(s) · {(a.stats?.top_skills || []).map((s) => `${s.skill} ${s.level}`).join(", ")}</div>
            {a.stats?.role_matches_staffing === false && <div className="text-[11px] text-neon-yellow mt-1">⚠ This role isn't part of your staffing plan — counts less toward coverage.</div>}
            {a.message && <div className="text-[11px] text-foreground/80 mt-1 italic">"{a.message}"</div>}
            <div className="text-[11px] text-neon-green mt-1">Recommended: ${a.recommended_wage}/h</div>
            <ProjLine proj={calcProj(a.projection, roleSel[a.id] ?? a.role, parseFloat(wages[a.id] ?? a.recommended_wage))} testid={`app-proj-${a.id}`} />
            <div className="flex items-center gap-2 mt-2 flex-wrap">
                <select value={roleSel[a.id] ?? a.role} onChange={(e) => setRoleSel((s) => ({ ...s, [a.id]: e.target.value }))} data-testid={`offer-role-${a.id}`}
                    className="bg-white/5 border border-white/12 rounded-sm px-2 py-1 text-xs text-white capitalize focus:outline-none focus:border-neon-cyan/50">
                    {roleOptions(a).map((r) => <option key={r} value={r} className="bg-[#0d0d12]">{roleLabel(r)}</option>)}
                </select>
                <select value={schedSel[a.id] ?? a.schedule?.preset ?? "early"} onChange={(e) => setSchedSel((s) => ({ ...s, [a.id]: e.target.value }))} data-testid={`offer-schedule-${a.id}`}
                    className="bg-white/5 border border-white/12 rounded-sm px-2 py-1 text-xs text-white focus:outline-none focus:border-neon-cyan/50">
                    {Object.entries(SHIFT_PRESETS).map(([k, v]) => <option key={k} value={k} className="bg-[#0d0d12]">{v.label} {pad2(v.start)}:00–{pad2(v.end)}:00</option>)}
                </select>
                <span className="text-[11px] text-muted-foreground">$/h</span>
                <WageInput value={wages[a.id] ?? a.recommended_wage} onChange={(v) => setW(a.id, v)} testid={`offer-wage-${a.id}`} />
                <KButton variant="green" loading={busy === a.id} onClick={() => offer(a)} data-testid={`offer-send-${a.id}`}>{a.status === "offered" ? "Update Offer" : "Send Offer"}</KButton>
                <KButton variant="ghost" loading={busy === a.id + "r"} onClick={() => reject(a)} data-testid={`offer-reject-${a.id}`}>Reject</KButton>
            </div>
        </Panel>
    );

    return (
        <div className="space-y-4">
            <Panel className="p-4 flex items-center justify-between" data-testid="hiring-status">
                <div>
                    <div className="font-display font-bold text-white">Player Hiring</div>
                    <div className="text-[11px] text-muted-foreground">{hiringOpen ? "Listed on the public Player Job Market." : "Not currently accepting player applications."}</div>
                </div>
                <KButton variant={hiringOpen ? "ghost" : "green"} loading={busy === "toggle"} onClick={toggle} data-testid="hiring-toggle">
                    {hiringOpen ? "Close Hiring" : "Open Hiring"}
                </KButton>
            </Panel>

            <div>
                <div className="font-display font-bold text-white mb-2">Applications ({pending.length})</div>
                {pending.length === 0 ? (
                    <EmptyState icon={UserPlus} title="No new applications" sub={hiringOpen ? "Players can find you on the Job Market." : "Open hiring to receive applications."} />
                ) : (
                    <div className="space-y-2">{pending.map(AppCard)}</div>
                )}
            </div>

            {offered.length > 0 && (
                <div>
                    <div className="font-display font-bold text-white mb-2">Pending Offers ({offered.length})</div>
                    <div className="space-y-2">{offered.map(AppCard)}</div>
                </div>
            )}

            <div>
                <div className="font-display font-bold text-white mb-2">Player Employees ({emps.length})</div>
                {emps.length === 0 ? (
                    <div className="text-sm text-muted-foreground">No player employees yet.</div>
                ) : (
                    <div className="space-y-2">
                        {emps.map((e) => (
                            <Panel key={e.id} className="p-3" data-testid={`player-emp-${e.id}`}>
                                <div className="flex items-center justify-between flex-wrap gap-2">
                                    <div className="min-w-0">
                                        <span className="font-display font-bold text-white text-sm">{e.employee_name}</span>
                                        <span className="text-[11px] text-muted-foreground ml-2 capitalize">{roleLabel(e.role)} · ${e.wage_per_hour}/h</span>
                                        {e.on_shift
                                            ? <Pill tone="green" className="ml-2" data-testid={`emp-onshift-${e.id}`}>Working now</Pill>
                                            : <Pill tone="yellow" className="ml-2" data-testid={`emp-offshift-${e.id}`}>Off shift</Pill>}
                                        {e.raise_due && <Pill tone="yellow" className="ml-2" data-testid={`emp-raise-due-${e.id}`}>Raise due</Pill>}
                                        <div className="text-[11px] text-neon-purple flex items-center gap-1 mt-0.5"><Clock className="w-3 h-3" /> {scheduleLabel(e.schedule)}</div>
                                        <div className="text-[11px] text-muted-foreground">Perf {Math.round(e.performance)} · Reliab {Math.round(e.reliability)} · {Math.round(e.total_hours_worked || 0)}h worked · earned ${Math.round(e.total_wages_earned)} · value added ${Math.round(e.total_value_added || 0)}</div>
                                        {e.today && e.today.hours > 0 && (
                                            <div className="text-[11px] mt-0.5" data-testid={`emp-net-${e.id}`}>
                                                Today ({e.today.hours}h): <span className="text-neon-green">+${Math.round(e.today.revenue)} revenue</span> − <span className="text-neon-red">${Math.round(e.today.wage)} wages</span> = net <span className={e.today.net >= 0 ? "text-neon-green" : "text-neon-red"}>{e.today.net >= 0 ? "+$" : "-$"}{Math.abs(Math.round(e.today.net))}</span>
                                            </div>
                                        )}
                                        <ProjLine proj={e.projection} label="Est. if working now" testid={`emp-proj-${e.id}`} />
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-[11px] text-muted-foreground">$/h</span>
                                        <WageInput value={wages["e" + e.id] ?? Math.round((e.wage_per_hour + 2) * 100) / 100} onChange={(v) => setW("e" + e.id, v)} testid={`raise-wage-${e.id}`} />
                                        <KButton variant="primary" loading={busy === e.id} onClick={() => raise(e)} data-testid={`raise-send-${e.id}`}>Raise</KButton>
                                        <KButton variant="danger" loading={busy === e.id + "f"} onClick={() => fire(e)} data-testid={`fire-emp-${e.id}`}>Fire</KButton>
                                    </div>
                                </div>
                                <div className="mt-2 pt-2 border-t border-white/5 grid sm:grid-cols-2 gap-2">
                                    <div className="flex items-center gap-1.5 flex-wrap">
                                        {e.training_offer ? (
                                            <span className="text-[11px] text-neon-yellow" data-testid={`emp-training-pending-${e.id}`}><GraduationCap className="w-3 h-3 inline mr-1" />Training offered: {e.training_offer.label} — awaiting response</span>
                                        ) : (
                                            <>
                                                <select value={trainSel[e.id] ?? (trainOpts[0] && trainOpts[0].id) ?? ""} onChange={(ev) => setTrainSel((s) => ({ ...s, [e.id]: ev.target.value }))} data-testid={`train-select-${e.id}`}
                                                    className="bg-white/5 border border-white/12 rounded-sm px-2 py-1 text-[11px] text-white focus:outline-none focus:border-neon-cyan/50">
                                                    {trainOpts.map((o) => <option key={o.id} value={o.id} className="bg-[#0d0d12]">{o.label} (${o.cost}, +{o.skill_gain})</option>)}
                                                </select>
                                                <KButton variant="ghost" className="!py-1 !px-2 !text-[11px]" loading={busy === e.id + "t"} onClick={() => offerTraining(e)} data-testid={`offer-training-${e.id}`}><GraduationCap className="w-3 h-3" /> Offer Training</KButton>
                                            </>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-1.5 flex-wrap sm:justify-end">
                                        {e.pending_schedule ? (
                                            <span className="text-[11px] text-neon-yellow" data-testid={`emp-sched-pending-${e.id}`}><Clock className="w-3 h-3 inline mr-1" />Proposed: {e.pending_schedule.label} — awaiting response</span>
                                        ) : (
                                            <>
                                                <select value={schedChangeSel[e.id] ?? e.schedule?.preset ?? "early"} onChange={(ev) => setSchedChangeSel((s) => ({ ...s, [e.id]: ev.target.value }))} data-testid={`sched-change-select-${e.id}`}
                                                    className="bg-white/5 border border-white/12 rounded-sm px-2 py-1 text-[11px] text-white focus:outline-none focus:border-neon-cyan/50">
                                                    {Object.entries(SHIFT_PRESETS).map(([k, v]) => <option key={k} value={k} className="bg-[#0d0d12]">{v.label} {pad2(v.start)}:00–{pad2(v.end)}:00</option>)}
                                                </select>
                                                <KButton variant="ghost" className="!py-1 !px-2 !text-[11px]" loading={busy === e.id + "s"} onClick={() => proposeSchedule(e)} data-testid={`propose-schedule-${e.id}`}><Clock className="w-3 h-3" /> Propose Schedule</KButton>
                                            </>
                                        )}
                                    </div>
                                </div>
                            </Panel>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

function BizActivityBanner({ activity }) {
    const start = new Date(activity.started_at).getTime();
    const end = new Date(activity.ends_at).getTime();
    const pct = Math.max(0, Math.min(100, ((Date.now() - start) / Math.max(1, end - start)) * 100));
    const dayNow = Math.min(activity.duration_days, Math.max(1, Math.ceil(activity.duration_days * pct / 100)));
    const upgrade = activity.type === "upgrade";
    const Icon = upgrade ? Hammer : Megaphone;
    return (
        <Panel className={cn("p-4 border", upgrade ? "border-neon-yellow/40 bg-neon-yellow/5" : "border-neon-cyan/40 bg-neon-cyan/5")} data-testid="business-activity-banner">
            <div className="flex items-center justify-between mb-2">
                <span className="font-display font-bold text-white flex items-center gap-2">
                    <Icon className={cn("w-4 h-4", upgrade ? "text-neon-yellow" : "text-neon-cyan")} />
                    {upgrade ? "Upgrading Business" : "Marketing Campaign"}
                </span>
                <span className="font-mono text-xs text-neon-cyan" data-testid="activity-remaining">
                    {upgrade ? `Upgrading... Day ${dayNow}/${activity.duration_days} (-50% income)` : `Marketing Campaign... Day ${dayNow}/${activity.duration_days}`}
                </span>
            </div>
            <div className="h-2 bg-white/8 rounded-full overflow-hidden">
                <div className={cn("h-full transition-all", upgrade ? "bg-neon-yellow" : "bg-neon-cyan")} style={{ width: `${pct}%` }} />
            </div>
            <p className="text-[11px] text-muted-foreground mt-2">
                {upgrade
                    ? "Construction disrupts trade — income is reduced 50% until it's done. On completion: +1 level and a new staff slot."
                    : "Your campaign is rolling out. The +25% demand and +10% price boost apply the moment it completes."}
            </p>
        </Panel>
    );
}

export default function BusinessManage() {
    const { id } = useParams();
    const navigate = useNavigate();
    const { act, tick } = useGame();
    const [detail, setDetail] = useState(null);
    const [employees, setEmployees] = useState([]);
    const [applicants, setApplicants] = useState([]);
    const [playerEmps, setPlayerEmps] = useState([]);
    const [trainOpts, setTrainOpts] = useState([]);
    const [events, setEvents] = useState([]);
    const [tab, setTab] = useState("overview");
    const [busy, setBusy] = useState(null);
    const [inject, setInject] = useState("");
    const [trainEmp, setTrainEmp] = useState(null);
    const [confirmSell, setConfirmSell] = useState(false);
    const [renaming, setRenaming] = useState(false);
    const [nameInput, setNameInput] = useState("");
    const [targetInput, setTargetInput] = useState("");

    const loadAll = useCallback(async () => {
        try {
            const [d, e, a, ev, pe] = await Promise.all([
                api.get(`/businesses/${id}`),
                api.get(`/businesses/${id}/employees`),
                api.get(`/businesses/${id}/applicants`),
                api.get(`/businesses/${id}/events`),
                api.get(`/businesses/${id}/player-employees`).catch(() => ({ data: [] })),
            ]);
            setDetail(d.data);
            setEmployees(e.data.employees);
            setApplicants(a.data);
            setEvents(ev.data);
            setPlayerEmps(pe.data);
        } catch (err) {
            if (err?.response?.status === 404 || err?.response?.status === 403) navigate("/businesses");
        }
    }, [id, navigate]);

    useEffect(() => {
        loadAll();
        api.get("/training-options").then(({ data }) => setTrainOpts(data)).catch(() => {});
    }, [loadAll]);

    useEffect(() => {
        const t = setInterval(loadAll, 8000);
        return () => clearInterval(t);
    }, [loadAll]);

    const run = async (fn, msg, key) => {
        setBusy(key);
        await act(fn, msg);
        await loadAll();
        setBusy(null);
    };
    const sellBiz = async () => {
        setBusy("sell");
        const r = await act(() => api.post(`/businesses/${id}/sell`), null);
        if (r?.ok) toast.success(`Sold for $${(r.res.data.value ?? 0).toLocaleString()}`);
        setConfirmSell(false);
        await loadAll();
        setBusy(null);
    };
    const doRename = async () => {
        const name = nameInput.trim();
        if (name.length < 2) return;
        setBusy("rename");
        const r = await act(() => api.post(`/businesses/${id}/rename`, { name }), "Business renamed");
        if (r?.ok) { setRenaming(false); await loadAll(); }
        setBusy(null);
    };
    const buyMaterials = async () => {
        setBusy("materials");
        const body = targetInput ? { units: Number(targetInput) } : {};
        const r = await act(() => api.post(`/businesses/${id}/buy-materials`, body), null);
        if (r?.ok) toast.success(r.res.data.cost > 0 ? `Restocked for $${Math.round(r.res.data.cost)}` : "Already fully stocked");
        await loadAll();
        setBusy(null);
    };
    const toggleAutoRestock = async (val) => {
        await act(() => api.post(`/businesses/${id}/restock-settings`, { auto_restock: val }), val ? "Auto-restock ON" : "Auto-restock OFF");
        await loadAll();
    };

    const doTrain = async (emp, opt) => {
        setBusy("train");
        const r = await act(() => api.post(`/businesses/employees/${emp.id}/train`, { option_id: opt.id }), `${emp.name} started ${opt.label}`);
        await loadAll();
        setBusy(null);
        if (r.ok) setTrainEmp(null);
    };

    if (!detail) return <Spinner />;
    const b = detail.business;
    const m = detail.metrics;
    const costs = detail.costs || {};
    // headline net derived from the same whole-dollar components shown in the P&L box, so it always adds up on screen
    const net = Math.round(m.rev_day || 0) - Math.round(m.material_day || 0) - Math.round(m.wage_per_day || 0);
    const RETAIL_IDS = ["kiosk", "clothing_store", "pet_shop", "online_shop"];
    const capacityLabel = RETAIL_IDS.includes(b.type_id) ? "Sales Capacity / day" : "Production / day";

    return (
        <div className="space-y-6">
            <Link to="/businesses" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-neon-cyan font-mono" data-testid="back-to-businesses">
                <ArrowLeft className="w-3.5 h-3.5" /> All businesses
            </Link>
            <SectionTitle icon={Boxes} kicker={`${b.category} · Level ${b.level}/${b.max_level}${b.bankrupt ? " · BANKRUPT" : ""}`} title={b.name}
                right={<Pill tone={net >= 0 ? "green" : "red"} className="text-sm py-1">{net >= 0 ? "+" : ""}{money(net)}/day</Pill>} />

            {b.activity && <BizActivityBanner activity={b.activity} />}

            <div className="flex flex-wrap gap-2">
                <Tab active={tab === "overview"} onClick={() => setTab("overview")} icon={LayoutGrid} testid="tab-overview">Overview</Tab>
                <Tab active={tab === "finances"} onClick={() => setTab("finances")} icon={LineChart} testid="tab-finances">Finances</Tab>
                <Tab active={tab === "employees"} onClick={() => setTab("employees")} icon={Users} testid="tab-employees">Employees ({m.employee_count})</Tab>
                <Tab active={tab === "applicants"} onClick={() => setTab("applicants")} icon={UserPlus} testid="tab-applicants">Applicants ({m.applicant_count})</Tab>
                <Tab active={tab === "hiring"} onClick={() => setTab("hiring")} icon={Users} testid="tab-hiring">Player Hiring</Tab>
                <Tab active={tab === "training"} onClick={() => setTab("training")} icon={GraduationCap} testid="tab-training">Training</Tab>
                <Tab active={tab === "events"} onClick={() => setTab("events")} icon={ScrollText} testid="tab-events">Events</Tab>
            </div>

            {/* OVERVIEW */}
            {tab === "overview" && (
                <div className="space-y-4">
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                        <Tile label="Net / day" value={money(net)} accent={net >= 0 ? "#00FF66" : "#FF0055"} sub="rev − materials − wages" />
                        <Tile label="Revenue / day" value={money(m.rev_day)} accent="#00F3FF" sub={`${Math.round(m.sold_day)} sold × ${money2(m.effective_price ?? m.product?.price ?? 0)}`} />
                        <Tile label="Materials / day" value={money(m.material_day)} accent="#FFC300" sub={`${money2(m.material_cost_per_unit)}/unit`} />
                        <Tile label="Wages / day" value={money(m.wage_per_day)} accent="#FF8A00" />
                        <Tile label={capacityLabel} value={`${Math.round(m.capacity_day ?? 0)}/day`} accent="#B026FF" info="How many units your staff can make/sell per day at current staffing and satisfaction. Hire more staff or upgrade to raise it." sub={`vs ${Math.round(m.demand_day)}/day demand`} />
                        <Tile label="Products in stock" value={Math.round(m.products_in_stock)} accent="#B026FF" />
                        <Tile label="Uncollected cash" value={money(b.cash)} accent="#00FF66" />
                        <Tile label="Staff slots" value={`${m.staff_count ?? 0}/${m.max_staff_slots ?? 0}`} accent="#00F3FF" sub="upgrade for +1 slot" />
                        <Tile label="Business debt" value={money(b.debt)} accent={b.debt > 0 ? "#FF0055" : "#9CA3AF"} />
                        <Tile label="Reputation" value={`${Math.round(b.reputation)}%`} accent="#00FF66" testid="reputation" info="Reputation acts as a multiplier for market demand. Higher reputation attracts more customers." sub={`Demand ×${(m.reputation_demand_mult ?? 1).toFixed(2)}`} />
                        <Tile label="Satisfaction" value={`${m.satisfaction}%`} accent="#00F3FF" testid="satisfaction" info="Staff satisfaction determines work efficiency. Unhappy workers produce or sell at a slower pace." sub={`Output ×${(m.satisfaction_production_mult ?? 1).toFixed(2)}`} />
                    </div>

                    {/* SUPPLY CHAIN — transparent P&L */}
                    <Panel className="p-5" data-testid="supply-chain-panel">
                        <div className="flex items-center gap-1.5 mb-3">
                            <span className="font-display font-bold text-white">Supply Chain — how this business makes money</span>
                            <InfoTip text="Your business buys ingredients, your workers turn them into the product, and the product is sold to meet daily demand. Profit = sales − materials − wages. No rent, no hidden fees." testid="supply-info" />
                        </div>
                        <div className="grid lg:grid-cols-2 gap-4">
                            <div>
                                <div className="text-[11px] uppercase tracking-wider text-neon-cyan/70 mb-2">Recipe</div>
                                <div className="text-sm text-white mb-1">Sells: <span className="font-bold">{m.product?.name}</span> @ <span className="text-neon-green">{money2(m.effective_price ?? m.product?.price ?? 0)}</span>/unit{m.marketing_level > 0 ? <span className="text-neon-cyan"> (incl. +{m.marketing_price_pct}% marketing)</span> : null}</div>
                                <div className="space-y-1 font-mono text-[12px]">
                                    {(m.recipe || []).map((r) => (
                                        <div key={r.id} className="flex justify-between text-muted-foreground" data-testid={`recipe-${r.id}`}>
                                            <span>{r.qty}× {r.name}</span><span className="text-neon-yellow">{money2(r.cost)}</span>
                                        </div>
                                    ))}
                                    <div className="flex justify-between border-t border-white/10 pt-1 mt-1 text-white">
                                        <span>Materials / unit</span><span className="text-neon-yellow">{money2(m.material_cost_per_unit)}</span>
                                    </div>
                                    <div className="flex justify-between text-white">
                                        <span>Margin / unit</span><span className="text-neon-green font-bold">{money2(m.margin_per_unit)}</span>
                                    </div>
                                </div>
                            </div>
                            <div>
                                <div className="text-[11px] uppercase tracking-wider text-neon-cyan/70 mb-2">Daily profit &amp; loss</div>
                                <div className="space-y-1 font-mono text-[12px] border border-white/10 rounded-sm p-3" data-testid="pnl-breakdown">
                                    <div className="flex justify-between"><span className="text-muted-foreground">Sold {Math.round(m.sold_day)} × {money2(m.effective_price ?? m.product?.price ?? 0)}</span><span className="text-neon-green">+{money(m.rev_day)}</span></div>
                                    <div className="flex justify-between"><span className="text-muted-foreground">− Materials ({Math.round(m.sold_day)} units)</span><span className="text-neon-yellow">−{money(m.material_day)}</span></div>
                                    <div className="flex justify-between"><span className="text-muted-foreground">− Wages (all workers)</span><span className="text-neon-red">−{money(m.wage_per_day)}</span></div>
                                    <div className="flex justify-between border-t border-white/10 pt-1 mt-1"><span className="text-white font-bold">Net / day</span><span className={net >= 0 ? "text-neon-green font-bold" : "text-neon-red font-bold"} data-testid="pnl-net">{net >= 0 ? "+" : ""}{money(net)}</span></div>
                                </div>
                                <div className="text-[11px] text-muted-foreground mt-2" data-testid="pnl-footer">
                                    {(m.capacity_day ?? 0) < (m.demand_day ?? 0)
                                        ? `Currently producing ${Math.round(m.capacity_day)} units/day. Market demand is ${Math.round(m.demand_day)}. Hire more staff or upgrade to increase output.`
                                        : `Demand caps sales at ${Math.round(m.demand_day)} units/day. Invest in Marketing to attract more customers.`}
                                </div>
                            </div>
                        </div>

                        {/* Materials stock + restock */}
                        <div className="mt-4 pt-4 border-t border-white/10">
                            <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
                                <span className="text-[11px] uppercase tracking-wider text-neon-cyan/70">Inventory &amp; restock</span>
                                <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer" title="Automatically buy ingredients from the business's cash to keep production running.">
                                    <input type="checkbox" checked={!!m.auto_restock} onChange={(e) => toggleAutoRestock(e.target.checked)} className="accent-neon-cyan" data-testid="auto-restock-toggle" /> Auto-restock
                                </label>
                            </div>
                            <div className="flex flex-wrap gap-2 mb-3">
                                {(m.materials || []).map((mat) => (
                                    <Pill key={mat.id} tone={mat.stock > 0 ? "cyan" : "red"} data-testid={`stock-${mat.id}`}>{mat.name}: {Math.round(mat.stock)}</Pill>
                                ))}
                                <Pill tone="purple" data-testid="stock-products">Finished: {Math.round(m.products_in_stock)}</Pill>
                            </div>
                            <div className="flex items-end gap-2 flex-wrap">
                                <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Stock target (units)
                                    <input type="number" min="0" value={targetInput} placeholder={String(Math.round(m.restock_target || 0))} onChange={(e) => setTargetInput(e.target.value)} data-testid="restock-target-input"
                                        className="w-28 bg-white/5 border border-white/12 rounded-sm px-2 py-1 text-xs text-white font-mono" /></label>
                                <KButton variant="primary" loading={busy === "materials"} onClick={buyMaterials} data-testid="buy-materials-button"><Boxes className="w-3.5 h-3.5" /> Buy Materials to Target</KButton>
                            </div>
                        </div>
                    </Panel>

                    {/* STAFFING */}
                    <Panel className="p-5">
                        <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
                            <div className="font-display font-bold text-white flex items-center gap-1.5">
                                Staffing
                                <InfoTip text="Workers (NPC and player employees alike) produce the goods during their scheduled shifts. Only workers on shift right now count toward 'active'. Same wage & productivity math for everyone." testid="staffing-info" />
                            </div>
                            <div className="text-[11px] font-mono text-muted-foreground" data-testid="active-staff-count">Active Staff: {m.staff_count ?? 0}/{m.max_staff_slots ?? 0} slots · {Math.round((m.active_coverage ?? 0) * 100)}% covered</div>
                        </div>
                        <div className="space-y-2 mt-2">
                            {m.staffing.length === 0 && <div className="text-sm text-muted-foreground">No specific staffing needed.</div>}
                            {m.staffing.map((s) => {
                                const activeOk = (s.active_working ?? 0) >= s.recommended;
                                return (
                                    <div key={s.role} className="flex items-center justify-between gap-3 border-b border-white/5 pb-2 last:border-0" data-testid={`staffing-${s.role}`}>
                                        <div className="min-w-0">
                                            <span className="capitalize text-white text-sm">{s.role.replace(/_/g, " ")}</span>
                                            <div className="text-[11px] font-mono">
                                                <span className="text-muted-foreground">Assigned {s.assigned}/{s.recommended} · </span>
                                                <span className={activeOk ? "text-neon-green" : "text-neon-yellow"} data-testid={`staffing-active-${s.role}`}>Active {s.active_working}/{s.recommended}</span>
                                            </div>
                                            <div className="text-[10px] text-muted-foreground">{s.status}{s.npc_have ? ` · ${s.npc_have} NPC` : ""}{s.player_have ? ` · ${s.player_have} player` : ""}</div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </Panel>

                    <Panel className="p-4" data-testid="biz-actions">
                        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                            <div className="border border-white/10 rounded-sm p-3 flex flex-col">
                                <div className="font-display font-bold text-white text-sm mb-0.5">Collect Profit</div>
                                <p className="text-[11px] text-muted-foreground mb-3 flex-1">Move the business's uncollected cash into your wallet. Instant.</p>
                                <KButton variant="green" disabled={b.cash <= 0} loading={busy === "collect"} onClick={() => run(() => api.post(`/businesses/${id}/collect`), "Profit collected", "collect")} data-testid="ov-collect">Collect {money(b.cash)}</KButton>
                            </div>
                            <div className="border border-white/10 rounded-sm p-3 flex flex-col">
                                <div className="font-display font-bold text-white text-sm mb-0.5 flex items-center gap-1.5">Marketing · Lvl {costs.marketing_level}
                                    <InfoTip text="Marketing builds your brand: +25% customer demand AND a +10% price premium per level. The price premium raises revenue immediately — even when you're already selling out." testid="marketing-info" /></div>
                                <p className="text-[11px] text-muted-foreground mb-3 flex-1">Each level: +{costs.marketing_demand_boost_pct}% demand, +{costs.marketing_price_boost_pct}% price, +{costs.marketing_reputation_gain} reputation. Takes ~{costs.marketing_duration_days} in-game days to roll out.</p>
                                <KButton variant="primary" disabled={costs.activity_in_progress} loading={busy === "marketing"} onClick={() => run(() => api.post(`/businesses/${id}/marketing`), "Marketing campaign launched", "marketing")} data-testid="ov-marketing"><Megaphone className="w-3.5 h-3.5" /> {costs.activity?.type === "marketing" ? "Campaign running…" : costs.activity_in_progress ? "Busy…" : `Run Marketing · ${money(costs.marketing_cost)} · ${costs.marketing_duration_days}d`}</KButton>
                            </div>
                            <div className="border border-white/10 rounded-sm p-3 flex flex-col">
                                <div className="font-display font-bold text-white text-sm mb-0.5 flex items-center gap-1.5">Upgrade — +1 Staff Slot
                                    <InfoTip text="Each upgrade adds one staff slot so you can hire another worker, and raises production capacity & demand by ~25% plus +4 reputation. Construction takes ~7 in-game days and cuts income 50% until done." testid="upgrade-info" /></div>
                                <p className="text-[11px] text-muted-foreground mb-3 flex-1">{costs.can_upgrade ? `Level ${costs.upgrade_from_level} → ${costs.upgrade_to_level}: +1 staff slot, +25% capacity & demand. Takes ~${costs.upgrade_duration_days} in-game days (income −50% during build).` : "This business is already at its maximum level."}</p>
                                <KButton variant="primary" disabled={!costs.can_upgrade || costs.activity_in_progress} loading={busy === "upgrade"} onClick={() => run(() => api.post(`/businesses/${id}/upgrade`), "Upgrade started", "upgrade")} data-testid="ov-upgrade"><ArrowUpCircle className="w-3.5 h-3.5" /> {costs.activity?.type === "upgrade" ? "Upgrading…" : !costs.can_upgrade ? "Max level" : costs.activity_in_progress ? "Busy…" : `Upgrade · ${money(costs.upgrade_cost)} · ${costs.upgrade_duration_days}d`}</KButton>
                            </div>
                        </div>
                        <div className="mt-3 pt-3 border-t border-white/10 flex flex-wrap items-center gap-2">
                            <span className="text-[10px] uppercase tracking-wider text-muted-foreground mr-1">More</span>
                            <KButton variant="ghost" className="!py-1 !px-2.5 !text-[11px]" onClick={() => { setNameInput(b.name); setRenaming(true); }} data-testid="ov-rename">Rename</KButton>
                            <KButton variant="ghost" className="!py-1 !px-2.5 !text-[11px] text-neon-red/80 hover:text-neon-red" onClick={() => setConfirmSell(true)} data-testid="ov-sell">Sell · ~{money(costs.sell_value)}</KButton>
                        </div>
                    </Panel>
                    {b.debt > 0 && (
                        <Panel className="p-4 flex gap-2 items-end">
                            <KInput label="Inject cash / pay business debt" type="number" value={inject} onChange={(e) => setInject(e.target.value)} className="flex-1" testid="inject-input" />
                            <KButton variant="green" loading={busy === "inject"} onClick={() => run(() => api.post(`/businesses/${id}/inject`, { amount: Number(inject) }), "Cash injected", "inject")} data-testid="inject-button">Inject</KButton>
                        </Panel>
                    )}
                </div>
            )}

            {/* FINANCES */}
            {tab === "finances" && (
                <div className="space-y-4">
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                        <Tile label="Revenue / day" value={money(m.rev_day)} accent="#00FF66" />
                        <Tile label="Materials / day" value={money(m.material_day)} accent="#FFC300" />
                        <Tile label="Wages / day" value={money(m.wage_per_day)} accent="#FF8A00" />
                        <Tile label="Net / day" value={money(net)} accent={net >= 0 ? "#00FF66" : "#FF0055"} />
                    </div>
                    <Panel className="p-5">
                        <div className="font-display font-bold text-white mb-1">Profit / Loss History</div>
                        <p className="text-[11px] text-muted-foreground mb-3">Each entry is a real settlement window: units sold × price − materials − wages. Rates shown are the per-day run-rate at that moment.</p>
                        {(!b.history || b.history.length === 0) ? (
                            <div className="text-sm text-muted-foreground">No history yet. Check back as time passes.</div>
                        ) : (
                            <div className="space-y-1 font-mono text-xs max-h-72 overflow-y-auto" data-testid="finance-history">
                                {b.history.slice().reverse().map((h, i) => (
                                    <div key={i} className="flex items-center justify-between gap-3 border-b border-white/5 py-1.5">
                                        <span className="text-muted-foreground shrink-0">{new Date(h.ts).toLocaleString()}</span>
                                        <span className="flex gap-2 items-center flex-wrap justify-end">
                                            {h.sold != null && <span className="text-foreground/60">{Math.round(h.sold)} sold</span>}
                                            <span className="text-neon-green">rev {money(h.rev || 0)}/d</span>
                                            <span className="text-neon-yellow">mat {money(h.material || 0)}/d</span>
                                            <span className="text-neon-red">wage {money(h.wages || 0)}/d</span>
                                            <span className={(h.net || 0) >= 0 ? "text-neon-green" : "text-neon-red"}>net {money(h.net)}/d</span>
                                            {h.amount != null && <span className="text-muted-foreground">({h.amount >= 0 ? "+" : ""}{money(h.amount)})</span>}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </Panel>
                </div>
            )}

            {/* EMPLOYEES */}
            {tab === "employees" && (
                <div className="space-y-4">
                    <div>
                        <div className="font-display font-bold text-white mb-2">NPC Employees ({employees.length})</div>
                        <div className="space-y-3">
                    {employees.length === 0 ? (
                        <EmptyState icon={Users} title="No NPC staff yet" sub="Hire from the Applicants tab. Understaffed businesses earn far less." />
                    ) : employees.map((e) => {
                        const inTraining = e.training && new Date(e.training.ends_at).getTime() > Date.now();
                        const trainLeft = inTraining ? (new Date(e.training.ends_at).getTime() - Date.now()) / 1000 : 0;
                        return (
                            <Panel key={e.id} className={cn("p-4", e.status === "sick" && "border-neon-red/30", e.wants_raise && "border-neon-yellow/40")} data-testid={`employee-${e.id}`}>
                                <div className="flex items-start justify-between gap-3 flex-wrap">
                                    <div className="flex-1 min-w-[200px]">
                                        <div className="flex items-center gap-2">
                                            <span className="font-display font-bold text-white">{e.name}</span>
                                            <Pill tone="cyan" className="capitalize">{e.role.replace(/_/g, " ")}</Pill>
                                            {e.status === "sick" && <Pill tone="red">Sick</Pill>}
                                            {e.wants_raise && <Pill tone="yellow">Wants Raise</Pill>}
                                            {inTraining && <Pill tone="purple">Training {fmtDuration(trainLeft)}</Pill>}
                                        </div>
                                        <div className="text-[11px] text-muted-foreground font-mono mt-1">Age {e.age} · Skill {e.skill}/10 · Loyalty {Math.round(e.loyalty)} · <span className="text-neon-green">${e.daily_wage}/day</span></div>
                                        <ProjLine proj={e.projection} label="Est. contribution" testid={`npc-proj-${e.id}`} />
                                        <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-2 max-w-xs">
                                            <StatBar label="Morale" value={e.morale} color="#B026FF" />
                                            <StatBar label="Energy" value={e.energy} color="#00F3FF" />
                                        </div>
                                        <div className="mt-2"><TraitPills traits={e.traits} /></div>
                                    </div>
                                    <div className="flex flex-col gap-2 w-32">
                                        <KButton variant={e.wants_raise ? "yellow" : "ghost"} className={e.wants_raise ? "border border-neon-yellow text-neon-yellow hover:bg-neon-yellow hover:text-black" : ""} loading={busy === "raise" + e.id} onClick={() => run(() => api.post(`/businesses/employees/${e.id}/raise`), "Raise given", "raise" + e.id)} data-testid={`raise-${e.id}`}><BadgeDollarSign className="w-3.5 h-3.5" /> Raise</KButton>
                                        <KButton variant="primary" disabled={inTraining} onClick={() => setTrainEmp(e)} data-testid={`train-${e.id}`}><GraduationCap className="w-3.5 h-3.5" /> Train</KButton>
                                        <KButton variant="danger" loading={busy === "fire" + e.id} onClick={() => run(() => api.post(`/businesses/employees/${e.id}/fire`), `${e.name} fired`, "fire" + e.id)} data-testid={`fire-${e.id}`}>Fire</KButton>
                                    </div>
                                </div>
                            </Panel>
                        );
                    })}
                        </div>
                    </div>
                    {playerEmps.length > 0 && (
                        <div>
                            <div className="font-display font-bold text-white mb-2 flex items-center gap-2 flex-wrap">Player Employees ({playerEmps.length})
                                <span className="text-[11px] text-muted-foreground font-normal">— real players · manage in Player Hiring tab</span></div>
                            <div className="space-y-2">
                                {playerEmps.map((e) => (
                                    <Panel key={e.id} className="p-3 border-neon-purple/20" data-testid={`emp-list-player-${e.id}`}>
                                        <div className="flex items-center justify-between flex-wrap gap-2">
                                            <div>
                                                <span className="font-display font-bold text-white text-sm">{e.employee_name}</span>
                                                <Pill tone="purple" className="ml-2 capitalize">{(e.role || "").replace(/_/g, " ")}</Pill>
                                                {e.on_shift
                                                    ? <Pill tone="green" className="ml-2">Working now</Pill>
                                                    : <Pill tone="yellow" className="ml-2">Off shift</Pill>}
                                                <span className="text-[11px] text-muted-foreground ml-2">${e.wage_per_hour}/h · {Math.round(e.total_hours_worked || 0)}h worked</span>
                                                <div className="text-[11px] text-neon-purple flex items-center gap-1 mt-0.5"><Clock className="w-3 h-3" /> {scheduleLabel(e.schedule)}</div>
                                            </div>
                                            <div className="text-[11px] text-muted-foreground">Perf {Math.round(e.performance)} · Reliab {Math.round(e.reliability)}{e.today && e.today.hours > 0 ? ` · today net ${e.today.net >= 0 ? "+$" : "-$"}${Math.abs(Math.round(e.today.net))}` : ""}</div>
                                        </div>
                                    </Panel>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
            {tab === "applicants" && (
                <div className="space-y-3">
                    <KButton variant="green" loading={busy === "recruit"} onClick={() => run(() => api.post(`/businesses/${id}/recruit`), "Premium candidate recruited", "recruit")} data-testid="recruit-button">
                        <Sparkles className="w-3.5 h-3.5" /> Pay to Recruit a Strong Candidate
                    </KButton>
                    {applicants.length === 0 ? (
                        <EmptyState icon={UserPlus} title="No applicants right now" sub="New applicants arrive over real time. Recruit to get one instantly." />
                    ) : applicants.map((a) => (
                        <Panel key={a.id} className="p-4" data-testid={`applicant-${a.id}`}>
                            <div className="flex items-start justify-between gap-3 flex-wrap">
                                <div className="flex-1 min-w-[200px]">
                                    <div className="flex items-center gap-2">
                                        <span className="font-display font-bold text-white">{a.name}</span>
                                        <Pill tone="cyan" className="capitalize">{a.role.replace(/_/g, " ")}</Pill>
                                    </div>
                                    <div className="text-[11px] text-muted-foreground font-mono mt-1">Age {a.age} · Skill {a.skill}/10 · Reliability {a.reliability} · Wants <span className="text-neon-yellow">${a.daily_wage}/day</span></div>
                                    <div className="mt-2"><TraitPills traits={a.traits} /></div>
                                </div>
                                <div className="flex flex-col gap-2 w-28">
                                    <KButton variant="green" loading={busy === "hire" + a.id} onClick={() => run(() => api.post(`/businesses/${id}/applicants/${a.id}/hire`), `Hired ${a.name}`, "hire" + a.id)} data-testid={`hire-${a.id}`}>Hire</KButton>
                                    <KButton variant="ghost" loading={busy === "rej" + a.id} onClick={() => run(() => api.post(`/businesses/${id}/applicants/${a.id}/reject`), "Rejected", "rej" + a.id)} data-testid={`reject-${a.id}`}>Reject</KButton>
                                </div>
                            </div>
                        </Panel>
                    ))}
                </div>
            )}

            {/* TRAINING */}
            {tab === "training" && (
                <div className="space-y-4">
                    <Panel className="p-5">
                        <div className="font-display font-bold text-white mb-3">In Training</div>
                        {employees.filter((e) => e.training && new Date(e.training.ends_at).getTime() > Date.now()).length === 0 ? (
                            <div className="text-sm text-muted-foreground">Nobody is training. Assign training from the Employees tab.</div>
                        ) : employees.filter((e) => e.training && new Date(e.training.ends_at).getTime() > Date.now()).map((e) => (
                            <div key={e.id} className="flex items-center justify-between border-b border-white/5 py-2 text-sm">
                                <span className="text-white">{e.name} — {e.training.label}</span>
                                <span className="font-mono text-neon-purple">{fmtDuration((new Date(e.training.ends_at).getTime() - Date.now()) / 1000)}</span>
                            </div>
                        ))}
                    </Panel>
                    <div className="grid sm:grid-cols-2 gap-3">
                        {trainOpts.map((o) => (
                            <Panel key={o.id} className="p-4">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="font-display font-bold text-white text-sm">{o.label}</span>
                                    <span className="font-mono text-neon-red">${o.cost}</span>
                                </div>
                                <p className="text-[11px] text-muted-foreground mb-2">{o.desc}</p>
                                <div className="flex flex-wrap gap-1">
                                    <Pill tone="green">+{o.skill_gain} skill</Pill>
                                    <Pill tone="purple">+{o.morale_gain} morale</Pill>
                                    <Pill tone="cyan">+{o.loyalty_gain} loyalty</Pill>
                                    <Pill tone="yellow">{Math.round(o.fail_chance * 100)}% fail</Pill>
                                </div>
                            </Panel>
                        ))}
                    </div>
                </div>
            )}

            {/* PLAYER HIRING */}
            {tab === "hiring" && <PlayerHiring bizId={id} hiringOpen={b.hiring_open} onReloadDetail={loadAll} roles={(m.staffing || []).map((s) => s.role)} />}

            {/* EVENTS */}
            {tab === "events" && (
                <Panel className="p-0 overflow-hidden bg-[#050505]">
                    {events.length === 0 ? (
                        <div className="px-4 py-8 text-center text-muted-foreground text-sm font-mono">No events for this business yet.</div>
                    ) : events.map((e, i) => (
                        <div key={e.id || i} className="px-4 py-2.5 font-mono text-xs border-b border-white/5" data-testid={`biz-event-${i}`}>
                            <span className="text-muted-foreground/50">{new Date(e.ts).toLocaleString()} </span>
                            <span className={SEV[e.severity] || "text-foreground"}>{e.message}</span>
                        </div>
                    ))}
                </Panel>
            )}

            {/* SELL CONFIRM MODAL */}
            {confirmSell && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-testid="sell-confirm-modal">
                    <div className="absolute inset-0 bg-black/75" onClick={() => setConfirmSell(false)} />
                    <Panel className="relative w-full max-w-md p-5">
                        <div className="flex items-center justify-between mb-3">
                            <span className="font-display font-bold text-white flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-neon-yellow" /> Sell {b.name}?</span>
                            <button onClick={() => setConfirmSell(false)}><X className="w-5 h-5 text-muted-foreground" /></button>
                        </div>
                        <p className="text-[13px] text-muted-foreground mb-3">This permanently sells the business. All employees are let go and this can't be undone.</p>
                        <div className="space-y-1.5 font-mono text-sm border border-white/10 rounded-sm p-3 mb-4">
                            <div className="flex justify-between"><span className="text-muted-foreground">Asset value (level {b.level}, rep {Math.round(b.reputation)})</span><span className="text-white">{money(Math.max(0, Math.round(b.purchase_price * 0.5 * b.level * (0.6 + 0.4 * b.reputation / 100))))}</span></div>
                            <div className="flex justify-between"><span className="text-muted-foreground">+ Uncollected cash</span><span className="text-neon-green">{money(b.cash)}</span></div>
                            <div className="flex justify-between"><span className="text-muted-foreground">− Outstanding debt</span><span className="text-neon-red">{money(b.debt)}</span></div>
                            <div className="flex justify-between border-t border-white/10 pt-1.5 mt-1.5"><span className="text-white font-bold">You receive</span><span className="text-neon-green font-bold" data-testid="sell-final-amount">{money(costs.sell_value)}</span></div>
                        </div>
                        <div className="flex gap-2">
                            <KButton variant="danger" className="flex-1" loading={busy === "sell"} onClick={sellBiz} data-testid="sell-confirm-button">Confirm Sale · {money(costs.sell_value)}</KButton>
                            <KButton variant="ghost" onClick={() => setConfirmSell(false)} data-testid="sell-cancel-button">Cancel</KButton>
                        </div>
                    </Panel>
                </div>
            )}

            {/* RENAME MODAL */}
            {renaming && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-testid="rename-modal">
                    <div className="absolute inset-0 bg-black/75" onClick={() => setRenaming(false)} />
                    <Panel className="relative w-full max-w-md p-5">
                        <div className="flex items-center justify-between mb-3">
                            <span className="font-display font-bold text-white">Rename business</span>
                            <button onClick={() => setRenaming(false)}><X className="w-5 h-5 text-muted-foreground" /></button>
                        </div>
                        <KInput label="New name (2–40 characters)" value={nameInput} onChange={(e) => setNameInput(e.target.value)} testid="rename-input" />
                        <div className="flex gap-2 mt-4">
                            <KButton variant="primary" className="flex-1" loading={busy === "rename"} disabled={nameInput.trim().length < 2} onClick={doRename} data-testid="rename-confirm-button">Save name</KButton>
                            <KButton variant="ghost" onClick={() => setRenaming(false)}>Cancel</KButton>
                        </div>
                    </Panel>
                </div>
            )}

            {/* TRAIN MODAL */}
            {trainEmp && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-testid="train-modal">
                    <div className="absolute inset-0 bg-black/75" onClick={() => setTrainEmp(null)} />
                    <Panel className="relative w-full max-w-md p-5">
                        <div className="flex items-center justify-between mb-3">
                            <span className="font-display font-bold text-white">Train {trainEmp.name}</span>
                            <button onClick={() => setTrainEmp(null)}><X className="w-5 h-5 text-muted-foreground" /></button>
                        </div>
                        <div className="space-y-2">
                            {trainOpts.map((o) => (
                                <button key={o.id} onClick={() => doTrain(trainEmp, o)} disabled={busy === "train"}
                                    className="w-full text-left p-3 border border-white/12 rounded-sm hover:border-neon-cyan/50 transition-colors disabled:opacity-50" data-testid={`train-opt-${o.id}`}>
                                    <div className="flex items-center justify-between">
                                        <span className="font-display font-bold text-white text-sm">{o.label}</span>
                                        <span className="font-mono text-neon-red text-xs">${o.cost} · {realDurationLabel(o.duration_minutes, 1)}</span>
                                    </div>
                                    <div className="text-[11px] text-muted-foreground">{o.desc}</div>
                                </button>
                            ))}
                        </div>
                    </Panel>
                </div>
            )}
        </div>
    );
}
