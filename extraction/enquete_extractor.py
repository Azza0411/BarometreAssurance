"""
Extrait et calcule toutes les statistiques de l'enquête de marché
à partir du fichier Excel source :
  data/Survey CX_Base de données de l'étude Extract.xlsx

Feuilles utilisées :
  - BDD Retail    → Grand public (Particuliers, Professionnels, TRE, Étudiants, Retraités)
  - BDD Corporate → Entreprises
  - Région        → Mapping Gouvernorat → zone géographique

Retour : dict prêt à être sérialisé en JSON par l'API Flask.
"""

import glob
import os
import re
import math
from functools import lru_cache

import pandas as pd

# ─── Chemin du fichier ───────────────────────────────────────────────────────
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def _find_xlsx():
    files = glob.glob(os.path.join(_DATA_DIR, "*.xlsx"))
    survey = [f for f in files if "Survey" in os.path.basename(f) or "survey" in os.path.basename(f)]
    return survey[0] if survey else (files[0] if files else None)


# ─── Normalisation ───────────────────────────────────────────────────────────

def _norm(v):
    """Nettoie une valeur texte (strip, espaces multiples, minuscules)."""
    if pd.isna(v):
        return None
    return re.sub(r"\s+", " ", str(v)).strip()

# Mapping Gouvernorat → clé de zone (4 zones enquête)
GOV_TO_ZONE = {
    "Sfax":       "centre-est",
    "Monastir":   "centre-est",
    "Sousse":     "centre-est",
    "Mahdia":     "centre-est",
    "Bizerte":    "nord-est",
    "Tunis":      "nord-est",
    "Nabeul":     "nord-est",
    "Ben Arous":  "nord-est",
    "Manouba":    "nord-est",
    "Ariana":     "nord-est",
    "Zaghouan":   "nord-est",
    "Jendouba":   "nord-centre-ouest",
    "Kasserine":  "nord-centre-ouest",
    "Béja":       "nord-centre-ouest",
    "Beja":       "nord-centre-ouest",
    "Sidi Bouzid":"nord-centre-ouest",
    "Séliana":    "nord-centre-ouest",
    "Seliana":    "nord-centre-ouest",
    "Le Kef":     "nord-centre-ouest",
    "Kef":        "nord-centre-ouest",
    "Kairouan":   "nord-centre-ouest",
    "Gabès":      "sud-est-ouest",
    "Gabes":      "sud-est-ouest",
    "Médenine":   "sud-est-ouest",
    "Médnine":    "sud-est-ouest",
    "Medenine":   "sud-est-ouest",
    "Tozeur":     "sud-est-ouest",
    "Gafsa":      "sud-est-ouest",
    "Kébili":     "sud-est-ouest",
    "Kebili":     "sud-est-ouest",
    "Tataouine":  "sud-est-ouest",
}

# Mapping segment Excel → clé interne
SEG_MAP = {
    "A - Particulier":   "particuliers",
    "B - Professionnel": "professionnels",
    "C - Etudiant":      "etudiants",
    "D - TRE":           "tre",
    "E - Retraité":      "retraites",
}

# Normalisation nom compagnie → code interne
COMPANY_ALIASES = {
    "assurances star":     "STAR",
    "star":                "STAR",
    "comar":               "COMAR",
    "gat":                 "GAT",
    "mae":                 "MAE",
    "maghrebia":           "MAGHREBIA",
    "lloyd":               "LLOYD_TUNISIEN",
    "lloyd tunisien":      "LLOYD_TUNISIEN",
    "ami":                 "AMI",
    "ctama":               "CTAMA",
    "astree":              "ASTREE",
    "astrée":              "ASTREE",
    "zitouna takaful":     "ZITOUNA_TAKAFUL",
    "zitouna":             "ZITOUNA_TAKAFUL",
    "attakafulia":         "AT_TAKAFULIA",
    "at-takafulia":        "AT_TAKAFULIA",
    "at takafulia":        "AT_TAKAFULIA",
    "assurances biat":     "BIAT",
    "biat":                "BIAT",
    "attijari":            "ATTIJARI",
    "attijeri assurance":  "ATTIJARI",
    "assurances hayett":   "HAYETT",
    "hayett":              "HAYETT",
    "bh assurance":        "BH",
    "bh":                  "BH",
    "el amana takaful":    "AL_AMANAH_TAKAFUL",
    "el amana":            "AL_AMANAH_TAKAFUL",
    "carte":               "CARTE",
    "nsp":                 None,  # Non spécifié → ignoré
    "nsp ":                None,
    "autres":              None,
    "autres ":             None,
    "aucune assurance":    None,
    "aucune":              None,
    "nc":                  None,
}

