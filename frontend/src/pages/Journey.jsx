import { useState } from "react";
import { Link } from "react-router-dom";
import { Compass, ArrowRight, Check, BookOpen, Radio, Flag } from "lucide-react";
import { toast } from "sonner";
import { api, errMessage } from "@/lib/api";
import { money } from "@/lib/helpers";
import { useJourney } from "@/hooks/useJourney";
import { useGame } from "@/context/GameContext";
import { Panel, SectionTitle, Spinner, Pill } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";

export function Rewards({ values = {} }) {
    const items = Object.entries(values).flatMap(([key, value]) => {
        if (key === "cash") return [money(value)];
        if (key === "skills") return Object.entries(value).map(([skill, xp]) => "+" + xp + " " + skill.replaceAll("_", " ") + " XP");
        if (key === "items") return Object.entries(value).map(([item, qty]) => qty + " × " + item.replaceAll("_", " "));
        return [(value >= 0 ? "+" : "") + value + " " + (key === "xp" ? "XP" : key.replaceAll("_", " "))];
    });
    return items.length ? <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs font-mono text-neon-green">{items.map((s) => <span key={s} className={s.startsWith("-") ? "text-neon-red" : undefined}>{s}</span>)}</div> : null;
}

export function Requirements({ rows = [] }) {
    return <div className="space-y-2">{rows.map((r, i) => <div key={i} className="text-sm">
        <div className="flex items-start justify-between gap-3">
            <span className={r.met ? "text-neon-green" : "text-muted-foreground"}>{r.met && <Check className="inline w-3 h-3 mr-1" />}{r.label || r.metric}</span>
            <span className="font-mono text-xs text-white whitespace-nowrap">{Math.floor(r.current)} / {r.target}</span>
        </div>
        <div className="h-1 bg-white/10 mt-2 rounded overflow-hidden"><div className="h-full bg-neon-cyan" style={{ width: Math.min(100, r.target === 0 ? 100 : r.current / r.target * 100) + "%" }} /></div>
        {!r.met && <Link to={r.href || "/journey"} className="inline-block text-xs text-neon-cyan mt-2 underline underline-offset-4">Make progress →</Link>}
    </div>)}</div>;
}

export function JourneyTeaser() {
    const { data } = useJourney();
    if (!data) return null;
    const goal = data.goals.find((g) => g.focused);
    const next = goal?.milestones.find((m) => !m.claimed);
    const story = data.stories.find((s) => !s.completed);
    const event = data.city_events.find((e) => e.is_live);
    return <Panel className="p-5 sm:p-6 border-neon-purple/30 bg-gradient-to-r from-neon-purple/10 to-transparent" data-testid="journey-teaser">
        <div className="flex items-start gap-4"><Compass className="w-6 h-6 text-neon-purple shrink-0" />
            <div className="flex-1 min-w-0"><div className="font-mono text-xs uppercase tracking-widest text-neon-purple">Your story in Kaeldor</div>
                <h2 className="font-display text-xl text-white font-bold mt-2">{goal?.name || "What kind of life will you build?"}</h2>
                <p className="text-sm text-muted-foreground mt-2">{next ? "Next milestone: " + next.name : goal ? "Ambition completed. Choose your next direction." : "Choose an ambition, meet Mira and find a place in your neighbourhood."}</p>
                {(story || event) && <p className="text-xs text-neon-cyan mt-3">{story ? "Continue: " + story.name : "In the realm: " + event.name}</p>}
                <Link to="/journey" className="inline-flex gap-2 items-center text-white font-bold mt-4 min-h-[44px]">Open your journal <ArrowRight className="w-4 h-4" /></Link>
            </div>
        </div>
    </Panel>;
}

