import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, StatTile, Money } from "@/components/game/primitives";
import { KButton, KInput } from "@/components/game/controls";
import { money } from "@/lib/helpers";
import { Landmark } from "lucide-react";

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

    return (
        <div className="space-y-6">
            <SectionTitle icon={Landmark} kicker="Money management" title="Bank & Loans"
                sub="Move money, take loans for big plays, and pay down debt before interest buries you." />

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <StatTile label="Cash" value={money(player.cash)} accent="#00F3FF" />
                <StatTile label="Bank" value={money(player.bank)} accent="#00F3FF" />
                <StatTile label="Debt" value={money(player.debt)} accent={player.debt > 0 ? "#FF0055" : "#9CA3AF"} sub={`${(info.interest_daily * 100).toFixed(1)}% daily interest`} />
                <StatTile label="Loan Limit" value={money(info.max_loan)} accent="#FFC300" />
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
                    <KInput type="number" label="Take a loan" value={loan} onChange={(e) => setLoan(e.target.value)} placeholder="0" testid="loan-input" />
                    <KButton variant="yellow" className="w-full border border-neon-yellow text-neon-yellow hover:bg-neon-yellow hover:text-black" loading={busy} onClick={() => run(() => api.post("/bank/loan", { amount: Number(loan) }), "Loan approved", () => setLoan(""))} data-testid="loan-button">Borrow</KButton>
                    <KInput type="number" label="Repay debt" value={repay} onChange={(e) => setRepay(e.target.value)} placeholder="0" testid="repay-input" />
                    <KButton variant="green" className="w-full" loading={busy} disabled={player.debt <= 0} onClick={() => run(() => api.post("/bank/repay", { amount: Number(repay) }), "Debt repaid", () => setRepay(""))} data-testid="repay-button">Repay</KButton>
                </Panel>
            </div>
        </div>
    );
}
