"use client";

import { type ReactNode } from "react";
import { FieldChange, ProjectMerge, RunStep } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

const METHOD_LABELS: Record<string, string> = {
  match_key: "Clé",
  fuzzy: "Fuzzy",
  siren: "SIREN",
  llm: "LLM",
  llm_cached: "LLM (cache)",
};

const FIELD_LABELS: Record<string, string> = {
  name: "Nom",
  company: "Promoteur",
  surface_m2: "Surface",
  delivery_date: "Livraison",
  city: "Ville",
  address: "Adresse",
  department: "Région",
  status: "Statut",
  sector: "Secteur",
  people: "Contacts",
};

function formatFieldValue(field: string, value: string | number | null): string {
  if (value == null || value === "") return "—";
  if (field === "surface_m2") return `${value} m²`;
  return String(value);
}

function ChangesList({ changes }: { changes: FieldChange[] }) {
  if (changes.length === 0) {
    return <p className="text-xs text-muted-foreground">Aucun champ modifié.</p>;
  }

  return (
    <ul className="mt-1.5 space-y-1">
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

function snapshotReason(merge: ProjectMerge): string | undefined {
  const raw = merge.snapshot.reason;
  return typeof raw === "string" && raw.trim() ? raw.trim() : undefined;
}

export function dedupReasonFromSteps(merge: ProjectMerge, steps: RunStep[]): string | undefined {
  const absorbed = merge.snapshot.absorbed?.name;
  const kept = merge.snapshot.kept?.name;
  if (!absorbed || !kept) return undefined;

  const names = new Set([absorbed, kept]);
  for (const step of steps) {
    if (step.step_type !== "llm_dedup_done") continue;
    const projectA =
      typeof step.data.project_a === "string" ? step.data.project_a : null;
    const projectB =
      typeof step.data.project_b === "string" ? step.data.project_b : null;
    const reason =
      typeof step.data.reason === "string" ? step.data.reason.trim() : "";
    if (!projectA || !projectB || !reason) continue;
    if (names.has(projectA) && names.has(projectB)) return reason;
  }
  return undefined;
}

export function resolveMergeReason(
  merge: ProjectMerge,
  steps: RunStep[] = [],
): string {
  const stored = snapshotReason(merge);
  if (stored) return stored;

  const fromSteps = dedupReasonFromSteps(merge, steps);
  if (fromSteps) return fromSteps;

  if (merge.method === "llm" || merge.method === "llm_cached") {
    return "Fusion validée par le LLM (raison non enregistrée)";
  }
  if (merge.score != null) {
    return `Fusion automatique (score ${Math.round(merge.score * 100)} %)`;
  }
  return "Fusion automatique";
}

function MergeAccordionDetails({
  merge,
  reason,
  footer,
}: {
  merge: ProjectMerge;
  reason: string;
  footer?: ReactNode;
}) {
  return (
    <div className="space-y-3 pt-1">
      <div className="rounded-md border bg-muted/30 px-3 py-2">
        <p className="text-xs font-medium text-muted-foreground">Raison</p>
        <p className="mt-1 text-sm leading-relaxed">{reason}</p>
      </div>

      {(merge.snapshot.absorbed?.city || merge.snapshot.kept?.city) && (
        <p className="text-xs text-muted-foreground">
          {merge.snapshot.absorbed?.city || "—"}
          {" → "}
          {merge.snapshot.kept?.city || "—"}
        </p>
      )}

      {merge.snapshot.sources_transferred &&
        merge.snapshot.sources_transferred.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground">
              Articles transférés
            </p>
            <ul className="mt-1 space-y-0.5">
              {merge.snapshot.sources_transferred.map((source) => (
                <li key={source.url}>
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-600 hover:underline line-clamp-1"
                  >
                    {source.title || source.url}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

      {merge.snapshot.changes && merge.snapshot.changes.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground">
            Champs mis à jour sur le projet conservé
          </p>
          <ChangesList changes={merge.snapshot.changes} />
        </div>
      )}

      {footer}
    </div>
  );
}

export function MergeAccordionList({
  merges,
  steps = [],
  emptyMessage = "Aucun rassemblement.",
  footerForMerge,
}: {
  merges: ProjectMerge[];
  steps?: RunStep[];
  emptyMessage?: string;
  footerForMerge?: (merge: ProjectMerge) => ReactNode;
}) {
  if (merges.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyMessage}</p>;
  }

  return (
    <Accordion type="multiple" className="w-full">
      {merges.map((merge) => {
        const absorbedName = merge.snapshot.absorbed?.name || "Projet absorbé";
        const keptName = merge.snapshot.kept?.name || "Projet conservé";
        const reason = resolveMergeReason(merge, steps);

        return (
          <AccordionItem key={merge.id} value={merge.id} className="border rounded-md px-3 mb-2">
            <AccordionTrigger className="py-3 hover:no-underline">
              <div className="flex flex-1 flex-col items-start gap-1.5 pr-2 text-left">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary">
                    {METHOD_LABELS[merge.method] || merge.method}
                  </Badge>
                  {merge.score != null && (
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {Math.round(merge.score * 100)} %
                    </span>
                  )}
                </div>
                <p className="text-sm leading-snug">
                  <span className="text-muted-foreground">{absorbedName}</span>
                  <span className="text-muted-foreground"> → </span>
                  <span className="font-medium">{keptName}</span>
                </p>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <MergeAccordionDetails
                merge={merge}
                reason={reason}
                footer={footerForMerge?.(merge)}
              />
            </AccordionContent>
          </AccordionItem>
        );
      })}
    </Accordion>
  );
}
