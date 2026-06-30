import { useEffect, useRef, useState, useCallback } from "react";
import { toast } from "sonner";
import { api, errMessage } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { cn } from "@/lib/utils";
import { MessageSquare, X, Send, Minus, Users } from "lucide-react";

export default function ChatWidget() {
    const { hasCharacter, player } = useGame();
    const [open, setOpen] = useState(false);
    const [data, setData] = useState({ messages: [], online_count: 0 });
    const [text, setText] = useState("");
    const [sending, setSending] = useState(false);
    const scrollRef = useRef(null);
    const meId = player?.id;

    const load = useCallback(async () => {
        try {
            const { data } = await api.get("/chat/world?limit=60");
            setData(data);
        } catch { /* ignore */ }
    }, []);

    useEffect(() => {
        if (!hasCharacter) return;
        load();
        const id = setInterval(load, open ? 4000 : 20000);
        return () => clearInterval(id);
    }, [hasCharacter, open, load]);

    useEffect(() => {
        if (open && scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [data.messages, open]);

    const send = async () => {
        const msg = text.trim();
        if (!msg) return;
        setSending(true);
        try {
            await api.post("/chat/world", { message: msg });
            setText("");
            await load();
        } catch (e) { toast.error(errMessage(e)); }
        setSending(false);
    };

    if (!hasCharacter) return null;

    if (!open) {
        return (
            <button onClick={() => setOpen(true)} data-testid="chat-widget-open"
                className="fixed bottom-4 right-4 z-50 flex items-center gap-2 px-4 py-2.5 bg-neon-cyan text-black font-display font-bold text-sm rounded-full shadow-[0_0_20px_rgba(0,243,255,0.4)] hover:scale-105 transition-transform">
                <MessageSquare className="w-4 h-4" /> World Chat
                <span className="flex items-center gap-1 text-[11px] bg-black/20 px-1.5 py-0.5 rounded-full"><span className="w-1.5 h-1.5 rounded-full bg-neon-green animate-pulse-dot" />{data.online_count}</span>
            </button>
        );
    }

    return (
        <div className="fixed bottom-4 right-4 z-50 w-[92vw] max-w-[360px] h-[460px] flex flex-col bg-[#0A0A0A] border border-neon-cyan/30 rounded-md shadow-2xl overflow-hidden" data-testid="chat-widget">
            <div className="flex items-center justify-between px-3 h-11 border-b border-white/10 bg-[#0C0C0C] shrink-0">
                <div className="flex items-center gap-2">
                    <MessageSquare className="w-4 h-4 text-neon-cyan" />
                    <span className="font-display font-bold text-white text-sm">World Chat</span>
                    <span className="flex items-center gap-1 text-[10px] text-muted-foreground"><Users className="w-3 h-3 text-neon-green" />{data.online_count} online</span>
                </div>
                <button onClick={() => setOpen(false)} data-testid="chat-widget-close" className="text-muted-foreground hover:text-white"><Minus className="w-4 h-4" /></button>
            </div>

            <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2 space-y-2 bg-[#050505]" data-testid="chat-messages">
                {data.messages.length === 0 ? (
                    <div className="text-center text-muted-foreground text-xs font-mono py-8">No messages yet. Say hi to Kaeldor.</div>
                ) : data.messages.map((m) => (
                    <div key={m.id} className={cn("text-sm", m.player_id === meId && "text-right")}>
                        <div className="text-[10px] text-muted-foreground font-mono">
                            <span className={cn("font-bold", m.player_id === meId ? "text-neon-cyan" : "text-neon-purple")}>{m.name}</span>
                            <span className="ml-1 text-muted-foreground/40">{new Date(m.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                        </div>
                        <div className={cn("inline-block px-2.5 py-1.5 rounded-md mt-0.5 max-w-[85%] text-left break-words",
                            m.player_id === meId ? "bg-neon-cyan/15 text-white" : "bg-white/5 text-foreground")}>{m.message}</div>
                    </div>
                ))}
            </div>

            <div className="flex items-center gap-2 p-2 border-t border-white/10 bg-[#0C0C0C] shrink-0">
                <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()}
                    maxLength={280} placeholder="Message the city…" data-testid="chat-input"
                    className="flex-1 bg-white/5 border border-white/12 rounded-sm px-3 py-2 text-sm text-white placeholder:text-muted-foreground/50 focus:outline-none focus:border-neon-cyan/50" />
                <button onClick={send} disabled={sending || !text.trim()} data-testid="chat-send"
                    className="p-2 bg-neon-cyan text-black rounded-sm disabled:opacity-40 hover:bg-neon-cyan/80 transition-colors"><Send className="w-4 h-4" /></button>
            </div>
        </div>
    );
}
