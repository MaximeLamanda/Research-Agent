export interface Country {
  code: string;
  label: string;
}

export const COUNTRIES: Country[] = [
  { code: "FR", label: "France" },
  { code: "DE", label: "Germany" },
];

export function getCountryLabel(code: string | null | undefined): string {
  if (!code) return "—";
  return COUNTRIES.find((country) => country.code === code)?.label ?? code;
}
