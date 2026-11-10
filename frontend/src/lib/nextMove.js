export function nextMove(player, activity, needs = {}) {
    if (player.status === "hospital") return {
        title: "Focus on recovery", detail: "Your infirmary countdown is running. Check your recovery or choose paid treatment to leave early.",
        to: "/hospital", label: "View recovery", tone: "red",
    };
    if (player.status === "jail") return {
        title: "Plan your release", detail: "Your sentence is running. View the remaining time and your bail options.",
        to: "/jail", label: "View sentence", tone: "red",
    };
    if (activity || player.on_shift) return {
        title: activity ? activity.name : "Your shift is underway", detail: "The timer continues while you're away. You can browse your inventory, messages and finances.",
        to: "/inventory", label: "Open inventory", tone: "cyan",
    };
    if (player.hunger > (needs.hunger_damage_threshold ?? 80)) return {
        title: "Get something to eat", detail: `Hunger is ${Math.round(player.hunger)}/100 — a lower value is better. Food helps protect your health and performance.`,
        to: "/home#food", label: "Find food", tone: "yellow",
    };
    if (player.health < (needs.health_warning_threshold ?? 35)) return {
        title: "Take care of your health", detail: "Your health is low. Check treatment options and keep food, rest and stress under control.",
        to: "/hospital", label: "Check treatment", tone: "red",
    };
    if (player.energy < (needs.low_energy_threshold ?? 15) || player.fatigue > (needs.fatigue_damage_threshold ?? 80)) return {
        title: "Make time to rest", detail: "Low energy and high fatigue make work less effective. Sleep or rest before your next shift.",
        to: "/home#rest", label: "Rest & recover", tone: "yellow",
    };
    if (player.stress > (needs.stress_damage_threshold ?? 80)) return {
        title: "Take the pressure off", detail: "High stress affects your health. Make time for leisure, rest or social contact.",
        to: "/home#leisure", label: "Find a break", tone: "yellow",
    };
    return player.job ? {
        title: "Choose your next shift", detail: "Check your schedule, build your skills or prepare for your next promotion.",
        to: "/current-job", label: "Open current job", tone: "cyan",
    } : {
        title: "Find your place in the realm", detail: "Browse job openings to build a steady income, or explore Hearth & Rest for a small task.",
        to: "/jobs", label: "Explore jobs", tone: "cyan",
    };
}
