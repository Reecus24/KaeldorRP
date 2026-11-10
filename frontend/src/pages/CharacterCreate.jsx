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
    const [creation, setCreation] = useState(null);
    const [loadError, setLoadError] = useState("");

    useEffect(() => {
        api.get("/world/creation").then(async ({data}) => {
            setCreation(data);
            if(data.random) { setSelected(data.origins.some(o=>o.weight>0) ? "random" : ""); }
            else { const res=await api.get("/backgrounds");setBackgrounds(res.data);setSelected(res.data[0]?.id||""); }
        }).catch(err => setLoadError(errMessage(err)));
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
                <p className="text-center text-muted-foreground mt-2 mb-8">{creation?.random ? "A beginning chosen by fate. A future shaped by what you learn." : "Your story begins with the origin you choose."}</p>

                <div className="max-w-sm mx-auto mb-8">
                    <KInput label="Character Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Rowan Ashford" maxLength={24} testid="character-name" />
                </div>

                {loadError && <p role="alert" className="text-center text-neon-red mb-4">{loadError}</p>}
                {creation?.random ? <div className="space-y-4"><Panel className="p-5 text-sm text-muted-foreground"><p>Your origin, age, starting coin and skill levels are rolled once when you create your character. You can learn any qualified profession later; this does not lock you into a class.</p><p className="mt-2">The Owner controls this pool, its weights and every range in Open World → Origin Picker.</p></Panel><div className="grid grid-cols-1 sm:grid-cols-3 gap-4">{creation.origins.filter(o=>o.weight>0).map(o=><Panel key={o.id} className="p-5"><p className="font-display text-xl text-white">{o.name}</p><p className="text-xs text-muted-foreground my-3">{o.description}</p><p className="text-xs text-neon-cyan">{Math.round(100*o.weight/creation.origins.reduce((n,x)=>n+x.weight,0))}% chance</p><p className="text-xs mt-2">Age {o.age[0]}–{o.age[1]} · {money(o.coins[0])}–{money(o.coins[1])}</p><div className="text-xs text-muted-foreground mt-3 space-y-1">{Object.entries(o.skills).map(([key,r])=><p key={key}>{worldLabel(key)} · level {r[0]}–{r[1]}</p>)}</div></Panel>)}</div>{!selected&&<p className="text-center">No weighted origins are enabled. Ask the Owner to configure the picker.</p>}</div> : backgrounds.length === 0 ? (
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
                        {creation?.random ? "Roll my beginning & enter" : "Enter the Ashen March"}
                    </KButton>
                </div>
            </div>
        </div>
    );
}
