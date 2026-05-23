import { describe, it, expect } from "vitest";
import { filterLocations } from "./locations";
import type { Location } from "@/types";

function loc(overrides: Partial<Location> & { name?: string }): Location {
  return {
    id: "loc-1",
    tenant_id: "t-1",
    client_id: "c-1",
    name: overrides.name ?? "Main Lobby",
    address: {
      street: "123 Main St",
      city: "Austin",
      state: "TX",
      zip: "78701",
      country: "US",
      ...(overrides.address ?? {}),
    },
    is_active: true,
    ...overrides,
  } as Location;
}

describe("filterLocations", () => {
  it("returns all items when query is empty", () => {
    const items = [loc({ name: "A" }), loc({ name: "B" })];
    expect(filterLocations(items, "")).toHaveLength(2);
  });

  it("matches on name (case-insensitive)", () => {
    const items = [loc({ name: "Main Lobby" }), loc({ name: "Back Office" })];
    expect(filterLocations(items, "main")).toHaveLength(1);
    expect(filterLocations(items, "MAIN")).toHaveLength(1);
  });

  it("matches on street and city", () => {
    const items = [
      loc({ name: "X", address: { street: "Common Blvd", city: "Austin", state: "TX", zip: "", country: "US" } }),
      loc({ name: "Y", address: { street: "Other Rd", city: "Common City", state: "TX", zip: "", country: "US" } }),
      loc({ name: "Z", address: { street: "Elm", city: "Dallas", state: "TX", zip: "", country: "US" } }),
    ];
    expect(filterLocations(items, "common")).toHaveLength(2);
  });

  // Regression for POC-001: searching "common" against a location whose
  // address.street is null used to crash the entire Locations page.
  it("does not crash when address.street is null", () => {
    const items = [
      loc({
        name: "Bayfront",
        address: { street: null as unknown as string, city: "Corpus Christi", state: "TX", zip: "78401", country: "US" },
      }),
    ];
    expect(() => filterLocations(items, "common")).not.toThrow();
    expect(filterLocations(items, "corpus")).toHaveLength(1);
  });

  it("does not crash when address itself is null", () => {
    const items = [
      loc({ name: "No Address", address: null as unknown as Location["address"] }),
    ];
    expect(() => filterLocations(items, "anything")).not.toThrow();
  });

  it("does not crash when name is null", () => {
    const items = [
      loc({ name: null as unknown as string }),
    ];
    expect(() => filterLocations(items, "anything")).not.toThrow();
  });
});
