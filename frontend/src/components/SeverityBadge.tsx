import type { Severity } from "../api/client";

const styles: Record<Severity, { bg: string; text: string; dot: string }> = {
  high:   { bg: "#FDEAEA", text: "#7A1020", dot: "#E03448" },
  medium: { bg: "#FEF0E6", text: "#7A3800", dot: "#F07020" },
  low:    { bg: "#E0F7EF", text: "#0D5C3A", dot: "#27B97C" },
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  const s = styles[severity];
  return (
    <span
      className="opb-badge"
      style={{ background: s.bg, color: s.text }}
    >
      <span className="opb-badge-dot" style={{ background: s.dot }} />
      {severity.toUpperCase()}
    </span>
  );
}
