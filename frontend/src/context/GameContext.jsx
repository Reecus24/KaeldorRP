import { createContext, useContext, useEffect, useState, useCallback, useRef } from "react";
import { toast } from "sonner";
import { api, errMessage } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const GameContext = createContext(null);

export function GameProvider({ children }) {
    const { user } = useAuth();
    const [state, setState] = useState(null); // /game/state response
    const [events, setEvents] = useState([]);
    const [hasCharacter, setHasCharacter] = useState(null); // null=unknown
    const [loading, setLoading] = useState(true);
    const [tick, setTick] = useState(0); // 1s ticker for smooth timers
    const [notifications, setNotifications] = useState({ items: [], unread_count: 0 });
    const [msgUnread, setMsgUnread] = useState(0);
    const refreshing = useRef(false);
    const lastEndRef = useRef(null);

    const fetchState = useCallback(async () => {
        try {
            const { data } = await api.get("/game/state");
            setState(data);
            setHasCharacter(true);
            lastEndRef.current = data.activity ? data.activity.ends_at : null;
        } catch (e) {
            if (e?.response?.status === 404) {
                setHasCharacter(false);
                setState(null);
            }
        } finally {
            setLoading(false);
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
        if (user && user.id) {
            setLoading(true);
            refresh();
        } else {
            setState(null);
            setEvents([]);
            setHasCharacter(null);
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

    // 1s ticker; when activity end passes, force a refresh once
    useEffect(() => {
        const id = setInterval(() => {
            setTick((t) => t + 1);
            const end = lastEndRef.current;
            if (end) {
                const remaining = (new Date(end).getTime() - Date.now()) / 1000;
                if (remaining <= 0 && !refreshing.current) {
                    refreshing.current = true;
                    lastEndRef.current = null;
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

    const createCharacter = async (name, background) => {
        await api.post("/character/create", { name, background });
        await refresh();
    };

    // computed activity remaining (uses local ticker)
    let activityRemaining = 0;
    let activityProgress = 0;
    if (state?.activity) {
        const end = new Date(state.activity.ends_at).getTime();
        const total = state.activity.total_seconds;
        activityRemaining = Math.max(0, (end - Date.now()) / 1000);
        activityProgress = Math.min(1, (total - activityRemaining) / total);
    }

    const player = state?.player || null;

    return (
        <GameContext.Provider
            value={{
                state,
                player,
                events,
                hasCharacter,
                loading,
                tick,
                refresh,
                act,
                createCharacter,
                activityRemaining,
                activityProgress,
                notifications,
                unreadCount: notifications.unread_count || 0,
                markNotificationsRead,
                msgUnread,
                fetchMsgUnread,
            }}
        >
            {children}
        </GameContext.Provider>
    );
}

export const useGame = () => useContext(GameContext);
