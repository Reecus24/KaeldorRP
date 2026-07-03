import { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react";
import { api, setToken, clearToken, getToken } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null); // null = checking, false = logged out, object = logged in
    const [ready, setReady] = useState(false);

    const loadMe = useCallback(async () => {
        if (!getToken()) {
            setUser(false);
            setReady(true);
            return;
        }
        try {
            const { data } = await api.get("/auth/me");
            setUser(data);
        } catch {
            clearToken();
            setUser(false);
        } finally {
            setReady(true);
        }
    }, []);

    useEffect(() => {
        loadMe();
    }, [loadMe]);

    const login = useCallback(async (email, password) => {
        const { data } = await api.post("/auth/login", { email, password });
        setToken(data.token);
        setUser(data.user);
        return data.user;
    }, []);

    const register = useCallback(async (email, password, name) => {
        const { data } = await api.post("/auth/register", { email, password, name });
        setToken(data.token);
        setUser(data.user);
        return data.user;
    }, []);

    const logout = useCallback(async () => {
        try {
            await api.post("/auth/logout");
        } catch {
            /* ignore */
        }
        clearToken();
        setUser(false);
    }, []);

    const value = useMemo(
        () => ({ user, ready, login, register, logout, refreshUser: loadMe }),
        [user, ready, login, register, logout, loadMe],
    );

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
}

export const useAuth = () => useContext(AuthContext);
