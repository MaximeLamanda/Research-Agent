import { getSearchAnchors } from "@/lib/api";
import { pruneRegionCities } from "@/lib/region-cities";

export const GEOGRAPHICAL_GRANULARITY_LARGE = "large";
export const GEOGRAPHICAL_GRANULARITY_CITY_FOCUS = "city_focus";

export type GeographicalGranularity =
  | typeof GEOGRAPHICAL_GRANULARITY_LARGE
  | typeof GEOGRAPHICAL_GRANULARITY_CITY_FOCUS;

export const GEOGRAPHICAL_GRANULARITY_OPTIONS = [
  { value: GEOGRAPHICAL_GRANULARITY_LARGE, label: "Large" },
  { value: GEOGRAPHICAL_GRANULARITY_CITY_FOCUS, label: "City focus" },
] as const;

export async function fetchDefaultRegionCities(
  country: string,
  regionCodes: string[]
): Promise<Record<string, string[]>> {
  if (regionCodes.length === 0) {
    return {};
  }
  const anchors = await getSearchAnchors(country, regionCodes);
  const result: Record<string, string[]> = {};
  for (const code of regionCodes) {
    const cities = anchors[code]?.cities ?? [];
    if (cities.length > 0) {
      result[code] = [...cities];
    }
  }
  return result;
}

export function mergeWithDefaultRegionCities(
  current: Record<string, string[]>,
  selectedCodes: string[],
  defaults: Record<string, string[]>
): Record<string, string[]> {
  const merged = pruneRegionCities(current, selectedCodes);
  for (const code of selectedCodes) {
    if (!merged[code]?.length) {
      const defaultCities = defaults[code];
      if (defaultCities?.length) {
        merged[code] = [...defaultCities];
      }
    }
  }
  return merged;
}
