import { KButton } from "@/components/game/controls";
import { Panel, Pill, RiskBadge, Money } from "@/components/game/primitives";
import { realDurationLabel, fmtDuration, gameDuration, SKILL_LABELS } from "@/lib/helpers";
import { useGame } from "@/context/GameContext";
import { Clock, Coins, Lock } from "lucide-react";
import { cn } from "@/lib/utils";

function effectChips(effects) {
    const entries = Object.entries(effects || {}).filter(([, v]) => v);
    return entries.slice(0, 6).map(([k, v]) => {
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

function skillChips(skillXp) {
    return Object.entries(skillXp || {}).filter(([, v]) => v).slice(0, 4).map(([k, v]) => (
        <span key={`sk-${k}`} className="font-mono text-[10px] px-1.5 py-0.5 rounded-sm border text-neon-cyan border-neon-cyan/30">
            +{Math.round(v)} {SKILL_LABELS[k] || k.replace("_", " ")} XP
        </span>
    ));
}

export default function ActionCard({ action, onStart, blocked, loading, ctaLabel = "Start", variant = "primary" }) {
    const { state, player } = useGame();
    const ts = state?.time_scale || 1;
    const available = action.available !== false;
    const onCd = (action.cooldown_remaining || 0) > 0;
    const cannotAfford = Number(action.money_cost || 0) > Number(player?.cash || 0) + Number(player?.bank || 0);
    const blockedReason = player?.status === "hospital" ? "Recovering in hospital" : player?.status === "jail" ? "Serving a jail sentence"
        : player?.on_shift ? "Finish your shift or clock out first" : "Finish or cancel your current activity first";
    const reason = blocked ? blockedReason : !available ? (onCd ? `Cooldown: ${fmtDuration(action.cooldown_remaining)}` : action.reason || "Requirements not met")
        : cannotAfford ? `Requires $${action.money_cost} in cash or bank` : null;
    const disabled = blocked || !available || cannotAfford || loading;

    return (
        <Panel className="p-4 flex flex-col h-full" data-testid={`action-card-${action.id}`}>
            <div className="flex items-start justify-between gap-2 mb-1">
                <h3 className="font-display font-bold text-white text-sm leading-relaxed">{action.name}</h3>
                {action.risk_level && <RiskBadge level={action.risk_level} />}
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed mb-3 flex-1">{action.result_text || action.desc}</p>

            <div className="flex flex-wrap gap-1 mb-3" data-testid={`action-gains-${action.id}`}>
                {effectChips(action.effects)}
                {skillChips(action.skill_xp)}
            </div>

            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground font-mono mb-2">
                <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {realDurationLabel(action.duration_minutes, ts)} real</span>
                {action.money_cost > 0 && <span className="flex items-center gap-1 text-neon-red"><Coins className="w-3 h-3" /> ${action.money_cost}</span>}
                {action.money_reward > 0 && <span className="flex items-center gap-1 text-neon-green"><Coins className="w-3 h-3" /> +${action.money_reward}</span>}
            </div>
            {ts !== 1 && <div className="text-xs text-muted-foreground mb-3">{gameDuration(action.duration_minutes)} at ×{ts} speed</div>}

            {reason && (
                <div className="flex items-start gap-1.5 text-xs text-neon-yellow mb-3" data-testid={`action-reason-${action.id}`}>
                    <Lock className="w-3 h-3 shrink-0 mt-0.5" /> {reason}
                </div>
            )}

            <KButton onClick={() => onStart(action)} disabled={disabled} loading={loading} variant={variant} className="w-full" data-testid={`start-action-${action.id}`}>
                {blocked ? "Unavailable" : cannotAfford ? "Not enough funds" : ctaLabel}
            </KButton>
        </Panel>
    );
}
