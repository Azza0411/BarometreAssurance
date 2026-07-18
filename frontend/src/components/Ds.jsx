/**
 * Design System — Baromètre Assurance TN
 * Tokens, composants partagés sur tous les dashboards.
 */

/* ── Palette ── */
export const DS = {
  bg:       '#F2F2F8',   // fond de page — bleu-gris très doux
  surface:  '#FFFFFF',   // cartes
  tile:     '#EBEBF4',   // tuiles internes (KPI secondaires)
  border:   'rgba(0,0,0,.06)',
  primary:  '#16161E',
  secondary:'#5E5E74',
  muted:    '#9696AC',
  accent:   '#FFE600',   // EY yellow
  dark:     '#2E2E38',   // EY dark
  pos:      '#16A34A',
  neg:      '#DC2626',
  R:  6,    // card radius
  r:  4,    // tile radius
  font: 'Barlow, system-ui, sans-serif',
};

/* ── Card ── */
export function DsCard({ children, style = {} }) {
  return (
    <div style={{
      background: DS.surface,
      border: `1px solid ${DS.border}`,
      borderRadius: DS.R,
      padding: '16px 18px',
      ...style,
    }}>
      {children}
    </div>
  );
}

/* ── Section title avec underline jaune ── */
export function DsTitle({ children, action }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', paddingBottom: 10 }}>
        <span style={{ fontSize:10, fontWeight:800, letterSpacing:'1.8px', textTransform:'uppercase', color: DS.primary, fontFamily: DS.font }}>
          {children}
        </span>
        {action}
      </div>
      <div style={{ height:2, background: DS.accent, borderRadius:1 }}/>
    </div>
  );
}

/* ── KPI tile secondaire ── */
export function DsKpi({ label, value, sub, delta, pos = true, accent = false }) {
  return (
    <div style={{
      background: DS.tile,
      borderTop: `2px solid ${accent ? DS.accent : 'transparent'}`,
      borderRadius: DS.r,
      padding: '11px 14px 9px',
      display: 'flex', flexDirection: 'column',
      minWidth: 0,
    }}>
      <div style={{ fontSize:8.5, fontWeight:700, letterSpacing:'1.6px', textTransform:'uppercase', color: DS.muted, marginBottom:6, fontFamily: DS.font }}>
        {label}
      </div>
      <div style={{ fontSize:22, fontWeight:700, color: DS.primary, lineHeight:1, fontVariantNumeric:'tabular-nums', letterSpacing:'-0.3px', marginBottom:5, fontFamily: DS.font }}>
        {value}
      </div>
      <div style={{ display:'flex', alignItems:'center', gap:5, marginTop:'auto' }}>
        {sub && <span style={{ fontSize:10.5, color: DS.muted }}>{sub}</span>}
        {delta && (
          <span style={{ fontSize:10.5, fontWeight:700, marginLeft:'auto', flexShrink:0, color: pos ? DS.pos : DS.neg }}>
            {pos ? '↑' : '↓'} {delta}
          </span>
        )}
      </div>
    </div>
  );
}

/* ── Bannière KPI macro (horizontal, blocs colorés) ── */
export function DsBanner({ kpis }) {
  return (
    <div style={{ display:'flex', gap:10, flexShrink:0, marginBottom:14 }}>
      {kpis.map((k, i) => (
        <div key={i} style={{
          flex: 1, minWidth: 0,
          background: DS.surface,
          border: `1px solid ${DS.border}`,
          borderTop: `3px solid ${k.accent ? DS.accent : 'transparent'}`,
          borderRadius: DS.R,
          padding: '14px 18px 12px',
          display: 'flex', flexDirection:'column',
        }}>
          <div style={{ fontSize:8.5, fontWeight:700, letterSpacing:'2px', textTransform:'uppercase', color: DS.muted, marginBottom:8 }}>
            {k.label}
          </div>
          <div style={{ fontSize:34, fontWeight:800, color: k.accent ? DS.dark : DS.primary, lineHeight:1, fontVariantNumeric:'tabular-nums', letterSpacing:'-1px', marginBottom:7, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>
            {k.value}
          </div>
          <div style={{ display:'flex', alignItems:'center', gap:6, marginTop:'auto' }}>
            {k.sub && <span style={{ fontSize:11, color: DS.muted }}>{k.sub}</span>}
            {k.delta && (
              <span style={{ fontSize:11, fontWeight:700, marginLeft:'auto', color: k.pos ? DS.pos : DS.neg }}>
                {k.pos ? '↑' : '↓'} {k.delta}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Source note ── */
export function DsSource({ children }) {
  return (
    <div style={{ textAlign:'right', fontSize:9.5, color: DS.muted, flexShrink:0, paddingTop:4, fontFamily: DS.font }}>
      {children}
    </div>
  );
}
