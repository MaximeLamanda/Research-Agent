"use client";

import { useEffect, useRef, useState } from "react";
import {
  applyRunStreamEvent,
  initialBatchesState,
  toggleBatchExpanded,
  type BatchesState,
} from "@/lib/run-article-batches";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface RunStreamState {
  active: boolean;
  message: string;
  stats: {
    articles_found?: number;
    projects_new?: number;
    projects_updated?: number;
    projects_merged?: number;
  } | null;
  batches: BatchesState;
}

export function useRunStream(runId: string | null, onComplete?: () => void) {
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const [state, setState] = useState<RunStreamState>({
    active: false,
    message: "",
    stats: null,
    batches: initialBatchesState(),
  });

  useEffect(() => {
    if (!runId) return;

    setState({
      active: true,
      message: "Initializing agent…",
      stats: null,
      batches: initialBatchesState(),
    });
    const source = new EventSource(`${API_URL}/api/runs/${runId}/stream`);

    function applyEvent(event: string, data: Record<string, unknown>) {
      setState((s) => ({
        ...s,
        batches: applyRunStreamEvent(s.batches, event, data),
      }));
    }

    const handlers: Record<string, (data: Record<string, unknown>) => void> = {
      run_started: (data) => {
        applyEvent("run_started", data);
        setState((s) => ({ ...s, message: "Searching for articles…" }));
      },
      searching: (data) => {
        applyEvent("searching", data);
        setState((s) => ({
          ...s,
          message: `Searching articles — ${data.sector} (dept. ${data.department})`,
        }));
      },
      extracting: (data) => {
        applyEvent("extracting", data);
        const label = (data.title as string) || (data.url as string) || "source";
        const truncated = label.length > 60 ? `${label.slice(0, 57)}…` : label;
        setState((s) => ({ ...s, message: `Analyzing source: ${truncated}` }));
      },
      llm_extract_start: (data) => {
        applyEvent("llm_extract_start", data);
        setState((s) => ({ ...s, message: "LLM — extraction en cours…" }));
      },
      llm_extract_done: (data) => {
        applyEvent("llm_extract_done", data);
        setState((s) => ({
          ...s,
          message: data.is_relevant
            ? "LLM — article pertinent détecté"
            : "LLM — article non pertinent",
        }));
      },
      article_not_relevant: (data) => {
        applyEvent("article_not_relevant", data);
        const label = (data.title as string) || "article";
        setState((s) => ({ ...s, message: `Article ignoré : ${label}` }));
      },
      article_skipped: (data) => {
        applyEvent("article_skipped", data);
      },
      exa_search_start: (data) => {
        applyEvent("exa_search_start", data);
        setState((s) => ({ ...s, message: "Recherche Exa en cours…" }));
      },
      exa_search_done: (data) => {
        applyEvent("exa_search_done", data);
      },
      exa_fetch_start: (data) => {
        applyEvent("exa_fetch_start", data);
        setState((s) => ({
          ...s,
          message: `Récupération de ${data.url_count ?? "?"} article(s)…`,
        }));
      },
      exa_fetch_done: (data) => {
        applyEvent("exa_fetch_done", data);
      },
      project_found: (data) => {
        applyEvent("project_found", data);
        setState((s) => ({
          ...s,
          message: data.is_new
            ? `Synthesis — new project: ${data.name}`
            : `Synthesis — update: ${data.name}`,
        }));
      },
      company_searching: (data) => {
        applyEvent("company_searching", data);
        setState((s) => ({
          ...s,
          message: `Recherche SIREN — ${data.company}`,
        }));
      },
      company_resolved: (data) => {
        applyEvent("company_resolved", data);
        setState((s) => ({
          ...s,
          message: `SIREN trouvé : ${data.siren}`,
        }));
      },
      company_skipped: (data) => {
        applyEvent("company_skipped", data);
        setState((s) => ({
          ...s,
          message: "SIREN non identifié",
        }));
      },
      deduplicating: (data) => {
        applyEvent("deduplicating", data);
        setState((s) => ({ ...s, message: "Consolidating duplicates…" }));
      },
      project_merged: (data) => {
        applyEvent("project_merged", data);
        setState((s) => ({
          ...s,
          message: `Merge: ${data.absorbed_name} → ${data.kept_name}`,
        }));
      },
      run_completed: (data) => {
        applyEvent("run_completed", data);
        setState({
          active: false,
          message: "",
          stats: data,
          batches: initialBatchesState(),
        });
        onCompleteRef.current?.();
        source.close();
      },
      run_failed: (data) => {
        applyEvent("run_failed", data);
        setState({
          active: false,
          message: `Error: ${data.error}`,
          stats: null,
          batches: initialBatchesState(),
        });
        source.close();
      },
    };

    for (const [event, handler] of Object.entries(handlers)) {
      source.addEventListener(event, (e) => {
        try {
          handler(JSON.parse((e as MessageEvent).data));
        } catch {
          handler({});
        }
      });
    }

    return () => source.close();
  }, [runId]);

  return {
    ...state,
    toggleBatch: (batchId: string) =>
      setState((s) => ({
        ...s,
        batches: toggleBatchExpanded(s.batches, batchId),
      })),
  };
}
