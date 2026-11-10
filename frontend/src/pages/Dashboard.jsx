import { Link } from "react-router-dom";
import { useGame } from "@/context/GameContext";
import { Panel, StatBar, StatTile, Spinner } from "@/components/game/primitives";
import EventLog from "@/components/game/EventLog";
import { money, STAT_INFO } from "@/lib/helpers";
import { nextMove } from "@/lib/nextMove";
import { JourneyTeaser } from "@/pages/Journey";
import { Wheat, Swords, Store, ArrowRight, ScrollText, Shield, Crown } from "lucide-react";

const PATHS = [
    { to: "/jobs", name: "Earn your bread", label: "Fields & craft", icon: Wheat, desc: "Begin with work in the village. Learn a trade and earn a place in the guilds." },
    { to: "/realm", name: "Swear an oath", label: "Steel & allegiance", icon: Swords, desc: "Join the Crownwardens or the Thornbound. Prepare your gear and answer the call." },
    { to: "/business-market", name: "Build a legacy", label: "Trade & prosperity", icon: Store, desc: "Save for a stall, forge or inn. Hire skilled hands and grow a thriving workshop." },
];
export default function Dashboard() {
    const { player, state } = useGame();
    if (!player) return <Spinner />;
    const move = nextMove(player, state?.activity, state?.needs_rules);
    const standing = state?.realm_standing;
    const next = standing?.next;
    const nextXp = (state?.player_xp_per_level ?? 250) * player.level;
    return <div className="space-y-6">
        <section className="realm-banner" aria-label="Your life in the Ashen March">
            <div className="relative z-10 p-6 sm:p-9 max-w-[650px]">
                <div className="flex items-center gap-3 mb-5"><span className="realm-seal"><Wheat size={23} /></span><div><div className="realm-eyebrow">Kaeldor · The Ashen March</div><div className="text-xs text-muted-foreground mt-1">A life written in deeds</div></div></div>
                <div className="realm-eyebrow">{standing?.current?.name || "Peasant"} · Level {player.level}</div>
                <h1 className="font-display text-4xl sm:text-5xl text-white mt-2 leading-tight">{player.name}</h1>
                <p className="text-sm text-[#d6d1bc] mt-3 leading-relaxed max-w-md">{player.job ? "Your trade: " + player.job.title + ". " : "No master. No trade. A whole realm ahead of you. "}Every shift, friendship and expedition shapes who you become.</p>
                <div className="flex flex-wrap gap-3 mt-6"><Link className="realm-button" to={move.to}>{move.label}<ArrowRight size={16} /></Link><Link className="realm-button secondary" to="/journey"><ScrollText size={16} /> Open journal</Link></div>
            </div>
        </section>
        <Panel className="p-5 flex flex-col sm:flex-row gap-4 items-start sm:items-center" data-testid="next-move">
            <Shield className="text-neon-yellow shrink-0" size={24} /><div className="flex-1"><h2 className="font-display text-xl text-white">{move.title}</h2><p className="text-sm text-muted-foreground mt-1">{move.detail}</p></div><Link to={move.to} className="realm-text-link shrink-0">Go there <ArrowRight size={15} /></Link>
        </Panel>
        <section aria-label="Choose your path"><div className="flex items-center gap-3 mb-4"><span className="realm-eyebrow">Three roads. Your story.</span><span className="h-px bg-white/10 flex-1" /></div><div className="grid grid-cols-1 md:grid-cols-3 gap-4">{PATHS.map(path => <Link key={path.to} to={path.to} className="realm-path"><path.icon size={28} strokeWidth={1.4} /><span className="realm-eyebrow mt-4">{path.label}</span><h3 className="font-display">{path.name}</h3><p>{path.desc}</p><ArrowRight size={18} className="mt-5" /></Link>)}</div></section>
        <JourneyTeaser />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Panel className="p-5 sm:p-6"><div className="flex items-center gap-2 mb-4"><Crown size={18} className="text-neon-yellow" /><h2 className="font-display text-2xl text-white">Your place in the realm</h2></div><p className="text-sm text-muted-foreground">{standing?.current?.description}</p>
                {next ? <><div className="flex justify-between text-sm mt-5 mb-2"><span className="text-white">Next: {next.name}</span><span className="text-muted-foreground">Days & deeds</span></div><div className="space-y-3">{[["Life in the realm", standing.days, next.min_days, "real days"], ["Experience", player.level, next.min_level, "level"], ["Completed deeds", standing.deeds, next.min_deeds, "deeds"]].map(([label, value, target, unit]) => <div key={label}><div className="flex justify-between text-xs text-muted-foreground mb-1"><span>{label}</span><span>{Math.min(value, target)} / {target} {unit}</span></div><div className="h-1.5 bg-black/30 rounded overflow-hidden"><div className="h-full bg-neon-cyan" style={{ width: Math.min(100, target === 0 ? 100 : value / target * 100) + "%" }} /></div></div>)}</div><p className="text-xs text-muted-foreground mt-4">All three requirements must be met. Work, activities, study and expeditions count as deeds. Progress lasts; no daily streak is required.</p></> : <p className="text-neon-yellow text-sm mt-4">You have reached the highest standing currently written in the realm's charter.</p>}
            </Panel>
            <Panel className="p-5 sm:p-6"><h2 className="font-display text-2xl text-white mb-4">Purse & provisions</h2><div className="grid grid-cols-2 gap-4"><div><div className="realm-eyebrow">Coin in hand</div><strong className="font-display text-3xl text-neon-yellow" data-testid="tile-cash">{money(player.cash)}</strong></div><div><div className="realm-eyebrow">Guild vault</div><strong className="font-display text-3xl text-white" data-testid="tile-bank">{money(player.bank)}</strong></div></div><div className="flex justify-between mt-5 pt-4 border-t border-white/10 text-sm"><span className="text-muted-foreground">Debt</span><span className={player.debt > 0 ? "text-neon-red" : "text-white"}>{money(player.debt)}</span></div><div className="flex justify-between mt-2 text-sm"><span className="text-muted-foreground">Total wealth</span><span className="text-neon-green" data-testid="tile-networth">{money(state?.net_worth)}</span></div><p className="text-xs text-muted-foreground mt-3">Coin + vault + resale value of property, mounts, workshops and trade goods − debt.</p><Link to="/bank" className="realm-text-link mt-4">Visit the guild vault <ArrowRight size={14} /></Link></Panel>
        </div>
        <details className="kael-panel p-5"><summary className="cursor-pointer font-display text-xl text-white">Character ledger · experience, standing & effectiveness</summary><div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mt-5"><StatBar label={"Level " + player.level + " · " + Math.round(player.xp) + " / " + nextXp + " XP"} value={player.xp / nextXp * 100} color="#D1B579" /><StatTile label="Effectiveness" value={Math.round((state?.effectiveness ?? 1) * 100) + "%"} sub="Health, hunger, energy, fatigue and stress affect your work." /><StatBar label="Reputation" value={player.reputation} color="#8EB89B" info={STAT_INFO.reputation} /><StatBar label="Legal standing" value={player.legal_reputation} color="#D1B579" info={STAT_INFO.legal_reputation} /><StatBar label="Watch suspicion" value={player.criminal_suspicion} color="#D9B66B" invert info={STAT_INFO.criminal_suspicion} /><StatBar label="Social standing" value={player.social_status} color="#B6A0CC" info={STAT_INFO.social_status} /></div></details>
        <div className="2xl:hidden"><EventLog max={12} /></div>
    </div>;
}
