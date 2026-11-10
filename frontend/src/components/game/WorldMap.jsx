import { useId, useRef } from "react";
import { Castle, Trees, Hammer, Wheat, Anchor, MapPin, Sprout, Move } from "lucide-react";
import { mapPoint, riverPath, mapEdges } from "@/lib/mapGeometry";

export const PLACE_ICONS = { village: Castle, forest: Trees, forge: Hammer, fields: Wheat, harbour: Anchor, keep: Castle, marsh: Sprout };

export default function WorldMap({ regions, current, selected, onSelect, visited = [], appearance = {}, editor }) {
    const root=useRef(null),drag=useRef(null),prefix=useId().replace(/:/g,"");
    const colors={ground_color:"#21372c",water_color:"#466c6a",road_color:"#cab784",forest_color:"#759477",mountain_color:"#91a083",...appearance};
    const features=Array.isArray(appearance.terrain)?appearance.terrain:[];
    const move=(event)=>{const held=drag.current;if(!held||Math.hypot(event.clientX-held.startX,event.clientY-held.startY)<3)return;const point=mapPoint(event.clientX-held.offsetX,event.clientY-held.offsetY,root.current.getBoundingClientRect());editor?.onMove(held.target,point);};
    const handlers=(target)=>editor?{
        onPointerDown:event=>{if(event.button!==0)return;if(editor.onPick(target)===false)return;event.stopPropagation();const rect=root.current.getBoundingClientRect(),feature=target.kind==="place"?regions.find(r=>r.id===target.id):features.find(f=>f.id===target.id),point=feature.kind==="river"?{x:feature.points[target.index][0],y:feature.points[target.index][1]}:feature;drag.current={target,startX:event.clientX,startY:event.clientY,offsetX:event.clientX-rect.left-point.x/100*rect.width,offsetY:event.clientY-rect.top-point.y/100*rect.height};event.currentTarget.setPointerCapture(event.pointerId);},
        onPointerMove:move,
        onPointerUp:event=>{if(!drag.current)return;move(event);drag.current=null;if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);},
        onPointerCancel:()=>{drag.current=null;},
        onLostPointerCapture:()=>{drag.current=null;},
        onKeyDown:event=>{const keys={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};if(!keys[event.key])return;event.preventDefault();if(editor.onPick(target)===false)return;editor.onNudge(target,keys[event.key].map(v=>v*(event.shiftKey?5:1)));},
        style:{touchAction:"none"},
    }:{};
    return <div ref={root} className={`world-atlas ${editor?"atlas-editing":""} ${editor?.placing?"atlas-placing":""}`} aria-label="World map" data-testid="world-map" onClick={e=>{if(editor?.placing&&!e.target.closest('[data-map-handle]'))editor.onPlace(mapPoint(e.clientX,e.clientY,root.current.getBoundingClientRect()));}}>
        <svg viewBox="0 0 1000 650" aria-hidden="true" className="world-atlas-art" preserveAspectRatio="none">
            <defs><pattern id={`${prefix}-grain`} width="46" height="46" patternUnits="userSpaceOnUse"><circle cx="7" cy="19" r="1" fill="#d3c28e" opacity=".11" /><path d="M20 40l7-5m9-30l3 6" stroke="#899f79" opacity=".14" /></pattern><marker id={`${prefix}-arrow`} viewBox="0 0 10 10" refX="7" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5 0 10" fill="none" stroke={colors.road_color}/></marker></defs>
            <rect width="1000" height="650" fill={colors.ground_color}/><rect width="1000" height="650" fill={`url(#${prefix}-grain)`}/>
            {features.map(f=>{
                if(!f.width || (f.kind!=="river"&&!f.height))return null;
                if(f.kind==="river")return <g key={f.id} data-testid={`terrain-${f.id}`}><path d={riverPath(f.points)} fill="none" stroke="#122c2e" strokeWidth={f.width*10+12}/><path d={riverPath(f.points)} fill="none" stroke={colors.water_color} strokeWidth={f.width*10}/><path d={riverPath(f.points)} fill="none" stroke="#c2d9c9" strokeWidth="1" opacity=".25"/></g>;
                if(f.kind==="lake")return <ellipse key={f.id} data-testid={`terrain-${f.id}`} cx={f.x*10} cy={f.y*6.5} rx={f.width*5} ry={f.height*3.25} fill={colors.water_color} stroke="#122c2e" strokeWidth="6"/>;
                if(f.kind==="forest")return <g key={f.id} data-testid={`terrain-${f.id}`} opacity=".55">{Array.from({length:26},(_,i)=><g key={i} transform={`translate(${f.x*10+((i*37)%97/97-.5)*f.width*10},${f.y*6.5+((i*53)%89/89-.5)*f.height*6.5})`}><path d="M-12 10L0-18 12 10H4V20H-3V10Z" fill="#10251c" stroke={colors.forest_color} strokeWidth="1.4"/></g>)}</g>;
                return <g key={f.id} data-testid={`terrain-${f.id}`} opacity=".5">{[0,1,2,3,4].map(i=><path key={i} d={`M${f.x*10-f.width*5+i*f.width*2} ${f.y*6.5+f.height*3.25}l${f.width*1.1} ${-f.height*6.5} ${f.width*1.2} ${f.height*6.5}m${-f.width*1.8} ${-f.height*1.8}l${f.width*.7} ${-f.height*1.4} ${f.width*.55} ${f.height*1.4}`} fill="#314333" stroke={colors.mountain_color}/>)}</g>;
            })}
            {mapEdges(regions).map(({key,a,b,twoWay}) => <path key={key} d={`M${a.x*10} ${a.y*6.5}L${(a.x+b.x)*5} ${(a.y+b.y)*3.25}L${b.x*10} ${b.y*6.5}`} stroke={colors.road_color} fill="none" strokeWidth="2" strokeDasharray="5 7" opacity={a.active===false||b.active===false?".2":".65"} markerMid={twoWay?undefined:`url(#${prefix}-arrow)`}/>)}
            <text x="500" y="610" textAnchor="middle" fill="#a3ad8e" fontSize="18" fontFamily="Georgia" letterSpacing="6" opacity=".6">{appearance.title}</text>
            {appearance.show_compass && <g transform="translate(925 565)" stroke="#b6ac7d" opacity=".6"><path d="M0-32V32M-23 0H23M0-32l-6 17 6-3 6 3Z" fill="#b6ac7d"/><text x="-5" y="-42" fill="#cab784" stroke="none" fontFamily="Georgia" fontSize="14">N</text></g>}
        </svg>
        {regions.map(r => { const Icon = PLACE_ICONS[r.biome] || MapPin; const events=editor?.layer==="places"?handlers({kind:"place",id:r.id}):{};return <button type="button" key={r.id} {...events} data-map-handle className={`atlas-place ${r.id === current ? "is-current" : ""} ${r.id === selected ? "is-selected" : ""} ${r.active===false?"atlas-inactive":""}`} style={{...events.style,left: `${r.x}%`, top: `${r.y}%`}} onClick={(e) => {e.stopPropagation();onSelect(r.id);}} aria-label={`${r.name}${r.id === current ? ", your location" : ""}`} aria-pressed={r.id === selected} data-testid={`map-${r.id}`}><span className="atlas-marker"><Icon size={19}/></span><span className="atlas-label">{r.name}</span>{r.id === current && <span className="atlas-here">YOU ARE HERE</span>}{visited.includes(r.id) && r.id !== current && <span className="sr-only">Visited</span>}</button>; })}
        {editor?.layer==="terrain"&&features.flatMap(f=>{
            const points=f.kind==="river"?f.points:[[f.x,f.y]];
            return points.map(([x,y],index)=>{const target={kind:"terrain",id:f.id,index};const events=handlers(target);return <button type="button" key={`${f.id}-${index}`} {...events} data-map-handle className={`atlas-terrain-handle ${f.id===editor.terrainSelected?"selected":""}`} style={{...events.style,left:`${x}%`,top:`${y}%`}} onClick={e=>{e.stopPropagation();editor.onPick(target);}} aria-label={`Move ${f.name}${f.kind==="river"?` bend ${index+1}`:""}`} data-testid={`terrain-handle-${f.id}-${index}`}>{f.kind==="river"?index+1:<Move size={14}/>}</button>;});
        })}
    </div>;
}
