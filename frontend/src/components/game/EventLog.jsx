import { useGame } from "@/context/GameContext";
import { Panel } from "@/components/game/primitives";
import { Terminal } from "lucide-react";

const SEV_COLOR = {
    success: "text-neon-green",
    info: "text-neon-cyan/90",
    warning: "text-neon-yellow",
    danger: "text-neon-red",
};

function timeAgo(ts) {
    const diff = (Date.now() - new Date(ts).getTime()) / 1000;
    if (diff < 60) return `${Math.floor(diff)}s`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
    return `${Math.floor(diff / 86400)}d`;
}

export default function EventLog({ max = 40, className = "" }) {
    const { events } = useGame();
    const list = events.slice(0, max);

    return (
        <Panel className={`p-0 overflow-hidden ${className}`} data-testid="event-log">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-white/8 bg-[#050505]">
                <Terminal className="w-4 h-4 text-neon-green" />
                <span className="font-mono text-[11px] uppercase tracking-[0.25em] text-neon-green">Event Log</span>
            </div>
            <div className="max-h-[420px] overflow-y-auto bg-[#050505] divide-y divide-white/5">
                {list.length === 0 && (
                    <div className="px-4 py-6 text-center text-muted-foreground text-sm font-mono">No events yet…</div>
                )}
                {list.map((e, i) => (
                    <div
                        key={e.id || i}
                        className="px-4 py-2.5 font-mono text-xs flex gap-3 items-start hover:bg-white/[0.02]"
                        style={{ opacity: Math.max(0.45, 1 - i * 0.012) }}
                        data-testid={`event-row-${i}`}
                    >
                        <span className="text-muted-foreground/60 shrink-0 tnum">{timeAgo(e.ts)}</span>
                        <span className={`${SEV_COLOR[e.severity] || "text-foreground"} leading-relaxed`}>
                            <span className="text-muted-foreground/50">{">"}</span> {e.message}
                        </span>
                    </div>
                ))}
            </div>
        </Panel>
    );
}
