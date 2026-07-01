import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { ShoppingCart, Coins, ArrowLeft, Store, ChevronRight, Building2 } from "lucide-react";
import { cn } from "@/lib/utils";

function EquipPills({ equip }) {
    const LABELS = {
        work_effectiveness: (v) => `+${Math.round(v * 100)}% work performance`,
        social_success: (v) => `+${Math.round(v * 100)}% social success`,
        tip_rate: (v) => `+${Math.round(v * 100)}% tips`,
        health_regen: (v) => `+${v}/h health regen`,
        energy_drain_mult: (v) => `−${Math.round((1 - v) * 100)}% energy drain`,
        social_status_floor: (v) => `Social status ≥ ${v}`,
        reputation_floor: (v) => `Reputation ≥ ${v}`,
        mood_floor: (v) => `Mood ≥ ${v}`,
    };
    const entries = Object.entries(equip || {});
    if (entries.length === 0) return null;
    return (
        <div className="flex flex-wrap gap-1">
            {entries.map(([k, v]) => (
                <span key={k} className="font-mono text-[10px] px-1.5 py-0.5 rounded-sm border text-neon-cyan border-neon-cyan/30">
                    {LABELS[k] ? LABELS[k](v) : `${k} ${v}`}
                </span>
            ))}
        </div>
    );
}

function EffectPills({ effects }) {
    return (
        <div className="flex flex-wrap gap-1">
            {Object.entries(effects || {}).map(([k, v]) => (
                <span key={k} className={cn("font-mono text-[10px] px-1.5 py-0.5 rounded-sm border", v > 0 ? "text-neon-green border-neon-green/30" : "text-neon-red border-neon-red/30")}>
                    {v > 0 ? "+" : ""}{v} {k.replace("_", " ")}
                </span>
            ))}
        </div>
    );
}

export default function Shop() {
    const { player, act } = useGame();
    const [stores, setStores] = useState(null);
    const [entered, setEntered] = useState(null);   // { shop, items }
    const [loadingItems, setLoadingItems] = useState(false);
    const [busyId, setBusyId] = useState(null);

    useEffect(() => { api.get("/shop/stores").then(({ data }) => setStores(data)).catch(() => setStores([])); }, []);

    const enter = async (s) => {
        setLoadingItems(true);
        try {
            const { data } = await api.get(`/shop/stores/${s.id}/items`);
            setEntered(data);
        } catch { setEntered({ shop: s, items: [] }); }
        setLoadingItems(false);
    };

    const buy = async (it) => {
        setBusyId(it.id);
        await act(() => api.post("/shop/buy", { item_id: it.id, qty: 1 }), `${it.name} added to your Inventory`);
        setBusyId(null);
    };

    if (!stores) return <Spinner />;

    // ---- Inside a shop ----
    if (entered) {
        const s = entered.shop;
        return (
            <div className="space-y-5">
                <button onClick={() => setEntered(null)} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-white" data-testid="back-to-shops">
                    <ArrowLeft className="w-4 h-4" /> Back to City Shops
                </button>
                <SectionTitle icon={Store} kicker={s.desc} title={s.name}
                    sub={s.business_type_name ? `A ${s.business_type_name}-type business. Everything here is ${s.category}.` : `Everything here is ${s.category}.`} />
                {loadingItems ? <Spinner /> : entered.items.length === 0 ? (
                    <Panel className="p-6 text-center text-sm text-muted-foreground">This shop has no stock right now.</Panel>
                ) : (
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {entered.items.map((it) => {
                            const afford = player.cash + player.bank >= it.price;
                            return (
                                <Panel key={it.id} className="p-4 flex flex-col" data-testid={`shop-item-${it.id}`}>
                                    <div className="flex items-center justify-between mb-1">
                                        <h3 className="font-display font-bold text-white text-sm">{it.name}</h3>
                                        <span className="font-mono text-neon-green tnum">${it.price}</span>
                                    </div>
                                    <p className="text-[11px] text-muted-foreground mb-3 flex-1">{it.desc}</p>
                                    <div className="mb-3">{it.slot ? <EquipPills equip={it.equip} /> : <EffectPills effects={it.effects} />}</div>
                                    <KButton variant="green" className="w-full" disabled={!afford} loading={busyId === it.id} onClick={() => buy(it)} data-testid={`buy-${it.id}`}>
                                        <Coins className="w-3.5 h-3.5" /> {afford ? "Buy to Inventory" : "Can't afford"}
                                    </KButton>
                                </Panel>
                            );
                        })}
                    </div>
                )}
            </div>
        );
    }

    // ---- Shop browser ----
    return (
        <div className="space-y-5">
            <SectionTitle icon={ShoppingCart} kicker="Businesses around Kaeldor" title="City Shops"
                sub="Pick a shop to browse its goods. Each store only stocks its own category — groceries at the grocer, gear at the hardware store, and so on." />
            <div className="grid sm:grid-cols-2 gap-3" data-testid="shop-browser">
                {stores.map((s) => (
                    <Panel key={s.id} className="p-5 flex items-center gap-4 group cursor-pointer hover:border-neon-cyan/40 transition-colors" onClick={() => enter(s)} data-testid={`store-${s.id}`}>
                        <div className="w-11 h-11 rounded-sm bg-neon-cyan/10 border border-neon-cyan/20 flex items-center justify-center shrink-0">
                            <Store className="w-5 h-5 text-neon-cyan" />
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                                <span className="font-display font-bold text-white">{s.name}</span>
                                {s.business_type_name && <Pill tone="green" className="!text-[9px]"><Building2 className="w-2.5 h-2.5 inline mr-0.5" />{s.business_type_name}</Pill>}
                            </div>
                            <p className="text-[11px] text-muted-foreground mt-0.5 truncate">{s.desc}</p>
                            <span className="text-[10px] font-mono text-muted-foreground/70 uppercase tracking-wider">{s.item_count} item{s.item_count === 1 ? "" : "s"} · {s.category}</span>
                        </div>
                        <KButton variant="primary" onClick={(e) => { e.stopPropagation(); enter(s); }} data-testid={`enter-${s.id}`}>
                            Enter Shop <ChevronRight className="w-3.5 h-3.5" />
                        </KButton>
                    </Panel>
                ))}
            </div>
        </div>
    );
}
