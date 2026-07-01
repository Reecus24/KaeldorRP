import { useEffect, useState, useCallback } from "react";
import { api, errMessage } from "@/lib/api";
import { SectionTitle, Spinner, Panel, Pill, Money } from "@/components/game/primitives";
import { KButton, KInput } from "@/components/game/controls";
import { money } from "@/lib/helpers";
import {
    Settings, Settings2, Plus, Pencil, Trash2, X, Database, Users, SlidersHorizontal, DollarSign, Gauge,
    MapPin, Store, Clock, Briefcase, LayoutDashboard, Building2, Skull, GripVertical, RotateCcw, Eye, EyeOff,
    Activity, TrendingUp, Wallet, Zap, GraduationCap, Sparkles,
    ShoppingCart, Scale, Home, Car, HeartPulse, Radio, AlertTriangle, Search,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, horizontalListSortingStrategy, useSortable, arrayMove } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

const CONTENT_TYPES = [
    { key: "jobs", label: "Jobs", name: "title" },
    { key: "actions", label: "Actions", name: "name" },
    { key: "courses", label: "Courses", name: "title" },
    { key: "items", label: "Items", name: "name" },
    { key: "housing", label: "Housing", name: "name" },
    { key: "vehicles", label: "Vehicles", name: "name" },
    { key: "business_types", label: "Businesses", name: "name" },
    { key: "illegal_actions", label: "Illegal", name: "name" },
    { key: "random_events", label: "Events", name: "name" },
    { key: "employee_roles", label: "Emp Roles", name: "label" },
    { key: "employee_traits", label: "Emp Traits", name: "label" },
    { key: "staffing_requirements", label: "Staffing", name: "id" },
    { key: "training_options", label: "Training", name: "label" },
    { key: "employee_events", label: "Staff Events", name: "message" },
    { key: "npc_archetypes", label: "NPC Archetypes", name: "label" },
    { key: "social_traits", label: "Personality", name: "label" },
    { key: "relationship_actions", label: "Rel. Actions", name: "label" },
    { key: "gift_types", label: "Gifts", name: "label" },
    { key: "social_events", label: "Social Events", name: "message" },
];

function JsonModal({ open, title, initial, onClose, onSave }) {
    const [text, setText] = useState("");
    useEffect(() => { if (open) setText(JSON.stringify(initial || {}, null, 2)); }, [open, initial]);
    if (!open) return null;
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-testid="json-modal">
            <div className="absolute inset-0 bg-black/75" onClick={onClose} />
            <Panel className="relative w-full max-w-2xl p-5 max-h-[85vh] flex flex-col">
                <div className="flex items-center justify-between mb-3">
                    <span className="font-display font-bold text-white">{title}</span>
                    <button onClick={onClose}><X className="w-5 h-5 text-muted-foreground" /></button>
                </div>
                <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    spellCheck={false}
                    data-testid="json-editor"
                    className="flex-1 min-h-[340px] bg-[#050505] border border-white/12 rounded-sm p-3 font-mono text-xs text-neon-green/90 outline-none focus:border-neon-cyan/60 resize-none"
                />
                <div className="flex justify-end gap-2 mt-4">
                    <KButton variant="ghost" onClick={onClose}>Cancel</KButton>
                    <KButton variant="green" onClick={() => {
                        try { onSave(JSON.parse(text)); } catch { toast.error("Invalid JSON"); }
                    }} data-testid="json-save">Save</KButton>
                </div>
            </Panel>
        </div>
    );
}

function ContentEditor({ ctype }) {
    const meta = CONTENT_TYPES.find((c) => c.key === ctype);
    const [items, setItems] = useState(null);
    const [modal, setModal] = useState({ open: false, item: null, isNew: false });

    const load = useCallback(() => api.get(`/admin/content/${ctype}`).then(({ data }) => setItems(data)).catch(() => setItems([])), [ctype]);
    useEffect(() => { setItems(null); load(); }, [ctype, load]);

    const save = async (obj) => {
        try {
            if (modal.isNew) await api.post(`/admin/content/${ctype}`, obj);
            else await api.put(`/admin/content/${ctype}/${obj.id}`, obj);
            toast.success("Saved");
            setModal({ open: false });
            load();
        } catch (e) { toast.error(errMessage(e)); }
    };
    const del = async (id) => {
        if (!window.confirm("Delete this item?")) return;
        try { await api.delete(`/admin/content/${ctype}/${id}`); toast.success("Deleted"); load(); }
        catch (e) { toast.error(errMessage(e)); }
    };
    const template = items && items[0] ? { ...items[0], id: "" } : {};

    if (!items) return <Spinner />;
    return (
        <div>
            <div className="flex justify-between items-center mb-3">
                <span className="font-mono text-[11px] text-muted-foreground">{items.length} items</span>
                <KButton variant="green" onClick={() => setModal({ open: true, item: template, isNew: true })} data-testid="admin-new"><Plus className="w-3.5 h-3.5" /> New</KButton>
            </div>
            <Panel className="p-0 overflow-hidden divide-y divide-white/5">
                {items.map((it) => (
                    <div key={it.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-white/[0.02]" data-testid={`admin-row-${it.id}`}>
                        <span className="font-mono text-[10px] text-muted-foreground/60 w-28 truncate">{it.id}</span>
                        <span className="flex-1 text-sm text-white truncate">{it[meta.name] || it.title || it.name}</span>
                        <button onClick={() => setModal({ open: true, item: it, isNew: false })} className="text-muted-foreground hover:text-neon-cyan" data-testid={`admin-edit-${it.id}`}><Pencil className="w-4 h-4" /></button>
                        <button onClick={() => del(it.id)} className="text-muted-foreground hover:text-neon-red" data-testid={`admin-del-${it.id}`}><Trash2 className="w-4 h-4" /></button>
                    </div>
                ))}
            </Panel>
            <JsonModal open={modal.open} title={modal.isNew ? `New ${meta.label}` : `Edit ${meta.label}`} initial={modal.item} onClose={() => setModal({ open: false })} onSave={save} />
        </div>
    );
}

function ConfigEditor() {
    const [cfg, setCfg] = useState(null);
    const [ts, setTs] = useState("");
    const load = () => api.get("/admin/config").then(({ data }) => { setCfg(data); setTs(String(data.time_scale)); });
    useEffect(() => { load(); }, []);

    const saveAll = async (obj) => {
        try { await api.put("/admin/config", obj); toast.success("Config saved"); load(); }
        catch (e) { toast.error(errMessage(e)); }
    };
    const saveTs = async () => {
        const v = Number(ts);
        if (!v || v <= 0) return toast.error("Invalid time scale");
        await saveAll({ ...cfg, time_scale: v });
    };
    if (!cfg) return <Spinner />;
    const realMinPerGameHour = (60 / cfg.time_scale).toFixed(1);
    const isRealtime = cfg.time_scale <= 1.0001;

    return (
        <div className="space-y-4">
            <Panel className={cn("p-4 flex items-center gap-3", isRealtime ? "border-neon-green/40" : "border-neon-yellow/40")} data-testid="realtime-indicator">
                <span className={cn("w-2.5 h-2.5 rounded-full", isRealtime ? "bg-neon-green" : "bg-neon-yellow animate-pulse-dot")} />
                <div className="flex-1">
                    <div className={cn("font-display font-bold", isRealtime ? "text-neon-green" : "text-neon-yellow")}>
                        {isRealtime ? "TRUE REAL-TIME MODE" : `ACCELERATED TEST MODE — ×${Math.round(cfg.time_scale)} faster`}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                        {isRealtime
                            ? "1 game hour = 1 real hour. Jobs, study, businesses, rent and sentences run over real-life time."
                            : `1 game hour = ${realMinPerGameHour} real minutes. Set time scale to 1 for true real-time.`}
                    </div>
                </div>
            </Panel>
            <Panel className="p-5">
                <div className="font-display font-bold text-white mb-1">Time Scale</div>
                <p className="text-[11px] text-muted-foreground mb-3">Game minutes that pass per 1 real minute. Currently <b className="text-neon-cyan">1 game hour = {realMinPerGameHour} real minutes</b>. Set to 1 for true real-time.</p>
                <div className="flex gap-2 max-w-xs">
                    <KInput type="number" value={ts} onChange={(e) => setTs(e.target.value)} testid="config-timescale" />
                    <KButton variant="green" onClick={saveTs} data-testid="save-timescale">Apply</KButton>
                </div>
            </Panel>
            <Panel className="p-5">
                <div className="font-display font-bold text-white mb-3">Full Balancing Config (JSON)</div>
                <ConfigJson cfg={cfg} onSave={saveAll} />
            </Panel>
        </div>
    );
}

function ConfigJson({ cfg, onSave }) {
    const [text, setText] = useState(JSON.stringify(cfg, null, 2));
    useEffect(() => { setText(JSON.stringify(cfg, null, 2)); }, [cfg]);
    return (
        <div>
            <textarea value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} data-testid="config-json"
                className="w-full min-h-[300px] bg-[#050505] border border-white/12 rounded-sm p-3 font-mono text-xs text-neon-green/90 outline-none focus:border-neon-cyan/60 resize-none" />
            <KButton variant="green" className="mt-3" onClick={() => { try { onSave(JSON.parse(text)); } catch { toast.error("Invalid JSON"); } }} data-testid="save-config">Save Config</KButton>
        </div>
    );
}

