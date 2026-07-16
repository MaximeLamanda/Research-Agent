"use client";

import { useCallback, useEffect, useState } from "react";
import { getRuns, Run } from "@/lib/api";
import { RunDetailDrawer } from "@/components/run-detail-drawer";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const STATUS_LABELS: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  pending: { label: "Pending", variant: "secondary" },
  in_progress: { label: "In progress", variant: "default" },
  completed: { label: "Completed", variant: "outline" },
  failed: { label: "Failed", variant: "destructive" },
  cancelled: { label: "Cancelled", variant: "secondary" },
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

export function RunList({ refreshKey }: { refreshKey: number }) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getRuns();
      setRuns(data);
    } catch {
      setError(
        "Unable to reach the API. Make sure the backend is running on the configured port."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  function openRun(run: Run) {
    setSelectedRun(run);
    setDrawerOpen(true);
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading runs…</p>;
  }

  if (error) {
    return <p className="text-sm text-destructive">{error}</p>;
  }

  if (runs.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No runs yet. Start a search to get started.
      </p>
    );
  }

  return (
    <>
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">{runs.length} run(s)</h2>
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Articles</TableHead>
                <TableHead className="text-right">New</TableHead>
                <TableHead className="text-right">Updated</TableHead>
                <TableHead className="text-right">Merges</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((run) => {
                const status = STATUS_LABELS[run.status] ?? {
                  label: run.status,
                  variant: "secondary" as const,
                };
                return (
                  <TableRow
                    key={run.id}
                    className="cursor-pointer"
                    onClick={() => openRun(run)}
                  >
                    <TableCell className="tabular-nums">
                      {formatDateTime(run.started_at ?? run.created_at)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={status.variant}>{status.label}</Badge>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {run.articles_found}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {run.projects_new}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {run.projects_updated}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {run.projects_merged ?? 0}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </div>

      <RunDetailDrawer
        run={selectedRun}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
      />
    </>
  );
}
