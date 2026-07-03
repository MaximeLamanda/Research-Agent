"use client";

import { Project } from "@/lib/api";
import { SourceAvatarGroup } from "@/components/source-avatar-group";
import { Badge, Card } from "@/components/ui/card";

const STATUS_LABELS: Record<string, string> = {
  conception: "Design",
  travaux: "Construction",
  livraison: "Delivery",
};

export function ProjectCard({ project }: { project: Project }) {
  return (
    <Card>
      <div className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="font-semibold">{project.name}</h3>
            <p className="text-sm text-muted-foreground">
              {[project.city, project.department && `(${project.department})`]
                .filter(Boolean)
                .join(" ")}
            </p>
          </div>
          <div className="flex flex-wrap gap-1">
            {project.sector && <Badge>{project.sector}</Badge>}
            {project.status && <Badge>{STATUS_LABELS[project.status] || project.status}</Badge>}
          </div>
        </div>

        <div className="grid gap-1 text-sm">
          {project.company && <p>Company: {project.company}</p>}
          {project.surface_m2 && <p>Area: {project.surface_m2} m²</p>}
          {project.delivery_date && <p>Delivery: {project.delivery_date}</p>}
          {project.address && <p>Address: {project.address}</p>}
        </div>

        {project.people.length > 0 && (
          <div className="space-y-1 border-t border-border pt-3">
            {project.people.map((person) => (
              <p key={person.name} className="text-sm">
                {person.name}
                {person.role && ` — ${person.role}`}
                {person.company && ` · ${person.company}`}
              </p>
            ))}
          </div>
        )}

        {project.sources.length > 0 && (
          <div className="space-y-2 border-t border-border pt-3">
            <p className="text-xs font-medium text-muted-foreground">
              Sources ({project.sources.length})
            </p>
            <SourceAvatarGroup sources={project.sources} />
          </div>
        )}
      </div>
    </Card>
  );
}