function EconomyTuner() {
    const [rows, setRows] = useState(null);
    const [applyExisting, setApplyExisting] = useState(true);
    const load = () => api.get("/admin/business-economy").then(({ data }) => setRows(data));
    useEffect(() => { load(); }, []);
    const setField = (id, k, v) => setRows((rs) => rs.map((r) => r.id === id ? { ...r, [k]: v } : r));
    const save = async (r) => {
        try {
            await api.put(`/admin/business-economy/${r.id}`, {
                price: Number(r.price), material_cost: Number(r.material_cost),
                daily_demand: Number(r.daily_demand), production_per_worker_hour: Number(r.production_per_worker_hour),
                base_hourly_wage: r.base_hourly_wage === "" || r.base_hourly_wage == null ? null : Number(r.base_hourly_wage),
                opening_open: r.opening_hours.open, opening_close: r.opening_hours.close,
                apply_existing: applyExisting,
            });
            toast.success(`${r.name} updated${applyExisting ? " (applied to existing)" : ""}`);
            load();
        } catch (e) { toast.error(errMessage(e)); }
    };
    if (!rows) return <Spinner />;
    return (
        <div className="space-y-3">
            <Panel className="p-4 flex items-center justify-between flex-wrap gap-2">
                <div className="text-[11px] text-muted-foreground">Edit price, material cost, demand, PPH, base wage and opening hours per business type. Changes hit the live simulation on the next tick.</div>
                <label className="flex items-center gap-2 text-xs text-white cursor-pointer">
                    <input type="checkbox" checked={applyExisting} onChange={(e) => setApplyExisting(e.target.checked)} data-testid="apply-existing-toggle" />
                    Apply to existing businesses (not just new)
                </label>
            </Panel>
            <Panel className="p-0 overflow-x-auto">
                <div className="min-w-[900px]">
                    <div className="grid grid-cols-12 gap-2 px-3 py-2 border-b border-white/8 bg-[#050505] font-mono text-[10px] uppercase text-muted-foreground">
                        <div className="col-span-2">Business</div><div className="col-span-1">Price</div><div className="col-span-2">Material $</div>
                        <div className="col-span-1">Demand</div><div className="col-span-1">PPH</div><div className="col-span-2">Base $/hr</div>
                        <div className="col-span-2">Open–Close</div><div className="col-span-1"></div>
                    </div>
                    {rows.map((r) => (
                        <div key={r.id} className="grid grid-cols-12 gap-2 px-3 py-2 border-b border-white/5 items-center" data-testid={`econ-row-${r.id}`}>
                            <div className="col-span-2 text-white text-xs truncate">{r.name}</div>
                            <input className="col-span-1 econ-inp" value={r.price} onChange={(e) => setField(r.id, "price", e.target.value)} data-testid={`econ-price-${r.id}`} />
                            <input className="col-span-2 econ-inp" value={r.material_cost} onChange={(e) => setField(r.id, "material_cost", e.target.value)} data-testid={`econ-mat-${r.id}`} />
                            <input className="col-span-1 econ-inp" value={r.daily_demand} onChange={(e) => setField(r.id, "daily_demand", e.target.value)} data-testid={`econ-demand-${r.id}`} />
                            <input className="col-span-1 econ-inp" value={r.production_per_worker_hour} onChange={(e) => setField(r.id, "production_per_worker_hour", e.target.value)} data-testid={`econ-pph-${r.id}`} />
                            <input className="col-span-2 econ-inp" placeholder="auto" value={r.base_hourly_wage ?? ""} onChange={(e) => setField(r.id, "base_hourly_wage", e.target.value)} data-testid={`econ-wage-${r.id}`} />
                            <div className="col-span-2 flex gap-1">
                                <input className="econ-inp w-full" value={r.opening_hours.open} onChange={(e) => setField(r.id, "opening_hours", { ...r.opening_hours, open: e.target.value })} data-testid={`econ-open-${r.id}`} />
                                <input className="econ-inp w-full" value={r.opening_hours.close} onChange={(e) => setField(r.id, "opening_hours", { ...r.opening_hours, close: e.target.value })} data-testid={`econ-close-${r.id}`} />
                            </div>
                            <div className="col-span-1"><KButton variant="green" className="!px-2 !py-1 !text-[10px]" onClick={() => save(r)} data-testid={`econ-save-${r.id}`}>Save</KButton></div>
                        </div>
                    ))}
                </div>
            </Panel>
            <style>{`.econ-inp{background:#050505;border:1px solid rgba(255,255,255,.12);border-radius:3px;padding:4px 6px;font-family:monospace;font-size:12px;color:#7CFFCB;outline:none}.econ-inp:focus{border-color:rgba(0,243,255,.6)}`}</style>
        </div>
    );
}

const TUNE_FIELDS = [
    { section: "Timers (in-game days)", keys: [["upgrade_days", "Upgrade duration"], ["marketing_days", "Marketing duration"], ["raise_cooldown_days", "Wage-raise cooldown"]] },
    { section: "Multiplier ranges", keys: [["satisfaction_mult_min", "Satisfaction→Production min"], ["satisfaction_mult_max", "Satisfaction→Production max"], ["reputation_mult_min", "Reputation→Demand min"], ["reputation_mult_max", "Reputation→Demand max"], ["worker_cond_min", "Worker condition min"], ["worker_cond_max", "Worker condition max"]] },
    { section: "Effectiveness → Accidents", keys: [["accident_eff_threshold", "Injury effectiveness threshold"], ["accident_chance", "Injury chance below threshold"]] },
    { section: "Stock Market (per real hour)", keys: [["stock_drift", "Base return / hr (e.g. 0.0015)"], ["stock_volatility", "Volatility / hr (e.g. 0.03)"]] },
    { section: "Crypto Market (per real hour)", keys: [["crypto_drift", "Base return / hr (e.g. 0.004)"], ["crypto_volatility", "Volatility / hr (e.g. 0.09)"]] },
    { section: "Player Progression", keys: [["skill_decay_per_hour", "Skill Decay Rate (XP/hr idle, 0 = off)"]] },
    { section: "Criminal Suspicion", keys: [["suspicion_decay_per_hour", "Suspicion Decay Rate (/hr clean, 0 = never)"], ["suspicion_gain_mult", "Suspicion Gain Multiplier (x illegal acts)"]] },
];

function TuningPanel() {
    const [cfg, setCfg] = useState(null);
    const [t, setT] = useState(null);
    const load = () => api.get("/admin/config").then(({ data }) => { setCfg(data); setT(data.tuning || {}); });
    useEffect(() => { load(); }, []);
    const setK = (k, v) => setT((o) => ({ ...o, [k]: v }));
    const setBracket = (i, field, v) => setT((o) => {
        const b = (o.tax_brackets || []).map((x) => [...x]);
        b[i][field] = field === 0 ? (v === "" ? null : Number(v)) : Number(v);
        return { ...o, tax_brackets: b };
    });
    const save = async () => {
        const clean = {};
        Object.entries(t).forEach(([k, v]) => { clean[k] = k === "tax_brackets" ? v.map((x) => [x[0] === null || x[0] === "" ? null : Number(x[0]), Number(x[1])]) : Number(v); });
        try { await api.put("/admin/config", { tuning: clean }); toast.success("Tuning saved — live on next tick"); load(); }
        catch (e) { toast.error(errMessage(e)); }
    };
    if (!t) return <Spinner />;
    return (
        <div className="space-y-4">
            {TUNE_FIELDS.map((grp) => (
                <Panel key={grp.section} className="p-5">
                    <div className="font-display font-bold text-white mb-3">{grp.section}</div>
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {grp.keys.map(([k, label]) => (
                            <label key={k} className="text-[11px] text-muted-foreground flex flex-col gap-1">{label}
                                <KInput type="number" step="0.01" value={t[k] ?? ""} onChange={(e) => setK(k, e.target.value)} testid={`tune-${k}`} />
                            </label>
                        ))}
                    </div>
                </Panel>
            ))}
            <Panel className="p-5">
                <div className="font-display font-bold text-white mb-1">Income Tax Brackets</div>
                <p className="text-[11px] text-muted-foreground mb-3">Progressive rate applied to each job shift's gross pay. "Up to" empty = top bracket.</p>
                <div className="space-y-2">
                    {(t.tax_brackets || []).map((b, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs" data-testid={`tax-bracket-${i}`}>
                            <span className="text-muted-foreground w-14">Up to $</span>
                            <KInput type="number" value={b[0] ?? ""} placeholder="∞ (top)" onChange={(e) => setBracket(i, 0, e.target.value)} testid={`tax-upto-${i}`} />
                            <span className="text-muted-foreground">rate</span>
                            <KInput type="number" step="0.01" value={b[1]} onChange={(e) => setBracket(i, 1, e.target.value)} testid={`tax-rate-${i}`} />
                            <span className="text-muted-foreground">= {Math.round((b[1] || 0) * 100)}%</span>
                        </div>
                    ))}
                </div>
            </Panel>
            <KButton variant="green" onClick={save} data-testid="save-tuning">Save Tuning</KButton>
        </div>
    );
}

