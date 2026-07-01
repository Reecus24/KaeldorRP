import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { Building2, BedDouble, Smile, Star, Receipt } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export default function RealEstate() {
    const { act } = useGame();
    const [data, setData] = useState(null);
    const [busyId, setBusyId] = useState(null);

    const load = () => api.get("/housing").then(({ data }) => setData(data)).catch(() => {});
    useEffect(() => { load(); }, []);

    const rent = async (h) => { setBusyId(h.id + "r"); const r = await act(() => api.post(`/housing/${h.id}/rent`), null); if (r?.ok) toast.success(r.res.data.refunded > 0 ? `Moved into ${h.name} · old deposit refunded +$${Math.round(r.res.data.refunded)}` : `Moved into ${h.name}`); await load(); setBusyId(null); };
    const buy = async (h) => { setBusyId(h.id + "b"); const r = await act(() => api.post(`/housing/${h.id}/buy`), null); if (r?.ok) toast.success(`Bought ${h.name}`); await load(); setBusyId(null); };
    const moveOut = async () => { setBusyId("moveout"); const r = await act(() => api.post("/housing/move-out"), null); if (r?.ok) toast.success(r.res.data.refunded > 0 ? `Moved out · deposit refunded +$${Math.round(r.res.data.refunded)}` : "Moved out"); await load(); setBusyId(null); };
    const sellProperty = async () => { setBusyId("sell"); const r = await act(() => api.post("/housing/sell"), null); if (r?.ok) toast.success(`Property sold for $${(r.res.data.value ?? 0).toLocaleString()}`); await load(); setBusyId(null); };

    if (!data) return <Spinner />;
    const currentId = data.current?.id;
    const owned = data.current?.owned;

    return (
        <div className="space-y-6">
            <SectionTitle icon={Building2} kicker="A roof over your head" title="Real Estate"
                sub="Better homes improve sleep quality, mood and status — but cost more in rent and bills. Rentals refund your deposit when you move out; owned homes resell for 60% of purchase price." />

            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {data.listings.map((h) => {
                    const isCurrent = h.id === currentId;
                    const resale = Math.round((h.buy_price || 0) * 0.6);
                    return (
                        <Panel key={h.id} className={cn("p-5 flex flex-col", isCurrent && "border-neon-green/40")} data-testid={`housing-${h.id}`}>
                            <div className="flex items-start justify-between gap-2 mb-1">
                                <h3 className="font-display font-bold text-white leading-tight">{h.name}</h3>
                                {isCurrent && <Pill tone="green">{owned ? "Owned" : "Renting"}</Pill>}
                            </div>
                            <p className="text-[11px] text-muted-foreground mb-3 flex-1">{h.desc}</p>

                            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono text-muted-foreground mb-3">
                                <span className="flex items-center gap-1"><BedDouble className="w-3 h-3 text-neon-cyan" /> Sleep x{h.sleep_quality}</span>
                                <span className="flex items-center gap-1"><Smile className="w-3 h-3 text-neon-green" /> Mood {h.mood_bonus >= 0 ? "+" : ""}{h.mood_bonus}</span>
                                <span className="flex items-center gap-1"><Star className="w-3 h-3 text-neon-purple" /> Status +{h.social_status}</span>
                                <span className="flex items-center gap-1"><Receipt className="w-3 h-3 text-neon-yellow" /> Bills ${h.bills_per_day}/d</span>
                            </div>

                            <div className="flex items-center justify-between text-[11px] font-mono mb-3">
                                <span className="text-neon-cyan">Rent ${h.rent_per_day}/day{h.deposit ? ` · dep $${h.deposit}` : ""}</span>
                            </div>

                            {isCurrent ? (
                                owned ? (
                                    <div className="space-y-2">
                                        <Pill tone="green" className="!flex justify-center py-2 w-full">Your Home (owned)</Pill>
                                        <KButton variant="ghost" className="w-full text-neon-red/80 hover:text-neon-red" loading={busyId === "sell"} onClick={sellProperty} data-testid="sell-property">
                                            Sell Property · ~${resale.toLocaleString()}
                                        </KButton>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        <Pill tone="green" className="!flex justify-center py-2 w-full">Current Rental</Pill>
                                        <KButton variant="ghost" className="w-full" loading={busyId === "moveout"} onClick={moveOut} data-testid="move-out">
                                            Move Out{h.deposit ? ` · refund $${h.deposit}` : ""}
                                        </KButton>
                                    </div>
                                )
                            ) : (
                                <div className="grid grid-cols-2 gap-2">
                                    <KButton variant="primary" loading={busyId === h.id + "r"} onClick={() => rent(h)} data-testid={`rent-${h.id}`}>Rent</KButton>
                                    <KButton variant="green" disabled={!h.buy_price} loading={busyId === h.id + "b"} onClick={() => buy(h)} data-testid={`buy-house-${h.id}`}>
                                        {h.buy_price ? `Buy $${(h.buy_price / 1000).toFixed(0)}k` : "N/A"}
                                    </KButton>
                                </div>
                            )}
                        </Panel>
                    );
                })}
            </div>
        </div>
    );
}
