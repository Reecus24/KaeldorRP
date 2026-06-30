import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Money } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { ShoppingCart, Coins } from "lucide-react";
import { cn } from "@/lib/utils";

const CAT_LABEL = { consumable: "Consumables", wearable: "Apparel", gear: "Gear", social: "Social", other: "Other" };

export default function Shop() {
    const { player, act } = useGame();
    const [items, setItems] = useState(null);
    const [busyId, setBusyId] = useState(null);

    useEffect(() => { api.get("/shop/items").then(({ data }) => setItems(data)).catch(() => setItems([])); }, []);

    const buy = async (it) => {
        setBusyId(it.id);
        await act(() => api.post("/shop/buy", { item_id: it.id, qty: 1 }), `Bought ${it.name}`);
        setBusyId(null);
    };

    if (!items) return <Spinner />;
    const cats = [...new Set(items.map((i) => i.category))];

    return (
        <div className="space-y-6">
            <SectionTitle icon={ShoppingCart} kicker="Supermarket & store" title="Shop"
                sub="Quick boosts and gear. Consumables apply instantly; apparel raises mood and status." />

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
                                    <div className="flex flex-wrap gap-1 mb-3">
                                        {Object.entries(it.effects || {}).map(([k, v]) => (
                                            <span key={k} className={cn("font-mono text-[10px] px-1.5 py-0.5 rounded-sm border", v > 0 ? "text-neon-green border-neon-green/30" : "text-neon-red border-neon-red/30")}>
                                                {v > 0 ? "+" : ""}{v} {k.replace("_", " ")}
                                            </span>
                                        ))}
                                    </div>
                                    <KButton variant="green" className="w-full" disabled={!afford} loading={busyId === it.id} onClick={() => buy(it)} data-testid={`buy-${it.id}`}>
                                        <Coins className="w-3.5 h-3.5" /> {afford ? "Buy" : "Can't afford"}
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
