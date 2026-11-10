import {mapPoint,mapEdges,riverPath} from "./mapGeometry";

test("pointer coordinates are responsive percentages and stop at map edges",()=>{
    expect(mapPoint(300,150,{left:100,top:50,width:400,height:200})).toEqual({x:50,y:50});
    expect(mapPoint(0,999,{left:100,top:50,width:400,height:200})).toEqual({x:0,y:100});
});
test("map shows direction until a return route exists and skips missing destinations",()=>{
    const regions=[{id:"a",connections:[{to:"b",minutes:0},{to:"deleted",minutes:2}]},{id:"b",connections:[]}];
    expect(mapEdges(regions)).toHaveLength(1);
    expect(mapEdges(regions)[0]).toMatchObject({twoWay:false,minutes:0});
    regions[1].connections.push({to:"a",minutes:5});
    expect(mapEdges(regions)).toHaveLength(1);
    expect(mapEdges(regions)[0].twoWay).toBe(true);
});
test("a river passes through its editable start and end points",()=>{
    expect(riverPath([[0,0],[100,100]])).toMatch(/^M0 0C.* 1000 650$/);
    expect(riverPath([])).toBe("");
});
