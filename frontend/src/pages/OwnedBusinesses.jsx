import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, StatBar, Money, EmptyState } from "@/components/game/primitives";
import { KButton, KInput } from "@/components/game/controls";
import { money } from "@/lib/helpers";
import { Boxes, TrendingUp, TrendingDown, AlertTriangle, Megaphone, ArrowUpCircle, Users, Smile, Gauge, Settings2 } from "lucide-react";
import { cn } from "@/lib/utils";

function BizCard({ b, onAction, busyKey }) {
    const [inject, setInject] = useState("");
    const net = b.last_net_day || 0;

    return (
        <Panel className={cn("p-5", b.bankrupt && "border-neon-red/50")} data-testid={`owned-biz-${b.id}`}>
            <div className="flex items-start justify-between gap-2 mb-3">
                <div>
                    <h3 className="font-display font-bold text-white text-lg leading-tight">{b.name}</h3>
                    <div className="flex items-center gap-2 mt-1">
                        <Pill tone="cyan">Lv {b.level}/{b.max_level}</Pill>
                        <Pill tone="purple">Mkt {b.marketing_level}</Pill>
                        {b.bankrupt && <Pill tone="red">Bankrupt</Pill>}
                    </div>
                </div>
                <div className="text-right">
                    <div className="text-[10px] uppercase text-muted-foreground font-mono">Net / day</div>
                    <div className={cn("font-mono text-lg tnum flex items-center gap-1 justify-end", net >= 0 ? "text-neon-green" : "text-neon-red")}>
                        {net >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                        {money(net)}
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-3 gap-2 text-[11px] font-mono mb-3">
                <div><div className="text-muted-foreground">Uncollected</div><Money value={b.cash} /></div>
                <div><div className="text-muted-foreground">Debt</div><span className="text-neon-red tnum">{money(b.debt)}</span></div>
                <div><div className="text-muted-foreground">Total rev</div><span className="text-white tnum">{money(b.revenue_total)}</span></div>
            </div>

            <div className="mb-3"><StatBar label="Reputation" value={b.reputation} color="#00FF66" /></div>

            {b.metrics && (
                <div className="grid grid-cols-4 gap-2 text-center mb-3 py-2 border-y border-white/8">
                    <div><div className="text-[9px] uppercase text-muted-foreground">Staff</div><div className="font-mono text-sm text-white">{b.metrics.employee_count}</div></div>
                    <div><div className="text-[9px] uppercase text-muted-foreground">Coverage</div><div className={cn("font-mono text-sm", b.metrics.coverage >= 0.9 ? "text-neon-green" : b.metrics.coverage < 0.6 ? "text-neon-red" : "text-neon-yellow")}>{Math.round(b.metrics.coverage * 100)}%</div></div>
                    <div><div className="text-[9px] uppercase text-muted-foreground">Morale</div><div className="font-mono text-sm text-neon-purple">{b.metrics.morale_avg}%</div></div>
                    <div><div className="text-[9px] uppercase text-muted-foreground">Satis.</div><div className="font-mono text-sm text-neon-cyan">{b.metrics.satisfaction}%</div></div>
                </div>
            )}
            {b.metrics && b.metrics.applicant_count > 0 && (
                <div className="text-[11px] text-neon-yellow font-mono mb-2">{b.metrics.applicant_count} applicant(s) waiting</div>
            )}
            <Link to={`/businesses/${b.id}`}>
                <KButton variant="primary" className="w-full mb-2" data-testid={`manage-${b.id}`}><Settings2 className="w-3.5 h-3.5" /> Manage Staff & Details</KButton>
            </Link>

            {b.bankrupt ? (
                <div className="space-y-2">
                    <div className="flex items-center gap-1 text-[11px] text-neon-red font-mono"><AlertTriangle className="w-3 h-3" /> Pay off debt to revive, or sell for scrap.</div>
                    <div className="flex gap-2">
                        <KInput type="number" value={inject} onChange={(e) => setInject(e.target.value)} placeholder="Inject $" className="flex-1" />
                        <KButton variant="green" loading={busyKey === b.id + "inject"} onClick={() => onAction(b, "inject", Number(inject), () => setInject(""))}>Inject</KButton>
                    </div>
                    <KButton variant="danger" className="w-full" loading={busyKey === b.id + "sell"} onClick={() => onAction(b, "sell")}>Sell</KButton>
                </div>
            ) : (
                <>
                    <div className="grid grid-cols-2 gap-2 mb-2">
                        <KButton variant="green" loading={busyKey === b.id + "collect"} disabled={b.cash <= 0} onClick={() => onAction(b, "collect")} data-testid={`collect-${b.id}`}>
                            Collect {money(b.cash)}
                        </KButton>
                        <KButton variant="primary" loading={busyKey === b.id + "upgrade"} disabled={b.level >= b.max_level} onClick={() => onAction(b, "upgrade")} data-testid={`upgrade-${b.id}`}>
                            <ArrowUpCircle className="w-3.5 h-3.5" /> Upgrade
                        </KButton>
                        <KButton variant="purple" className="border border-neon-purple text-neon-purple hover:bg-neon-purple hover:text-white" loading={busyKey === b.id + "marketing"} onClick={() => onAction(b, "marketing")} data-testid={`marketing-${b.id}`}>
                            <Megaphone className="w-3.5 h-3.5" /> Market
                        </KButton>
                        <KButton variant="ghost" loading={busyKey === b.id + "sell"} onClick={() => onAction(b, "sell")} data-testid={`sell-biz-${b.id}`}>Sell</KButton>
                    </div>
                    {b.debt > 0 && (
                        <div className="flex gap-2 mt-2">
                            <KInput type="number" value={inject} onChange={(e) => setInject(e.target.value)} placeholder="Pay debt $" className="flex-1" />
                            <KButton variant="green" loading={busyKey === b.id + "inject"} onClick={() => onAction(b, "inject", Number(inject), () => setInject(""))}>Pay</KButton>
                        </div>
                    )}
                </>
            )}
        </Panel>
    );
}

export default function OwnedBusinesses() {
    const { act } = useGame();
    const [bizs, setBizs] = useState(null);
    const [busyKey, setBusyKey] = useState(null);

    const load = () => api.get("/businesses/owned").then(({ data }) => setBizs(data)).catch(() => setBizs([]));
    useEffect(() => { load(); }, []);

    const onAction = async (b, action, amount, clear) => {
        setBusyKey(b.id + action);
        let req;
        if (action === "inject") req = () => api.post(`/businesses/${b.id}/inject`, { amount });
        else req = () => api.post(`/businesses/${b.id}/${action}`);
        const r = await act(req, action.charAt(0).toUpperCase() + action.slice(1) + " done");
        await load();
        if (r.ok && clear) clear();
        setBusyKey(null);
    };

    if (!bizs) return <Spinner />;

    return (
        <div className="space-y-6">
            <SectionTitle icon={Boxes} kicker="Your empire" title="My Businesses"
                sub="Collect profits, upgrade to scale revenue, run marketing to boost reputation, and keep debt under control." />

            {bizs.length === 0 ? (
                <EmptyState icon={Boxes} title="You don't own any business yet" sub="Visit the Business Marketplace to buy your first venture." />
            ) : (
                <div className="grid md:grid-cols-2 gap-3">
                    {bizs.map((b) => <BizCard key={b.id} b={b} onAction={onAction} busyKey={busyKey} />)}
                </div>
            )}
            <Link to="/business-market"><KButton variant="ghost" data-testid="goto-market">Buy another business →</KButton></Link>
        </div>
    );
}
