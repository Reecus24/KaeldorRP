// The API reports real seconds remaining. Advance that snapshot with a monotonic
// local clock, rather than comparing server timestamps with the browser's clock.
export function gameTimers(state, elapsedSeconds = 0) {
    const elapsed = Math.max(0, Number(elapsedSeconds) || 0);
    const remaining = (seconds) => Math.max(0, (Number(seconds) || 0) - elapsed);
    const activityRemaining = state?.activity ? remaining(state.activity.remaining_seconds) : 0;
    const total = Number(state?.activity?.total_seconds) || 0;
    const activityProgress = state?.activity && total > 0
        ? Math.max(0, Math.min(1, 1 - activityRemaining / total))
        : 0;
    return {
        activityRemaining,
        activityProgress,
        confinementRemaining: {
            hospital: remaining(state?.confinement?.hospital),
            jail: remaining(state?.confinement?.jail),
        },
    };
}

export function nextStateDeadline(state) {
    const remaining = [state?.activity?.remaining_seconds];
    if (["hospital", "jail"].includes(state?.player?.status)) {
        remaining.push(state?.confinement?.[state.player.status]);
    }
    const active = remaining.filter((seconds) => Number.isFinite(seconds) && seconds > 0);
    return active.length ? Math.min(...active) : null;
}
