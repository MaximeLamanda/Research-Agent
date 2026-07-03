import { format, startOfMonth, startOfWeek, startOfYear, subDays } from "date-fns";

export const PUBLISHED_DATE_PRESET_ALL = "all";
export const PUBLISHED_DATE_PRESET_TODAY = "today";
export const PUBLISHED_DATE_PRESET_THIS_WEEK = "this_week";
export const PUBLISHED_DATE_PRESET_THIS_MONTH = "this_month";
export const PUBLISHED_DATE_PRESET_THIS_YEAR = "this_year";
export const PUBLISHED_DATE_PRESET_LAST_7_DAYS = "last_7_days";
export const PUBLISHED_DATE_PRESET_LAST_30_DAYS = "last_30_days";
export const PUBLISHED_DATE_PRESET_LAST_90_DAYS = "last_90_days";
export const PUBLISHED_DATE_PRESET_CUSTOM = "custom";

export type PublishedDatePreset =
  | typeof PUBLISHED_DATE_PRESET_ALL
  | typeof PUBLISHED_DATE_PRESET_TODAY
  | typeof PUBLISHED_DATE_PRESET_THIS_WEEK
  | typeof PUBLISHED_DATE_PRESET_THIS_MONTH
  | typeof PUBLISHED_DATE_PRESET_THIS_YEAR
  | typeof PUBLISHED_DATE_PRESET_LAST_7_DAYS
  | typeof PUBLISHED_DATE_PRESET_LAST_30_DAYS
  | typeof PUBLISHED_DATE_PRESET_LAST_90_DAYS
  | typeof PUBLISHED_DATE_PRESET_CUSTOM;

export const PUBLISHED_DATE_PRESETS: { value: PublishedDatePreset; label: string }[] = [
  { value: PUBLISHED_DATE_PRESET_ALL, label: "All time" },
  { value: PUBLISHED_DATE_PRESET_TODAY, label: "Today" },
  { value: PUBLISHED_DATE_PRESET_THIS_WEEK, label: "This week" },
  { value: PUBLISHED_DATE_PRESET_THIS_MONTH, label: "This month" },
  { value: PUBLISHED_DATE_PRESET_THIS_YEAR, label: "This year" },
  { value: PUBLISHED_DATE_PRESET_LAST_7_DAYS, label: "Last 7 days" },
  { value: PUBLISHED_DATE_PRESET_LAST_30_DAYS, label: "Last 30 days" },
  { value: PUBLISHED_DATE_PRESET_LAST_90_DAYS, label: "Last 90 days" },
  { value: PUBLISHED_DATE_PRESET_CUSTOM, label: "Custom range" },
];

function toIsoDate(date: Date): string {
  return format(date, "yyyy-MM-dd");
}

export function resolvePublishedDateRange(
  preset: PublishedDatePreset | string | null | undefined,
  startDate?: string,
  endDate?: string,
  referenceDate: Date = new Date()
): { startDate: string | null; endDate: string | null } {
  const today = referenceDate;

  if (!preset || preset === PUBLISHED_DATE_PRESET_ALL) {
    return { startDate: null, endDate: null };
  }

  if (preset === PUBLISHED_DATE_PRESET_CUSTOM) {
    return {
      startDate: startDate || null,
      endDate: endDate || null,
    };
  }

  if (preset === PUBLISHED_DATE_PRESET_TODAY) {
    const iso = toIsoDate(today);
    return { startDate: iso, endDate: iso };
  }

  if (preset === PUBLISHED_DATE_PRESET_THIS_WEEK) {
    return {
      startDate: toIsoDate(startOfWeek(today, { weekStartsOn: 1 })),
      endDate: toIsoDate(today),
    };
  }

  if (preset === PUBLISHED_DATE_PRESET_THIS_MONTH) {
    return {
      startDate: toIsoDate(startOfMonth(today)),
      endDate: toIsoDate(today),
    };
  }

  if (preset === PUBLISHED_DATE_PRESET_THIS_YEAR) {
    return {
      startDate: toIsoDate(startOfYear(today)),
      endDate: toIsoDate(today),
    };
  }

  if (preset === PUBLISHED_DATE_PRESET_LAST_7_DAYS) {
    return {
      startDate: toIsoDate(subDays(today, 6)),
      endDate: toIsoDate(today),
    };
  }

  if (preset === PUBLISHED_DATE_PRESET_LAST_30_DAYS) {
    return {
      startDate: toIsoDate(subDays(today, 29)),
      endDate: toIsoDate(today),
    };
  }

  if (preset === PUBLISHED_DATE_PRESET_LAST_90_DAYS) {
    return {
      startDate: toIsoDate(subDays(today, 89)),
      endDate: toIsoDate(today),
    };
  }

  return {
    startDate: startDate || null,
    endDate: endDate || null,
  };
}

export function inferPublishedDatePreset(
  preset: string | null | undefined,
  startDate?: string | null,
  endDate?: string | null
): PublishedDatePreset {
  if (preset && PUBLISHED_DATE_PRESETS.some((option) => option.value === preset)) {
    return preset as PublishedDatePreset;
  }
  if (startDate || endDate) {
    return PUBLISHED_DATE_PRESET_CUSTOM;
  }
  return PUBLISHED_DATE_PRESET_ALL;
}

export function formatPublishedDateRangeLabel(
  preset: PublishedDatePreset,
  startDate?: string,
  endDate?: string
): string {
  const resolved = resolvePublishedDateRange(preset, startDate, endDate);
  if (!resolved.startDate && !resolved.endDate) {
    return "No date filter";
  }
  if (resolved.startDate && resolved.endDate) {
    if (resolved.startDate === resolved.endDate) {
      return resolved.startDate;
    }
    return `${resolved.startDate} → ${resolved.endDate}`;
  }
  if (resolved.startDate) {
    return `From ${resolved.startDate}`;
  }
  return `Until ${resolved.endDate}`;
}
