import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { SectionTitle, Spinner, Panel, Pill, StatBar, Money, EmptyState } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { money } from "@/lib/helpers";
import { Boxes, TrendingUp, TrendingDown, AlertTriangle, Hammer, Megaphone, Settings2 } from "lucide-react";
import { cn } from "@/lib/utils";

function activityInfo(act) {
    if (!act) return null;
    const start = new Date(act.started_at).getTime();
    const end = new Date(act.ends_at).getTime();
    const pct = Math.max(0, Math.min(100, ((Date.now() - start) / Math.max(1, end - start)) * 100));
    const remDays = Math.max(0, act.duration_days * (1 - pct / 100));
    const upgrade = act.type === "upgrade";
    return { upgrade, pct, remLabel: remDays < 0.1 ? "finishing…" : `${remDays.toFixed(1)}d left`, Icon: upgrade ? Hammer : Megaphone };
}

function BizCard({ b }) {
    const net = b.metrics?.net_day || 0;
    const ai = activityInfo(b.activity);
    const staff = (b.metrics?.employee_count || 0) + (b.metrics?.player_employee_count || 0);

    return (
        <Panel className={cn("p-5", b.bankrupt && "border-neon-red/50")} data-testid={`owned-biz-${b.id}`}>
            <div className="flex items-start justify-between gap-2 mb-3">
                <div>
                    <h3 className="font-display font-bold text-white text-lg leading-tight">{b.name}</h3>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <Pill tone="cyan">Lv {b.level}/{b.max_level}</Pill>
                        <Pill tone="purple">Mkt {b.marketing_level}</Pill>
                        {ai && <Pill tone={ai.upgrade ? "yellow" : "purple"}><ai.Icon className="w-3 h-3 mr-1" />{ai.upgrade ? "Upgrading" : "Campaign"}</Pill>}
                        {b.bankrupt && <Pill tone="red">Bankrupt</Pill>}
                    </div>
                </div>
                <div className="text-right">
                    <div className="text-[10px] uppercase text-muted-foreground font-mono">Net / day (est.)</div>
                    <div className={cn("font-mono text-lg tnum flex items-center gap-1 justify-end", net >= 0 ? "text-neon-green" : "text-neon-red")}>
                        {net >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                        {money(net)}
                    </div>
                </div>
            </div>

            {ai && (
                <div className="mb-3 border border-white/10 rounded-sm p-2.5" data-testid={`biz-activity-${b.id}`}>
                    <div className="flex items-center justify-between text-[11px] font-mono mb-1.5">
                        <span className="flex items-center gap-1.5 text-white"><ai.Icon className={cn("w-3.5 h-3.5", ai.upgrade ? "text-neon-yellow" : "text-neon-purple")} />
                            {ai.upgrade ? "Upgrading (income −50%)" : "Marketing campaign"}</span>
                        <span className="text-neon-cyan">{ai.remLabel}</span>
                    </div>
                    <div className="h-1.5 bg-white/8 rounded-full overflow-hidden">
                        <div className={cn("h-full transition-all", ai.upgrade ? "bg-neon-yellow" : "bg-neon-purple")} style={{ width: `${ai.pct}%` }} />
                    </div>
                </div>
            )}

            <div className="grid grid-cols-3 gap-2 text-[11px] font-mono mb-3">
                <div><div className="text-muted-foreground">Uncollected</div><Money value={b.cash} /></div>
                <div><div className="text-muted-foreground">Debt</div><span className="text-neon-red tnum">{money(b.debt)}</span></div>
                <div><div className="text-muted-foreground">Staff</div><span className="text-white tnum">{staff}</span></div>
            </div>

            <div className="mb-3"><StatBar label="Reputation" value={b.reputation} color="#00FF66" /></div>

            {b.metrics && (
                <div className="grid grid-cols-4 gap-2 text-center mb-3 py-2 border-y border-white/8">
                    <div><div className="text-[9px] uppercase text-muted-foreground">Active</div><div className={cn("font-mono text-sm", b.metrics.coverage >= 0.9 ? "text-neon-green" : b.metrics.coverage < 0.6 ? "text-neon-red" : "text-neon-yellow")}>{Math.round((b.metrics.coverage || 0) * 100)}%</div></div>
                    <div><div className="text-[9px] uppercase text-muted-foreground">Stock</div><div className="font-mono text-sm text-neon-purple">{Math.round(b.metrics.products_in_stock || 0)}</div></div>
                    <div><div className="text-[9px] uppercase text-muted-foreground">Satis.</div><div className="font-mono text-sm text-neon-cyan">{b.metrics.satisfaction}%</div></div>
                    <div><div className="text-[9px] uppercase text-muted-foreground">Total rev</div><div className="font-mono text-sm text-white" title="Lifetime revenue collected since purchase (not comparable to the per-day estimate)">{money(b.revenue_total)}</div></div>
                </div>
            )}
            {b.metrics && b.metrics.applicant_count > 0 && (
                <div className="text-[11px] text-neon-yellow font-mono mb-2">{b.metrics.applicant_count} applicant(s) waiting</div>
            )}
            {b.bankrupt && (
                <div className="flex items-center gap-1 text-[11px] text-neon-red font-mono mb-2"><AlertTriangle className="w-3 h-3" /> Open Manage to inject cash, revive, or sell.</div>
            )}

            <Link to={`/businesses/${b.id}`} className="block">
                <KButton variant="primary" className="w-full" data-testid={`manage-${b.id}`}><Settings2 className="w-3.5 h-3.5" /> Manage Business</KButton>
            </Link>
        </Panel>
    );
}

export default function OwnedBusinesses() {
    const [bizs, setBizs] = useState(null);

    const load = () => api.get("/businesses/owned").then(({ data }) => setBizs(data)).catch(() => setBizs([]));
    useEffect(() => { load(); }, []);

    if (!bizs) return <Spinner />;

    return (
        <div className="space-y-6">
            <SectionTitle icon={Boxes} kicker="Your empire" title="My Businesses"
                sub="A quick glance at each venture. Open Manage to collect profits, hire staff, upgrade, run marketing, buy materials or sell." />

            {bizs.length === 0 ? (
                <EmptyState icon={Boxes} title="You don't own any business yet" sub="Visit the Business Marketplace to buy your first venture." />
            ) : (
                <div className="grid md:grid-cols-2 gap-3">
                    {bizs.map((b) => <BizCard key={b.id} b={b} />)}
                </div>
            )}
            <Link to="/business-market"><KButton variant="ghost" data-testid="goto-market">Buy another business →</KButton></Link>
        </div>
    );
}
