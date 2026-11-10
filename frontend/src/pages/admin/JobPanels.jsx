import { useEffect, useState, useCallback, useMemo } from "react";
import { api, errMessage } from "@/lib/api";
import { SectionTitle, Spinner, Panel, Pill, Money } from "@/components/game/primitives";
import { KButton, KInput } from "@/components/game/controls";
import { money } from "@/lib/helpers";
import {
    Settings, Settings2, Plus, Pencil, Trash2, X, Database, Users, SlidersHorizontal, Coins as DollarSign, Gauge,
    MapPin, Store, Clock, Hammer as Briefcase, Castle as LayoutDashboard, Castle as Building2, Skull, GripVertical, RotateCcw, Eye, EyeOff,
    Activity, TrendingUp, Wallet, Shield as Zap, BookOpen as GraduationCap, Sparkles, User, BadgeCheck,
    ShoppingCart, Scale, Home, Compass as Car, Footprints as Bike, Package as Truck, Gem, HeartPulse, Radio, AlertTriangle, Search,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, horizontalListSortingStrategy, useSortable, arrayMove } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

function JobShiftsPanel() {
    const [data, setData] = useState(null);
    const [sel, setSel] = useState(null);      // job id being edited
    const [draft, setDraft] = useState(null);   // shift_options array
    const [saving, setSaving] = useState(false);
    const load = useCallback(() => api.get("/admin/job-shifts").then(({ data }) => setData(data)).catch(() => setData({ jobs: [] })), []);
    useEffect(() => { load(); }, [load]);

    const openJob = (jb) => { setSel(jb.id); setDraft(JSON.parse(JSON.stringify(jb.shift_options || []))); };
    const setShift = (i, k, v) => setDraft((d) => d.map((s, idx) => (idx === i ? { ...s, [k]: v } : s)));
    const setWin = (i, k, v) => setDraft((d) => d.map((s, idx) => (idx === i ? { ...s, start_window: { ...(s.start_window || {}), [k]: v } } : s)));
    const addShift = () => setDraft((d) => [...d, { id: `shift${d.length + 1}`, name: "New Shift", duration_hours: 4, start_window: { min_hour: 8, max_hour: 18 }, injury_risk: 0.03, pay_multiplier: 1, xp_multiplier: 1 }]);
    const removeShift = (i) => setDraft((d) => d.filter((_, idx) => idx !== i));
    const save = async () => {
        setSaving(true);
        try {
            await api.put(`/admin/job-shifts/${sel}`, { shift_options: draft });
            toast.success("Shifts saved — live for players immediately");
            setSel(null); setDraft(null); await load();
        } catch (e) { toast.error(errMessage(e)); }
        setSaving(false);
    };

    if (!data) return <Spinner />;
    const selJob = (data.jobs || []).find((j) => j.id === sel);
    const numCls = "bg-black/40 border border-white/15 rounded-sm px-2 py-1.5 text-xs text-white w-full";

    return (
        <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Configure each job's work shifts — hours, start-time window, injury risk and pay/XP multipliers. A shift can only be started while the current game hour is inside its window. An overnight window wraps midnight when Start &gt; End (e.g. 21 → 03). Changes go live in players' My Trade page immediately.</p>

            {sel && draft ? (
                <Panel className="p-5 space-y-4 border-neon-cyan/30" data-testid="jobshifts-editor">
                    <div className="flex items-center justify-between flex-wrap gap-2">
                        <div className="flex items-center gap-2">
                            <Briefcase className="w-4 h-4 text-neon-cyan" />
                            <span className="font-display font-bold text-white">{selJob?.title || sel}</span>
                            <Pill tone="green">¤ {selJob?.hourly_wage}/h base</Pill>
                        </div>
                        <KButton variant="ghost" onClick={addShift} data-testid="jobshift-add"><Plus className="w-3.5 h-3.5" /> Add Shift</KButton>
                    </div>

                    <div className="space-y-3">
                        {draft.map((s, i) => (
                            <div key={i} className="border border-white/10 rounded-sm p-3 space-y-2" data-testid={`jobshift-row-${i}`}>
                                <div className="flex items-center justify-between gap-2">
                                    <span className="text-[10px] font-mono text-muted-foreground">Shift #{i + 1}</span>
                                    <button onClick={() => removeShift(i)} className="text-neon-red hover:text-neon-red/70" data-testid={`jobshift-del-${i}`}><Trash2 className="w-4 h-4" /></button>
                                </div>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                    <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Name
                                        <KInput value={s.name} onChange={(e) => setShift(i, "name", e.target.value)} testid={`jobshift-name-${i}`} /></label>
                                    <label className="text-[10px] text-muted-foreground flex flex-col gap-1">ID (unique)
                                        <KInput value={s.id} onChange={(e) => setShift(i, "id", e.target.value)} testid={`jobshift-id-${i}`} /></label>
                                </div>
                                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                                    <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Hours
                                        <input type="number" min="1" max="16" className={numCls} value={s.duration_hours} onChange={(e) => setShift(i, "duration_hours", Number(e.target.value))} data-testid={`jobshift-hours-${i}`} /></label>
                                    <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Start (0-24)
                                        <input type="number" min="0" max="24" className={numCls} value={s.start_window?.min_hour ?? 0} onChange={(e) => setWin(i, "min_hour", Number(e.target.value))} data-testid={`jobshift-start-${i}`} /></label>
                                    <label className="text-[10px] text-muted-foreground flex flex-col gap-1">End (0-24)
                                        <input type="number" min="0" max="24" className={numCls} value={s.start_window?.max_hour ?? 24} onChange={(e) => setWin(i, "max_hour", Number(e.target.value))} data-testid={`jobshift-end-${i}`} /></label>
                                    <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Injury risk
                                        <input type="number" min="0" max="1" step="0.01" className={numCls} value={s.injury_risk} onChange={(e) => setShift(i, "injury_risk", Number(e.target.value))} data-testid={`jobshift-risk-${i}`} /></label>
                                    <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Pay ×
                                        <input type="number" min="0.1" step="0.05" className={numCls} value={s.pay_multiplier} onChange={(e) => setShift(i, "pay_multiplier", Number(e.target.value))} data-testid={`jobshift-pay-${i}`} /></label>
                                </div>
                                <label className="text-[10px] text-muted-foreground flex flex-col gap-1 sm:w-1/5">XP ×
                                    <input type="number" min="0.1" step="0.05" className={numCls} value={s.xp_multiplier} onChange={(e) => setShift(i, "xp_multiplier", Number(e.target.value))} data-testid={`jobshift-xp-${i}`} /></label>
                            </div>
                        ))}
                        {draft.length === 0 && <p className="text-[11px] text-neon-yellow font-mono">No shifts — add at least one so players can work this job.</p>}
                    </div>

                    <div className="flex gap-2 pt-1">
                        <KButton variant="green" loading={saving} disabled={draft.length === 0} onClick={save} data-testid="jobshift-save">Save Shifts</KButton>
                        <KButton variant="ghost" onClick={() => { setSel(null); setDraft(null); }} data-testid="jobshift-cancel">Cancel</KButton>
                    </div>
                </Panel>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {(data.jobs || []).map((jb) => (
                        <Panel key={jb.id} className="p-4" data-testid={`jobshift-job-${jb.id}`}>
                            <div className="flex items-start justify-between mb-2">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <span className="font-display font-bold text-white">{jb.title}</span>
                                    <Pill tone="purple">T{jb.tier}</Pill>
                                    <span className="text-[10px] font-mono text-muted-foreground">{jb.category}</span>
                                </div>
                                <button onClick={() => openJob(jb)} className="text-muted-foreground hover:text-neon-cyan" data-testid={`jobshift-edit-${jb.id}`}><Pencil className="w-4 h-4" /></button>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {(jb.shift_options || []).filter((s) => typeof s === "object").map((s) => {
                                    const w = s.start_window || {};
                                    const pad = (n) => String(n).padStart(2, "0");
                                    return (
                                        <Pill key={s.id} tone={(s.injury_risk || 0) >= 0.1 ? "red" : "cyan"}>
                                            {s.name} · {s.duration_hours}h · {pad(w.min_hour ?? 0)}-{pad(w.max_hour ?? 24)}
                                        </Pill>
                                    );
                                })}
                                {(!jb.shift_options || jb.shift_options.length === 0) && <span className="text-[11px] text-neon-yellow font-mono">No shifts configured</span>}
                            </div>
                        </Panel>
                    ))}
                </div>
            )}
        </div>
    );
}
function JobApplicationsPanel() {
    const [data, setData] = useState(null);
    const [sel, setSel] = useState(null);
    const [draft, setDraft] = useState(null);
    const [saving, setSaving] = useState(false);
    const [view, setView] = useState("tuning"); // "tuning" | "monitor"
    const load = useCallback(() => api.get("/admin/job-applications").then(({ data }) => setData(data)).catch(() => setData({ jobs: [] })), []);
    useEffect(() => { load(); }, [load]);

    const openJob = (jb) => {
        setSel(jb.id);
        setDraft({
            acceptance_base_chance: jb.acceptance_base_chance ?? 0.5,
            skill_weight: jb.skill_weight ?? 1.0,
            success_response: jb.success_response || "",
            failure_response: jb.failure_response || "",
            reason_strings: {
                accept: { ...(jb.reason_strings?.accept || {}) },
                reject: { ...(jb.reason_strings?.reject || {}) },
            },
        });
    };
    const setReason = (kind, key, val) => setDraft((d) => ({ ...d, reason_strings: { ...d.reason_strings, [kind]: { ...d.reason_strings[kind], [key]: val } } }));
    const save = async () => {
        setSaving(true);
        try {
            await api.put(`/admin/job-applications/${sel}`, draft);
            toast.success("Hiring settings saved — live for players immediately");
            setSel(null); setDraft(null); await load();
        } catch (e) { toast.error(errMessage(e)); }
        setSaving(false);
    };

    if (!data) return <Spinner />;
    const selJob = (data.jobs || []).find((j) => j.id === sel);
    const numCls = "bg-black/40 border border-white/15 rounded-sm px-2 py-1.5 text-xs text-white w-full";
    const taCls = "bg-black/40 border border-white/15 rounded-sm px-2 py-1.5 text-xs text-white w-full min-h-[64px]";
    const rowCls = "bg-black/40 border border-white/15 rounded-sm px-2 py-1 text-xs text-white flex-1";
    const humanize = (k) => k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-2" data-testid="jobapps-view-toggle">
                <KButton variant={view === "tuning" ? "primary" : "ghost"} onClick={() => setView("tuning")} data-testid="jobapps-tab-tuning">Job Tuning</KButton>
                <KButton variant={view === "monitor" ? "primary" : "ghost"} onClick={() => setView("monitor")} data-testid="jobapps-tab-monitor">Recent Applications</KButton>
            </div>

            {view === "monitor" ? <ApplicationsMonitor /> : (
            <>
            <p className="text-sm text-muted-foreground">
                Tune hire difficulty, roleplay responses and the per-outcome <span className="text-white">reason strings</span> the system picks from.
                <span className="text-white"> Base Chance</span> (0–1) is the starting hire probability; <span className="text-white">Skill Weight</span> multiplies how much skill helps.
                Responses support <span className="font-mono text-neon-cyan">{"{title}"}</span>, <span className="font-mono text-neon-cyan">{"{wage}"}</span>, <span className="font-mono text-neon-cyan">{"{reason}"}</span>.
                Reason strings are managerial — players only ever see the final Success/Failure response (embed <span className="font-mono text-neon-cyan">{"{reason}"}</span> in it to surface one).
            </p>

            {sel && draft ? (
                <Panel className="p-5 space-y-4 border-neon-cyan/30" data-testid="jobapps-editor">
                    <div className="flex items-center gap-2">
                        <Briefcase className="w-4 h-4 text-neon-cyan" />
                        <span className="font-display font-bold text-white">{selJob?.title || sel}</span>
                        <Pill tone="purple">T{selJob?.tier}</Pill>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Acceptance Base Chance (0.0–1.0)
                            <input type="number" min="0" max="1" step="0.05" className={numCls} value={draft.acceptance_base_chance}
                                onChange={(e) => setDraft((d) => ({ ...d, acceptance_base_chance: Number(e.target.value) }))} data-testid="jobapps-base" /></label>
                        <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Skill Weight (0.0–10.0)
                            <input type="number" min="0" max="10" step="0.1" className={numCls} value={draft.skill_weight}
                                onChange={(e) => setDraft((d) => ({ ...d, skill_weight: Number(e.target.value) }))} data-testid="jobapps-weight" /></label>
                    </div>
                    <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Success Response (shown when hired)
                        <textarea className={taCls} value={draft.success_response}
                            onChange={(e) => setDraft((d) => ({ ...d, success_response: e.target.value }))} data-testid="jobapps-success" /></label>
                    <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Failure Response (shown when rejected)
                        <textarea className={taCls} value={draft.failure_response}
                            onChange={(e) => setDraft((d) => ({ ...d, failure_response: e.target.value }))} data-testid="jobapps-failure" /></label>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                        <div data-testid="jobapps-accept-reasons">
                            <div className="text-[11px] font-mono uppercase tracking-wider text-neon-green/80 mb-2">Accept Reasons</div>
                            <div className="space-y-1.5">
                                {(data.accept_reason_keys || Object.keys(draft.reason_strings.accept)).map((k) => (
                                    <div key={k} className="flex items-center gap-2">
                                        <span className="text-[10px] text-muted-foreground w-28 shrink-0">{humanize(k)}</span>
                                        <input className={rowCls} value={draft.reason_strings.accept[k] ?? ""} onChange={(e) => setReason("accept", k, e.target.value)} data-testid={`jobapps-accept-${k}`} />
                                    </div>
                                ))}
                            </div>
                        </div>
                        <div data-testid="jobapps-reject-reasons">
                            <div className="text-[11px] font-mono uppercase tracking-wider text-neon-red/80 mb-2">Reject Reasons</div>
                            <div className="space-y-1.5">
                                {(data.reject_reason_keys || Object.keys(draft.reason_strings.reject)).map((k) => (
                                    <div key={k} className="flex items-center gap-2">
                                        <span className="text-[10px] text-muted-foreground w-28 shrink-0">{humanize(k)}</span>
                                        <input className={rowCls} value={draft.reason_strings.reject[k] ?? ""} onChange={(e) => setReason("reject", k, e.target.value)} data-testid={`jobapps-reject-${k}`} />
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="flex gap-2 pt-1">
                        <KButton variant="green" loading={saving} onClick={save} data-testid="jobapps-save">Save</KButton>
                        <KButton variant="ghost" onClick={() => { setSel(null); setDraft(null); }} data-testid="jobapps-cancel">Cancel</KButton>
                    </div>
                </Panel>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {(data.jobs || []).map((jb) => (
                        <Panel key={jb.id} className="p-4" data-testid={`jobapps-job-${jb.id}`}>
                            <div className="flex items-start justify-between mb-2">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <span className="font-display font-bold text-white">{jb.title}</span>
                                    <Pill tone="purple">T{jb.tier}</Pill>
                                </div>
                                <button onClick={() => openJob(jb)} className="text-muted-foreground hover:text-neon-cyan" data-testid={`jobapps-edit-${jb.id}`}><Pencil className="w-4 h-4" /></button>
                            </div>
                            <div className="flex flex-wrap gap-1.5 mb-2">
                                <Pill tone="cyan">Base {Math.round((jb.acceptance_base_chance ?? 0.5) * 100)}%</Pill>
                                <Pill tone="green">Skill ×{jb.skill_weight ?? 1}</Pill>
                            </div>
                            <p className="text-[10px] text-muted-foreground line-clamp-2 italic">"{jb.failure_response}"</p>
                        </Panel>
                    ))}
                </div>
            )}
            </>
            )}
        </div>
    );
}
function ApplicationsMonitor() {
    const [apps, setApps] = useState(null);
    const [filter, setFilter] = useState("");
    const [edit, setEdit] = useState({}); // app_id -> reason draft
    const [busy, setBusy] = useState(null);
    const load = useCallback(() => api.get(`/admin/applications${filter ? `?status=${filter}` : ""}`).then(({ data }) => setApps(data.applications || [])).catch(() => setApps([])), [filter]);
    useEffect(() => { load(); }, [load]);

    const saveReason = async (a) => {
        setBusy(a.id);
        try {
            await api.put(`/admin/applications/${a.id}`, { reason: edit[a.id] });
            toast.success("Reason overridden");
            setEdit((e) => { const n = { ...e }; delete n[a.id]; return n; });
            await load();
        } catch (e) { toast.error(errMessage(e)); }
        setBusy(null);
    };
    const tone = (s) => s === "accepted" ? "green" : s === "rejected" ? "red" : s === "pending" ? "yellow" : "cyan";
    if (!apps) return <Spinner />;

    return (
        <div className="space-y-3" data-testid="applications-monitor">
            <div className="flex items-center gap-2 flex-wrap">
                {["", "pending", "accepted", "rejected", "expired"].map((s) => (
                    <button key={s || "all"} onClick={() => setFilter(s)} data-testid={`appmon-filter-${s || "all"}`}
                        className={cn("text-[11px] px-2.5 py-1 rounded-sm border font-mono", filter === s ? "border-neon-cyan text-neon-cyan bg-neon-cyan/10" : "border-white/15 text-muted-foreground hover:text-white")}>
                        {s ? s.toUpperCase() : "ALL"}
                    </button>
                ))}
            </div>
            {apps.length === 0 ? <p className="text-sm text-muted-foreground">No applications found.</p> : (
                <div className="space-y-2">
                    {apps.map((a) => (
                        <Panel key={a.id} className="p-3" data-testid={`appmon-row-${a.id}`}>
                            <div className="flex items-center justify-between gap-2 flex-wrap mb-1.5">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <span className="text-sm text-white font-display font-bold">{a.player_name}</span>
                                    <span className="text-[11px] text-muted-foreground">→ {a.title}</span>
                                    <Pill tone={tone(a.status)}>{a.status}</Pill>
                                    {a.wage_offer ? <Pill tone="green">¤ {a.wage_offer}/h</Pill> : null}
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] text-muted-foreground shrink-0">Reason</span>
                                <input className="bg-black/40 border border-white/15 rounded-sm px-2 py-1 text-xs text-white flex-1"
                                    value={edit[a.id] ?? (a.reason ?? "")} placeholder="(not yet decided)"
                                    onChange={(e) => setEdit((m) => ({ ...m, [a.id]: e.target.value }))} data-testid={`appmon-reason-${a.id}`} />
                                <KButton variant="green" loading={busy === a.id} disabled={edit[a.id] === undefined || edit[a.id] === (a.reason ?? "")}
                                    onClick={() => saveReason(a)} data-testid={`appmon-save-${a.id}`}>Override</KButton>
                            </div>
                            {a.outcome_message && <p className="text-[10px] text-muted-foreground/70 mt-1.5 italic">Player sees: "{a.outcome_message}"</p>}
                        </Panel>
                    ))}
                </div>
            )}
        </div>
    );
}

export { JobShiftsPanel, JobApplicationsPanel, ApplicationsMonitor };
