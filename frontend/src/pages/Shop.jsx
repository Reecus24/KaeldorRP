import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, InfoTip } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { ShoppingCart, Coins, Package, Check, Shield, Shirt, Watch, Smartphone, Laptop, Dumbbell, X } from "lucide-react";
import { cn } from "@/lib/utils";

const CAT_LABEL = { consumable: "Consumables", apparel: "Apparel", accessory: "Accessories", device: "Devices", gear: "Work & Fitness Gear", other: "Other" };
const SLOT_ICON = { outfit: Shirt, accessory: Watch, phone: Smartphone, computer: Laptop, work_gear: Dumbbell };

const EQUIP_LABELS = {
    work_effectiveness: (v) => `+${Math.round(v * 100)}% work performance`,
    social_success: (v) => `+${Math.round(v * 100)}% social success`,
    tip_rate: (v) => `+${Math.round(v * 100)}% tips`,
    health_regen: (v) => `+${v}/h health regen`,
    energy_drain_mult: (v) => `−${Math.round((1 - v) * 100)}% energy drain`,
    social_status_floor: (v) => `Social status ≥ ${v}`,
    reputation_floor: (v) => `Reputation ≥ ${v}`,
    mood_floor: (v) => `Mood ≥ ${v}`,
};

function EquipPills({ equip }) {
    const entries = Object.entries(equip || {});
    if (entries.length === 0) return null;
    return (
        <div className="flex flex-wrap gap-1">
            {entries.map(([k, v]) => (
                <span key={k} className="font-mono text-[10px] px-1.5 py-0.5 rounded-sm border text-neon-cyan border-neon-cyan/30">
                    {EQUIP_LABELS[k] ? EQUIP_LABELS[k](v) : `${k} ${v}`}
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
    const [inventory, setInventory] = useState([]);
    const [equipment, setEquipment] = useState(null);
    const [busyId, setBusyId] = useState(null);

    const loadInventory = useCallback(() => api.get("/inventory").then(({ data }) => setInventory(data)).catch(() => setInventory([])), []);
    const loadEquipment = useCallback(() => api.get("/equipment").then(({ data }) => setEquipment(data)).catch(() => setEquipment(null)), []);
    useEffect(() => {
        api.get("/shop/items").then(({ data }) => setItems(data)).catch(() => setItems([]));
        loadInventory();
        loadEquipment();
    }, [loadInventory, loadEquipment]);

    const refreshAll = async () => { await Promise.all([loadInventory(), loadEquipment()]); };

    const buy = async (it) => {
        setBusyId("buy" + it.id);
        await act(() => api.post("/shop/buy", { item_id: it.id, qty: 1 }), `${it.name} added to inventory`);
        await refreshAll();
        setBusyId(null);
    };
    const use = async (it) => {
        setBusyId("use" + it.id);
        await act(() => api.post(`/inventory/${it.id}/use`), `Used ${it.name}`);
        await refreshAll();
        setBusyId(null);
    };
    const equip = async (it) => {
        setBusyId("eq" + it.id);
        await act(() => api.post(`/inventory/${it.id}/equip`), `Equipped ${it.name}`);
        await refreshAll();
        setBusyId(null);
    };
    const unequip = async (slot) => {
        setBusyId("uneq" + slot);
        await act(() => api.post(`/equipment/${slot}/unequip`), `Unequipped`);
        await refreshAll();
        setBusyId(null);
    };

    if (!items) return <Spinner />;
    const cats = [...new Set(items.map((i) => i.category))];

    return (
        <div className="space-y-6">
            <SectionTitle icon={ShoppingCart} kicker="Supermarket & store" title="Shop & Inventory"
                sub="Buy consumables for instant effects, or apparel, devices and gear you can equip for permanent passive bonuses while worn." />

            {/* EQUIPMENT */}
            <Panel className="p-5" data-testid="equipment-panel">
                <div className="flex items-center gap-1.5 mb-3">
                    <Shield className="w-4 h-4 text-neon-purple" />
                    <span className="font-display font-bold text-white">Equipment</span>
                    <InfoTip text="Equip apparel, a device and gear into their slots. Equipped items give passive bonuses (work performance, social success, tips, stat floors, recovery) as long as they're worn." testid="equipment-info" />
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                    {(equipment?.slots || []).map((s) => {
                        const Icon = SLOT_ICON[s.slot] || Shield;
                        return (
                            <div key={s.slot} className={cn("border rounded-sm p-3 flex flex-col items-center text-center min-h-[130px]", s.item ? "border-neon-purple/40 bg-neon-purple/5" : "border-white/10 border-dashed")} data-testid={`equip-slot-${s.slot}`}>
                                <Icon className={cn("w-5 h-5 mb-1", s.item ? "text-neon-purple" : "text-muted-foreground/50")} />
                                <div className="text-[9px] uppercase tracking-wider text-muted-foreground mb-1">{s.label}</div>
                                {s.item ? (
                                    <>
                                        <div className="font-display font-bold text-white text-xs mb-1.5 leading-tight">{s.item.name}</div>
                                        <div className="mb-2"><EquipPills equip={s.item.equip} /></div>
                                        <button onClick={() => unequip(s.slot)} disabled={busyId === "uneq" + s.slot}
                                            className="mt-auto inline-flex items-center gap-1 text-[10px] font-mono text-neon-red hover:text-neon-red/80 disabled:opacity-50" data-testid={`unequip-${s.slot}`}>
                                            <X className="w-3 h-3" /> Unequip
                                        </button>
                                    </>
                                ) : (
                                    <div className="text-[10px] text-muted-foreground/60 font-mono mt-auto">Empty</div>
                                )}
                            </div>
                        );
                    })}
                </div>
                {equipment?.bonuses && Object.keys(equipment.bonuses).length > 0 && (
                    <div className="mt-4 pt-3 border-t border-white/10">
                        <div className="text-[10px] uppercase tracking-wider text-neon-green/70 mb-2">Active passive bonuses</div>
                        <EquipPills equip={equipment.bonuses} />
                    </div>
                )}
            </Panel>

            {/* INVENTORY */}
            <Panel className="p-5" data-testid="inventory-panel">
                <div className="flex items-center gap-1.5 mb-3">
                    <Package className="w-4 h-4 text-neon-cyan" />
                    <span className="font-display font-bold text-white">Your Inventory</span>
                    <InfoTip text="Items you own. Use a consumable to apply its effect (it's consumed). Equip apparel/devices/gear into an equipment slot for a passive bonus." testid="inventory-info" />
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
                                <div className="mb-3 flex-1">{it.equippable ? <EquipPills equip={it.equip} /> : <EffectPills effects={it.effects} />}</div>
                                {it.usable ? (
                                    <KButton variant="primary" className="w-full" loading={busyId === "use" + it.id} onClick={() => use(it)} data-testid={`use-${it.id}`}>
                                        <Check className="w-3.5 h-3.5" /> Use
                                    </KButton>
                                ) : it.equippable ? (
                                    it.equipped ? (
                                        <div className="text-[10px] text-neon-purple font-mono uppercase tracking-wider py-2 text-center border border-neon-purple/30 rounded-sm" data-testid={`equipped-tag-${it.id}`}>✓ Equipped</div>
                                    ) : (
                                        <KButton variant="ghost" className="w-full" loading={busyId === "eq" + it.id} onClick={() => equip(it)} data-testid={`equip-${it.id}`}>
                                            <Shield className="w-3.5 h-3.5" /> Equip
                                        </KButton>
                                    )
                                ) : (
                                    <div className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider py-2 text-center">No action</div>
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
                                    <div className="mb-3">{it.slot ? <EquipPills equip={it.equip} /> : <EffectPills effects={it.effects} />}</div>
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
