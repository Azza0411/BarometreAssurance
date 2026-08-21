// Miroir front-end de config/company_registry.py::TAKAFUL_CODES (Python).
// Duplication volontaire : même pattern déjà utilisé pour ASSUREURS/
// COMPANY_LABELS dans AnalyseComparative.jsx/ApercuMarche.jsx, pas d'appel
// réseau juste pour classer 2 codes compagnie.
export const TAKAFUL_CODES = new Set(["AT_TAKAFULIA", "ZITOUNA_TAKAFUL", "AL_AMANAH_TAKAFUL"]);

export function isTakaful(code) {
  return TAKAFUL_CODES.has(code);
}

export function getFamille(code) {
  return isTakaful(code) ? "takaful" : "conventionnelle";
}
