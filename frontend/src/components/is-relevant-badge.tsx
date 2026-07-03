import { Badge } from "@/components/ui/badge";

export function IsRelevantBadge({ value }: { value: boolean | null | undefined }) {
  if (value == null) {
    return <span className="text-muted-foreground">—</span>;
  }
  return (
    <Badge variant={value ? "default" : "secondary"} className="font-mono text-xs">
      {value ? "true" : "false"}
    </Badge>
  );
}
