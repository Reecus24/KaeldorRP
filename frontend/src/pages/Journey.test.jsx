import React from "react";
import { renderToStaticMarkup } from "react-dom/server.node";
import Journey, { JourneyTeaser, Rewards, Requirements } from "./Journey";
import { useJourney } from "@/hooks/useJourney";
import { BusinessOperations } from "@/components/game/BusinessOperations";

jest.mock("@/hooks/useJourney", () => ({ useJourney: jest.fn() }));
jest.mock("@/context/GameContext", () => ({ useGame: () => ({ refresh: jest.fn() }) }));
jest.mock("react-router-dom", () => ({ Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a> }), { virtual: true });

test("story requirements expose progress and the place to make progress", () => {
    const html = renderToStaticMarkup(<Requirements rows={[{ metric: "actions", target: 2, current: 1, met: false, label: "Prepare a route", href: "/home" }]} />);
    expect(html).toContain("Prepare a route");
    expect(html).toContain('href="/home"');
    const element = document.createElement("div");
    element.innerHTML = html;
    expect(element.textContent).toContain("1 / 2");
    expect(html).toContain("width:50%");
});

test("costs and changes to reputation are distinct from positive rewards", () => {
    const html = renderToStaticMarkup(<Rewards values={{ cash: 25, reputation: -2, skills: { management: 20 }, items: { sandwich: 1 } }} />);
    expect(html).toContain("¤ 25");
    expect(html).toContain("-2 reputation");
    expect(html).toContain("+20 management XP");
    expect(html).toContain("1 × sandwich");
});

test("dashboard exposes the selected milestone and ongoing story", () => {
    useJourney.mockReturnValue({ data: { goals: [{ focused: true, name: "My workshop", milestones: [{ name: "Open doors" }] }], stories: [{ name: "A delivery", completed: false }], city_events: [] } });
    const html = renderToStaticMarkup(<JourneyTeaser />);
    expect(html).toContain("My workshop");
    expect(html).toContain("Next milestone: Open doors");
    expect(html).toContain("Continue: A delivery");
    expect(html).toContain('href="/journey"');
});

test("unavailable choices explain why and cannot be selected", () => {
    useJourney.mockReturnValue({ data: { goals: [], city_events: [], offers: [], stories: [{
        id: "s", name: "Delivery", history: [], completed: false, node: { id: "n", title: "Pick a route", text: "Decide.", choices: [
            { id: "c", label: "Hire a driver", available: false, cost: 25, reasons: ["Need $25 available."], progress: [] }
        ] }
    }] }, load: jest.fn() });
    const html = renderToStaticMarkup(<Journey />);
    expect(html).toContain("Need $25 available.");
    expect(html).toContain('disabled=""');
    expect(html).toContain("Accepted stories have no deadline.");
});

test("business overview distinguishes payout from operating funds and forecasts", () => {
    const html = renderToStaticMarkup(<BusinessOperations business={{ id: "b" }} operations={{ safe_to_collect: 120, reserve: 80, daily_cost: 40, reserve_days: 2, stock_days: 0.5, max_reserve_days: 30, status: "Needs attention", alerts: [{ title: "Review supplies", detail: "Keep stock", tab: "overview" }] }} />);
    expect(html).toContain("Available payout");
    expect(html).toContain("¤ 120");
    expect(html).toContain("¤ 80");
    expect(html).toContain("0.5 game days");
    expect(html).toContain("not guaranteed earnings");
});
