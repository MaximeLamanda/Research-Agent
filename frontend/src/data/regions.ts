import { FRENCH_DEPARTMENTS } from "@/data/french-departments";
import { GERMAN_LANDER } from "@/data/german-landern";
import { IRELAND_PROVINCES } from "@/data/ireland-provinces";
import { UK_REGIONS } from "@/data/uk-regions";

export interface Region {
  code: string;
  name: string;
}

const REGIONS_BY_COUNTRY: Record<string, Region[]> = {
  FR: FRENCH_DEPARTMENTS,
  DE: GERMAN_LANDER,
  GB: UK_REGIONS,
  IE: IRELAND_PROVINCES,
};

export function getRegionsForCountry(country: string): Region[] {
  return REGIONS_BY_COUNTRY[country] ?? [];
}

export function getRegionCodesForCountry(country: string): string[] {
  return getRegionsForCountry(country).map((region) => region.code);
}

export function getRegionLabel(code: string, country: string = "FR"): string {
  const formatted = code.match(/^([A-Z]{2,3}|\d{2}[AB]?)\s*[-—]\s*(.+)$/i);
  if (formatted) {
    return `${formatted[1].toUpperCase()} — ${formatted[2]}`;
  }

  const regions = getRegionsForCountry(country);
  const region = regions.find((entry) => entry.code === code);
  if (region) {
    return `${region.code} — ${region.name}`;
  }

  for (const fallbackCountry of Object.keys(REGIONS_BY_COUNTRY)) {
    if (fallbackCountry === country) continue;
    const fallback = REGIONS_BY_COUNTRY[fallbackCountry].find((entry) => entry.code === code);
    if (fallback) {
      return `${fallback.code} — ${fallback.name}`;
    }
  }

  return code;
}

export function filterRegionCodesForCountry(codes: string[], country: string): string[] {
  const valid = new Set(getRegionCodesForCountry(country));
  return codes.filter((code) => valid.has(code));
}
