import { Routes, Route } from "react-router-dom";
import { Navbar } from "./components/Navbar";
import { Footer } from "./components/Footer";
import { Dashboard } from "./pages/Dashboard";
import { Alerts } from "./pages/Alerts";
import { Documents } from "./pages/Documents";
import { Reviews } from "./pages/Reviews";
import { AuditLog } from "./pages/AuditLog";
import { Pipeline } from "./pages/Pipeline";
import { Trends } from "./pages/Trends";

export default function App() {
  return (
    <div className="h-screen flex flex-col">
      <Navbar />
      <main className="flex-1 overflow-y-auto bg-opb-light flex flex-col">
        <div className="flex-1">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/reviews" element={<Reviews />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/audit" element={<AuditLog />} />
            <Route path="/pipeline" element={<Pipeline />} />
            <Route path="/trends" element={<Trends />} />
          </Routes>
        </div>
        <Footer />
      </main>
    </div>
  );
}
