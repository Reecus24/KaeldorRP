import { gameTimers, nextStateDeadline } from "./gameTimers.js";
import { computeGameTime, timeMode, needWarningThreshold } from "./helpers.js";

test("confinement and activity use server durations, independent of browser clock", () => {
    const snapshot = {
        player: { status: "hospital", hospital_until: "2000-01-01T00:00:00Z" },
        confinement: { hospital: 60 },
        activity: { ends_at: "2100-01-01T00:00:00Z", total_seconds: 120, remaining_seconds: 90 },
    };
    const timers = gameTimers(snapshot, 15);
    expect(timers.confinementRemaining.hospital).toBe(45);
    expect(timers.activityRemaining).toBe(75);
    expect(timers.activityProgress).toBe(0.375);
    expect(nextStateDeadline(snapshot)).toBe(60);
});

test("hospital discharge schedules a refresh even without an activity", () => {
    expect(nextStateDeadline({ player: { status: "hospital" }, confinement: { hospital: 10 } })).toBe(10);
    expect(nextStateDeadline({ player: { status: "jail" }, confinement: { jail: 25 } })).toBe(25);
    expect(nextStateDeadline({ player: { status: "free" }, confinement: {} })).toBe(null);
});

test("expired timers stay at zero and a new server snapshot replaces the countdown", () => {
    const first = { player: { status: "hospital" }, confinement: { hospital: 10 } };
    expect(gameTimers(first, 25).confinementRemaining.hospital).toBe(0);
    const next = { player: { status: "hospital" }, confinement: { hospital: 80 } };
    expect(gameTimers(next, 0).confinementRemaining.hospital).toBe(80);
    expect(gameTimers({ player: { status: "free" } }, 0).confinementRemaining.hospital).toBe(0);
});

test("empty or completed activities cannot yield invalid progress", () => {
    expect(gameTimers(null).activityProgress).toBe(0);
    expect(gameTimers({ activity: { total_seconds: 0, remaining_seconds: 0 } }).activityProgress).toBe(0);
    expect(gameTimers({ activity: { total_seconds: 60, remaining_seconds: 5 } }, 20).activityProgress).toBe(1);
});

test("world time advances from the server snapshot even if browser wall time is wrong", () => {
    const clock = jest.spyOn(performance, "now").mockReturnValue(16000);
    const wall = jest.spyOn(Date, "now").mockReturnValue(0);
    const state = { game_time: "2026-01-01T12:00:00Z", time_scale: 2, _clientReceivedAt: 1000 };
    expect(computeGameTime(state).toISOString()).toBe("2026-01-01T12:00:30.000Z");
    clock.mockRestore();
    wall.mockRestore();
});

test("slow and fractional world-clock speeds retain their actual scale", () => {
    expect(timeMode(1).realtime).toBe(true);
    expect(timeMode(0.5)).toEqual({ realtime: false, label: "SLOW ×0.5", tone: "cyan" });
    expect(timeMode(1.25).label).toBe("FAST ×1.25");
    expect(timeMode(0.00001).label).toBe("SLOW ×0.00001");
});

test("all needs warning colors use configurable cutoffs, including zero", () => {
    expect(needWarningThreshold("hunger", { hunger_damage_threshold: 90 })).toBe(90);
    expect(needWarningThreshold("energy", { low_energy_threshold: 0 })).toBe(0);
    expect(needWarningThreshold("health", { health_warning_threshold: 45 })).toBe(45);
    expect(needWarningThreshold("mood", { mood_warning_threshold: 10 })).toBe(10);
});
