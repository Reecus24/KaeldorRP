import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, InfoTip } from "@/components/game/primitives";
import { SKILL_LABELS, SKILL_INFO, XP_INFO } from "@/lib/helpers";
import { Sparkles } from "lucide-react";

export default function Skills() {
    const { player } = useGame();
    if (!player) return <Spinner />;

    const skills = player.skills || {};

    return (
        <div className="space-y-6">
            <SectionTitle icon={Sparkles} kicker="Your abilities" title="Skills"
                sub="Skills grow as you work, study and act. Higher skills unlock jobs, workshops and better outcomes." />

            <Panel className="p-3 flex items-center gap-2 text-[11px] text-muted-foreground" data-testid="skills-explainer">
                <InfoTip text={SKILL_INFO} testid="skills-info" />
                <span>Each skill levels up by filling its XP bar. <span className="text-foreground/80">{XP_INFO}</span></span>
            </Panel>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {Object.entries(SKILL_LABELS).map(([key, label]) => {
                    const s = skills[key] || { level: 1, xp: 0 };
                    const next = 120 * s.level;
                    const pct = Math.min(100, (s.xp / next) * 100);
                    return (
                        <Panel key={key} className="p-4" data-testid={`skill-${key}`}>
                            <div className="flex items-center justify-between mb-2">
                                <span className="font-display font-bold text-white text-sm">{label}</span>
                                <span className="font-mono text-neon-cyan text-lg tnum">Lv {s.level}</span>
                            </div>
                            <div className="h-2 bg-white/5 border border-white/10 rounded-sm overflow-hidden">
                                <div className="h-full bg-neon-cyan" style={{ width: `${pct}%`, boxShadow: "0 0 8px #D1B57988" }} />
                            </div>
                            <div className="font-mono text-[10px] text-muted-foreground mt-1 text-right tnum">{Math.round(s.xp)} / {next} XP</div>
                        </Panel>
                    );
                })}
            </div>
        </div>
    );
}
