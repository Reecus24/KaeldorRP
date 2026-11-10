import { worldLabel } from "@/lib/helpers";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errMessage } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { KButton, KInput } from "@/components/game/controls";
import { Panel, Money, Spinner } from "@/components/game/primitives";
import { money } from "@/lib/helpers";
import { cn } from "@/lib/utils";
import { Shield as Zap, User } from "lucide-react";
import { toast } from "sonner";

export default function CharacterCreate() {
    const navigate = useNavigate();
    const { createCharacter } = useGame();
    const [name, setName] = useState("");
    const [backgrounds, setBackgrounds] = useState([]);
    const [selected, setSelected] = useState("drifter");
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        api.get("/backgrounds").then(({ data }) => { setBackgrounds(data); setSelected(data[0]?.id || ""); }).catch(() => {});
    }, []);

    const submit = async () => {
        if (!name.trim()) {
            toast.error("Enter a name for your character");
            return;
        }
        setLoading(true);
        try {
            await createCharacter(name.trim(), selected);
            toast.success(`Welcome to Kaeldor, ${name}!`);
            navigate("/");
        } catch (err) {
            toast.error(errMessage(err));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#101A16] kael-grid p-6 flex items-center justify-center">
            <div className="w-full max-w-3xl">
                <div className="flex items-center gap-2 mb-6 justify-center">
                    <Zap className="w-6 h-6 text-neon-cyan" />
                    <span className="font-display font-black tracking-tighter text-xl">KAELDOR<span className="text-neon-cyan">.</span></span>
                </div>
                <h1 className="font-display font-black tracking-tighter text-4xl text-center text-white">Create Your Character</h1>
                <p className="text-center text-muted-foreground mt-2 mb-8">Your story begins as an unemployed peasant. No title, no trade — only the future you earn.</p>

                <div className="max-w-sm mx-auto mb-8">
                    <KInput label="Character Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Rowan Ashford" maxLength={24} testid="character-name" />
                </div>

                {backgrounds.length === 0 ? (
                    <p className="text-center text-muted-foreground">No origins available yet. The Owner can enable one in the Sandbox.</p>
                ) : (
                    <div className={backgrounds.length === 1 ? "max-w-md mx-auto" : "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"}>
                        {backgrounds.map((bg) => (
                            <button
                                key={bg.id}
                                onClick={() => setSelected(bg.id)}
                                data-testid={`background-${bg.id}`}
                                className={cn(
                                    "text-left p-5 rounded-sm border transition-all",
                                    selected === bg.id
                                        ? "border-neon-cyan bg-neon-cyan/5 neon-border"
                                        : "border-white/10 bg-[#1B2520] hover:border-white/25",
                                )}
                            >
                                <div className="flex items-center gap-2 mb-2">
                                    <User className={cn("w-4 h-4", selected === bg.id ? "text-neon-cyan" : "text-muted-foreground")} />
                                    <span className="font-display font-bold text-white">{bg.label}</span>
                                </div>
                                <p className="text-xs text-muted-foreground mb-3 min-h-[32px]">{bg.desc}</p>
                                <div className="font-mono text-[11px] space-y-1">
                                    <div className="text-muted-foreground">Coin <Money value={bg.cash} /> · Vault <Money value={bg.bank} />{bg.debt ? <> · Debt <span className="text-neon-red">{money(bg.debt)}</span></> : null}</div>
                                    <div className="flex flex-wrap gap-1 mt-2">
                                        {Object.entries(bg.skills || {}).map(([s, v]) => (
                                            <span key={s} className="px-1.5 py-0.5 border border-neon-green/30 text-neon-green rounded-sm text-[10px] uppercase">
                                                +{v} {worldLabel(s)}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>
                )}

                <div className="flex justify-center mt-8">
                    <KButton onClick={submit} loading={loading} disabled={!selected} variant="solid" className="px-10 py-3" data-testid="create-character-submit">
                        Enter the Ashen March
                    </KButton>
                </div>
            </div>
        </div>
    );
}
