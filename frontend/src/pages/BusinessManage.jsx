import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api, errMessage } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, StatBar, Money, EmptyState, InfoTip } from "@/components/game/primitives";
import { KButton, KInput } from "@/components/game/controls";
import { money, fmtDuration, realDurationLabel, scheduleLabel, SHIFT_PRESETS } from "@/lib/helpers";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
    Boxes, ArrowLeft, Users, UserPlus, GraduationCap, ScrollText, LineChart, LayoutGrid,
    TrendingUp, TrendingDown, AlertTriangle, Megaphone, ArrowUpCircle, Smile, Gauge,
    Heart, BadgeDollarSign, Sparkles, X, Clock, ShieldCheck,
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

function Tile({ label, value, accent = "#fff", sub }) {
    return (
        <Panel className="p-3">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
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

function PlayerHiring({ bizId, hiringOpen, onReloadDetail, roles = [] }) {
    const [apps, setApps] = useState(null);
    const [emps, setEmps] = useState([]);
    const [wages, setWages] = useState({});
    const [roleSel, setRoleSel] = useState({});
    const [schedSel, setSchedSel] = useState({});
    const [busy, setBusy] = useState(null);
    const load = useCallback(async () => {
        const [a, e] = await Promise.all([
            api.get(`/businesses/${bizId}/player-applications`),
            api.get(`/businesses/${bizId}/player-employees`),
        ]);
        setApps(a.data); setEmps(e.data);
    }, [bizId]);
    useEffect(() => { load(); }, [load]);

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
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-[11px] text-muted-foreground">$/h</span>
                                        <WageInput value={wages["e" + e.id] ?? Math.round((e.wage_per_hour + 2) * 100) / 100} onChange={(v) => setW("e" + e.id, v)} testid={`raise-wage-${e.id}`} />
                                        <KButton variant="primary" loading={busy === e.id} onClick={() => raise(e)} data-testid={`raise-send-${e.id}`}>Raise</KButton>
                                        <KButton variant="danger" loading={busy === e.id + "f"} onClick={() => fire(e)} data-testid={`fire-emp-${e.id}`}>Fire</KButton>
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
    const toggleBackup = async (role, enabled) => {
        await act(() => api.post(`/businesses/${id}/backup`, { role, enabled }), enabled ? `NPC backup enabled for ${role.replace(/_/g, " ")}` : `NPC backup disabled for ${role.replace(/_/g, " ")}`);
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
    const net = m.net_day || 0;

    return (
        <div className="space-y-6">
            <Link to="/businesses" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-neon-cyan font-mono" data-testid="back-to-businesses">
                <ArrowLeft className="w-3.5 h-3.5" /> All businesses
            </Link>
            <SectionTitle icon={Boxes} kicker={`${b.category} · Level ${b.level}/${b.max_level}${b.bankrupt ? " · BANKRUPT" : ""}`} title={b.name}
                right={<Pill tone={net >= 0 ? "green" : "red"} className="text-sm py-1">{net >= 0 ? "+" : ""}{money(net)}/day</Pill>} />

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
                        <Tile label="Net / day" value={money(net)} accent={net >= 0 ? "#00FF66" : "#FF0055"} />
                        <Tile label="Revenue / day" value={money(m.rev_day)} accent="#00F3FF" />
                        <Tile label="Expenses / day" value={money(m.exp_day)} accent="#FFC300" />
                        <Tile label="Wages / day" value={money(m.wage_per_day)} accent="#FF8A00" />
                        <Tile label="Active Coverage" value={`${Math.round((m.active_coverage ?? m.coverage) * 100)}%`} accent={(m.active_coverage ?? m.coverage) >= 0.9 ? "#00FF66" : (m.active_coverage ?? m.coverage) < 0.6 ? "#FF0055" : "#FFC300"} sub={`Roster ${Math.round((m.roster_coverage ?? 1) * 100)}%`} />
                        <Tile label="Satisfaction" value={`${m.satisfaction}%`} accent="#00F3FF" />
                        <Tile label="Avg Morale" value={`${m.morale_avg}%`} accent="#B026FF" />
                        <Tile label="Reputation" value={`${Math.round(b.reputation)}%`} accent="#00FF66" />
                        <Tile label="Uncollected" value={money(b.cash)} accent="#00FF66" />
                        <Tile label="Debt" value={money(b.debt)} accent={b.debt > 0 ? "#FF0055" : "#9CA3AF"} />
                        <Tile label="Bankruptcy Risk" value={`${m.bankruptcy_risk}%`} accent={m.bankruptcy_risk > 60 ? "#FF0055" : "#FFC300"} />
                        <Tile label="Employees" value={`${m.employee_count}${m.sick_count ? ` (+${m.sick_count} sick)` : ""}`} accent="#fff" />
                    </div>

                    <Panel className="p-5">
                        <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
                            <div className="font-display font-bold text-white flex items-center gap-1.5">
                                Staffing — Roster vs Active Coverage
                                <InfoTip text="Roster = who's officially hired/scheduled for a role. Active = who's actually working right now. Business output only comes from active coverage. Enable NPC backup to auto-cover a role when nobody is working it (the business pays a backup wage)." testid="staffing-info" />
                            </div>
                            <div className="text-[11px] font-mono text-muted-foreground">Roster {Math.round((m.roster_coverage ?? 1) * 100)}% · Active {Math.round((m.active_coverage ?? m.coverage) * 100)}%</div>
                        </div>
                        <div className="space-y-2 mt-2">
                            {m.staffing.length === 0 && <div className="text-sm text-muted-foreground">No specific staffing needed.</div>}
                            {m.staffing.map((s) => {
                                const activeOk = (s.active_filled ?? 0) >= s.recommended;
                                return (
                                    <div key={s.role} className="flex items-center justify-between gap-3 border-b border-white/5 pb-2 last:border-0" data-testid={`staffing-${s.role}`}>
                                        <div className="min-w-0">
                                            <span className="capitalize text-white text-sm">{s.role.replace(/_/g, " ")}</span>
                                            <div className="text-[11px] font-mono">
                                                <span className="text-muted-foreground">Roster {s.roster_filled}/{s.recommended}</span>
                                                <span className="text-muted-foreground"> · </span>
                                                <span className={activeOk ? "text-neon-green" : "text-neon-yellow"} data-testid={`staffing-active-${s.role}`}>
                                                    Active {s.active_working}{s.backup_active ? " (+backup)" : ""}/{s.recommended}
                                                </span>
                                            </div>
                                            <div className="text-[10px] text-muted-foreground">{s.status}{s.npc_have ? ` · ${s.npc_have} NPC` : ""}{s.player_roster ? ` · ${s.player_roster} player` : ""}</div>
                                        </div>
                                        <label className="flex items-center gap-1.5 text-[10px] text-muted-foreground cursor-pointer shrink-0" title="Auto-cover this role with an NPC when nobody is actively working it (the business pays a backup wage).">
                                            <input type="checkbox" checked={!!s.backup_enabled} onChange={(e) => toggleBackup(s.role, e.target.checked)} className="accent-neon-cyan" data-testid={`backup-toggle-${s.role}`} />
                                            <ShieldCheck className="w-3 h-3" /> NPC backup
                                        </label>
                                    </div>
                                );
                            })}
                        </div>
                        {m.backup_wage_day > 0 && <div className="text-[11px] text-neon-yellow mt-2">NPC backup currently costs ~{money(m.backup_wage_day)}/day while covering empty roles.</div>}
                    </Panel>

                    {!b.bankrupt ? (
                        <Panel className="p-4" data-testid="biz-actions">
                            <div className="grid sm:grid-cols-2 gap-3">
                                <div className="border border-white/10 rounded-sm p-3 flex flex-col">
                                    <div className="font-display font-bold text-white text-sm mb-0.5">Collect Profit</div>
                                    <p className="text-[11px] text-muted-foreground mb-3 flex-1">Move the business's uncollected cash into your wallet. Instant.</p>
                                    <KButton variant="green" disabled={b.cash <= 0} loading={busy === "collect"} onClick={() => run(() => api.post(`/businesses/${id}/collect`), "Profit collected", "collect")} data-testid="ov-collect">Collect {money(b.cash)}</KButton>
                                </div>
                                <div className="border border-white/10 rounded-sm p-3 flex flex-col">
                                    <div className="font-display font-bold text-white text-sm mb-0.5">Upgrade · Lvl {costs.upgrade_from_level} → {costs.upgrade_to_level}</div>
                                    <p className="text-[11px] text-muted-foreground mb-3 flex-1">{costs.can_upgrade ? `+${costs.upgrade_revenue_boost_pct}% revenue capacity per level and +${costs.upgrade_reputation_gain} reputation. Instant.` : "This business is already at its maximum level."}</p>
                                    <KButton variant="primary" disabled={!costs.can_upgrade} loading={busy === "upgrade"} onClick={() => run(() => api.post(`/businesses/${id}/upgrade`), "Upgraded", "upgrade")} data-testid="ov-upgrade"><ArrowUpCircle className="w-3.5 h-3.5" /> {costs.can_upgrade ? `Upgrade · ${money(costs.upgrade_cost)}` : "Max level"}</KButton>
                                </div>
                                <div className="border border-white/10 rounded-sm p-3 flex flex-col">
                                    <div className="font-display font-bold text-white text-sm mb-0.5">Marketing · Level {costs.marketing_level} → {costs.marketing_next_level}</div>
                                    <p className="text-[11px] text-muted-foreground mb-3 flex-1">+{costs.marketing_revenue_boost_pct}% ongoing revenue and +{costs.marketing_reputation_gain} reputation. Instant, permanent demand boost.</p>
                                    <KButton className="border border-neon-purple text-neon-purple hover:bg-neon-purple hover:text-white" loading={busy === "marketing"} onClick={() => run(() => api.post(`/businesses/${id}/marketing`), "Marketing campaign run", "marketing")} data-testid="ov-marketing"><Megaphone className="w-3.5 h-3.5" /> Run Marketing · {money(costs.marketing_cost)}</KButton>
                                </div>
                                <div className="border border-white/10 rounded-sm p-3 flex flex-col">
                                    <div className="font-display font-bold text-white text-sm mb-0.5">Sell Business</div>
                                    <p className="text-[11px] text-muted-foreground mb-3 flex-1">Permanently sell this business. Estimated payout <span className="text-neon-green">{money(costs.sell_value)}</span> (asset value − debt + uncollected cash).</p>
                                    <KButton variant="ghost" onClick={() => setConfirmSell(true)} data-testid="ov-sell">Sell · ~{money(costs.sell_value)}</KButton>
                                </div>
                            </div>
                        </Panel>
                    ) : (
                        <Panel className="p-4 border-neon-red/40 flex items-center gap-2 text-neon-red text-sm">
                            <AlertTriangle className="w-4 h-4" /> Bankrupt. Pay off the debt below to revive, or sell.
                        </Panel>
                    )}
                    {(b.debt > 0 || b.bankrupt) && (
                        <Panel className="p-4 flex gap-2 items-end">
                            <KInput label="Inject cash / pay debt" type="number" value={inject} onChange={(e) => setInject(e.target.value)} className="flex-1" testid="inject-input" />
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
                        <Tile label="Operating / day" value={money(m.exp_day - m.wage_per_day)} accent="#FFC300" />
                        <Tile label="Wages / day" value={money(m.wage_per_day)} accent="#FF8A00" />
                        <Tile label="Net / day" value={money(net)} accent={net >= 0 ? "#00FF66" : "#FF0055"} />
                    </div>
                    <Panel className="p-5">
                        <div className="font-display font-bold text-white mb-1">Profit / Loss History</div>
                        <p className="text-[11px] text-muted-foreground mb-3"><span className="text-foreground/70">Forecast</span> = current per-day rate (not a charge). <span className="text-neon-purple">Booking</span> = real money moved (e.g. player shifts).</p>
                        {(!b.history || b.history.length === 0) ? (
                            <div className="text-sm text-muted-foreground">No history yet. Check back as time passes.</div>
                        ) : (
                            <div className="space-y-1 font-mono text-xs max-h-72 overflow-y-auto" data-testid="finance-history">
                                {b.history.slice().reverse().map((h, i) => (
                                    <div key={i} className="flex items-center justify-between gap-3 border-b border-white/5 py-1.5">
                                        <span className="text-muted-foreground shrink-0">{new Date(h.ts).toLocaleString()}</span>
                                        {h.kind === "shift" ? (
                                            <span className="flex gap-2 items-center flex-wrap justify-end">
                                                <Pill tone="purple">Booking</Pill>
                                                <span className="text-foreground/70">{h.label}</span>
                                                <span className={h.amount >= 0 ? "text-neon-green" : "text-neon-red"}>{h.amount >= 0 ? "+" : ""}{money(h.amount)}</span>
                                            </span>
                                        ) : (
                                            <span className="flex gap-2 items-center flex-wrap justify-end">
                                                <Pill>Forecast</Pill>
                                                <span className="text-neon-green">rev {money(h.rev || 0)}/d</span>
                                                <span className="text-neon-yellow">exp {money(h.exp || 0)}/d</span>
                                                <span className={h.net >= 0 ? "text-neon-green" : "text-neon-red"}>net {money(h.net)}/d</span>
                                                {h.amount != null && <span className="text-muted-foreground">({h.amount >= 0 ? "+" : ""}{money(h.amount)})</span>}
                                            </span>
                                        )}
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
