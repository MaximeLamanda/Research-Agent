"use client";

import { Project } from "@/lib/api";
import {
  formatDate,
  formatCountry,
  formatDepartment,
  formatArticleDates,
  formatRunIds,
  formatSurface,
  STATUS_LABELS,
} from "@/lib/project-formatters";
import { SourceAvatarGroup } from "@/components/source-avatar-group";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export function ProjectTable({
  projects,
  onProjectClick,
}: {
  projects: Project[];
  onProjectClick?: (project: Project) => void;
}) {
  return (
    <div className="rounded-lg border">
      <Table className="w-max min-w-full">
        <TableHeader>
          <TableRow>
            <TableHead className="min-w-48">Project</TableHead>
            <TableHead className="min-w-28">Run</TableHead>
            <TableHead className="min-w-40">Company</TableHead>
            <TableHead className="min-w-32">City</TableHead>
            <TableHead className="min-w-24">Country</TableHead>
            <TableHead className="min-w-36">Région</TableHead>
            <TableHead className="min-w-28">Delivery</TableHead>
            <TableHead className="min-w-28">Area (m²)</TableHead>
            <TableHead className="min-w-28">Sector</TableHead>
            <TableHead className="min-w-28">Status</TableHead>
            <TableHead className="min-w-40">Contacts</TableHead>
            <TableHead className="min-w-56">Sources</TableHead>
            <TableHead className="min-w-28">Article date</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {projects.map((project) => (
            <TableRow
              key={project.id}
              className={onProjectClick ? "cursor-pointer" : undefined}
              onClick={() => onProjectClick?.(project)}
            >
              <TableCell className="font-medium">{project.name}</TableCell>
              <TableCell className="tabular-nums font-mono text-xs">
                {formatRunIds(project.sources)}
              </TableCell>
              <TableCell>{project.company || "—"}</TableCell>
              <TableCell>{project.city || "—"}</TableCell>
              <TableCell>{formatCountry(project.country)}</TableCell>
              <TableCell>{formatDepartment(project.department, project.country)}</TableCell>
              <TableCell>{formatDate(project.delivery_date)}</TableCell>
              <TableCell className="tabular-nums">
                {formatSurface(project.surface_m2)}
              </TableCell>
              <TableCell>
                {project.sector ? <Badge variant="secondary">{project.sector}</Badge> : "—"}
              </TableCell>
              <TableCell>
                {project.status ? (
                  <Badge variant="outline">
                    {STATUS_LABELS[project.status] || project.status}
                  </Badge>
                ) : (
                  "—"
                )}
              </TableCell>
              <TableCell>
                {project.people.length > 0
                  ? project.people.map((p) => p.name).join(", ")
                  : "—"}
              </TableCell>
              <TableCell onClick={(e) => e.stopPropagation()}>
                {project.sources.length > 0 ? (
                  <SourceAvatarGroup sources={project.sources} />
                ) : (
                  "—"
                )}
              </TableCell>
              <TableCell className="tabular-nums">{formatArticleDates(project.sources)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
