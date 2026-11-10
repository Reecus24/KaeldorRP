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
    { key: "work", label: "Work & Hiring", types: "job,workshop" },
    { key: "crime", label: "Crime & Legal", types: "crime,legal,health" },
    { key: "finance", label: "Stewardship", types: "finance,bank" },
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

export { FEED_META, FEED_FILTERS, feedTimeAgo, LiveCityFeed };
