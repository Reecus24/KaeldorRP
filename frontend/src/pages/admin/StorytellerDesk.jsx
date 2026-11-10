import { useCallback, useEffect, useState } from "react";
import { api, errMessage } from "@/lib/api";
import { Panel, Spinner } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { toast } from "sonner";
import { JsonModal } from "./shared";

export default function StorytellerDesk() {
    const [data,setData]=useState(null), [selected,setSelected]=useState(null), [draft,setDraft]=useState(null), [note,setNote]=useState(""), [advanced,setAdvanced]=useState(false), [busy,setBusy]=useState(false);
    const load=useCallback(async()=>{try{setData((await api.get("/admin/world/intents")).data);}catch(e){toast.error(errMessage(e));}},[]);
    useEffect(()=>{load();},[load]);
    const review=async(approved)=>{setBusy(true);try{await api.put(`/admin/players/${selected.player_id}/world-intents/${selected.id}`,{approved,note,definition:draft});toast.success(approved?"Custom check approved":"Proposal declined");setSelected(null);await load();}catch(e){toast.error(errMessage(e));}finally{setBusy(false);}};
    if(!data)return <Spinner/>;
    return <div className="space-y-5"><Panel className="p-5"><h2 className="font-display text-2xl">The storyteller's desk</h2><p className="text-sm text-muted-foreground mt-2">Players describe an intention. Decide whether it is possible, choose a relevant skill and define the stakes. Approval creates a single-use check; the player reviews the odds before starting. No reward is granted by this approval.</p><p className="text-xs text-muted-foreground mt-2">Durations use game minutes. Skill level minus difficulty changes the success chance using Config → world. Outcome weights split success and failure; a zero weight disables that result. Advanced JSON controls all costs, supplies, prerequisites, rewards and consequences.</p></Panel>
        <KButton onClick={load}>Refresh proposals</KButton>
        {!data.requests.length&&<Panel className="p-6">No proposals waiting for review.</Panel>}
        {data.requests.map(i=><Panel key={i.id} className="p-5"><p className="text-xs text-neon-cyan">{i.player_name} · {i.region}</p><p className="my-3">{i.text}</p><KButton onClick={()=>{setSelected(i);setDraft({...data.template,id:i.id,name:"A new undertaking",regions:[i.region],description:i.text});setNote("");}}>Set the check</KButton></Panel>)}
        {selected&&<Panel className="p-6 space-y-4"><h3 className="font-display text-2xl">{selected.player_name}'s undertaking</h3><p>{selected.text}</p><div className="grid grid-cols-1 sm:grid-cols-2 gap-4">{[["name","Name","text"],["skill","Skill ID","text"],["difficulty","Difficulty","number"],["duration_minutes","Duration (game minutes)","number"]].map(([key,label,type])=><label key={key} className="text-sm">{label}<input className="block w-full mt-1 p-2 bg-black/30 border border-white/20 rounded" type={type} min={type==="number"?0:undefined} value={draft[key]} onChange={e=>setDraft({...draft,[key]:type==="number"?Number(e.target.value):e.target.value})}/></label>)}</div><p className="text-xs text-muted-foreground">Player skills: {Object.entries(selected.skills).map(([s,v])=>`${s}: ${v.level}`).join(" · ")}</p><KButton onClick={()=>setAdvanced(true)}>Edit outcomes & advanced rules</KButton><label className="block text-sm">Storyteller note<textarea className="block w-full mt-2 p-3 bg-black/30 border border-white/20 rounded" value={note} onChange={e=>setNote(e.target.value)} maxLength={1000}/></label><div className="flex flex-wrap gap-3"><KButton disabled={busy} onClick={()=>review(true)}>Approve check</KButton><KButton disabled={busy} variant="ghost" onClick={()=>review(false)}>Decline with note</KButton><KButton variant="ghost" onClick={()=>setSelected(null)}>Close</KButton></div></Panel>}
        <JsonModal open={advanced} title="Custom action rules" initial={draft} onClose={()=>setAdvanced(false)} onSave={obj=>{setDraft(obj);setAdvanced(false);}}/>
    </div>;
}
