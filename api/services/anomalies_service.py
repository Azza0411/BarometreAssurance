"""
Service centralisé — Anomalies Système.

Enrichit les données du pipeline_audit avec :
  - Catégorie (type) d'anomalie
  - Gravité data-quality (Critique / Élevée / Moyenne / Faible)
  - Recommandation générée
  - Score qualité par compagnie et global
  - Historique multi-années
  - Rapport structuré (markdown)
"""

import os
import re
import datetime
from collections import Counter

from dotenv import load_dotenv

from database.repository import get_connection, get_quality_score_history, list_documents_by_source
from api.services.pipeline_audit import build_pipeline_audit

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

# "llama-3.3-70b-versatile" retire du catalogue Groq (verifie le
# 2026-08-18, reponse API 404 model_not_found) -- voir meme constante dans
# chatbot_portable/app.py::GROQ_MODEL pour le detail de la decouverte.
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "cmf",
)

# ── Classification par étape pipeline ────────────────────────────────────────
_TYPE_PAR_ETAPE = {
    1: "Scraping / Collecte",
    2: "Extraction PDF",
    3: "Extraction PDF",
    4: "Transformation",
    5: "Extraction PDF",
    6: "Validation",
    7: "Cohérence des données",  # deseq. Bilan / variation YoY, voir pipeline_audit.py
    8: "Validation",             # doublure RC≈RF, voir quality.py
    9: "Validation",             # écart sectoriel, voir quality.py
}

_DQ_GRAVITE_PAR_ETAPE = {
    1: "Critique",
    2: "Élevée",
    3: "Moyenne",
    4: "Faible",
    5: "Moyenne",
    6: "Élevée",
    7: "Élevée",
    8: "Moyenne",
    9: "Moyenne",
}

_PENALITE = {
    "Critique": 12,
    "Élevée":   5,
    "Moyenne":  2,
    "Faible":   0.5,
}

# ── Génération de recommandation ──────────────────────────────────────────────
def _recommandation(p: dict) -> str:
    etape = p.get("etape", 0)
    code  = p.get("code", "")
    kpi   = p.get("kpi", "")
    comps = p.get("composantes_manquantes", [])

    if etape == 1:
        return (
            f"Télécharger le rapport annuel {p.get('annee')} de {code} depuis le portail CMF "
            f"et le déposer dans data/cmf/{code}/. "
            "Vérifier que le scraper est configuré pour cette compagnie."
        )
    if etape == 2:
        sec = p.get("details", "")
        return (
            f"La section PDF n'a pas été détectée pour {code}. "
            "Ouvrir le PDF manuellement et vérifier que le libellé du titre de section "
            "correspond aux patterns de pdf_sections.py. "
            "Si le rapport est dans un format différent des années précédentes, "
            "ajouter un nouveau pattern dans _WEIGHTED_PATTERNS."
        )
    if etape == 3:
        comp = comps[0] if comps else kpi
        return (
            f"La composante « {comp} » n'a pas été trouvée dans le tableau PDF. "
            "Vérifier la normalisation du libellé (accents, retours à la ligne, "
            "abréviations). Consulter extraction/CAS_PARTICULIERS.md pour les cas connus."
        )
    if etape == 4:
        return (
            f"Le KPI « {kpi} » a été estimé avec des composantes partielles. "
            "Vérifier les composantes manquantes et si possible les extraire manuellement. "
            "La valeur estimée peut diverger de la valeur officielle."
        )
    if etape == 5:
        return (
            f"La valeur brute de « {kpi} » est absente. "
            "Vérifier que l'extracteur couvre ce libellé dans le tableau correspondant. "
            "Comparer le libellé dans le PDF avec les patterns de l'extracteur Python."
        )
    if etape == 6:
        val = p.get("valeur")
        return (
            f"La valeur {val} est hors plage métier. "
            "Ouvrir le PDF source, localiser la cellule et vérifier si l'unité est correcte "
            "(DT vs milliers DT), ou si le décalage de colonne a récupéré une mauvaise valeur. "
            "Utiliser la fonctionnalité de surlignage PDF dans la page Traçabilité KPI."
        )
    if etape == 7:
        return (
            f"{p.get('raison', '')} Vérifier la ligne « {kpi} » dans le PDF source de {code} "
            f"({p.get('annee')}) — cette anomalie a été détectée automatiquement pendant "
            "l'extraction (voir extraction/CAS_PARTICULIERS.md pour les cas déjà connus), "
            "pas recalculée à l'affichage."
        )
    if etape == 8:
        return (
            f"{p.get('raison', '')} Ratio combiné et Ratio de frais quasi identiques : "
            "probable erreur d'extraction où la même cellule PDF a été lue pour les deux "
            "KPI. Vérifier dans la page Traçabilité KPI que « Ratio combiné » et « Ratio "
            "de frais de gestion » pointent bien vers des lignes différentes du tableau."
        )
    if etape == 9:
        return (
            f"{p.get('raison', '')} Valeur individuellement plausible mais très atypique "
            "par rapport aux autres compagnies la même année : à documenter comme "
            "spécificité réelle de la société, ou signe d'une extraction encore fautive "
            "non détectée par les autres contrôles. Comparer avec le PDF source via la "
            "page Traçabilité KPI."
        )
    return "Analyser le pipeline pour identifier la cause racine."


