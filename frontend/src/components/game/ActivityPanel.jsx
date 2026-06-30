import { useGame } from "@/context/GameContext";
import { Panel } from "@/components/game/primitives";
import { fmtDuration } from "@/lib/helpers";
import { api } from "@/lib/api";
import { Loader2, X, Clock, Coffee } from "lucide-react";

export default function ActivityPanel({ compact = false }) {
    const { state, activityRemaining, activityProgress, act } = useGame();
    const activity = state?.activity;

    const cancel = () =>
        act(() => api.post("/game/cancel-activity"), "Activity cancelled");

    if (!activity) {
        return (
            <Panel className="p-5" data-testid="activity-panel-idle">
                <div className="flex items-center gap-2 text-neon-green mb-1">
                    <Coffee className="w-4 h-4" />
                    <span className="font-mono text-[11px] uppercase tracking-[0.25em]">Idle</span>
                </div>
                <div className="text-sm text-muted-foreground">
                    You're free. Pick a job, run a hustle, study, or take care of yourself.
                </div>
            </Panel>
        );
    }

    const pct = Math.round(activityProgress * 100);

    return (
        <Panel className="p-5 neon-border" data-testid="activity-panel">
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-neon-cyan">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="font-mono text-[11px] uppercase tracking-[0.25em]">In Progress</span>
                </div>
                <button
                    onClick={cancel}
                    data-testid="cancel-activity-button"
                    title="Cancel activity"
                    className="text-muted-foreground hover:text-neon-red transition-colors"
                >
                    <X className="w-4 h-4" />
                </button>
            </div>

            <div className="font-display font-bold text-lg text-white leading-tight" data-testid="activity-name">
                {activity.name}
            </div>

            <div className="flex items-center gap-2 mt-4 mb-2">
                <Clock className="w-4 h-4 text-neon-cyan" />
                <span className="font-mono text-2xl text-white tnum neon-text" data-testid="activity-timer">
                    {fmtDuration(activityRemaining)}
                </span>
            </div>

            <div className="h-2.5 w-full bg-white/5 border border-white/10 overflow-hidden rounded-sm">
                <div
                    className="h-full bg-neon-cyan transition-all duration-1000 progress-shimmer"
                    style={{
                        width: `${pct}%`,
                        backgroundImage: "linear-gradient(90deg, #00F3FF, #B026FF)",
                    }}
                />
            </div>
            <div className="font-mono text-[10px] text-muted-foreground mt-1.5 text-right tnum">{pct}%</div>

            {!compact && activity.blocking && (
                <div className="mt-3 text-[11px] text-neon-yellow/80 font-mono">
                    This activity blocks you physically. You can still browse, plan & manage finances.
                </div>
            )}
        </Panel>
    );
}
