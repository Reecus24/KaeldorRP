import { useEffect, useState, useCallback, useMemo } from "react";
import { api, errMessage } from "@/lib/api";
import { SectionTitle, Spinner, Panel, Pill, Money } from "@/components/game/primitives";
import { KButton, KInput } from "@/components/game/controls";
import { money, timeMode } from "@/lib/helpers";
import { editableConfigFields, configValue, setConfigValue, normalizeConfigPatch } from "@/lib/configFields";
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
    const clockMode = timeMode(cfg.time_scale);
    const isRealtime = clockMode.realtime;

    return (
        <div className="space-y-4">
            <Panel className={cn("p-4 flex items-center gap-3", isRealtime ? "border-neon-green/40" : "border-neon-yellow/40")} data-testid="realtime-indicator">
                <span className={cn("w-2.5 h-2.5 rounded-full", isRealtime ? "bg-neon-green" : "bg-neon-yellow animate-pulse-dot")} />
                <div className="flex-1">
                    <div className={cn("font-display font-bold", isRealtime ? "text-neon-green" : "text-neon-yellow")}>
                        {isRealtime ? "TRUE REAL-TIME MODE" : `${clockMode.label} — SCALED WORLD CLOCK`}
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                        {isRealtime
                            ? "1 game hour = 1 real hour. Jobs, study, workshops, rent and sentences run over real-life time."
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
                className="w-full min-h-[300px] bg-[#101A16] border border-white/12 rounded-sm p-3 font-mono text-xs text-neon-green/90 outline-none focus:border-neon-cyan/60 resize-none" />
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
                <div className="text-[11px] text-muted-foreground">Edit price, material cost, demand, PPH, base wage and opening hours per workshop type. Changes hit the live simulation on the next tick.</div>
                <label className="flex items-center gap-2 text-xs text-white cursor-pointer">
                    <input type="checkbox" checked={applyExisting} onChange={(e) => setApplyExisting(e.target.checked)} data-testid="apply-existing-toggle" />
                    Apply to existing workshops (not just new)
                </label>
            </Panel>
            <Panel className="p-0 overflow-x-auto">
                <div className="min-w-[900px]">
                    <div className="grid grid-cols-12 gap-2 px-3 py-2 border-b border-white/8 bg-[#101A16] font-mono text-[10px] uppercase text-muted-foreground">
                        <div className="col-span-2">Workshop</div><div className="col-span-1">Price</div><div className="col-span-2">Material ¤ </div>
                        <div className="col-span-1">Demand</div><div className="col-span-1">PPH</div><div className="col-span-2">Base ¤ /hr</div>
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
            <style>{`.econ-inp{background:#101A16;border:1px solid rgba(255,255,255,.12);border-radius:3px;padding:4px 6px;font-family:monospace;font-size:12px;color:#7CFFCB;outline:none}.econ-inp:focus{border-color:rgba(0,243,255,.6)}`}</style>
        </div>
    );
}
const TUNE_FIELDS = [
    { section: "Timers (in-game days)", keys: [["upgrade_days", "Upgrade duration"], ["marketing_days", "Heralds duration"], ["raise_cooldown_days", "Wage-raise cooldown"]] },
    { section: "Multiplier ranges", keys: [["satisfaction_mult_min", "Satisfaction→Production min"], ["satisfaction_mult_max", "Satisfaction→Production max"], ["reputation_mult_min", "Reputation→Demand min"], ["reputation_mult_max", "Reputation→Demand max"], ["worker_cond_min", "Worker condition min"], ["worker_cond_max", "Worker condition max"]] },
    { section: "Effectiveness → Accidents", keys: [["accident_eff_threshold", "Injury effectiveness threshold"], ["accident_chance", "Injury chance below threshold"]] },
    { section: "Commodity Exchange (per real hour)", keys: [["stock_drift", "Base return / hr (e.g. 0.0015)"], ["stock_volatility", "Volatility / hr (e.g. 0.03)"]] },
    { section: "Relic Exchange (per real hour)", keys: [["crypto_drift", "Base return / hr (e.g. 0.004)"], ["crypto_volatility", "Volatility / hr (e.g. 0.09)"]] },
    { section: "Player Progression", keys: [["skill_decay_per_hour", "Skill Decay Rate (XP/hr idle, 0 = off)"]] },
    { section: "Criminal Suspicion", keys: [["suspicion_decay_per_hour", "Suspicion Decay Rate (/hr clean, 0 = never)"], ["suspicion_gain_mult", "Suspicion Gain Multiplier (x illegal acts)"]] },
];
function TuningPanel() {
    const [cfg, setCfg] = useState(null);
    const [patch, setPatch] = useState({});
    const [busy, setBusy] = useState(false);
    const load = () => api.get("/admin/config").then(({ data }) => { setCfg(data); setPatch({}); });
    useEffect(() => { load(); }, []);
    const setField = (path, value) => setPatch((current) => setConfigValue(current, path, value));
    const currentValue = (path) => configValue(patch, path) ?? configValue(cfg, path);
    const setBracket = (i, field, v) => {
        const b = (currentValue(["tuning", "tax_brackets"]) || []).map((x) => [...x]);
        b[i][field] = field === 0 ? (v === "" ? null : Number(v)) : Number(v);
        setField(["tuning", "tax_brackets"], b);
    };
    const save = async () => {
        setBusy(true);
        try {
            const clean = normalizeConfigPatch(patch, cfg);
            await api.put("/admin/config", clean);
            toast.success("Settings saved — live on next tick");
            await load();
        } catch (e) { toast.error(e.response ? errMessage(e) : e.message); }
        finally { setBusy(false); }
    };
    if (!cfg) return <Spinner />;
    const knownKeys = new Set(TUNE_FIELDS.flatMap((group) => group.keys.map(([key]) => key)));
    const humanLabel = (text) => text.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
    const renderField = ({ path, value }, label) => (
        <div key={path.join(".")} className="space-y-1">
            {typeof value === "boolean" ? (
                <label className="flex items-center gap-3 min-h-[42px] text-sm text-white">
                    <input type="checkbox" checked={!!currentValue(path)} onChange={(event) => setField(path, event.target.checked)} data-testid={`tune-${path.join("-")}`} />
                    {label || humanLabel(path[path.length - 1])}
                </label>
            ) : (
                <KInput label={label || humanLabel(path.slice(1).join(" / ") || path[0])} type="number" step="any" value={currentValue(path) ?? ""}
                    onChange={(event) => setField(path, event.target.value)} testid={path[0] === "tuning" && path.length === 2 ? `tune-${path[1]}` : `tune-${path.join("-")}`} />
            )}
        </div>
    );
    const newTuning = editableConfigFields(cfg.tuning, ["tuning"]).filter(({ path }) => !knownKeys.has(path[1]));
    const otherGroups = Object.entries(cfg).filter(([key]) => key !== "tuning")
        .map(([key, value]) => ({ key, fields: editableConfigFields(value, [key]) })).filter(({ fields }) => fields.length);
    return (
        <div className="space-y-4">
            <Panel className="p-5 border-neon-cyan/25">
                <h3 className="font-display font-bold text-white">Owner gameplay controls</h3>
                <p className="text-sm text-muted-foreground mt-2">Needs, infirmary care, economy and progression share this configuration. New numeric settings and switches appear here automatically. Advanced structures remain available in Config.</p>
                <p className="text-xs text-muted-foreground mt-2">Rates marked per hour use game time. Infirmary duration is in game minutes; Time Scale converts these to real waiting time.</p>
                <p className="text-xs text-muted-foreground mt-2">Duration changes apply to newly scheduled timers. Rates and thresholds apply on the next character update.</p>
            </Panel>
            {otherGroups.map(({ key, fields }) => (
                <Panel key={key} className="p-5" data-testid={`config-group-${key}`}>
                    <h3 className="font-display font-bold text-white mb-4">{humanLabel(key)}</h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">{fields.map((field) => renderField(field))}</div>
                </Panel>
            ))}
            {TUNE_FIELDS.map((grp) => (
                <Panel key={grp.section} className="p-5">
                    <div className="font-display font-bold text-white mb-3">{grp.section}</div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {grp.keys.filter(([key]) => typeof cfg.tuning?.[key] === "number").map(([key, label]) => renderField({ path: ["tuning", key], value: cfg.tuning[key] }, label))}
                    </div>
                </Panel>
            ))}
            {newTuning.length > 0 && <Panel className="p-5" data-testid="additional-tuning-fields">
                <h3 className="font-display font-bold text-white mb-4">Additional gameplay settings</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">{newTuning.map((field) => renderField(field))}</div>
            </Panel>}
            <Panel className="p-5">
                <div className="font-display font-bold text-white mb-1">Income Tax Brackets</div>
                <p className="text-[11px] text-muted-foreground mb-3">Progressive rate applied to each job shift's gross pay. "Up to" empty = top bracket.</p>
                <div className="space-y-2">
                    {(currentValue(["tuning", "tax_brackets"]) || []).map((b, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs" data-testid={`tax-bracket-${i}`}>
                            <span className="text-muted-foreground w-14">Up to ¤ </span>
                            <KInput type="number" value={b[0] ?? ""} placeholder="∞ (top)" onChange={(e) => setBracket(i, 0, e.target.value)} testid={`tax-upto-${i}`} />
                            <span className="text-muted-foreground">rate</span>
                            <KInput type="number" step="0.01" value={b[1]} onChange={(e) => setBracket(i, 1, e.target.value)} testid={`tax-rate-${i}`} />
                            <span className="text-muted-foreground">= {Math.round((b[1] || 0) * 100)}%</span>
                        </div>
                    ))}
                </div>
            </Panel>
            <div className="sticky bottom-4 p-3 bg-[#19251e]/95 backdrop-blur border border-neon-cyan/25 rounded-sm flex items-center justify-between gap-3">
                <span className="text-sm text-muted-foreground">{Object.keys(patch).length ? "Unsaved changes" : "All changes saved"}</span>
                <KButton variant="green" onClick={save} loading={busy} disabled={!Object.keys(patch).length} data-testid="save-tuning">Save Tuning</KButton>
            </div>
        </div>
    );
}
function MarketsPanel() {
    const [data, setData] = useState(null);
    const [edits, setEdits] = useState({});
    const [busy, setBusy] = useState(false);
    const load = useCallback(() => api.get("/admin/market").then(({ data }) => { setData(data); setEdits({}); }).catch(() => setData({ assets: [], tuning: {} })), []);
    useEffect(() => { load(); }, [load]);

    const setEdit = (id, k, v) => setEdits((e) => ({ ...e, [id]: { ...(e[id] || {}), [k]: v } }));
    const saveAsset = async (a) => {
        const e = edits[a.id] || {};
        const body = {};
        if (e.price !== undefined && e.price !== "") body.price = Number(e.price);
        if (e.base_price !== undefined && e.base_price !== "") body.base_price = Number(e.base_price);
        if (!Object.keys(body).length) return;
        setBusy(true);
        try { await api.put(`/admin/market/${a.id}`, body); toast.success(`${a.symbol} updated`); await load(); }
        catch (err) { toast.error(errMessage(err)); }
        setBusy(false);
    };
    const reroll = async () => {
        setBusy(true);
        try { const { data } = await api.post("/admin/market/refresh"); toast.success(`Re-rolled ${data.advanced} assets`); await load(); }
        catch (err) { toast.error(errMessage(err)); }
        setBusy(false);
    };
    const [nw, setNw] = useState({ symbol: "", name: "", kind: "stock", base_price: 100 });
    const createAsset = async () => {
        if (!nw.symbol.trim() || !nw.name.trim()) { toast.error("Symbol and name are required"); return; }
        setBusy(true);
        try { await api.post("/admin/market", { ...nw, base_price: Number(nw.base_price) }); toast.success(`${nw.symbol.toUpperCase()} created`); setNw({ symbol: "", name: "", kind: "stock", base_price: 100 }); await load(); }
        catch (err) { toast.error(errMessage(err)); }
        setBusy(false);
    };
    const delAsset = async (a) => {
        if (!window.confirm(`Delete ${a.symbol} from the market? Player holdings become untradable.`)) return;
        setBusy(true);
        try { await api.delete(`/admin/market/${a.id}`); toast.success(`${a.symbol} deleted`); await load(); }
        catch (err) { toast.error(errMessage(err)); }
        setBusy(false);
    };

    if (!data) return <Spinner />;
    const t = data.tuning || {};
    const groups = [["stock", "Stocks"], ["crypto", "Relic"]];
    const inCls = "bg-black/40 border border-white/15 rounded-sm px-2 py-1.5 text-xs text-white";

    return (
        <div className="space-y-4">
            <div className="flex items-start justify-between gap-3 flex-wrap">
                <p className="text-sm text-muted-foreground max-w-2xl">Live market assets. Prices follow a per-real-hour random walk driven by the drift/volatility below (set those in Gameplay Tuning ▸ Tuning). Because movement scales with elapsed real time, changes look gradual — hit <strong className="text-white">Re-roll Now</strong> to apply a full step instantly, or set a price directly. New assets are picked up by the price engine automatically.</p>
                <KButton variant="primary" loading={busy} onClick={reroll} data-testid="market-reroll"><Radio className="w-4 h-4" /> Re-roll Now</KButton>
            </div>

            <Panel className="p-4 border-neon-green/25" data-testid="market-create">
                <div className="text-[11px] font-mono uppercase tracking-wider text-neon-green/80 mb-2">Add New Asset</div>
                <div className="flex items-end gap-2 flex-wrap">
                    <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Symbol
                        <input className={cn(inCls, "w-24 uppercase")} value={nw.symbol} onChange={(e) => setNw((s) => ({ ...s, symbol: e.target.value.toUpperCase().slice(0, 6) }))} data-testid="market-new-symbol" /></label>
                    <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Name
                        <input className={cn(inCls, "w-48")} value={nw.name} onChange={(e) => setNw((s) => ({ ...s, name: e.target.value }))} data-testid="market-new-name" /></label>
                    <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Kind
                        <select className={inCls} value={nw.kind} onChange={(e) => setNw((s) => ({ ...s, kind: e.target.value }))} data-testid="market-new-kind">
                            <option value="stock">Commodity</option><option value="crypto">Relic</option>
                        </select></label>
                    <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Start Price
                        <input type="number" className={cn(inCls, "w-28")} value={nw.base_price} onChange={(e) => setNw((s) => ({ ...s, base_price: e.target.value }))} data-testid="market-new-price" /></label>
                    <KButton variant="green" loading={busy} onClick={createAsset} data-testid="market-new-create"><Plus className="w-3.5 h-3.5" /> Create</KButton>
                </div>
            </Panel>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono">
                <div className="p-2 border border-white/10 rounded-sm"><span className="text-muted-foreground">Commodity drift/hr</span><div className="text-neon-cyan">{t.stock_drift}</div></div>
                <div className="p-2 border border-white/10 rounded-sm"><span className="text-muted-foreground">Commodity vol/hr</span><div className="text-neon-cyan">{t.stock_volatility}</div></div>
                <div className="p-2 border border-white/10 rounded-sm"><span className="text-muted-foreground">Relic drift/hr</span><div className="text-neon-purple">{t.crypto_drift}</div></div>
                <div className="p-2 border border-white/10 rounded-sm"><span className="text-muted-foreground">Relic vol/hr</span><div className="text-neon-purple">{t.crypto_volatility}</div></div>
            </div>

            {groups.map(([kind, label]) => (
                <div key={kind}>
                    <div className="text-[10px] uppercase tracking-wider text-neon-cyan/80 mb-1.5">{label}</div>
                    <div className="space-y-1.5">
                        {data.assets.filter((a) => a.kind === kind).map((a) => (
                            <div key={a.id} className="flex items-center gap-2 p-2 border border-white/10 rounded-sm flex-wrap" data-testid={`market-asset-${a.id}`}>
                                <div className="min-w-0 flex-1">
                                    <span className="font-display font-bold text-white text-sm">{a.symbol}</span>
                                    <span className="ml-2 text-[11px] text-muted-foreground">{a.name}</span>
                                </div>
                                <label className="text-[10px] text-muted-foreground flex flex-col">Price
                                    <input type="number" defaultValue={a.price} onChange={(e) => setEdit(a.id, "price", e.target.value)}
                                        className="bg-black/40 border border-white/15 rounded-sm px-2 py-1 text-xs text-white w-28" data-testid={`market-price-${a.id}`} /></label>
                                <label className="text-[10px] text-muted-foreground flex flex-col">Base (anchor)
                                    <input type="number" defaultValue={a.base_price} onChange={(e) => setEdit(a.id, "base_price", e.target.value)}
                                        className="bg-black/40 border border-white/15 rounded-sm px-2 py-1 text-xs text-white w-28" data-testid={`market-base-${a.id}`} /></label>
                                <KButton variant="green" loading={busy} onClick={() => saveAsset(a)} data-testid={`market-save-${a.id}`}>Set</KButton>
                                <button onClick={() => delAsset(a)} className="text-neon-red hover:text-neon-red/70" title="Delete asset" data-testid={`market-delete-${a.id}`}><Trash2 className="w-4 h-4" /></button>
                            </div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

export { ConfigEditor, ConfigJson, EconomyTuner, TUNE_FIELDS, TuningPanel, MarketsPanel };