def _enrich(p: dict) -> dict:
    etape = p.get("etape", 0)
    return {
        **p,
        "type":        _TYPE_PAR_ETAPE.get(etape, "Inconnu"),
        "dq_gravite":  _DQ_GRAVITE_PAR_ETAPE.get(etape, "Faible"),
        "recommandation": _recommandation(p),
        "statut": "Nouveau",   # Toujours "Nouveau" — aucune DB de statuts pour l'instant
        "source": f"Pipeline étape {etape}",
    }


_SEVERITY_WEIGHT = {"Critique": 4, "Élevée": 2, "Moyenne": 1, "Faible": 0.5}

def _quality_score(problemes: list, n_kpis_total: int = 200) -> float:
    """Score 0–100.

    weighted_impact = Σ poids_gravité / n_kpis_total
    score = max(0, 100 × (1 − weighted_impact))

    Interprétation : une pénalité de 1 = 1 KPI Élevé absent / 200 KPIs référence = 0,5 pt déduit.
    """
    if not problemes:
        return 100.0
    weighted = sum(
        _SEVERITY_WEIGHT.get(_DQ_GRAVITE_PAR_ETAPE.get(p.get("etape", 0), "Faible"), 1)
        for p in problemes
    )
    fraction = weighted / max(n_kpis_total, 1)
    raw = max(0.0, 100.0 * (1.0 - fraction))
    return round(raw, 1)


def _get_years_available(conn) -> list[int]:
    docs = list_documents_by_source(conn, "CMF")
    return sorted({doc_annee for _, _, _, doc_annee in docs}, reverse=True)


