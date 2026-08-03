import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from "react-router-dom";
import VeilleActualites    from "./pages/VeilleActualites";
import VeilleReglementaire from "./pages/VeilleReglementaire";

const Y = "#FFE600", D = "#2E2E38";
const FONT = "Barlow,system-ui,sans-serif";

const NAV = [
  { to: "/actualites",    label: "Veille d'actualités"  },
  { to: "/reglementaire", label: "Veille réglementaire" },
];

function Navbar() {
  const nav = useNavigate();
  const loc = useLocation();
  return (
    <nav style={{
      position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
      height: 64, background: D, display: "flex", alignItems: "center",
      padding: "0 32px", gap: 32,
      boxShadow: "0 1px 0 rgba(255,255,255,.08)",
      fontFamily: FONT,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginRight: 24 }}>
        <div style={{ width: 4, height: 20, background: Y, borderRadius: 2 }}/>
        <span style={{ fontSize: 14, fontWeight: 800, color: "white", letterSpacing: "-0.3px" }}>
          Baromètre&nbsp;<span style={{ color: Y }}>Assurance TN</span>
        </span>
      </div>
      {NAV.map(m => {
        const active = loc.pathname === m.to;
        return (
          <button key={m.to} onClick={() => nav(m.to)} style={{
            background: "none", border: "none", cursor: "pointer",
            fontSize: 13, fontWeight: active ? 700 : 400,
            color: active ? Y : "rgba(255,255,255,.65)",
            borderBottom: `3px solid ${active ? Y : "transparent"}`,
            borderTop: "3px solid transparent",
            padding: "0 4px", height: 64,
            transition: "all .15s", fontFamily: FONT,
          }}>
            {m.label}
          </button>
        );
      })}
    </nav>
  );
}

function Shell() {
  return (
    <div style={{ minHeight: "100vh", background: "#F8F9FA" }}>
      <Navbar />
      <div style={{ paddingTop: 64 }}>
        <Routes>
          <Route path="/"              element={<Navigate to="/actualites" replace />} />
          <Route path="/actualites"    element={<VeilleActualites />} />
          <Route path="/reglementaire" element={<VeilleReglementaire />} />
        </Routes>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  );
}
