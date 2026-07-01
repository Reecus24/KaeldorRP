import { Link } from "react-router-dom";
import { useGame } from "@/context/GameContext";
import { Panel, SectionTitle, StatBar, StatTile, Money, Spinner, InfoTip } from "@/components/game/primitives";
import EventLog from "@/components/game/EventLog";
import { money, STAT_INFO, XP_INFO } from "@/lib/helpers";
import {
    LayoutDashboard, Home, Briefcase, GraduationCap, Skull, Store,
    TrendingUp, Gauge, Shield, AlertTriangle, Star, Activity,
} from "lucide-react";

const QUICK = [
    { to: "/home", label: "Home & Needs", icon: Home, desc: "Eat, sleep, rest, train" },
    { to: "/jobs", label: "Find Work", icon: Briefcase, desc: "Shifts & careers" },
    { to: "/education", label: "Study", icon: GraduationCap, desc: "Courses & degrees" },
    { to: "/business-market", label: "Business", icon: Store, desc: "Build an empire" },
    { to: "/underworld", label: "Underworld", icon: Skull, desc: "High risk, high reward" },
    { to: "/leaderboard", label: "Rankings", icon: TrendingUp, desc: "Climb the city" },
];

export default function Dashboard() {
    const { player, state } = useGame();
    if (!player) return <Spinner />;

    const nextXp = 250 * player.level;
    const xpPct = Math.min(100, (player.xp / nextXp) * 100);
    const nwb = state?.net_worth_breakdown;
    const nwInfo = nwb ? (
        <div className="space-y-0.5" data-testid="networth-breakdown">
            <div className="font-bold mb-1">Net worth = what you'd have if you cashed out</div>
            <div className="flex justify-between gap-4"><span>Cash</span><span>{money(nwb.cash)}</span></div>
            <div className="flex justify-between gap-4"><span>Bank</span><span>{money(nwb.bank)}</span></div>
            <div className="flex justify-between gap-4"><span>− Debt</span><span>-{money(nwb.debt)}</span></div>
            <div className="flex justify-between gap-4"><span>Vehicles (resale)</span><span>{money(nwb.vehicles)}</span></div>
            <div className="flex justify-between gap-4"><span>Property (est.)</span><span>{money(nwb.property)}</span></div>
            <div className="flex justify-between gap-4"><span>Businesses</span><span>{money(nwb.business)}</span></div>
            <div className="flex justify-between gap-4 border-t border-white/15 mt-1 pt-1 font-bold"><span>Total</span><span>{money(nwb.total)}</span></div>
        </div>
    ) : "Cash + Bank − Debt + Vehicles + Property + Business value.";

    return (
        <div className="space-y-6">
            <SectionTitle
                icon={LayoutDashboard}
                kicker={`Level ${player.level} · ${player.background}`}
                title={player.name}
                sub="Your life, in real time. Everything keeps running while you're away."
            />

            {/* Money tiles */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <StatTile label="Net Worth" value={money(state?.net_worth)} accent="#00FF66" testid="tile-networth" info={nwInfo} />
                <StatTile label="Cash" value={money(player.cash)} accent="#00F3FF" testid="tile-cash" />
                <StatTile label="Bank" value={money(player.bank)} accent="#00F3FF" testid="tile-bank" />
                <StatTile label="Debt" value={money(player.debt)} accent={player.debt > 0 ? "#FF0055" : "#9CA3AF"} testid="tile-debt" />
            </div>

            {/* Level + effectiveness */}
            <div className="grid md:grid-cols-2 gap-3">
                <Panel className="p-5">
                    <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                            <Star className="w-4 h-4 text-neon-yellow" />
                            <span className="font-display font-bold text-white">Level {player.level}</span>
                            <InfoTip text={XP_INFO} testid="xp-info" />
                        </div>
                        <span className="font-mono text-xs text-muted-foreground tnum">{Math.round(player.xp)} / {nextXp} XP</span>
                    </div>
                    <div className="h-2.5 bg-white/5 border border-white/10 rounded-sm overflow-hidden">
                        <div className="h-full" style={{ width: `${xpPct}%`, backgroundImage: "linear-gradient(90deg,#FFC300,#FF8A00)", boxShadow: "0 0 10px #FFC30088" }} />
                    </div>
                </Panel>
                <Panel className="p-5">
                    <div className="flex items-center gap-2 mb-3">
                        <Gauge className="w-4 h-4 text-neon-cyan" />
                        <span className="font-display font-bold text-white">Effectiveness</span>
                        <span className="font-mono text-xs text-muted-foreground ml-auto">how well you perform</span>
                    </div>
                    <div className="flex items-end gap-3">
                        <div className="font-display font-black text-3xl text-neon-cyan tnum" data-testid="effectiveness-value">
                            {Math.round((state?.effectiveness || 1) * 100)}%
                        </div>
                        <p className="text-xs text-muted-foreground pb-1">Low energy, high fatigue, hunger and stress reduce your pay and XP, and raise accident risk.</p>
                    </div>
                </Panel>
            </div>

            {/* Reputation / Status */}
            <Panel className="p-5">
                <div className="flex items-center gap-2 mb-4">
                    <Shield className="w-4 h-4 text-neon-cyan" />
                    <span className="font-display font-bold text-white">Standing in the City</span>
                </div>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <StatBar label="Reputation" value={player.reputation} color="#00FF66" info={STAT_INFO.reputation} testid="stat-reputation" />
                    <StatBar label="Legal Standing" value={player.legal_reputation} color="#00F3FF" info={STAT_INFO.legal_reputation} testid="stat-legal" />
                    <StatBar label="Criminal Suspicion" value={player.criminal_suspicion} color="#FFC300" invert info={STAT_INFO.criminal_suspicion} testid="stat-suspicion" />
                    <StatBar label="Social Status" value={player.social_status} color="#B026FF" info={STAT_INFO.social_status} testid="stat-social" />
                </div>
            </Panel>

            {/* Quick actions */}
            <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.25em] text-muted-foreground mb-3">Quick Access</div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {QUICK.map((q) => (
                        <Link key={q.to} to={q.to} data-testid={`quick-${q.to.replace("/", "")}`}>
                            <Panel className="p-4 hover:-translate-y-1 transition-transform hover:border-neon-cyan/40 h-full">
                                <q.icon className="w-5 h-5 text-neon-cyan mb-2" strokeWidth={1.6} />
                                <div className="font-display font-bold text-white text-sm">{q.label}</div>
                                <div className="text-[11px] text-muted-foreground mt-0.5">{q.desc}</div>
                            </Panel>
                        </Link>
                    ))}
                </div>
            </div>

            {/* Mobile log */}
            <div className="xl:hidden">
                <EventLog max={20} />
            </div>
        </div>
    );
}
