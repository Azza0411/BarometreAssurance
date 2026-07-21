import PageHeaderBar from "./PageHeaderBar";

export default function PageLayout({
  title,
  children,
  kpis = [],
  source = "Source : CMF · CGA · FTUSA · Données extraites",
  rightComponent = null
}) {
  return (
    <div style={{
      height: "calc(100vh - 92px)",
      background: "#F9F9FB",
      fontFamily: "Barlow, system-ui, sans-serif",
      display: "flex",
      flexDirection: "column",
      overflow: "hidden"
    }}>

      <PageHeaderBar title={title} right={rightComponent} />

      {/* BARRE KPIs SOMBRE - Style exact comme Aperçu Marché */}
      {kpis.length > 0 && (
        <div style={{
          background: "#1F2937",
          padding: "22px 32px",
          display: "flex",
          gap: "64px",
          flexWrap: "wrap",
          borderBottom: "1px solid #374151",
        }}>
          {kpis.map((kpi, i) => (
            <div key={i} style={{ minWidth: "185px" }}>
              <div style={{ 
                fontSize: "11px", 
                fontWeight: 600, 
                color: "#9CA3AF", 
                textTransform: "uppercase", 
                letterSpacing: "1px",
                marginBottom: "8px" 
              }}>
                {kpi.label}
              </div>
              <div style={{ 
                fontSize: "36px", 
                fontWeight: 800, 
                color: "#FFFFFF", 
                letterSpacing: "-1.5px" 
              }}>
                {kpi.value}
              </div>
              {kpi.sub && (
                <div style={{ 
                  fontSize: "13.5px", 
                  color: kpi.pos ? "#34D399" : "#94A3B8", 
                  marginTop: "6px",
                  fontWeight: 500 
                }}>
                  {kpi.sub}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Contenu principal */}
      <div style={{
        flex: 1,
        overflowY: "auto",
        padding: "28px 32px",
        display: "flex",
        flexDirection: "column",
        gap: 24
      }}>
        {children}

        <div style={{ textAlign: "right", fontSize: "10px", color: "#64748B", marginTop: "auto" }}>
          {source}
        </div>
      </div>
    </div>
  );
}