def build_anomalies_systeme(conn, annee: int) -> dict:
    """Données enrichies pour la page Anomalies Système."""
    audit = build_pipeline_audit(conn, annee)
    problemes = audit.get("problemes", [])
    enriched  = [_enrich(p) for p in problemes]

    # ── KPIs globaux ──────────────────────────────────────────────────────────
    n_pdfs = sum(
        1 for code in os.listdir(_DATA_DIR)
        if os.path.isfile(os.path.join(_DATA_DIR, code, f"{code}_{annee}.pdf"))
    ) if os.path.isdir(_DATA_DIR) else 0

    score = _quality_score(problemes)

    dq_gravite_counts = {}
    for p in enriched:
        g = p["dq_gravite"]
        dq_gravite_counts[g] = dq_gravite_counts.get(g, 0) + 1

    type_counts = {}
    for p in enriched:
        t = p["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    # ── Top 5 anomalies les plus fréquentes ──────────────────────────────────
    from collections import Counter
    kpi_counts = Counter(p["kpi"] for p in enriched)
    top5 = [
        {"kpi": kpi, "count": cnt, "gravite": max(
            (p["dq_gravite"] for p in enriched if p["kpi"] == kpi),
            key=lambda g: ["Faible","Moyenne","Élevée","Critique"].index(g)
        )}
        for kpi, cnt in kpi_counts.most_common(5)
    ]

    # ── Classement des sources par score qualité ──────────────────────────────
    from collections import defaultdict
    code_probs = defaultdict(list)
    for p in enriched:
        code_probs[p["code"]].append(p)

    source_ranking = []
    for code, probs in code_probs.items():
        s = _quality_score(probs, n_kpis_total=20)
        source_ranking.append({"code": code, "score": s, "n_anomalies": len(probs)})
    source_ranking.sort(key=lambda x: x["n_anomalies"], reverse=True)

    # ── Historique ────────────────────────────────────────────────────────────
    # Instantanés réels persistés par pipelines/run_pipeline.py::_check_quality()
    # à chaque exécution planifiée (table anomalies_detectees, voir
    # database/repository.py::get_quality_score_history) — une vraie tendance
    # s'accumule désormais exécution après exécution. Avant juillet 2026,
    # rien n'était persisté : seul le point du jour courant pouvait être
    # affiché (fabriqué à chaque requête, jamais de tendance). Repli sur ce
    # même point du jour tant qu'aucun instantané n'a encore été persisté
    # (avant la toute première exécution planifiée après cette mise à jour).
    persisted = get_quality_score_history(conn, annee=annee)
    if persisted:
        historique = [
            {
                "date":  pt["date"],
                "label": datetime.datetime.fromisoformat(pt["date"]).strftime("%d/%m"),
                "score": pt["score"],
                "n_anomalies": pt["n_anomalies"],
            }
            for pt in persisted
        ]
    else:
        today = datetime.date.today()
        historique = [{
            "date":  today.isoformat(),
            "label": today.strftime("%d/%m"),
            "score": score,
            "n_anomalies": len(enriched),
        }]

    return {
        "annee": annee,
        "kpis": {
            "documents_analyses": n_pdfs,
            "n_anomalies": len(enriched),
            "score_qualite": score,
            "derniere_analyse": datetime.date.today().isoformat(),
        },
        "anomalies":        enriched,
        "par_type":         type_counts,
        "par_dq_gravite":   dq_gravite_counts,
        "top5":             top5,
        "source_ranking":   source_ranking,
        "historique":       historique,
    }


def _generate_rapport_template(conn, annee: int) -> str:
    """Génère un rapport structuré markdown à partir des données d'audit —
    entièrement à base de texte statique (aucun appel IA). Utilisé comme
    repli si le rapport généré par IA générative (voir generate_rapport_ia
    ci-dessous) échoue ou si Groq est indisponible."""
    audit   = build_pipeline_audit(conn, annee)
    probs   = audit.get("problemes", [])
    enriched = [_enrich(p) for p in probs]
    score   = _quality_score(probs)

    n_crit   = sum(1 for p in enriched if p["dq_gravite"] == "Critique")
    n_elev   = sum(1 for p in enriched if p["dq_gravite"] == "Élevée")
    n_moy    = sum(1 for p in enriched if p["dq_gravite"] == "Moyenne")
    n_faib   = sum(1 for p in enriched if p["dq_gravite"] == "Faible")
    n_comp   = audit.get("n_compagnies_affectees", 0)

    type_counts = {}
    for p in enriched:
        t = p["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    from collections import Counter
    kpi_counts = Counter(p["kpi"] for p in probs)
    top_kpis   = kpi_counts.most_common(5)

    code_counts = Counter(p["code"] for p in probs)
    top_codes   = code_counts.most_common(5)

    # Analyse des causes par type
    causes_extraction = [p for p in enriched if p["etape"] in (2, 3, 5)]
    causes_aberrantes = [p for p in enriched if p["etape"] == 6]
    causes_manquantes = [p for p in enriched if p["etape"] == 1]

    today = datetime.date.today().strftime("%d/%m/%Y")

    rapport = f"""# Rapport d'anomalies Système — Exercice {annee}

**Généré le** : {today}
**Source** : Pipeline d'extraction EY · FS Market Intelligence · Tunisie
**Confidentiel** — Usage interne EY uniquement

---

## 1. Résumé exécutif

L'analyse du pipeline de données pour l'exercice **{annee}** a révélé **{len(probs)} anomalies**
affectant **{n_comp} compagnies** sur les {audit.get("compagnies_affectees", []) and len(audit["compagnies_affectees"])} analysées.

Le **score de qualité global des données** est de **{score}/100**, reflétant des lacunes
significatives dans l'extraction PDF et la transformation des indicateurs clés.

| Niveau de gravité | Anomalies | Impact |
|---|---|---|
| Critique | {n_crit} | Blocage total de l'indicateur |
| Élevée | {n_elev} | Valeur absente ou erronée |
| Moyenne | {n_moy} | Indicateur partiel ou estimé |
| Faible | {n_faib} | Estimation avec données incomplètes |

---

## 2. Statistiques des anomalies

### Répartition par étape du pipeline

"""
    for etape_label, count in audit.get("par_etape", {}).items():
        pct = round(count / max(1, len(probs)) * 100)
        rapport += f"- **{etape_label}** : {count} anomalies ({pct} %)\n"

    rapport += f"""
### Répartition par type d'anomalie

"""
    for t, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
        rapport += f"- **{t}** : {cnt} cas\n"

    rapport += f"""
---

## 3. Tendances observées

L'étape **« {max(audit.get("par_etape", {}).items(), key=lambda x: x[1], default=("N/A",0))[0]} »**
représente la majorité des anomalies détectées ({max(audit.get("par_etape", {}).values(), default=0)} cas),
ce qui indique une fragilité structurelle dans cette phase du pipeline.

"""
    if causes_extraction:
        rapport += f"- **{len(causes_extraction)} anomalies d'extraction** : les patterns de détection des libellés " \
                   "dans les tableaux PDF doivent être mis à jour pour accommoder les variations de format entre compagnies.\n"
    if causes_aberrantes:
        codes_ab = list({p["code"] for p in causes_aberrantes})
        rapport += f"- **{len(causes_aberrantes)} valeurs aberrantes** détectées chez : {', '.join(codes_ab)}. " \
                   "Probable décalage de colonne ou erreur d'unité dans l'extraction.\n"
    if causes_manquantes:
        codes_miss = list({p["code"] for p in causes_manquantes})
        rapport += f"- **{len(causes_manquantes)} PDF absents** pour : {', '.join(codes_miss)}. " \
                   "Le scraping n'a pas couvert ces compagnies.\n"

    rapport += f"""
---

## 4. Analyse des causes principales

### 4.1 Problèmes d'extraction PDF

Les sections Annexe 12 et Annexe 13 (résultats techniques) présentent le taux d'échec
d'extraction le plus élevé. Les causes identifiées sont :

1. **Variabilité des mises en page** : chaque compagnie utilise sa propre mise en page,
   ce qui rend les patterns génériques insuffisants.
2. **Cellules fusionnées** : les en-têtes fusionnés (ex. « Automobile » sur 2 colonnes)
   décalent l'indexation des cellules dans pdfplumber.
3. **Encodages non standards** : certains PDF utilisent des polices avec mapping Unicode
   non conventionnel, dégradant l'extraction textuelle.

### 4.2 Valeurs aberrantes

Les valeurs hors plage métier sont généralement dues à :
- Extraction de la mauvaise colonne (décalage dû à des cellules fusionnées)
- Unité incorrecte (montants en milliers TND extraits comme TND)
- Signe inversé (résultat négatif présenté en valeur absolue dans le tableau)

---

## 5. Compagnies les plus impactées

"""
    for code, cnt in top_codes:
        rapport += f"- **{code}** : {cnt} anomalies\n"

    rapport += f"""
---

## 6. Risques pour les dashboards

| Risque | Probabilité | Impact |
|---|---|---|
| KPI manquant affiché comme vide | Haute | Comparaison sectorielle incomplète |
| Valeur aberrante intégrée au calcul de moyenne | Faible | Distorsion des indicateurs sectoriels |
| Part de marché calculée avec données partielles | Moyenne | Classement compagnies erroné |
| ROE/ROA erronés pour compagnies recalculées | Moyenne | Analyse de profitabilité biaisée |

---

## 7. Recommandations d'amélioration

### Court terme (< 1 mois)
1. **Vérifier manuellement** les {n_elev} anomalies de gravité Élevée et corriger les valeurs en base.
2. **Télécharger** les PDF manquants pour les {n_crit} anomalies Critiques.
3. **Relancer l'extraction** sur les pages identifiées après correction des patterns.

### Moyen terme (1–3 mois)
1. **Enrichir les patterns** de détection de sections en couvrant les variantes de libellés
   identifiées lors des audits manuels.
2. **Implémenter un test de régression** : vérifier que chaque release ne dégrade pas
   le taux d'extraction sur les PDF historiques.
3. **Créer un module de validation** post-extraction qui flag automatiquement les valeurs
   hors plage avant insertion en base.

### Long terme (3–6 mois)
1. **Migration vers une extraction hybride** : combiner pdfplumber (tableaux) + OCR (Tesseract)
   pour les PDF scannés ou à mise en page complexe.
2. **Base de connaissance des cas particuliers** : documenter systématiquement chaque variante
   de format dans CAS_PARTICULIERS.md avec le code de fix appliqué.
3. **Dashboard de monitoring en temps réel** : déclencher une alerte qualité après chaque
   scraping/extraction en comparant les scores avec l'historique.

---

*Rapport généré automatiquement par EY FS Market Intelligence — Pipeline d'extraction v2.0*
*Données sources : CMF · FTUSA · {annee}*
"""
    return rapport


# ── Nombres autorisés à apparaître dans une phrase générée par le LLM ──────────
# Un chiffre "autorisé" est soit un des faits fournis en entrée (comptages,
# score, pourcentages dérivés), soit un petit entier générique (numérotation
# de liste, année, pourcentage rond) qui n'a pas besoin d'être sourcé.
_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def _allowed_numbers(stats: dict) -> set[str]:
    """Construit l'ensemble des valeurs numériques que le LLM a le droit de
    citer, à partir des faits qu'on lui a réellement fournis dans le prompt
    (voir _build_llm_facts). Comparé en tant que chaînes normalisées
    (virgule/point, pas de zéro inutile) pour tolérer les reformulations
    superficielles ("12 %" vs "12,0 %")."""
    allowed = set()
    for v in stats.values():
        if isinstance(v, (int, float)):
            allowed.add(_normalize_number(v))
        elif isinstance(v, str):
            for match in _NUMBER_RE.finditer(v):
                allowed.add(_normalize_number(float(match.group())))
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], (int, float)):
                    allowed.add(_normalize_number(item[1]))
                elif isinstance(item, str):
                    for match in _NUMBER_RE.finditer(item):
                        allowed.add(_normalize_number(float(match.group())))
    # Nombres génériques toujours tolérés : années plausibles, petits entiers
    # de mise en forme (numérotation "1.", "2.", pourcentages ronds usuels),
    # et "100" (dénominateur systématique du score de qualité "X/100").
    for y in range(2013, 2031):
        allowed.add(str(y))
    for n in range(0, 10):
        allowed.add(str(n))
    allowed.add("100")
    return allowed


