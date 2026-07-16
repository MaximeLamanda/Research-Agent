import { describe, expect, it } from "vitest";
import {
  applyRunStreamEvent,
  articleStatusLabel,
  initialBatchesState,
  SKIP_REASON_LABELS,
} from "./run-article-batches";

describe("SKIP_REASON_LABELS", () => {
  it("labels foreign_location skip reason", () => {
    expect(SKIP_REASON_LABELS.foreign_location).toBe("hors France");
  });
});

describe("applyRunStreamEvent", () => {
  it("creates a batch from exa_search_done with articles sorted by score", () => {
    const state = applyRunStreamEvent(initialBatchesState(), "exa_search_done", {
      sector: "industriel",
      department: "69",
      results: [
        { url: "https://a.com/low", title: "Low", score: 0.3 },
        { url: "https://a.com/high", title: "High", score: 0.9 },
      ],
    });
    expect(state.batches).toHaveLength(1);
    expect(state.batches[0].articles[0].url).toBe("https://a.com/high");
    expect(state.batches[0].articles[0].status).toBe("pending");
    expect(state.batches[0].collapsed).toBe(false);
  });

  it("marks article as ignored on article_skipped", () => {
    let state = applyRunStreamEvent(initialBatchesState(), "exa_search_done", {
      sector: "industriel",
      department: "69",
      results: [{ url: "https://a.com/x", title: "X", score: 0.5 }],
    });
    state = applyRunStreamEvent(state, "article_skipped", {
      url: "https://a.com/x",
      reason: "prefiltered",
    });
    const article = state.batches[0].articles[0];
    expect(article.status).toBe("ignored");
    expect(article.skipReason).toBe("prefiltered");
    expect(articleStatusLabel(article)).toBe("préfiltré");
  });

  it("shows prefilter LLM reason on article_skipped", () => {
    let state = applyRunStreamEvent(initialBatchesState(), "exa_search_done", {
      sector: "industriel",
      department: "UKC",
      results: [{ url: "https://a.com/x", title: "Recycling plant", score: 0.5 }],
    });
    state = applyRunStreamEvent(state, "article_skipped", {
      url: "https://a.com/x",
      reason: "prefiltered",
      prefilter_reason: "Article hors sujet sans lien avec un bâtiment",
    });
    const article = state.batches[0].articles[0];
    expect(article.prefilterReason).toBe("Article hors sujet sans lien avec un bâtiment");
    expect(articleStatusLabel(article)).toBe(
      "préfiltré — Article hors sujet sans lien avec un bâtiment"
    );
  });

  it("auto-collapses batch when all articles are terminal", () => {
    let state = applyRunStreamEvent(initialBatchesState(), "exa_search_done", {
      sector: "industriel",
      department: "69",
      results: [{ url: "https://a.com/x", title: "X", score: 0.5 }],
    });
    state = applyRunStreamEvent(state, "article_skipped", {
      url: "https://a.com/x",
      reason: "known",
    });
    expect(state.batches[0].collapsed).toBe(true);
  });

  it("labels not_relevant articles", () => {
    let state = applyRunStreamEvent(initialBatchesState(), "exa_search_done", {
      sector: "industriel",
      department: "69",
      results: [{ url: "https://a.com/x", title: "X", score: 0.5 }],
    });
    state = applyRunStreamEvent(state, "extracting", { url: "https://a.com/x", title: "X" });
    state = applyRunStreamEvent(state, "llm_extract_done", { title: "X", is_relevant: false });
    const article = state.batches[0].articles[0];
    expect(article.status).toBe("not_relevant");
    expect(articleStatusLabel(article)).toBe("non pertinent");
  });

  it("transitions extracting → done via llm_extract_done on scanning article", () => {
    let state = applyRunStreamEvent(initialBatchesState(), "exa_search_done", {
      sector: "industriel",
      department: "69",
      results: [{ url: "https://a.com/x", title: "X", score: 0.5 }],
    });
    state = applyRunStreamEvent(state, "extracting", {
      url: "https://a.com/x",
      title: "X",
    });
    expect(state.batches[0].articles[0].status).toBe("scanning");
    state = applyRunStreamEvent(state, "llm_extract_done", {
      title: "X",
      is_relevant: true,
    });
    expect(state.batches[0].articles[0].status).toBe("done");
    expect(state.batches[0].collapsed).toBe(true);
  });

  it("marks unfetched articles as deferred on exa_fetch_done", () => {
    let state = applyRunStreamEvent(initialBatchesState(), "exa_search_done", {
      sector: "industriel",
      department: "69",
      results: [
        { url: "https://a.com/fetched", title: "Fetched", score: 0.9 },
        { url: "https://a.com/waiting", title: "Waiting", score: 0.5 },
      ],
    });
    state = applyRunStreamEvent(state, "exa_fetch_done", {
      articles: [{ url: "https://a.com/fetched", title: "Fetched" }],
    });
    const fetched = state.batches[0].articles.find((a) => a.url === "https://a.com/fetched");
    const waiting = state.batches[0].articles.find((a) => a.url === "https://a.com/waiting");
    expect(fetched?.status).toBe("pending");
    expect(waiting?.status).toBe("deferred");
    expect(waiting?.skipReason).toBe("deferred");
  });

  it("labels deferred skip reason", () => {
    expect(SKIP_REASON_LABELS.deferred).toBe("en attente");
  });

  it("marks article as cross_department on project_imported_cross_department", () => {
    let state = applyRunStreamEvent(initialBatchesState(), "exa_search_done", {
      sector: "industriel",
      department: "77",
      results: [{ url: "https://a.com/rhone", title: "Amazon Lyon", score: 0.9 }],
    });
    state = applyRunStreamEvent(state, "extracting", { url: "https://a.com/rhone", title: "Amazon Lyon" });
    state = applyRunStreamEvent(state, "llm_extract_done", { title: "Amazon Lyon", is_relevant: true });
    state = applyRunStreamEvent(state, "project_imported_cross_department", {
      url: "https://a.com/rhone",
      extracted_department: "69 - Rhône",
      target_department: "77 - Seine-et-Marne",
      name: "Amazon warehouse",
    });
    expect(state.batches[0].articles[0].status).toBe("cross_department");
    expect(state.batches[0].articles[0].importedDepartment).toBe("69");
  });
});
