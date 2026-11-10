export function money(n) {
    const v = Math.round(Number(n || 0));
    const neg = v < 0;
    const s = Math.abs(v).toLocaleString("en-US");
    return `${neg ? "-" : ""}$${s}`;
}

// precise money with cents — for per-unit prices/costs/margins
export function money2(n) {
    const v = Number(n || 0);
    const neg = v < 0;
    const s = Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
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

// Real-world wait time for an activity, given the current time_scale.
// real_minutes = game_minutes / time_scale (time_scale = game min per real min).
export function realDurationLabel(gameMinutes, timeScale = 1) {
    const realMin = gameMinutes / (timeScale || 1);
    if (realMin >= 1440) return `${(realMin / 1440).toFixed(realMin % 1440 ? 1 : 0)}d`;
    if (realMin >= 60) return `${(realMin / 60).toFixed(realMin % 60 ? 1 : 0)}h`;
    if (realMin >= 1) return `${Math.round(realMin)} min`;
    return `${Math.round(realMin * 60)} sec`;
}

// Describe slower, real-time and faster world clocks without rounding away the scale.
export function timeMode(timeScale = 1) {
    const scale = Number(timeScale);
    if (!Number.isFinite(scale) || scale <= 0) return { realtime: false, label: "CLOCK UNAVAILABLE", tone: "default" };
    if (scale === 1) return { realtime: true, label: "REAL-TIME", tone: "green" };
    const display = scale.toLocaleString("en-US", { maximumSignificantDigits: 8 });
    return { realtime: false, label: `${scale < 1 ? "SLOW" : "FAST"} ×${display}`, tone: scale < 1 ? "cyan" : "yellow" };
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
    energy: { label: "Energy", invert: false, color: "#00F3FF", warningKey: "low_energy_threshold", warningDefault: 15 },
    fatigue: { label: "Fatigue", invert: true, color: "#FFC300", warningKey: "fatigue_damage_threshold", warningDefault: 80 },
    hunger: { label: "Hunger", invert: true, color: "#FF8A00", warningKey: "hunger_damage_threshold", warningDefault: 80 },
    mood: { label: "Mood", invert: false, color: "#00FF66", warningKey: "mood_warning_threshold", warningDefault: 25 },
    stress: { label: "Stress", invert: true, color: "#B026FF", warningKey: "stress_damage_threshold", warningDefault: 80 },
    health: { label: "Health", invert: false, color: "#00FF66", warningKey: "health_warning_threshold", warningDefault: 35 },
};

export function needWarningThreshold(key, rules = {}) {
    const meta = NEED_META[key];
    return rules?.[meta?.warningKey] ?? meta?.warningDefault;
}

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

// ---------- Relationships ----------
export const REL_STATUS = {
    close: { label: "Close", tone: "green" },
    romantic: { label: "Romantic", tone: "purple" },
    active: { label: "Active", tone: "cyan" },
    distant: { label: "Distant", tone: "yellow" },
    angry: { label: "Angry", tone: "red" },
    blocked: { label: "Blocked", tone: "default" },
    ex_partner: { label: "Ex-Partner", tone: "red" },
};

export function scoreColor(s) {
    if (s >= 60) return "#00FF66";
    if (s >= 20) return "#00F3FF";
    if (s >= -20) return "#FFC300";
    return "#FF0055";
}

// Compact "time since" label from seconds.
export function relTime(sec) {
    const s = Math.max(0, Math.floor(sec || 0));
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
}

// ---------- World clock ----------
const GAME_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Compute the current in-game Date from world anchors + time_scale (client-side ticking).
export function computeGameTime(state) {
    const ts = state?.time_scale || 1;
    if (state?.game_time && Number.isFinite(state?._clientReceivedAt)) {
        const snapshot = new Date(state.game_time).getTime();
        if (Number.isFinite(snapshot)) {
            return new Date(snapshot + Math.max(0, performance.now() - state._clientReceivedAt) * ts);
        }
    }
    const wr = state?.world_start_real ? new Date(state.world_start_real).getTime() : null;
    const wg = state?.world_start_game ? new Date(state.world_start_game).getTime() : null;
    if (!wr || !wg) return null;
    return new Date(wg + (Date.now() - wr) * ts);
}

export function fmtGameClock(d, state) {
    if (!d || isNaN(d.getTime())) return { day: "—", time: "--:--", date: "" };
    // Day index is relative to the world's game-start anchor (1:1 real-time clock),
    // so it always starts at Day 1 and stays positive.
    const baseMs = state?.world_start_game ? new Date(state.world_start_game).getTime() : d.getTime();
    const base = new Date(baseMs);
    const baseDayUTC = Date.UTC(base.getUTCFullYear(), base.getUTCMonth(), base.getUTCDate());
    const dayIndex = Math.floor((d.getTime() - baseDayUTC) / 86400000) + 1;
    const hh = String(d.getUTCHours()).padStart(2, "0");
    const mm = String(d.getUTCMinutes()).padStart(2, "0");
    return { day: `Day ${dayIndex}`, time: `${hh}:${mm}`, date: `${GAME_MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}` };
}

// ---------- Scheduled working hours ----------
export const SHIFT_PRESETS = {
    early: { label: "Early Shift", start: 8, end: 16 },
    late: { label: "Late Shift", start: 14, end: 22 },
    night: { label: "Night Shift", start: 22, end: 6 },
    morning: { label: "Part-Time Morning", start: 8, end: 12 },
    evening: { label: "Part-Time Evening", start: 18, end: 22 },
};

export function scheduleLabel(sch) {
    if (!sch) return "No schedule";
    const pad = (n) => String(n).padStart(2, "0");
    return `${sch.label || "Shift"} · ${pad(sch.start)}:00–${pad(sch.end)}:00`;
}

// ---------- Job shift windows (Universal Shift & Risk Engine) ----------
// min_hour > max_hour = overnight window that wraps past midnight (e.g. 21 -> 3).
export function shiftWindowOpen(win, hour) {
    if (!win) return true;
    const lo = Number(win.min_hour ?? 0), hi = Number(win.max_hour ?? 24);
    if (lo === hi) return true;
    if (lo < hi) return hour >= lo && hour < hi;
    return hour >= lo || hour < hi;
}

export function fmtWindow(win) {
    if (!win) return "Any time";
    const pad = (n) => String(n).padStart(2, "0");
    const lo = Number(win.min_hour ?? 0), hi = Number(win.max_hour ?? 24);
    if (lo === 0 && hi >= 24) return "Any time";
    return `${pad(lo)}:00–${pad(hi)}:00`;
}

// ---------- Shift registration (fixed start times; sign up before it begins) ----------
export function fmtShiftClock(s) {
    const pad = (n) => String(n).padStart(2, "0");
    const start = Number(s?.start_hour ?? (s?.start_window?.min_hour ?? 8));
    const end = (start + Number(s?.duration_hours ?? 0)) % 24;
    return `${pad(start)}:00–${pad(end)}:00`;
}

// The next real Date at which the game clock reaches `startHour`. `now` is the current game Date (UTC).
export function nextShiftStart(state, startHour) {
    const g = computeGameTime(state);
    if (!g) return null;
    const ts = state?.time_scale || 1;
    const startGame = new Date(Date.UTC(g.getUTCFullYear(), g.getUTCMonth(), g.getUTCDate(), startHour, 0, 0));
    if (startGame.getTime() <= g.getTime()) startGame.setUTCDate(startGame.getUTCDate() + 1);
    // convert game -> real: real_now + (startGame - gameNow)/ts
    const deltaGameMs = startGame.getTime() - g.getTime();
    return new Date(Date.now() + deltaGameMs / ts);
}

// ---------- Social interaction rewards (transparency) ----------
const REWARD_META = {
    relationship_score: { label: "Relationship", pos: true },
    trust: { label: "Trust", pos: true },
    respect: { label: "Respect", pos: true },
    attraction: { label: "Attraction", pos: true },
    p_mood: { label: "Your Mood", pos: true },
    p_stress: { label: "Stress", pos: false },
    p_reputation: { label: "Reputation", pos: true },
    p_social_status: { label: "Social Status", pos: true },
    p_suspicion: { label: "Suspicion", pos: false },
    c_mood: { label: "Their Mood", pos: true },
};

export function actionRewards(a) {
    const eff = a?.on_success || {};
    const out = [];
    for (const [k, v] of Object.entries(eff)) {
        const meta = REWARD_META[k];
        if (!meta || !v) continue;
        const sign = v > 0 ? "+" : "";
        // green when it helps the player (gains, or a drop in a "bad" stat)
        const good = meta.pos ? v > 0 : v < 0;
        out.push({ label: `${sign}${v} ${meta.label}`, tone: good ? "green" : "red" });
    }
    return out;
}

// ---------- Tooltip / explainer copy ----------
export const STAT_INFO = {
    energy: "Energy fuels activities. It drops as you stay awake and work; sleep and rest restore it.",
    fatigue: "Fatigue builds the longer you're active. High fatigue lowers your effectiveness — sleep to reduce it.",
    hunger: "Hunger rises over time. Eating lowers it; starving harms your health and mood.",
    mood: "Mood reflects how you feel. Good housing, rest and relationships lift it; stress and neglect lower it.",
    stress: "Stress rises from work and crime. High stress damages health and mood — relax, sleep or socialize.",
    health: "Health is your overall condition. It falls from neglect, hunger and stress. At zero you collapse and go to hospital.",
    reputation: "Reputation is your public standing — it affects job offers, wages and your business reputation.",
    legal_reputation: "Legal Standing reflects your record. Crime lowers it; a low value blocks jobs and credit.",
    criminal_suspicion: "Criminal Suspicion is how closely the police watch you. Higher suspicion raises your chance of getting caught.",
    social_status: "Social Status is your standing in society, raised by education, wealth and relationships.",
};

export const XP_INFO = "Experience (XP) accumulates from actions, work and study. Fill the bar to reach the next Level, which unlocks better opportunities.";
export const SKILL_INFO = "Skills grow as you work, study and act. Higher skill levels unlock jobs and businesses and improve your outcomes and pay.";