def _normalize_number(value) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).replace(",", ".")


def _check_grounding(text: str, stats: dict) -> list[str]:
    """Renvoie la liste des nombres cités dans `text` qui ne correspondent à
    AUCUN chiffre fourni en entrée au LLM (voir _allowed_numbers) — un
    nombre "orphelin" est un signal fort d'invention (hallucination), le
    LLM n'ayant reçu aucune autre source de chiffres. Garde-fou ajouté le
    2026-08-18 après avoir constaté, sur la fonctionnalité de prévision de
    KPI, que le modèle invente des faits plausibles (une fusion de sociétés,
    un cadre réglementaire fictif) quand on lui demande d'être "concret"
    sans lui fournir la donnée correspondante — même risque ici pour un
    rapport destiné à un consultant."""
    allowed = _allowed_numbers(stats)
    orphans = []
    for match in _NUMBER_RE.finditer(text):
        token = match.group().replace(",", ".")
        try:
            normalized = _normalize_number(float(token))
        except ValueError:
            continue
        if normalized not in allowed and token not in allowed:
            orphans.append(match.group())
    return orphans


def _build_llm_facts(annee: int, enriched: list, score: int, n_comp: int) -> dict:
    """Chiffres et échantillons de texte RÉELS (déjà calculés/extraits, pas
    inventés) mis à disposition du LLM pour rédiger le rapport — c'est
    l'unique matière première autorisée (voir _check_grounding)."""
    n_crit = sum(1 for p in enriched if p["dq_gravite"] == "Critique")
    n_elev = sum(1 for p in enriched if p["dq_gravite"] == "Élevée")
    n_moy = sum(1 for p in enriched if p["dq_gravite"] == "Moyenne")
    n_faib = sum(1 for p in enriched if p["dq_gravite"] == "Faible")
    type_counts = Counter(p["type"] for p in enriched)
    kpi_counts = Counter(p["kpi"] for p in enriched)
    code_counts = Counter(p["code"] for p in enriched)
    # Échantillon de causes RÉELLEMENT détectées (texte déjà généré
    # déterministement par _recommandation()/pipeline_audit.py, jamais par
    # le LLM) — matière première pour la section "causes", pas une source
    # que le LLM doit compléter de son cru.
    sample_causes = [
        f"{p['code']} {p['annee']} — {p['kpi']} : {p['raison']}"
        for p in enriched[:8]
    ]
    return {
        "annee": annee,
        "n_anomalies": len(enriched),
        "n_compagnies_affectees": n_comp,
        "score_qualite": score,
        "n_critique": n_crit,
        "n_elevee": n_elev,
        "n_moyenne": n_moy,
        "n_faible": n_faib,
        "par_type": list(type_counts.most_common()),
        "top5_kpis": kpi_counts.most_common(5),
        "top5_codes": code_counts.most_common(5),
        "echantillon_causes": sample_causes,
    }


