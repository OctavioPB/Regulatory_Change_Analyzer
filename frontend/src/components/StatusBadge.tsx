import type { ApprovalStatus } from "../api/client";

const styles: Record<ApprovalStatus, string> = {
  pending: "bg-gray-100 text-gray-600 ring-gray-200",
  approved: "bg-green-100 text-green-700 ring-green-200",
  modified: "bg-blue-100 text-blue-700 ring-blue-200",
  rejected: "bg-red-100 text-red-700 ring-red-200",
};

export function StatusBadge({ status }: { status: ApprovalStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${styles[status]}`}
    >
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}
