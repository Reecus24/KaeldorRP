import { cn } from "@/lib/utils";
import { money as fmtMoney, RISK_COLORS } from "@/lib/helpers";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Info } from "lucide-react";

export function InfoTip({ text, className, side = "top", testid }) {
    return (
        <TooltipProvider delayDuration={120}>
            <Tooltip>
                <TooltipTrigger asChild>
                    <button type="button" aria-label="More information" data-testid={testid} onClick={(e) => e.preventDefault()}
                        className={cn("inline-flex items-center text-muted-foreground/60 hover:text-neon-cyan transition-colors align-middle", className)}>
                        <Info className="w-3 h-3" />
                    </button>
                </TooltipTrigger>
                <TooltipContent side={side} className="max-w-[230px] bg-[#1B2520] border border-white/15 text-foreground text-[11px] leading-relaxed font-mono">
                    {text}
                </TooltipContent>
            </Tooltip>
        </TooltipProvider>
    );
}

export function Panel({ className, children, ...props }) {
    return (
        <div className={cn("kael-panel rounded-sm transition-colors", className)} {...props}>
            {children}
        </div>
    );
}

export function SectionTitle({ kicker, title, sub, right, icon: Icon }) {
    return (
        <div className="flex items-end justify-between gap-4 mb-5">
            <div>
                {kicker && (
                    <div className="font-mono text-[11px] uppercase tracking-[0.3em] text-neon-cyan/70 mb-2">
                        {kicker}
                    </div>
                )}
                <h1 className="font-display font-extrabold tracking-tighter text-3xl sm:text-4xl text-white flex items-center gap-3">
                    {Icon && <Icon className="w-7 h-7 text-neon-cyan" strokeWidth={1.5} />}
                    {title}
                </h1>
                {sub && <p className="text-muted-foreground text-sm mt-2 max-w-2xl">{sub}</p>}
            </div>
            {right}
        </div>
    );
}

export function StatBar({ label, value, max = 100, color = "#D1B579", invert = false, showValue = true, testid, info, warningThreshold, showDirection = false }) {
    const numeric = Number(value);
    const safeValue = Number.isFinite(numeric) ? Math.max(0, Math.min(max, numeric)) : 0;
    const pct = max > 0 ? (safeValue / max) * 100 : 0;
    // warning tint when in a bad zone
    const threshold = warningThreshold ?? (invert ? 70 : 25);
    const bad = invert ? safeValue > threshold : safeValue < threshold;
    const barColor = bad ? "#DE8274" : color;
    return (
        <div data-testid={testid}>
            {label && (
                <div className="flex justify-between items-center mb-1.5">
                    <span className="text-xs tracking-wide text-muted-foreground font-medium flex items-center gap-1">
                        {label}{info && <InfoTip text={info} testid={testid ? `${testid}-info` : undefined} />}
                    </span>
                    {showValue && <span className="font-mono text-xs text-white tnum">{Number.isFinite(numeric) ? Math.round(safeValue) : "—"}</span>}
                </div>
            )}
            <div className="h-2 w-full bg-white/5 overflow-hidden rounded-sm" role="progressbar"
                aria-label={label || "Stat"} aria-valuemin={0} aria-valuemax={max} aria-valuenow={safeValue}
                aria-valuetext={`${Math.round(safeValue)} of ${max}; ${invert ? "lower" : "higher"} is better`}
                title={invert ? "Lower is better" : "Higher is better"}>
                <div
                    className="h-full transition-all duration-500 rounded-sm"
                    style={{ width: `${pct}%`, backgroundColor: barColor }}
                />
            </div>
            {showDirection && <div className="text-[10px] text-muted-foreground mt-1">{invert ? "Lower is better" : "Higher is better"}</div>}
        </div>
    );
}

export function Pill({ children, className, tone = "default", "data-testid": testid }) {
    const tones = {
        default: "border-white/15 text-muted-foreground",
        cyan: "border-neon-cyan/40 text-neon-cyan",
        green: "border-neon-green/40 text-neon-green",
        yellow: "border-neon-yellow/40 text-neon-yellow",
        red: "border-neon-red/40 text-neon-red",
        purple: "border-neon-purple/40 text-neon-purple",
    };
    return (
        <span
            data-testid={testid}
            className={cn(
                "inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider border rounded-sm",
                tones[tone],
                className,
            )}
        >
            {children}
        </span>
    );
}

export function RiskBadge({ level }) {
    const labels = { none: "Safe", low: "Low Risk", medium: "Med Risk", high: "High Risk" };
    return (
        <span className={cn("inline-flex items-center px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider border rounded-sm", RISK_COLORS[level] || RISK_COLORS.none)}>
            {labels[level] || level}
        </span>
    );
}

export function Money({ value, className, testid }) {
    const v = Number(value || 0);
    return (
        <span
            data-testid={testid}
            className={cn("font-mono tnum", v < 0 ? "text-neon-red" : "text-neon-green", className)}
        >
            {fmtMoney(v)}
        </span>
    );
}

export function StatTile({ label, value, accent = "#D1B579", testid, sub, info }) {
    return (
        <Panel className="p-4" data-testid={testid}>
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium flex items-center gap-1">
                {label}{info && <InfoTip text={info} testid={testid ? `${testid}-info` : undefined} />}
            </div>
            <div className="font-display font-bold text-xl mt-1" style={{ color: accent }}>
                {value}
            </div>
            {sub && <div className="text-[11px] text-muted-foreground mt-0.5">{sub}</div>}
        </Panel>
    );
}

export function Spinner({ className }) {
    return (
        <div className={cn("flex items-center justify-center py-16", className)}>
            <div className="w-8 h-8 border-2 border-neon-cyan/30 border-t-neon-cyan rounded-full animate-spin" />
        </div>
    );
}

export function EmptyState({ icon: Icon, title, sub }) {
    return (
        <Panel className="p-10 text-center">
            {Icon && <Icon className="w-10 h-10 mx-auto text-muted-foreground/50 mb-3" strokeWidth={1.5} />}
            <div className="font-display text-lg text-white">{title}</div>
            {sub && <div className="text-sm text-muted-foreground mt-1">{sub}</div>}
        </Panel>
    );
}
