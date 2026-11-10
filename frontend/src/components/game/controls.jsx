import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

const VARIANTS = {
    primary:
        "border border-neon-cyan text-neon-cyan hover:bg-neon-cyan hover:text-black",
    green: "border border-neon-green text-neon-green hover:bg-neon-green hover:text-black",
    danger: "border border-neon-red text-neon-red hover:bg-neon-red hover:text-white",
    ghost: "border border-white/15 text-white hover:bg-white/10",
    solid: "bg-neon-cyan text-black hover:bg-neon-cyan/80 border border-neon-cyan",
};

export function KButton({ children, variant = "primary", className, loading, disabled, ...props }) {
    return (
        <button
            type="button"
            disabled={disabled || loading}
            aria-busy={loading || undefined}
            className={cn(
                "inline-flex min-h-[42px] items-center justify-center gap-2 px-4 py-2 text-xs font-bold uppercase tracking-wider rounded-sm transition-colors disabled:opacity-45 disabled:cursor-not-allowed disabled:hover:bg-transparent",
                VARIANTS[variant],
                className,
            )}
            {...props}
        >
            {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            {children}
        </button>
    );
}

export function KInput({ className, label, testid, ...props }) {
    return (
        <label className="block">
            {label && <span className="block text-xs tracking-wide text-muted-foreground mb-1.5 font-medium">{label}</span>}
            <input
                data-testid={testid}
                className={cn(
                    "w-full bg-[#101A16] border border-white/12 rounded-sm px-3 py-2.5 text-sm text-white outline-none transition-colors placeholder:text-muted-foreground/50 focus:border-neon-cyan/60 font-mono",
                    className,
                )}
                {...props}
            />
        </label>
    );
}
