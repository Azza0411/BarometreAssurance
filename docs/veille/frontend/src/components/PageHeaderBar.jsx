const Y = "#FFE600", D = "#2E2E38", G = "#747480";
const FONT = "Barlow,system-ui,sans-serif";

export default function PageHeaderBar({ title, subtitle, right }) {
  return (
    <div style={{
      background: "white",
      borderBottom: "1px solid #E5E7EB",
      padding: "18px 32px",
      display: "flex", alignItems: "center", justifyContent: "space-between",
      fontFamily: FONT,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ width: 3, height: 22, background: Y, borderRadius: 2, flexShrink: 0 }}/>
        <div>
          <div style={{ fontSize: 17, fontWeight: 800, color: D, letterSpacing: "-0.3px" }}>
            {title}
          </div>
          {subtitle && (
            <div style={{ fontSize: 11, color: G, marginTop: 2 }}>{subtitle}</div>
          )}
        </div>
      </div>
      {right && <div>{right}</div>}
    </div>
  );
}