COMPANY_LABELS = {
    "STAR":            "STAR",
    "COMAR":           "Comar",
    "GAT":             "GAT",
    "MAE":             "MAE",
    "MAGHREBIA":       "Maghrebia",
    "LLOYD_TUNISIEN":  "Lloyd",
    "AMI":             "Ami",
    "CTAMA":           "CTAMA",
    "ASTREE":          "Astrée",
    "ZITOUNA_TAKAFUL": "Zitouna Takaful",
    "AT_TAKAFULIA":    "At-Takafulia",
    "BIAT":            "BIAT Assurances",
    "ATTIJARI":        "Attijari",
    "HAYETT":          "Hayett",
    "BH":              "BH Assurance",
    "AL_AMANAH_TAKAFUL":"El Amana Takaful",
    "CARTE":           "La Carte",
}

def _norm_company(raw):
    if not raw or pd.isna(raw):
        return None
    key = re.sub(r"\s+", " ", str(raw).strip()).lower()
    return COMPANY_ALIASES.get(key, key.upper() if key else None)


# ─── Helpers stats ───────────────────────────────────────────────────────────

def _pct(n, total):
    if not total:
        return 0
    return round(n / total * 100)

def _vc_pct(series, total=None):
    """value_counts → {label: pct}"""
    vc = series.dropna().value_counts()
    t = total or len(series.dropna())
    return {str(k).strip(): _pct(int(v), t) for k, v in vc.items()}

def _ordered_pct(series, order, total=None):
    """value_counts filtré et ordonné selon `order`, retourne (labs, vals)."""
    t = total or len(series.dropna())
    vc = {}
    for v in series.dropna():
        sv = str(v).strip()
        for o in order:
            if o.lower() in sv.lower():
                vc[o] = vc.get(o, 0) + 1
                break
    labs, vals = [], []
    for o in order:
        if vc.get(o, 0) > 0 or o in order[:3]:
            labs.append(o)
            vals.append(_pct(vc.get(o, 0), t))
    return labs, vals

def _top_companies(series, n=5):
    """Retourne les n premières compagnies avec leur pct, normalisées."""
    counts = {}
    total = 0
    for v in series.dropna():
        sv = str(v).strip()
        # Peut contenir plusieurs séparées par /
        parts = [p.strip() for p in re.split(r"[/,;]", sv) if p.strip()]
        for p in parts:
            code = _norm_company(p)
            if code:
                counts[code] = counts.get(code, 0) + 1
                total += 1
    if not total:
        return []
    ranked = sorted(counts.items(), key=lambda x: -x[1])[:n]
    return [
        {"code": code, "label": COMPANY_LABELS.get(code, code), "pct": _pct(cnt, sum(counts.values()))}
        for code, cnt in ranked
    ]

def _treemap(series, total=None):
    """Retourne [{x:label, y:pct}] pour treemap ApexCharts."""
    vc = series.dropna().value_counts()
    t = total or vc.sum()
    items = []
    for k, v in vc.items():
        label = str(k).strip()
        if label and label.lower() not in ("nan", "nc", "nsp"):
            pct = _pct(int(v), t)
            if pct > 0:
                items.append({"x": label, "y": pct})
    return sorted(items, key=lambda x: -x["y"])

def _canal_row(df, col):
    """Compte Digital/Mixte/Physique dans une colonne de canal."""
    counts = {"Digital": 0, "Mixte": 0, "Physique": 0}
    total = 0
    for v in df[col].dropna():
        sv = str(v).strip().lower()
        if "digital" in sv:
            counts["Digital"] += 1
        elif "neutre" in sv or "mixte" in sv:
            counts["Mixte"] += 1
        elif "physique" in sv or "agence" in sv:
            counts["Physique"] += 1
        total += 1
    return counts, total

