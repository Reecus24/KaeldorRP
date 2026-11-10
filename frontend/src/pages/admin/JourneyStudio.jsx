import { useEffect, useState, useCallback } from "react";
import { Plus, Copy, Eye, Pencil, Save } from "lucide-react";
import { api, errMessage } from "@/lib/api";
import { Panel, Pill, Spinner } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { JsonModal } from "./shared";
import { Rewards } from "@/pages/Journey";
import { toast } from "sonner";

const names = { journey_goals: "Ambitions", story_arcs: "Stories", city_events: "City events" };
export default function JourneyStudio({ kind }) {
    const [items, setItems] = useState(null);
    const [templates, setTemplates] = useState({});
    const [edit, setEdit] = useState(null);
    const [advanced, setAdvanced] = useState(false);
    const [preview, setPreview] = useState(null);
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);
    const load = useCallback(async () => {
        try {
            const [content, defaults] = await Promise.all([api.get("/admin/content/" + kind), api.get("/admin/journey/templates")]);
            setItems(content.data); setTemplates(defaults.data); setError("");
        } catch (e) { setError(errMessage(e)); }
    }, [kind]);
    useEffect(() => { setItems(null); setEdit(null); setPreview(null); load(); }, [load]);
    const save = async (doc, isNew = false) => {
        setBusy(true);
        try {
            if (isNew) await api.post("/admin/content/" + kind, doc);
            else await api.put("/admin/content/" + kind + "/" + doc.id, doc);
            setEdit(null); setAdvanced(false); await load(); toast.success("Content saved");
        } catch (e) { toast.error(errMessage(e)); }
        finally { setBusy(false); }
    };
    const duplicate = (doc) => { setEdit({ isNew: true, doc: { ...JSON.parse(JSON.stringify(doc)), id: "", name: doc.name + " · copy", active: false } }); };
    const update = (key, value) => setEdit((e) => ({ ...e, doc: { ...e.doc, [key]: value } }));
    const previewDraft = async (doc) => {
        try { await api.post("/admin/journey/" + kind + "/validate", doc); setPreview(doc); }
        catch (e) { toast.error(errMessage(e)); }
    };
    if (!items && !error) return <Spinner />;
    return <div className="space-y-5" data-testid="journey-studio">
        <Panel className="p-5 border-neon-purple/25">
            <h2 className="font-display text-white text-xl font-bold">Content Workshop · {names[kind]}</h2>
            <p className="text-muted-foreground text-sm leading-relaxed mt-2">Create, duplicate and disable content here. Advanced JSON exposes every milestone, requirement, choice, cost, reward and follow-up. Read through a story before enabling it.</p>
            <p className="text-xs text-neon-cyan mt-3">Accepted stories and tracked ambitions keep their saved version. Edits apply to new starts. City schedules use real hours from the world's creation time.</p>
            <p className="text-xs text-muted-foreground mt-2">Requirement metrics: funds, bank, shifts, actions, courses, businesses, business_revenue, contacts, level, reputation, stories_completed, skill:driving or item:sandwich. Use since_start for new shifts, actions, courses or completed stories in the current chapter.</p>
        </Panel>
        {error && <p role="alert" className="text-neon-red">{error}<KButton onClick={load}>Retry</KButton></p>}
        <KButton variant="green" onClick={() => duplicate(templates[kind])} disabled={!templates[kind]}><Plus className="w-4 h-4" />New from template</KButton>
        <div className="space-y-3">{items?.map((it) => <Panel key={it.id} className="p-4 flex items-center justify-between gap-3 flex-wrap">
            <div className="min-w-0"><div className="text-white font-bold">{it.name}</div><p className="font-mono text-xs text-muted-foreground break-all mt-1">{it.id}</p></div>
            <div className="flex gap-2 flex-wrap items-center"><Pill tone={it.active !== false ? "green" : "yellow"}>{it.active !== false ? "Enabled" : "Disabled"}</Pill>
                <KButton variant="ghost" onClick={() => previewDraft(it)} aria-label={"Preview " + it.name}><Eye className="w-4 h-4" />Preview</KButton>
                <KButton variant="ghost" onClick={() => setEdit({ doc: JSON.parse(JSON.stringify(it)), isNew: false })}><Pencil className="w-4 h-4" />Edit</KButton>
                <KButton variant="ghost" onClick={() => duplicate(it)}><Copy className="w-4 h-4" />Duplicate</KButton>
                <KButton variant="ghost" disabled={busy} onClick={() => save({ ...it, active: it.active === false })}>{it.active === false ? "Enable" : "Disable"}</KButton>
            </div>
        </Panel>)}</div>
        {edit && <Panel className="p-5 space-y-4 border-neon-cyan/40">
            <h3 className="text-white font-bold">{edit.isNew ? "Create draft" : "Edit content"}</h3>
            {edit.isNew && <label className="block text-sm text-muted-foreground">Content ID · optional, auto-generated if empty<input className="block w-full mt-2 bg-black/30 border border-white/15 p-3 text-white font-mono" value={edit.doc.id} onChange={(e) => update("id", e.target.value)} /></label>}
            <label className="block text-sm text-muted-foreground">Name<input className="block w-full mt-2 bg-black/30 border border-white/15 p-3 text-white" value={edit.doc.name} onChange={(e) => update("name", e.target.value)} /></label>
            <label className="block text-sm text-muted-foreground">Description<textarea rows="3" className="block w-full mt-2 bg-black/30 border border-white/15 p-3 text-white" value={edit.doc.description || ""} onChange={(e) => update("description", e.target.value)} /></label>
            <label className="flex gap-2 text-sm text-white"><input type="checkbox" checked={edit.doc.active !== false} onChange={(e) => update("active", e.target.checked)} />Enabled for new starts</label>
            {kind === "city_events" && <div className="grid sm:grid-cols-3 gap-3">{[["offset_hours", "First start · real hours after world creation"], ["duration_hours", "Duration · real hours"], ["repeat_hours", "Repeat every · real hours"]].map(([key, label]) => <label key={key} className="text-xs text-muted-foreground">{label}<input type="number" min="0" className="block w-full bg-black/30 border border-white/15 p-3 mt-2 text-white" value={edit.doc[key]} onChange={(e) => update(key, Number(e.target.value))} /></label>)}</div>}
            <div className="flex gap-3 flex-wrap"><KButton disabled={busy} variant="green" onClick={() => save(edit.doc, edit.isNew)}><Save className="w-4 h-4" />Save</KButton><KButton variant="ghost" onClick={() => setAdvanced(true)}>Edit all fields · JSON</KButton><KButton variant="ghost" onClick={() => previewDraft(edit.doc)}>Preview draft</KButton><KButton variant="ghost" onClick={() => setEdit(null)}>Cancel</KButton></div>
        </Panel>}
        {preview && <Panel className="p-5 border-neon-purple/40" data-testid="story-preview">
            <div className="flex justify-between gap-4"><h3 className="text-xl font-display text-white font-bold">Preview · {preview.name}</h3><KButton variant="ghost" onClick={() => setPreview(null)}>Close</KButton></div><p className="text-sm text-muted-foreground mt-3">{preview.description}</p>
            <p className="text-xs text-neon-purple mt-3">Read-through only. No player progress or rewards are changed.</p>
            {(preview.nodes || preview.milestones || []).map((n) => <div key={n.id} className="border-t border-white/10 pt-4 mt-4">
                <h4 className="text-white font-bold">{n.title || n.name} <span className="text-xs font-mono text-muted-foreground">({n.id})</span></h4><p className="text-muted-foreground text-sm mt-2">{n.text}</p><Rewards values={n.rewards} />
                {(n.requirements || []).map((r, i) => <p key={i} className="text-xs text-muted-foreground mt-2">{r.label || r.metric}: {r.target}{r.since_start ? " new since this step began" : ""}</p>)}
                {n.choices?.map((c) => <div key={c.id} className="p-3 mt-3 bg-black/20 text-sm"><div className="text-white font-bold">{c.label} → {c.next || "Finish"}</div><p className="text-muted-foreground mt-1">{c.detail}</p>{c.cost > 0 && <p className="text-neon-yellow mt-1">Cost: {"$" + c.cost}</p>}<Rewards values={c.rewards} />{(c.requirements || []).map((r, i) => <p key={i} className="text-xs text-muted-foreground">{r.label || r.metric}: {r.target}</p>)}<p className="text-muted-foreground mt-2">{c.outcome}</p></div>)}
            </div>)}
            {preview.arc_ids && <p className="text-sm text-neon-cyan mt-4">Opens stories: {preview.arc_ids.join(", ")}</p>}
        </Panel>}
        <JsonModal open={advanced} title="Edit complete definition" initial={edit?.doc} onClose={() => setAdvanced(false)} onSave={async (doc) => {
            try {
                await api.post("/admin/journey/" + kind + "/validate", doc);
                setEdit((e) => ({ ...e, doc: { ...doc, id: e.isNew ? doc.id : e.doc.id } }));
                setAdvanced(false);
            } catch (e) { toast.error(errMessage(e)); }
        }} />
    </div>;
}
