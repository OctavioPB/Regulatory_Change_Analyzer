import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import { Navbar } from "./components/Navbar";
import { Footer } from "./components/Footer";
import { Dashboard } from "./pages/Dashboard";

// Route-level code splitting: each page ships in its own chunk, loaded on first visit
const page = <K extends string>(loader: () => Promise<Record<K, React.ComponentType>>, name: K) =>
  lazy(() => loader().then((m) => ({ default: m[name] })));

const Alerts = page(() => import("./pages/Alerts"), "Alerts");
const Documents = page(() => import("./pages/Documents"), "Documents");
const Reviews = page(() => import("./pages/Reviews"), "Reviews");
const AuditLog = page(() => import("./pages/AuditLog"), "AuditLog");
const Pipeline = page(() => import("./pages/Pipeline"), "Pipeline");
const Trends = page(() => import("./pages/Trends"), "Trends");
const Heatmap = page(() => import("./pages/Heatmap"), "Heatmap");
const Chat = page(() => import("./pages/Chat"), "Chat");
const Addendum = page(() => import("./pages/Addendum"), "Addendum");
const Info = page(() => import("./pages/Info"), "Info");

export default function App() {
  return (
    <div className="h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 overflow-y-auto bg-opb-light flex flex-col">
        <div className="flex-1">
          <Suspense fallback={<div className="p-6 font-body text-sm" style={{ color: "var(--mid)" }}>Loading…</div>}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/reviews" element={<Reviews />} />
              <Route path="/documents" element={<Documents />} />
              <Route path="/audit" element={<AuditLog />} />
              <Route path="/pipeline" element={<Pipeline />} />
              <Route path="/trends" element={<Trends />} />
              <Route path="/heatmap" element={<Heatmap />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/addendum" element={<Addendum />} />
              <Route path="/info" element={<Info />} />
            </Routes>
          </Suspense>
        </div>
        <Footer />
      </main>
    </div>
  );
}
