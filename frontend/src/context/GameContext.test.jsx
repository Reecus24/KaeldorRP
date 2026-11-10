import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { GameProvider, useGame } from "./GameContext";
import { api } from "@/lib/api";

jest.mock("@/context/AuthContext", () => {
    const user = { id: "test-player" };
    return { useAuth: () => ({ user }) };
});
jest.mock("@/lib/api", () => ({ api: { get: jest.fn() }, errMessage: () => "Request failed" }));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

test("hospital expiry refreshes state without waiting for the five-second poll", async () => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    jest.useFakeTimers("modern");
    let stateCalls = 0;
    api.get.mockImplementation(async (url) => {
        if (url === "/game/state") {
            stateCalls += 1;
            return { data: stateCalls === 1
                ? { player: { status: "hospital" }, activity: null, confinement: { hospital: 2 } }
                : { player: { status: "free" }, activity: null, confinement: {} } };
        }
        return { data: { items: [], unread_count: 0, count: 0 } };
    });
    const container = document.createElement("div");
    const root = createRoot(container);
    function Status() {
        const game = useGame();
        return <span>{game.player?.status || "loading"}</span>;
    }
    try {
        await act(async () => { root.render(<GameProvider><Status /></GameProvider>); });
        expect(container.textContent).toBe("hospital");
        await act(async () => { jest.advanceTimersByTime(2000); });
        expect(stateCalls).toBe(2);
        expect(container.textContent).toBe("free");
    } finally {
        await act(async () => { root.unmount(); });
        jest.useRealTimers();
        delete global.IS_REACT_ACT_ENVIRONMENT;
    }
});
