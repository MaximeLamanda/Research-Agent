"use client";

import { useCallback, useEffect, useState } from "react";
import { FileSpreadsheet } from "lucide-react";
import { DepartmentCombobox } from "@/components/department-combobox";
import { getConfig, getProjects, Project } from "@/lib/api";
import { COUNTRIES } from "@/data/countries";
import {
  exportProjectsToExcel,
  filterProjectsByCountry,
} from "@/lib/export-projects-excel";
import { ProjectDetailDrawer } from "@/components/project-detail-drawer";
import { ProjectTable } from "@/components/project-table";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

const EXPORT_COUNTRY_LABELS: Record<string, string> = {
  FR: "France",
  DE: "Allemagne",
  GB: "United Kingdom",
  IE: "Ireland",
};

function regionFilterLabel(country: string): string {
  if (country === "DE") return "Land";
  if (country === "GB") return "Région";
  if (country === "IE") return "Province";
  return "Région";
}

export function ProjectList({ refreshKey }: { refreshKey: number }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [exportCountry, setExportCountry] = useState("FR");
  const [filterCountry, setFilterCountry] = useState("FR");
  const [selectedDepartments, setSelectedDepartments] = useState<string[]>([]);

  useEffect(() => {
    getConfig()
      .then((config) => setFilterCountry(config.country || "FR"))
      .catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getProjects({
        country: filterCountry,
        ...(selectedDepartments.length > 0
          ? { departments: selectedDepartments }
          : {}),
      });
      setProjects(data);
    } catch {
      setError(
        "Unable to reach the API. Make sure the backend is running on the configured port (8001 locally)."
      );
    } finally {
      setLoading(false);
    }
  }, [selectedDepartments, filterCountry]);

  useEffect(() => {
    load();
  }, [load, refreshKey, selectedDepartments, filterCountry]);

  function handleCountryChange(country: string) {
    setFilterCountry(country);
    setSelectedDepartments([]);
  }

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

  const hasActiveFilters = selectedDepartments.length > 0;
  const filteredEmpty = projects.length === 0;

  if (filteredEmpty && !hasActiveFilters) {
    const countryLabel =
      COUNTRIES.find((country) => country.code === filterCountry)?.label ??
      filterCountry;
    return (
      <>
        <ProjectFilters
          filterCountry={filterCountry}
          selectedDepartments={selectedDepartments}
          onCountryChange={handleCountryChange}
          onDepartmentsChange={setSelectedDepartments}
        />
        <p className="text-sm text-muted-foreground">
          Aucun projet pour {countryLabel}. Configurez les régions et lancez une
          recherche.
        </p>
      </>
    );
  }

  return (
    <>
      <div className="space-y-4">
        <ProjectFilters
          filterCountry={filterCountry}
          selectedDepartments={selectedDepartments}
          onCountryChange={handleCountryChange}
          onDepartmentsChange={setSelectedDepartments}
        />

        {filteredEmpty ? (
          <p className="text-sm text-muted-foreground">
            Aucun projet pour les régions sélectionnées.
          </p>
        ) : (
          <>
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
                        <span>
                          {EXPORT_COUNTRY_LABELS[country.code] ?? country.label}
                        </span>
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
          </>
        )}
      </div>

      <ProjectDetailDrawer
        project={selectedProject}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
      />
    </>
  );
}

function ProjectFilters({
  filterCountry,
  selectedDepartments,
  onCountryChange,
  onDepartmentsChange,
}: {
  filterCountry: string;
  selectedDepartments: string[];
  onCountryChange: (country: string) => void;
  onDepartmentsChange: (departments: string[]) => void;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="space-y-2">
        <Label htmlFor="project-filter-country">Pays</Label>
        <Select value={filterCountry} onValueChange={(value) => value && onCountryChange(value)}>
          <SelectTrigger id="project-filter-country" className="w-full">
            <SelectValue placeholder="Choisir un pays" />
          </SelectTrigger>
          <SelectContent side="bottom" align="start" alignItemWithTrigger={false}>
            {COUNTRIES.map((country) => (
              <SelectItem key={country.code} value={country.code}>
                {country.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-2">
        <Label htmlFor="project-filter-region">{regionFilterLabel(filterCountry)}</Label>
        <DepartmentCombobox
          country={filterCountry}
          value={selectedDepartments}
          onChange={onDepartmentsChange}
        />
      </div>
    </div>
  );
}
