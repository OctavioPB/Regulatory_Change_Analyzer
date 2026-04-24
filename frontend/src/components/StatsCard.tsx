interface Props {
  label: string;
  value: number | string;
  sub?: string;
  icon?: never;
  accent?: "blue" | "red" | "amber" | "green";
}

export function StatsCard({ label, value, sub }: Props) {
  return (
    <div className="rounded-xl bg-white shadow-sm overflow-hidden">
      <div className="accent-bar" />
      <div className="px-5 py-5 flex flex-col items-center text-center gap-1">
        <p
          className="font-display leading-none"
          style={{ fontSize: "32px", fontWeight: 300, color: "var(--dark)" }}
        >
          {value}
        </p>
        <p className="opb-label text-opb-mid">{label}</p>
        {sub && (
          <p className="text-opb-mid" style={{ fontSize: "11px" }}>
            {sub}
          </p>
        )}
      </div>
    </div>
  );
}
