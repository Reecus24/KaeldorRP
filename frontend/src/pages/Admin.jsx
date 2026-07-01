import { useEffect, useState, useCallback } from "react";
import { api, errMessage } from "@/lib/api";
import { SectionTitle, Spinner, Panel, Pill, Money } from "@/components/game/primitives";
import { KButton, KInput } from "@/components/game/controls";
import { money } from "@/lib/helpers";
import { Settings, Plus, Pencil, Trash2, X, Database, Users, SlidersHorizontal, DollarSign, Gauge, MapPin, Store, Clock } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

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

function PlayersTable() {
    const [players, setPlayers] = useState(null);
    const [edit, setEdit] = useState(null);
    const load = () => api.get("/admin/players").then(({ data }) => setPlayers(data));
    useEffect(() => { load(); }, []);
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
    return (
        <Panel className="p-0 overflow-hidden">
            <div className="grid grid-cols-12 gap-2 px-4 py-3 border-b border-white/8 bg-[#050505] font-mono text-[10px] uppercase text-muted-foreground">
                <div className="col-span-3">Name</div><div className="col-span-1">Lvl</div><div className="col-span-2 text-right">Cash</div>
                <div className="col-span-2 text-right">Net Worth</div><div className="col-span-1 text-right">Rep</div><div className="col-span-1 text-right">Legal</div>
                <div className="col-span-1 text-right">Susp</div><div className="col-span-1"></div>
            </div>
            {players.map((p) => (
                <div key={p.id} className="grid grid-cols-12 gap-2 px-4 py-2.5 border-b border-white/5 text-sm items-center" data-testid={`admin-player-${p.id}`}>
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
            {edit && (
                <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={() => setEdit(null)}>
                    <Panel className="p-5 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
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

export default function Admin() {
    const [tab, setTab] = useState("stats");

    return (
        <div className="space-y-6">
            <SectionTitle icon={Settings} kicker="Game Master" title="Admin Dashboard"
                sub="Create and balance every part of Kaeldor — jobs, actions, courses, items, housing, vehicles, businesses, crimes, events and global config." />

            <div className="flex flex-wrap gap-2">
                <TabBtn active={tab === "stats"} onClick={() => setTab("stats")} icon={Database}>Stats</TabBtn>
                <TabBtn active={tab === "economy"} onClick={() => setTab("economy")} icon={DollarSign}>Economy Sandbox</TabBtn>
                <TabBtn active={tab === "tuning"} onClick={() => setTab("tuning")} icon={Gauge}>Tuning</TabBtn>
                <TabBtn active={tab === "locations"} onClick={() => setTab("locations")} icon={MapPin}>Locations</TabBtn>
                <TabBtn active={tab === "cityshops"} onClick={() => setTab("cityshops")} icon={Store}>City Shops</TabBtn>
                <TabBtn active={tab === "players"} onClick={() => setTab("players")} icon={Users}>Players</TabBtn>
                <TabBtn active={tab === "config"} onClick={() => setTab("config")} icon={SlidersHorizontal}>Config</TabBtn>
                {CONTENT_TYPES.map((c) => <TabBtn key={c.key} active={tab === c.key} onClick={() => setTab(c.key)}>{c.label}</TabBtn>)}
            </div>

            <div>
                {tab === "stats" && <StatsView />}
                {tab === "economy" && <EconomyTuner />}
                {tab === "tuning" && <TuningPanel />}
                {tab === "locations" && <LocationsPanel />}
                {tab === "cityshops" && <CityShopsPanel />}
                {tab === "config" && <ConfigEditor />}
                {tab === "players" && <PlayersTable />}
                {CONTENT_TYPES.some((c) => c.key === tab) && <ContentEditor ctype={tab} />}
            </div>
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
