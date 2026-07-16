"use client";

import { RunStep } from "@/lib/api";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

const STEP_LABELS: Record<string, string> = {
  run_started: "Démarrage",
  searching: "Recherche",
  exa_search_start: "Exa recherche",
  exa_search_done: "Exa recherche OK",
  prefilter_start: "Préfiltre LLM",
  prefilter_done: "Préfiltre LLM OK",
  prefilter_failed: "Préfiltre LLM échoué",
  exa_fetch_start: "Exa fetch",
  exa_fetch_done: "Exa fetch OK",
  extracting: "Extraction",
  llm_extract_start: "LLM extraction",
  llm_extract_done: "LLM extraction OK",
  article_not_relevant: "Non pertinent",
  article_skipped: "Article ignoré",
  company_searching: "Recherche SIREN",
  api_entreprise_search_start: "API gouv",
  api_entreprise_search_done: "API gouv OK",
  llm_company_resolve_start: "LLM SIREN",
  llm_company_resolve_done: "LLM SIREN OK",
  company_resolved: "SIREN identifié",
  company_skipped: "SIREN ignoré",
  project_found: "Projet",
  project_imported_cross_department: "Import cross-dépt.",
  deduplicating: "Déduplication",
  llm_dedup_start: "LLM dédup",
  llm_dedup_done: "LLM dédup OK",
  project_merged: "Fusion",
  run_completed: "Terminé",
  run_failed: "Échec",
  run_cancelled: "Arrêté",
};

const STEP_COLORS: Record<string, string> = {
  exa_search_start: "bg-sky-500",
  exa_search_done: "bg-sky-400",
  exa_fetch_start: "bg-cyan-500",
  exa_fetch_done: "bg-cyan-400",
  llm_extract_start: "bg-violet-500",
  llm_extract_done: "bg-violet-400",
  llm_company_resolve_start: "bg-fuchsia-500",
  llm_company_resolve_done: "bg-fuchsia-400",
  llm_dedup_start: "bg-amber-500",
  llm_dedup_done: "bg-amber-400",
  api_entreprise_search_start: "bg-teal-500",
  api_entreprise_search_done: "bg-teal-400",
  article_not_relevant: "bg-orange-400",
  article_skipped: "bg-gray-400",
  project_found: "bg-emerald-500",
  project_imported_cross_department: "bg-sky-400",
  run_failed: "bg-red-500",
};

function formatOffset(ms: number): string {
  if (ms < 1000) return `+${ms} ms`;
  return `+${(ms / 1000).toFixed(2)} s`;
}

function stepDuration(step: RunStep, nextOffset: number | null): number {
  const explicit = step.data.duration_ms;
  if (typeof explicit === "number" && explicit > 0) return explicit;
  const offset = step.data.offset_ms;
  if (typeof offset === "number" && typeof nextOffset === "number" && nextOffset > offset) {
    return nextOffset - offset;
  }
  return 50;
}

function stepColor(stepType: string): string {
  return STEP_COLORS[stepType] ?? "bg-muted-foreground/50";
}

interface ExaSearchResult {
  url: string;
  title?: string;
  score?: number;
  published_at?: string;
  snippet?: string;
}

interface ExaFetchedArticle {
  url: string;
  title?: string;
  text_length?: number;
}

function asExaSearchResults(data: Record<string, unknown>): ExaSearchResult[] {
  const raw = data.results;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => ({
      url: String(item.url ?? ""),
      title: item.title != null ? String(item.title) : undefined,
      score: typeof item.score === "number" ? item.score : undefined,
      published_at: item.published_at != null ? String(item.published_at) : undefined,
      snippet: item.snippet != null ? String(item.snippet) : undefined,
    }))
    .filter((item) => item.url.length > 0);
}

function asExaFetchedArticles(data: Record<string, unknown>): ExaFetchedArticle[] {
  const raw = data.articles;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => ({
      url: String(item.url ?? ""),
      title: item.title != null ? String(item.title) : undefined,
      text_length: typeof item.text_length === "number" ? item.text_length : undefined,
    }))
    .filter((item) => item.url.length > 0);
}

