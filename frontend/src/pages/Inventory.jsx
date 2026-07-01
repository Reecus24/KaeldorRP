import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, InfoTip, StatBar, EmptyState } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { Backpack, Package, Check, Shield, Shirt, Watch, Smartphone, Laptop, Dumbbell, X, Car } from "lucide-react";
import { cn } from "@/lib/utils";

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

export default function Inventory() {
    const { act } = useGame();
    const [inventory, setInventory] = useState(null);
    const [equipment, setEquipment] = useState(null);
    const [vehicles, setVehicles] = useState(null);
    const [busyId, setBusyId] = useState(null);

    const loadInventory = useCallback(() => api.get("/inventory").then(({ data }) => setInventory(data)).catch(() => setInventory([])), []);
    const loadEquipment = useCallback(() => api.get("/equipment").then(({ data }) => setEquipment(data)).catch(() => setEquipment(null)), []);
    const loadVehicles = useCallback(() => api.get("/vehicles").then(({ data }) => setVehicles(data.owned || [])).catch(() => setVehicles([])), []);
    useEffect(() => { loadInventory(); loadEquipment(); loadVehicles(); }, [loadInventory, loadEquipment, loadVehicles]);
    const refreshAll = async () => { await Promise.all([loadInventory(), loadEquipment()]); };

    const use = async (it) => { setBusyId("use" + it.id); await act(() => api.post(`/inventory/${it.id}/use`), `Used ${it.name}`); await refreshAll(); setBusyId(null); };
    const equip = async (it) => { setBusyId("eq" + it.id); await act(() => api.post(`/inventory/${it.id}/equip`), `Equipped ${it.name}`); await refreshAll(); setBusyId(null); };
    const unequip = async (slot) => { setBusyId("uneq" + slot); await act(() => api.post(`/equipment/${slot}/unequip`), `Unequipped`); await refreshAll(); setBusyId(null); };

    const sellEstimate = (v) => Math.round((v.spec?.price || 0) * (v.spec?.resale ?? 0.5) * ((v.condition ?? 100) / 100));
    const sellVehicle = async (v) => {
        setBusyId("veh" + v.instance_id);
        const r = await act(() => api.post(`/vehicles/${v.instance_id}/sell`), null);
        if (r?.ok) toast.success(`Sold ${v.name} for $${(r.res.data.value ?? 0).toLocaleString()}`);
        await loadVehicles();
        setBusyId(null);
    };

    if (!inventory || !vehicles) return <Spinner />;

    return (
        <div className="space-y-6">
            <SectionTitle icon={Backpack} kicker="Your assets" title="Inventory"
                sub="Everything you own in one place — consumables, equippable gear, and your vehicles. Buy more from the Shop and Vehicle Dealer." />

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

            {/* ITEMS */}
            <Panel className="p-5" data-testid="inventory-panel">
                <div className="flex items-center gap-1.5 mb-3">
                    <Package className="w-4 h-4 text-neon-cyan" />
                    <span className="font-display font-bold text-white">Items</span>
                    <InfoTip text="Use a consumable to apply its effect (it's consumed). Equip apparel/devices/gear into an equipment slot for a passive bonus." testid="inventory-info" />
                </div>
                {inventory.length === 0 ? (
                    <div className="text-sm text-muted-foreground">No items yet. Buy something from the Shop.</div>
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

            {/* VEHICLES */}
            <Panel className="p-5" data-testid="garage-panel">
                <div className="flex items-center gap-1.5 mb-3">
                    <Car className="w-4 h-4 text-neon-green" />
                    <span className="font-display font-bold text-white">Your Garage</span>
                    <InfoTip text="Vehicles you own. They unlock delivery work but cost fuel, insurance and maintenance daily. Buy more at the Vehicle Dealer." testid="garage-info" />
                </div>
                {vehicles.length === 0 ? (
                    <EmptyState icon={Car} title="No vehicles yet" sub="Buy one at the Vehicle Dealer to unlock delivery work." />
                ) : (
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {vehicles.map((v) => (
                            <div key={v.instance_id} className="border border-white/10 rounded-sm p-4" data-testid={`owned-vehicle-${v.instance_id}`}>
                                <div className="flex items-center justify-between mb-2">
                                    <span className="font-display font-bold text-white text-sm">{v.name}</span>
                                    <Pill tone="green">Owned</Pill>
                                </div>
                                <StatBar label="Condition" value={v.condition} color="#00FF66" />
                                <div className="text-[11px] text-muted-foreground mt-2 flex items-center justify-between">
                                    <span>Resale value</span>
                                    <span className="font-mono text-neon-green tnum" data-testid={`resale-${v.instance_id}`}>~${sellEstimate(v).toLocaleString()}</span>
                                </div>
                                <KButton variant="ghost" className="w-full mt-3" loading={busyId === "veh" + v.instance_id} onClick={() => sellVehicle(v)} data-testid={`sell-vehicle-${v.instance_id}`}>Sell · ~${sellEstimate(v).toLocaleString()}</KButton>
                            </div>
                        ))}
                    </div>
                )}
            </Panel>
        </div>
    );
}
