import { NavLink } from "react-router-dom";
import { LayoutDashboard, Bell, ClipboardCheck, FileText, ShieldCheck, Play, TrendingUp, Flame } from "lucide-react";

const nav = [
  { to: "/",         label: "Dashboard",   icon: LayoutDashboard },
  { to: "/alerts",   label: "Alerts",      icon: Bell },
  { to: "/reviews",  label: "Reviews",     icon: ClipboardCheck },
  { to: "/documents",label: "Documents",   icon: FileText },
  { to: "/audit",    label: "Audit Trail", icon: ShieldCheck },
  { to: "/heatmap",  label: "Heatmap",     icon: Flame },
  { to: "/trends",   label: "Trends",      icon: TrendingUp },
  { to: "/pipeline", label: "Pipeline",    icon: Play },
];

export function Navbar() {
  return (
    <nav
      className="h-[52px] sticky top-0 z-40 flex items-center justify-between px-6 shrink-0"
      style={{
        background: "rgba(0,51,102,.97)",
        backdropFilter: "blur(12px)",
        borderBottom: "1px solid rgba(255,255,255,.08)",
      }}
    >
      {/* Left: monogram + nav links */}
      <div className="flex items-center gap-7">
        <span
          className="leading-none select-none"
          style={{ fontFamily: "'Fraunces', Georgia, serif", fontSize: "20px", fontWeight: 300 }}
        >
          <span style={{ color: "#ffffff" }}>O</span>
          <em style={{ color: "var(--gold-light)", fontStyle: "italic" }}>PB</em>
        </span>

        <div className="flex items-center">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              style={({ isActive }) =>
                isActive ? { color: "var(--gold)" } : undefined
              }
              className={({ isActive }) =>
                `flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium tracking-wide transition-colors border-b-2 ${
                  isActive
                    ? "border-gold"
                    : "text-white/50 border-transparent hover:text-white/80"
                }`
              }
            >
              <Icon size={12} strokeWidth={2} />
              {label}
            </NavLink>
          ))}
        </div>
      </div>

      {/* Right: app title */}
      <span
        className="text-white/40 hidden sm:block"
        style={{ fontSize: "9px", letterSpacing: "3px", textTransform: "uppercase" }}
      >
        Regulatory Change Analyzer
      </span>
    </nav>
  );
}
