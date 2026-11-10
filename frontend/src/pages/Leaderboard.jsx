import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SectionTitle, Spinner, Panel } from "@/components/game/primitives";
import { money } from "@/lib/helpers";
import { Trophy } from "lucide-react";
import { cn } from "@/lib/utils";

export default function Leaderboard() {
    const [data, setData] = useState(null);

    useEffect(() => { api.get("/leaderboard").then(({ data }) => setData(data)).catch(() => setData({ top: [], my_id: null })); }, []);
    if (!data) return <Spinner />;

    return (
        <div className="space-y-6">
            <SectionTitle icon={Trophy} kicker="Who runs Kaeldor" title="Hall of Renown"
                sub="The richest citizens in the realm, ranked by net worth." />

            <Panel className="p-0 overflow-hidden">
                <div className="grid grid-cols-12 gap-2 px-4 py-3 border-b border-white/8 bg-[#101A16] font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    <div className="col-span-1">#</div>
                    <div className="col-span-5">Citizen</div>
                    <div className="col-span-2 text-center">Lvl</div>
                    <div className="col-span-4 text-right">Net Worth</div>
                </div>
                {data.top.length === 0 && <div className="px-4 py-8 text-center text-muted-foreground">No players ranked yet.</div>}
                {data.top.map((p, i) => {
                    const isMe = p.id === data.my_id;
                    return (
                        <div key={p.id} className={cn("grid grid-cols-12 gap-2 px-4 py-3 items-center border-b border-white/5", isMe && "bg-neon-cyan/10")} data-testid={`rank-${i}`}>
                            <div className={cn("col-span-1 font-display font-bold", i === 0 ? "text-neon-yellow" : i < 3 ? "text-neon-cyan" : "text-muted-foreground")}>{i + 1}</div>
                            <div className="col-span-5 text-white font-medium truncate">{p.name}{isMe && <span className="text-neon-cyan text-[10px] ml-2 font-mono">YOU</span>}</div>
                            <div className="col-span-2 text-center font-mono text-muted-foreground tnum">{p.level}</div>
                            <div className="col-span-4 text-right font-mono text-neon-green tnum">{money(p.net_worth)}</div>
                        </div>
                    );
                })}
            </Panel>
        </div>
    );
}
