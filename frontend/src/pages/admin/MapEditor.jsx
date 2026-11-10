import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { MapPin, Trees, Palette, Plus, Save, RotateCcw, Code, MousePointer2, Trash2, Route } from "lucide-react";
import { api, errMessage } from "@/lib/api";
import { Spinner } from "@/components/game/primitives";
import WorldMap from "@/components/game/WorldMap";
import { JsonModal } from "./shared";
import { toast } from "sonner";
import "./map-editor.css";

const clone = obj => JSON.parse(JSON.stringify(obj));
const same = (a,b) => JSON.stringify(a) === JSON.stringify(b);
const uid = prefix => `${prefix}_${crypto.randomUUID().replace(/-/g, "").slice(0,12)}`;
const clamp = n => Math.round(Math.max(0,Math.min(100,n))*100)/100;
const TERRAIN = { forest: "Forest", mountains: "Mountains", lake: "Lake", river: "River" };
function NumberField({ label, value, onChange, max=100 }) {
    return <label>{label}<input type="number" min="0" max={max} step="any" value={value ?? ""} onChange={e=>onChange(e.target.value===""?"":Number(e.target.value))}/></label>;
}

export default function MapEditor() {
    const [saved,setSaved]=useState(null),[draft,setDraft]=useState(null),[original,setOriginal]=useState(null),[isNew,setIsNew]=useState(false);
    const [appearance,setAppearance]=useState(null),[start,setStart]=useState(""),[layer,setLayer]=useState("places"),[terrainId,setTerrainId]=useState("");
    const [placing,setPlacing]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(""),[modal,setModal]=useState(null);
    const placeDirty=!!draft&&(isNew||!same(draft,original)),mapDirty=!!saved&&(!same(appearance,saved.appearance)||start!==saved.start_region);
    const load=async()=>{setBusy(true);setError("");try{const {data}=await api.get("/admin/world/map");setSaved(data);setAppearance(clone(data.appearance));setStart(data.start_region);setDraft(null);setOriginal(null);setIsNew(false);setPlacing(false);setTerrainId("");}catch(e){setError(errMessage(e));}finally{setBusy(false);}};
    useEffect(()=>{load();},[]);
    useEffect(()=>{if(!placeDirty&&!mapDirty)return;const warn=e=>{e.preventDefault();e.returnValue="";};window.addEventListener("beforeunload",warn);return()=>window.removeEventListener("beforeunload",warn);},[placeDirty,mapDirty]);
    const confirmPlace=()=>!placeDirty||window.confirm("Discard the unsaved location changes?");
    const select=id=>{if(draft?.id===id)return true;if(!confirmPlace())return false;const item=saved.regions.find(r=>r.id===id);if(!item)return false;setDraft(clone(item));setOriginal(clone(item));setIsNew(false);setPlacing(false);setError("");return true;};
    const newPlace=()=>{if(!confirmPlace())return;setDraft({id:uid("place"),name:"New location",biome:"village",description:"",x:50,y:50,connections:[],active:true});setOriginal(null);setIsNew(true);setPlacing(true);setLayer("places");setError("");};
    const patchPlace=patch=>setDraft(d=>({...d,...patch}));
    const patchTerrain=(id,patch)=>setAppearance(a=>({...a,terrain:a.terrain.map(f=>f.id===id?{...f,...patch}:f)}));
    const move=(target,point)=>{if(target.kind==="place")setDraft(d=>d?.id===target.id?{...d,...point}:d);else setAppearance(a=>({...a,terrain:a.terrain.map(f=>f.id!==target.id?f:f.kind==="river"?{...f,points:f.points.map((p,i)=>i===target.index?[point.x,point.y]:p)}:{...f,...point})}));};
    const pick=target=>{if(target.kind==="terrain"){setTerrainId(target.id);return true;}if(!select(target.id))return false;setPlacing(false);return true;};
    const nudge=(target,[dx,dy])=>{const f=target.kind==="place"?(draft?.id===target.id?draft:saved.regions.find(r=>r.id===target.id)):appearance.terrain.find(r=>r.id===target.id);const p=f.kind==="river"?{x:f.points[target.index][0],y:f.points[target.index][1]}:f;move(target,{x:clamp(Number(p.x)+dx),y:clamp(Number(p.y)+dy)});};
    const savePlace=async(value=draft)=>{setBusy(true);setError("");try{const result=isNew?await api.post("/admin/content/world_regions",value):await api.put(`/admin/world/map/regions/${original.id}`,{expected:original,region:value});const region=result.data.region||value;setSaved(s=>({...s,regions:isNew?[...s.regions,region]:s.regions.map(r=>r.id===region.id?region:r)}));setDraft(clone(region));setOriginal(clone(region));setIsNew(false);setPlacing(false);setModal(null);toast.success("Location saved to the world");}catch(e){setError(errMessage(e));toast.error(errMessage(e));}finally{setBusy(false);}};
    const saveMap=async(value=appearance)=>{setBusy(true);setError("");try{const {data}=await api.put("/admin/world/map/style",{expected:saved.appearance,appearance:value,expected_start:saved.start_region,start_region:start});setSaved(s=>({...s,appearance:data.appearance,start_region:data.start_region}));setAppearance(clone(data.appearance));setModal(null);toast.success("Map saved to the world");}catch(e){setError(errMessage(e));toast.error(errMessage(e));}finally{setBusy(false);}};
    const addTerrain=kind=>{const f={id:uid(kind),name:`New ${TERRAIN[kind].toLowerCase()}`,kind,...(kind==="river"?{width:2,points:[[45,20],[50,50],[55,80]]}:{x:50,y:50,width:20,height:20})};setAppearance(a=>({...a,terrain:[...a.terrain,f]}));setTerrainId(f.id);};
    if(!saved)return <div className="map-editor">{error?<div role="alert">{error}<button onClick={load}>Retry</button></div>:<Spinner/>}</div>;
    const regions=[...saved.regions.filter(r=>r.id!==draft?.id),...(draft?[{...draft,x:Number(draft.x)||0,y:Number(draft.y)||0}]:[])];
    const feature=appearance.terrain.find(f=>f.id===terrainId);
    const terrainPreview={...appearance,terrain:appearance.terrain.map(f=>({...f,width:Number(f.width)||0,height:Number(f.height)||0,x:Number(f.x)||0,y:Number(f.y)||0,...(f.points?{points:f.points.map(p=>p.map(v=>Number(v)||0))}:{})}))};
    const routeChange=(index,patch)=>patchPlace({connections:draft.connections.map((r,i)=>i===index?{...r,...patch}:r)});
    return <section className="map-editor" aria-label="Map editor">
        <header className="map-editor-heading"><div><span className="map-eyebrow">OWNER'S ATLAS</span><h2>Shape your realm</h2><p>Build places, connect journeys and draw the landscape. Save your drafts to update the shared world.</p></div><button disabled={busy} onClick={()=>{if((!placeDirty&&!mapDirty)||window.confirm("Discard all unsaved map changes and reload?"))load();}}><RotateCcw size={15}/> Reload saved map</button></header>
        <div className="map-editor-tabs" role="tablist" aria-label="Map layers">{[["places","Places & routes",MapPin],["terrain","Landscape",Trees],["style","Map style",Palette]].map(([key,label,Icon])=><button key={key} role="tab" id={`map-layer-${key}`} aria-selected={layer===key} aria-controls="map-layer-panel" onClick={()=>{setLayer(key);setPlacing(false);}}><Icon size={16}/>{label}{(key==="places"?placeDirty:mapDirty)&&<span className="map-unsaved-dot" aria-label="Unsaved changes"/>}</button>)}</div>
        {error&&<div className="map-editor-error" role="alert">{error}</div>}
        <div className="map-editor-grid">
            <div className="map-editor-canvas">
                <div className="map-canvas-bar"><span>{layer==="places"?`${regions.length} locations`:layer==="terrain"?`${appearance.terrain.length} landscape features`:"Appearance preview"}</span><span className={placeDirty||mapDirty?"map-draft-badge":""}>{placeDirty||mapDirty?"DRAFT · NOT SAVED":"Saved world"}</span></div>
                <WorldMap regions={regions} selected={layer==="places"?draft?.id:null} onSelect={id=>layer==="places"&&select(id)} appearance={terrainPreview} editor={{layer,placing,terrainSelected:terrainId,onPick:pick,onMove:move,onNudge:nudge,onPlace:p=>{patchPlace(p);setPlacing(false);}}}/>
                <p className="map-canvas-hint"><MousePointer2 size={15}/>{placing?"Click or tap anywhere on the map to place this location.":layer==="places"?"Drag a location to move it, or select it to edit. Arrow keys move 1%; Shift + arrow moves 5%.":layer==="terrain"?"Drag the round handles to move features or river bends. Fine-tune their size in the panel.":"Colours, title and compass appear on the player map after saving."}</p>
                <div className="map-editor-note"><Route size={18}/><p><strong>The roads are playable.</strong> Dotted lines are travel routes; arrows mark one-way paths. Landscape shapes are decorative. New journeys use saved routes and times; journeys already underway keep their original duration.</p></div>
            </div>
            <fieldset disabled={busy} className="map-editor-panel" role="tabpanel" id="map-layer-panel" aria-labelledby={`map-layer-${layer}`}>
                {layer==="places"&&<>
                    <div className="map-panel-title"><h3>Locations</h3><button onClick={newPlace} disabled={busy}><Plus size={15}/> New place</button></div>
                    <label>Select location<select aria-label="Select location" value={draft?.id||""} onChange={e=>select(e.target.value)}><option value="" disabled>Choose a place…</option>{regions.map(r=><option key={r.id} value={r.id}>{r.name}{r.active===false?" (hidden)":""}</option>)}</select></label>
                    {!draft?<div className="map-editor-empty"><MapPin size={28}/><h3>A world of your making</h3><p>Select a marker or create a place. Its coordinates, description and outgoing routes are yours to edit.</p></div>:<>
                        <label>Location name<input value={draft.name} maxLength={120} onChange={e=>patchPlace({name:e.target.value})}/></label>
                        <label>Description<textarea rows={3} value={draft.description||""} onChange={e=>patchPlace({description:e.target.value})}/></label>
                        <label>Map icon<select aria-label="Map icon" value={draft.biome||"village"} onChange={e=>patchPlace({biome:e.target.value})}>{[...new Set(["village","forest","forge","fields","harbour","keep","marsh",draft.biome].filter(Boolean))].map(k=><option key={k} value={k}>{k}</option>)}</select></label>
                        <div className="map-field-pair"><NumberField label="Position X (%)" value={draft.x} onChange={x=>patchPlace({x})}/><NumberField label="Position Y (%)" value={draft.y} onChange={y=>patchPlace({y})}/></div>
                        <button className={placing?"map-button-active":""} onClick={()=>setPlacing(!placing)}><MousePointer2 size={15}/>{placing?"Cancel placement":"Place on map"}</button>
                        <label className="map-check"><input type="checkbox" checked={draft.active!==false} onChange={e=>patchPlace({active:e.target.checked})}/> Visible and open for travel</label>
                        {draft.active===false&&<p className="map-field-help">Hidden from players. Existing references are kept. Characters here move to an available location on their next world refresh.</p>}
                        <div className="map-panel-title map-routes-heading"><h3>Outgoing routes</h3><button disabled={!regions.some(r=>r.id!==draft.id&&!(draft.connections||[]).some(e=>e.to===r.id))} onClick={()=>{const dest=regions.find(r=>r.id!==draft.id&&!(draft.connections||[]).some(e=>e.to===r.id));patchPlace({connections:[...(draft.connections||[]),{to:dest.id,minutes:60}]});}}><Plus size={14}/> Route</button></div>
                        <p className="map-field-help">Times use game minutes. Add the return route at the other location for two-way travel.</p>
                        {(draft.connections||[]).map((route,index)=><div className="map-route" key={index}><div className="map-route-fields"><label>Destination {index+1}<select aria-label={`Destination ${index+1}`} value={route.to} onChange={e=>routeChange(index,{to:e.target.value})}>{!regions.some(r=>r.id===route.to)&&<option value={route.to}>{route.to} (missing)</option>}{regions.filter(r=>r.id!==draft.id).map(r=><option key={r.id} value={r.id}>{r.name}{r.active===false?" (hidden)":""}</option>)}</select></label><NumberField label="Game minutes" value={route.minutes} max={10080} onChange={minutes=>routeChange(index,{minutes})}/><button className="map-icon-button" aria-label={`Remove route ${index+1}`} onClick={()=>patchPlace({connections:draft.connections.filter((_,i)=>i!==index)})}><Trash2 size={16}/></button></div><p className="map-field-help">{Number(route.minutes)===0?"Instant travel":`${Math.round(Number(route.minutes)/saved.time_scale*60)} real seconds at the current world speed`}</p></div>)}
                        {!(draft.connections||[]).length&&<p className="map-field-help">No outgoing routes yet. Players will need a route to leave this place.</p>}
                        {saved.regions.some(r=>(r.connections||[]).some(e=>e.to===draft.id))&&<details className="map-incoming"><summary>Incoming routes</summary>{saved.regions.filter(r=>(r.connections||[]).some(e=>e.to===draft.id)).map(r=><button key={r.id} onClick={()=>select(r.id)}>{r.name} → {draft.name}</button>)}</details>}
                        <div className="map-save-row"><button className="map-save" disabled={busy||!placeDirty} onClick={()=>savePlace()}><Save size={16}/> Save location</button><button disabled={busy||!placeDirty} onClick={()=>{setDraft(original?clone(original):null);setIsNew(false);setPlacing(false);}}>Discard</button></div>
                        <button className="map-json" onClick={()=>setModal({kind:"place",value:clone(draft)})}><Code size={15}/> Advanced location JSON</button><p className="map-field-help map-id">Stable ID: {draft.id}</p>
                    </>}
                </>}
                {layer==="terrain"&&<>
                    <div className="map-panel-title"><h3>Landscape</h3><span className="map-field-help">No coding needed</span></div>
                    <div className="map-terrain-add">{Object.entries(TERRAIN).map(([kind,label])=><button key={kind} disabled={appearance.terrain.length>=200} onClick={()=>addTerrain(kind)}><Plus size={14}/>{label}</button>)}</div>
                    <label>Select feature<select aria-label="Select feature" value={terrainId} onChange={e=>setTerrainId(e.target.value)}><option value="">Choose a feature…</option>{appearance.terrain.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select></label>
                    {feature?<>
                        <label>Feature name<input maxLength={120} value={feature.name} onChange={e=>patchTerrain(feature.id,{name:e.target.value})}/></label>
                        <NumberField label={feature.kind==="river"?"River width (%)":"Width (%)"} value={feature.width} max={feature.kind==="river"?30:100} onChange={width=>patchTerrain(feature.id,{width})}/>
                        {feature.kind!=="river"?<><div className="map-field-pair"><NumberField label="Centre X (%)" value={feature.x} onChange={x=>patchTerrain(feature.id,{x})}/><NumberField label="Centre Y (%)" value={feature.y} onChange={y=>patchTerrain(feature.id,{y})}/></div><NumberField label="Height (%)" value={feature.height} onChange={height=>patchTerrain(feature.id,{height})}/></>:<>
                            <p className="map-field-help">Numbered handles follow the river from its first bend to its last.</p>
                            {feature.points.map((p,i)=><div className="map-bend" key={i}><span>{i+1}</span><NumberField label={`Bend ${i+1} X (%)`} value={p[0]} onChange={x=>patchTerrain(feature.id,{points:feature.points.map((q,j)=>j===i?[x,q[1]]:q)})}/><NumberField label={`Bend ${i+1} Y (%)`} value={p[1]} onChange={y=>patchTerrain(feature.id,{points:feature.points.map((q,j)=>j===i?[q[0],y]:q)})}/><button className="map-icon-button" disabled={feature.points.length<=2} aria-label={`Remove bend ${i+1}`} onClick={()=>patchTerrain(feature.id,{points:feature.points.filter((_,j)=>j!==i)})}><Trash2 size={14}/></button></div>)}
                            <button disabled={feature.points.length>=100} onClick={()=>patchTerrain(feature.id,{points:[...feature.points,[50,50]]})}><Plus size={14}/> Add river bend</button>
                        </>}
                        <p className="map-field-help">Set width to 0 to hide this feature without removing it.</p>
                        <button className="map-danger" onClick={()=>{setAppearance(a=>({...a,terrain:a.terrain.filter(f=>f.id!==feature.id)}));setTerrainId("");}}><Trash2 size={15}/> Remove feature from draft</button>
                    </>:<div className="map-editor-empty"><Trees size={28}/><h3>Give the realm its shape</h3><p>Add forests, mountain ranges, lakes and rivers. An empty landscape is allowed and stays empty.</p></div>}
                </>}
                {layer==="style"&&<>
                    <h3>Map style</h3><label>Map title<input maxLength={120} value={appearance.title} onChange={e=>setAppearance(a=>({...a,title:e.target.value}))}/></label>
                    <div className="map-colours">{[["ground_color","Ground"],["water_color","Water"],["road_color","Routes"],["forest_color","Forest"],["mountain_color","Mountains"]].map(([key,label])=><label key={key}>{label}<span><input type="color" value={appearance[key]} onChange={e=>setAppearance(a=>({...a,[key]:e.target.value}))}/><code>{appearance[key]}</code></span></label>)}</div>
                    <label className="map-check"><input type="checkbox" checked={appearance.show_compass} onChange={e=>setAppearance(a=>({...a,show_compass:e.target.checked}))}/> Show compass</label>
                    <label>Starting location<select aria-label="Starting location" value={start} onChange={e=>setStart(e.target.value)}>{!saved.regions.some(r=>r.id===start&&r.active!==false)&&<option value={start}>{start} (unavailable)</option>}{saved.regions.filter(r=>r.active!==false).map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label><p className="map-field-help">Used for new characters. Existing characters stay where they are. Save a new location before choosing it here.</p>
                </>}
                {layer!=="places"&&<><div className="map-save-row"><button className="map-save" disabled={busy||!mapDirty} onClick={()=>saveMap()}><Save size={16}/> Save map</button><button disabled={busy||!mapDirty} onClick={()=>{setAppearance(clone(saved.appearance));setStart(saved.start_region);setTerrainId("");}}>Discard</button></div><p className="map-field-help">Saves landscape, colours, title and starting location together. Location and route drafts are saved separately.</p><button className="map-json" onClick={()=>setModal({kind:"map",value:clone(appearance)})}><Code size={15}/> Advanced map JSON</button></>}
            </fieldset>
        </div>
        {modal&&createPortal(<JsonModal open title={modal.kind==="place"?"Save location JSON":"Save map appearance JSON"} initial={modal.value} onClose={()=>!busy&&setModal(null)} onSave={value=>{if(!busy)(modal.kind==="place"?savePlace(value):saveMap(value));}}/>,document.body)}
    </section>;
}
