"use client";

import { useEffect, useState } from "react";
import {
  FieldChange,
  getRunMerges,
  getRunSources,
  getRunSteps,
  getRunUpdates,
  ProjectMerge,
  ProjectUpdate,
  Run,
  RunStep,
  Source,
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { IsRelevantBadge } from "@/components/is-relevant-badge";
import { MergeAccordionList } from "@/components/merge-accordion-list";
import { RunStepsTimeline } from "@/components/run-steps-timeline";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Separator } from "@/components/ui/separator";
import {
  exaCategoryLabel,
  exaSearchTypeLabel,
  geographicalGranularityLabel,
} from "@/lib/run-settings-labels";

const STATUS_LABELS: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  pending: { label: "Pending", variant: "secondary" },
  in_progress: { label: "In progress", variant: "default" },
  completed: { label: "Completed", variant: "outline" },
  failed: { label: "Failed", variant: "destructive" },
};


const FIELD_LABELS: Record<string, string> = {
  name: "Name",
  company: "Company",
  surface_m2: "Area",
  delivery_date: "Delivery",
  city: "City",
  address: "Address",
  department: "Région",
  status: "Status",
  sector: "Sector",
  people: "Contacts",
};

const PROJECT_STATUS_LABELS: Record<string, string> = {
  conception: "Design",
  travaux: "Construction",
  livraison: "Delivery",
};

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-US", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-US");
}

function formatFieldValue(field: string, value: string | number | null): string {
  if (value == null || value === "") return "—";
  if (field === "status" && typeof value === "string") {
    return PROJECT_STATUS_LABELS[value] ?? value;
  }
  if (field === "surface_m2") {
    return `${value} m²`;
  }
  return String(value);
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function ChangesList({ changes }: { changes: FieldChange[] }) {
  if (changes.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">No fields changed.</p>
    );
  }

  return (
    <ul className="mt-2 space-y-1.5">
      {changes.map((change) => (
        <li key={change.field} className="text-xs">
          <span className="font-medium">{FIELD_LABELS[change.field] ?? change.field}</span>
          {": "}
          {change.old != null && change.old !== "" ? (
            <>
              <span className="text-muted-foreground line-through">
                {formatFieldValue(change.field, change.old)}
              </span>
              {" → "}
            </>
          ) : null}
          <span>{formatFieldValue(change.field, change.new)}</span>
        </li>
      ))}
    </ul>
  );
}

export function RunDetailDrawer({
  run,
  open,
  onOpenChange,
}: {
  run: Run | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [merges, setMerges] = useState<ProjectMerge[]>([]);
  const [updates, setUpdates] = useState<ProjectUpdate[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [steps, setSteps] = useState<RunStep[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !run) return;
    setLoading(true);
    Promise.all([
      getRunMerges(run.id),
      getRunUpdates(run.id),
      getRunSources(run.id),
      getRunSteps(run.id),
    ])
      .then(([mergesData, updatesData, sourcesData, stepsData]) => {
        setMerges(mergesData);
        setUpdates(updatesData);
        setSources(sourcesData);
        setSteps(stepsData);
      })
      .catch(() => {
        setMerges([]);
        setUpdates([]);
        setSources([]);
        setSteps([]);
      })
      .finally(() => setLoading(false));
  }, [open, run]);

  useEffect(() => {
    if (!open || !run || run.status !== "in_progress") return;
    const interval = setInterval(() => {
      getRunSteps(run.id).then(setSteps).catch(() => {});
    }, 800);
    return () => clearInterval(interval);
  }, [open, run]);

  if (!run) return null;

  const status = STATUS_LABELS[run.status] ?? { label: run.status, variant: "secondary" as const };

  return (
    <Drawer open={open} onOpenChange={onOpenChange} direction="right">
      <DrawerContent className="data-[vaul-drawer-direction=right]:sm:max-w-lg">
        <DrawerHeader>
          <DrawerTitle className="flex items-center gap-2">
            Run {run.id.slice(0, 8)}
            <Badge variant={status.variant}>{status.label}</Badge>
          </DrawerTitle>
          <DrawerDescription>
            {formatDateTime(run.started_at ?? run.created_at)}
            {run.finished_at ? ` → ${formatDateTime(run.finished_at)}` : ""}
          </DrawerDescription>
        </DrawerHeader>

        <div className="flex-1 overflow-y-auto px-4 pb-6 space-y-6">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <StatCard label="Articles" value={run.articles_found} />
            <StatCard label="New" value={run.projects_new} />
            <StatCard label="Updated" value={run.projects_updated} />
            <StatCard label="Rassemblements" value={run.projects_merged ?? 0} />
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <div className="rounded-lg border px-3 py-2">
              <p className="text-xs text-muted-foreground">Geographical granularity</p>
              <p className="text-sm font-medium">
                {geographicalGranularityLabel(run.geographical_granularity)}
              </p>
            </div>
            <div className="rounded-lg border px-3 py-2">
              <p className="text-xs text-muted-foreground">Exa search type</p>
              <p className="text-sm font-medium">{exaSearchTypeLabel(run.exa_search_type)}</p>
            </div>
            <div className="rounded-lg border px-3 py-2">
              <p className="text-xs text-muted-foreground">Exa category</p>
              <p className="text-sm font-medium">{exaCategoryLabel(run.exa_category)}</p>
            </div>
          </div>

          {run.error_message && (
            <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {run.error_message}
            </p>
          )}

          <section className="space-y-3">
            <h3 className="text-sm font-medium">Timeline IA</h3>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : (
              <RunStepsTimeline steps={steps} />
            )}
          </section>

          <Separator />

          <section className="space-y-3">
            <h3 className="text-sm font-medium">
              Updates ({updates.length})
            </h3>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : updates.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No project updates during this run.
              </p>
            ) : (
              <ul className="space-y-2">
                {updates.map((update) => (
                  <li key={update.id} className="rounded-md border p-3 text-sm">
                    <a
                      href={update.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-blue-600 hover:underline line-clamp-2"
                    >
                      {update.source_title || update.source_url}
                    </a>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Project: {update.project_name}
                    </p>
                    <ChangesList changes={update.changes} />
                  </li>
                ))}
              </ul>
            )}
          </section>

          <Separator />

          <section className="space-y-3">
            <h3 className="text-sm font-medium">
              Rassemblements ({merges.length})
            </h3>
            {loading ? (
              <p className="text-sm text-muted-foreground">Chargement…</p>
            ) : (
              <MergeAccordionList merges={merges} steps={steps} />
            )}
          </section>

          <Separator />

          <section className="space-y-3">
            <h3 className="text-sm font-medium">
              Analyzed articles ({sources.length})
            </h3>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : sources.length === 0 ? (
              <p className="text-sm text-muted-foreground">No articles analyzed.</p>
            ) : (
              <ul className="space-y-2">
                {sources.map((source) => (
                  <li key={source.id} className="rounded-md border p-3 text-sm">
                    <div className="flex items-start justify-between gap-2">
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-blue-600 hover:underline line-clamp-2"
                      >
                        {source.title || source.url}
                      </a>
                      <div className="shrink-0 text-right">
                        <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                          is_relevant
                        </p>
                        <IsRelevantBadge value={source.is_relevant} />
                      </div>
                    </div>
                    {source.published_at && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Published {formatDate(source.published_at)}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
