import { nextMove } from "./nextMove";

const healthy = { status: "free", hunger: 10, fatigue: 10, health: 100, energy: 90, stress: 10 };
test("hospital status takes priority over food or work suggestions", () => {
    expect(nextMove({ ...healthy, status: "hospital", hunger: 100 }).to).toBe("/hospital");
});
test("a hungry free player can go directly to food", () => {
    expect(nextMove({ ...healthy, hunger: 90 }).to).toBe("/home#food");
});
test("working players do not receive an incompatible start-activity suggestion", () => {
    expect(nextMove({ ...healthy, hunger: 90, on_shift: { employment_id: "test" } }).to).toBe("/inventory");
});
test("owner-configured needs thresholds change dashboard guidance", () => {
    expect(nextMove({ ...healthy, hunger: 60 }, null, { hunger_damage_threshold: 50 }).to).toBe("/home#food");
    expect(nextMove({ ...healthy, energy: 40 }, null, { low_energy_threshold: 50 }).to).toBe("/home#rest");
    expect(nextMove({ ...healthy, health: 40 }, null, { health_warning_threshold: 45 }).to).toBe("/hospital");
});
