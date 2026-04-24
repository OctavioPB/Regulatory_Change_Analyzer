import type { ApprovalStatus } from "../api/client";

const styles: Record<ApprovalStatus, { bg: string; text: string; dot: string }> = {
  pending:  { bg: "#FEF0E6", text: "#7A3800", dot: "#F07020" },
  approved: { bg: "#E0F7EF", text: "#0D5C3A", dot: "#27B97C" },
  modified: { bg: "#F0EBF9", text: "#3D1F70", dot: "#7C4DBD" },
  rejected: { bg: "#FDEAEA", text: "#7A1020", dot: "#E03448" },
};

const labels: Record<ApprovalStatus, string> = {
  pending:  "Pending",
  approved: "Approved",
  modified: "Modified",
  rejected: "Rejected",
};

export function StatusBadge({ status }: { status: ApprovalStatus }) {
  const s = styles[status];
  return (
    <span
      className="opb-badge"
      style={{ background: s.bg, color: s.text }}
    >
      <span className="opb-badge-dot" style={{ background: s.dot }} />
      {labels[status]}
    </span>
  );
}
