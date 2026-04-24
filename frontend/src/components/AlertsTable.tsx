import { ChevronRight, Mail, MailOpen } from "lucide-react";
import type { ImpactAlert } from "../api/client";
import { SeverityBadge } from "./SeverityBadge";

interface Props {
  alerts: ImpactAlert[];
  onSelect: (alert: ImpactAlert) => void;
}

function maxSeverity(alert: ImpactAlert) {
  if (alert.items.some((i) => i.severity === "high")) return "high" as const;
  if (alert.items.some((i) => i.severity === "medium")) return "medium" as const;
  return "low" as const;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function AlertsTable({ alerts, onSelect }: Props) {
  if (alerts.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-gray-300 py-16 text-center text-gray-400">
        No alerts found.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100 bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
            <th className="px-4 py-3 w-6"></th>
            <th className="px-4 py-3">Alert</th>
            <th className="px-4 py-3">Severity</th>
            <th className="px-4 py-3">Items</th>
            <th className="px-4 py-3">Date</th>
            <th className="px-4 py-3 w-8"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {alerts.map((alert) => (
            <tr
              key={alert.id}
              onClick={() => onSelect(alert)}
              className="cursor-pointer transition-colors hover:bg-blue-50"
            >
              <td className="px-4 py-3 text-gray-400">
                {alert.is_read ? <MailOpen size={14} /> : <Mail size={14} className="text-blue-500" />}
              </td>
              <td className="px-4 py-3">
                <span className={alert.is_read ? "text-gray-600" : "font-medium text-gray-900"}>
                  {alert.title}
                </span>
              </td>
              <td className="px-4 py-3">
                {alert.items.length > 0 ? (
                  <SeverityBadge severity={maxSeverity(alert)} />
                ) : (
                  <span className="text-gray-400">—</span>
                )}
              </td>
              <td className="px-4 py-3 text-gray-600">{alert.items.length}</td>
              <td className="px-4 py-3 text-gray-400">{fmtDate(alert.created_at)}</td>
              <td className="px-4 py-3 text-gray-400">
                <ChevronRight size={14} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
