import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ShieldCheck, ArrowRight, PackageCheck } from "lucide-react";
import { Panel, Pill } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { money } from "@/lib/helpers";
import { api, errMessage } from "@/lib/api";
import { toast } from "sonner";

export function BusinessOperations({ business, operations: op, onReload, onTab }) {
    const [days, setDays] = useState("");
    const [busy, setBusy] = useState(false);
    if (!op) return null;
    const save = async () => {
        setBusy(true);
        try {
            await api.post("/businesses/" + business.id + "/restock-settings", { reserve_days: Number(days) });
            await onReload(); setDays(""); toast.success("Operating reserve updated");
        } catch (e) { toast.error(errMessage(e)); }
        finally { setBusy(false); }
    };
    return <Panel className="p-5 sm:p-6 border-neon-cyan/25" data-testid="business-operations">
        <div className="flex items-center justify-between gap-3 flex-wrap"><h2 className="text-lg font-bold font-display text-white inline-flex gap-2 items-center"><ShieldCheck className="w-5 h-5 text-neon-cyan" /> Your workshop at a glance</h2><Pill tone={op.alerts.length ? "yellow" : "green"}>{op.status}</Pill></div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 my-5">
            {[["Available payout", money(op.safe_to_collect)], ["Keep in the workshop", money(op.reserve)], ["Daily costs · est.", money(op.daily_cost)],
                ["Materials coverage", op.stock_days == null ? "No production yet" : op.stock_days + " game days"]].map(([label, value]) =>
                <div key={label}><p className="text-xs text-muted-foreground">{label}</p><p className="text-lg font-display text-white font-bold mt-1">{value}</p></div>)}
        </div>
        <p className="text-sm text-muted-foreground leading-relaxed">Payouts leave {op.reserve_days} game day(s) of forecast material and wage costs, plus outstanding debt, in the workshop. Forecasts assume steady operation; they are not guaranteed earnings.</p>
        <div className="space-y-3 mt-5">{op.alerts.slice(0, 3).map((a) => <div key={a.title} className="border-l-2 border-neon-yellow/50 pl-3">
            <button className="text-left text-sm font-bold text-white inline-flex items-center gap-2 min-h-[32px]" onClick={() => onTab(a.tab)}>{a.title}<ArrowRight className="w-3 h-3" /></button><p className="text-xs text-muted-foreground leading-relaxed mt-1">{a.detail}</p>
        </div>)}</div>
        <details className="mt-5 pt-4 border-t border-white/10">
            <summary className="text-sm text-neon-cyan cursor-pointer">Adjust your operating reserve</summary>
            <div className="flex items-end gap-3 flex-wrap mt-3"><label className="text-xs text-muted-foreground">Game days to keep
                <input aria-label="Operating reserve days" type="number" min="0" max={op.max_reserve_days} step="0.5" placeholder={String(op.reserve_days)} value={days} onChange={(e) => setDays(e.target.value)} className="block mt-2 w-28 p-2.5 bg-black/30 border border-white/20 text-white rounded-sm" />
            </label><KButton disabled={busy || days === "" || !Number.isFinite(Number(days)) || Number(days) < 0 || Number(days) > op.max_reserve_days} onClick={save}>Save reserve</KButton></div>
            <p className="text-xs text-muted-foreground mt-3">Setting this to zero allows cash above outstanding debt to be withdrawn. A reserve helps avoid interrupting production.</p>
        </details>
        <Link to="/journey" className="inline-flex gap-2 items-center text-sm text-neon-purple mt-5 min-h-[44px]"><PackageCheck className="w-4 h-4" /> Find realm opportunities for your workshop <ArrowRight className="w-4 h-4" /></Link>
    </Panel>;
}

export function MaterialsPurchase({ business, target, onReload }) {
    const [quote, setQuote] = useState(null);
    const [allowOwner, setAllowOwner] = useState(false);
    const [busy, setBusy] = useState(false);
    useEffect(() => { setQuote(null); setAllowOwner(false); }, [business.id, target]);
    const request = async (purchase) => {
        setBusy(true);
        try {
            const body = { ...(target === "" ? {} : { units: Number(target) }), allow_owner_funds: allowOwner };
            const { data } = await api.post("/businesses/" + business.id + (purchase ? "/buy-materials" : "/materials-quote"), body);
            if (purchase) { setQuote(null); setAllowOwner(false); toast.success("Materials purchased for " + money(data.cost)); await onReload(); }
            else setQuote(data);
        } catch (e) { toast.error(errMessage(e)); }
        finally { setBusy(false); }
    };
    const invalid = target !== "" && (!Number.isFinite(Number(target)) || Number(target) < 0 || Number(target) > 1000000);
    return <div className="w-full">
        <KButton disabled={busy || invalid} variant="primary" onClick={() => request(false)} data-testid="materials-quote">Review purchase</KButton>
        {quote && <div className="mt-3 p-4 bg-black/25 border border-neon-cyan/25 rounded-sm space-y-3" data-testid="materials-quote-detail">
            <div className="text-white font-bold">Top up to {quote.units} product units · {money(quote.cost)}</div>
            <p className="text-sm text-muted-foreground">Workshop pays {money(quote.from_business)}. Personal contribution: {money(quote.from_owner)}. Supplier discounts are included.</p>
            <details><summary className="cursor-pointer text-xs text-muted-foreground">Ingredient breakdown</summary>{quote.lines.filter((l) => l.quantity > 0).map((l) => <p key={l.id} className="text-xs text-muted-foreground mt-2">{l.name}: {l.quantity} · {money(l.cost)}</p>)}</details>
            {quote.from_owner > 0 && <label className="flex items-start gap-2 text-sm text-neon-yellow"><input type="checkbox" checked={allowOwner} onChange={(e) => setAllowOwner(e.target.checked)} className="mt-1 accent-neon-cyan" />Allow the shortfall to be paid from my personal cash / bank</label>}
            <p className="text-xs text-muted-foreground">The price is recalculated when you confirm because production can change your stock.</p>
            <KButton disabled={busy || quote.cost === 0 || (quote.from_owner > 0 && !allowOwner)} onClick={() => request(true)}>{quote.cost === 0 ? "Already stocked" : "Confirm purchase"}</KButton>
        </div>}
    </div>;
}
