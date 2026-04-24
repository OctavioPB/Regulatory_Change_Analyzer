import { LucideIcon } from "lucide-react";

interface Props {
  label: string;
  value: number | string;
  sub?: string;
  icon: LucideIcon;
  accent?: "blue" | "red" | "amber" | "green";
}

const accents = {
  blue: "bg-blue-50 text-blue-600",
  red: "bg-red-50 text-red-600",
  amber: "bg-amber-50 text-amber-600",
  green: "bg-green-50 text-green-600",
};

export function StatsCard({ label, value, sub, icon: Icon, accent = "blue" }: Props) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">{label}</p>
          <p className="mt-1 text-3xl font-bold text-gray-900">{value}</p>
          {sub && <p className="mt-1 text-xs text-gray-400">{sub}</p>}
        </div>
        <span className={`rounded-lg p-2 ${accents[accent]}`}>
          <Icon size={22} />
        </span>
      </div>
    </div>
  );
}
