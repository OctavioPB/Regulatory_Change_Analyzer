import { ChevronRight, Mail, MailOpen } from "lucide-react";
import type { ImpactAlert } from "../api/client";
import { SeverityBadge } from "./SeverityBadge";

interface Props {
  alerts: ImpactAlert[];
  onSelect: (alert: ImpactAlert) => void;
}

function maxSeverity(alert: ImpactAlert) {
  if (alert.items.some((i) => i.severity === "high"))   return "high"   as const;
  if (alert.items.some((i) => i.severity === "medium")) return "medium" as const;
  return "low" as const;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric",
  });
}

export function AlertsTable({ alerts, onSelect }: Props) {
  if (alerts.length === 0) {
    return (
      <div
        className="rounded-xl py-16 text-center font-body"
        style={{
          border: "1px dashed var(--primary-30)",
          color: "var(--mid)",
          fontSize: "14px",
        }}
      >
        No alerts found.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl bg-white shadow-sm" style={{ border: "1px solid var(--primary-10)" }}>
      <table className="w-full" style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "var(--primary)" }}>
            <th className="px-4 py-3 w-6" />
            {["Alert", "Severity", "Items", "Date", ""].map((h) => (
              <th
                key={h}
                className="px-4 py-3 text-left text-white"
                style={{ fontSize: "10px", letterSpacing: "2px", textTransform: "uppercase", fontFamily: "var(--fb)", fontWeight: 500 }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {alerts.map((alert, idx) => (
            <tr
              key={alert.id}
              onClick={() => onSelect(alert)}
              className="cursor-pointer transition-colors"
              style={{
                background: idx % 2 === 0 ? "var(--white)" : "var(--primary-10)",
                borderBottom: "1px solid var(--primary-10)",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#dce9f6")}
              onMouseLeave={(e) => (e.currentTarget.style.background = idx % 2 === 0 ? "var(--white)" : "var(--primary-10)")}
            >
              <td className="px-4 py-3" style={{ color: "var(--mid)" }}>
                {alert.is_read
                  ? <MailOpen size={13} />
                  : <Mail size={13} style={{ color: "var(--primary)" }} />}
              </td>
              <td className="px-4 py-3" style={{ fontFamily: "var(--fb)", fontSize: "14px" }}>
                <span style={{ color: alert.is_read ? "var(--mid)" : "var(--dark)", fontWeight: alert.is_read ? 400 : 500 }}>
                  {alert.title}
                </span>
              </td>
              <td className="px-4 py-3">
                {alert.items.length > 0
                  ? <SeverityBadge severity={maxSeverity(alert)} />
                  : <span style={{ color: "var(--mid)" }}>—</span>}
              </td>
              <td className="px-4 py-3" style={{ color: "var(--mid)", fontFamily: "var(--fb)", fontSize: "14px" }}>
                {alert.items.length}
              </td>
              <td className="px-4 py-3" style={{ color: "var(--mid)", fontFamily: "var(--fb)", fontSize: "12px" }}>
                {fmtDate(alert.created_at)}
              </td>
              <td className="px-4 py-3" style={{ color: "var(--primary-30)" }}>
                <ChevronRight size={14} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
