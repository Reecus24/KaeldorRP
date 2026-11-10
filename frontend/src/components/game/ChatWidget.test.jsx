import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ChatWidget from "./ChatWidget";

jest.mock("@/context/GameContext", () => ({ useGame: () => ({ hasCharacter: true, player: { id: "test-chat-player" } }) }));
jest.mock("@/lib/api", () => ({ api: { get: async () => ({ data: { messages: [{ id: "m1", player_id: "other", ts: "2099-01-01T00:00:00Z", name: "Other", message: "Hello" }], online_count: 2 } }) }, errMessage: () => "Request failed" }));

test("compact chat has an accessible unread label and can expand and minimize", async () => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    const container = document.createElement("div");
    const root = createRoot(container);
    localStorage.clear();
    try {
        await act(async () => { root.render(<ChatWidget />); });
        const trigger = container.querySelector('[data-testid="chat-widget-open"]');
        expect(trigger.getAttribute("aria-label")).toContain("1 unread messages");
        expect(trigger.className).toContain("w-12");
        expect(trigger.querySelector('[data-testid="chat-unread-badge"]')).not.toBeNull();
        await act(async () => { trigger.click(); });
        expect(container.querySelector('[aria-label="World chat"]')).not.toBeNull();
        const close = container.querySelector('[aria-label="Minimize world chat"]');
        await act(async () => { close.click(); });
        expect(container.querySelector('[data-testid="chat-widget-open"]')).not.toBeNull();
        expect(container.querySelector('[data-testid="chat-unread-badge"]')).toBeNull();
    } finally {
        await act(async () => { root.unmount(); });
        delete global.IS_REACT_ACT_ENVIRONMENT;
    }
});
