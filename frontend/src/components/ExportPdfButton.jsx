const D = "#2E2E38", Y = "#FFE600";

/* Lien de téléchargement direct — le backend répond avec
   Content-Disposition: attachment (send_file(as_attachment=True)),
   pas besoin de fetch/blob côté client. */
export default function ExportPdfButton({ href, label = "Exporter PDF", disabled = false }) {
  return (
    <a
      href={disabled ? undefined : href}
      download
      aria-disabled={disabled}
      style={{
        display: "flex", alignItems: "center", gap: 6,
        background: disabled ? "#E5E7EB" : D, color: disabled ? "#9CA3AF" : Y,
        textDecoration: "none", border: "none",
        padding: "8px 14px", borderRadius: 9, fontSize: 12, fontWeight: 800,
        fontFamily: "Barlow, system-ui, sans-serif",
        cursor: disabled ? "default" : "pointer",
        pointerEvents: disabled ? "none" : "auto",
        whiteSpace: "nowrap", flexShrink: 0,
      }}
    >
      <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
        <path d="M8 1v9m0 0l-3.5-3.5M8 10l3.5-3.5M2 12v2a1 1 0 001 1h10a1 1 0 001-1v-2"
          stroke={disabled ? "#9CA3AF" : Y} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {label}
    </a>
  );
}
