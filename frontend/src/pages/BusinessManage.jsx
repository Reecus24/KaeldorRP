import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { api, errMessage } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, StatBar, Money, EmptyState } from "@/components/game/primitives";
import { KButton, KInput } from "@/components/game/controls";
import { money, fmtDuration, realDurationLabel } from "@/lib/helpers";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
    Boxes, ArrowLeft, Users, UserPlus, GraduationCap, ScrollText, LineChart, LayoutGrid,
    TrendingUp, TrendingDown, AlertTriangle, Megaphone, ArrowUpCircle, Smile, Gauge,
    Heart, BadgeDollarSign, Sparkles, X,
} from "lucide-react";

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

export default function BusinessManage() {
    const { id } = useParams();
    const navigate = useNavigate();
    const { act, tick } = useGame();
    const [detail, setDetail] = useState(null);
    const [employees, setEmployees] = useState([]);
    const [applicants, setApplicants] = useState([]);
    const [trainOpts, setTrainOpts] = useState([]);
    const [events, setEvents] = useState([]);
    const [tab, setTab] = useState("overview");
    const [busy, setBusy] = useState(null);
    const [inject, setInject] = useState("");
    const [trainEmp, setTrainEmp] = useState(null);

    const loadAll = useCallback(async () => {
        try {
            const [d, e, a, ev] = await Promise.all([
                api.get(`/businesses/${id}`),
                api.get(`/businesses/${id}/employees`),
                api.get(`/businesses/${id}/applicants`),
                api.get(`/businesses/${id}/events`),
            ]);
            setDetail(d.data);
            setEmployees(e.data.employees);
            setApplicants(a.data);
            setEvents(ev.data);
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
                        <Tile label="Staff Coverage" value={`${Math.round(m.coverage * 100)}%`} accent={m.coverage >= 0.9 ? "#00FF66" : m.coverage < 0.6 ? "#FF0055" : "#FFC300"} sub={m.missing_roles ? `${m.missing_roles} role(s) empty` : "fully staffed"} />
                        <Tile label="Satisfaction" value={`${m.satisfaction}%`} accent="#00F3FF" />
                        <Tile label="Avg Morale" value={`${m.morale_avg}%`} accent="#B026FF" />
                        <Tile label="Reputation" value={`${Math.round(b.reputation)}%`} accent="#00FF66" />
                        <Tile label="Uncollected" value={money(b.cash)} accent="#00FF66" />
                        <Tile label="Debt" value={money(b.debt)} accent={b.debt > 0 ? "#FF0055" : "#9CA3AF"} />
                        <Tile label="Bankruptcy Risk" value={`${m.bankruptcy_risk}%`} accent={m.bankruptcy_risk > 60 ? "#FF0055" : "#FFC300"} />
                        <Tile label="Employees" value={`${m.employee_count}${m.sick_count ? ` (+${m.sick_count} sick)` : ""}`} accent="#fff" />
                    </div>

                    <Panel className="p-5">
                        <div className="font-display font-bold text-white mb-3">Staffing Requirements</div>
                        <div className="space-y-2">
                            {m.staffing.length === 0 && <div className="text-sm text-muted-foreground">No specific staffing needed.</div>}
                            {m.staffing.map((s) => {
                                const ok = s.have >= s.recommended;
                                return (
                                    <div key={s.role} className="flex items-center justify-between text-sm" data-testid={`staffing-${s.role}`}>
                                        <span className="capitalize text-white">{s.role.replace(/_/g, " ")}</span>
                                        <span className={cn("font-mono", ok ? "text-neon-green" : "text-neon-red")}>
                                            {s.have} / {s.recommended} {ok ? "✓" : "understaffed"}
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    </Panel>

                    {!b.bankrupt ? (
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
                            <KButton variant="green" disabled={b.cash <= 0} loading={busy === "collect"} onClick={() => run(() => api.post(`/businesses/${id}/collect`), "Profit collected", "collect")} data-testid="ov-collect">Collect {money(b.cash)}</KButton>
                            <KButton variant="primary" disabled={b.level >= b.max_level} loading={busy === "upgrade"} onClick={() => run(() => api.post(`/businesses/${id}/upgrade`), "Upgraded", "upgrade")} data-testid="ov-upgrade"><ArrowUpCircle className="w-3.5 h-3.5" /> Upgrade</KButton>
                            <KButton className="border border-neon-purple text-neon-purple hover:bg-neon-purple hover:text-white" loading={busy === "marketing"} onClick={() => run(() => api.post(`/businesses/${id}/marketing`), "Marketing campaign run", "marketing")} data-testid="ov-marketing"><Megaphone className="w-3.5 h-3.5" /> Market</KButton>
                            <KButton variant="ghost" loading={busy === "sell"} onClick={() => run(() => api.post(`/businesses/${id}/sell`), "Business sold", "sell")} data-testid="ov-sell">Sell</KButton>
                        </div>
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
                        <div className="font-display font-bold text-white mb-3">Profit / Loss History</div>
                        {(!b.history || b.history.length === 0) ? (
                            <div className="text-sm text-muted-foreground">No history yet. Check back as time passes.</div>
                        ) : (
                            <div className="space-y-1 font-mono text-xs max-h-72 overflow-y-auto">
                                {b.history.slice().reverse().map((h, i) => (
                                    <div key={i} className="flex items-center justify-between border-b border-white/5 py-1.5">
                                        <span className="text-muted-foreground">{new Date(h.ts).toLocaleString()}</span>
                                        <span className="flex gap-4">
                                            <span className="text-neon-green">rev {money(h.rev || 0)}</span>
                                            <span className="text-neon-yellow">exp {money(h.exp || 0)}</span>
                                            <span className={h.net >= 0 ? "text-neon-green" : "text-neon-red"}>net {money(h.net)}</span>
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
                <div className="space-y-3">
                    {employees.length === 0 ? (
                        <EmptyState icon={Users} title="No staff yet" sub="Hire from the Applicants tab. Understaffed businesses earn far less." />
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
            )}

            {/* APPLICANTS */}
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
