import { useEffect, useState, useCallback, useMemo } from "react";
import { api, errMessage } from "@/lib/api";
import { SectionTitle, Spinner, Panel, Pill, Money } from "@/components/game/primitives";
import { KButton, KInput } from "@/components/game/controls";
import { money } from "@/lib/helpers";
import {
    Settings, Settings2, Plus, Pencil, Trash2, X, Database, Users, SlidersHorizontal, DollarSign, Gauge,
    MapPin, Store, Clock, Briefcase, LayoutDashboard, Building2, Skull, GripVertical, RotateCcw, Eye, EyeOff,
    Activity, TrendingUp, Wallet, Zap, GraduationCap, Sparkles, User, BadgeCheck,
    ShoppingCart, Scale, Home, Car, Bike, Truck, Gem, HeartPulse, Radio, AlertTriangle, Search,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, horizontalListSortingStrategy, useSortable, arrayMove } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

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

    // Re-fetch after an item add/remove, preserving any unsaved capacity/discount edits in the draft.
    const refreshDraft = async (localCfg) => {
        const { data: fresh } = await api.get("/admin/city-shops");
        setData(fresh);
        const s = (fresh.shops || []).find((x) => x.id === draft.id);
        if (s) setDraft({ ...s, opening_hours: s.opening_hours || { open: "08:00", close: "20:00" }, items_config: { ...(s.items_config || {}), ...(localCfg || {}) } });
    };
    const addItem = async (itemId) => {
        if (!itemId || !draft?.id) return;
        try { await api.post(`/admin/city-shops/${draft.id}/items`, { item_id: itemId }); toast.success("Item added to shop"); await refreshDraft(draft.items_config); }
        catch (e) { toast.error(errMessage(e)); }
    };
    const removeItem = async (itemId) => {
        if (!draft?.id) return;
        try { await api.delete(`/admin/city-shops/${draft.id}/items/${itemId}`); toast.success("Item removed"); await refreshDraft(draft.items_config); }
        catch (e) { toast.error(errMessage(e)); }
    };

    if (!data) return <Spinner />;
    const catItems = (data.items_by_category || {})[draft?.category] || [];
    const assignedItems = draft?.id ? (draft.items || []) : catItems;
    const assignedIds = new Set(assignedItems.map((i) => i.id));
    const addableItems = (data.all_items || []).filter((i) => !assignedIds.has(i.id));
    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">City shops the players browse. A shop's inventory is a list of assigned items — use <span className="text-white">Add item</span> to pull any item from the global list and the trash icon to remove one. Set the Opening Hours (players can only buy while OPEN) and per-item daily Stock + a <span className="text-white">Price %</span> multiplier (100 = base price, 90 = 10% cheaper, 150 = 50% markup). Stock restocks to capacity at game midnight. New shops start pre-filled with all items of their chosen Category.</p>
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
                        <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                            <div className="text-[11px] font-mono uppercase tracking-wider text-neon-cyan/80">Shop Inventory ({assignedItems.length} items)</div>
                            {draft.id ? (
                                <div className="flex items-center gap-2" data-testid="shop-additem-wrap">
                                    <select defaultValue="" onChange={(e) => { addItem(e.target.value); e.target.value = ""; }} data-testid="shop-additem-select"
                                        className="bg-black/40 border border-white/15 rounded-sm px-2 py-1.5 text-xs text-white max-w-[220px]">
                                        <option value="">+ Add item…</option>
                                        {addableItems.map((it) => <option key={it.id} value={it.id}>{it.name} (${it.price} · {it.store_type})</option>)}
                                    </select>
                                </div>
                            ) : <span className="text-[10px] text-muted-foreground">Save the shop first to add/remove individual items.</span>}
                        </div>
                        {assignedItems.length === 0 ? (
                            <p className="text-[11px] text-muted-foreground">No items assigned yet{draft.id ? " — use “Add item” above." : `. New shops start with all “${draft.category}” items; you can customize after saving.`}</p>
                        ) : (
                            <div className="space-y-2" data-testid="shop-items-config">
                                <div className="grid grid-cols-[1fr_auto_auto_auto] gap-3 text-[10px] font-mono uppercase tracking-wider text-muted-foreground/60 px-1">
                                    <span>Item</span><span className="w-24 text-center">Daily stock</span><span className="w-24 text-center">Price %</span><span className="w-8" />
                                </div>
                                {assignedItems.map((it) => {
                                    const c = draft.items_config?.[it.id] || {};
                                    const pct = c.price_pct ?? 100;
                                    const bp = it.base_price ?? it.price ?? 0;
                                    return (
                                        <div key={it.id} className="grid grid-cols-[1fr_auto_auto_auto] gap-3 items-center" data-testid={`shop-itemcfg-${it.id}`}>
                                            <div className="min-w-0">
                                                <span className="text-xs text-white">{it.name}</span>
                                                <span className="ml-2 text-[10px] font-mono text-muted-foreground">base ${bp} → <span className={pct < 100 ? "text-neon-green" : pct > 100 ? "text-neon-yellow" : "text-muted-foreground"}>${Math.max(1, Math.round(bp * pct / 100))}</span></span>
                                            </div>
                                            <KInput type="number" className="w-24" value={c.capacity ?? defCap} onChange={(e) => setItemCfg(it.id, "capacity", Math.max(0, Number(e.target.value)))} testid={`cfg-cap-${it.id}`} />
                                            <KInput type="number" className="w-24" value={pct} onChange={(e) => setItemCfg(it.id, "price_pct", Math.max(1, Math.min(1000, Number(e.target.value))))} testid={`cfg-price-${it.id}`} />
                                            {draft.id ? (
                                                <button onClick={() => removeItem(it.id)} className="text-neon-red hover:text-neon-red/70 justify-self-center" title="Remove item" data-testid={`shop-removeitem-${it.id}`}><Trash2 className="w-4 h-4" /></button>
                                            ) : <span className="w-8" />}
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
    const toggleVisibility = async (j) => {
        try {
            await api.put(`/admin/jobs/${j.id}/visibility`, { visible: !(j.visible_in_listings !== false) });
            await load();
        } catch (e) { toast.error(errMessage(e)); }
    };

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

            {!draft && (
                <Panel className="p-4" data-testid="job-visibility-panel">
                    <div className="font-display font-bold text-white mb-1 flex items-center gap-2"><Eye className="w-4 h-4 text-neon-cyan" /> Job Center Visibility</div>
                    <p className="text-[11px] text-muted-foreground mb-3">Hide "rank-up only" jobs so players can't apply for them directly — they'll only be reachable by earning a promotion. Hidden jobs stay fully promotable.</p>
                    <div className="grid sm:grid-cols-2 gap-1.5 max-h-80 overflow-y-auto pr-1">
                        {data.jobs.map((j) => {
                            const visible = j.visible_in_listings !== false;
                            return (
                                <div key={j.id} className="flex items-center justify-between gap-2 p-2 border border-white/10 rounded-sm" data-testid={`job-visibility-${j.id}`}>
                                    <div className="min-w-0">
                                        <span className="text-xs text-white">{j.title}</span>
                                        <span className="ml-1.5 text-[10px] font-mono text-muted-foreground">T{j.tier} · {j.category}</span>
                                    </div>
                                    <button onClick={() => toggleVisibility(j)}
                                        className={cn("inline-flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded-sm border transition-colors",
                                            visible ? "border-neon-green/40 text-neon-green hover:bg-neon-green/10" : "border-neon-yellow/40 text-neon-yellow hover:bg-neon-yellow/10")}
                                        title={visible ? "Visible — click to hide" : "Hidden — click to show"} data-testid={`job-visibility-toggle-${j.id}`}>
                                        {visible ? <><Eye className="w-3 h-3" /> Visible</> : <><EyeOff className="w-3 h-3" /> Hidden</>}
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                </Panel>
            )}
        </div>
    );
}
const VCAT_ICON_OPTIONS = ["Car", "Bike", "Truck", "Gem"];
function VehicleCategoriesPanel() {
    const [data, setData] = useState(null);
    const [draft, setDraft] = useState(null);
    const [saving, setSaving] = useState(false);
    const load = useCallback(() => api.get("/admin/vehicle-categories").then(({ data }) => setData(data)).catch(() => setData({ categories: [], vehicles: [] })), []);
    useEffect(() => { load(); }, [load]);

    const emptyCat = () => ({ name: "", desc: "", icon: "Car", active: true, order: 50, vehicle_ids: [] });
    const set = (k, v) => setDraft((d) => ({ ...d, [k]: v }));
    const toggleVeh = (vid) => setDraft((d) => {
        const has = (d.vehicle_ids || []).includes(vid);
        return { ...d, vehicle_ids: has ? d.vehicle_ids.filter((x) => x !== vid) : [...(d.vehicle_ids || []), vid] };
    });
    const editCat = (c) => setDraft({ ...c, vehicle_ids: (data.vehicles || []).filter((v) => v.category_id === c.id).map((v) => v.id) });
    const save = async () => {
        setSaving(true);
        try {
            const body = { name: draft.name, desc: draft.desc || "", icon: draft.icon || "Car",
                active: !!draft.active, order: Number(draft.order) || 50, vehicle_ids: draft.vehicle_ids || [] };
            if (draft.id) await api.put(`/admin/vehicle-categories/${draft.id}`, body);
            else await api.post("/admin/vehicle-categories", body);
            toast.success("Category saved — live in the Vehicle Dealer immediately");
            setDraft(null); await load();
        } catch (e) { toast.error(errMessage(e)); }
        setSaving(false);
    };
    const del = async (c) => { if (!window.confirm(`Delete "${c.name}"? Its vehicles become uncategorized.`)) return; try { await api.delete(`/admin/vehicle-categories/${c.id}`); toast.success("Deleted"); await load(); } catch (e) { toast.error(errMessage(e)); } };

    if (!data) return <Spinner />;
    const otherAssigned = {};
    (data.vehicles || []).forEach((v) => { if (v.category_id && (!draft || v.category_id !== draft.id)) otherAssigned[v.id] = v.category_id; });
    const catName = (id) => (data.categories.find((c) => c.id === id) || {}).name || id;

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">Showroom categories players browse in the Vehicle Dealer. Create a category, then assign vehicle models to it — each vehicle belongs to one category. Any vehicle left unassigned appears under an "Other Vehicles" fallback so nothing is unreachable.</p>
                {!draft && <KButton variant="green" onClick={() => setDraft(emptyCat())} data-testid="vcat-new"><Plus className="w-4 h-4" /> New Category</KButton>}
            </div>

            {draft && (
                <Panel className="p-5 space-y-3 border-neon-cyan/30" data-testid="vcat-editor">
                    <div className="grid sm:grid-cols-2 gap-3">
                        <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Category name
                            <KInput value={draft.name} onChange={(e) => set("name", e.target.value)} testid="vcat-name" /></label>
                        <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Icon
                            <select value={draft.icon} onChange={(e) => set("icon", e.target.value)} data-testid="vcat-icon"
                                className="bg-black/40 border border-white/15 rounded-sm px-2 py-2 text-xs text-white">
                                {VCAT_ICON_OPTIONS.map((c) => <option key={c} value={c}>{c}</option>)}
                            </select></label>
                    </div>
                    <label className="text-[11px] text-muted-foreground flex flex-col gap-1">Description
                        <KInput value={draft.desc} onChange={(e) => set("desc", e.target.value)} testid="vcat-desc" /></label>
                    <div className="flex items-center gap-4">
                        <label className="text-[11px] text-muted-foreground flex flex-col gap-1 w-20">Order
                            <KInput type="number" value={draft.order} onChange={(e) => set("order", Number(e.target.value))} testid="vcat-order" /></label>
                        <label className="text-[11px] text-muted-foreground flex items-center gap-2 mt-4">
                            <input type="checkbox" checked={!!draft.active} onChange={(e) => set("active", e.target.checked)} data-testid="vcat-active" /> Active</label>
                    </div>

                    <div className="pt-2">
                        <div className="text-[11px] font-mono uppercase tracking-wider text-neon-cyan/80 mb-2">Assign Vehicles ({(draft.vehicle_ids || []).length} selected)</div>
                        <div className="grid sm:grid-cols-2 gap-1.5 max-h-72 overflow-y-auto pr-1" data-testid="vcat-vehicle-picker">
                            {data.vehicles.map((v) => {
                                const checked = (draft.vehicle_ids || []).includes(v.id);
                                const takenBy = otherAssigned[v.id];
                                return (
                                    <label key={v.id} className={cn("flex items-center gap-2 p-2 border rounded-sm cursor-pointer transition-colors",
                                        checked ? "border-neon-cyan/50 bg-neon-cyan/5" : "border-white/10 hover:border-white/25")} data-testid={`vcat-vehicle-${v.id}`}>
                                        <input type="checkbox" checked={checked} onChange={() => toggleVeh(v.id)} data-testid={`vcat-vehicle-cb-${v.id}`} />
                                        <div className="min-w-0 flex-1">
                                            <span className="text-xs text-white">{v.name}</span>
                                            <span className="ml-1.5 text-[10px] font-mono text-muted-foreground">{v.type} · ${v.price?.toLocaleString()}</span>
                                            {takenBy && !checked && <span className="block text-[9px] text-neon-yellow/80 font-mono">in {catName(takenBy)}</span>}
                                        </div>
                                    </label>
                                );
                            })}
                        </div>
                    </div>

                    <div className="flex gap-2 pt-2">
                        <KButton variant="green" loading={saving} disabled={!draft.name} onClick={save} data-testid="vcat-save">Save Category</KButton>
                        <KButton variant="ghost" onClick={() => setDraft(null)} data-testid="vcat-cancel">Cancel</KButton>
                    </div>
                </Panel>
            )}

            {!draft && (
                <div className="grid md:grid-cols-2 gap-3">
                    {data.categories.map((c) => (
                        <Panel key={c.id} className="p-4" data-testid={`admin-vcat-${c.id}`}>
                            <div className="flex items-start justify-between mb-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                    <span className="font-display font-bold text-white">{c.name}</span>
                                    <span className="text-[10px] uppercase text-neon-cyan/80 font-mono">{c.icon}</span>
                                    {!c.active && <Pill tone="red">Inactive</Pill>}
                                </div>
                                <div className="flex gap-1">
                                    <button onClick={() => editCat(c)} className="text-muted-foreground hover:text-white" data-testid={`vcat-edit-${c.id}`}><Pencil className="w-4 h-4" /></button>
                                    <button onClick={() => del(c)} className="text-neon-red hover:text-neon-red/70" data-testid={`vcat-del-${c.id}`}><Trash2 className="w-4 h-4" /></button>
                                </div>
                            </div>
                            <p className="text-[11px] text-muted-foreground mb-2">{c.desc}</p>
                            <div className="text-[10px] font-mono text-muted-foreground">{c.vehicle_count} model{c.vehicle_count === 1 ? "" : "s"} assigned</div>
                        </Panel>
                    ))}
                </div>
            )}
        </div>
    );
}

export { emptyLoc, AttrRow, LocationEditor, LocationsPanel, CityShopsPanel, SECTOR_ICON_OPTIONS, JobSectorsPanel, VCAT_ICON_OPTIONS, VehicleCategoriesPanel };
