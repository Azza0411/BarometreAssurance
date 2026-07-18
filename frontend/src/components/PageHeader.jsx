import { HiOutlineBookOpen } from "react-icons/hi";

export default function PageHeader({ title, subtitle, year = "2024", children }) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h1 className="text-3xl font-black text-ey-dark">{title}</h1>
        <p className="text-sm text-ey-grey mt-0.5">{subtitle}</p>
      </div>
      <div className="flex items-center gap-3 flex-shrink-0 mt-1">
        {children}
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-ey-dark">Année</span>
          <span className="bg-ey-yellow text-ey-dark text-xs font-bold px-3 py-1 rounded">
            {year} ✕
          </span>
          <span className="text-ey-grey text-lg">∨</span>
        </div>
        <button className="flex items-center gap-2 bg-white border border-gray-200 rounded-lg px-4 py-2 text-sm font-semibold text-ey-dark hover:bg-gray-50 transition shadow-sm">
          <HiOutlineBookOpen className="text-base" />
          Guide d'utilisation ↗
        </button>
      </div>
    </div>
  );
}
