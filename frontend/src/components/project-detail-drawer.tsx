"use client";

import { type ReactNode, useEffect, useState } from "react";
import { getProjectMerges, Project, ProjectMerge } from "@/lib/api";
import { getCountryLabel } from "@/data/countries";
import { getRegionLabel } from "@/data/regions";
import { MergeAccordionList } from "@/components/merge-accordion-list";
import { SourceAvatarGroup } from "@/components/source-avatar-group";
import { IsRelevantBadge } from "@/components/is-relevant-badge";
import { Badge } from "@/components/ui/badge";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Separator } from "@/components/ui/separator";

const STATUS_LABELS: Record<string, string> = {
  conception: "Design",
  travaux: "Construction",
  livraison: "Delivery",
};

function formatDate(value: string | null): string {
  if (!value) return "—";
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (match) {
    const [, year, month, day] = match;
    return new Date(Number(year), Number(month) - 1, Number(day)).toLocaleDateString("en-US");
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-US");
}

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

function formatSurface(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value).toLocaleString("en-US")} m²`;
}

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="grid grid-cols-[8rem_1fr] gap-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span>{value}</span>
    </div>
  );
}

export function ProjectDetailDrawer({
  project,
  open,
  onOpenChange,
}: {
  project: Project | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [merges, setMerges] = useState<ProjectMerge[]>([]);
  const [mergesLoading, setMergesLoading] = useState(false);

  useEffect(() => {
    if (!open || !project) return;
    setMergesLoading(true);
    getProjectMerges(project.id)
      .then(setMerges)
      .catch(() => setMerges([]))
      .finally(() => setMergesLoading(false));
  }, [open, project?.id]);

  if (!project) return null;

  const incomingMerges = merges.filter((merge) => merge.kept_project_id === project.id);
  const outgoingMerges = merges.filter((merge) => merge.absorbed_project_id === project.id);
  const rassemblements = [...incomingMerges, ...outgoingMerges];

  return (
    <Drawer open={open} onOpenChange={onOpenChange} direction="right">
      <DrawerContent className="data-[vaul-drawer-direction=right]:sm:max-w-lg">
        <DrawerHeader>
          <DrawerTitle>{project.name}</DrawerTitle>
          <DrawerDescription>
            {[project.company, project.city].filter(Boolean).join(" · ") || "Construction project"}
          </DrawerDescription>
        </DrawerHeader>

        <div className="flex-1 space-y-6 overflow-y-auto px-4 pb-6">
          {project.lead_pitch && (
            <section className="rounded-lg border bg-muted/40 px-3 py-3">
              <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Why this lead?
              </h3>
              <p className="mt-2 text-sm leading-relaxed">{project.lead_pitch}</p>
            </section>
          )}

          <section className="space-y-2">
            <h3 className="text-sm font-medium">Details</h3>
            <div className="space-y-2 rounded-lg border p-3">
              <DetailRow label="Company" value={project.company || "—"} />
              {project.siren && (
                <DetailRow
                  label="SIREN"
                  value={
                    <>
                      {project.siren}
                      {project.company_legal_name ? ` — ${project.company_legal_name}` : ""}
                    </>
                  }
                />
              )}
              {project.naf_code && (
                <DetailRow label="NAF" value={project.naf_code} />
              )}
              <DetailRow label="City" value={project.city || "—"} />
              <DetailRow label="Country" value={getCountryLabel(project.country)} />
              <DetailRow
                label={
                  project.country === "DE"
                    ? "Land"
                    : project.country === "GB"
                      ? "Region"
                      : project.country === "IE"
                        ? "Province"
                        : "Région"
                }
                value={
                  project.department
                    ? getRegionLabel(project.department, project.country || "FR")
                    : "—"
                }
              />
              <DetailRow label="Address" value={project.address || "—"} />
              <DetailRow label="Area" value={formatSurface(project.surface_m2)} />
              <DetailRow label="Delivery" value={formatDate(project.delivery_date)} />
              <DetailRow
                label="Sector"
                value={
                  project.sector ? (
                    <Badge variant="secondary">{project.sector}</Badge>
                  ) : (
                    "—"
                  )
                }
              />
              <DetailRow
                label="Status"
                value={
                  project.status ? (
                    <Badge variant="outline">
                      {STATUS_LABELS[project.status] || project.status}
                    </Badge>
                  ) : (
                    "—"
                  )
                }
              />
              <DetailRow label="First detected" value={formatDate(project.first_seen_at)} />
              <DetailRow label="Last updated" value={formatDateTime(project.last_updated_at)} />
            </div>
          </section>

          {project.people.length > 0 && (
            <section className="space-y-2">
              <h3 className="text-sm font-medium">
                Contacts ({project.people.length})
              </h3>
              <ul className="space-y-2">
                {project.people.map((person) => (
                  <li key={person.name} className="rounded-md border p-3 text-sm">
                    <p className="font-medium">{person.name}</p>
                    {(person.role || person.company) && (
                      <p className="text-muted-foreground">
                        {[person.role, person.company].filter(Boolean).join(" · ")}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <Separator />

          <section className="space-y-2">
            <h3 className="text-sm font-medium">
              Rassemblements ({rassemblements.length})
            </h3>
            {mergesLoading ? (
              <p className="text-sm text-muted-foreground">Chargement…</p>
            ) : (
              <MergeAccordionList
                merges={rassemblements}
                emptyMessage="Aucun rassemblement enregistré pour ce projet."
                footerForMerge={(merge) =>
                  merge.run_id ? (
                    <p className="text-xs text-muted-foreground">
                      Run {merge.run_id.slice(0, 8)}
                      {merge.created_at
                        ? ` · ${new Date(merge.created_at).toLocaleDateString("fr-FR")}`
                        : ""}
                    </p>
                  ) : null
                }
              />
            )}
          </section>

          <Separator />

          <section className="space-y-2">
            <h3 className="text-sm font-medium">
              Sources ({project.sources.length})
            </h3>
            {project.sources.length === 0 ? (
              <p className="text-sm text-muted-foreground">No sources.</p>
            ) : (
              <div className="space-y-3">
                <SourceAvatarGroup sources={project.sources} maxVisible={6} />
                <ul className="space-y-2">
                  {project.sources.map((source) => (
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
              </div>
            )}
          </section>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
