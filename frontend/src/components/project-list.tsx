"use client";

import { useCallback, useEffect, useState } from "react";
import { FileSpreadsheet } from "lucide-react";
import { getProjects, Project } from "@/lib/api";
import { COUNTRIES } from "@/data/countries";
import {
  exportProjectsToExcel,
  filterProjectsByCountry,
} from "@/lib/export-projects-excel";
import { ProjectDetailDrawer } from "@/components/project-detail-drawer";
import { ProjectTable } from "@/components/project-table";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

const EXPORT_COUNTRY_LABELS: Record<string, string> = {
  FR: "France",
  DE: "Allemagne",
};

export function ProjectList({ refreshKey }: { refreshKey: number }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [exportCountry, setExportCountry] = useState("FR");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getProjects();
      setProjects(data);
    } catch {
      setError(
        "Unable to reach the API. Make sure the backend is running on the configured port (8001 locally)."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  function openProject(project: Project) {
    setSelectedProject(project);
    setDrawerOpen(true);
  }

  const exportCount = filterProjectsByCountry(projects, exportCountry).length;

  async function handleExport() {
    setExporting(true);
    try {
      await exportProjectsToExcel(projects, exportCountry);
      setExportOpen(false);
    } finally {
      setExporting(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading projects…</p>;
  }

  if (error) {
    return <p className="text-sm text-destructive">{error}</p>;
  }

  if (projects.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No projects yet. Configure regions and start a search.
      </p>
    );
  }

  return (
    <>
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">{projects.length} project(s)</h2>
          <Popover open={exportOpen} onOpenChange={setExportOpen}>
            <PopoverTrigger
              render={
                <Button
                  variant="outline"
                  size="icon-sm"
                  aria-label="Export to Excel"
                />
              }
            >
              <FileSpreadsheet />
            </PopoverTrigger>
            <PopoverContent align="end" className="w-64">
              <PopoverHeader>
                <PopoverTitle>Export Excel</PopoverTitle>
                <PopoverDescription>
                  Sélectionnez la région à inclure dans l&apos;export.
                </PopoverDescription>
              </PopoverHeader>
              <div className="flex flex-col gap-1.5">
                {COUNTRIES.map((country) => (
                  <button
                    key={country.code}
                    type="button"
                    onClick={() => setExportCountry(country.code)}
                    className={cn(
                      "flex items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors",
                      exportCountry === country.code
                        ? "border-primary bg-primary/5 font-medium"
                        : "border-transparent hover:bg-muted"
                    )}
                  >
                    <span>{EXPORT_COUNTRY_LABELS[country.code] ?? country.label}</span>
                    <span className="text-xs text-muted-foreground">
                      {filterProjectsByCountry(projects, country.code).length}
                    </span>
                  </button>
                ))}
              </div>
              <Button
                className="w-full"
                size="sm"
                onClick={handleExport}
                disabled={exporting || exportCount === 0}
              >
                {exporting
                  ? "Export en cours…"
                  : `Exporter (${exportCount} projet${exportCount > 1 ? "s" : ""})`}
              </Button>
            </PopoverContent>
          </Popover>
        </div>
        <ProjectTable projects={projects} onProjectClick={openProject} />
      </div>

      <ProjectDetailDrawer
        project={selectedProject}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
      />
    </>
  );
}
