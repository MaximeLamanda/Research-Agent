"use client";

import { useEffect, useState } from "react";
import { getProjectMerges, Project, ProjectMerge } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

const METHOD_LABELS: Record<string, string> = {
  match_key: "Key",
  fuzzy: "Fuzzy",
  siren: "SIREN",
  llm: "LLM",
  llm_cached: "LLM (cache)",
};

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-US");
}

export function MergeHistoryDialog({ project }: { project: Project }) {
  const [merges, setMerges] = useState<ProjectMerge[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    getProjectMerges(project.id)
      .then(setMerges)
      .catch(() => setMerges([]))
      .finally(() => setLoading(false));
  }, [open, project.id]);

  const incomingMerges = merges.filter((merge) => merge.kept_project_id === project.id);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        className="inline-flex h-7 items-center rounded-md px-2 text-xs hover:bg-muted"
      >
        Merges
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Merge history — {project.name}</DialogTitle>
        </DialogHeader>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : incomingMerges.length === 0 ? (
          <p className="text-sm text-muted-foreground">No merges recorded.</p>
        ) : (
          <ul className="space-y-3">
            {incomingMerges.map((merge) => (
              <li key={merge.id} className="rounded-md border p-3 text-sm">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">
                    {METHOD_LABELS[merge.method] || merge.method}
                  </Badge>
                  {merge.score != null && (
                    <span className="text-muted-foreground">
                      score {Math.round(merge.score * 100)}%
                    </span>
                  )}
                </div>
                <p className="mt-2 font-medium">
                  {merge.snapshot.absorbed?.name || "Absorbed project"}
                </p>
                <p className="text-muted-foreground">
                  {formatDate(merge.created_at)}
                  {merge.run_id ? ` · run ${merge.run_id.slice(0, 8)}` : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}
