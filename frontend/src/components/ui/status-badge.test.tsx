import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge, PriorityBadge } from "./status-badge";

describe("StatusBadge", () => {
  it("renders the capitalized status label", () => {
    render(<StatusBadge status="in_progress" />);
    expect(screen.getByText("In progress")).toBeInTheDocument();
  });

  it("applies the status-specific color class", () => {
    render(<StatusBadge status="completed" />);
    const badge = screen.getByText("Completed");
    expect(badge.className).toMatch(/success/);
  });

  it("merges a custom className alongside the status color", () => {
    render(<StatusBadge status="paid" className="custom-cls" />);
    const badge = screen.getByText("Paid");
    expect(badge.className).toContain("custom-cls");
    expect(badge.className).toMatch(/success/);
  });
});

describe("PriorityBadge", () => {
  it("renders the capitalized priority label", () => {
    render(<PriorityBadge priority="urgent" />);
    expect(screen.getByText("Urgent")).toBeInTheDocument();
  });

  it("applies the danger color for urgent priority", () => {
    render(<PriorityBadge priority="urgent" />);
    expect(screen.getByText("Urgent").className).toMatch(/danger/);
  });
});
