/* ─────────────────────────────────────────────────────────────
   EY Baromètre Assurance TN — Charte graphique ApexCharts
   Police : Barlow (chargée globalement)
   Palette categorielle : validée CVD, contraste 3:1 min sur blanc
───────────────────────────────────────────────────────────── */

/* ── Tokens ── */
export const C = {
  dark:    "#2E2E38",   // EY charcoal — série 1 / axe / texte
  yellow:  "#FFE600",   // EY jaune    — accentuation
  blue:    "#3A6EA8",   // bleu acier  — série 3
  orange:  "#D4620A",   // ambre foncé — série 4
  slate:   "#647294",   // ardoise     — série 5
  grey:    "#9A9AA8",   // gris neutre — série 6
  muted:   "#747480",   // texte axes
  grid:    "#EBEBEF",   // grille
  surface: "#FFFFFF",   // fond carte
};

/* Ordre catégoriel fixe — ne jamais cycler */
export const CAT6 = [C.dark, C.yellow, C.blue, C.orange, C.slate, C.grey];

/* ── Helpers réutilisables ── */

const FONT = "Barlow, system-ui, sans-serif";

const axisLabel = { style: { colors: C.muted, fontSize: "11px", fontWeight: 500, fontFamily: FONT } };
const axisBase  = { axisBorder: { show: false }, axisTicks: { show: false } };
const gridBase  = {
  borderColor: C.grid, strokeDashArray: 4,
  xaxis: { lines: { show: false } },
  yaxis: { lines: { show: true } },
  padding: { top: 4, right: 12, bottom: 0, left: 4 },
};
const legendBase = {
  position: "top", horizontalAlign: "left",
  fontSize: "12px", fontWeight: 600, fontFamily: FONT,
  labels: { colors: C.dark },
  markers: { radius: 3, width: 14, height: 8, offsetY: 1 },
  itemMargin: { horizontal: 16, vertical: 0 },
};
const tooltipBase = {
  style: { fontFamily: FONT, fontSize: "12px" },
  x: { show: true },
};

/* ── BASE — tous les charts héritent de ça ── */
export function base(categories = []) {
  return {
    chart: {
      toolbar: { show: false },
      fontFamily: FONT,
      background: "transparent",
      animations: { enabled: false },
    },
    colors: CAT6,
    grid: gridBase,
    xaxis: { ...axisBase, categories, labels: axisLabel },
    yaxis: { labels: axisLabel },
    legend: legendBase,
    dataLabels: { enabled: false },
    tooltip: tooltipBase,
    stroke: { curve: "smooth" },
  };
}

/* ── LINE ── */
export function line(categories = [], overrides = {}) {
  return {
    ...base(categories),
    chart: { ...base().chart, type: "line" },
    stroke: { width: 2.5, curve: "smooth" },
    markers: { size: 4, strokeColors: C.surface, strokeWidth: 2, hover: { size: 6 } },
    ...overrides,
  };
}

/* ── BAR VERTICAL ── */
export function bar(categories = [], overrides = {}) {
  return {
    ...base(categories),
    chart: { ...base().chart, type: "bar" },
    plotOptions: { bar: { columnWidth: "58%", borderRadius: 4, borderRadiusApplication: "end" } },
    ...overrides,
  };
}

/* ── BAR HORIZONTAL ── */
export function barH(categories = [], overrides = {}) {
  return {
    ...base(categories),
    chart: { ...base().chart, type: "bar" },
    plotOptions: { bar: { horizontal: true, barHeight: "58%", borderRadius: 4, borderRadiusApplication: "end" } },
    grid: { ...gridBase, xaxis: { lines: { show: true } }, yaxis: { lines: { show: false } } },
    xaxis: { ...axisBase, categories, labels: axisLabel },
    yaxis: { labels: { ...axisLabel, maxWidth: 130 }, axisBorder: { show: false }, axisTicks: { show: false } },
    legend: { show: false },
    dataLabels: {
      enabled: true,
      textAnchor: "start",
      offsetX: 6,
      style: { fontSize: "11px", fontWeight: 700, fontFamily: FONT, colors: [C.dark] },
      formatter: v => v != null ? v : "",
    },
    ...overrides,
  };
}

/* ── COMBO line+bar ── */
export function combo(categories = [], overrides = {}) {
  return {
    ...base(categories),
    chart: { ...base().chart, type: "line" },
    plotOptions: { bar: { columnWidth: "58%", borderRadius: 3, borderRadiusApplication: "end" } },
    stroke: { width: [0, 0, 2.5], curve: "smooth" },
    markers: { size: [0, 0, 4], strokeColors: C.surface, strokeWidth: 2 },
    fill: {
      type: ["gradient", "gradient", "solid"],
      gradient: { shade: "light", type: "vertical", shadeIntensity: 0.15, opacityFrom: 0.85, opacityTo: 0.55, stops: [0, 100] },
    },
    ...overrides,
  };
}

/* ── DONUT ── */
export function donut(labels = [], totalFormatter = v => v, overrides = {}) {
  return {
    chart: { type: "donut", fontFamily: FONT, background: "transparent", animations: { enabled: false } },
    colors: CAT6,
    labels,
    plotOptions: {
      pie: {
        donut: {
          size: "64%",
          labels: {
            show: true,
            total: {
              show: true, label: "Total", fontSize: "12px", fontWeight: 700,
              color: C.muted, fontFamily: FONT,
              formatter: totalFormatter,
            },
            value: { show: true, fontSize: "22px", fontWeight: 900, color: C.dark, fontFamily: FONT, formatter: v => `${parseFloat(v).toFixed(1)}%` },
          },
        },
      },
    },
    dataLabels: { enabled: false },
    legend: {
      position: "bottom", fontSize: "12px", fontWeight: 600, fontFamily: FONT,
      labels: { colors: C.dark },
      markers: { radius: 3, width: 14, height: 8 },
      itemMargin: { horizontal: 10, vertical: 6 },
    },
    tooltip: { ...tooltipBase, y: { formatter: v => `${v}%` } },
    ...overrides,
  };
}

/* ── AREA ── */
export function area(categories = [], overrides = {}) {
  return {
    ...line(categories),
    chart: { ...base().chart, type: "area" },
    fill: {
      type: "gradient",
      gradient: { shade: "light", type: "vertical", shadeIntensity: 0.1, opacityFrom: 0.4, opacityTo: 0.05, stops: [0, 100] },
    },
    stroke: { width: 2.5, curve: "smooth" },
    ...overrides,
  };
}