function StoryCard({ story, busy, act }) {
    const node = story.node;
    const last = story.history.at(-1);
    return <Panel className="p-5 sm:p-7 border-neon-purple/25" data-testid={"story-" + story.id}>
        <div className="flex gap-3 justify-between flex-wrap"><div><p className="font-mono text-xs uppercase tracking-wider text-neon-purple">{story.contact || "Your story"}</p><h2 className="text-xl font-display font-bold text-white mt-2">{story.name}</h2></div>{story.completed && <Pill tone="green">Completed</Pill>}</div>
        {last && <div className="border-l-2 border-neon-green/50 pl-4 my-5 text-sm text-white/80 leading-relaxed" role="status">{last.outcome}</div>}
        {node && <div className="mt-5">
            <h3 className="text-lg text-white font-bold">{node.title}</h3>
            <p className="text-muted-foreground text-sm leading-relaxed mt-2 max-w-3xl">{node.text}</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-5">{node.choices.map((c) => <div key={c.id} className="p-4 bg-black/20 border border-white/10 rounded-sm flex flex-col gap-3">
                <h4 className="font-bold text-white">{c.label}</h4>{c.detail && <p className="text-sm text-muted-foreground">{c.detail}</p>}
                {c.cost > 0 && <p className="text-xs text-neon-yellow font-mono">Cost: {money(c.cost)} from cash / bank</p>}
                {Object.entries(c.consume_items || {}).map(([item, qty]) => <p key={item} className="text-xs text-neon-yellow">Uses {qty} × {item.replaceAll("_", " ")}</p>)}
                <Requirements rows={c.progress} /><Rewards values={c.rewards} />
                {!c.available && <p className="text-xs text-muted-foreground">{c.reasons.join(" · ")}</p>}
                <KButton className="mt-auto min-h-[44px]" disabled={busy || !c.available} onClick={() => act("/journey/stories/" + story.id + "/choose", { node_id: node.id, choice_id: c.id })}>Choose this approach <ArrowRight className="w-4 h-4" /></KButton>
            </div>)}</div>
        </div>}
        {story.history.length > 0 && <details className="mt-5 border-t border-white/10 pt-4"><summary className="cursor-pointer text-sm text-muted-foreground">Your choices so far ({story.history.length})</summary><ol className="space-y-3 mt-4">{story.history.map((h, i) => <li key={i} className="text-sm"><span className="text-white">{h.choice}</span><p className="text-muted-foreground mt-1">{h.outcome}</p></li>)}</ol></details>}
    </Panel>;
}

