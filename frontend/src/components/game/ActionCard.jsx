import { KButton } from "@/components/game/controls";
import { Panel, Pill, RiskBadge, Money } from "@/components/game/primitives";
import { realDurationLabel, fmtDuration } from "@/lib/helpers";
import { useGame } from "@/context/GameContext";
import { Clock, Coins, Lock } from "lucide-react";
import { cn } from "@/lib/utils";

const POSITIVE_GOOD = ["energy", "hygiene", "mood", "health", "reputation", "legal_reputation", "social_status"];

function effectChips(effects) {
    const entries = Object.entries(effects || {}).filter(([, v]) => v);
    return entries.slice(0, 6).map(([k, v]) => {
        const goodWhenPositive = POSITIVE_GOOD.includes(k) || ["fatigue", "stress", "hunger", "criminal_suspicion"].indexOf(k) === -1;
        // hunger/fatigue/stress/suspicion: negative is good
        const inverse = ["fatigue", "stress", "hunger", "criminal_suspicion"].includes(k);
        const good = inverse ? v < 0 : v > 0;
        return (
            <span
                key={k}
                className={cn("font-mono text-[10px] px-1.5 py-0.5 rounded-sm border", good ? "text-neon-green border-neon-green/30" : "text-neon-red border-neon-red/30")}
            >
                {v > 0 ? "+" : ""}
                {Math.round(v)} {k.replace("_", " ")}
            </span>
        );
    });
}

export default function ActionCard({ action, onStart, blocked, loading, ctaLabel = "Start", variant = "primary" }) {
    const { state } = useGame();
    const ts = state?.time_scale || 1;
    const available = action.available !== false;
    const onCd = (action.cooldown_remaining || 0) > 0;
    const disabled = blocked || !available || loading;

    return (
        <Panel className="p-4 flex flex-col h-full" data-testid={`action-card-${action.id}`}>
            <div className="flex items-start justify-between gap-2 mb-1">
                <h3 className="font-display font-bold text-white text-sm leading-tight">{action.name}</h3>
                {action.risk_level && <RiskBadge level={action.risk_level} />}
            </div>
            <p className="text-[11px] text-muted-foreground mb-3 flex-1">{action.result_text || action.desc}</p>

            <div className="flex flex-wrap gap-1 mb-3">{effectChips(action.effects || action.skill_xp_display)}</div>

            <div className="flex items-center gap-3 text-[11px] text-muted-foreground font-mono mb-3">
                <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {realDurationLabel(action.duration_minutes, ts)}</span>
                {action.money_cost > 0 && <span className="flex items-center gap-1 text-neon-red"><Coins className="w-3 h-3" /> ${action.money_cost}</span>}
                {action.money_reward > 0 && <span className="flex items-center gap-1 text-neon-green"><Coins className="w-3 h-3" /> +${action.money_reward}</span>}
            </div>

            {!available && action.reason && (
                <div className="flex items-center gap-1 text-[11px] text-neon-yellow font-mono mb-2">
                    <Lock className="w-3 h-3" /> {onCd ? `Cooldown ${fmtDuration(action.cooldown_remaining)}` : action.reason}
                </div>
            )}

            <KButton onClick={() => onStart(action)} disabled={disabled} loading={loading} variant={variant} className="w-full" data-testid={`start-action-${action.id}`}>
                {blocked ? "Busy" : ctaLabel}
            </KButton>
        </Panel>
    );
}
