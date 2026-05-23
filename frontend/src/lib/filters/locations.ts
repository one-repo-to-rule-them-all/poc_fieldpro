import type { Location } from "@/types";

export function filterLocations(items: Location[], query: string): Location[] {
  if (!query) return items;
  const needle = query.toLowerCase();
  return items.filter(
    (loc) =>
      loc.name?.toLowerCase().includes(needle) ||
      loc.address?.street?.toLowerCase().includes(needle) ||
      loc.address?.city?.toLowerCase().includes(needle)
  );
}
