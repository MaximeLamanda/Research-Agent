import { describe, expect, it } from "vitest";
import {
  applyRunStreamEvent,
  initialBatchesState,
  type ArticleBatch,
} from "./run-article-batches";

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
      reason: "known",
    });
    expect(state.batches[0].articles[0].status).toBe("ignored");
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

  it("overrides done status to ignored on wrong_department skip", () => {
    let state = applyRunStreamEvent(initialBatchesState(), "exa_search_done", {
      sector: "industriel",
      department: "77",
      results: [{ url: "https://a.com/rhone", title: "Amazon Lyon", score: 0.9 }],
    });
    state = applyRunStreamEvent(state, "extracting", {
      url: "https://a.com/rhone",
      title: "Amazon Lyon",
    });
    state = applyRunStreamEvent(state, "llm_extract_done", {
      title: "Amazon Lyon",
      is_relevant: true,
    });
    expect(state.batches[0].articles[0].status).toBe("done");

    state = applyRunStreamEvent(state, "article_skipped", {
      url: "https://a.com/rhone",
      reason: "wrong_department",
      target_department: "77 - Seine-et-Marne",
      extracted_department: "69 - Rhône",
    });
    expect(state.batches[0].articles[0].status).toBe("ignored");
    expect(state.batches[0].articles[0].skipReason).toBe("wrong_department");
  });
});
