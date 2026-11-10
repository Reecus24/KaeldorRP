import { useGame } from "@/context/GameContext";
import { Link } from "react-router-dom";
import { Panel } from "@/components/game/primitives";
import { fmtDuration, scheduleLabel } from "@/lib/helpers";
import { api } from "@/lib/api";
import { Loader2, X, Clock, Coffee, Briefcase, LogOut, Stethoscope, Lock } from "lucide-react";

export default function ActivityPanel({ compact = false }) {
    const { state, player, activityRemaining, activityProgress, confinementRemaining, act } = useGame();
    const activity = state?.activity;
    const onShift = player?.on_shift;

    const cancel = () =>
        act(() => api.post("/game/cancel-activity"), "Activity cancelled");
    const clockOut = () =>
        act(() => api.post(`/jobs/employment/${onShift.employment_id}/clock-out`), "You clocked out early");

    if (["hospital", "jail"].includes(player?.status)) {
        const hospital = player.status === "hospital";
        const remaining = confinementRemaining[player.status];
        const Icon = hospital ? Stethoscope : Lock;
        return (
            <Panel className="p-5 border-neon-red/30" data-testid={`activity-panel-${player.status}`}>
                <div className="flex items-center gap-2 text-neon-red mb-2">
                    <Icon className="w-4 h-4" />
                    <span className="font-mono text-[11px] uppercase tracking-[0.25em]">
                        {hospital ? "In Hospital" : "In Jail"}
                    </span>
                </div>
                <div className="font-mono text-2xl text-white tnum" data-testid="confinement-timer">
                    {remaining > 0 ? fmtDuration(remaining) : "Checking release…"}
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                    {hospital ? "Recovering until discharge. Work and other activities are unavailable."
                        : "Serving your sentence. Work and other activities are unavailable."}
                </p>
                <Link to={hospital ? "/hospital" : "/jail"}
                    className="inline-block text-xs text-neon-cyan hover:underline mt-3">
                    {hospital ? "View treatment & recovery" : "View sentence & bail"}
                </Link>
            </Panel>
        );
    }

    if (!activity && onShift) {
        return (
            <Panel className="p-5 neon-border" data-testid="activity-panel-onshift">
                <div className="flex items-center gap-2 text-neon-purple mb-1">
                    <Briefcase className="w-4 h-4" />
                    <span className="font-mono text-[11px] uppercase tracking-[0.25em]">On Shift</span>
                </div>
                <div className="font-display font-bold text-white leading-tight" data-testid="onshift-business">{onShift.business_name}</div>
                <div className="text-[11px] text-muted-foreground capitalize mt-0.5">{(onShift.role || "").replace(/_/g, " ")}</div>
                <div className="flex items-center gap-1.5 text-[11px] text-neon-purple mt-1"><Clock className="w-3 h-3" /> {scheduleLabel(onShift.schedule)}</div>
                <div className="text-[11px] text-muted-foreground mt-2">Auto-working — wages & business output accrue in real time. Physical activities are paused until your shift ends.</div>
                {!compact && (
                    <button onClick={clockOut} data-testid="onshift-clock-out"
                        className="mt-3 w-full inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-mono uppercase tracking-wider rounded-sm border border-neon-red/60 text-neon-red hover:bg-neon-red hover:text-white transition-colors">
                        <LogOut className="w-3.5 h-3.5" /> Clock Out Early
                    </button>
                )}
            </Panel>
        );
    }

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
