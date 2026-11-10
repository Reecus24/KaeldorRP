import { useEffect, useState, useCallback, useRef } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api, errMessage } from "@/lib/api";
import { useGame } from "@/context/GameContext";
import { SectionTitle, Spinner, Panel, Pill, EmptyState } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { relTime } from "@/lib/helpers";
import { cn } from "@/lib/utils";
import { Inbox, MessageSquare, Mail, Send, Plus, X, Ban, ShieldAlert, ScrollText as Smartphone, BookOpen as Laptop, ArrowLeft } from "lucide-react";

const CHANNELS = {
    whisper: { label: "Private RP", icon: MessageSquare, device: null },
    sms: { label: "Courier Note", icon: MessageSquare, device: "smartphone", deviceLabel: "Courier Seal" },
    email: { label: "Sealed Letter", icon: Mail, device: "laptop", deviceLabel: "Scribe's Kit" },
};

function Compose({ channel, directory, onClose, onSent }) {
    const [to, setTo] = useState("");
    const [subject, setSubject] = useState("");
    const [body, setBody] = useState("");
    const [busy, setBusy] = useState(false);

    const send = async () => {
        if (!to) return toast.error("Pick a recipient");
        if (!body.trim()) return toast.error("Write a message");
        setBusy(true);
        try {
            if (channel === "whisper") await api.post("/world/chat", {channel, peer: to, message: body, mode: "ooc"});
            else await api.post("/messages/send", { channel, to_player_id: to, subject: channel === "email" ? subject : null, body });
            toast.success("Message sent");
            onSent();
        } catch (e) { toast.error(errMessage(e)); }
        setBusy(false);
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-testid="compose-modal">
            <div className="absolute inset-0 bg-black/75" onClick={onClose} />
            <Panel className="relative w-full max-w-md p-5 space-y-3">
                <div className="flex items-center justify-between">
                    <span className="font-display font-bold text-white">New {CHANNELS[channel].label}</span>
                    <button onClick={onClose}><X className="w-5 h-5 text-muted-foreground" /></button>
                </div>
                <select value={to} onChange={(e) => setTo(e.target.value)} data-testid="compose-recipient"
                    className="w-full bg-white/5 border border-white/12 rounded-sm px-3 py-2 text-sm text-white focus:outline-none focus:border-neon-cyan/50">
                    <option value="">Select recipient…</option>
                    {directory.map((d) => <option key={d.id} value={d.id}>{d.name}{d.online ? " ● online" : ""}</option>)}
                </select>
                {channel === "email" && (
                    <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject" data-testid="compose-subject"
                        className="w-full bg-white/5 border border-white/12 rounded-sm px-3 py-2 text-sm text-white placeholder:text-muted-foreground/50 focus:outline-none focus:border-neon-cyan/50" />
                )}
                <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={channel === "email" ? 5 : 3} placeholder="Write your message…" data-testid="compose-body"
                    className="w-full bg-white/5 border border-white/12 rounded-sm px-3 py-2 text-sm text-white placeholder:text-muted-foreground/50 focus:outline-none focus:border-neon-cyan/50 resize-none" />
                <KButton variant="primary" className="w-full" loading={busy} onClick={send} data-testid="compose-send"><Send className="w-3.5 h-3.5" /> Send</KButton>
            </Panel>
        </div>
    );
}

