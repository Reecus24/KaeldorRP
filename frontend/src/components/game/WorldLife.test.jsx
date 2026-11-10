import React,{act} from "react";
import {createRoot} from "react-dom/client";
import {EncounterCard,DayAtmosphere} from "./WorldLife";

test("a completed daily choice stays recorded and a shared reward uses the event ID",async()=>{
    global.IS_REACT_ACT_ENVIRONMENT=true;
    const container=document.createElement("div"),root=createRoot(container),mutate=jest.fn();
    const event={id:"shared-day",name:"A village feast",description:"Everyone helps.",choices:[],mine:{choice:"Carry baskets",result:"The tables are ready."},goal:{name:"Feed the village",target:2,progress:2,reward_coins:0,contributors:[{name:"Rowan",amount:1},{name:"Ada",amount:1}],can_claim:true}};
    try{
        await act(async()=>root.render(<EncounterCard event={event} kind="day" mutate={mutate} skills={[]} scale={1}/>));
        expect(container.textContent).toContain("Rowan +1 · Ada +1");
        expect(container.textContent).toContain("The tables are ready.");
        const button=[...container.querySelectorAll("button")].find(b=>b.textContent.includes("Claim your shared reward"));
        await act(async()=>button.click());
        expect(mutate).toHaveBeenCalledWith("/world/life/day/claim",{event_id:"shared-day"},expect.any(String));
        await act(async()=>root.render(<EncounterCard event={{...event,goal:{...event.goal,claimed:true,can_claim:false}}} kind="day" mutate={mutate} skills={[]} scale={1}/>));
        expect(container.querySelector("button")).toBeNull();
    }finally{await act(async()=>root.unmount());delete global.IS_REACT_ACT_ENVIRONMENT;}
});

test("empty weather and phase settings do not restore default atmosphere",async()=>{
    global.IS_REACT_ACT_ENVIRONMENT=true;
    const container=document.createElement("div"),root=createRoot(container);
    try{await act(async()=>root.render(<DayAtmosphere life={{day:2,clock:"00:00",phase:null,weather:null}} region="Owner village"/>));expect(container.textContent).toContain("Owner village");expect(container.textContent).not.toContain("Clear skies");}finally{await act(async()=>root.unmount());delete global.IS_REACT_ACT_ENVIRONMENT;}
});
