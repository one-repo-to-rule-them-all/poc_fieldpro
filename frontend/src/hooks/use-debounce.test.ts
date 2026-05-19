import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDebounce } from "./use-debounce";

describe("useDebounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns the initial value immediately", () => {
    const { result } = renderHook(() => useDebounce("hello", 500));
    expect(result.current).toBe("hello");
  });

  it("does not update before the delay elapses", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 500),
      { initialProps: { value: "a" } }
    );
    rerender({ value: "b" });
    act(() => {
      vi.advanceTimersByTime(499);
    });
    expect(result.current).toBe("a");
  });

  it("updates to the latest value once the delay elapses", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 500),
      { initialProps: { value: "a" } }
    );
    rerender({ value: "b" });
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(result.current).toBe("b");
  });

  it("resets the timer when the value changes again within the delay", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 500),
      { initialProps: { value: "a" } }
    );
    rerender({ value: "b" });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    rerender({ value: "c" });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toBe("a");
    act(() => {
      vi.advanceTimersByTime(200);
    });
    expect(result.current).toBe("c");
  });
});
