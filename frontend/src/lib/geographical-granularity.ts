export const GEOGRAPHICAL_GRANULARITY_LARGE = "large";

export type GeographicalGranularity = typeof GEOGRAPHICAL_GRANULARITY_LARGE;

export const GEOGRAPHICAL_GRANULARITY_OPTIONS = [
  { value: GEOGRAPHICAL_GRANULARITY_LARGE, label: "Département" },
] as const;