def _satisfaction_row(series):
    """Retourne [pct_pas_du_tout, pct_peu, pct_ni_ni, pct_satisfait, pct_tres] → regroupé en 4."""
    buckets = {
        "Pas du tout satisfait": 0,
        "Peu satisfait": 0,
        "Neutre": 0,
        "Satisfait": 0,
        "Très satisfait": 0,
    }
    total = 0
    for v in series.dropna():
        sv = str(v).strip().lower()
        if "pas du tout" in sv:
            buckets["Pas du tout satisfait"] += 1
        elif "pas satisfait" in sv or "peu satisfait" in sv:
            buckets["Peu satisfait"] += 1
        elif "ni satisfait" in sv or "ni pas satisfait" in sv or "nc" == sv:
            buckets["Neutre"] += 1
        elif "très satisfait" in sv or "tres satisfait" in sv:
            buckets["Très satisfait"] += 1
        elif "satisfait" in sv:
            buckets["Satisfait"] += 1
        total += 1
    if not total:
        return [0, 0, 0, 0, 0]
    return [_pct(buckets[k], total) for k in
            ["Pas du tout satisfait", "Peu satisfait", "Neutre", "Satisfait", "Très satisfait"]]

def _normalize_modele(v):
    sv = str(v).strip().lower() if v and not pd.isna(v) else ""
    if "mixte" in sv:
        return "Mixte"
    elif "digital" in sv and "physique" not in sv:
        return "Digital"
    elif ("physique" in sv or "agence" in sv) and "digital" not in sv:
        return "Physique"
    return None

def _normalize_perception(v):
    sv = str(v).strip().lower() if v and not pd.isna(v) else ""
    if "très positive" in sv or "tres positive" in sv:
        return "Très positive"
    elif "plutôt positive" in sv or "plutot positive" in sv or "positive" in sv:
        return "Plutôt positive"
    elif "neutre" in sv:
        return "Neutre"
    elif "très négative" in sv or "tres negative" in sv:
        return "Très négative"
    elif "négative" in sv or "negative" in sv:
        return "Plutôt négative"
    return None

def _normalize_confiance(v):
    sv = str(v).strip().lower() if v and not pd.isna(v) else ""
    if "très fort" in sv:
        return "Très fort"
    elif "très faible" in sv or "tres faible" in sv:
        return "Très faible"
    elif "faible" in sv:
        return "Faible"
    elif "fort" in sv:
        return "Fort"
    elif "moyen" in sv:
        return "Moyen"
    return None

def _normalize_revenu(v):
    """Normalise les tranches de revenu — aligne dinars et euros."""
    if not v or pd.isna(v):
        return None
    sv = str(v).strip()
    if "refus" in sv.lower():
        return None
    return sv


# ─── Calcul principal ────────────────────────────────────────────────────────

