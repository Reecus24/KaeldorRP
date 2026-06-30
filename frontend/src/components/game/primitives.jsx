import { cn } from "@/lib/utils";
import { money as fmtMoney, RISK_COLORS } from "@/lib/helpers";

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

export function StatBar({ label, value, max = 100, color = "#00F3FF", invert = false, showValue = true, testid }) {
    const pct = Math.max(0, Math.min(100, (value / max) * 100));
    // warning tint when in a bad zone
    const bad = invert ? value > 70 : value < 25;
    const barColor = bad ? "#FF0055" : color;
    return (
        <div data-testid={testid}>
            {label && (
                <div className="flex justify-between items-center mb-1.5">
                    <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">{label}</span>
                    {showValue && <span className="font-mono text-[11px] text-white tnum">{Math.round(value)}</span>}
                </div>
            )}
            <div className="h-2.5 w-full bg-white/5 border border-white/10 overflow-hidden rounded-sm">
                <div
                    className="h-full transition-all duration-500 rounded-sm"
                    style={{ width: `${pct}%`, backgroundColor: barColor, boxShadow: `0 0 10px ${barColor}88` }}
                />
            </div>
        </div>
    );
}

export function Pill({ children, className, tone = "default" }) {
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

export function StatTile({ label, value, accent = "#00F3FF", testid, sub }) {
    return (
        <Panel className="p-4" data-testid={testid}>
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">{label}</div>
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
