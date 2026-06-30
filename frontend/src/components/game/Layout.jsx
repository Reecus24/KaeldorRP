import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useGame } from "@/context/GameContext";
import { Money, StatBar, Pill } from "@/components/game/primitives";
import ActivityPanel from "@/components/game/ActivityPanel";
import EventLog from "@/components/game/EventLog";
import { NEED_META, statusLabel, statusColor, timeMode } from "@/lib/helpers";
import { cn } from "@/lib/utils";
import {
    LayoutDashboard, Home, Briefcase, BadgeCheck, GraduationCap, ShoppingCart,
    Landmark, Building2, Car, Store, Boxes, Sparkles, Skull, Stethoscope,
    Lock, Trophy, Settings, LogOut, Menu, X, Activity, Zap, Clock3,
} from "lucide-react";

const NAV = [
    { section: "Life" },
    { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/home", label: "Home & Needs", icon: Home },
    { to: "/skills", label: "Skills", icon: Sparkles },
    { section: "Work" },
    { to: "/jobs", label: "Job Center", icon: Briefcase },
    { to: "/current-job", label: "Current Job", icon: BadgeCheck },
    { to: "/education", label: "Education", icon: GraduationCap },
    { section: "Economy" },
    { to: "/shop", label: "Shop", icon: ShoppingCart },
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
    return (
        <nav className="px-3 py-2 space-y-0.5">
            {NAV.map((item, i) =>
                item.section ? (
                    <div key={i} className="px-3 pt-4 pb-1 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground/50">
                        {item.section}
                    </div>
                ) : (
                    <NavLink
                        key={item.to}
                        to={item.to}
                        end={item.end}
                        onClick={onNavigate}
                        data-testid={`nav-${item.label.toLowerCase().replace(/[^a-z]+/g, "-")}`}
                        className={({ isActive }) =>
                            cn(
                                "flex items-center gap-3 px-3 py-2 text-sm rounded-sm transition-all group border-l-2",
                                isActive
                                    ? "bg-neon-cyan/10 text-neon-cyan border-neon-cyan font-medium"
                                    : "text-muted-foreground hover:text-white hover:bg-white/5 border-transparent",
                            )
                        }
                    >
                        <item.icon className="w-4 h-4 shrink-0" strokeWidth={1.7} />
                        {item.label}
                    </NavLink>
                ),
            )}
            {isAdmin && (
                <>
                    <div className="px-3 pt-4 pb-1 font-mono text-[10px] uppercase tracking-[0.25em] text-neon-red/60">
                        Admin
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
                        Admin Dashboard
                    </NavLink>
                </>
            )}
        </nav>
    );
}

export default function Layout({ children }) {
    const { user, logout } = useAuth();
    const { player, state } = useGame();
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
                    <button className="lg:hidden text-white" onClick={() => setMobileNav(true)} data-testid="mobile-menu-button">
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
                                <span className="text-muted-foreground">NET <Money value={state?.net_worth} testid="topbar-networth" /></span>
                            </div>
                            <Pill tone={mode.tone} className="hidden sm:inline-flex" >
                                <Clock3 className="w-3 h-3 mr-1" /> {mode.label}
                            </Pill>
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
                <aside className="hidden lg:block w-60 shrink-0 border-r border-white/8 bg-[#080808] h-[calc(100vh-3.5rem)] sticky top-14 overflow-y-auto">
                    <NavItems isAdmin={isAdmin} />
                </aside>

                {/* MOBILE NAV DRAWER */}
                {mobileNav && (
                    <div className="fixed inset-0 z-50 lg:hidden" data-testid="mobile-nav-drawer">
                        <div className="absolute inset-0 bg-black/70" onClick={() => setMobileNav(false)} />
                        <div className="absolute left-0 top-0 h-full w-72 bg-[#080808] border-r border-white/10 overflow-y-auto animate-fade">
                            <div className="flex items-center justify-between px-4 h-14 border-b border-white/8">
                                <span className="font-display font-extrabold tracking-tighter">KAELDOR<span className="text-neon-cyan">.</span></span>
                                <button onClick={() => setMobileNav(false)}><X className="w-5 h-5 text-muted-foreground" /></button>
                            </div>
                            <NavItems isAdmin={isAdmin} onNavigate={() => setMobileNav(false)} />
                        </div>
                    </div>
                )}

                {/* MAIN */}
                <main className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8 max-w-[1100px] mx-auto w-full">
                    {/* Needs strip */}
                    {player && (
                        <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-7 gap-3 mb-6" data-testid="needs-strip">
                            {Object.entries(NEED_META).map(([key, meta]) => (
                                <StatBar
                                    key={key}
                                    label={meta.label}
                                    value={player[key]}
                                    color={meta.color}
                                    invert={meta.invert}
                                    testid={`need-${key}`}
                                />
                            ))}
                        </div>
                    )}

                    {/* Mobile activity (above content) */}
                    <div className="xl:hidden mb-6">
                        <ActivityPanel compact />
                    </div>

                    <div className="animate-fade">{children}</div>
                </main>

                {/* RIGHT RAIL */}
                <aside className="hidden xl:block w-80 shrink-0 border-l border-white/8 bg-[#080808] h-[calc(100vh-3.5rem)] sticky top-14 overflow-y-auto p-4 space-y-4">
                    <ActivityPanel />
                    <EventLog max={30} />
                </aside>
            </div>
        </div>
    );
}
