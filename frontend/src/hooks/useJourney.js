import { useCallback, useEffect, useRef, useState } from "react";
import { api, errMessage } from "@/lib/api";

export function useJourney() {
    const [data, setData] = useState(null);
    const [error, setError] = useState("");
    const sequence = useRef(0);
    const load = useCallback(async () => {
        const current = ++sequence.current;
        try {
            const response = await api.get("/journey");
            if (current === sequence.current) { setData(response.data); setError(""); }
        } catch (e) { if (current === sequence.current) setError(errMessage(e)); }
    }, []);
    useEffect(() => {
        load();
        const timer = setInterval(load, 15000);
        return () => { clearInterval(timer); sequence.current += 1; };
    }, [load]);
    return { data, error, load };
}
