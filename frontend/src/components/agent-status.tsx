"use client";

import { ShiningText } from "@/components/ui/shining-text";
import type { RunStreamState } from "@/hooks/use-run-stream";

interface AgentStatusProps {
  active: boolean;
  message: string;
  stats: RunStreamState["stats"];
}

export function AgentStatus({ active, message, stats }: AgentStatusProps) {
  if (!active && !stats) return null;

  return (
    <div className="flex w-full max-w-sm flex-col items-center gap-2 text-center">
      {active && message && <ShiningText text={message} />}
      {stats && (
        <p className="text-xs text-muted-foreground">
          {stats.articles_found} articles · {stats.projects_new} new ·{" "}
          {stats.projects_updated} updated
          {typeof stats.projects_merged === "number" && stats.projects_merged > 0
            ? ` · ${stats.projects_merged} merged`
            : ""}
        </p>
      )}
    </div>
  );
}
