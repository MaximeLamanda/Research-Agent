"use client";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  sectorLabel,
  type ArticleBatch,
  type ArticleLine,
  type BatchesState,
} from "@/lib/run-article-batches";
import { BouncingDots } from "@/components/ui/bouncing-dots";
import { Check, Circle, Minus } from "lucide-react";

function StatusIcon({ article }: { article: ArticleLine }) {
  switch (article.status) {
    case "scanning":
      return (
        <span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center">
          <BouncingDots
            dots={3}
            bounceHeight={3}
            label="Analyse en cours"
            containerClassName="gap-px"
            dotClassName="h-1 w-1 bg-violet-500"
          />
        </span>
      );
    case "done":
      return <Check className="h-3.5 w-3.5 shrink-0 text-emerald-500" />;
    case "ignored":
      return <Minus className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />;
    case "not_relevant":
      return <Check className="h-3.5 w-3.5 shrink-0 text-orange-400" />;
    default:
      return <Circle className="h-3.5 w-3.5 shrink-0 text-muted-foreground/40" />;
  }
}

function ArticleRow({ article }: { article: ArticleLine }) {
  const muted = article.status === "ignored";
  return (
    <li
      className={`flex items-center gap-2 py-1 text-xs ${muted ? "text-muted-foreground" : ""}`}
    >
      <StatusIcon article={article} />
      <a
        href={article.url}
        target="_blank"
        rel="noopener noreferrer"
        className={`min-w-0 flex-1 truncate hover:underline ${muted ? "line-through" : "text-foreground"}`}
      >
        {article.title}
      </a>
      {article.score != null && (
        <span className="shrink-0 tabular-nums text-[10px] text-muted-foreground">
          {article.score.toFixed(2)}
        </span>
      )}
      {article.status === "ignored" && (
        <span className="shrink-0 text-[10px] text-muted-foreground">ignoré</span>
      )}
    </li>
  );
}

function BatchBlock({
  batch,
  onToggle,
}: {
  batch: ArticleBatch;
  onToggle: () => void;
}) {
  const doneCount = batch.articles.filter((a) =>
    ["done", "ignored", "not_relevant"].includes(a.status)
  ).length;

  return (
    <Accordion
      type="single"
      collapsible
      value={batch.collapsed ? "" : batch.id}
      onValueChange={() => onToggle()}
    >
      <AccordionItem value={batch.id} className="border rounded-lg px-3">
        <AccordionTrigger className="py-2 text-xs hover:no-underline">
          <span className="font-medium">
            {sectorLabel(batch.sector)} · {batch.department}
          </span>
          <span className="ml-2 text-muted-foreground">
            {doneCount}/{batch.articles.length}
          </span>
        </AccordionTrigger>
        <AccordionContent className="pb-2">
          <ul className="space-y-0.5">
            {batch.articles.map((article) => (
              <ArticleRow key={article.url} article={article} />
            ))}
          </ul>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

export function RunArticleBatches({
  batches,
  onToggleBatch,
}: {
  batches: BatchesState;
  onToggleBatch: (batchId: string) => void;
}) {
  if (batches.batches.length === 0) return null;

  return (
    <div className="flex w-full max-w-sm flex-col gap-2">
      {batches.batches.map((batch) => (
        <BatchBlock
          key={batch.id}
          batch={batch}
          onToggle={() => onToggleBatch(batch.id)}
        />
      ))}
    </div>
  );
}
