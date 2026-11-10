import React,{act} from "react";
import {createRoot} from "react-dom/client";
import WorldMap from "./WorldMap";

test("the player atlas renders saved geometry, including an intentionally empty landscape",async()=>{
    global.IS_REACT_ACT_ENVIRONMENT=true;
    const container=document.createElement("div"),root=createRoot(container);
    try{
        const appearance={title:"Owner's realm",ground_color:"#010203",terrain:[{id:"custom",name:"Lake",kind:"lake",x:0,y:100,width:10,height:20}]};
        await act(async()=>root.render(<WorldMap regions={[]} appearance={appearance}/>));
        expect(container.textContent).toContain("Owner's realm");
        expect(container.querySelector('[data-testid="terrain-custom"]').getAttribute("cx")).toBe("0");
        expect(container.querySelector('[data-testid="terrain-custom"]').getAttribute("cy")).toBe("650");
        await act(async()=>root.render(<WorldMap regions={[]} appearance={{...appearance,terrain:[]}}/>));
        expect(container.querySelector('[data-testid^="terrain-"]')).toBeNull();
    }finally{await act(async()=>root.unmount());delete global.IS_REACT_ACT_ENVIRONMENT;}
});