def _call_groq_report(facts: dict) -> str | None:
    try:
        from groq import Groq
    except ImportError:
        return None
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None

    facts_text = (
        f"Exercice : {facts['annee']}\n"
        f"Nombre total d'anomalies : {facts['n_anomalies']}\n"
        f"Compagnies affectées : {facts['n_compagnies_affectees']}\n"
        f"Score de qualité global : {facts['score_qualite']}/100\n"
        f"Répartition par gravité : Critique={facts['n_critique']}, "
        f"Élevée={facts['n_elevee']}, Moyenne={facts['n_moyenne']}, "
        f"Faible={facts['n_faible']}\n"
        f"Répartition par type : {facts['par_type']}\n"
        f"Top 5 KPI les plus touchés : {facts['top5_kpis']}\n"
        f"Top 5 compagnies les plus touchées : {facts['top5_codes']}\n"
        f"Échantillon de causes réellement détectées (à résumer, pas à "
        f"compléter) :\n" + "\n".join(f"- {c}" for c in facts["echantillon_causes"])
    )

    system_prompt = (
        "Tu es un analyste qualité de données senior chez EY Tunisie. "
        "Rédige un rapport d'anomalies en 3 parties courtes, en français, "
        "ton professionnel de conseil :\n"
        "1. ## Résumé exécutif (3-4 phrases)\n"
        "2. ## Tendances et causes principales (résume l'échantillon de "
        "causes fourni, ne l'invente pas — 4-6 phrases)\n"
        "3. ## Recommandations (3 recommandations concrètes et actionnables, "
        "priorisées selon la répartition par gravité fournie)\n\n"
        "RÈGLES STRICTES :\n"
        "- N'utilise QUE les chiffres fournis ci-dessous. N'invente aucun "
        "chiffre, pourcentage, date ou statistique supplémentaire.\n"
        "- N'invente aucune cause technique, aucun nom de société, aucun "
        "événement ou texte réglementaire absent des données fournies.\n"
        "- Si l'échantillon de causes ne permet pas d'identifier un motif "
        "clair, dis-le explicitement plutôt que d'en inventer un.\n"
        "- Format Markdown, maximum 300 mots au total."
    )
    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": facts_text},
            ],
            max_tokens=800,
            temperature=0.1,
        )
        return resp.choices[0].message.content
    except Exception:
        return None


