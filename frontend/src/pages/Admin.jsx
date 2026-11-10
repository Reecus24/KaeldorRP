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

import { ContentEditor } from "./admin/shared";
import { Shield as ShieldRealm } from "lucide-react";
import JourneyStudio from "./admin/JourneyStudio";
import StorytellerDesk from "./admin/StorytellerDesk";
import WorldCharacters from "./admin/WorldCharacters";
import MapEditor from "./admin/MapEditor";
import { ConfigEditor, EconomyTuner, TuningPanel, MarketsPanel } from "./admin/EconomyPanels";
import { PlayersTable, StatsView, CharacterOriginsPanel } from "./admin/PlayerPanels";
import { LocationsPanel, CityShopsPanel, JobSectorsPanel, VehicleCategoriesPanel } from "./admin/CityPanels";
import { JobShiftsPanel, JobApplicationsPanel } from "./admin/JobPanels";
import { LiveCityFeed } from "./admin/OverviewPanels";

const ADMIN_GROUPS = [
    { key: "world", label: "Open World", icon: MapPin, children: [{ key: "world_intents", label: "Storyteller Desk" }, { key: "world_characters", label: "Characters & Memories" }, { key: "world_regions", label: "Map & Routes" }, { key: "world_npcs", label: "People & Routines" }, { key: "world_actions", label: "Actions & Dice" }, { key: "world_quests", label: "NPC Quests" }, { key: "world_professions", label: "Learned Professions" }, { key: "world_skills", label: "Skills" }, { key: "world_charters", label: "Founding Charters" }, { key: "world_origins", label: "Origin Picker" }] },
    { key: "realm", label: "Fantasy Realm", icon: ShieldRealm, children: [{ key: "realm_ranks", label: "Life Ranks" }, { key: "factions", label: "Factions & Ranks" }, { key: "expeditions", label: "Expeditions" }] },
    { key: "journey", label: "Stories & Goals", icon: Sparkles,
      children: [{ key: "journey_goals", label: "Ambitions" }, { key: "story_arcs", label: "Stories" }, { key: "city_events", label: "Realm Events" }] },
    { key: "overview", label: "Overview", icon: LayoutDashboard, locked: true,
      children: [{ key: "stats", label: "Village" }, { key: "feed", label: "Live Feed" }] },
    { key: "economy", label: "Economy", icon: DollarSign,
      children: [
          { key: "economy", label: "Economy Sandbox" }, { key: "business_types", label: "Workshops" },
          { key: "items", label: "Items" }, { key: "housing", label: "Housing" }, { key: "vehicles", label: "Mounts & Carts" }] },
    { key: "tuning", label: "Gameplay Tuning", icon: Gauge,
      children: [
          { key: "tuning", label: "Tuning" }, { key: "config", label: "Config" }, { key: "actions", label: "Actions" },
          { key: "courses", label: "Courses" }, { key: "jobs", label: "Jobs" }, { key: "jobshifts", label: "Job Shifts" }, { key: "jobapps", label: "Applications" }, { key: "random_events", label: "Events" }] },
    { key: "players", label: "Player Management", icon: Users,
      children: [
          { key: "players", label: "Players" }, { key: "origins", label: "Peasant Origins" }, { key: "employee_roles", label: "Emp Roles" }, { key: "employee_traits", label: "Emp Traits" },
          { key: "staffing_requirements", label: "Staffing" }, { key: "training_options", label: "Training" }, { key: "employee_events", label: "Staff Events" },
          { key: "npc_archetypes", label: "NPC Archetypes" }, { key: "social_traits", label: "Personality" },
          { key: "relationship_actions", label: "Rel. Actions" }, { key: "gift_types", label: "Gifts" }, { key: "social_events", label: "Social Events" }] },
    { key: "city", label: "Realm Stewardship", icon: Building2,
      children: [{ key: "cityshops", label: "Realm Shops" }, { key: "jobsectors", label: "Job Sectors" }, { key: "vehiclecats", label: "Stable Categories" }, { key: "locations", label: "Locations" }] },
    { key: "underworld", label: "Underworld & Stewardship", icon: Skull,
      children: [{ key: "illegal_actions", label: "Illegal" }, { key: "markets", label: "Markets" }] },
];
const cmoney = (n) => {
    const v = Number(n || 0);
    const a = Math.abs(v);
    const sign = v < 0 ? "-" : "";
    if (a >= 1e6) return `${sign}¤ ${(a / 1e6).toFixed(2)}M`;
    if (a >= 1e3) return `${sign}¤ ${(a / 1e3).toFixed(1)}K`;
    return money(v);
};
const ADMIN_SUMMARY = {
    overview: (m) => [
        { label: "Players", value: m.players_total, icon: Users },
        { label: "Employed", value: m.players_employed, icon: Briefcase },
        { label: "Workshops", value: m.businesses_total, icon: Building2 },
        { label: "Active Workers", value: m.active_workers, icon: Activity },
        { label: "Market Value", value: cmoney(m.market_value), icon: TrendingUp },
        { label: "Total Debt", value: cmoney(m.total_debt), icon: Wallet },
    ],
    economy: (m) => [
        { label: "Workshops", value: m.businesses_total, icon: Building2 },
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
        { label: "Realm Shops", value: `${m.shops_active}/${m.shops_total}`, icon: Store },
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
        case "world_regions": return <MapEditor />;
        case "world_characters": return <WorldCharacters />;
        case "world_intents": return <StorytellerDesk />;
        case "journey_goals":
        case "story_arcs":
        case "city_events": return <JourneyStudio key={key} kind={key} />;
        case "stats": return <StatsView />;
        case "feed": return <LiveCityFeed onPlayerClick={ctx.onFeedPlayerClick} />;
        case "economy": return <EconomyTuner />;
        case "tuning": return <TuningPanel />;
        case "config": return <ConfigEditor />;
        case "locations": return <LocationsPanel />;
        case "cityshops": return <CityShopsPanel />;
        case "jobsectors": return <JobSectorsPanel />;
        case "vehiclecats": return <VehicleCategoriesPanel />;
        case "jobshifts": return <JobShiftsPanel />;
        case "jobapps": return <JobApplicationsPanel />;
        case "markets": return <MarketsPanel />;
        case "origins": return <CharacterOriginsPanel />;
        case "players": return <PlayersTable focus={ctx.focusPlayer} onFocusHandled={ctx.onFocusHandled} />;
        default: return <ContentEditor ctype={key} />;
    }
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
            <SectionTitle icon={Settings} kicker="Game Master" title="Admin Village"
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
