import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { Panel, Pill, Spinner } from "@/components/game/primitives";
import { KButton, KInput } from "@/components/game/controls";
import { money } from "@/lib/helpers";
import { TrendingUp, TrendingDown, Wallet } from "lucide-react";
import { cn } from "@/lib/utils";

function Sparkline({ data, up }) {
    if (!data || data.length < 2) return null;
    const w = 68, h = 22;
    const min = Math.min(...data), max = Math.max(...data);
    const span = max - min || 1;
    const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / span) * h}`).join(" ");
    return (
        <svg width={w} height={h} className="shrink-0">
            <polyline points={pts} fill="none" stroke={up ? "#00FF9C" : "#FF0055"} strokeWidth="1.5" />
        </svg>
    );
}

function fmtPrice(v) {
    if (v == null) return "—";
    return v < 5 ? `$${v.toFixed(4)}` : `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function MarketPanel({ endpoint, kind, accent = "#00F3FF" }) {
    const { act } = useGame();
    const [assets, setAssets] = useState(null);
    const [portfolio, setPortfolio] = useState(null);
    const [qty, setQty] = useState({});
    const [busy, setBusy] = useState(null);

    const load = useCallback(async () => {
        const [{ data: a }, { data: pf }] = await Promise.all([
            api.get(endpoint),
            api.get("/market/portfolio"),
        ]);
        setAssets(Array.isArray(a) ? a : (a.assets || []));
        setPortfolio(pf);
    }, [endpoint]);

    useEffect(() => { load().catch(() => setAssets([])); }, [load]);
    // gentle live refresh so prices tick
    useEffect(() => {
        const t = setInterval(() => load().catch(() => {}), 20000);
        return () => clearInterval(t);
    }, [load]);

    if (!assets) return <Spinner />;

    const held = (id) => (portfolio?.holdings || []).find((h) => h.id === id);
    const trade = async (asset, side) => {
        const q = Number(qty[asset.id]);
        if (!q || q <= 0) return;
        setBusy(asset.id + side);
        const r = await act(() => api.post(`/market/${side}`, { asset_id: asset.id, qty: q }),
            `${side === "buy" ? "Bought" : "Sold"} ${q} ${asset.symbol}`);
        await load();
        if (r.ok) setQty((x) => ({ ...x, [asset.id]: "" }));
        setBusy(null);
    };

    const myKind = (portfolio?.holdings || []).filter((h) => h.kind === kind);
    const myValue = myKind.reduce((s, h) => s + h.value, 0);
    const myPnl = myKind.reduce((s, h) => s + h.pnl, 0);

    return (
        <div className="space-y-4">
            <Panel className="p-4 flex items-center justify-between" data-testid={`${kind}-portfolio-summary`}>
                <div className="flex items-center gap-2">
                    <Wallet className="w-4 h-4" style={{ color: accent }} />
                    <span className="font-display font-bold text-white text-sm">Your {kind === "crypto" ? "Crypto" : "Stock"} Holdings</span>
                </div>
                <div className="text-right">
                    <div className="font-mono text-white tnum" data-testid={`${kind}-holdings-value`}>{money(myValue)}</div>
                    <div className={cn("text-[11px] font-mono", myPnl >= 0 ? "text-neon-green" : "text-neon-red")}>
                        {myPnl >= 0 ? "+" : ""}{money(myPnl)} unrealized
                    </div>
                </div>
            </Panel>

            <div className="space-y-2">
                {assets.map((a) => {
                    const up = (a.trend ?? a.change ?? 0) >= 0;
                    const h = held(a.id);
                    return (
                        <Panel key={a.id} className="p-4" data-testid={`asset-${a.id}`}>
                            <div className="flex items-center justify-between gap-3 flex-wrap">
                                <div className="min-w-[150px]">
                                    <div className="flex items-center gap-2">
                                        <span className="font-display font-bold text-white">{a.symbol}</span>
                                        <span className="text-[11px] text-muted-foreground">{a.name}</span>
                                    </div>
                                    <div className="flex items-center gap-2 mt-0.5">
                                        <span className="font-mono text-sm tnum" style={{ color: accent }} data-testid={`price-${a.id}`}>{fmtPrice(a.price)}</span>
                                        <Pill tone={up ? "green" : "red"}>
                                            {up ? <TrendingUp className="w-3 h-3 inline" /> : <TrendingDown className="w-3 h-3 inline" />}
                                            {" "}{((a.trend ?? a.change ?? 0) * 100).toFixed(2)}%
                                        </Pill>
                                    </div>
                                </div>
                                <Sparkline data={a.history} up={up} />
                                <div className="flex items-end gap-2">
                                    <div className="w-24">
                                        <KInput type="number" label={h ? `Hold ${h.qty}` : "Qty"} value={qty[a.id] || ""}
                                            onChange={(e) => setQty((x) => ({ ...x, [a.id]: e.target.value }))}
                                            placeholder="0" testid={`qty-${a.id}`} />
                                    </div>
                                    <KButton variant="green" loading={busy === a.id + "buy"} onClick={() => trade(a, "buy")} data-testid={`buy-${a.id}`}>Buy</KButton>
                                    <KButton variant="ghost" disabled={!h} loading={busy === a.id + "sell"} onClick={() => trade(a, "sell")} data-testid={`sell-${a.id}`}>Sell</KButton>
                                </div>
                            </div>
                            {h && (
                                <div className="mt-2 pt-2 border-t border-white/5 text-[11px] font-mono flex gap-4 text-muted-foreground" data-testid={`position-${a.id}`}>
                                    <span>Position: <span className="text-white">{h.qty}</span> @ {fmtPrice(h.avg_cost)}</span>
                                    <span>Value: <span className="text-white">{money(h.value)}</span></span>
                                    <span className={h.pnl >= 0 ? "text-neon-green" : "text-neon-red"}>P&L: {h.pnl >= 0 ? "+" : ""}{money(h.pnl)} ({(h.pnl_pct * 100).toFixed(1)}%)</span>
                                </div>
                            )}
                        </Panel>
                    );
                })}
            </div>
        </div>
    );
}
