import type { Severity } from "../api/client";

const styles: Record<Severity, string> = {
  high: "bg-red-100 text-red-700 ring-red-200",
  medium: "bg-amber-100 text-amber-700 ring-amber-200",
  low: "bg-green-100 text-green-700 ring-green-200",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${styles[severity]}`}
    >
      {severity.toUpperCase()}
    </span>
  );
}
