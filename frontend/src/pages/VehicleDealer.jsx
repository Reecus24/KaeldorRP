import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { Car, Bike, Truck, Gem, Fuel, ShieldCheck, Wrench, ChevronRight, ArrowLeft } from "lucide-react";

const CAT_ICONS = { Car, Bike, Truck, Gem };

function VehicleCard({ v, player, busyId, onBuy }) {
    const afford = player.cash + player.bank >= v.price;
    return (
        <Panel className="p-5 flex flex-col" data-testid={`vehicle-${v.id}`}>
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
            <KButton variant="green" className="w-full" disabled={!afford} loading={busyId === v.id} onClick={() => onBuy(v)} data-testid={`buy-vehicle-${v.id}`}>
                {afford ? "Buy" : "Can't afford"}
            </KButton>
        </Panel>
    );
}

export default function VehicleDealer() {
    const { player, act } = useGame();
    const [cats, setCats] = useState(null);
    const [entered, setEntered] = useState(null);
    const [loadingList, setLoadingList] = useState(false);
    const [busyId, setBusyId] = useState(null);

    const loadCats = useCallback(() => api.get("/vehicle-categories").then(({ data }) => setCats(data.categories || [])).catch(() => setCats([])), []);
    useEffect(() => { loadCats(); }, [loadCats]);

    const enter = async (c) => {
        setLoadingList(true);
        setEntered({ category: c, listings: [] });
        try {
            const { data } = await api.get(`/vehicle-categories/${c.id}`);
            setEntered({ category: data.category, listings: data.listings || [] });
        } catch { setEntered({ category: c, listings: [] }); }
        setLoadingList(false);
    };

    const buy = async (v) => {
        setBusyId(v.id);
        await act(() => api.post(`/vehicles/${v.id}/buy`), `Bought a ${v.name}`);
        if (entered) await enter(entered.category);
        setBusyId(null);
    };

    if (!cats) return <Spinner />;

    // ---- Inside a category ----
    if (entered) {
        const c = entered.category;
        const Icon = CAT_ICONS[c.icon] || Car;
        return (
            <div className="space-y-6">
                <button onClick={() => { setEntered(null); loadCats(); }} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-white" data-testid="back-to-categories">
                    <ArrowLeft className="w-4 h-4" /> Back to Categories
                </button>
                <SectionTitle icon={Icon} kicker={c.desc} title={c.name}
                    sub="Vehicles unlock delivery jobs and street activities — but they cost fuel, insurance and maintenance every day (charged at 00:00). Your owned vehicles live in the Inventory tab." />
                {loadingList ? <Spinner /> : entered.listings.length === 0 ? (
                    <Panel className="p-6 text-center text-sm text-muted-foreground">No models in this category right now.</Panel>
                ) : (
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="category-vehicles">
                        {entered.listings.map((v) => <VehicleCard key={v.id} v={v} player={player} busyId={busyId} onBuy={buy} />)}
                    </div>
                )}
            </div>
        );
    }

    // ---- Category browser ----
    return (
        <div className="space-y-6">
            <SectionTitle icon={Car} kicker="Get moving" title="Vehicle Dealer"
                sub="Kaeldor's showroom, organised by category. Pick a category to browse its models, then buy — vehicles unlock delivery work but cost fuel, insurance and maintenance each day." />
            <div className="grid sm:grid-cols-2 gap-3" data-testid="vehicle-category-browser">
                {cats.map((c) => {
                    const Icon = CAT_ICONS[c.icon] || Car;
                    return (
                        <Panel key={c.id} className="p-5 flex items-center gap-4 group cursor-pointer hover:border-neon-cyan/40 transition-colors" onClick={() => enter(c)} data-testid={`vehicle-category-${c.id}`}>
                            <div className="w-12 h-12 rounded-sm bg-neon-cyan/10 border border-neon-cyan/20 flex items-center justify-center shrink-0">
                                <Icon className="w-6 h-6 text-neon-cyan" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <span className="font-display font-bold text-white">{c.name}</span>
                                <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">{c.desc}</p>
                                <span className="text-[10px] font-mono text-muted-foreground/70 uppercase tracking-wider">
                                    {c.vehicle_count} model{c.vehicle_count === 1 ? "" : "s"}
                                </span>
                            </div>
                            <KButton variant="primary" onClick={(e) => { e.stopPropagation(); enter(c); }} data-testid={`browse-models-${c.id}`}>
                                Browse Models <ChevronRight className="w-3.5 h-3.5" />
                            </KButton>
                        </Panel>
                    );
                })}
            </div>
        </div>
    );
}
