export function money(n) {
    const v = Math.round(Number(n || 0));
    const neg = v < 0;
    const s = Math.abs(v).toLocaleString("en-US");
    return `${neg ? "-" : ""}$${s}`;
}

export function fmtDuration(totalSeconds) {
    let s = Math.max(0, Math.floor(totalSeconds || 0));
    const d = Math.floor(s / 86400);
    s -= d * 86400;
    const h = Math.floor(s / 3600);
    s -= h * 3600;
    const m = Math.floor(s / 60);
    s -= m * 60;
    const pad = (x) => String(x).padStart(2, "0");
    if (d > 0) return `${d}d ${pad(h)}h ${pad(m)}m`;
    if (h > 0) return `${h}h ${pad(m)}m ${pad(s)}s`;
    return `${m}m ${pad(s)}s`;
}

export function gameDuration(gameMinutes) {
    const m = gameMinutes;
    if (m >= 1440) return `${(m / 1440).toFixed(m % 1440 ? 1 : 0)} game days`;
    if (m >= 60) return `${(m / 60).toFixed(m % 60 ? 1 : 0)} game hours`;
    return `${m} game min`;
}

// risk level -> color classes
export const RISK_COLORS = {
    none: "text-neon-green border-neon-green/40",
    low: "text-neon-green border-neon-green/40",
    medium: "text-neon-yellow border-neon-yellow/40",
    high: "text-neon-red border-neon-red/40",
};

// stat metadata: invert=true means higher value is BAD
export const NEED_META = {
    energy: { label: "Energy", invert: false, color: "#00F3FF" },
    fatigue: { label: "Fatigue", invert: true, color: "#FFC300" },
    hunger: { label: "Hunger", invert: true, color: "#FF8A00" },
    hygiene: { label: "Hygiene", invert: false, color: "#22D3EE" },
    mood: { label: "Mood", invert: false, color: "#00FF66" },
    stress: { label: "Stress", invert: true, color: "#FF0055" },
    health: { label: "Health", invert: false, color: "#FF3B6B" },
};

export const SKILL_LABELS = {
    sales: "Sales",
    cooking: "Cooking",
    management: "Management",
    driving: "Driving",
    charisma: "Charisma",
    fitness: "Fitness",
    technology: "Technology",
    crafting: "Crafting",
    creativity: "Creativity",
    finance: "Finance",
    studying: "Studying",
    street_smarts: "Street Smarts",
};

export function statusLabel(status) {
    const map = {
        free: "Free",
        busy: "Busy",
        working: "Working",
        studying: "Studying",
        sleeping: "Sleeping",
        jail: "In Jail",
        hospital: "In Hospital",
    };
    return map[status] || status;
}

export function statusColor(status) {
    if (status === "jail" || status === "hospital") return "text-neon-red border-neon-red/50";
    if (status === "free") return "text-neon-green border-neon-green/50";
    return "text-neon-cyan border-neon-cyan/50";
}
