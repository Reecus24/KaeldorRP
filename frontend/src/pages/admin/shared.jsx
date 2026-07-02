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
    const validity = useMemo(() => {
        if (!text.trim()) return { ok: false, msg: "Empty" };
        try { const v = JSON.parse(text); if (typeof v !== "object" || v === null || Array.isArray(v)) return { ok: false, msg: "Must be a JSON object" }; return { ok: true, msg: "Valid JSON" }; }
        catch (e) { return { ok: false, msg: e.message.replace(/^JSON\.parse:\s*/, "") }; }
    }, [text]);
    const prettify = () => { try { setText(JSON.stringify(JSON.parse(text), null, 2)); toast.success("Formatted"); } catch { toast.error("Can't format — invalid JSON"); } };
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
                    className={cn("flex-1 min-h-[340px] bg-[#050505] border rounded-sm p-3 font-mono text-xs text-neon-green/90 outline-none resize-none",
                        validity.ok ? "border-white/12 focus:border-neon-cyan/60" : "border-neon-red/50 focus:border-neon-red")}
                />
                <div className="flex items-center justify-between mt-2">
                    <span className={cn("text-[11px] font-mono flex items-center gap-1", validity.ok ? "text-neon-green/80" : "text-neon-red")} data-testid="json-validity">
                        {validity.ok ? <BadgeCheck className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}{validity.msg}
                    </span>
                    <button onClick={prettify} className="text-[11px] font-mono text-neon-cyan/80 hover:text-neon-cyan" data-testid="json-prettify">Format ⧉</button>
                </div>
                <div className="flex justify-end gap-2 mt-3">
                    <KButton variant="ghost" onClick={onClose}>Cancel</KButton>
                    <KButton variant="green" disabled={!validity.ok} onClick={() => {
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

export { CONTENT_TYPES, JsonModal, ContentEditor };
