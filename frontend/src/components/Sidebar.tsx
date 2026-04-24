import { NavLink } from "react-router-dom";
import { LayoutDashboard, Bell, FileText, Shield } from "lucide-react";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/documents", label: "Documents", icon: FileText },
];

export function Sidebar() {
  return (
    <aside className="flex h-full w-56 flex-col border-r border-gray-200 bg-white">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-5 border-b border-gray-100">
        <Shield size={22} className="text-blue-600 shrink-0" />
        <span className="text-sm font-bold text-gray-900 leading-tight">
          Regulatory<br />Analyzer
        </span>
      </div>

      {/* Nav links */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-5 py-4 text-xs text-gray-400 border-t border-gray-100">
        v0.1.0
      </div>
    </aside>
  );
}
