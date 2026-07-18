const LOGO_MAP = {
  AL_AMANAH_TAKAFUL: "/logos/El Amana Takaful.png",
  AMI:               "/logos/AMI.png",
  ASTREE:            "/logos/astree.png",
  ATTIJARI:          "/logos/Attijari.png",
  AT_TAKAFULIA:      "/logos/At-Takafulia.png",
  BH:                "/logos/BH.png",
  BIAT:              "/logos/BIAT.png",
  BNA:               "/logos/BNA.png",
  CARTE:             "/logos/Carte.png",
  CARTE_VIE:         "/logos/Carte-Vie.png",
  COMAR:             "/logos/COMAR.png",
  COTUNACE:          "/logos/COTUNACE.png",
  CTAMA:             "/logos/CTAMA.png",
  GAT:               "/logos/GAT.png",
  GAT_VIE:           "/logos/GAT-vie.png",
  HAYETT:            "/logos/hayett.png",
  LLOYD_TUNISIEN:    "/logos/LLOYD.png",
  LLOYD_VIE:         "/logos/LLOYD-Vie.png",
  MAGHREBIA:         "/logos/Maghrebia.png",
  MAGHREBIA_VIE:     "/logos/Maghrebia-Vie.png",
  STAR:              "/logos/STAR.png",
  TUNIS_RE:          "/logos/TunisRe.png",
  UIB:               "/logos/UIB.png",
  ZITOUNA_TAKAFUL:   "/logos/Zitouna-Takaful.png",
};

export function getLogoSrc(code) {
  return LOGO_MAP[code] ?? null;
}
