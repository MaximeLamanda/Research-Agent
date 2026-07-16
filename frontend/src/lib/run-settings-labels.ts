import { GEOGRAPHICAL_GRANULARITY_OPTIONS } from "@/lib/geographical-granularity";

const EXA_SEARCH_TYPE_LABELS: Record<string, string> = {
  auto: "Auto",
  neural: "Neural",
  keyword: "Keyword",
  fast: "Fast",
};

const EXA_CATEGORY_LABELS: Record<string, string> = {
  news: "News",
  company: "Company",
  "research paper": "Research paper",
  pdf: "PDF",
  github: "GitHub",
  tweet: "Tweet",
  "personal site": "Personal site",
  "linkedin profile": "LinkedIn profile",
  "financial report": "Financial report",
};

export function geographicalGranularityLabel(value: string): string {
  return (
    GEOGRAPHICAL_GRANULARITY_OPTIONS.find((option) => option.value === value)?.label ??
    (value === "city_focus" ? "Département" : value)
  );
}

export function exaSearchTypeLabel(value: string): string {
  return EXA_SEARCH_TYPE_LABELS[value] ?? value;
}

export function exaCategoryLabel(value: string): string {
  return EXA_CATEGORY_LABELS[value] ?? value;
}