function ThreadView({ thread, onBack, onChanged }) {
    const { player } = useGame();
    const [msgs, setMsgs] = useState(null);
    const [reply, setReply] = useState("");
    const [busy, setBusy] = useState(false);
    const meId = player?.id;
    const scrollRef = useRef(null);

    const load = useCallback(async () => {
        const { data } = await api.get(`/messages/thread/${thread.thread_id}`);
        setMsgs(data.messages);
        onChanged();
    }, [thread.thread_id, onChanged]);

    useEffect(() => { load(); }, [load]);
    useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; }, [msgs]);

    const send = async () => {
        if (!reply.trim()) return;
        setBusy(true);
        try {
            if (thread.channel === "whisper") await api.post("/world/chat", {channel: "whisper", peer: thread.other_id, message: reply, mode: "ooc"});
            else await api.post("/messages/send", { channel: thread.channel, to_player_id: thread.other_id,
                subject: thread.channel === "email" ? `Re: ${thread.subject || ""}` : null, body: reply, thread_id: thread.thread_id });
            setReply("");
            await load();
        } catch (e) { toast.error(errMessage(e)); }
        setBusy(false);
    };

    const block = async () => {
        try {
            const { data } = await api.post("/messages/block", { player_id: thread.other_id });
            toast.success(data.status === "blocked" ? `Blocked ${thread.other_name}` : `Unblocked ${thread.other_name}`);
        } catch (e) { toast.error(errMessage(e)); }
    };

    return (
        <Panel className="flex flex-col h-[60vh] lg:h-[68vh]">
            <div className="flex items-center justify-between px-3 h-12 border-b border-white/10 shrink-0">
                <div className="flex items-center gap-2 min-w-0">
                    <button onClick={onBack} className="lg:hidden text-muted-foreground"><ArrowLeft className="w-4 h-4" /></button>
                    <div className="min-w-0">
                        <div className="font-display font-bold text-white text-sm truncate">{thread.other_name}</div>
                        {thread.channel === "email" && <div className="text-[10px] text-muted-foreground truncate">{thread.subject}</div>}
                    </div>
                </div>
                <button onClick={block} title="Block / unblock" data-testid="block-button" className="text-muted-foreground hover:text-neon-red"><Ban className="w-4 h-4" /></button>
            </div>
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3 space-y-3 bg-[#101A16]" data-testid="thread-messages">
                {!msgs ? <Spinner /> : msgs.map((m) => (
                    <div key={m.id} className={cn(m.from_player_id === meId && "text-right")}>
                        {m.subject && <div className="text-[10px] text-neon-cyan font-mono mb-0.5">{m.subject}</div>}
                        <div className={cn("inline-block px-3 py-2 rounded-md max-w-[85%] text-left text-sm break-words",
                            m.from_player_id === meId ? "bg-neon-cyan/15 text-white" : "bg-white/5 text-foreground")}>{m.body}</div>
                        <div className="text-[9px] text-muted-foreground/50 font-mono mt-0.5">{new Date(m.ts).toLocaleString()}</div>
                    </div>
                ))}
            </div>
            <div className="flex items-center gap-2 p-2 border-t border-white/10 shrink-0">
                <input value={reply} onChange={(e) => setReply(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()}
                    placeholder={`Reply via ${thread.channel.toUpperCase()}…`} data-testid="thread-reply-input"
                    className="flex-1 bg-white/5 border border-white/12 rounded-sm px-3 py-2 text-sm text-white placeholder:text-muted-foreground/50 focus:outline-none focus:border-neon-cyan/50" />
                <button onClick={send} disabled={busy || !reply.trim()} data-testid="thread-send"
                    className="p-2 bg-neon-cyan text-black rounded-sm disabled:opacity-40 hover:bg-neon-cyan/80"><Send className="w-4 h-4" /></button>
            </div>
        </Panel>
    );
}

export default function Messages() {
    const { player, fetchMsgUnread } = useGame();
    const [channel, setChannel] = useState("sms");
    const [threads, setThreads] = useState(null);
    const [selected, setSelected] = useState(null);
    const [directory, setDirectory] = useState([]);
    const [composeOpen, setComposeOpen] = useState(false);

    const hasDevice = !CHANNELS[channel].device || !!player?.inventory?.[CHANNELS[channel].device];

    const loadThreads = useCallback(async () => {
        const { data } = await api.get(`/messages/threads?channel=${channel}`);
        setThreads(data);
        fetchMsgUnread();
    }, [channel, fetchMsgUnread]);

    useEffect(() => { setSelected(null); setThreads(null); loadThreads(); }, [loadThreads]);
    useEffect(() => { api.get("/players/directory").then(({ data }) => setDirectory(data)).catch(() => {}); }, []);

    const meta = CHANNELS[channel];

    return (
        <div className="space-y-6">
            <SectionTitle icon={Inbox} kicker="Communication" title="Messages"
                sub="Private RP is available without equipment for planning together. Courier Note is quick and casual (needs a courier seal); sealed letters are for longer, formal notes like job applications and offers (needs a scribe's kit)." />

            <div className="flex flex-wrap items-center gap-2">
                {Object.entries(CHANNELS).map(([k, c]) => (
                    <button key={k} onClick={() => setChannel(k)} data-testid={`messages-tab-${k}`}
                        className={cn("inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono uppercase tracking-wider rounded-sm border transition-colors",
                            channel === k ? "border-neon-cyan text-neon-cyan bg-neon-cyan/10" : "border-white/12 text-muted-foreground hover:text-white")}>
                        <c.icon className="w-3.5 h-3.5" /> {c.label}
                    </button>
                ))}
                <div className="ml-auto">
                    <KButton variant="primary" disabled={!hasDevice} onClick={() => setComposeOpen(true)} data-testid="compose-button"><Plus className="w-3.5 h-3.5" /> New {meta.label}</KButton>
                </div>
            </div>

            {!hasDevice && (
                <Panel className="p-4 border-neon-yellow/40 flex items-center gap-3" data-testid="device-gate-banner">
                    {channel === "sms" ? <Smartphone className="w-5 h-5 text-neon-yellow" /> : <Laptop className="w-5 h-5 text-neon-yellow" />}
                    <div className="flex-1 text-sm text-neon-yellow">You need a <strong>{meta.deviceLabel}</strong> to send {meta.label}.</div>
                    <Link to="/shop"><KButton variant="ghost">Go to Shop</KButton></Link>
                </Panel>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4">
                <div className={cn("space-y-2", selected && "hidden lg:block")}>
                    {!threads ? <Spinner /> : threads.length === 0 ? (
                        <EmptyState icon={meta.icon} title={`No ${meta.label} yet`} sub={hasDevice ? "Start a conversation with the New button." : `Buy a ${meta.deviceLabel} to get started.`} />
                    ) : threads.map((t) => (
                        <button key={t.thread_id} onClick={() => setSelected(t)} data-testid={`thread-${t.thread_id}`}
                            className={cn("w-full text-left p-3 border rounded-sm transition-colors",
                                selected?.thread_id === t.thread_id ? "border-neon-cyan bg-neon-cyan/10" : "border-white/10 hover:border-white/25 bg-white/[0.02]")}>
                            <div className="flex items-center justify-between">
                                <span className="font-display font-bold text-white text-sm truncate">{t.other_name}</span>
                                {t.unread > 0 && <span className="ml-2 min-w-[18px] h-[18px] px-1 rounded-full bg-neon-red text-[10px] font-bold text-black flex items-center justify-center">{t.unread}</span>}
                            </div>
                            {t.channel === "email" && t.subject && <div className="text-[11px] text-neon-cyan/80 truncate">{t.subject}</div>}
                            <div className="text-[11px] text-muted-foreground truncate">{t.last_from_me ? "You: " : ""}{t.last_body}</div>
                            <div className="text-[9px] text-muted-foreground/50 font-mono mt-0.5">{relTime((Date.now() - new Date(t.last_ts).getTime()) / 1000)}</div>
                        </button>
                    ))}
                </div>

                <div className={cn(!selected && "hidden lg:block")}>
                    {selected ? (
                        <ThreadView thread={selected} onBack={() => setSelected(null)} onChanged={loadThreads} />
                    ) : (
                        <Panel className="h-[68vh] hidden lg:flex items-center justify-center text-muted-foreground text-sm">Select a conversation</Panel>
                    )}
                </div>
            </div>

            {composeOpen && <Compose channel={channel} directory={directory} onClose={() => setComposeOpen(false)}
                onSent={() => { setComposeOpen(false); loadThreads(); }} />}
        </div>
    );
}