function PlayersTable({ focus, onFocusHandled }) {
    const [players, setPlayers] = useState(null);
    const [edit, setEdit] = useState(null);
    const [search, setSearch] = useState("");
    const [highlightId, setHighlightId] = useState(null);
    const load = () => api.get("/admin/players").then(({ data }) => setPlayers(data));
    useEffect(() => { load(); }, []);

    // Quick-Jump from the Live City Feed: filter to the player, highlight + open edit.
    useEffect(() => {
        if (!focus || !players) return;
        setSearch(focus.name || "");
        const target = players.find((p) => p.id === focus.id);
        if (target) {
            setEdit({ ...target });
            setHighlightId(target.id);
        } else {
            toast.error(`Player "${focus.name}" not found`);
        }
        onFocusHandled && onFocusHandled();
    }, [focus, players]); // eslint-disable-line react-hooks/exhaustive-deps

    const save = async () => {
        try {
            await api.put(`/admin/players/${edit.id}`, {
                cash: Number(edit.cash), bank: Number(edit.bank), debt: Number(edit.debt),
                reputation: Number(edit.reputation), legal_reputation: Number(edit.legal_reputation),
                criminal_suspicion: Number(edit.criminal_suspicion), social_status: Number(edit.social_status),
                health: Number(edit.health), energy: Number(edit.energy),
            });
            toast.success(`${edit.name} updated`); setEdit(null); load();
        } catch (e) { toast.error(errMessage(e)); }
    };
    if (!players) return <Spinner />;
    const q = search.trim().toLowerCase();
    const shown = q ? players.filter((p) => (p.name || "").toLowerCase().includes(q)) : players;
    return (
        <Panel className="p-0 overflow-hidden">
            <div className="p-3 border-b border-white/8 bg-[#050505] flex items-center gap-2">
                <Search className="w-4 h-4 text-muted-foreground shrink-0" />
                <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search players by name…"
                    className="bg-transparent flex-1 text-sm text-white placeholder:text-muted-foreground/50 outline-none" data-testid="player-search" />
                {search && <button onClick={() => { setSearch(""); setHighlightId(null); }} className="text-muted-foreground hover:text-white" data-testid="player-search-clear"><X className="w-4 h-4" /></button>}
                <span className="font-mono text-[10px] text-muted-foreground shrink-0">{shown.length}/{players.length}</span>
            </div>
            <div className="grid grid-cols-12 gap-2 px-4 py-3 border-b border-white/8 bg-[#050505] font-mono text-[10px] uppercase text-muted-foreground">
                <div className="col-span-3">Name</div><div className="col-span-1">Lvl</div><div className="col-span-2 text-right">Cash</div>
                <div className="col-span-2 text-right">Net Worth</div><div className="col-span-1 text-right">Rep</div><div className="col-span-1 text-right">Legal</div>
                <div className="col-span-1 text-right">Susp</div><div className="col-span-1"></div>
            </div>
            <div className="max-h-[58vh] overflow-y-auto">
            {shown.map((p) => (
                <div key={p.id} className={cn("grid grid-cols-12 gap-2 px-4 py-2.5 border-b border-white/5 text-sm items-center transition-colors",
                    highlightId === p.id ? "bg-neon-cyan/10 ring-1 ring-inset ring-neon-cyan/40" : "")} data-testid={`admin-player-${p.id}`}>
                    <div className="col-span-3 text-white truncate">{p.name}</div>
                    <div className="col-span-1 font-mono tnum">{p.level}</div>
                    <div className="col-span-2 text-right font-mono"><Money value={p.cash} /></div>
                    <div className="col-span-2 text-right font-mono"><Money value={p.net_worth} /></div>
                    <div className="col-span-1 text-right font-mono tnum text-muted-foreground">{Math.round(p.reputation)}</div>
                    <div className="col-span-1 text-right font-mono tnum text-neon-yellow">{Math.round(p.legal_reputation ?? 0)}</div>
                    <div className="col-span-1 text-right font-mono tnum text-neon-red">{Math.round(p.criminal_suspicion ?? 0)}</div>
                    <div className="col-span-1 text-right"><KButton variant="ghost" className="!px-2 !py-1 !text-[10px]" onClick={() => setEdit({ ...p })} data-testid={`edit-player-${p.id}`}>Edit</KButton></div>
                </div>
            ))}
            {shown.length === 0 && <div className="px-4 py-6 text-center text-sm text-muted-foreground">No players match "{search}".</div>}
            </div>
            {edit && (
                <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={() => setEdit(null)}>
                    <Panel className="p-5 w-full max-w-md" onClick={(e) => e.stopPropagation()} data-testid="player-edit-modal">
                        <div className="flex items-center justify-between mb-3"><div className="font-display font-bold text-white">Edit {edit.name}</div><button onClick={() => setEdit(null)}><X className="w-4 h-4 text-muted-foreground" /></button></div>
                        <div className="grid grid-cols-2 gap-3">
                            {[["cash", "Cash"], ["bank", "Bank"], ["debt", "Debt"], ["reputation", "Reputation"], ["legal_reputation", "Legal Standing"], ["criminal_suspicion", "Criminal Suspicion"], ["social_status", "Social Status"], ["health", "Health"], ["energy", "Energy"]].map(([k, label]) => (
                                <label key={k} className="text-[11px] text-muted-foreground flex flex-col gap-1">{label}
                                    <KInput type="number" value={edit[k] ?? 0} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })} testid={`edit-${k}`} />
                                </label>
                            ))}
                        </div>
                        <KButton variant="green" className="w-full mt-4" onClick={save} data-testid="save-player">Save Player</KButton>
                    </Panel>
                </div>
            )}
        </Panel>
    );
}

function StatsView() {
    const [stats, setStats] = useState(null);
    useEffect(() => { api.get("/admin/stats").then(({ data }) => setStats(data)); }, []);
    if (!stats) return <Spinner />;
    return (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
            {Object.entries(stats).map(([k, v]) => (
                <Panel key={k} className="p-4"><div className="text-[11px] uppercase text-muted-foreground">{k}</div><div className="font-display text-2xl text-neon-cyan tnum">{v}</div></Panel>
            ))}
        </div>
    );
}

function emptyLoc() {
    return { name: "", category: "bar", desc: "", icon: "MapPin", money_cost: 0, duration_minutes: 60,
        cooldown_minutes: 120, requires_job: false, suspicion_gain: 0, success_base: 0.72, charisma_factor: 0.3,
        active: true, order: 50, npcs: [], include_filtered: false, category_whitelist: [], min_attrs: {}, max_attrs: {}, filter_weight: 1 };
}

function AttrRow({ label, attrs, options, onChange }) {
    const set = (attr, v) => {
        const next = { ...attrs };
        if (v === "" || v === null) delete next[attr];
        else next[attr] = Number(v);
        onChange(next);
    };
    return (
        <div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">{label}</div>
            <div className="grid grid-cols-3 gap-2">
                {options.map((attr) => (
                    <label key={attr} className="text-[10px] text-muted-foreground flex flex-col gap-1">
                        {attr.replace("_", " ")}
                        <KInput type="number" value={attrs[attr] ?? ""} placeholder="—"
                            onChange={(e) => set(attr, e.target.value)} testid={`${label.toLowerCase().includes("min") ? "min" : "max"}-${attr}`} />
                    </label>
                ))}
            </div>
        </div>
    );
}

