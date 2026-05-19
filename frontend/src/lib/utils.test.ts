import { describe, it, expect } from "vitest";
import {
  formatCurrency,
  formatDate,
  getInitials,
  truncate,
  buildQueryString,
  getStatusColor,
  getPriorityColor,
  capitalize,
  getDistanceLabel,
  cn,
} from "./utils";

describe("formatCurrency", () => {
  it("formats whole numbers with 2 decimals", () => {
    expect(formatCurrency(100)).toBe("$100.00");
  });
  it("formats fractional amounts", () => {
    expect(formatCurrency(1234.5)).toBe("$1,234.50");
  });
  it("formats zero", () => {
    expect(formatCurrency(0)).toBe("$0.00");
  });
});

describe("formatDate", () => {
  it("formats an ISO date with the default format", () => {
    expect(formatDate("2026-05-18")).toBe("May 18, 2026");
  });
  it("accepts a custom format string", () => {
    expect(formatDate("2026-05-18", "yyyy-MM-dd")).toBe("2026-05-18");
  });
  it("returns 'Invalid date' for unparseable input", () => {
    expect(formatDate("not-a-date")).toBe("Invalid date");
  });
});

describe("getInitials", () => {
  it("returns uppercase initials", () => {
    expect(getInitials("rodolfo", "baez")).toBe("RB");
  });
  it("trims whitespace before taking the first character", () => {
    expect(getInitials("  alice", " smith")).toBe("AS");
  });
});

describe("truncate", () => {
  it("returns the string unchanged when shorter than the limit", () => {
    expect(truncate("hi", 10)).toBe("hi");
  });
  it("truncates and appends an ellipsis when longer than the limit", () => {
    expect(truncate("hello world", 5)).toBe("hello…");
  });
});

describe("buildQueryString", () => {
  it("returns an empty string when no params are set", () => {
    expect(buildQueryString({})).toBe("");
  });
  it("omits undefined, null, and empty-string values", () => {
    expect(
      buildQueryString({ a: 1, b: undefined, c: null, d: "", e: "x" })
    ).toBe("?a=1&e=x");
  });
  it("encodes special characters", () => {
    expect(buildQueryString({ q: "a b&c" })).toBe("?q=a+b%26c");
  });
});

describe("getStatusColor", () => {
  it("returns the mapped color for a known work-order status", () => {
    expect(getStatusColor("in_progress")).toContain("warning");
  });
  it("returns the mapped color for a known invoice status", () => {
    expect(getStatusColor("paid")).toContain("success");
  });
  it("falls back to a neutral color for unknown statuses", () => {
    // @ts-expect-error — exercising the fallback branch
    expect(getStatusColor("totally-bogus")).toBe(
      "bg-neutral-100 text-neutral-700"
    );
  });
});

describe("getPriorityColor", () => {
  it("returns the danger style for urgent", () => {
    expect(getPriorityColor("urgent")).toContain("danger");
  });
});

describe("capitalize", () => {
  it("uppercases the first letter and replaces underscores with spaces", () => {
    expect(capitalize("in_progress")).toBe("In progress");
  });
});

describe("getDistanceLabel", () => {
  it("uses meters for sub-kilometer distances", () => {
    expect(getDistanceLabel(250)).toBe("250m away");
  });
  it("uses kilometers for distances >= 1000m", () => {
    expect(getDistanceLabel(1500)).toBe("1.5km away");
  });
});

describe("cn", () => {
  it("merges Tailwind class names and dedupes conflicts", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
  });
});
