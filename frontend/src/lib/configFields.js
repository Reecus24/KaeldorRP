export function editableConfigFields(value, path = []) {
    // Persisted world anchors and migration markers are internal bookkeeping,
    // not gameplay controls. All other future numeric/boolean keys remain visible.
    if (path.length === 1 && (["id", "_id", "time_synced_de"].includes(path[0]) || path[0].startsWith("world_start_"))) return [];
    if (typeof value === "number" || typeof value === "boolean") return [{ path, value }];
    if (!value || typeof value !== "object" || Array.isArray(value)) return [];
    return Object.entries(value).flatMap(([key, child]) => editableConfigFields(child, [...path, key]));
}

export function configValue(value, path) {
    return path.reduce((current, key) => current?.[key], value);
}

export function setConfigValue(value, [key, ...path], next) {
    return { ...value, [key]: path.length ? setConfigValue(value?.[key], path, next) : next };
}

export function normalizeConfigPatch(patch, schema) {
    return Object.fromEntries(Object.entries(patch).map(([key, value]) => {
        const original = schema?.[key];
        if (typeof original === "number") {
            if (value === "" || !Number.isFinite(Number(value))) throw new Error(`${key.replace(/_/g, " ")} must be a finite number`);
            return [key, Number(value)];
        }
        if (value && typeof value === "object" && !Array.isArray(value)) return [key, normalizeConfigPatch(value, original)];
        return [key, value];
    }));
}
