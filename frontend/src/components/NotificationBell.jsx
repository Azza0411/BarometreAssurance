import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

const Y = "#FFE600", D = "#2E2E38";
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";

const GRAVITE_COLOR = { critique: "#EF4444", avertissement: "#F59E0B", info: "#3A6EA8" };

function timeAgo(iso) {
  if (!iso) return "";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "à l'instant";
  if (mins < 60) return `il y a ${mins} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `il y a ${hours} h`;
  return `il y a ${Math.floor(hours / 24)} j`;
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [count, setCount] = useState(0);
  const [notifs, setNotifs] = useState([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef(null);
  const nav = useNavigate();

  const fetchCount = () => {
    fetch(`${API}/api/notifications/unread-count`)
      .then(r => r.json()).then(d => setCount(d.count || 0)).catch(() => {});
  };

  useEffect(() => {
    fetchCount();
    const id = setInterval(fetchCount, 60000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    function handler(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const toggleOpen = () => {
    const next = !open;
    setOpen(next);
    if (next) {
      setLoading(true);
      fetch(`${API}/api/notifications`)
        .then(r => r.json()).then(d => { setNotifs(d); setLoading(false); })
        .catch(() => setLoading(false));
    }
  };

  const onClickNotif = (n) => {
    if (!n.lu) {
      fetch(`${API}/api/notifications/${n.id}/read`, { method: "POST" }).catch(() => {});
      setNotifs(prev => prev.map(x => x.id === n.id ? { ...x, lu: true } : x));
      setCount(c => Math.max(0, c - 1));
    }
    setOpen(false);
    if (n.lien) nav(n.lien);
  };

  const markAllRead = () => {
    fetch(`${API}/api/notifications/read-all`, { method: "POST" }).catch(() => {});
    setNotifs(prev => prev.map(x => ({ ...x, lu: true })));
    setCount(0);
  };

  return (
    <div ref={ref} style={{ position: "relative", display: "flex", alignItems: "center", height: "100%" }}>
      <button onClick={toggleOpen} style={{
        background: "none", border: "none", cursor: "pointer", position: "relative",
        padding: "0 14px", height: "100%", display: "flex", alignItems: "center",
      }}>
        <svg viewBox="0 0 20 20" fill="none" width="16" height="16">
          <path d="M10 2.5c-2.5 0-4 1.9-4 4.3v2.6c0 .6-.2 1.1-.6 1.6l-.9 1c-.6.6-.2 1.6.6 1.6h9.8c.8 0 1.2-1 .6-1.6l-.9-1c-.4-.5-.6-1-.6-1.6V6.8c0-2.4-1.5-4.3-4-4.3z"
            stroke="rgba(255,255,255,.65)" strokeWidth="1.4" strokeLinejoin="round" />
          <path d="M8.2 15.5a1.8 1.8 0 003.6 0" stroke="rgba(255,255,255,.65)" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
        {count > 0 && (
          <span style={{
            position: "absolute", top: 12, right: 8, background: "#EF4444", color: "#fff",
            fontSize: 9, fontWeight: 800, borderRadius: 10, minWidth: 15, height: 15,
            display: "flex", alignItems: "center", justifyContent: "center", padding: "0 3px",
          }}>{count > 9 ? "9+" : count}</span>
        )}
      </button>

      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", right: 0, width: 340,
          background: "#fff", border: "1px solid #E5E7EB", borderRadius: 12,
          boxShadow: "0 12px 32px rgba(0,0,0,.18)", zIndex:200, overflow: "hidden",
          fontFamily: "Barlow, system-ui, sans-serif",
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "10px 14px", borderBottom: "1px solid #F0F0F0" }}>
            <span style={{ fontSize: 12, fontWeight: 800, color: D }}>Notifications</span>
            {notifs.some(n => !n.lu) && (
              <button onClick={markAllRead} style={{
                background: "none", border: "none", cursor: "pointer",
                fontSize: 10.5, fontWeight: 700, color: "#3A6EA8",
              }}>Tout marquer comme lu</button>
            )}
          </div>
          <div style={{ maxHeight: 360, overflowY: "auto" }}>
            {loading && <div style={{ padding: 24, textAlign: "center", color: "#9A9AA8", fontSize: 12 }}>Chargement…</div>}
            {!loading && notifs.length === 0 && (
              <div style={{ padding: 24, textAlign: "center", color: "#9A9AA8", fontSize: 12 }}>Aucune notification</div>
            )}
            {!loading && notifs.map(n => (
              <button key={n.id} onClick={() => onClickNotif(n)} style={{
                display: "flex", gap: 10, width: "100%", textAlign: "left",
                padding: "10px 14px", border: "none", borderBottom: "1px solid #F5F5F8",
                background: n.lu ? "#fff" : "#FFFBEA", cursor: n.lien ? "pointer" : "default",
              }}>
                <div style={{
                  width: 7, height: 7, borderRadius: "50%", flexShrink: 0, marginTop: 5,
                  background: GRAVITE_COLOR[n.gravite] || GRAVITE_COLOR.info,
                }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: n.lu ? 600 : 800, color: D }}>{n.titre}</div>
                  {n.message && (
                    <div style={{ fontSize: 10.5, color: "#747480", marginTop: 2, lineHeight: 1.4 }}>{n.message}</div>
                  )}
                  <div style={{ fontSize: 9.5, color: "#9A9AA8", marginTop: 3 }}>{timeAgo(n.created_at)}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
