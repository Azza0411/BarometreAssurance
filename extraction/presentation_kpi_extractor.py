"""
Extraction de KPI à partir du paragraphe narratif "PRESENTATION DE LA
SOCIETE" (ou équivalent), et non d'un tableau : chaque KPI correspond à une
ligne à puce "Libellé : Valeur" du bloc d'identité de la société, en tête des
notes aux états financiers.

KPI extraits :
  - "Date de création"  (texte)  <- ligne "Date de constitution"/"Date de création"
  - "Nombre d'actions"  (nombre) <- nombre d'actions cité sur la ligne "Capital social"
  - "Siège social"      (texte)  <- ligne "Siège social"
  - "Effectif"          (nombre) <- ligne "Effectif"

"Cours de l'action" est volontairement exclu : la seule valeur disponible à
cet endroit est la valeur nominale de l'action (ex: "10D chacune"), pas un
cours de bourse réel -> à traiter plus tard via une source boursière (BVMT).

Détection par ":" plutôt que par mots-clés isolés : chaque ligne candidate
est coupée sur son premier ":", et seul le texte AVANT (le libellé) est
comparé aux motifs ci-dessous. Ceci évite les faux positifs (ex: le mot
"effectif" employé comme nom commun ailleurs dans le document) puisqu'une
correspondance n'est retenue que si le libellé complet avant les ":"
correspond au motif.

Voir extraction/CAS_PARTICULIERS_PRESENTATION.md pour les formats de
présentation rencontrés qui ne suivent pas ce schéma "Libellé : Valeur"
(paragraphes narratifs chez LLOYD_TUNISIEN et TUNIS_RE, section introuvable
chez ATTIJARI et GAT) et les valeurs non chiffrées (capital social écrit en
toutes lettres chez COMAR, effectif détaillé par catégorie plutôt que total
chez COMAR).
"""

import re

from extraction.bilan_kpi_extractor import _normalizer

MAX_PAGES_SCANNED = 25

LABEL_PATTERNS = {
    "Date de création": re.compile(r"^date de (constitution|creation)\b"),
    "Nombre d'actions": re.compile(r"^capital social\b"),
    "Siège social": re.compile(r"^siege social\b"),
    "Effectif": re.compile(r"^effectif\b"),
}

ACTIONS_COUNT_RE = re.compile(r"(\d[\d\s.,]*\d|\d)\s*actions", re.IGNORECASE)
LEADING_NUMBER_RE = re.compile(r"\d[\d\s.,]*\d|\d")

KPI_NAMES = list(LABEL_PATTERNS.keys())


def _clean_number(raw):
    digits = re.sub(r"[.,\s]", "", raw)
    return float(digits) if digits else None


def _split_label_value(line):
    if ":" not in line:
        return None, None
    label, _, value = line.partition(":")
    return _normalizer.clean(label), value.strip()


def extract_presentation_kpis(pdf):
    """Renvoie {"Date de création", "Nombre d'actions", "Siège social",
    "Effectif"} -> valeur|None (texte pour les deux premiers, nombre pour
    les deux derniers)."""
    found = {}
    for page in pdf.pages[:MAX_PAGES_SCANNED]:
        text = page.extract_text() or ""
        if not text:
            continue
        for raw_line in text.split("\n"):
            label, value = _split_label_value(raw_line.strip())
            if label is None or not value:
                continue
            for kpi_name, pattern in LABEL_PATTERNS.items():
                if kpi_name in found or not pattern.search(label):
                    continue
                if kpi_name in ("Date de création", "Siège social"):
                    found[kpi_name] = value
                elif kpi_name == "Nombre d'actions":
                    m = ACTIONS_COUNT_RE.search(value)
                    if m:
                        found[kpi_name] = _clean_number(m.group(1))
                elif kpi_name == "Effectif":
                    m = LEADING_NUMBER_RE.search(value)
                    if m:
                        found[kpi_name] = _clean_number(m.group(0))
        if len(found) == len(LABEL_PATTERNS):
            break
    return {name: found.get(name) for name in KPI_NAMES}
