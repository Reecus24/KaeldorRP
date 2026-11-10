import React from "react";
import { renderToStaticMarkup } from "react-dom/server.node";
import ActivityPanel from "./ActivityPanel";
import ActionCard from "./ActionCard";
import { StatBar } from "./primitives";
import { useGame } from "@/context/GameContext";

jest.mock("@/context/GameContext", () => ({ useGame: jest.fn() }));
jest.mock("react-router-dom", () => ({ Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a> }), { virtual: true });

test("hospital player sees recovery and a timer, never the free/idle prompt", () => {
    useGame.mockReturnValue({ player: { status: "hospital" }, state: { activity: null }, confinementRemaining: { hospital: 90 }, act: jest.fn() });
    const html = renderToStaticMarkup(<ActivityPanel />);
    expect(html).toContain("In Infirmary");
    expect(html).toContain("1m 30s");
    expect(html).toContain('href="/hospital"');
    expect(html).not.toContain("You're free");
    expect(html).not.toContain("activity-panel-idle");
});

test("food actions explain insufficient funds and disable starting", () => {
    useGame.mockReturnValue({ player: { status: "free", cash: 2, bank: 1 }, state: { time_scale: 2 } });
    const html = renderToStaticMarkup(<ActionCard action={{ id: "meal", name: "Meal", money_cost: 10, duration_minutes: 60, available: true }} onStart={jest.fn()} />);
    expect(html).toContain("Requires ¤ 10 in your purse or vault");
    expect(html).toContain("Not enough funds");
    expect(html).toContain("disabled");
    expect(html).toContain("30 min");
    expect(html).toContain("game hours");
});

test("needs bars use owner warning cutoffs and healthy health stays green", () => {
    const safe = renderToStaticMarkup(<StatBar label="Hunger" value={85} invert warningThreshold={90} color="#00FF66" showDirection />);
    const unsafe = renderToStaticMarkup(<StatBar label="Hunger" value={85} invert warningThreshold={80} color="#00FF66" />);
    const healthy = renderToStaticMarkup(<StatBar label="Health" value={100} warningThreshold={35} color="#00FF66" showDirection />);
    expect(safe).toContain("#00FF66");
    expect(safe).toContain("Lower is better");
    expect(unsafe).toContain("#DE8274");
    expect(healthy).toContain("#00FF66");
    expect(healthy).toContain("Higher is better");
});
