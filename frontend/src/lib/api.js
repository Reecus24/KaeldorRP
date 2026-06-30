import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;
const TOKEN_KEY = "kaeldor_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

export const api = axios.create({
    baseURL: API,
    withCredentials: true,
});

api.interceptors.request.use((config) => {
    const token = getToken();
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
});

export function formatApiError(detail) {
    if (detail == null) return "Something went wrong. Please try again.";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail))
        return detail
            .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
            .filter(Boolean)
            .join(" ");
    if (detail && typeof detail.msg === "string") return detail.msg;
    return String(detail);
}

export function errMessage(e) {
    return formatApiError(e?.response?.data?.detail) || e?.message || "Request failed";
}
