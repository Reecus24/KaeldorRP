import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, InfoTip } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { ShoppingCart, Coins, Package, Check } from "lucide-react";
import { cn } from "@/lib/utils";

const CAT_LABEL = { consumable: "Consumables", wearable: "Apparel", gear: "Gear", social: "Social", other: "Other" };

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
    const [inventory, setInventory] = useState([]);
    const [busyId, setBusyId] = useState(null);

    const loadInventory = useCallback(() => api.get("/inventory").then(({ data }) => setInventory(data)).catch(() => setInventory([])), []);
    useEffect(() => { api.get("/shop/items").then(({ data }) => setItems(data)).catch(() => setItems([])); loadInventory(); }, [loadInventory]);

    const buy = async (it) => {
        setBusyId("buy" + it.id);
        await act(() => api.post("/shop/buy", { item_id: it.id, qty: 1 }), `${it.name} added to inventory`);
        await loadInventory();
        setBusyId(null);
    };
    const use = async (it) => {
        setBusyId("use" + it.id);
        await act(() => api.post(`/inventory/${it.id}/use`), `Used ${it.name}`);
        await loadInventory();
        setBusyId(null);
    };

    if (!items) return <Spinner />;
    const cats = [...new Set(items.map((i) => i.category))];

    return (
        <div className="space-y-6">
            <SectionTitle icon={ShoppingCart} kicker="Supermarket & store" title="Shop"
                sub="Buy items into your inventory — nothing is applied automatically. Head to your inventory and hit Use when you actually want the effect." />

            {/* INVENTORY */}
            <Panel className="p-5" data-testid="inventory-panel">
                <div className="flex items-center gap-1.5 mb-3">
                    <Package className="w-4 h-4 text-neon-cyan" />
                    <span className="font-display font-bold text-white">Your Inventory</span>
                    <InfoTip text="Items you own. Use a consumable or outfit to apply its effect (it's consumed). Gear like phones and laptops work passively just by owning them." testid="inventory-info" />
                </div>
                {inventory.length === 0 ? (
                    <div className="text-sm text-muted-foreground">Your inventory is empty. Buy something below.</div>
                ) : (
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {inventory.map((it) => (
                            <div key={it.id} className="border border-white/10 rounded-sm p-3 flex flex-col" data-testid={`inv-item-${it.id}`}>
                                <div className="flex items-center justify-between mb-1">
                                    <span className="font-display font-bold text-white text-sm">{it.name}</span>
                                    <Pill tone="cyan" data-testid={`inv-qty-${it.id}`}>x{it.qty}</Pill>
                                </div>
                                <div className="mb-3 flex-1"><EffectPills effects={it.effects} /></div>
                                {it.usable ? (
                                    <KButton variant="primary" className="w-full" loading={busyId === "use" + it.id} onClick={() => use(it)} data-testid={`use-${it.id}`}>
                                        <Check className="w-3.5 h-3.5" /> Use
                                    </KButton>
                                ) : (
                                    <div className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider py-2 text-center">Passive gear</div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </Panel>

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
                                    <div className="mb-3"><EffectPills effects={it.effects} /></div>
                                    <KButton variant="green" className="w-full" disabled={!afford} loading={busyId === "buy" + it.id} onClick={() => buy(it)} data-testid={`buy-${it.id}`}>
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
