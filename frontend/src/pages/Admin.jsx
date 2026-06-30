import { useEffect, useState, useCallback } from "react";
import { api, errMessage } from "@/lib/api";
import { SectionTitle, Spinner, Panel, Pill, Money } from "@/components/game/primitives";
import { KButton, KInput } from "@/components/game/controls";
import { money } from "@/lib/helpers";
import { Settings, Plus, Pencil, Trash2, X, Database, Users, SlidersHorizontal } from "lucide-react";
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

function PlayersTable() {
    const [players, setPlayers] = useState(null);
    useEffect(() => { api.get("/admin/players").then(({ data }) => setPlayers(data)); }, []);
    if (!players) return <Spinner />;
    return (
        <Panel className="p-0 overflow-hidden">
            <div className="grid grid-cols-12 gap-2 px-4 py-3 border-b border-white/8 bg-[#050505] font-mono text-[10px] uppercase text-muted-foreground">
                <div className="col-span-3">Name</div><div className="col-span-1">Lvl</div><div className="col-span-2 text-right">Cash</div>
                <div className="col-span-2 text-right">Net Worth</div><div className="col-span-2">Status</div><div className="col-span-2 text-right">Rep</div>
            </div>
            {players.map((p) => (
                <div key={p.id} className="grid grid-cols-12 gap-2 px-4 py-2.5 border-b border-white/5 text-sm items-center">
                    <div className="col-span-3 text-white truncate">{p.name}</div>
                    <div className="col-span-1 font-mono tnum">{p.level}</div>
                    <div className="col-span-2 text-right font-mono"><Money value={p.cash} /></div>
                    <div className="col-span-2 text-right font-mono"><Money value={p.net_worth} /></div>
                    <div className="col-span-2"><Pill>{p.status}</Pill></div>
                    <div className="col-span-2 text-right font-mono tnum text-muted-foreground">{Math.round(p.reputation)}</div>
                </div>
            ))}
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

export default function Admin() {
    const [tab, setTab] = useState("stats");

    return (
        <div className="space-y-6">
            <SectionTitle icon={Settings} kicker="Game Master" title="Admin Dashboard"
                sub="Create and balance every part of Kaeldor — jobs, actions, courses, items, housing, vehicles, businesses, crimes, events and global config." />

            <div className="flex flex-wrap gap-2">
                <TabBtn active={tab === "stats"} onClick={() => setTab("stats")} icon={Database}>Stats</TabBtn>
                {CONTENT_TYPES.map((c) => <TabBtn key={c.key} active={tab === c.key} onClick={() => setTab(c.key)}>{c.label}</TabBtn>)}
                <TabBtn active={tab === "config"} onClick={() => setTab("config")} icon={SlidersHorizontal}>Config</TabBtn>
                <TabBtn active={tab === "players"} onClick={() => setTab("players")} icon={Users}>Players</TabBtn>
            </div>

            <div>
                {tab === "stats" && <StatsView />}
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
