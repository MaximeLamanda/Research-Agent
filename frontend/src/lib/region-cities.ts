/** Identifiant composite région + ville pour le combobox multi-régions. */
const SEP = "|";

export function cityOptionId(regionCode: string, city: string): string {
  return `${regionCode}${SEP}${city}`;
}

export function parseCityOptionId(id: string): { regionCode: string; city: string } | null {
  const idx = id.indexOf(SEP);
  if (idx <= 0) {
    return null;
  }
  return {
    regionCode: id.slice(0, idx),
    city: id.slice(idx + 1),
  };
}

export function regionCitiesToOptionIds(regionCities: Record<string, string[]>): string[] {
  const ids: string[] = [];
  for (const [code, cities] of Object.entries(regionCities)) {
    for (const city of cities) {
      ids.push(cityOptionId(code, city));
    }
  }
  return ids;
}

export function optionIdsToRegionCities(ids: string[]): Record<string, string[]> {
  const result: Record<string, string[]> = {};
  for (const id of ids) {
    const parsed = parseCityOptionId(id);
    if (!parsed) {
      continue;
    }
    const list = result[parsed.regionCode] ?? [];
    if (!list.includes(parsed.city)) {
      list.push(parsed.city);
    }
    result[parsed.regionCode] = list;
  }
  return result;
}

export function pruneRegionCities(
  regionCities: Record<string, string[]>,
  selectedCodes: string[]
): Record<string, string[]> {
  const pruned: Record<string, string[]> = {};
  for (const code of selectedCodes) {
    const cities = regionCities[code];
    if (cities?.length) {
      pruned[code] = cities;
    }
  }
  return pruned;
}

export function cityChipLabel(
  regionCode: string,
  city: string,
  country: string,
  getRegionLabel: (code: string, country: string) => string
): string {
  const region = getRegionLabel(regionCode, country);
  const short = region.split("—")[0]?.trim() || regionCode;
  return `${city} (${short})`;
}
