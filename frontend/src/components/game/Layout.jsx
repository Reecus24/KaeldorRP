import { useState } from "react";
import { NavLink, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useGame } from "@/context/GameContext";
import { Money, StatBar, Pill, InfoTip } from "@/components/game/primitives";
import ActivityPanel from "@/components/game/ActivityPanel";
import EventLog from "@/components/game/EventLog";
import ChatWidget from "@/components/game/ChatWidget";
import { NEED_META, needWarningThreshold, statusLabel, statusColor, timeMode, computeGameTime, fmtGameClock, STAT_INFO } from "@/lib/helpers";
import { cn } from "@/lib/utils";
import {
    LayoutDashboard, Home, Briefcase, BadgeCheck, GraduationCap, ShoppingCart,
    Landmark, Building2, Car, Store, Boxes, Sparkles, Skull, Stethoscope,
    Lock, Trophy, Settings, LogOut, Menu, X, Activity, Zap, Clock3, Users,
    Bell, ScrollText, CalendarClock, MessageSquare, Backpack, Search, ChevronDown,
} from "lucide-react";

const NAV = [
    { section: "Life" },
    { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/home", label: "Home & Needs", icon: Home },
    { to: "/skills", label: "Skills", icon: Sparkles },
    { to: "/social", label: "Social", icon: Users },
    { to: "/messages", label: "Messages", icon: MessageSquare },
    { to: "/daily-summary", label: "Daily Summary", icon: ScrollText },
    { section: "Work" },
    { to: "/jobs", label: "Job Center", icon: Briefcase },
    { to: "/current-job", label: "Current Job", icon: BadgeCheck },
    { to: "/job-market", label: "Player Jobs", icon: Store },
    { to: "/education", label: "Education", icon: GraduationCap },
    { section: "Economy" },
    { to: "/shop", label: "Shop", icon: ShoppingCart },
    { to: "/inventory", label: "Inventory", icon: Backpack },
    { to: "/bank", label: "Bank & Loans", icon: Landmark },
    { to: "/real-estate", label: "Real Estate", icon: Building2 },
    { to: "/vehicles", label: "Vehicle Dealer", icon: Car },
    { section: "Business" },
    { to: "/business-market", label: "Buy a Business", icon: Store },
    { to: "/businesses", label: "My Businesses", icon: Boxes },
    { section: "Risk & Status" },
    { to: "/underworld", label: "Underworld", icon: Skull },
    { to: "/legal", label: "Police Record", icon: Lock },
    { to: "/hospital", label: "Hospital", icon: Stethoscope },
    { to: "/jail", label: "Jail", icon: Lock },
    { to: "/leaderboard", label: "Leaderboard", icon: Trophy },
];

function NavItems({ onNavigate, isAdmin }) {
    const { msgUnread } = useGame();
    const { pathname } = useLocation();
    const [query, setQuery] = useState("");
    const [collapsed, setCollapsed] = useState({});
    const groups = [];
    NAV.forEach((item) => {
        if (item.section) groups.push({ name: item.section, items: [] });
        else groups[groups.length - 1].items.push(item);
    });
    const matches = (label) => label.toLowerCase().includes(query.trim().toLowerCase());
    const visibleGroups = groups.map((group) => ({ ...group, items: group.items.filter((item) => matches(item.label) || matches(group.name)) }))
        .filter((group) => group.items.length);
    return (
        <nav className="px-3 py-4 space-y-1" aria-label="Game navigation">
            <label className="flex items-center gap-2 px-3 py-2.5 border border-white/15 rounded-sm mb-4 bg-black/30">
                <Search className="w-4 h-4 text-muted-foreground shrink-0" />
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find a place…" aria-label="Search navigation"
                    className="min-w-0 w-full bg-transparent text-sm text-white outline-none placeholder:text-muted-foreground/70" />
            </label>
            {visibleGroups.map((group) => {
                const currentGroup = group.items.some((item) => item.to === "/" ? pathname === "/" : pathname.startsWith(item.to));
                const expanded = query.trim() || !(collapsed[group.name] ?? (!currentGroup && !["Life", "Work"].includes(group.name)));
                return (
                <div key={group.name}>
                    <button type="button" onClick={() => setCollapsed((old) => ({ ...old, [group.name]: !!expanded }))}
                        aria-expanded={!!expanded} className="w-full flex items-center justify-between px-3 py-3 text-xs font-mono uppercase tracking-widest text-muted-foreground hover:text-white">
                        {group.name}<ChevronDown className={cn("w-3.5 h-3.5 transition-transform", !expanded && "-rotate-90")} />
                    </button>
                    {expanded && group.items.map((item) => (
                    <NavLink
                        key={item.to}
                        to={item.to}
                        end={item.end}
                        onClick={onNavigate}
                        data-testid={`nav-${item.label.toLowerCase().replace(/[^a-z]+/g, "-")}`}
                        className={({ isActive }) =>
                            cn(
                                "flex min-h-[42px] items-center gap-3 px-3 py-2 text-sm rounded-sm transition-colors group border-l-2",
                                isActive
                                    ? "bg-neon-cyan/10 text-neon-cyan border-neon-cyan font-medium"
                                    : "text-muted-foreground hover:text-white hover:bg-white/5 border-transparent",
                            )
                        }
                    >
                        <item.icon className="w-4 h-4 shrink-0" strokeWidth={1.7} />
                        {item.to === "/messages" && msgUnread > 0 && (
                            <span data-testid="nav-messages-badge" className="min-w-[18px] h-[18px] px-1 rounded-full bg-[#EF4444] text-[10px] font-bold text-white flex items-center justify-center shadow-[0_0_8px_rgba(239,68,68,0.7)] shrink-0">{msgUnread > 9 ? "9+" : msgUnread}</span>
                        )}
                        <span className="flex-1">{item.label}</span>
                    </NavLink>
                    ))}
                </div>
                );
            })}
            {!visibleGroups.length && !(isAdmin && matches("Owner Sandbox Admin")) && <p className="text-sm text-muted-foreground px-3 py-4">No places match your search.</p>}
            {isAdmin && (!query.trim() || matches("Owner Sandbox Admin")) && (
                <>
                    <div className="px-3 pt-5 pb-2 font-mono text-xs uppercase tracking-widest text-neon-purple">
                        Owner Tools
                    </div>
                    <NavLink
                        to="/admin"
                        onClick={onNavigate}
                        data-testid="nav-admin"
                        className={({ isActive }) =>
                            cn(
                                "flex items-center gap-3 px-3 py-2 text-sm rounded-sm transition-all border-l-2",
                                isActive
                                    ? "bg-neon-red/10 text-neon-red border-neon-red font-medium"
                                    : "text-muted-foreground hover:text-white hover:bg-white/5 border-transparent",
                            )
                        }
                    >
                        <Settings className="w-4 h-4 shrink-0" strokeWidth={1.7} />
                        Owner Sandbox
                    </NavLink>
                </>
            )}
        </nav>
    );
}

function NotificationBell() {
    const navigate = useNavigate();
    const { notifications, unreadCount, markNotificationsRead } = useGame();
    const [open, setOpen] = useState(false);
    const items = notifications?.items || [];
    const sev = { success: "text-neon-green", info: "text-neon-cyan", warning: "text-neon-yellow", danger: "text-neon-red" };

    const onItem = (n) => {
        setOpen(false);
        if (!n.read) markNotificationsRead([n.id]);
        if (n.link) navigate(n.link);
    };

    return (
        <div className="relative">
            <button onClick={() => setOpen((o) => !o)} data-testid="notifications-button"
                className="relative text-muted-foreground hover:text-neon-cyan transition-colors" title="Notifications">
                <Bell className="w-4 h-4" />
                {unreadCount > 0 && (
                    <span data-testid="notif-unread-count" className="absolute -top-1.5 -right-1.5 min-w-[15px] h-[15px] px-0.5 rounded-full bg-[#EF4444] text-[9px] font-bold text-white flex items-center justify-center ring-2 ring-[#0A0A0A]">
                        {unreadCount > 9 ? "9+" : unreadCount}
                    </span>
                )}
            </button>
            {open && (
                <>
                    <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
                    <div className="absolute right-0 mt-2 w-80 max-h-[70vh] overflow-y-auto z-50 bg-[#0C0C0C] border border-white/12 rounded-sm shadow-2xl" data-testid="notifications-dropdown">
                        <div className="flex items-center justify-between px-3 py-2 border-b border-white/8 sticky top-0 bg-[#0C0C0C]">
                            <span className="font-display font-bold text-white text-sm">Notifications</span>
                            {unreadCount > 0 && (
                                <button onClick={() => markNotificationsRead()} className="text-[11px] text-neon-cyan hover:underline" data-testid="notif-mark-all-read">Mark all read</button>
                            )}
                        </div>
                        {items.length === 0 ? (
                            <div className="px-3 py-8 text-center text-muted-foreground text-xs font-mono">No notifications yet.</div>
                        ) : items.map((n) => (
                            <button key={n.id} onClick={() => onItem(n)} data-testid={`notif-item-${n.id}`}
                                className={cn("w-full text-left px-3 py-2.5 border-b border-white/5 hover:bg-white/5 transition-colors", !n.read && "bg-neon-cyan/[0.04]")}>
                                <div className="flex items-center gap-2">
                                    {!n.read && <span className="w-1.5 h-1.5 rounded-full bg-neon-cyan shrink-0" />}
                                    <span className={cn("font-display font-bold text-xs", sev[n.severity] || "text-white")}>{n.title}</span>
                                </div>
                                {n.body && <div className="text-[11px] text-muted-foreground mt-0.5 pl-3.5">{n.body}</div>}
                                <div className="text-[9px] text-muted-foreground/50 font-mono mt-0.5 pl-3.5">{new Date(n.ts).toLocaleString()}</div>
                            </button>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}

function GameClock() {
    const { state, tick } = useGame();
    void tick; // re-render every second
    const gt = computeGameTime(state);
    const c = fmtGameClock(gt, state);
    if (!gt) return null;
    return (
        <div className="hidden sm:flex flex-col items-end leading-none font-mono" data-testid="game-clock" title={c.date}>
            <span className="text-neon-cyan text-sm tnum tracking-wide">{c.time}</span>
            <span className="text-[9px] text-muted-foreground uppercase tracking-wider">{c.day}</span>
        </div>
    );
}

export default function Layout({ children }) {
    const { user, logout } = useAuth();
    const { player, state, stateError, refresh } = useGame();
    const navigate = useNavigate();
    const [mobileNav, setMobileNav] = useState(false);

    const isAdmin = user?.role === "admin";
    const status = player?.status || "free";
    const mode = timeMode(state?.time_scale || 1);

    const doLogout = async () => {
        await logout();
        navigate("/login");
    };

    return (
        <div className="min-h-screen bg-[#050505] kael-grid text-foreground">
            {/* TOP BAR */}
            <header className="sticky top-0 z-40 bg-[#0A0A0A]/90 backdrop-blur-md border-b border-white/8">
                <div className="flex items-center gap-3 px-4 h-14">
                    <button className="lg:hidden text-white p-2 -ml-2" aria-label="Open navigation" onClick={() => setMobileNav(true)} data-testid="mobile-menu-button">
                        <Menu className="w-5 h-5" />
                    </button>
                    <div className="flex items-center gap-2 mr-2">
                        <Zap className="w-5 h-5 text-neon-cyan" />
                        <span className="font-display font-extrabold tracking-tighter text-lg hidden sm:block">
                            KAELDOR<span className="text-neon-cyan">.</span>
                        </span>
                    </div>

                    {/* Money strip */}
                    {player && (
                        <div className="flex items-center gap-3 sm:gap-5 ml-auto">
                            <div className="hidden md:flex items-center gap-4 font-mono text-xs">
                                <span className="text-muted-foreground">CASH <Money value={player.cash} testid="topbar-cash" /></span>
                                <span className="text-muted-foreground">BANK <Money value={player.bank} testid="topbar-bank" /></span>
                                <span className="text-muted-foreground">DEBT <span className="text-neon-red tnum">${Math.round(player.debt).toLocaleString()}</span></span>
                                <span className="text-muted-foreground inline-flex items-center gap-1">NET <Money value={state?.net_worth} testid="topbar-networth" /><InfoTip text="NET = Cash + Bank - Debt + 50% Asset Resell Value." testid="networth-info" /></span>
                            </div>
                            <Pill tone={mode.tone} className="hidden sm:inline-flex" >
                                <Clock3 className="w-3 h-3 mr-1" /> {mode.label}
                            </Pill>
                            <GameClock />
                            <NotificationBell />
                            <Pill tone={status === "free" ? "green" : status === "jail" || status === "hospital" ? "red" : "cyan"}>
                                <span className={cn("w-1.5 h-1.5 rounded-full mr-1", status === "free" ? "bg-neon-green" : "bg-neon-cyan animate-pulse-dot")} />
                                {statusLabel(status)}
                            </Pill>
                            <button
                                onClick={doLogout}
                                data-testid="logout-button"
                                className="text-muted-foreground hover:text-neon-red transition-colors"
                                title="Logout"
                            >
                                <LogOut className="w-4 h-4" />
                            </button>
                        </div>
                    )}
                </div>
                {/* Mobile money strip */}
                {player && (
                    <div className="md:hidden flex items-center gap-4 px-4 py-1.5 border-t border-white/5 font-mono text-[11px] overflow-x-auto">
                        <span className="text-muted-foreground">CASH <Money value={player.cash} /></span>
                        <span className="text-muted-foreground">BANK <Money value={player.bank} /></span>
                        <span className="text-muted-foreground">NET <Money value={state?.net_worth} /></span>
                    </div>
                )}
            </header>

            <div className="flex">
                {/* SIDEBAR (desktop) */}
                <aside className="hidden lg:block w-64 shrink-0 border-r border-white/8 bg-[#080808] h-[calc(100vh-3.5rem)] sticky top-14 overflow-y-auto">
                    <NavItems isAdmin={isAdmin} />
                </aside>

                {/* MOBILE NAV DRAWER */}
                {mobileNav && (
                    <div className="fixed inset-0 z-50 lg:hidden" data-testid="mobile-nav-drawer">
                        <div className="absolute inset-0 bg-black/70" onClick={() => setMobileNav(false)} />
                        <div className="absolute left-0 top-0 h-full w-72 bg-[#080808] border-r border-white/10 overflow-y-auto animate-fade">
                            <div className="flex items-center justify-between px-4 h-14 border-b border-white/8">
                                <span className="font-display font-extrabold tracking-tighter">KAELDOR<span className="text-neon-cyan">.</span></span>
                                <button aria-label="Close navigation" className="p-2" onClick={() => setMobileNav(false)}><X className="w-5 h-5 text-muted-foreground" /></button>
                            </div>
                            <NavItems isAdmin={isAdmin} onNavigate={() => setMobileNav(false)} />
                        </div>
                    </div>
                )}

                {/* MAIN */}
                <main className="flex-1 min-w-0 p-4 pb-24 sm:p-6 sm:pb-24 lg:p-8 lg:pb-24 max-w-[1100px] mx-auto w-full">
                    {stateError && (
                        <div role="alert" className="mb-5 p-4 rounded-sm border border-neon-yellow/40 bg-neon-yellow/5 text-sm">
                            <p className="text-neon-yellow">{stateError} Displayed values may be out of date.</p>
                            <button type="button" onClick={refresh} className="text-white underline mt-2">Retry now</button>
                        </div>
                    )}
                    {/* Needs strip */}
                    {player && (
                        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-x-5 gap-y-4 mb-6 p-4 bg-[#0d1115]/90 border border-white/10 rounded-sm" data-testid="needs-strip">
                            {Object.entries(NEED_META).map(([key, meta]) => (
                                <StatBar
                                    key={key}
                                    label={meta.label}
                                    value={player[key]}
                                    color={meta.color}
                                    invert={meta.invert}
                                    warningThreshold={needWarningThreshold(key, state?.needs_rules)}
                                    showDirection
                                    info={STAT_INFO[key]}
                                    testid={`need-${key}`}
                                />
                            ))}
                        </div>
                    )}

                    {/* Mobile activity (above content) */}
                    <div className="2xl:hidden mb-6">
                        <ActivityPanel compact />
                    </div>

                    <div className="animate-fade">{children}</div>
                </main>

                {/* RIGHT RAIL */}
                <aside className="hidden 2xl:block w-80 shrink-0 border-l border-white/8 bg-[#080808] h-[calc(100vh-3.5rem)] sticky top-14 overflow-y-auto p-4 space-y-4">
                    <ActivityPanel />
                    <EventLog max={30} />
                </aside>
            </div>
            <ChatWidget />
        </div>
    );
}
