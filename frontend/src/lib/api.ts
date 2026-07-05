const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface RunStep {
  id: string;
  run_id: string;
  step_type: string;
  message: string | null;
  data: Record<string, unknown>;
  created_at: string | null;
}

export interface Config {
  id: number;
  country: string;
  departments: string[];
  region_cities: Record<string, string[]>;
  cron_day: number;
  cron_hour: number;
  sectors: string[];
  exa_search_type: string;
  exa_category: string;
  geographical_granularity: string;
  exa_published_date_preset: string | null;
  exa_start_published_date: string | null;
  exa_end_published_date: string | null;
  exa_published_date_effective_start: string | null;
  exa_published_date_effective_end: string | null;
}

export interface RegionAnchor {
  code: string;
  metro: string | null;
  cities: string[];
}

export interface Source {
  id: string;
  url: string;
  title: string | null;
  published_at: string | null;
  created_at: string | null;
  run_id: string | null;
  run_started_at: string | null;
  is_relevant: boolean | null;
}

export interface Project {
  id: string;
  name: string;
  company: string | null;
  siren: string | null;
  company_legal_name: string | null;
  naf_code: string | null;
  surface_m2: number | null;
  delivery_date: string | null;
  city: string | null;
  address: string | null;
  department: string | null;
  country: string | null;
  status: string | null;
  sector: string | null;
  people: { name: string; role?: string; company?: string }[];
  lead_pitch: string | null;
  sources: Source[];
  first_seen_at: string | null;
  last_updated_at: string | null;
}

export interface Run {
  id: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
  articles_found: number;
  projects_new: number;
  projects_updated: number;
  projects_merged?: number;
  error_message: string | null;
  mode: string;
  geographical_granularity: string;
  exa_search_type: string;
  exa_category: string;
}

export interface ProjectMerge {
  id: string;
  run_id: string | null;
  kept_project_id: string;
  absorbed_project_id: string;
  method: string;
  score: number | null;
  snapshot: {
    kept?: { name?: string; company?: string; city?: string };
    absorbed?: { name?: string; company?: string; city?: string };
    changes?: FieldChange[];
    sources_transferred?: { url: string; title?: string | null }[];
    reason?: string;
  };
  created_at: string | null;
}

export interface FieldChange {
  field: string;
  old: string | number | null;
  new: string | number | null;
}

export interface ProjectUpdate {
  id: string;
  run_id: string;
  project_id: string;
  project_name: string;
  source_id: string;
  source_url: string;
  source_title: string | null;
  changes: FieldChange[];
  created_at: string | null;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly cause?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (error) {
    throw new ApiError(
      `Unable to reach the API (${API_URL}). Make sure the backend is running.`,
      error
    );
  }
  if (!response.ok) {
    let detail = `API error ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new ApiError(detail);
  }
  return response.json();
}

export function getConfig() {
  return request<Config>("/api/config");
}

export function updateConfig(data: Partial<Config>) {
  return request<Config>("/api/config", { method: "PUT", body: JSON.stringify(data) });
}

export function getSearchAnchors(country: string, codes?: string[]) {
  const params = new URLSearchParams({ country });
  if (codes?.length) {
    for (const code of codes) {
      params.append("codes", code);
    }
  }
  return request<Record<string, RegionAnchor>>(`/api/search-anchors?${params.toString()}`);
}

export function getProjects(params?: { departments?: string[]; country?: string }) {
  const search = new URLSearchParams();
  params?.departments?.forEach((d) => search.append("departments", d));
  if (params?.country) search.set("country", params.country);
  const qs = search.toString();
  return request<Project[]>(`/api/projects${qs ? `?${qs}` : ""}`);
}

export function getProject(projectId: string) {
  return request<Project>(`/api/projects/${projectId}`);
}

export function getProjectMerges(projectId: string) {
  return request<ProjectMerge[]>(`/api/projects/${projectId}/merges`);
}

export function getRuns() {
  return request<Run[]>("/api/runs");
}

export function getRun(runId: string) {
  return request<Run>(`/api/runs/${runId}`);
}

export function getRunMerges(runId: string) {
  return request<ProjectMerge[]>(`/api/runs/${runId}/merges`);
}

export function getRunUpdates(runId: string) {
  return request<ProjectUpdate[]>(`/api/runs/${runId}/updates`);
}

export function getRunSources(runId: string) {
  return request<Source[]>(`/api/runs/${runId}/sources`);
}

export function getRunSteps(runId: string) {
  return request<RunStep[]>(`/api/runs/${runId}/steps`);
}

export function triggerRun(mode: "full" | "test_single" = "full") {
  return request<Run>("/api/runs", { method: "POST", body: JSON.stringify({ mode }) });
}

export interface RunDedupResponse {
  run_id: string;
  status: "started";
  scope: "run" | "config" | "all";
  targets: Array<{ country: string; departments: string[] }>;
}

export function triggerRunDedup(
  runId: string,
  options?: { scope?: "run" | "config" | "all"; departments?: string[]; country?: string }
) {
  return request<RunDedupResponse>(`/api/runs/${runId}/dedup`, {
    method: "POST",
    body: JSON.stringify(options ?? {}),
  });
}

export function triggerTestRun() {
  return triggerRun("test_single");
}
