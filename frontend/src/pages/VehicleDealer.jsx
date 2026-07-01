import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { Car, Fuel, ShieldCheck, Wrench } from "lucide-react";

export default function VehicleDealer() {
    const { player, act } = useGame();
    const [data, setData] = useState(null);
    const [busyId, setBusyId] = useState(null);

    const load = () => api.get("/vehicles").then(({ data }) => setData(data)).catch(() => {});
    useEffect(() => { load(); }, []);

    const buy = async (v) => { setBusyId(v.id); await act(() => api.post(`/vehicles/${v.id}/buy`), `Bought a ${v.name}`); await load(); setBusyId(null); };

    if (!data) return <Spinner />;

    return (
        <div className="space-y-6">
            <SectionTitle icon={Car} kicker="Get moving" title="Vehicle Dealer"
                sub="Vehicles unlock delivery jobs and street activities — but they cost fuel, insurance and maintenance every day. Your owned vehicles live in the Inventory tab." />

            <div>
                <div className="font-mono text-[11px] uppercase tracking-[0.25em] text-neon-cyan/70 mb-3">For Sale</div>
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {data.listings.map((v) => {
                        const afford = player.cash + player.bank >= v.price;
                        return (
                            <Panel key={v.id} className="p-5 flex flex-col" data-testid={`vehicle-${v.id}`}>
                                <div className="flex items-start justify-between gap-2 mb-1">
                                    <h3 className="font-display font-bold text-white leading-tight">{v.name}</h3>
                                    <span className="font-mono text-neon-green tnum">${v.price.toLocaleString()}</span>
                                </div>
                                <p className="text-[11px] text-muted-foreground mb-3 flex-1">{v.desc}</p>
                                <div className="grid grid-cols-3 gap-2 text-[10px] font-mono text-muted-foreground mb-3">
                                    <span className="flex items-center gap-1"><Fuel className="w-3 h-3 text-neon-yellow" /> ${v.fuel_per_day}/d</span>
                                    <span className="flex items-center gap-1"><ShieldCheck className="w-3 h-3 text-neon-cyan" /> ${v.insurance_per_day}/d</span>
                                    <span className="flex items-center gap-1"><Wrench className="w-3 h-3" /> ${v.maintenance_per_day}/d</span>
                                </div>
                                <KButton variant="green" className="w-full" disabled={!afford} loading={busyId === v.id} onClick={() => buy(v)} data-testid={`buy-vehicle-${v.id}`}>
                                    {afford ? "Buy" : "Can't afford"}
                                </KButton>
                            </Panel>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
