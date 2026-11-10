import { useEffect, useState } from "react";
import { api, errMessage } from "@/lib/api";
import { Panel, Spinner } from "@/components/game/primitives";
import { KButton } from "@/components/game/controls";
import { JsonModal } from "./shared";
import { toast } from "sonner";

export default function WorldCharacters() {
    const [players,setPlayers]=useState(null),[selected,setSelected]=useState(null),[draft,setDraft]=useState(null);
    useEffect(()=>{api.get("/admin/players").then(({data})=>setPlayers(data)).catch(e=>toast.error(errMessage(e)));},[]);
    const open=async p=>{try{const {data}=await api.get(`/admin/players/${p.id}/world`);setSelected(p);setDraft(data);}catch(e){toast.error(errMessage(e));}};
    const save=async data=>{try{await api.put(`/admin/players/${selected.id}/world`,data);toast.success("Character world state updated");setSelected(null);}catch(e){toast.error(errMessage(e));}};
    if(!players)return <Spinner/>;
    return <div className="space-y-4"><Panel className="p-5"><h2 className="font-display text-2xl">Characters & memories</h2><p className="text-sm text-muted-foreground mt-2">Edit a character's current region, chosen title, skill levels and XP, successful lesson counts or NPC memories. Empty training or memory objects clear those fields. This settles elapsed play first and preserves quests, founded groups and other progress.</p><p className="text-xs text-muted-foreground mt-2">A title alone does not grant qualifications: actions still check skills and training. Skill XP must be below the next level threshold. Memories contain things said in conversation; verified quest outcomes remain separate.</p></Panel>{players.map(p=><Panel key={p.id} className="p-4 flex items-center justify-between gap-3"><span>{p.name}</span><KButton onClick={()=>open(p)}>Edit world state</KButton></Panel>)}<JsonModal open={!!selected} title={`World state · ${selected?.name||""}`} initial={draft} onClose={()=>setSelected(null)} onSave={save}/></div>;
}
