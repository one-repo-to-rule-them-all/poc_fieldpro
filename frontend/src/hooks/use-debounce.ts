import { useState, useEffect } from "react";
import { TIMINGS } from "@/lib/timings";

export function useDebounce<T>(value: T, delay = TIMINGS.DEBOUNCE_SEARCH_MS): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}