export default function Journey() {
    const { data, error, load } = useJourney();
    const { refresh } = useGame();
    const [tab, setTab] = useState("stories");
    const [busy, setBusy] = useState(false);
    const act = async (url, body = {}) => {
        if (busy) return;
        setBusy(true);
        try { await api.post(url, body); await Promise.all([load(), refresh()]); }
        catch (e) { toast.error(errMessage(e)); await load(); }
        finally { setBusy(false); }
    };
    if (!data && !error) return <Spinner />;
    return <div className="space-y-6">
        <SectionTitle icon={Compass} kicker="A life with direction" title="Chronicle" sub="Ambitions to work towards. People to remember. Decisions that become your story." />
        {error && <Panel className="p-4 text-neon-yellow" role="alert">{error}<KButton onClick={load} variant="ghost">Try again</KButton></Panel>}
        {data && <>
            <nav className="flex gap-2 flex-wrap" aria-label="Journal sections">{[["stories", "Stories", BookOpen], ["goals", "Ambitions", Flag], ["city", "In the realm", Radio]].map(([key, label, Icon]) => <KButton key={key} variant={tab === key ? "primary" : "ghost"} onClick={() => setTab(key)} aria-pressed={tab === key}><Icon className="w-4 h-4" />{label}</KButton>)}</nav>
            {tab === "stories" && <div className="space-y-5">
                <p className="text-sm text-muted-foreground">Accepted stories have no deadline. You can plan your next choice while working; physical progress still uses normal activities.</p>
                {data.stories.filter((s) => !s.completed).map((s) => <StoryCard key={s.id} story={s} busy={busy} act={act} />)}
                <div><h2 className="font-display font-bold text-lg text-white mb-3">New opportunities</h2>
                    {data.offers.length === 0 && <p className="text-muted-foreground text-sm">No new offers right now. Your ambitions and accepted stories are still available.</p>}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{data.offers.map((o) => <Panel key={o.run_id} className="p-5 flex flex-col gap-3">
                        <div className="text-xs font-mono text-neon-cyan">{o.event_name || o.contact || "A local story"}</div><h3 className="text-white font-display font-bold text-lg">{o.name}</h3><p className="text-sm text-muted-foreground leading-relaxed">{o.description}</p>
                        <Requirements rows={o.progress} />{!o.available && <p className="text-xs text-neon-yellow">{o.reasons.join(" · ")}</p>}
                        <KButton className="mt-auto" disabled={busy || !o.available} onClick={() => act("/journey/stories/" + o.id + "/start", { event_id: o.event_id })}>Accept story</KButton>
                    </Panel>)}</div>
                </div>
                {data.stories.some((s) => s.completed) && <details><summary className="cursor-pointer text-muted-foreground py-3">Completed stories</summary><div className="space-y-4">{data.stories.filter((s) => s.completed).map((s) => <StoryCard key={s.id} story={s} busy={busy} act={act} />)}</div></details>}
            </div>}
            {tab === "goals" && <div className="space-y-4"><p className="text-sm text-muted-foreground">You can change direction at any time. Your completed milestones stay with you.</p>{[...data.goals].sort((a, b) => Number(b.focused) - Number(a.focused)).map((g) => {
                const next = g.milestones.find((m) => !m.claimed);
                return <Panel key={g.id} className={"p-5 sm:p-6 " + (g.focused ? "border-neon-cyan/40" : "")}>
                    <div className="flex justify-between items-start gap-4 flex-wrap"><div><h2 className="text-white text-xl font-display font-bold">{g.name}</h2><p className="text-sm text-muted-foreground mt-2">{g.description}</p></div><Pill tone={g.completed ? "green" : g.focused ? "cyan" : "purple"}>{g.completed ? "Completed" : g.focused ? "Your focus" : "Choose your direction"}</Pill></div>
                    <div className="flex gap-1 mt-5" aria-label="Milestone progress">{g.milestones.map((m) => <div key={m.id} title={m.name} className={"h-1.5 flex-1 " + (m.claimed ? "bg-neon-green" : "bg-white/10")} />)}</div>
                    {next && <div className="my-5 max-w-2xl space-y-3"><h3 className="text-white font-bold">{next.name}</h3><Requirements rows={next.progress} /><Rewards values={next.rewards} /></div>}
                    <div className="flex flex-wrap gap-3">{!g.focused && <KButton disabled={busy} onClick={() => act("/journey/goals/" + g.id + "/track")}>{g.tracked ? "Make this my focus" : "Follow this ambition"}</KButton>}
                    {g.tracked && next && <KButton variant="green" disabled={busy || !next.ready} onClick={() => act("/journey/goals/" + g.id + "/claim/" + next.id)}>Complete milestone</KButton>}</div>
                    <details className="mt-4"><summary className="text-sm text-muted-foreground cursor-pointer">See the whole path</summary><ol className="mt-3 space-y-2">{g.milestones.map((m) => <li key={m.id} className={m.claimed ? "text-neon-green text-sm" : "text-muted-foreground text-sm"}>{m.claimed ? "✓ " : "○ "}{m.name}</li>)}</ol></details>
                </Panel>;
            })}</div>}
            {tab === "city" && <div className="space-y-4"><p className="text-sm text-muted-foreground">Realm occasions repeat. Accept an opportunity while it is open, then finish at your own pace. Times below use your local clock.</p>
                {data.city_events.length === 0 && <Panel className="p-5 text-muted-foreground">The realm noticeboard is quiet. Check back for new occasions.</Panel>}
                {data.city_events.map((e) => <Panel key={e.id} className={"p-5 sm:p-6 " + (e.is_live ? "border-neon-cyan/30" : "")}>
                    <Pill tone={e.is_live ? "green" : "purple"}>{e.is_live ? "Happening now" : "Coming up"}</Pill><h2 className="font-display text-xl text-white font-bold mt-3">{e.name}</h2><p className="text-muted-foreground text-sm my-3">{e.description}</p>
                    <p className="text-xs font-mono text-muted-foreground">{e.is_live ? "Offers close: " : "Starts: "}{new Date(e.is_live ? e.ends_at : e.starts_at).toLocaleString()}</p>
                    {e.is_live && <KButton className="mt-4" onClick={() => setTab("stories")}>Explore opportunities <ArrowRight className="w-4 h-4" /></KButton>}
                </Panel>)}
            </div>}
        </>}
    </div>;
}
