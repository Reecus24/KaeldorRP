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

function PlayersTable({ focus, onFocusHandled }) {
    const [players, setPlayers] = useState(null);
    const [edit, setEdit] = useState(null);
    const [search, setSearch] = useState("");
    const [highlightId, setHighlightId] = useState(null);
    const load = useCallback(() => api.get("/admin/players").then(({ data }) => setPlayers(data)), []);
    useEffect(() => { load(); }, [load]);

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
function CharacterOriginsPanel() {
    const [data, setData] = useState(null);
    const [draft, setDraft] = useState(null);
    const [busy, setBusy] = useState(false);
    const load = useCallback(() => api.get("/admin/backgrounds").then(({ data }) => setData(data)).catch(() => setData({ backgrounds: [], skills: [], items: [], stat_keys: [] })), []);
    useEffect(() => { load(); }, [load]);

    const blank = () => ({ id: null, label: "", desc: "", cash: 100, bank: 0, debt: 0,
        stats: { health: 100, energy: 100, fatigue: 0, hunger: 20, mood: 70, stress: 10 },
        skills: {}, inventory: {}, order: 99, active: true });
    const save = async () => {
        if (!draft.label.trim()) { toast.error("Name is required"); return; }
        setBusy(true);
        try {
            if (draft.id) await api.put(`/admin/backgrounds/${draft.id}`, draft);
            else await api.post("/admin/backgrounds", draft);
            toast.success("Origin saved — live on the character creation screen");
            setDraft(null); await load();
        } catch (e) { toast.error(errMessage(e)); }
        setBusy(false);
    };
    const del = async (b) => {
        if (!window.confirm(`Delete origin "${b.label}"?`)) return;
        try { await api.delete(`/admin/backgrounds/${b.id}`); toast.success("Deleted"); await load(); }
        catch (e) { toast.error(errMessage(e)); }
    };

    if (!data) return <Spinner />;
    const inCls = "bg-black/40 border border-white/15 rounded-sm px-2 py-1.5 text-xs text-white";
    const skillLabel = (s) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

    return (
        <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Starting backgrounds ("Origins") players pick at character creation — pulled live from the DB. Configure starting money, debt, stats, skill bonuses (added on top of level 1) and starting inventory. Changes appear on the creation screen immediately.</p>

            {draft ? (
                <Panel className="p-5 space-y-4 border-neon-cyan/30" data-testid="origin-editor">
                    <div className="flex items-center gap-2"><User className="w-4 h-4 text-neon-cyan" /><span className="font-display font-bold text-white">{draft.id ? `Edit ${draft.label}` : "New Origin"}</span></div>
                    <div className="grid sm:grid-cols-2 gap-3">
                        <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Name<input className={inCls} value={draft.label} onChange={(e) => setDraft((d) => ({ ...d, label: e.target.value }))} data-testid="origin-label" /></label>
                        <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Order<input type="number" className={inCls} value={draft.order} onChange={(e) => setDraft((d) => ({ ...d, order: Number(e.target.value) }))} data-testid="origin-order" /></label>
                    </div>
                    <label className="text-[10px] text-muted-foreground flex flex-col gap-1">Description<textarea className={cn(inCls, "min-h-[52px]")} value={draft.desc} onChange={(e) => setDraft((d) => ({ ...d, desc: e.target.value }))} data-testid="origin-desc" /></label>
                    <div className="grid grid-cols-3 gap-3">
                        {["cash", "bank", "debt"].map((k) => (
                            <label key={k} className="text-[10px] text-muted-foreground flex flex-col gap-1 capitalize">Starting {k}
                                <input type="number" className={inCls} value={draft[k]} onChange={(e) => setDraft((d) => ({ ...d, [k]: Number(e.target.value) }))} data-testid={`origin-${k}`} /></label>
                        ))}
                    </div>
                    <div>
                        <div className="text-[10px] uppercase tracking-wider text-neon-cyan/80 mb-1.5">Starting Stats</div>
                        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                            {(data.stat_keys || []).map((k) => (
                                <label key={k} className="text-[10px] text-muted-foreground flex flex-col gap-1 capitalize">{k}
                                    <input type="number" className={inCls} value={draft.stats[k] ?? 0} onChange={(e) => setDraft((d) => ({ ...d, stats: { ...d.stats, [k]: Number(e.target.value) } }))} data-testid={`origin-stat-${k}`} /></label>
                            ))}
                        </div>
                    </div>
                    <div>
                        <div className="text-[10px] uppercase tracking-wider text-neon-purple/80 mb-1.5">Skill Bonuses (levels above 1)</div>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                            {(data.skills || []).map((s) => (
                                <label key={s} className="text-[10px] text-muted-foreground flex flex-col gap-1">{skillLabel(s)}
                                    <input type="number" min="0" max="20" className={inCls} value={draft.skills[s] ?? 0} onChange={(e) => { const v = Math.max(0, Number(e.target.value)); setDraft((d) => { const sk = { ...d.skills }; if (v) sk[s] = v; else delete sk[s]; return { ...d, skills: sk }; }); }} data-testid={`origin-skill-${s}`} /></label>
                            ))}
                        </div>
                    </div>
                    <div>
                        <div className="flex items-center justify-between mb-1.5">
                            <div className="text-[10px] uppercase tracking-wider text-neon-green/80">Starting Inventory</div>
                            <select defaultValue="" className={inCls} onChange={(e) => { const id = e.target.value; if (id) setDraft((d) => ({ ...d, inventory: { ...d.inventory, [id]: (d.inventory[id] || 0) + 1 } })); e.target.value = ""; }} data-testid="origin-additem">
                                <option value="">+ Add item…</option>
                                {(data.items || []).filter((it) => draft.inventory[it.id] === undefined).map((it) => <option key={it.id} value={it.id}>{it.name}</option>)}
                            </select>
                        </div>
                        {Object.keys(draft.inventory).length === 0 ? <p className="text-[11px] text-muted-foreground">No starting items.</p> : (
                            <div className="space-y-1.5" data-testid="origin-inventory">
                                {Object.entries(draft.inventory).map(([iid, qty]) => (
                                    <div key={iid} className="flex items-center gap-2">
                                        <span className="text-xs text-white flex-1">{(data.items.find((x) => x.id === iid) || {}).name || iid}</span>
                                        <input type="number" min="1" className={cn(inCls, "w-20")} value={qty} onChange={(e) => setDraft((d) => ({ ...d, inventory: { ...d.inventory, [iid]: Math.max(1, Number(e.target.value)) } }))} data-testid={`origin-qty-${iid}`} />
                                        <button onClick={() => setDraft((d) => { const inv = { ...d.inventory }; delete inv[iid]; return { ...d, inventory: inv }; })} className="text-neon-red hover:text-neon-red/70" data-testid={`origin-removeitem-${iid}`}><Trash2 className="w-4 h-4" /></button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                    <label className="flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={draft.active} onChange={(e) => setDraft((d) => ({ ...d, active: e.target.checked }))} data-testid="origin-active" /> Active (shown to players)</label>
                    <div className="flex gap-2">
                        <KButton variant="green" loading={busy} onClick={save} data-testid="origin-save">Save Origin</KButton>
                        <KButton variant="ghost" onClick={() => setDraft(null)} data-testid="origin-cancel">Cancel</KButton>
                    </div>
                </Panel>
            ) : (
                <>
                    <KButton variant="primary" onClick={() => setDraft(blank())} data-testid="origin-new"><Plus className="w-4 h-4" /> New Origin</KButton>
                    <div className="grid md:grid-cols-2 gap-3">
                        {(data.backgrounds || []).map((b) => (
                            <Panel key={b.id} className="p-4" data-testid={`origin-card-${b.id}`}>
                                <div className="flex items-start justify-between mb-1.5">
                                    <div className="flex items-center gap-2 flex-wrap">
                                        <span className="font-display font-bold text-white">{b.label}</span>
                                        {!b.active && <Pill tone="yellow">Hidden</Pill>}
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button onClick={() => setDraft({ ...blank(), ...b, stats: { ...blank().stats, ...(b.stats || {}) }, skills: { ...(b.skills || {}) }, inventory: { ...(b.inventory || {}) } })} className="text-muted-foreground hover:text-neon-cyan" data-testid={`origin-edit-${b.id}`}><Pencil className="w-4 h-4" /></button>
                                        <button onClick={() => del(b)} className="text-muted-foreground hover:text-neon-red" data-testid={`origin-delete-${b.id}`}><Trash2 className="w-4 h-4" /></button>
                                    </div>
                                </div>
                                <p className="text-[11px] text-muted-foreground mb-2 line-clamp-2">{b.desc}</p>
                                <div className="flex flex-wrap gap-1.5">
                                    <Pill tone="green">${b.cash} cash</Pill><Pill tone="cyan">${b.bank} bank</Pill>
                                    {b.debt > 0 && <Pill tone="red">${b.debt} debt</Pill>}
                                    {Object.entries(b.skills || {}).map(([s, v]) => <Pill key={s} tone="purple">{skillLabel(s)} +{v}</Pill>)}
                                    {Object.keys(b.inventory || {}).length > 0 && <Pill>{Object.keys(b.inventory).length} item(s)</Pill>}
                                </div>
                            </Panel>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}

export { PlayersTable, StatsView, CharacterOriginsPanel };
