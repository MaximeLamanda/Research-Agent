export type ArticleLineStatus =
  | "pending"
  | "scanning"
  | "done"
  | "ignored"
  | "not_relevant";

export interface ArticleLine {
  url: string;
  title: string;
  score?: number;
  status: ArticleLineStatus;
  skipReason?: string;
}

export interface ArticleBatch {
  id: string;
  sector: string;
  department: string;
  collapsed: boolean;
  manuallyExpanded: boolean;
  articles: ArticleLine[];
}

export interface BatchesState {
  batches: ArticleBatch[];
  scanningUrl: string | null;
}

const TERMINAL: ArticleLineStatus[] = ["done", "ignored", "not_relevant"];

const SECTOR_LABELS: Record<string, string> = {
  industriel: "Industriel",
  logistique: "Logistique",
  retail: "Retail",
};

export function sectorLabel(sector: string): string {
  return SECTOR_LABELS[sector] ?? sector;
}

export function initialBatchesState(): BatchesState {
  return { batches: [], scanningUrl: null };
}

function isTerminal(status: ArticleLineStatus): boolean {
  return TERMINAL.includes(status);
}

function maybeCollapseBatch(batch: ArticleBatch): ArticleBatch {
  if (batch.manuallyExpanded) return batch;
  const allDone = batch.articles.length > 0 && batch.articles.every((a) => isTerminal(a.status));
  return allDone ? { ...batch, collapsed: true } : batch;
}

function updateArticleInLatestBatch(
  state: BatchesState,
  url: string,
  updater: (article: ArticleLine) => ArticleLine
): BatchesState {
  const batches = [...state.batches];
  for (let i = batches.length - 1; i >= 0; i--) {
    const idx = batches[i].articles.findIndex((a) => a.url === url);
    if (idx === -1) continue;
    const articles = [...batches[i].articles];
    articles[idx] = updater(articles[idx]);
    batches[i] = maybeCollapseBatch({ ...batches[i], articles });
    return { ...state, batches };
  }
  return state;
}

function markUnfetchedAsIgnored(
  batch: ArticleBatch,
  fetchedUrls: Set<string>
): ArticleBatch {
  const articles = batch.articles.map((a) =>
    !fetchedUrls.has(a.url) && a.status === "pending"
      ? { ...a, status: "ignored" as const, skipReason: "not_fetched" }
      : a
  );
  return maybeCollapseBatch({ ...batch, articles });
}

export function toggleBatchExpanded(state: BatchesState, batchId: string): BatchesState {
  return {
    ...state,
    batches: state.batches.map((b) =>
      b.id === batchId
        ? { ...b, collapsed: !b.collapsed, manuallyExpanded: !b.collapsed }
        : b
    ),
  };
}

export function applyRunStreamEvent(
  state: BatchesState,
  event: string,
  data: Record<string, unknown>
): BatchesState {
  switch (event) {
    case "exa_search_done": {
      const sector = String(data.sector ?? "");
      const department = String(data.department ?? "");
      const raw = Array.isArray(data.results) ? data.results : [];
      const articles: ArticleLine[] = raw
        .filter((r): r is Record<string, unknown> => typeof r === "object" && r !== null)
        .map((r) => ({
          url: String(r.url ?? ""),
          title: String(r.title ?? r.url ?? ""),
          score: typeof r.score === "number" ? r.score : undefined,
          status: "pending" as const,
        }))
        .filter((a) => a.url.length > 0)
        .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));

      const batch: ArticleBatch = {
        id: `${sector}-${department}-${Date.now()}`,
        sector,
        department,
        collapsed: false,
        manuallyExpanded: false,
        articles,
      };
      return { ...state, batches: [...state.batches, batch], scanningUrl: null };
    }

    case "exa_fetch_done": {
      const raw = Array.isArray(data.articles) ? data.articles : [];
      const fetchedUrls = new Set(
        raw
          .filter((a): a is Record<string, unknown> => typeof a === "object" && a !== null)
          .map((a) => String(a.url ?? ""))
          .filter(Boolean)
      );
      if (state.batches.length === 0) return state;
      const batches = [...state.batches];
      const last = batches.length - 1;
      batches[last] = markUnfetchedAsIgnored(batches[last], fetchedUrls);
      return { ...state, batches };
    }

    case "article_skipped":
      return updateArticleInLatestBatch(state, String(data.url ?? ""), (a) => ({
        ...a,
        status: "ignored",
        skipReason: String(data.reason ?? "skipped"),
      }));

    case "extracting": {
      const url = String(data.url ?? "");
      const next = updateArticleInLatestBatch(state, url, (a) => ({
        ...a,
        status: "scanning",
      }));
      return { ...next, scanningUrl: url };
    }

    case "llm_extract_done": {
      const url = state.scanningUrl;
      if (!url) return state;
      const isRelevant = data.is_relevant === true;
      const next = updateArticleInLatestBatch(state, url, (a) => ({
        ...a,
        status: isRelevant ? "done" : "not_relevant",
      }));
      return { ...next, scanningUrl: null };
    }

    case "article_not_relevant":
      return updateArticleInLatestBatch(state, String(data.url ?? ""), (a) => ({
        ...a,
        status: "not_relevant",
      }));

    case "run_started":
      return initialBatchesState();

    default:
      return state;
  }
}
