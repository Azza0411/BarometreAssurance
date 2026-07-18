export const YEARS = [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024];

export const primesMarche = {
  categories: [...YEARS, 2026],
  historique:  [1.031, 1.091, 1.144, 1.219, 1.334, 1.435],
  prevision:   [null,  null,  null,  null,  null,  1.435, 1.540],
};

export const ratioSinistralite = {
  categories: YEARS,
  values: [67.0, 66.1, 67.2, 68.0, 68.3, 69.1],
};

export const compagnies = [
  { rang:1,  nom:"STAR Assurances",    logo:"/logos/STAR.png",     primes:756.3, pdm:15.6, rc:96.1,  roe:12.6, branche:"Non-Vie"      },
  { rang:2,  nom:"AMI Assurances",     logo:"/logos/AMI.png",      primes:548.1, pdm:11.3, rc:98.3,  roe:11.4, branche:"Non-Vie"      },
  { rang:3,  nom:"CARTE Assurances",   logo:"/logos/Carte.png",    primes:421.2, pdm:8.7,  rc:99.2,  roe:11.4, branche:"Non-Vie"      },
  { rang:4,  nom:"COMAR Assurances",   logo:"/logos/COMAR.png",    primes:358.6, pdm:7.4,  rc:101.8, roe:11.4, branche:"Non-Vie"      },
  { rang:5,  nom:"ATTIJARI Assurances",logo:"/logos/Attijari.png", primes:330.7, pdm:6.8,  rc:97.5,  roe:11.4, branche:"Non-Vie"      },
  { rang:6,  nom:"GAT Assurances",     logo:"/logos/GAT.png",      primes:296.1, pdm:6.1,  rc:95.4,  roe:11.4, branche:"Non-Vie"      },
  { rang:7,  nom:"BH Assurances",      logo:"/logos/BH.png",       primes:237.5, pdm:4.9,  rc:93.6,  roe:11.4, branche:"Non-Vie"      },
  { rang:8,  nom:"Tunis Re",           logo:"/logos/TunisRe.png",  primes:175.0, pdm:3.6,  rc:93.6,  roe:11.4, branche:"Réassurance"  },
  { rang:9,  nom:"Maghrebia",          logo:"/logos/Maghrebia.png",primes:146.6, pdm:3.0,  rc:93.6,  roe:11.4, branche:"Non-Vie"      },
  { rang:10, nom:"GAT VIE",            logo:"/logos/GAT-vie.png",  primes:126.2, pdm:2.6,  rc:93.6,  roe:11.4, branche:"Non-Vie"      },
];

export const gouvernorats = [
  { gouv:"Tunis",      primes:1247312000, pdm:21.6, agences:342, region:"Grand Tunis", pop:1056247 },
  { gouv:"Ariana",     primes:677896000,  pdm:11.7, agences:212, region:"Grand Tunis", pop:484481  },
  { gouv:"Sousse",     primes:536540000,  pdm:9.3,  agences:181, region:"Littoral",    pop:674971  },
  { gouv:"Sfax",       primes:477522000,  pdm:8.3,  agences:178, region:"Littoral",    pop:955421  },
  { gouv:"Nabeul",     primes:317572000,  pdm:5.5,  agences:132, region:"Littoral",    pop:787920  },
  { gouv:"Monastir",   primes:284443000,  pdm:4.9,  agences:101, region:"Littoral",    pop:547977  },
  { gouv:"Bizerte",    primes:236219000,  pdm:4.1,  agences:96,  region:"Littoral",    pop:568219  },
  { gouv:"Ben Arous",  primes:228155000,  pdm:4.0,  agences:94,  region:"Grand Tunis", pop:620594  },
  { gouv:"Zaghouan",   primes:173442000,  pdm:3.0,  agences:72,  region:"Intérieur",   pop:184100  },
  { gouv:"Mahdia",     primes:144814000,  pdm:2.5,  agences:57,  region:"Littoral",    pop:411803  },
  { gouv:"Manouba",    primes:120000000,  pdm:2.1,  agences:48,  region:"Grand Tunis", pop:384500  },
  { gouv:"Béja",       primes:95000000,   pdm:1.6,  agences:38,  region:"Intérieur",   pop:303276  },
  { gouv:"Kairouan",   primes:98000000,   pdm:1.7,  agences:42,  region:"Intérieur",   pop:572800  },
  { gouv:"Gabès",      primes:110000000,  pdm:1.9,  agences:45,  region:"Sud",         pop:374300  },
  { gouv:"Médenine",   primes:125000000,  pdm:2.2,  agences:52,  region:"Sud",         pop:496000  },
];

export const starData = {
  primesEvolution: [179.8, 198.4, 221.7, 235.9, 252.8, 270.6],
  resTechEvolution:[24.5,  27.1,  34.8,  42.7,  48.3,  51.2 ],
  produits: [
    { label:"Automobile", value:42.7 },
    { label:"Vie",        value:24.3 },
    { label:"Incendie",   value:15.6 },
    { label:"Accidents",  value:7.9  },
    { label:"Autres",     value:9.5  },
  ],
  roa: [1.10, 1.30, 1.47, 1.72, 2.10, 2.41],
  roe: [8.45, 9.10, 9.85, 10.70, 11.87, 14.60],
};

export const bubble = [
  { nom:"STAR",    pdm:15.6, croissance:12.6, primes:756 },
  { nom:"AMI",     pdm:11.3, croissance:10.5, primes:548 },
  { nom:"CARTE",   pdm:8.7,  croissance:9.8,  primes:421 },
  { nom:"COMAR",   pdm:7.4,  croissance:11.0, primes:358 },
  { nom:"GAT",     pdm:6.1,  croissance:9.0,  primes:296 },
  { nom:"Attijari",pdm:6.8,  croissance:10.2, primes:331 },
  { nom:"BH",      pdm:4.9,  croissance:7.5,  primes:237 },
  { nom:"LLOYD",   pdm:5.2,  croissance:8.2,  primes:252 },
  { nom:"Maghrebia",pdm:3.0, croissance:8.8,  primes:147 },
];