def generate_rapport_ia(conn, annee: int) -> str:
    """Génère le rapport d'anomalies : les tableaux de chiffres sont
    calculés directement (jamais reformulés par le LLM, donc jamais
    faussés), le récit (résumé/tendances/recommandations) est rédigé par
    Groq à partir de ces mêmes chiffres puis vérifié (_check_grounding)
    avant d'être inséré — tout nombre cité par le LLM qui ne provient pas
    des données fournies fait basculer sur le rapport 100% statique
    (_generate_rapport_template) plutôt que de risquer un chiffre inventé
    dans un rapport destiné à un consultant."""
    audit = build_pipeline_audit(conn, annee)
    probs = audit.get("problemes", [])
    enriched = [_enrich(p) for p in probs]
    score = _quality_score(probs)
    n_comp = audit.get("n_compagnies_affectees", 0)

    facts = _build_llm_facts(annee, enriched, score, n_comp)
    llm_text = _call_groq_report(facts)

    if llm_text:
        orphans = _check_grounding(llm_text, facts)
        if orphans:
            import logging
            logging.getLogger(__name__).warning(
                f"Rapport IA rejeté (nombres non sourcés détectés: {orphans}) "
                f"— repli sur le rapport statique."
            )
            llm_text = None

    if not llm_text:
        return _generate_rapport_template(conn, annee)

    today = datetime.date.today().strftime("%d/%m/%Y")
    return (
        f"# Rapport d'anomalies Système — Exercice {annee}\n\n"
        f"**Généré le** : {today} · **IA générative (Groq/{GROQ_MODEL})**\n"
        f"**Source** : Pipeline d'extraction EY · FS Market Intelligence · Tunisie\n"
        f"**Confidentiel** — Usage interne EY uniquement\n\n---\n\n"
        f"{llm_text}\n\n---\n\n"
        f"## Détail chiffré\n\n"
        f"| Niveau de gravité | Anomalies |\n|---|---|\n"
        f"| Critique | {facts['n_critique']} |\n"
        f"| Élevée | {facts['n_elevee']} |\n"
        f"| Moyenne | {facts['n_moyenne']} |\n"
        f"| Faible | {facts['n_faible']} |\n\n"
        f"**Score de qualité global** : {score}/100 · "
        f"**{len(probs)} anomalies** sur **{n_comp} compagnies**\n\n"
        f"*Rapport généré automatiquement par EY FS Market Intelligence — "
        f"Pipeline d'extraction v2.0*\n*Données sources : CMF · FTUSA · {annee}*\n"
    )
