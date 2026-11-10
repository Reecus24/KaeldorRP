import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { KButton, KInput } from "@/components/game/controls";
import { errMessage } from "@/lib/api";
import { Zap } from "lucide-react";

const HERO = "https://images.unsplash.com/photo-1590347945111-a14c8efd9249?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1Nzd8MHwxfHNlYXJjaHwyfHxkYXJrJTIwbmVvJTIwbm9pciUyMGNpdHklMjBzdHJlZXQlMjBuaWdodHxlbnwwfHx8fDE3ODI3ODg1Njh8MA&ixlib=rb-4.1.0&q=85";

export default function Login() {
    const { login } = useAuth();
    const navigate = useNavigate();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const submit = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            await login(email, password);
            navigate("/");
        } catch (err) {
            setError(errMessage(err));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex">
            <div className="hidden lg:block w-1/2 relative">
                <img src={HERO} alt="Kaeldor city" className="absolute inset-0 w-full h-full object-cover" />
                <div className="absolute inset-0 bg-gradient-to-r from-[#050505] via-[#050505]/70 to-transparent" />
                <div className="absolute bottom-12 left-12 right-12">
                    <h2 className="font-display font-black tracking-tighter text-5xl text-white leading-none neon-text">
                        THE CITY<br />NEVER SLEEPS.
                    </h2>
                    <p className="text-muted-foreground mt-4 max-w-md">
                        Start with nothing. Work shifts, study, hustle, build businesses — or take the risky road.
                        Time keeps moving whether you're online or not.
                    </p>
                </div>
            </div>

            <div className="flex-1 flex items-center justify-center p-6 kael-grid bg-[#050505]">
                <div className="w-full max-w-sm">
                    <div className="flex items-center gap-2 mb-8">
                        <Zap className="w-7 h-7 text-neon-cyan" />
                        <span className="font-display font-black tracking-tighter text-2xl">KAELDOR<span className="text-neon-cyan">.</span></span>
                    </div>
                    <h1 className="font-display font-bold text-2xl mb-1">Welcome back</h1>
                    <p className="text-sm text-muted-foreground mb-6">Log in to continue your life in Kaeldor.</p>

                    <form onSubmit={submit} className="space-y-4">
                        <KInput label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@kaeldor.com" testid="login-email" />
                        <KInput label="Password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" testid="login-password" />
                        {error && <div className="text-neon-red text-xs font-mono" data-testid="login-error">{error}</div>}
                        <KButton type="submit" loading={loading} className="w-full py-3" testid="login-submit" data-testid="login-submit">
                            Enter Kaeldor
                        </KButton>
                    </form>

                    <p className="text-sm text-muted-foreground mt-6">
                        New to the city?{" "}
                        <Link to="/register" className="text-neon-cyan hover:underline" data-testid="goto-register">Create an account</Link>
                    </p>
                </div>
            </div>
        </div>
    );
}
