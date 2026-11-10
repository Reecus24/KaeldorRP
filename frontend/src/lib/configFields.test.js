import { editableConfigFields, configValue, setConfigValue, normalizeConfigPatch } from "./configFields";

test("future numeric and boolean settings automatically become editable without flattening arrays", () => {
    const fields = editableConfigFields({ hospital: { duration_minutes: 360 }, feature: { enabled: false, cost: 0 }, brackets: [[null, 0.1]] });
    expect(fields.map(({ path }) => path.join("."))).toEqual(["hospital.duration_minutes", "feature.enabled", "feature.cost"]);
});

test("owner edits send only changed keys and preserve explicit zero and false", () => {
    const schema = { needs: { enabled: true, decay: 3, untouched: 9 }, tuning: { brackets: [[null, 0.1]] } };
    let patch = setConfigValue({}, ["needs", "decay"], "0");
    patch = setConfigValue(patch, ["needs", "enabled"], false);
    const normalized = normalizeConfigPatch(patch, schema);
    expect(normalized).toEqual({ needs: { decay: 0, enabled: false } });
    expect(configValue(schema, ["needs", "untouched"])).toBe(9);
});

test("invalid numeric edits fail instead of being sent as null", () => {
    const schema = { hospital: { duration_minutes: 360 } };
    expect(() => normalizeConfigPatch({ hospital: { duration_minutes: "" } }, schema)).toThrow();
    expect(() => normalizeConfigPatch({ hospital: { duration_minutes: "Infinity" } }, schema)).toThrow();
});

test("bookkeeping is hidden while future gameplay switches remain editable", () => {
    const fields = editableConfigFields({ id: 1, time_synced_de: true, world_start_real: 123, world_start_game: 456, new_feature: { enabled: false, rate: 0 } });
    expect(fields.map(({ path }) => path.join("."))).toEqual(["new_feature.enabled", "new_feature.rate"]);
});
