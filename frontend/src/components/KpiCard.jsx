export default function KpiCard({ label, value, delta, deltaLabel, positive }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="text-[10px] font-bold tracking-[1.2px] text-ey-grey uppercase mb-2">
        {label}
      </div>
      <div className="text-3xl font-black text-ey-dark leading-tight">{value}</div>
      {delta && (
        <div className={`text-xs font-semibold mt-1.5 flex items-center gap-1 ${
          positive === false ? "text-ey-red" : "text-ey-green"
        }`}>
          {positive === false ? "▼" : "▲"} {delta}
          {deltaLabel && <span className="text-ey-grey font-normal">{deltaLabel}</span>}
        </div>
      )}
    </div>
  );
}
