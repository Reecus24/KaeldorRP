import { Castle, Trees, Hammer, Wheat, Anchor, MapPin, Sprout } from "lucide-react";

export const PLACE_ICONS = { village: Castle, forest: Trees, forge: Hammer, fields: Wheat, harbour: Anchor, keep: Castle, marsh: Sprout };

export default function WorldMap({ regions, current, selected, onSelect, visited = [] }) {
    const byId = Object.fromEntries(regions.map(r => [r.id, r]));
    const edges = new Map();
    regions.forEach(r => r.connections.filter(e=>byId[e.to]).forEach(e => edges.set([r.id,e.to].sort().join(":"), [r,byId[e.to]])));
    return <div className="world-atlas" aria-label="Map of the Ashen March">
        <svg viewBox="0 0 1000 650" aria-hidden="true" className="world-atlas-art" preserveAspectRatio="none">
            <defs><pattern id="atlas-grain" width="46" height="46" patternUnits="userSpaceOnUse"><circle cx="7" cy="19" r="1" fill="#d3c28e" opacity=".11" /><path d="M20 40l7-5m9-30l3 6" stroke="#899f79" opacity=".14" /></pattern><radialGradient id="atlas-light"><stop stopColor="#668969" stopOpacity=".18"/><stop offset="1" stopColor="#172a22" stopOpacity="0"/></radialGradient></defs>
            <rect width="1000" height="650" fill="#21372c"/><rect width="1000" height="650" fill="url(#atlas-grain)"/>
            <path d="M625 -30C500 100 790 160 695 325S590 530 804 700" fill="none" stroke="#122c2e" strokeWidth="62"/>
            <path d="M625 -30C500 100 790 160 695 325S590 530 804 700" fill="none" stroke="#466c6a" strokeWidth="40"/>
            <path d="M625 -30C500 100 790 160 695 325S590 530 804 700" fill="none" stroke="#79a39a" strokeWidth="2" opacity=".45"/>
            <ellipse cx="360" cy="320" rx="500" ry="330" fill="url(#atlas-light)"/>
            {Array.from({ length: 25 }, (_, i) => <g key={i} transform={`translate(${45 + (i * 47) % 310},${45 + (i * 53) % 270})`} opacity=".35"><path d="M0 30L12 2l12 28h-8v10H9V30Z" fill="#10251c" stroke="#759477" strokeWidth="1"/></g>)}
            {[420, 478, 532, 590, 660].map((x, i) => <path key={x} d={`M${x} 145l38-${58 + i * 6} 48 ${58 + i * 6}m-66-20l20-20 17 19`} fill="#314333" stroke="#91a083" opacity=".35"/>)}
            {[...edges.entries()].map(([key,[a,b]]) => <path key={key} d={`M${a.x*10} ${a.y*6.5}L${b.x*10} ${b.y*6.5}`} stroke="#cab784" strokeWidth="2" strokeDasharray="5 7" opacity=".55"/>)}
            <text x="350" y="610" fill="#a3ad8e" fontSize="18" fontFamily="Georgia" letterSpacing="6" opacity=".6">THE ASHEN MARCH</text>
            <g transform="translate(925 565)" stroke="#b6ac7d" opacity=".6"><path d="M0-32V32M-23 0H23M0-32l-6 17 6-3 6 3Z" fill="#b6ac7d"/><text x="-5" y="-42" fill="#cab784" stroke="none" fontFamily="Georgia" fontSize="14">N</text></g>
        </svg>
        {regions.map(r => { const Icon = PLACE_ICONS[r.biome] || MapPin; return <button key={r.id} className={`atlas-place ${r.id === current ? "is-current" : ""} ${r.id === selected ? "is-selected" : ""}`} style={{ left: `${r.x}%`, top: `${r.y}%` }} onClick={() => onSelect(r.id)} aria-label={`${r.name}${r.id === current ? ", your location" : ""}`} aria-pressed={r.id === selected} data-testid={`map-${r.id}`}><span className="atlas-marker"><Icon size={19}/></span><span className="atlas-label">{r.name}</span>{r.id === current && <span className="atlas-here">YOU ARE HERE</span>}{visited.includes(r.id) && r.id !== current && <span className="sr-only">Visited</span>}</button>; })}
    </div>;
}
