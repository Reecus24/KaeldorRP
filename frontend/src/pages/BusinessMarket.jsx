import { worldLabel } from "@/lib/helpers";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, Money } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { money, money2 } from "@/lib/helpers";
import { Store, Lock, TrendingUp, Receipt } from "lucide-react";

const HERO = "https://images.unsplash.com/photo-1562447574-797880741dd1?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1ODB8MHwxfHNlYXJjaHwxfHxjeWJlcnB1bmslMjBuZW9uJTIwZGFzaGJvYXJkJTIwZWxlbWVudHN8ZW58MHx8fHwxNzgyNzg4NTY4fDA&ixlib=rb-4.1.0&q=85";

export default function BusinessMarket() {
    const { player, act } = useGame();
    const navigate = useNavigate();
    const [types, setTypes] = useState(null);
    const [busyId, setBusyId] = useState(null);

    useEffect(() => { api.get("/businesses/market").then(({ data }) => setTypes(data)).catch(() => setTypes([])); }, []);

    const buy = async (t) => {
        setBusyId(t.id);
        const r = await act(() => api.post(`/businesses/${t.id}/buy`), `Acquired ${t.name}!`);
        setBusyId(null);
        if (r.ok) navigate("/businesses");
    };

    if (!types) return <Spinner />;

    return (
        <div className="space-y-6">
            <div className="relative overflow-hidden rounded-sm border border-white/10">
                <img src={HERO} alt="" className="absolute inset-0 w-full h-full object-cover opacity-20" />
                <div className="absolute inset-0 bg-gradient-to-r from-[#101A16] via-[#101A16]/85 to-[#101A16]/40" />
                <div className="relative p-6">
                    <SectionTitle icon={Store} kicker="Build an empire" title="Workshop Marketplace"
                        sub="Buy a workshop and it earns (or loses) money around the clock — even offline. Upgrade and market it to grow, or watch debt drag it into bankruptcy." />
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {types.map((t) => {
                    const est = t.estimate || {};
                    const profit = est.profit_day ?? 0;
                    const costs = (est.material_day ?? 0) + (est.wage_day ?? 0);
                    const afford = player.cash + player.bank >= t.purchase_price;
                    return (
                        <Panel key={t.id} className="p-5 flex flex-col" data-testid={`biz-type-${t.id}`}>
                            <div className="flex items-start justify-between gap-2 mb-1">
                                <h3 className="font-display font-bold text-white leading-tight">{t.name}</h3>
                                <Pill tone="cyan">{worldLabel(t.category)}</Pill>
                            </div>
                            <p className="text-[11px] text-muted-foreground mb-3 flex-1">{t.desc}</p>

                            <div className="space-y-1 text-[11px] font-mono mb-2">
                                <div className="flex justify-between"><span className="text-muted-foreground">Price</span><span className="text-neon-green">¤ {t.purchase_price.toLocaleString()}</span></div>
                                <div className="flex justify-between"><span className="text-muted-foreground">Sells</span><span className="text-white">{est.product?.name} @ {money2(est.product?.price || 0)}</span></div>
                                <div className="flex justify-between"><span className="text-muted-foreground">Material / unit</span><span className="text-neon-yellow">{money2(est.material_cost_per_unit || 0)}</span></div>
                                <div className="flex justify-between"><span className="text-muted-foreground">Margin / unit</span><span className="text-neon-green">{money2(est.margin_per_unit || 0)}</span></div>
                            </div>
                            <div className="space-y-1 text-[11px] font-mono mb-2 border-t border-white/10 pt-2" title="Estimate assuming recommended staffing (1 shift/day each) and a fresh-workshop reputation of 50.">
                                <div className="text-[10px] uppercase tracking-wider text-neon-cyan/60">Est. / day at recommended staffing</div>
                                <div className="flex justify-between"><span className="text-muted-foreground">Revenue ({Math.round(est.sold_day || 0)} sold)</span><span className="text-neon-green">+{money(est.revenue_day || 0)}</span></div>
                                <div className="flex justify-between"><span className="text-muted-foreground">− Materials</span><span className="text-neon-yellow">−{money(est.material_day || 0)}</span></div>
                                <div className="flex justify-between"><span className="text-muted-foreground">− Wages</span><span className="text-neon-red">−{money(est.wage_day || 0)}</span></div>
                                <div className="flex justify-between border-t border-white/10 pt-1"><span className="text-muted-foreground">Est. profit/day</span><span className={profit >= 0 ? "text-neon-green" : "text-neon-red"} data-testid={`biz-profit-${t.id}`}>{profit >= 0 ? "+" : ""}{money(profit)}</span></div>
                            </div>
                            <p className="text-[10px] text-muted-foreground/70 mb-1">Assumes: {(est.staff_needed || []).map((s) => `${s.recommended}× ${worldLabel(s.role)}`).join(", ") || "1 worker"} on shift.</p>
                            <p className="text-[10px] text-muted-foreground/70 mb-3">No rent — you buy ingredients, staff produce & sell. Heralds/upgrades raise demand & output.</p>

                            {!t.qualified ? (
                                <div className="flex items-center gap-1 text-[11px] text-neon-yellow font-mono"><Lock className="w-3 h-3" /> {t.reason}</div>
                            ) : (
                                <KButton variant="green" className="w-full" disabled={!afford} loading={busyId === t.id} onClick={() => buy(t)} data-testid={`buy-biz-${t.id}`}>
                                    {afford ? "Acquire" : "Can't afford"}
                                </KButton>
                            )}
                        </Panel>
                    );
                })}
            </div>
        </div>
    );
}
