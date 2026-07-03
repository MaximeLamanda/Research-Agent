import { Source } from "@/lib/api";
import { getCountryLabel } from "@/data/countries";
import { getRegionLabel } from "@/data/regions";

export const STATUS_LABELS: Record<string, string> = {
  conception: "Design",
  travaux: "Construction",
  livraison: "Delivery",
};

const STATUS_CANONICAL_KEYS: Record<string, keyof typeof STATUS_LABELS> = {
  conception: "conception",
  travaux: "travaux",
  livraison: "livraison",
  design: "conception",
  construction: "travaux",
  delivery: "livraison",
};

export function resolveStatusKey(status: string | null | undefined): string | null {
  if (!status) return null;
  return STATUS_CANONICAL_KEYS[status.toLowerCase()] ?? null;
}

export function formatProjectStatus(status: string | null | undefined): string {
  if (!status) return "—";
  const key = resolveStatusKey(status);
  if (key) return STATUS_LABELS[key];
  return status;
}

export function formatSurface(value: number | string | null): string {
  if (value === null || value === undefined || value === "") return "—";
  const num = Number(value);
  if (Number.isNaN(num)) return "—";
  return Math.round(num).toLocaleString("en-US");
}

export function formatRunIds(sources: Source[]): string {
  const ids = new Set<string>();
  for (const source of sources) {
    if (source.run_id) ids.add(source.run_id.slice(0, 8));
  }
  if (ids.size === 0) return "—";
  return Array.from(ids).join(", ");
}

export function formatRunDates(sources: Source[]): string {
  const labels = new Map<string, string>();
  for (const source of sources) {
    if (!source.run_id) continue;
    const dateValue = source.run_started_at ?? source.created_at;
    if (!dateValue) continue;
    labels.set(source.run_id, formatDate(dateValue));
  }
  if (labels.size === 0) return "—";
  return Array.from(labels.values()).join(", ");
}

export function formatArticleDates(sources: Source[]): string {
  const dates = new Set<string>();
  for (const source of sources) {
    if (source.published_at) {
      dates.add(formatDate(source.published_at));
    }
  }
  if (dates.size === 0) return "—";
  return Array.from(dates).join(", ");
}

export function formatSourcesBulleted(sources: Source[]): string {
  if (sources.length === 0) return "—";
  return sources
    .map((source) => {
      const title = source.title || "Untitled article";
      const dateStr = source.published_at ? formatDate(source.published_at) : null;
      const lines = [`• ${title}`];
      if (dateStr) lines.push(`  ${dateStr}`);
      lines.push(`  ${source.url}`);
      return lines.join("\n");
    })
    .join("\n\n");
}

export function formatDate(value: string | null): string {
  if (!value) return "—";
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (match) {
    const [, year, month, day] = match;
    return new Date(Number(year), Number(month) - 1, Number(day)).toLocaleDateString(
      "en-US"
    );
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-US");
}

export function formatDepartment(
  code: string | null,
  country: string | null = "FR"
): string {
  if (!code) return "—";
  return getRegionLabel(code, country || "FR");
}

export function formatCountry(code: string | null): string {
  return getCountryLabel(code);
}

export function formatPeople(
  people: { name: string; role?: string; company?: string }[]
): string {
  if (people.length === 0) return "—";
  return people
    .map((p) => {
      const parts = [p.name];
      if (p.role) parts.push(p.role);
      if (p.company) parts.push(p.company);
      return parts.join(" — ");
    })
    .join(" | ");
}

export function formatSourceUrls(sources: Source[]): string {
  if (sources.length === 0) return "—";
  return sources.map((s) => s.url).join("\n");
}
