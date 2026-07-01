import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { ShoppingCart, Coins } from "lucide-react";
import { cn } from "@/lib/utils";

const CAT_LABEL = { consumable: "Consumables", apparel: "Apparel", accessory: "Accessories", device: "Devices", gear: "Work & Fitness Gear", other: "Other" };

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
    const [items, setItems] = useState(null);
    const [busyId, setBusyId] = useState(null);

    useEffect(() => { api.get("/shop/items").then(({ data }) => setItems(data)).catch(() => setItems([])); }, []);

    const buy = async (it) => {
        setBusyId(it.id);
        await act(() => api.post("/shop/buy", { item_id: it.id, qty: 1 }), `${it.name} added to your Inventory`);
        setBusyId(null);
    };

    if (!items) return <Spinner />;
    const cats = [...new Set(items.map((i) => i.category))];

    return (
        <div className="space-y-6">
            <SectionTitle icon={ShoppingCart} kicker="Supermarket & store" title="Shop"
                sub="Buy consumables, apparel, devices and gear. Purchases go straight to your Inventory, where you can use or equip them." />

            {cats.map((cat) => (
                <div key={cat}>
                    <div className="font-mono text-[11px] uppercase tracking-[0.25em] text-neon-cyan/70 mb-3">{CAT_LABEL[cat] || cat}</div>
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {items.filter((i) => i.category === cat).map((it) => {
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
                </div>
            ))}
        </div>
    );
}
