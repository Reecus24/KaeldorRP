export function mapPoint(clientX, clientY, rect) {
    const clamp = v => Math.round(Math.max(0, Math.min(100, v)) * 100) / 100;
    return { x: clamp((clientX - rect.left) / Math.max(1, rect.width) * 100), y: clamp((clientY - rect.top) / Math.max(1, rect.height) * 100) };
}

export function riverPath(points) {
    if (!points || points.length < 2) return "";
    const p = points.map(([x,y]) => [x*10,y*6.5]);
    let path = `M${p[0][0]} ${p[0][1]}`;
    for(let i=0;i<p.length-1;i++) {
        const a=p[Math.max(0,i-1)],b=p[i],c=p[i+1],d=p[Math.min(p.length-1,i+2)];
        path += `C${b[0]+(c[0]-a[0])/6} ${b[1]+(c[1]-a[1])/6} ${c[0]-(d[0]-b[0])/6} ${c[1]-(d[1]-b[1])/6} ${c[0]} ${c[1]}`;
    }
    return path;
}

export function mapEdges(regions) {
    const byId=Object.fromEntries(regions.map(r=>[r.id,r])),edges=new Map();
    regions.forEach(a=>(a.connections||[]).filter(e=>byId[e.to]).forEach(e=>{
        const b=byId[e.to],key=[a.id,b.id].sort().join(":");
        if(!edges.has(key)) edges.set(key,{key,a,b,minutes:e.minutes,twoWay:(b.connections||[]).some(r=>r.to===a.id)});
    }));
    return [...edges.values()];
}
