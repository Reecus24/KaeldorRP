import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SectionTitle, Spinner, Panel, Pill, EmptyState } from "@/components/game/primitives";
import { ScrollText, TrendingUp, TrendingDown, AlertTriangle, Sparkles, ListTree, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

const INCOME = [
    ["expedition_income", "Expedition Spoils"],
    ["story_income", "Stories & Milestones"],
    ["wages_earned", "Total Wages"],
    ["business_income", "Workshop Dividends / Profits"],
    ["crime_income", "Crime Income"],
    ["social_income", "Social & Deals"],
    ["savings_interest", "Savings Interest"],
];
const EXPENSE = [
    ["expedition_costs", "Faction Oaths"],
    ["story_costs", "Story Expenses"],
    ["rent", "Housing Rent"],
    ["vehicle_costs", "Mount or Cart Expenses (Fodder / Ins / Maint)"],
    ["bills", "Utilities"],
    ["living_costs", "Social Spending"],
    ["fines", "Fines & Bail"],
    ["medical", "Medical"],
    ["taxes", "Taxes"],
    ["loan_interest", "Loan Interest"],
];
const INFO = [
    ["business_pnl", "Workshop P&L (info)"],
    ["employee_wages", "Staff wages (paid by workshop)"],
];
const SEV_DOT = { success: "bg-neon-green", warning: "bg-neon-yellow", danger: "bg-neon-red", info: "bg-neon-cyan" };

const fmt = (v) => `${v < 0 ? "-" : ""}¤ ${Math.abs(Math.round(v || 0)).toLocaleString()}`;

const BALANCES = [["cash", "Coin", true, true], ["bank", "Vault", true, true], ["debt", "Debt", true, false]];
const STATS = [
    ["energy", "Energy", true], ["health", "Health", true], ["mood", "Mood", true],
    ["hunger", "Hunger", false], ["fatigue", "Fatigue", false], ["stress", "Stress", false],
];

function BARow({ label, before, after, money, goodUp }) {
    const rawDelta = (after || 0) - (before || 0);
    const showDelta = Math.abs(rawDelta) >= 0.5;
    const beneficial = rawDelta > 0 === goodUp;
    const deltaColor = !showDelta ? "text-muted-foreground" : (beneficial ? "text-neon-green" : "text-neon-red");
    const fmtv = money ? fmt : (v) => Math.round(v || 0);
    const deltaStr = money ? `${rawDelta > 0 ? "+" : ""}${fmt(rawDelta)}` : `${rawDelta > 0 ? "+" : ""}${Math.round(rawDelta)}`;
    return (
        <div className="flex items-center justify-between py-1 text-sm" data-testid={`ba-${label.toLowerCase()}`}>
            <span className="text-muted-foreground">{label}</span>
            <span className="font-mono tnum flex items-center gap-1.5">
                <span className="text-white/45">{fmtv(before)}</span>
                <ArrowRight className="w-3 h-3 text-muted-foreground/40" />
                <span className="text-white">{fmtv(after)}</span>
                {showDelta && <span className={cn("text-[11px]", deltaColor)}>({deltaStr})</span>}
            </span>
        </div>
    );
}

function BeforeAfter({ open, close }) {
    const hasStats = ["energy", "health", "mood", "hunger", "fatigue", "stress"].some((k) => open[k] != null || close[k] != null);
    return (
        <div className="mt-4 pt-3 border-t border-white/8 grid sm:grid-cols-2 gap-4" data-testid="before-after">
            <div>
                <div className="text-[10px] uppercase tracking-wider text-neon-cyan mb-1">Balances · before → after</div>
                {BALANCES.map(([k, label, money, goodUp]) => (
                    <BARow key={k} label={label} before={open[k]} after={close[k]} money={money} goodUp={goodUp} />
                ))}
            </div>
            {hasStats && (
                <div>
                    <div className="text-[10px] uppercase tracking-wider text-neon-purple mb-1">Condition · before → after</div>
                    {STATS.map(([k, label, goodUp]) => (
                        <BARow key={k} label={label} before={open[k]} after={close[k]} money={false} goodUp={goodUp} />
                    ))}
                </div>
            )}
        </div>
    );
}

function Line({ label, value, positive }) {
    if (!value) return null;
    return (
        <div className="flex justify-between items-center py-1 text-sm">
            <span className="text-muted-foreground">{label}</span>
            <span className={cn("font-mono tnum", positive ? "text-neon-green" : "text-neon-red")}>{fmt(value)}</span>
        </div>
    );
}

function SummaryCard({ s }) {
    const L = s.ledger || {};
    const hasIncome = INCOME.some(([k]) => L[k]);
    const hasExpense = EXPENSE.some(([k]) => L[k]);
    const hasInfo = INFO.some(([k]) => L[k]);
    return (
        <Panel className="p-5" data-testid={`summary-card-${s.id}`}>
            <div className="flex items-start justify-between mb-4">
                <div>
                    <h3 className="font-display font-bold text-white text-lg">{s.game_date}</h3>
                    <div className="text-[11px] text-muted-foreground font-mono">
                        {s.days_covered > 1 ? `${s.days_covered} days resolved` : "Daily ledger"} · {new Date(s.real_ts).toLocaleString()}
                    </div>
                </div>
                <div className="text-right">
                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Net cash</div>
                    <div className={cn("font-display font-extrabold text-2xl flex items-center gap-1", s.net_cash >= 0 ? "text-neon-green" : "text-neon-red")}>
                        {s.net_cash >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                        {fmt(s.net_cash)}
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                    <div className="flex justify-between items-center text-[10px] uppercase tracking-wider text-neon-green mb-1">
                        <span>Income</span><span className="font-mono">{fmt(s.income_total)}</span>
                    </div>
                    {hasIncome ? INCOME.map(([k, label]) => <Line key={k} label={label} value={L[k]} positive />) : <div className="text-xs text-muted-foreground/60 py-1">No income</div>}
                </div>
                <div>
                    <div className="flex justify-between items-center text-[10px] uppercase tracking-wider text-neon-red mb-1">
                        <span>Expenses</span><span className="font-mono">{fmt(s.expense_total)}</span>
                    </div>
                    {hasExpense ? EXPENSE.map(([k, label]) => <Line key={k} label={label} value={L[k]} />) : <div className="text-xs text-muted-foreground/60 py-1">No expenses</div>}
                </div>
            </div>

            {hasInfo && (
                <div className="mt-3 pt-3 border-t border-white/8">
                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Workshop & debt</div>
                    {INFO.map(([k, label]) => (
                        <div key={k} className="flex justify-between items-center py-1 text-sm">
                            <span className="text-muted-foreground">{label}</span>
                            <span className={cn("font-mono tnum", (L[k] || 0) >= 0 ? "text-neon-cyan" : "text-neon-yellow")}>{fmt(L[k])}</span>
                        </div>
                    ))}
                </div>
            )}

            {L.rel_events?.length > 0 && (
                <div className="mt-3 pt-3 border-t border-white/8">
                    <div className="text-[10px] uppercase tracking-wider text-neon-purple mb-1 flex items-center gap-1"><Sparkles className="w-3 h-3" /> Social events</div>
                    {L.rel_events.slice(0, 6).map((e, i) => <div key={i} className="text-xs text-muted-foreground py-0.5">› {e}</div>)}
                </div>
            )}

            {s.events?.length > 0 && (
                <div className="mt-3 pt-3 border-t border-white/8" data-testid={`summary-events-${s.id}`}>
                    <div className="text-[10px] uppercase tracking-wider text-neon-cyan mb-1 flex items-center gap-1"><ListTree className="w-3 h-3" /> Event Log</div>
                    <div className="max-h-56 overflow-y-auto pr-1">
                        {s.events.slice(-18).reverse().map((e, i) => (
                            <div key={i} className="flex items-start gap-2 text-xs py-0.5">
                                <span className={cn("mt-1.5 w-1.5 h-1.5 rounded-full shrink-0", SEV_DOT[e.severity] || "bg-white/30")} />
                                <span className="text-muted-foreground leading-snug">{e.message}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {L.warnings?.length > 0 && (
                <div className="mt-3 pt-3 border-t border-neon-yellow/20">
                    {L.warnings.map((w, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs text-neon-yellow py-0.5"><AlertTriangle className="w-3.5 h-3.5 shrink-0" /> {w}</div>
                    ))}
                </div>
            )}

            {s.open && s.close ? (
                <BeforeAfter open={s.open} close={s.close} />
            ) : (
                <div className="mt-4 pt-3 border-t border-white/8 flex flex-wrap gap-2">
                    <Pill tone="cyan">Coin ¤ {Math.round(s.cash).toLocaleString()}</Pill>
                    <Pill tone="green">Vault ¤ {Math.round(s.bank).toLocaleString()}</Pill>
                    {s.debt > 0 && <Pill tone="red">Debt ¤ {Math.round(s.debt).toLocaleString()}</Pill>}
                </div>
            )}
        </Panel>
    );
}

export default function DailySummary() {
    const [items, setItems] = useState(null);

    useEffect(() => {
        api.get("/daily-summaries?limit=30").then(({ data }) => setItems(data)).catch(() => setItems([]));
    }, []);

    if (!items) return <Spinner />;
    return (
        <div className="space-y-6">
            <SectionTitle icon={ScrollText} kicker="Your ledger" title="Daily Chronicle"
                sub="A 100% transparent receipt of every in-game day — income (wages, workshop dividends), expenses (housing rent, mount or cart, utilities, social), workshop P&L, the day's event log and warnings. Fixed rent & mount or cart costs are charged as one daily sum at 00:00; continuous flows (bills, interest) accrue through the day." />
            {items.length === 0 ? (
                <EmptyState icon={ScrollText} title="No summaries yet" sub="Your first daily report will appear after the next in-game midnight. Keep living your life — it's all being tracked." />
            ) : (
                <div className="space-y-4">
                    {items.map((s) => <SummaryCard key={s.id} s={s} />)}
                </div>
            )}
        </div>
    );
}
