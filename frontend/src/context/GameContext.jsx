import { createContext, useContext, useEffect, useState, useCallback, useRef, useMemo } from "react";
import { toast } from "sonner";
import { api, errMessage } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { gameTimers, nextStateDeadline } from "@/lib/gameTimers";

const GameContext = createContext(null);

export function GameProvider({ children }) {
    const { user } = useAuth();
    const [state, setState] = useState(null); // /game/state response
    const [events, setEvents] = useState([]);
    const [hasCharacter, setHasCharacter] = useState(null); // null=unknown
    const [loading, setLoading] = useState(true);
    const [stateError, setStateError] = useState(null);
    const [tick, setTick] = useState(0); // 1s ticker for smooth timers
    const [notifications, setNotifications] = useState({ items: [], unread_count: 0 });
    const [msgUnread, setMsgUnread] = useState(0);
    const refreshing = useRef(false);
    const nextDeadlineRef = useRef(null);
    const stateReceivedAtRef = useRef(0);
    const stateRequestRef = useRef(0);

    const fetchState = useCallback(async () => {
        const request = ++stateRequestRef.current;
        try {
            const { data } = await api.get("/game/state");
            if (request !== stateRequestRef.current) return;
            const receivedAt = performance.now();
            stateReceivedAtRef.current = receivedAt;
            const deadline = nextStateDeadline(data);
            nextDeadlineRef.current = deadline === null ? null : receivedAt + deadline * 1000;
            setState({ ...data, _clientReceivedAt: receivedAt });
            setStateError(null);
            setHasCharacter(true);
        } catch (e) {
            if (request !== stateRequestRef.current) return;
            if (e?.response?.status === 404) {
                setHasCharacter(false);
                setState(null);
                nextDeadlineRef.current = null;
                setStateError(null);
            } else {
                setStateError("Couldn't refresh your character. Please try again.");
            }
        } finally {
            if (request === stateRequestRef.current) setLoading(false);
        }
    }, []);

    const fetchEvents = useCallback(async () => {
        try {
            const { data } = await api.get("/game/events?limit=80");
            setEvents(data);
        } catch {
            /* ignore */
        }
    }, []);

    const fetchNotifications = useCallback(async () => {
        try {
            const { data } = await api.get("/notifications?limit=30");
            setNotifications(data);
        } catch {
            /* ignore (e.g. no character yet) */
        }
    }, []);

    const fetchMsgUnread = useCallback(async () => {
        try {
            const { data } = await api.get("/messages/unread");
            setMsgUnread(data.count || 0);
        } catch {
            /* ignore */
        }
    }, []);

    const markNotificationsRead = useCallback(async (ids) => {
        try {
            await api.post("/notifications/read", { ids: ids || null });
            await fetchNotifications();
        } catch {
            /* ignore */
        }
    }, [fetchNotifications]);

    const refresh = useCallback(async () => {
        await Promise.all([fetchState(), fetchEvents(), fetchNotifications(), fetchMsgUnread()]);
    }, [fetchState, fetchEvents, fetchNotifications, fetchMsgUnread]);

    // Initial + when user changes
    useEffect(() => {
        stateRequestRef.current += 1;
        setStateError(null);
        if (user && user.id) {
            setLoading(true);
            refresh();
        } else {
            setState(null);
            setEvents([]);
            setHasCharacter(null);
            nextDeadlineRef.current = null;
        }
    }, [user, refresh]);

    // Poll every 5s
    useEffect(() => {
        if (!user || !user.id) return;
        const id = setInterval(() => {
            if (hasCharacter) refresh();
        }, 5000);
        return () => clearInterval(id);
    }, [user, hasCharacter, refresh]);

    // 1s ticker; refresh when an activity finishes or confinement expires.
    useEffect(() => {
        const id = setInterval(() => {
            setTick((t) => t + 1);
            const end = nextDeadlineRef.current;
            if (end !== null) {
                const remaining = (end - performance.now()) / 1000;
                if (remaining <= 0 && !refreshing.current) {
                    refreshing.current = true;
                    nextDeadlineRef.current = null;
                    refresh().finally(() => {
                        refreshing.current = false;
                    });
                }
            }
        }, 1000);
        return () => clearInterval(id);
    }, [refresh]);

    // Run an API mutation, then refresh + toast
    const act = useCallback(
        async (fn, successMsg) => {
            try {
                const res = await fn();
                await refresh();
                if (successMsg) toast.success(successMsg);
                return { ok: true, res };
            } catch (e) {
                toast.error(errMessage(e));
                await refresh();
                return { ok: false, error: errMessage(e) };
            }
        },
        [refresh],
    );

    const createCharacter = useCallback(async (name, background) => {
        await api.post("/character/create", { name, background });
        await refresh();
    }, [refresh]);

    // BROWSER TAB TITLE + FLASH: reflect unread messages in the document title. When the tab is
    // backgrounded and new messages are waiting, alternate the title so the "(N)" badge catches the eye.
    useEffect(() => {
        const BASE = "Kaeldor";
        if (!msgUnread) { document.title = BASE; return; }
        const badge = `(${msgUnread}) ${BASE}`;
        const alt = msgUnread === 1 ? "New message ·" : `${msgUnread} new messages ·`;
        document.title = badge;
        let flip = false;
        let timer = null;
        const startFlash = () => {
            if (timer) return;
            timer = setInterval(() => {
                flip = !flip;
                document.title = flip ? `${alt} ${BASE}` : badge;
            }, 1400);
        };
        const stopFlash = () => { if (timer) { clearInterval(timer); timer = null; } document.title = badge; };
        const onVis = () => { if (document.hidden) startFlash(); else stopFlash(); };
        if (document.hidden) startFlash();
        document.addEventListener("visibilitychange", onVis);
        return () => { document.removeEventListener("visibilitychange", onVis); if (timer) clearInterval(timer); document.title = BASE; };
    }, [msgUnread]);

    const { activityRemaining, activityProgress, confinementRemaining } = gameTimers(
        state, (performance.now() - stateReceivedAtRef.current) / 1000,
    );

    const player = state?.player || null;

    const value = useMemo(
        () => ({
            state,
            player,
            events,
            hasCharacter,
            loading,
            stateError,
            tick,
            refresh,
            act,
            createCharacter,
            activityRemaining,
            activityProgress,
            confinementRemaining,
            notifications,
            unreadCount: notifications.unread_count || 0,
            markNotificationsRead,
            msgUnread,
            fetchMsgUnread,
        }),
        [state, player, events, hasCharacter, loading, stateError, tick, refresh, act, createCharacter,
         activityRemaining, activityProgress, confinementRemaining, notifications, markNotificationsRead, msgUnread, fetchMsgUnread],
    );

    return (
        <GameContext.Provider value={value}>
            {children}
        </GameContext.Provider>
    );
}

export const useGame = () => useContext(GameContext);