function LocationEditor({ draft, setDraft, archetypes, tagOptions, attrOptions, onSave, onCancel, saving }) {
    const set = (k, v) => setDraft((d) => ({ ...d, [k]: v }));
    const setNpc = (i, k, v) => setDraft((d) => { const n = d.npcs.map((x) => ({ ...x })); n[i][k] = v; return { ...d, npcs: n }; });
    const addNpc = () => setDraft((d) => ({ ...d, npcs: [...d.npcs, { archetype_id: archetypes[0]?.id || "", weight: 1 }] }));
    const delNpc = (i) => setDraft((d) => ({ ...d, npcs: d.npcs.filter((_, j) => j !== i) }));
    const toggleTag = (t) => setDraft((d) => {
        const cur = d.category_whitelist || [];
        return { ...d, category_whitelist: cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t] };
    });
    const total = draft.npcs.reduce((s, n) => s + (Number(n.weight) > 0 ? Number(n.weight) : 0), 0) || 1;
    return (
        <Panel className="p-5 space-y-3 border-neon-cyan/30" data-testid="location-editor">
            <div className="grid sm:grid-cols-2 gap-3">
                <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Name
                    <KInput value={draft.name} onChange={(e) => set("name", e.target.value)} testid="loc-name" /></label>
                <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Category
                    <KInput value={draft.category} onChange={(e) => set("category", e.target.value)} testid="loc-category" /></label>
            </div>
            <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Description
                <KInput value={draft.desc} onChange={(e) => set("desc", e.target.value)} testid="loc-desc" /></label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Cost $
                    <KInput type="number" value={draft.money_cost} onChange={(e) => set("money_cost", Number(e.target.value))} testid="loc-cost" /></label>
                <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Duration (min)
                    <KInput type="number" value={draft.duration_minutes} onChange={(e) => set("duration_minutes", Number(e.target.value))} testid="loc-duration" /></label>
                <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Cooldown (min)
                    <KInput type="number" value={draft.cooldown_minutes} onChange={(e) => set("cooldown_minutes", Number(e.target.value))} testid="loc-cooldown" /></label>
                <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Order
                    <KInput type="number" value={draft.order} onChange={(e) => set("order", Number(e.target.value))} testid="loc-order" /></label>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 items-end">
                <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Success base
                    <KInput type="number" step="0.01" value={draft.success_base} onChange={(e) => set("success_base", Number(e.target.value))} testid="loc-success" /></label>
                <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Suspicion gain
                    <KInput type="number" step="0.5" value={draft.suspicion_gain} onChange={(e) => set("suspicion_gain", Number(e.target.value))} testid="loc-suspicion" /></label>
                <label className="text-[11px] text-muted-foreground flex items-center gap-2 mt-4">
                    <input type="checkbox" checked={!!draft.requires_job} onChange={(e) => set("requires_job", e.target.checked)} data-testid="loc-requires-job" /> Requires job</label>
                <label className="text-[11px] text-muted-foreground flex items-center gap-2 mt-4">
                    <input type="checkbox" checked={!!draft.active} onChange={(e) => set("active", e.target.checked)} data-testid="loc-active" /> Active</label>
            </div>

            {/* NPC FILTERS */}
            <div className="border-t border-white/10 pt-3 space-y-3">
                <label className="text-[11px] text-white flex items-center gap-2 font-medium">
                    <input type="checkbox" checked={!!draft.include_filtered} onChange={(e) => set("include_filtered", e.target.checked)} data-testid="loc-include-filtered" />
                    Auto-include NPCs matching filters (in addition to manual)
                </label>
                {draft.include_filtered && (
                    <div className="space-y-3 pl-1">
                        <div>
                            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Category whitelist (empty = any)</div>
                            <div className="flex flex-wrap gap-1.5">
                                {tagOptions.map((t) => {
                                    const on = (draft.category_whitelist || []).includes(t);
                                    return (
                                        <button key={t} onClick={() => toggleTag(t)} data-testid={`tag-${t}`}
                                            className={cn("text-[10px] font-mono px-2 py-1 rounded-sm border transition-colors",
                                                on ? "bg-neon-cyan/20 border-neon-cyan text-neon-cyan" : "border-white/15 text-muted-foreground hover:border-white/40")}>
                                            {t}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                        <div className="grid sm:grid-cols-2 gap-3">
                            <AttrRow label="Min attribute" attrs={draft.min_attrs || {}} options={attrOptions} onChange={(v) => set("min_attrs", v)} />
                            <AttrRow label="Max attribute" attrs={draft.max_attrs || {}} options={attrOptions} onChange={(v) => set("max_attrs", v)} />
                        </div>
                        <label className="text-[11px] text-muted-foreground flex flex-col gap-1 w-32">Filter weight
                            <KInput type="number" step="0.1" value={draft.filter_weight} onChange={(e) => set("filter_weight", Number(e.target.value))} testid="loc-filter-weight" /></label>
                    </div>
                )}
            </div>

            <div className="border-t border-white/10 pt-3">
                <div className="flex items-center justify-between mb-2">
                    <span className="font-display font-bold text-white text-sm">Manually assigned NPCs (bypass filters)</span>
                    <KButton variant="ghost" onClick={addNpc} data-testid="loc-add-npc"><Plus className="w-3.5 h-3.5" /> Add NPC</KButton>
                </div>
                {draft.npcs.length === 0 && <div className="text-[11px] text-muted-foreground">No manual NPCs. {draft.include_filtered ? "The pool comes from the filters above." : "Nobody can be met here — assign NPCs or enable filters."}</div>}
                <div className="space-y-2">
                    {draft.npcs.map((n, i) => (
                        <div key={i} className="flex items-center gap-2" data-testid={`loc-npc-row-${i}`}>
                            <select value={n.archetype_id} onChange={(e) => setNpc(i, "archetype_id", e.target.value)} data-testid={`loc-npc-select-${i}`}
                                className="flex-1 bg-black/40 border border-white/15 rounded-sm px-2 py-1.5 text-xs text-white">
                                {archetypes.map((a) => <option key={a.id} value={a.id}>{a.label} [{(a.tags || []).join(",")}]</option>)}
                            </select>
                            <div className="w-24"><KInput type="number" step="0.1" value={n.weight} onChange={(e) => setNpc(i, "weight", Number(e.target.value))} testid={`loc-npc-weight-${i}`} /></div>
                            <span className="w-14 text-right font-mono text-[11px] text-neon-cyan" data-testid={`loc-npc-chance-${i}`}>
                                {Math.round((Number(n.weight) > 0 ? Number(n.weight) : 0) / total * 100)}%
                            </span>
                            <button onClick={() => delNpc(i)} className="text-neon-red hover:text-neon-red/70" data-testid={`loc-npc-del-${i}`}><Trash2 className="w-4 h-4" /></button>
                        </div>
                    ))}
                </div>
            </div>

            <div className="flex gap-2 pt-2">
                <KButton variant="green" loading={saving} disabled={!draft.name} onClick={onSave} data-testid="loc-save">Save Location</KButton>
                <KButton variant="ghost" onClick={onCancel} data-testid="loc-cancel">Cancel</KButton>
            </div>
        </Panel>
    );
}

function LocationsPanel() {
    const [data, setData] = useState(null);
    const [draft, setDraft] = useState(null);
    const [saving, setSaving] = useState(false);
    const load = useCallback(() => api.get("/admin/locations").then(({ data }) => setData(data)).catch(() => setData({ locations: [], archetypes: [] })), []);
    useEffect(() => { load(); }, [load]);

    const save = async () => {
        setSaving(true);
        try {
            const { id, encounters, _id, ...body } = draft;
            if (id) await api.put(`/admin/locations/${id}`, body);
            else await api.post("/admin/locations", body);
            toast.success("Location saved — live immediately");
            setDraft(null); await load();
        } catch (e) { toast.error(errMessage(e)); }
        setSaving(false);
    };
    const del = async (l) => {
        if (!window.confirm(`Delete "${l.name}"?`)) return;
        try { await api.delete(`/admin/locations/${l.id}`); toast.success("Deleted"); await load(); }
        catch (e) { toast.error(errMessage(e)); }
    };

    if (!data) return <Spinner />;
    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">Meeting places players can visit. Assign NPCs and set their meeting chance (weights auto-normalize to %).</p>
                {!draft && <KButton variant="green" onClick={() => setDraft(emptyLoc())} data-testid="loc-new"><Plus className="w-4 h-4" /> New Location</KButton>}
            </div>

            {draft && <LocationEditor draft={draft} setDraft={setDraft} archetypes={data.archetypes} tagOptions={data.tag_options || []} attrOptions={data.attr_options || []} onSave={save} onCancel={() => setDraft(null)} saving={saving} />}

            {!draft && (
                <div className="grid md:grid-cols-2 gap-3">
                    {data.locations.map((l) => (
                        <Panel key={l.id} className="p-4" data-testid={`admin-location-${l.id}`}>
                            <div className="flex items-start justify-between mb-1">
                                <div>
                                    <span className="font-display font-bold text-white">{l.name}</span>
                                    <span className="ml-2 text-[10px] uppercase text-muted-foreground font-mono">{l.category}</span>
                                    {!l.active && <Pill tone="red" className="ml-2">Inactive</Pill>}
                                    {l.requires_job && <Pill tone="yellow" className="ml-2">Needs job</Pill>}
                                </div>
                                <div className="flex gap-1">
                                    <button onClick={() => setDraft(JSON.parse(JSON.stringify(l)))} className="text-muted-foreground hover:text-white" data-testid={`loc-edit-${l.id}`}><Pencil className="w-4 h-4" /></button>
                                    <button onClick={() => del(l)} className="text-neon-red hover:text-neon-red/70" data-testid={`loc-del-${l.id}`}><Trash2 className="w-4 h-4" /></button>
                                </div>
                            </div>
                            <p className="text-[11px] text-muted-foreground mb-2">{l.desc}</p>
                            <div className="text-[10px] font-mono text-muted-foreground mb-2">${l.money_cost} · {l.duration_minutes}min · CD {l.cooldown_minutes}min{l.suspicion_gain ? ` · +${l.suspicion_gain} suspicion` : ""}</div>
                            {l.include_filtered && (
                                <div className="text-[10px] font-mono text-neon-purple/90 mb-2" data-testid={`filter-info-${l.id}`}>
                                    Filters: {(l.category_whitelist || []).length ? l.category_whitelist.join("/") : "any"}
                                    {Object.keys(l.min_attrs || {}).length ? ` · min ${Object.entries(l.min_attrs).map(([k, v]) => `${k}≥${v}`).join(", ")}` : ""}
                                    {Object.keys(l.max_attrs || {}).length ? ` · max ${Object.entries(l.max_attrs).map(([k, v]) => `${k}≤${v}`).join(", ")}` : ""}
                                </div>
                            )}
                            <div className="flex flex-wrap gap-1" data-testid={`admin-encounters-${l.id}`}>
                                {l.encounters.map((e) => (
                                    <span key={e.archetype_id} className={cn("font-mono text-[10px] px-1.5 py-0.5 rounded-sm border",
                                        e.source === "filter" ? "border-neon-purple/30 text-neon-purple/90" : "border-neon-cyan/25 text-neon-cyan/90")}>
                                        {e.label} <span className="text-white">{Math.round(e.chance * 100)}%</span>{e.source === "filter" ? "*" : ""}
                                    </span>
                                ))}
                                {l.encounters.length === 0 && <span className="text-[10px] text-neon-red font-mono">No NPCs assigned</span>}
                            </div>
                        </Panel>
                    ))}
                </div>
            )}
        </div>
    );
}

function CityShopsPanel() {
    const [data, setData] = useState(null);
    const [draft, setDraft] = useState(null);
    const [saving, setSaving] = useState(false);
    const load = useCallback(() => api.get("/admin/city-shops").then(({ data }) => setData(data)).catch(() => setData({ shops: [], category_options: [], business_types: [], locations: [], items_by_category: {}, default_capacity: 25 })), []);
    useEffect(() => { load(); }, [load]);

    const defCap = data?.default_capacity || 25;
    const emptyShop = () => ({ name: "", category: data?.category_options?.[0] || "grocery", desc: "", icon: "Store", business_type_id: "", location_id: "", active: true, order: 50, opening_hours: { open: "08:00", close: "20:00" }, items_config: {} });
    const set = (k, v) => setDraft((d) => ({ ...d, [k]: v }));
    const setHours = (k, v) => setDraft((d) => ({ ...d, opening_hours: { ...(d.opening_hours || {}), [k]: v } }));
    const setItemCfg = (iid, k, v) => setDraft((d) => {
        const ic = { ...(d.items_config || {}) };
        const cur = { capacity: defCap, discount_pct: 0, ...(ic[iid] || {}) };
        ic[iid] = { ...cur, [k]: v };
        return { ...d, items_config: ic };
    });
    const save = async () => {
        setSaving(true);
        try {
            const body = {
                name: draft.name, category: draft.category, desc: draft.desc || "",
                icon: draft.icon || "Store",
                business_type_id: draft.business_type_id || null,
                location_id: draft.location_id || null,
                active: !!draft.active, order: Number(draft.order) || 50,
                opening_hours: { open: draft.opening_hours?.open || "08:00", close: draft.opening_hours?.close || "20:00" },
                items_config: draft.items_config || {},
            };
            if (draft.id) await api.put(`/admin/city-shops/${draft.id}`, body);
            else await api.post("/admin/city-shops", body);
            toast.success("Shop saved — live in the Shop tab immediately (stock restocks to new capacity)");
            setDraft(null); await load();
        } catch (e) { toast.error(errMessage(e)); }
        setSaving(false);
    };
    const del = async (s) => { if (!window.confirm(`Delete "${s.name}"?`)) return; try { await api.delete(`/admin/city-shops/${s.id}`); toast.success("Deleted"); await load(); } catch (e) { toast.error(errMessage(e)); } };
    const editShop = (s) => setDraft({ ...s, opening_hours: s.opening_hours || { open: "08:00", close: "20:00" }, items_config: s.items_config || {} });

    if (!data) return <Spinner />;
    const catItems = (data.items_by_category || {})[draft?.category] || [];
    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">City shops the players browse. Set the item Category (the shop sells only items of that category), the Opening Hours (players can only buy while OPEN), and per-item daily Stock + optional Discount for sale events. Stock restocks to capacity at game midnight.</p>
                {!draft && <KButton variant="green" onClick={() => setDraft(emptyShop())} data-testid="shop-new"><Plus className="w-4 h-4" /> New Shop</KButton>}
            </div>

            {draft && (
                <Panel className="p-5 space-y-3 border-neon-cyan/30" data-testid="cityshop-editor">
                    <div className="grid sm:grid-cols-2 gap-3">
                        <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Shop name
                            <KInput value={draft.name} onChange={(e) => set("name", e.target.value)} testid="shop-name" /></label>
                        <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Item category
                            <select value={draft.category} onChange={(e) => set("category", e.target.value)} data-testid="shop-category"
                                className="bg-black/40 border border-white/15 rounded-sm px-2 py-2 text-xs text-white">
                                {data.category_options.map((c) => <option key={c} value={c}>{c}</option>)}
                            </select></label>
                    </div>
                    <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Description
                        <KInput value={draft.desc} onChange={(e) => set("desc", e.target.value)} testid="shop-desc" /></label>
                    <div className="grid sm:grid-cols-3 gap-3 items-end">
                        <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Link business type (optional)
                            <select value={draft.business_type_id || ""} onChange={(e) => set("business_type_id", e.target.value)} data-testid="shop-biztype"
                                className="bg-black/40 border border-white/15 rounded-sm px-2 py-2 text-xs text-white">
                                <option value="">— none —</option>
                                {data.business_types.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
                            </select></label>
                        <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Link location (optional)
                            <select value={draft.location_id || ""} onChange={(e) => set("location_id", e.target.value)} data-testid="shop-location"
                                className="bg-black/40 border border-white/15 rounded-sm px-2 py-2 text-xs text-white">
                                <option value="">— none —</option>
                                {data.locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                            </select></label>
                        <div className="flex items-center gap-4">
                            <label className="text-[11px] text-muted-foreground flex flex-col gap-1 w-20">Order
                                <KInput type="number" value={draft.order} onChange={(e) => set("order", Number(e.target.value))} testid="shop-order" /></label>
                            <label className="text-[11px] text-muted-foreground flex items-center gap-2 mt-4">
                                <input type="checkbox" checked={!!draft.active} onChange={(e) => set("active", e.target.checked)} data-testid="shop-active" /> Active</label>
                        </div>
                    </div>

                    <div className="grid sm:grid-cols-2 gap-3 pt-1">
                        <label className="text-[11px] text-muted-foreground flex flex-col gap-1"><Clock className="w-3 h-3 inline mr-1" />Opens
                            <KInput type="time" value={draft.opening_hours?.open || "08:00"} onChange={(e) => setHours("open", e.target.value)} testid="shop-open-time" /></label>
                        <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Closes <span className="text-muted-foreground/50">(use 24:00 for round-the-clock)</span>
                            <KInput type="time" value={(draft.opening_hours?.close === "24:00" ? "00:00" : draft.opening_hours?.close) || "20:00"} onChange={(e) => setHours("close", e.target.value)} testid="shop-close-time" /></label>
                    </div>

                    <div className="pt-2">
                        <div className="text-[11px] font-mono uppercase tracking-wider text-neon-cyan/80 mb-2">Stock & Discounts ({draft.category})</div>
                        {catItems.length === 0 ? (
                            <p className="text-[11px] text-muted-foreground">No items in this category yet. Add items with store_type "{draft.category}" in the Items tab.</p>
                        ) : (
                            <div className="space-y-2" data-testid="shop-items-config">
                                <div className="grid grid-cols-[1fr_auto_auto] gap-3 text-[10px] font-mono uppercase tracking-wider text-muted-foreground/60 px-1">
                                    <span>Item</span><span className="w-24 text-center">Daily stock</span><span className="w-24 text-center">Discount %</span>
                                </div>
                                {catItems.map((it) => {
                                    const c = draft.items_config?.[it.id] || {};
                                    return (
                                        <div key={it.id} className="grid grid-cols-[1fr_auto_auto] gap-3 items-center" data-testid={`shop-itemcfg-${it.id}`}>
                                            <div className="min-w-0">
                                                <span className="text-xs text-white">{it.name}</span>
                                                <span className="ml-2 text-[10px] font-mono text-muted-foreground">${it.base_price}</span>
                                            </div>
                                            <KInput type="number" className="w-24" value={c.capacity ?? defCap} onChange={(e) => setItemCfg(it.id, "capacity", Math.max(0, Number(e.target.value)))} testid={`cfg-cap-${it.id}`} />
                                            <KInput type="number" className="w-24" value={c.discount_pct ?? 0} onChange={(e) => setItemCfg(it.id, "discount_pct", Math.max(0, Math.min(95, Number(e.target.value))))} testid={`cfg-disc-${it.id}`} />
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    <div className="flex gap-2 pt-2">
                        <KButton variant="green" loading={saving} disabled={!draft.name} onClick={save} data-testid="shop-save">Save Shop</KButton>
                        <KButton variant="ghost" onClick={() => setDraft(null)} data-testid="shop-cancel">Cancel</KButton>
                    </div>
                </Panel>
            )}

            {!draft && (
                <div className="grid md:grid-cols-2 gap-3">
                    {data.shops.map((s) => (
                        <Panel key={s.id} className="p-4" data-testid={`admin-shop-${s.id}`}>
                            <div className="flex items-start justify-between mb-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <span className="font-display font-bold text-white">{s.name}</span>
                                    <span className="text-[10px] uppercase text-neon-cyan/80 font-mono">{s.category}</span>
                                    <Pill tone={s.is_open_now ? "green" : "red"} className="!text-[9px]">{s.is_open_now ? "Open" : "Closed"}</Pill>
                                    {!s.active && <Pill tone="red">Inactive</Pill>}
                                </div>
                                <div className="flex gap-1">
                                    <button onClick={() => editShop(s)} className="text-muted-foreground hover:text-white" data-testid={`shop-edit-${s.id}`}><Pencil className="w-4 h-4" /></button>
                                    <button onClick={() => del(s)} className="text-neon-red hover:text-neon-red/70" data-testid={`shop-del-${s.id}`}><Trash2 className="w-4 h-4" /></button>
                                </div>
                            </div>
                            <p className="text-[11px] text-muted-foreground mb-2">{s.desc}</p>
                            <div className="text-[10px] font-mono text-muted-foreground flex items-center gap-1.5 flex-wrap">
                                <span><Clock className="w-2.5 h-2.5 inline mr-0.5" />{s.opening_hours?.open}–{s.opening_hours?.close}</span>
                                <span>·</span>
                                <span>{s.item_count} items</span>
                                {s.business_type_name ? <><span>·</span><span>linked to {s.business_type_name}</span></> : null}
                            </div>
                        </Panel>
                    ))}
                </div>
            )}
        </div>
    );
}

const SECTOR_ICON_OPTIONS = ["Briefcase", "ShoppingBag", "UtensilsCrossed", "Truck", "Building2", "Wrench", "Shield", "Landmark"];

function JobSectorsPanel() {
    const [data, setData] = useState(null);
    const [draft, setDraft] = useState(null);
    const [saving, setSaving] = useState(false);
    const load = useCallback(() => api.get("/admin/job-sectors").then(({ data }) => setData(data)).catch(() => setData({ sectors: [], jobs: [], assigned: {} })), []);
    useEffect(() => { load(); }, [load]);

    const emptySector = () => ({ name: "", desc: "", icon: "Briefcase", active: true, order: 50, job_ids: [] });
    const set = (k, v) => setDraft((d) => ({ ...d, [k]: v }));
    const toggleJob = (jid) => setDraft((d) => {
        const has = (d.job_ids || []).includes(jid);
        return { ...d, job_ids: has ? d.job_ids.filter((x) => x !== jid) : [...(d.job_ids || []), jid] };
    });
    const save = async () => {
        setSaving(true);
        try {
            const body = {
                name: draft.name, desc: draft.desc || "", icon: draft.icon || "Briefcase",
                active: !!draft.active, order: Number(draft.order) || 50, job_ids: draft.job_ids || [],
            };
            if (draft.id) await api.put(`/admin/job-sectors/${draft.id}`, body);
            else await api.post("/admin/job-sectors", body);
            toast.success("Sector saved — live in the Job Center immediately");
            setDraft(null); await load();
        } catch (e) { toast.error(errMessage(e)); }
        setSaving(false);
    };
    const del = async (s) => { if (!window.confirm(`Delete "${s.name}"?`)) return; try { await api.delete(`/admin/job-sectors/${s.id}`); toast.success("Deleted"); await load(); } catch (e) { toast.error(errMessage(e)); } };
    const editSector = (s) => setDraft({ ...s, job_ids: [...(s.job_ids || [])] });

    if (!data) return <Spinner />;
    // which sector each job is currently assigned to (excluding the one being edited)
    const otherAssigned = {};
    (data.sectors || []).forEach((s) => { if (!draft || s.id !== draft.id) (s.job_ids || []).forEach((jid) => { otherAssigned[jid] = s.name; }); });

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">Job sectors / agencies the players browse in the Job Center. Create sectors, then assign jobs to them. A job assigned here shows only under its sector. Any job left unassigned appears under a "General Listings" fallback so nothing is unreachable.</p>
                {!draft && <KButton variant="green" onClick={() => setDraft(emptySector())} data-testid="sector-new"><Plus className="w-4 h-4" /> New Sector</KButton>}
            </div>

            {draft && (
                <Panel className="p-5 space-y-3 border-neon-cyan/30" data-testid="jobsector-editor">
                    <div className="grid sm:grid-cols-2 gap-3">
                        <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Sector name
                            <KInput value={draft.name} onChange={(e) => set("name", e.target.value)} testid="sector-name" /></label>
                        <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Icon
                            <select value={draft.icon} onChange={(e) => set("icon", e.target.value)} data-testid="sector-icon"
                                className="bg-black/40 border border-white/15 rounded-sm px-2 py-2 text-xs text-white">
                                {SECTOR_ICON_OPTIONS.map((c) => <option key={c} value={c}>{c}</option>)}
                            </select></label>
                    </div>
                    <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Description
                        <KInput value={draft.desc} onChange={(e) => set("desc", e.target.value)} testid="sector-desc" /></label>
                    <div className="flex items-center gap-4">
                        <label className="text-[11px] text-muted-foreground flex flex-col gap-1 w-20">Order
                            <KInput type="number" value={draft.order} onChange={(e) => set("order", Number(e.target.value))} testid="sector-order" /></label>
                        <label className="text-[11px] text-muted-foreground flex items-center gap-2 mt-4">
                            <input type="checkbox" checked={!!draft.active} onChange={(e) => set("active", e.target.checked)} data-testid="sector-active" /> Active</label>
                    </div>

                    <div className="pt-2">
                        <div className="text-[11px] font-mono uppercase tracking-wider text-neon-cyan/80 mb-2">Assign Jobs ({(draft.job_ids || []).length} selected)</div>
                        <div className="grid sm:grid-cols-2 gap-1.5 max-h-72 overflow-y-auto pr-1" data-testid="sector-jobs-picker">
                            {data.jobs.map((j) => {
                                const checked = (draft.job_ids || []).includes(j.id);
                                const takenBy = otherAssigned[j.id];
                                return (
                                    <label key={j.id} className={cn("flex items-center gap-2 p-2 border rounded-sm cursor-pointer transition-colors",
                                        checked ? "border-neon-cyan/50 bg-neon-cyan/5" : "border-white/10 hover:border-white/25")} data-testid={`sector-job-${j.id}`}>
                                        <input type="checkbox" checked={checked} onChange={() => toggleJob(j.id)} data-testid={`sector-job-cb-${j.id}`} />
                                        <div className="min-w-0 flex-1">
                                            <span className="text-xs text-white">{j.title}</span>
                                            <span className="ml-1.5 text-[10px] font-mono text-muted-foreground">T{j.tier} · {j.category}</span>
                                            {takenBy && !checked && <span className="block text-[9px] text-neon-yellow/80 font-mono">in {takenBy}</span>}
                                        </div>
                                    </label>
                                );
                            })}
                        </div>
                    </div>

                    <div className="flex gap-2 pt-2">
                        <KButton variant="green" loading={saving} disabled={!draft.name} onClick={save} data-testid="sector-save">Save Sector</KButton>
                        <KButton variant="ghost" onClick={() => setDraft(null)} data-testid="sector-cancel">Cancel</KButton>
                    </div>
                </Panel>
            )}

            {!draft && (
                <div className="grid md:grid-cols-2 gap-3">
                    {data.sectors.map((s) => (
                        <Panel key={s.id} className="p-4" data-testid={`admin-sector-${s.id}`}>
                            <div className="flex items-start justify-between mb-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <span className="font-display font-bold text-white">{s.name}</span>
                                    <span className="text-[10px] uppercase text-neon-cyan/80 font-mono">{s.icon}</span>
                                    {!s.active && <Pill tone="red">Inactive</Pill>}
                                </div>
                                <div className="flex gap-1">
                                    <button onClick={() => editSector(s)} className="text-muted-foreground hover:text-white" data-testid={`sector-edit-${s.id}`}><Pencil className="w-4 h-4" /></button>
                                    <button onClick={() => del(s)} className="text-neon-red hover:text-neon-red/70" data-testid={`sector-del-${s.id}`}><Trash2 className="w-4 h-4" /></button>
                                </div>
                            </div>
                            <p className="text-[11px] text-muted-foreground mb-2">{s.desc}</p>
                            <div className="text-[10px] font-mono text-muted-foreground">{s.job_count} job{s.job_count === 1 ? "" : "s"} assigned</div>
                        </Panel>
                    ))}
                </div>
            )}
        </div>
    );
}


const ADMIN_GROUPS = [
    { key: "overview", label: "Overview", icon: LayoutDashboard, locked: true,
      children: [{ key: "stats", label: "Dashboard" }, { key: "feed", label: "Live Feed" }] },
    { key: "economy", label: "Economy", icon: DollarSign,
      children: [
          { key: "economy", label: "Economy Sandbox" }, { key: "business_types", label: "Businesses" },
          { key: "items", label: "Items" }, { key: "housing", label: "Housing" }, { key: "vehicles", label: "Vehicles" }] },
    { key: "tuning", label: "Gameplay Tuning", icon: Gauge,
      children: [
          { key: "tuning", label: "Tuning" }, { key: "config", label: "Config" }, { key: "actions", label: "Actions" },
          { key: "courses", label: "Courses" }, { key: "jobs", label: "Jobs" }, { key: "random_events", label: "Events" }] },
    { key: "players", label: "Player Management", icon: Users,
      children: [
          { key: "players", label: "Players" }, { key: "employee_roles", label: "Emp Roles" }, { key: "employee_traits", label: "Emp Traits" },
          { key: "staffing_requirements", label: "Staffing" }, { key: "training_options", label: "Training" }, { key: "employee_events", label: "Staff Events" },
          { key: "npc_archetypes", label: "NPC Archetypes" }, { key: "social_traits", label: "Personality" },
          { key: "relationship_actions", label: "Rel. Actions" }, { key: "gift_types", label: "Gifts" }, { key: "social_events", label: "Social Events" }] },
    { key: "city", label: "City Infrastructure", icon: Building2,
      children: [{ key: "cityshops", label: "City Shops" }, { key: "jobsectors", label: "Job Sectors" }, { key: "locations", label: "Locations" }] },
    { key: "underworld", label: "Underworld & Finance", icon: Skull,
      children: [{ key: "illegal_actions", label: "Illegal" }] },
];

const cmoney = (n) => {
    const v = Number(n || 0);
    const a = Math.abs(v);
    const sign = v < 0 ? "-" : "";
    if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(2)}M`;
    if (a >= 1e3) return `${sign}$${(a / 1e3).toFixed(1)}K`;
    return money(v);
};

const ADMIN_SUMMARY = {
    overview: (m) => [
        { label: "Players", value: m.players_total, icon: Users },
        { label: "Employed", value: m.players_employed, icon: Briefcase },
        { label: "Businesses", value: m.businesses_total, icon: Building2 },
        { label: "Active Workers", value: m.active_workers, icon: Activity },
        { label: "Market Value", value: cmoney(m.market_value), icon: TrendingUp },
        { label: "Total Debt", value: cmoney(m.total_debt), icon: Wallet },
    ],
    economy: (m) => [
        { label: "Businesses", value: m.businesses_total, icon: Building2 },
        { label: "Hiring Now", value: m.businesses_hiring, icon: Briefcase },
        { label: "Active Workers", value: m.active_workers, icon: Activity },
        { label: "Market Value", value: cmoney(m.market_value), icon: TrendingUp },
        { label: "Liquidity", value: cmoney(m.total_cash + m.total_bank), icon: DollarSign },
    ],
    tuning: (m) => [
        { label: "Jobs", value: m.jobs_total, icon: Briefcase },
        { label: "Actions", value: m.actions_total, icon: Zap },
        { label: "Courses", value: m.courses_total, icon: GraduationCap },
        { label: "Events", value: m.events_total, icon: Sparkles },
    ],
    players: (m) => [
        { label: "Players", value: m.players_total, icon: Users },
        { label: "Employed", value: m.players_employed, icon: Briefcase },
        { label: "Active Workers", value: m.active_workers, icon: Activity },
        { label: "Avg Net Worth", value: cmoney(m.avg_net_worth), icon: TrendingUp },
    ],
    city: (m) => [
        { label: "City Shops", value: `${m.shops_active}/${m.shops_total}`, icon: Store },
        { label: "Job Sectors", value: m.sectors_total, icon: Briefcase },
        { label: "Locations", value: m.locations_total, icon: MapPin },
    ],
    underworld: (m) => [
        { label: "Illegal Actions", value: m.illegal_total, icon: Skull },
        { label: "Market Assets", value: m.market_assets_total, icon: TrendingUp },
        { label: "Avg Suspicion", value: m.avg_suspicion, icon: Activity },
    ],
};

function renderAdminLeaf(key, ctx = {}) {
    switch (key) {
        case "stats": return <StatsView />;
        case "feed": return <LiveCityFeed onPlayerClick={ctx.onFeedPlayerClick} />;
        case "economy": return <EconomyTuner />;
        case "tuning": return <TuningPanel />;
        case "config": return <ConfigEditor />;
        case "locations": return <LocationsPanel />;
        case "cityshops": return <CityShopsPanel />;
        case "jobsectors": return <JobSectorsPanel />;
        case "players": return <PlayersTable focus={ctx.focusPlayer} onFocusHandled={ctx.onFocusHandled} />;
        default: return <ContentEditor ctype={key} />;
    }
}

const FEED_META = {
    shop: { icon: ShoppingCart, tone: "text-neon-green", border: "border-neon-green/30" },
    job: { icon: Briefcase, tone: "text-neon-cyan", border: "border-neon-cyan/30" },
    business: { icon: Building2, tone: "text-neon-cyan", border: "border-neon-cyan/30" },
    crime: { icon: Skull, tone: "text-neon-red", border: "border-neon-red/30" },
    legal: { icon: Scale, tone: "text-neon-yellow", border: "border-neon-yellow/30" },
    finance: { icon: TrendingUp, tone: "text-neon-purple", border: "border-neon-purple/30" },
    bank: { icon: DollarSign, tone: "text-neon-purple", border: "border-neon-purple/30" },
    social: { icon: Users, tone: "text-neon-purple", border: "border-neon-purple/30" },
    health: { icon: HeartPulse, tone: "text-neon-red", border: "border-neon-red/30" },
    housing: { icon: Home, tone: "text-neon-cyan", border: "border-neon-cyan/30" },
    vehicle: { icon: Car, tone: "text-neon-cyan", border: "border-neon-cyan/30" },
    education: { icon: GraduationCap, tone: "text-neon-cyan", border: "border-neon-cyan/30" },
    action: { icon: Zap, tone: "text-muted-foreground", border: "border-white/15" },
    system: { icon: Sparkles, tone: "text-muted-foreground", border: "border-white/15" },
};

const FEED_FILTERS = [
    { key: "all", label: "All", types: null },
    { key: "shop", label: "Purchases", types: "shop" },
    { key: "work", label: "Work & Hiring", types: "job,business" },
    { key: "crime", label: "Crime & Legal", types: "crime,legal,health" },
    { key: "finance", label: "Finance", types: "finance,bank" },
    { key: "social", label: "Social", types: "social" },
];

const feedTimeAgo = (iso) => {
    const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 60) return `${Math.floor(s)}s ago`;
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
};

function LiveCityFeed({ onPlayerClick }) {
    const [events, setEvents] = useState(null);
    const [filter, setFilter] = useState("all");
    const load = useCallback(() => {
        const f = FEED_FILTERS.find((x) => x.key === filter);
        const qs = f && f.types ? `?limit=50&types=${f.types}` : "?limit=50";
        api.get(`/admin/feed${qs}`).then(({ data }) => setEvents(data)).catch(() => setEvents([]));
    }, [filter]);
    useEffect(() => { load(); }, [load]);
    useEffect(() => { const t = setInterval(load, 6000); return () => clearInterval(t); }, [load]);

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-2">
                    <span className="relative flex h-2.5 w-2.5" data-testid="feed-live-indicator">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-neon-green opacity-75" />
                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-neon-green" />
                    </span>
                    <span className="font-mono text-xs uppercase tracking-wider text-neon-green">Live · auto-refresh 6s</span>
                    <span className="font-mono text-[10px] text-muted-foreground/70 hidden sm:inline">· click a name to jump to the player</span>
                </div>
                <div className="flex flex-wrap gap-1.5" data-testid="feed-filters">
                    {FEED_FILTERS.map((f) => (
                        <button key={f.key} onClick={() => setFilter(f.key)} data-testid={`feed-filter-${f.key}`}
                            className={cn("px-2.5 py-1 text-[11px] font-mono rounded-sm border transition-colors",
                                filter === f.key ? "border-neon-cyan text-neon-cyan bg-neon-cyan/10" : "border-white/12 text-muted-foreground hover:text-white")}>
                            {f.label}
                        </button>
                    ))}
                </div>
            </div>

            {events === null ? <Spinner /> : events.length === 0 ? (
                <Panel className="p-6 text-center text-sm text-muted-foreground">No recent activity for this filter.</Panel>
            ) : (
                <div className="space-y-1.5 max-h-[62vh] overflow-y-auto pr-1" data-testid="live-city-feed">
                    {events.map((e) => {
                        const isDanger = e.severity === "danger";
                        const meta = FEED_META[e.type] || FEED_META.system;
                        const Icon = isDanger ? AlertTriangle : meta.icon;
                        return (
                            <div key={e.id}
                                className={cn("flex items-start gap-3 p-2.5 border rounded-sm",
                                    isDanger ? "danger-pulse bg-[#FF4444]/10 border-[#FF4444]/60" : cn("bg-black/20", meta.border))}
                                data-testid={`feed-event-${e.id}`} data-severity={e.severity}>
                                <div className={cn("w-7 h-7 rounded-sm border flex items-center justify-center shrink-0",
                                    isDanger ? "bg-[#FF4444]/15 border-[#FF4444]/50 text-[#FF4444]" : cn("bg-white/5 border-white/10", meta.tone))}>
                                    <Icon className="w-3.5 h-3.5" />
                                </div>
                                <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-2 flex-wrap">
                                        <button onClick={() => onPlayerClick && onPlayerClick(e.player_id, e.player_name)}
                                            className="font-display font-bold text-white text-xs hover:text-neon-cyan hover:underline underline-offset-2 transition-colors"
                                            data-testid={`feed-player-${e.player_id}`} title="Jump to this player">
                                            {e.player_name}
                                        </button>
                                        <span className={cn("font-mono text-[9px] uppercase tracking-wider", isDanger ? "text-[#FF4444]" : meta.tone)}>{e.type}</span>
                                        {isDanger && <span className="font-mono text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm bg-[#FF4444]/20 text-[#FF4444] border border-[#FF4444]/50" data-testid={`feed-danger-${e.id}`}>Danger</span>}
                                    </div>
                                    <p className={cn("text-[11px] leading-snug", isDanger ? "text-[#FF6666]" : "text-muted-foreground")}>{e.message}</p>
                                </div>
                                <span className="font-mono text-[10px] text-muted-foreground/60 shrink-0 whitespace-nowrap">{feedTimeAgo(e.ts)}</span>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

function SummaryCard({ label, value, icon: Icon }) {
    return (
        <Panel className="p-3 flex items-center gap-3" data-testid={`summary-${label.toLowerCase().replace(/\s+/g, "-")}`}>
            <div className="w-9 h-9 rounded-sm bg-neon-cyan/10 border border-neon-cyan/20 flex items-center justify-center shrink-0">
                <Icon className="w-4 h-4 text-neon-cyan" />
            </div>
            <div className="min-w-0">
                <div className="text-[10px] uppercase font-mono text-muted-foreground tracking-wider leading-tight">{label}</div>
                <div className="font-display font-bold text-white tnum text-lg leading-tight">{value}</div>
            </div>
        </Panel>
    );
}

function SortableMainTab({ g, active, customizing, onSelect }) {
    const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: g.key });
    const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1, zIndex: isDragging ? 20 : "auto" };
    const Icon = g.icon;
    return (
        <div ref={setNodeRef} style={style} className="flex items-center">
            <button onClick={onSelect} data-testid={`admin-group-${g.key}`}
                className={cn("inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-mono uppercase tracking-wider rounded-sm border transition-colors",
                    active ? "border-neon-cyan text-neon-cyan bg-neon-cyan/10" : "border-white/12 text-muted-foreground hover:text-white hover:border-white/25")}>
                {customizing && (
                    <span {...attributes} {...listeners} data-testid={`admin-drag-${g.key}`}
                        className="cursor-grab active:cursor-grabbing text-muted-foreground/60 hover:text-neon-cyan" onClick={(e) => e.stopPropagation()}>
                        <GripVertical className="w-3.5 h-3.5" />
                    </span>
                )}
                <Icon className="w-3.5 h-3.5" />{g.label}
            </button>
        </div>
    );
}

export default function Admin() {
    const [metrics, setMetrics] = useState(null);
    const [order, setOrder] = useState(null);
    const [hidden, setHidden] = useState([]);
    const [activeGroup, setActiveGroup] = useState("overview");
    const [activeLeaf, setActiveLeaf] = useState("stats");
    const [customizing, setCustomizing] = useState(false);
    const [focusPlayer, setFocusPlayer] = useState(null);
    const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

    const byKey = Object.fromEntries(ADMIN_GROUPS.map((g) => [g.key, g]));

    useEffect(() => {
        api.get("/admin/overview").then(({ data }) => setMetrics(data)).catch(() => setMetrics({}));
        api.get("/admin/layout").then(({ data }) => {
            const saved = (data?.order || []).filter((k) => byKey[k]);
            const missing = ADMIN_GROUPS.filter((g) => !saved.includes(g.key)).map((g) => g.key);
            setOrder([...saved, ...missing]);
            setHidden((data?.hidden || []).filter((k) => k !== "overview" && byKey[k]));
        }).catch(() => setOrder(ADMIN_GROUPS.map((g) => g.key)));
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const persist = (o, h) => api.put("/admin/layout", { order: o, hidden: h }).catch(() => {});

    const orderedGroups = (order || ADMIN_GROUPS.map((g) => g.key)).map((k) => byKey[k]).filter(Boolean);
    const visibleGroups = orderedGroups.filter((g) => !hidden.includes(g.key));

    const selectGroup = (gk) => {
        setActiveGroup(gk);
        const g = byKey[gk];
        if (g && g.children[0]) setActiveLeaf(g.children[0].key);
    };

    const onFeedPlayerClick = (playerId, playerName) => {
        setFocusPlayer({ id: playerId, name: playerName });
        setActiveGroup("players");
        setActiveLeaf("players");
    };

    const onDragEnd = ({ active, over }) => {
        if (!over || active.id === over.id) return;
        const next = arrayMove(order, order.indexOf(active.id), order.indexOf(over.id));
        setOrder(next); persist(next, hidden);
    };

    const toggleHidden = (gk) => {
        if (gk === "overview") return;
        const next = hidden.includes(gk) ? hidden.filter((k) => k !== gk) : [...hidden, gk];
        setHidden(next); persist(order, next);
        if (activeGroup === gk && !hidden.includes(gk)) selectGroup("overview");
    };

    const resetLayout = () => {
        const def = ADMIN_GROUPS.map((g) => g.key);
        setOrder(def); setHidden([]); persist(def, []); selectGroup("overview");
    };

    if (!order) return <Spinner />;
    const activeG = byKey[activeGroup] || ADMIN_GROUPS[0];
    const cards = metrics && ADMIN_SUMMARY[activeGroup] ? ADMIN_SUMMARY[activeGroup](metrics) : [];

    return (
        <div className="space-y-5">
            <SectionTitle icon={Settings} kicker="Game Master" title="Admin Dashboard"
                sub="Balance every part of Kaeldor. Tabs are grouped by domain — drag to reorder in Customize mode." />

            {/* Main groups (draggable) */}
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
                    <SortableContext items={visibleGroups.map((g) => g.key)} strategy={horizontalListSortingStrategy}>
                        <div className="flex flex-wrap gap-2" data-testid="admin-main-tabs">
                            {visibleGroups.map((g) => (
                                <SortableMainTab key={g.key} g={g} active={g.key === activeGroup} customizing={customizing} onSelect={() => selectGroup(g.key)} />
                            ))}
                        </div>
                    </SortableContext>
                </DndContext>
                <div className="flex gap-2 shrink-0">
                    <KButton variant={customizing ? "green" : "ghost"} onClick={() => setCustomizing((c) => !c)} data-testid="admin-customize-toggle">
                        <Settings2 className="w-3.5 h-3.5" /> {customizing ? "Done" : "Customize"}
                    </KButton>
                    {customizing && (
                        <KButton variant="ghost" onClick={resetLayout} data-testid="admin-layout-reset">
                            <RotateCcw className="w-3.5 h-3.5" /> Reset
                        </KButton>
                    )}
                </div>
            </div>

            {/* Customize panel: reorder hint + show/hide toggles */}
            {customizing && (
                <Panel className="p-4 border-neon-cyan/30 space-y-2" data-testid="admin-customize-panel">
                    <p className="text-[11px] text-muted-foreground font-mono">Drag the <GripVertical className="w-3 h-3 inline" /> handle on a main tab to reorder. Toggle a section below to show/hide it. Your layout is saved to your account.</p>
                    <div className="flex flex-wrap gap-2">
                        {orderedGroups.map((g) => {
                            const isHidden = hidden.includes(g.key);
                            return (
                                <button key={g.key} onClick={() => toggleHidden(g.key)} disabled={g.key === "overview"} data-testid={`admin-toggle-${g.key}`}
                                    className={cn("inline-flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-mono rounded-sm border transition-colors",
                                        g.key === "overview" ? "border-white/10 text-muted-foreground/40 cursor-not-allowed" :
                                        isHidden ? "border-white/12 text-muted-foreground hover:text-white" : "border-neon-cyan/40 text-neon-cyan")}>
                                    {isHidden ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}{g.label}
                                </button>
                            );
                        })}
                    </div>
                </Panel>
            )}

            {/* Dashboard summary for the active group */}
            {cards.length > 0 && (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5" data-testid="admin-summary">
                    {cards.map((c) => <SummaryCard key={c.label} {...c} />)}
                </div>
            )}

            {/* Sub-tabs for the active group */}
            <div className="flex flex-wrap gap-2 border-t border-white/10 pt-4" data-testid="admin-subtabs">
                {activeG.children.map((c) => (
                    <TabBtn key={c.key} active={activeLeaf === c.key} onClick={() => setActiveLeaf(c.key)}>{c.label}</TabBtn>
                ))}
            </div>

            {/* Active panel */}
            <div>{renderAdminLeaf(activeLeaf, { focusPlayer, onFocusHandled: () => setFocusPlayer(null), onFeedPlayerClick })}</div>
        </div>
    );
}

function TabBtn({ active, onClick, children, icon: Icon }) {
    return (
        <button onClick={onClick} data-testid={`admin-tab-${String(children).toLowerCase()}`}
            className={cn("inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono uppercase tracking-wider rounded-sm border transition-colors",
                active ? "border-neon-cyan text-neon-cyan bg-neon-cyan/10" : "border-white/12 text-muted-foreground hover:text-white hover:border-white/25")}>
            {Icon && <Icon className="w-3.5 h-3.5" />}{children}
        </button>
    );
}
