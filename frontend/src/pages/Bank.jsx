import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, StatTile, Money } from "@/components/game/primitives";
import { KButton, KInput } from "@/components/game/controls";
import { money } from "@/lib/helpers";
import { Landmark, LineChart } from "lucide-react";
import { MarketPanel } from "@/components/game/MarketPanel";

export default function Bank() {
    const { player, act } = useGame();
    const [info, setInfo] = useState(null);
    const [dep, setDep] = useState("");
    const [wit, setWit] = useState("");
    const [loan, setLoan] = useState("");
    const [repay, setRepay] = useState("");
    const [busy, setBusy] = useState(false);

    const load = () => api.get("/bank").then(({ data }) => setInfo(data)).catch(() => {});
    useEffect(() => { load(); }, []);

    const run = async (fn, msg, clear) => {
        setBusy(true);
        const r = await act(fn, msg);
        await load();
        if (r.ok && clear) clear();
        setBusy(false);
    };

    if (!info) return <Spinner />;

    const limit = info.credit_limit ?? info.max_loan ?? 0;
    const used = info.credit_used ?? player.debt ?? 0;
    const available = info.credit_available ?? Math.max(0, limit - used);
    const rate = info.interest_daily ?? 0;
    const loanAmt = Number(loan) || 0;
    const newDebt = used + loanAmt;
    const overLimit = loanAmt > available;
    const usedPct = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;

    return (
        <div className="space-y-6">
            <SectionTitle icon={Landmark} kicker="Money management" title="Bank & Loans"
                sub="Move money, take loans for big plays, and pay down debt before interest buries you." />

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <StatTile label="Cash" value={money(player.cash)} accent="#00F3FF" />
                <StatTile label="Bank" value={money(player.bank)} accent="#00F3FF" />
                <StatTile label="Debt" value={money(player.debt)} accent={player.debt > 0 ? "#FF0055" : "#9CA3AF"} sub={`${(rate * 100).toFixed(1)}% daily interest`} />
                <StatTile label="Available Credit" value={money(available)} accent="#FFC300" />
            </div>

            <div className="grid md:grid-cols-2 gap-3">
                <Panel className="p-5 space-y-3">
                    <div className="font-display font-bold text-white">Deposit / Withdraw</div>
                    <KInput type="number" label="Deposit to bank" value={dep} onChange={(e) => setDep(e.target.value)} placeholder="0" testid="deposit-input" />
                    <KButton className="w-full" loading={busy} onClick={() => run(() => api.post("/bank/deposit", { amount: Number(dep) }), "Deposited", () => setDep(""))} data-testid="deposit-button">Deposit</KButton>
                    <KInput type="number" label="Withdraw to cash" value={wit} onChange={(e) => setWit(e.target.value)} placeholder="0" testid="withdraw-input" />
                    <KButton variant="ghost" className="w-full" loading={busy} onClick={() => run(() => api.post("/bank/withdraw", { amount: Number(wit) }), "Withdrew", () => setWit(""))} data-testid="withdraw-button">Withdraw</KButton>
                </Panel>

                <Panel className="p-5 space-y-3">
                    <div className="font-display font-bold text-white">Loans</div>

                    <div className="rounded-sm border border-white/10 bg-white/5 p-3 space-y-2" data-testid="credit-summary">
                        <div className="grid grid-cols-3 gap-2 text-center text-[11px] font-mono">
                            <div><div className="text-muted-foreground uppercase">Limit</div><div className="text-white tnum" data-testid="credit-limit">{money(limit)}</div></div>
                            <div><div className="text-muted-foreground uppercase">Used</div><div className="text-neon-red tnum" data-testid="credit-used">{money(used)}</div></div>
                            <div><div className="text-muted-foreground uppercase">Available</div><div className="text-neon-yellow tnum" data-testid="credit-available">{money(available)}</div></div>
                        </div>
                        <div className="h-2 w-full bg-white/5 border border-white/10 overflow-hidden rounded-sm">
                            <div className="h-full bg-neon-red/70 transition-all duration-500" style={{ width: `${usedPct}%` }} />
                        </div>
                        <p className="text-[11px] text-muted-foreground">
                            You can borrow up to <span className="text-neon-yellow font-mono">{money(available)}</span> more. Your total credit limit is <span className="text-white font-mono">{money(limit)}</span>, of which <span className="text-neon-red font-mono">{money(used)}</span> is already used.
                        </p>
                        {info.blocked && (
                            <p className="text-[11px] text-neon-red font-mono" data-testid="credit-blocked">Credit frozen: {(info.reasons || []).join(", ")}.</p>
                        )}
                        {!info.blocked && (info.reasons || []).length > 0 && (
                            <p className="text-[11px] text-muted-foreground">Limited by: {(info.reasons || []).join(", ")}.</p>
                        )}
                    </div>

                    <KInput type="number" label="Take a loan" value={loan} onChange={(e) => setLoan(e.target.value)} placeholder="0" testid="loan-input" />
                    {loanAmt > 0 && (
                        <div className="rounded-sm border border-neon-yellow/20 bg-neon-yellow/5 p-3 text-[11px] font-mono space-y-1" data-testid="loan-preview">
                            <div className="flex justify-between"><span className="text-muted-foreground">New loan</span><span className="text-white">{money(loanAmt)}</span></div>
                            <div className="flex justify-between"><span className="text-muted-foreground">Current debt</span><span className="text-white">{money(used)}</span></div>
                            <div className="flex justify-between"><span className="text-muted-foreground">Total debt after</span><span className="text-neon-red" data-testid="loan-new-debt">{money(newDebt)}</span></div>
                            <div className="flex justify-between"><span className="text-muted-foreground">Interest</span><span className="text-white">{(rate * 100).toFixed(1)}%/day</span></div>
                            <div className="flex justify-between"><span className="text-muted-foreground">Daily interest after</span><span className="text-neon-red">~{money(newDebt * rate)}/day</span></div>
                            {overLimit
                                ? <div className="text-neon-red pt-1" data-testid="loan-over-limit">Exceeds available credit ({money(available)}). Repay debt or improve creditworthiness first.</div>
                                : <div className="text-muted-foreground pt-1">Unpaid debt grows daily and lowers your credit limit. Miss payments and the bank cuts you off.</div>}
                        </div>
                    )}
                    <KButton variant="yellow" className="w-full border border-neon-yellow text-neon-yellow hover:bg-neon-yellow hover:text-black" loading={busy}
                        disabled={info.blocked || loanAmt <= 0 || overLimit}
                        onClick={() => run(() => api.post("/bank/loan", { amount: loanAmt }), "Loan approved", () => setLoan(""))} data-testid="loan-button">Borrow</KButton>

                    <KInput type="number" label="Repay debt" value={repay} onChange={(e) => setRepay(e.target.value)} placeholder="0" testid="repay-input" />
                    <KButton variant="green" className="w-full" loading={busy} disabled={player.debt <= 0} onClick={() => run(() => api.post("/bank/repay", { amount: Number(repay) }), "Debt repaid", () => setRepay(""))} data-testid="repay-button">Repay</KButton>
                </Panel>
            </div>

            <div>
                <div className="flex items-center gap-1.5 mb-3 mt-2">
                    <LineChart className="w-4 h-4 text-neon-cyan" />
                    <span className="font-display font-bold text-white">Stock Market</span>
                    <span className="text-[11px] text-muted-foreground">— buy low, sell high. Prices move in real time.</span>
                </div>
                <MarketPanel endpoint="/market/stocks" kind="stock" accent="#00F3FF" />
            </div>
        </div>
    );
}
