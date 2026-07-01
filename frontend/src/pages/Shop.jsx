import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { ShoppingCart, Coins, ArrowLeft, Store, ChevronRight, Building2, Clock, Lock, Tag, PackageX } from "lucide-react";
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

const fmtHours = (oh) => oh ? `${oh.open}–${oh.close}` : "08:00–20:00";

export default function Shop() {
    const { player, act } = useGame();
    const [stores, setStores] = useState(null);
    const [entered, setEntered] = useState(null);   // { shop, items, is_open_now }
    const [loadingItems, setLoadingItems] = useState(false);
    const [busyId, setBusyId] = useState(null);

    const loadStores = () => api.get("/shop/stores").then(({ data }) => setStores(data)).catch(() => setStores([]));
    useEffect(() => { loadStores(); }, []);

    const enter = async (s) => {
        setLoadingItems(true);
        try {
            const { data } = await api.get(`/shop/stores/${s.id}/items`);
            setEntered(data);
        } catch { setEntered({ shop: s, items: [], is_open_now: s.is_open_now }); }
        setLoadingItems(false);
    };

    const refreshEntered = async (storeId) => {
        try { const { data } = await api.get(`/shop/stores/${storeId}/items`); setEntered(data); } catch { /* ignore */ }
    };

    const buy = async (it, storeId) => {
        setBusyId(it.id);
        const r = await act(() => api.post("/shop/buy", { item_id: it.id, qty: 1, store_id: storeId }), `${it.name} added to your Inventory`);
        await refreshEntered(storeId);
        await loadStores();
        setBusyId(null);
        return r;
    };

    if (!stores) return <Spinner />;

    // ---- Inside a shop ----
    if (entered) {
        const s = entered.shop;
        const open = entered.is_open_now;
        return (
            <div className="space-y-5">
                <button onClick={() => setEntered(null)} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-white" data-testid="back-to-shops">
                    <ArrowLeft className="w-4 h-4" /> Back to City Shops
                </button>
                <div className="flex flex-wrap items-start justify-between gap-3">
                    <SectionTitle icon={Store} kicker={s.desc} title={s.name}
                        sub={s.business_type_name ? `A ${s.business_type_name}-type business. Everything here is ${s.category}.` : `Everything here is ${s.category}.`} />
                    <div className="flex flex-col items-end gap-1.5 pt-1">
                        <Pill tone={open ? "green" : "red"} data-testid="shop-open-status">
                            {open ? <Clock className="w-3 h-3 inline mr-1" /> : <Lock className="w-3 h-3 inline mr-1" />}
                            {open ? "Open now" : "Closed"}
                        </Pill>
                        <span className="text-[10px] font-mono text-muted-foreground/70">Hours {fmtHours(s.opening_hours)}</span>
                    </div>
                </div>
                {!open && (
                    <Panel className="p-4 border-neon-red/30 bg-neon-red/5 flex items-center gap-3" data-testid="shop-closed-banner">
                        <Lock className="w-5 h-5 text-neon-red shrink-0" />
                        <div className="text-sm text-white">This shop is <span className="text-neon-red font-bold">closed</span> right now. It opens daily {fmtHours(s.opening_hours)}. You can browse but can't buy until it reopens.</div>
                    </Panel>
                )}
                {loadingItems ? <Spinner /> : entered.items.length === 0 ? (
                    <Panel className="p-6 text-center text-sm text-muted-foreground">This shop has no stock right now.</Panel>
                ) : (
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {entered.items.map((it) => {
                            const soldOut = it.sold_out;
                            const afford = player.cash + player.bank >= it.price;
                            const canBuy = open && !soldOut && afford;
                            const label = !open ? "Closed" : soldOut ? "Sold out" : !afford ? "Can't afford" : "Buy to Inventory";
                            return (
                                <Panel key={it.id} className={cn("p-4 flex flex-col", (soldOut || !open) && "opacity-60")} data-testid={`shop-item-${it.id}`}>
                                    <div className="flex items-center justify-between mb-1">
                                        <h3 className="font-display font-bold text-white text-sm">{it.name}</h3>
                                        <div className="text-right leading-tight">
                                            {it.discount_pct > 0 && <span className="font-mono text-[10px] text-muted-foreground line-through mr-1">${it.base_price}</span>}
                                            <span className="font-mono text-neon-green tnum">${it.price}</span>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2 mb-2">
                                        {it.discount_pct > 0 && <span className="font-mono text-[9px] px-1.5 py-0.5 rounded-sm bg-neon-purple/15 text-neon-purple border border-neon-purple/30" data-testid={`sale-${it.id}`}><Tag className="w-2.5 h-2.5 inline mr-0.5" />−{it.discount_pct}%</span>}
                                        <span className={cn("font-mono text-[9px] uppercase tracking-wider", soldOut ? "text-neon-red" : "text-muted-foreground/70")} data-testid={`stock-${it.id}`}>
                                            {soldOut ? <><PackageX className="w-2.5 h-2.5 inline mr-0.5" />Out of stock</> : `${it.stock} in stock`}
                                        </span>
                                    </div>
                                    <p className="text-[11px] text-muted-foreground mb-3 flex-1">{it.desc}</p>
                                    <div className="mb-3">{it.slot ? <EquipPills equip={it.equip} /> : <EffectPills effects={it.effects} />}</div>
                                    <KButton variant="green" className="w-full" disabled={!canBuy} loading={busyId === it.id} onClick={() => buy(it, s.id)} data-testid={`buy-${it.id}`}>
                                        <Coins className="w-3.5 h-3.5" /> {label}
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
                sub="Pick a shop to browse its goods. Each store only stocks its own category and restocks at midnight. Shops have opening hours — you can only buy while they're open." />
            <div className="grid sm:grid-cols-2 gap-3" data-testid="shop-browser">
                {stores.map((s) => (
                    <Panel key={s.id} className="p-5 flex items-center gap-4 group cursor-pointer hover:border-neon-cyan/40 transition-colors" onClick={() => enter(s)} data-testid={`store-${s.id}`}>
                        <div className="w-11 h-11 rounded-sm bg-neon-cyan/10 border border-neon-cyan/20 flex items-center justify-center shrink-0">
                            <Store className="w-5 h-5 text-neon-cyan" />
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-display font-bold text-white">{s.name}</span>
                                {s.business_type_name && <Pill tone="green" className="!text-[9px]"><Building2 className="w-2.5 h-2.5 inline mr-0.5" />{s.business_type_name}</Pill>}
                                <Pill tone={s.is_open_now ? "cyan" : "red"} className="!text-[9px]" data-testid={`store-status-${s.id}`}>
                                    {s.is_open_now ? "Open" : "Closed"}
                                </Pill>
                                {s.on_sale && <Pill tone="purple" className="!text-[9px]"><Tag className="w-2.5 h-2.5 inline mr-0.5" />Sale</Pill>}
                            </div>
                            <p className="text-[11px] text-muted-foreground mt-0.5 truncate">{s.desc}</p>
                            <span className="text-[10px] font-mono text-muted-foreground/70 uppercase tracking-wider">{s.item_count} item{s.item_count === 1 ? "" : "s"} · {s.category} · {fmtHours(s.opening_hours)}</span>
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