function ExaSearchResultsAccordion({
  results,
  query,
}: {
  results: ExaSearchResult[];
  query?: string;
}) {
  if (results.length === 0) return null;

  return (
    <Accordion type="single" collapsible className="mt-1.5 w-full">
      <AccordionItem value="results" className="border-none">
        <AccordionTrigger className="py-1.5 text-xs text-muted-foreground hover:no-underline">
          {results.length} résultat{results.length > 1 ? "s" : ""} de recherche
        </AccordionTrigger>
        <AccordionContent className="pb-1">
          {query && (
            <p className="mb-2 text-[11px] text-muted-foreground">
              <span className="font-medium">Requête :</span> {query}
            </p>
          )}
          <ul className="space-y-2">
            {results.map((result) => (
              <li key={result.url} className="rounded-md border bg-muted/20 px-2.5 py-2 text-xs">
                <a
                  href={result.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-blue-600 hover:underline line-clamp-2"
                >
                  {result.title || result.url}
                </a>
                <div className="mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5 text-[10px] text-muted-foreground">
                  {result.score != null && (
                    <span>score {result.score.toFixed(3)}</span>
                  )}
                  {result.published_at && (
                    <span>{new Date(result.published_at).toLocaleDateString("fr-FR")}</span>
                  )}
                </div>
                {result.snippet && (
                  <p className="mt-1 line-clamp-2 text-[11px] text-muted-foreground">
                    {result.snippet}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

function ExaFetchArticlesAccordion({ articles }: { articles: ExaFetchedArticle[] }) {
  if (articles.length === 0) return null;

  return (
    <Accordion type="single" collapsible className="mt-1.5 w-full">
      <AccordionItem value="articles" className="border-none">
        <AccordionTrigger className="py-1.5 text-xs text-muted-foreground hover:no-underline">
          {articles.length} article{articles.length > 1 ? "s" : ""} récupéré
          {articles.length > 1 ? "s" : ""}
        </AccordionTrigger>
        <AccordionContent className="pb-1">
          <ul className="space-y-1.5">
            {articles.map((article) => (
              <li key={article.url} className="rounded-md border bg-muted/20 px-2.5 py-2 text-xs">
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-blue-600 hover:underline line-clamp-2"
                >
                  {article.title || article.url}
                </a>
                {article.text_length != null && (
                  <p className="mt-0.5 text-[10px] text-muted-foreground">
                    {article.text_length.toLocaleString("fr-FR")} caractères
                  </p>
                )}
              </li>
            ))}
          </ul>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

function StepDedupDetails({ step }: { step: RunStep }) {
  if (step.step_type !== "llm_dedup_start" && step.step_type !== "llm_dedup_done") {
    return null;
  }

  const projectA =
    typeof step.data.project_a === "string" ? step.data.project_a : null;
  const projectB =
    typeof step.data.project_b === "string" ? step.data.project_b : null;
  const sameProject =
    step.step_type === "llm_dedup_done" && typeof step.data.same_project === "boolean"
      ? step.data.same_project
      : null;
  const reason =
    step.step_type === "llm_dedup_done" && typeof step.data.reason === "string"
      ? step.data.reason.trim()
      : "";

  if (!projectA && !projectB && sameProject == null && !reason) {
    return null;
  }

  return (
    <Accordion type="single" collapsible className="mt-1.5 w-full">
      <AccordionItem value="dedup" className="border-none">
        <AccordionTrigger className="py-1.5 text-xs text-muted-foreground hover:no-underline">
          {projectA && projectB
            ? `${projectA} vs ${projectB}`
            : "Comparaison dédup"}
          {sameProject != null && (
            <span
              className={
                sameProject
                  ? "ml-2 font-medium text-emerald-600 dark:text-emerald-400"
                  : "ml-2 font-medium text-orange-600 dark:text-orange-400"
              }
            >
              {sameProject ? "· même chantier" : "· chantiers distincts"}
            </span>
          )}
        </AccordionTrigger>
        <AccordionContent className="pb-1">
          <div className="space-y-2 rounded-md border bg-amber-500/5 px-2.5 py-2 text-xs">
            {projectA && projectB && (
              <p className="text-muted-foreground">
                <span className="font-medium text-foreground">{projectA}</span>
                {" vs "}
                <span className="font-medium text-foreground">{projectB}</span>
              </p>
            )}
            {reason ? (
              <div>
                <p className="font-medium text-foreground">Raison</p>
                <p className="mt-1 leading-relaxed text-muted-foreground">{reason}</p>
              </div>
            ) : (
              <p className="text-muted-foreground">Analyse LLM en cours…</p>
            )}
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

function StepExaDetails({ step }: { step: RunStep }) {
  if (step.step_type === "exa_search_done") {
    const results = asExaSearchResults(step.data);
    const query = typeof step.data.query === "string" ? step.data.query : undefined;
    return <ExaSearchResultsAccordion results={results} query={query} />;
  }
  if (step.step_type === "exa_fetch_done") {
    const articles = asExaFetchedArticles(step.data);
    return <ExaFetchArticlesAccordion articles={articles} />;
  }
  return null;
}

function StepArticleSkippedDetails({ step }: { step: RunStep }) {
  if (step.step_type !== "article_skipped") return null;

  const url = typeof step.data.url === "string" ? step.data.url : "";
  const reason = typeof step.data.reason === "string" ? step.data.reason : "";
  const prefilterReason =
    typeof step.data.prefilter_reason === "string" ? step.data.prefilter_reason.trim() : "";

  if (!url && !prefilterReason) return null;

  return (
    <div className="mt-1 rounded-md border bg-muted/20 px-2.5 py-2 text-xs text-muted-foreground">
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="line-clamp-2 font-medium text-blue-600 hover:underline"
        >
          {url}
        </a>
      )}
      {reason === "prefiltered" && prefilterReason && (
        <p className="mt-1 leading-relaxed">
          <span className="font-medium text-foreground">Raison LLM :</span> {prefilterReason}
        </p>
      )}
    </div>
  );
}

export function RunStepsTimeline({ steps }: { steps: RunStep[] }) {
  if (steps.length === 0) {
    return <p className="text-sm text-muted-foreground">Aucune étape enregistrée.</p>;
  }

  const offsets = steps.map((s) =>
    typeof s.data.offset_ms === "number" ? s.data.offset_ms : 0
  );
  const totalMs = Math.max(
    ...offsets,
    ...steps.map((s) => (typeof s.data.duration_ms === "number" ? s.data.duration_ms : 0))
  ) || 1;

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Histogramme ({steps.length} étapes)</span>
          <span className="tabular-nums">durée totale ~{formatOffset(totalMs)}</span>
        </div>
        <div className="flex h-6 w-full overflow-hidden rounded-md border bg-muted/30">
          {steps.map((step, index) => {
            const nextOffset =
              index < steps.length - 1 ? offsets[index + 1] : offsets[index];
            const duration = stepDuration(step, nextOffset);
            const widthPct = Math.max((duration / totalMs) * 100, 1.5);
            return (
              <div
                key={step.id}
                title={`${STEP_LABELS[step.step_type] ?? step.step_type} — ${formatOffset(offsets[index])}${typeof step.data.duration_ms === "number" ? ` (${step.data.duration_ms} ms)` : ""}`}
                className={`${stepColor(step.step_type)} h-full shrink-0 border-r border-background/20 last:border-r-0`}
                style={{ width: `${widthPct}%` }}
              />
            );
          })}
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-sm bg-violet-500" /> LLM
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-sm bg-sky-500" /> Exa
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-sm bg-teal-500" /> API gouv
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-sm bg-emerald-500" /> Projet
          </span>
        </div>
      </div>

      <ol className="relative max-h-80 space-y-2 overflow-y-auto border-l pl-4">
        {steps.map((step) => {
          const offset =
            typeof step.data.offset_ms === "number" ? step.data.offset_ms : null;
          const duration =
            typeof step.data.duration_ms === "number" ? step.data.duration_ms : null;
          return (
            <li key={step.id} className="text-sm">
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
                  {offset != null ? formatOffset(offset) : "—"}
                </span>
                {duration != null && (
                  <span className="font-mono text-[11px] text-violet-600 dark:text-violet-400 tabular-nums">
                    {duration} ms
                  </span>
                )}
                <span className="font-medium">
                  {STEP_LABELS[step.step_type] ?? step.step_type}
                </span>
              </div>
              {step.message && (
                <p className="text-xs text-muted-foreground">{step.message}</p>
              )}
              <StepDedupDetails step={step} />
              <StepExaDetails step={step} />
              <StepArticleSkippedDetails step={step} />
            </li>
          );
        })}
      </ol>
    </div>
  );
}