@lru_cache(maxsize=4)
def compute_stats(company_code="STAR"):
    """
    Calcule et retourne toutes les statistiques de l'enquête.
    Le `company_code` est gardé pour compatibilité API mais le fichier
    est une seule enquête globale — les stats sont les mêmes pour tous.
    """
    path = _find_xlsx()
    if not path:
        return None

    retail = pd.read_excel(path, sheet_name="BDD Retail")
    corp   = pd.read_excel(path, sheet_name="BDD Corporate")

    # ── Segments Grand Public ─────────────────────────────────────────────────
    retail["_seg"] = retail["Segment"].apply(
        lambda v: SEG_MAP.get(str(v).strip(), None) if not pd.isna(v) else None
    )

    seg_counts = {}
    for seg_key in SEG_MAP.values():
        seg_counts[seg_key] = int((retail["_seg"] == seg_key).sum())

    def build_segment(df_seg):
        n = len(df_seg)
        if n == 0:
            return None

        # Genre
        genre_vc = {str(k).strip(): int(v) for k, v in df_seg["Genre"].dropna().value_counts().items()}
        h = genre_vc.get("Homme", 0)
        f = genre_vc.get("Femme", 0)
        tot_gf = h + f
        genre = [_pct(h, tot_gf), _pct(f, tot_gf)] if tot_gf else [0, 0]

        # Tranche d'âge — ordre canonique
        age_order = ["18 – 24 ans", "25– 34 ans", "25 – 34 ans", "35 – 44 ans",
                     "45 – 54 ans", "55–64 ans", "65 ans et plus"]
        age_labels = ["18–24", "25–34", "35–44", "45–54", "55–64", "65+"]
        age_counts = [0] * 6
        col_age = "Tranche d'âge"
        for v in df_seg[col_age].dropna():
            sv = str(v).strip()
            if "18" in sv:   age_counts[0] += 1
            elif "25" in sv: age_counts[1] += 1
            elif "35" in sv: age_counts[2] += 1
            elif "45" in sv: age_counts[3] += 1
            elif "55" in sv: age_counts[4] += 1
            elif "65" in sv: age_counts[5] += 1
        age_total = sum(age_counts) or 1
        age = [_pct(c, age_total) for c in age_counts]

        # Type de profession (treemap)
        type_pro = _treemap(df_seg["Type de profession"])

        # Véhicule
        veh_col = "Disposez-vous d’un véhicule ?"
        if veh_col in df_seg.columns:
            veh_vc = {str(k).strip().lower(): int(v)
                      for k, v in df_seg[veh_col].dropna().value_counts().items()}
            vehicule = _pct(veh_vc.get("oui", 0), n)
        else:
            vehicule = 0

        # Propriétaire
        log_col = "Statut de logement"
        log_vc = {str(k).strip().lower(): int(v)
                  for k, v in df_seg[log_col].dropna().value_counts().items()}
        proprio = _pct(log_vc.get("propriétaire", 0), n)

        # Professions (pour les professionnels)
        prof_col = "Profession - Pour les professionnels "
        professions = []
        if prof_col in df_seg.columns:
            pvc = df_seg[prof_col].dropna().value_counts()
            pt = pvc.sum() or 1
            for k, v in list(pvc.items())[:8]:
                professions.append([str(k).strip(), _pct(int(v), pt)])

        # Revenu individuel mensuel
        rev_ind_order = [
            "<800 dinars/mois", "[800, 1499] dinars par mois", "[1500,2999] dinars par mois",
            "[3000,4999] dinars par mois", "[5000,10000] dinars par mois", ">10000",
            "[1500, 2999] euros par mois", "[3000,4999] euros par mois",
        ]
        rev_ind_labels = [
            "<800 DT", "[800–1499] DT", "[1500–2999] DT",
            "[3000–4999] DT", "[5000–10000] DT", ">10000 DT",
            "[1500–2999] €", "[3000–4999] €",
        ]
        ri_col = "Revenu individuel mensuel"
        ri_vc = {}
        ri_total = 0
        for v in df_seg[ri_col].dropna():
            sv = str(v).strip()
            if "refus" in sv.lower():
                continue
            for i, o in enumerate(rev_ind_order):
                if sv == o or sv.replace(" ", "") == o.replace(" ", ""):
                    ri_vc[i] = ri_vc.get(i, 0) + 1
                    ri_total += 1
                    break
        rev_ind_labs = [rev_ind_labels[i] for i in sorted(ri_vc.keys()) if ri_vc[i] > 0]
        rev_ind_vals = [_pct(ri_vc[i], ri_total) for i in sorted(ri_vc.keys()) if ri_vc[i] > 0]
        revInd = {"labs": rev_ind_labs, "vals": rev_ind_vals}

        # Revenu familial mensuel
        rev_fam_order = [
            "[1150, 2049] dinars par mois", "[2050, 4599] dinars par mois",
            "[2050,4599] dinars par mois", "≥4600 dinars/mois", ">4600", "Refus",
        ]
        rev_fam_labels_clean = {
            "[1150, 2049] dinars par mois": "[1150–2049] DT",
            "[2050, 4599] dinars par mois": "[2050–4599] DT",
            "[2050,4599] dinars par mois":  "[2050–4599] DT",
            "≥4600 dinars/mois":            "≥4600 DT",
            ">4600":                        ">4600 DT",
        }
        rf_col = "Revenu familial mensuel"
        rf_vc = {}
        rf_total = 0
        for v in df_seg[rf_col].dropna():
            sv = str(v).strip()
            if sv.lower() == "refus":
                continue
            clean = rev_fam_labels_clean.get(sv, sv)
            rf_vc[clean] = rf_vc.get(clean, 0) + 1
            rf_total += 1
        # Trier par ordre croissant de revenu
        # Fusionner ≥4600 et >4600 (même tranche, libellés variés)
        merged_4600 = rf_vc.pop("≥4600 DT", 0) + rf_vc.pop(">4600 DT", 0)
        if merged_4600:
            rf_vc["≥4600 DT"] = merged_4600
        rf_order_final = ["[1150–2049] DT", "[2050–4599] DT", "≥4600 DT"]
        rf_labs = [l for l in rf_order_final if l in rf_vc]
        rf_vals = [_pct(rf_vc[l], rf_total) for l in rf_labs]
        revFam = {"labs": rf_labs, "vals": rf_vals}

        return {
            "genre":      genre,
            "age":        age,
            "typePro":    type_pro,
            "vehicule":   vehicule,
            "proprio":    proprio,
            "professions": professions,
            "revFam":     revFam,
            "revInd":     revInd,
        }

    segments = {}
    for seg_key in SEG_MAP.values():
        df_s = retail[retail["_seg"] == seg_key]
        segments[seg_key] = build_segment(df_s)
    segments["all"] = build_segment(retail)

    # ── Géographie (combiné retail + corporate) ───────────────────────────────
    zone_counts = {z: 0 for z in ["nord-est", "centre-est", "nord-centre-ouest", "sud-est-ouest"]}
    total_geo = 0
    for df in (retail, corp):
        for gov in df["Gouvernorat"].dropna():
            zone = GOV_TO_ZONE.get(str(gov).strip())
            if zone:
                zone_counts[zone] += 1
                total_geo += 1
    geo = {z: _pct(c, total_geo) for z, c in zone_counts.items()} if total_geo else None

    # ── Entreprises (corporate) ───────────────────────────────────────────────
    # Secteur d'activité — nettoyage des doublons avec espaces
    secteur_col = "Secteur d’activité"
    if secteur_col in corp.columns:
        corp["_sect"] = corp[secteur_col].apply(
            lambda v: re.sub(r"\s+", " ", str(v)).strip() if not pd.isna(v) else None
        )
        secteurs = _treemap(corp["_sect"])
    else:
        secteurs = []

    # Nombre d'employés — clé de tri
    emp_col = "Nombre d’employés dans votre entreprise"
    emp_order = ["5;19", "20-99", "100-499", "500 et plus"]
    emp_labels = ["5–19", "20–99", "100–499", "500+"]
    emp_vc = {}
    emp_total = 0
    if emp_col in corp.columns:
        for v in corp[emp_col].dropna():
            sv = str(v).strip()
            for i, o in enumerate(emp_order):
                if sv == o:
                    emp_vc[i] = emp_vc.get(i, 0) + 1
                    emp_total += 1
                    break
    employes_labs = [emp_labels[i] for i in sorted(emp_vc.keys())]
    employes_vals = [_pct(emp_vc[i], emp_total) for i in sorted(emp_vc.keys())]
    employes = {"labs": employes_labs, "vals": employes_vals}

    # Chiffre d'affaires annuel
    ca_col = "Chiffre d'affaires annuel"
    ca_order = [
        "<500 000 dinars",
        "[500 000, 4 999 000] dinars",
        "[5 000 000, 9 999 000]",
        "[10 000 000, 20 000 000]",
        ">20 000 000 T",
    ]
    ca_labels = [
        "<500 000 DT",
        "[500K–4,99M] DT",
        "[5M–9,99M] DT",
        "[10M–20M] DT",
        ">20M DT",
    ]
    ca_vc = {}
    ca_total = 0
    if ca_col in corp.columns:
        for v in corp[ca_col].dropna():
            sv = str(v).strip()
            if "refus" in sv.lower():
                continue
            for i, o in enumerate(ca_order):
                if sv == o:
                    ca_vc[i] = ca_vc.get(i, 0) + 1
                    ca_total += 1
                    break
    ca_labs = [ca_labels[i] for i in sorted(ca_vc.keys())]
    ca_vals = [_pct(ca_vc[i], ca_total) for i in sorted(ca_vc.keys())]
    ca = {"labs": ca_labs, "vals": ca_vals}

    entreprises = {"secteurs": secteurs, "employes": employes, "ca": ca}

    # ── Fiche (données combinées retail + corporate pour la fiche client) ─────
    # Modèle idéal (retail uniquement pour fiche Grand Public)
    modele_col = "Assurance - Modèle idéal"
    modele_counts = {"Digital": 0, "Mixte": 0, "Physique": 0}
    modele_total = 0
    for df in (retail,):
        for v in df[modele_col].dropna():
            nm = _normalize_modele(v)
            if nm:
                modele_counts[nm] += 1
                modele_total += 1
    modele_ideal = {
        "labs": ["Digital", "Mixte", "Physique"],
        "vals": [_pct(modele_counts[k], modele_total)
                 for k in ["Digital", "Mixte", "Physique"]],
    } if modele_total else {"labs": ["Digital", "Mixte", "Physique"], "vals": []}

    # Perception générale (retail)
    perc_col = "Assurance - Perception générale"
    perc_order = ["Très positive", "Plutôt positive", "Neutre", "Plutôt négative", "Très négative"]
    perc_colors = ["#00B86B", "#7BC67A", "#FFE600", "#FF8C42", "#B80C26"]
    perc_counts = {k: 0 for k in perc_order}
    perc_total = 0
    for v in retail[perc_col].dropna():
        nm = _normalize_perception(v)
        if nm and nm in perc_counts:
            perc_counts[nm] += 1
            perc_total += 1
    perc_labs = [k for k in perc_order if perc_counts[k] > 0]
    perc_vals = [_pct(perc_counts[k], perc_total) for k in perc_labs]
    perception = {"labs": perc_labs, "vals": perc_vals}

    # Degré de confiance (retail)
    conf_col = "Assurance - Degré de confiance"
    conf_order = ["Très faible", "Faible", "Moyen", "Fort", "Très fort"]
    conf_counts = {k: 0 for k in conf_order}
    conf_total = 0
    for v in retail[conf_col].dropna():
        nm = _normalize_confiance(v)
        if nm and nm in conf_counts:
            conf_counts[nm] += 1
            conf_total += 1
    conf_labs = [k for k in conf_order if conf_counts[k] > 0]
    conf_vals = [_pct(conf_counts[k], conf_total) for k in conf_labs]
    confiance = {"labs": conf_labs, "vals": conf_vals}

    # Top of Mind, Meilleure, Pire (retail)
    tom  = _top_companies(retail["Assurance - Top of Mind"])
    meil = _top_companies(retail["Assurance - Meilleure compagnie"])
    pire_col = "Assurance - Pire Compagnie "
    pire_raw = _top_companies(retail[pire_col])
    # Exclure NSP du classement pire (déjà filtré dans _top_companies)
    pire = pire_raw

    # Canal (retail)
    canal_ops = [
        "Souscrire à un contrat",
        "Déclarer un sinistre",
        "Demander une information",
        "Faire une réclamation",
        "Consulter mes contrats",
    ]
    canal_cols = [
        " Assurance - Souscrire à un contrat d'assurance",
        "Assurance - Déclarer un sinistre ",
        "Assurance - Demander une information",
        "Assurance - Faire une réclamation",
        "Assurance - Consulter mes contrats/mes sinistres ",
    ]
    canal_rows_data = {"Digital": [], "Mixte": [], "Physique": []}
    for ccol in canal_cols:
        if ccol in retail.columns:
            counts, total_c = _canal_row(retail, ccol)
            for mode in ["Digital", "Mixte", "Physique"]:
                canal_rows_data[mode].append(_pct(counts[mode], total_c) if total_c else 0)
        else:
            for mode in ["Digital", "Mixte", "Physique"]:
                canal_rows_data[mode].append(0)
    canal = {
        "ops": canal_ops,
        "rows": [
            {"label": mode, "vals": canal_rows_data[mode]}
            for mode in ["Digital", "Mixte", "Physique"]
        ],
    }

    # Satisfaction (retail)
    sat_ops = [
        "Souscription",
        "Couverture",
        "Remboursement",
        "Délais",
        "Qualité service",
        "Accompagnement",
        "Clarté",
    ]
    sat_cols = [
        "Assurance - Simplicité de la souscription",
        "Assurance - Couverture offerte",
        "Assurance - Simplicité des demandes remboursement",
        "Assurance - Délais de remboursement",
        "Assurance - Qualité du service",
        "Assurance -  Accompagnement et conseil",
        "Assurance - Clarté et transparence",
    ]
    sat_levels = ["Pas du tout satisfait", "Peu satisfait", "Neutre", "Satisfait", "Très satisfait"]
    sat_matrix = {lv: [] for lv in sat_levels}
    for scol in sat_cols:
        if scol in retail.columns:
            row = _satisfaction_row(retail[scol])
        else:
            row = [0, 0, 0, 0, 0]
        for i, lv in enumerate(sat_levels):
            sat_matrix[lv].append(row[i])
    satisfaction = {
        "ops": sat_ops,
        "rows": [
            {"label": lv, "vals": sat_matrix[lv]}
            for lv in sat_levels
        ],
    }

    return {
        "code":       company_code,
        "counts":     seg_counts,
        "segments":   segments,
        "entreprises": entreprises,
        "geo":        geo,
        "fiche": {
            "modeleIdeal":        modele_ideal,
            "perception":         perception,
            "confiance":          confiance,
            "topOfMind":          tom,
            "meilleureCompagnie": meil,
            "pireCompagnie":      pire,
            "canal":              canal,
            "satisfaction":       satisfaction,
        },
    }
