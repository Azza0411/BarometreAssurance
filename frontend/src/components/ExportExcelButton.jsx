const D = "#2E2E38", Y = "#FFE600";

export default function ExportExcelButton({ href, label = "Exporter Excel" }) {
  return (
    <a
      href={href}
      download
      style={{
        display: "flex", alignItems: "center", gap: 6,
        background: "#fff", color: D, border: `1.5px solid ${D}`,
        textDecoration: "none",
        padding: "7px 14px", borderRadius: 9, fontSize: 12, fontWeight: 800,
        fontFamily: "Barlow, system-ui, sans-serif",
        whiteSpace: "nowrap", flexShrink: 0,
      }}
    >
      <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
        <rect x="1.5" y="2" width="13" height="12" rx="1.5" stroke={D} strokeWidth="1.3" />
        <path d="M1.5 6h13M6 6v8M11 6v8" stroke={D} strokeWidth="1.3" />
      </svg>
      {label}
    </a>
  );
}
