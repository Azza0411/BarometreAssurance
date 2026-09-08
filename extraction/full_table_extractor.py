"""Extraction "grille complète" d'un tableau annexe (toutes les lignes,
toutes les colonnes par branche) — contrairement à annexe12_kpi_extractor.py
et annexe13_kpi_extractor.py qui ne récupèrent QUE les 7 lignes/1 colonne
("Montant" total) dont les dashboards ont besoin.

Motivation (retour utilisateur, page Gestion de données) : l'export Excel
doit pouvoir montrer le tableau annexe tel qu'il existe réellement dans le
PDF source (toutes les branches — Automobile, Transport, Incendie...), pas
seulement le sous-ensemble déjà utilisé par les dashboards.

Principe (vérifié manuellement le 2026-09-08 sur GAT_2024.pdf, Annexe 13 —
16 colonnes par branche, valeurs recoupées avec la capture d'écran déjà
utilisée pour l'audit du Ratio Combiné dans cette session) :
  1. Repérer les positions X des VALEURS NUMÉRIQUES de toutes les lignes de
     données (fiables : une seule ligne de texte, jamais scindées sur
     plusieurs lignes visuelles) → ce sont les vrais centres de colonnes.
     Bien plus robuste que de partir des libellés d'en-tête, qui eux sont
     souvent repliés sur 2-3 lignes visuelles ("Responsabilité" / "civile",
     "Autres" / "dommages" / "aux" / "biens"...).
  2. Rattacher chaque MOT de l'en-tête (qui peut être réparti sur plusieurs
     lignes visuelles) à la colonne dont le centre est le plus proche de son
     x0, puis reconstituer le libellé de chaque colonne en triant ses mots
     par position verticale (haut → bas) — restitue l'ordre de lecture réel
     d'un libellé replié sur 2-3 lignes.
  3. Toute colonne du tableau totalement vide sur cette page (aucune valeur
     nulle part, ex. "Autres" chez GAT) n'a pas de centre déductible de
     l'étape 1 — son mot d'en-tête reste alors "non assigné" ; il est
     réinséré comme colonne à part entière (toutes valeurs = None) à sa
     position x réelle, pour ne pas la faire disparaître silencieusement du
     tableau restitué.

Limite connue : cette heuristique cible la mise en page des tableaux
Annexe 12/13 (et gabarits proches — même préambule "Société... / Annexe
N°X / titre / (exprimé en dinars tunisiens)" observé aussi sur les pages
"raccordement"/Etat de résultat technique). Le Bilan (Brut/Amortissement/
Net/Net N-1, pas de branches) et les tableaux Takaful (Annexes 14/15) ont
une structure différente et ne sont pas couverts par ce module pour
l'instant."""

from extraction.bilan_kpi_extractor import _cluster_lines, _extract_numeric_clusters, _normalizer
from extraction.annexe13_kpi_extractor import _label_text

MIN_DATA_CLUSTERS = 3   # une vraie ligne de donnees a au moins 3 colonnes remplies
COL_GAP = 6             # tolerance (pt) pour regrouper des x0 de valeurs en une colonne
ASSIGN_MAX_DIST = 25    # distance max (pt) pour rattacher un mot d'entete a une colonne


def _find_column_centers(lines, data_start_idx, gap=COL_GAP):
    all_x0 = []
    for line in lines[data_start_idx:]:
        for _val, x0 in _extract_numeric_clusters(line):
            all_x0.append(x0)
    all_x0.sort()
    centers, current = [], []
    for x in all_x0:
        if current and abs(x - current[-1]) <= gap:
            current.append(x)
        else:
            if current:
                centers.append(sum(current) / len(current))
            current = [x]
    if current:
        centers.append(sum(current) / len(current))
    return centers


def _nearest_index(x, centers, max_dist):
    best_i, best_d = None, max_dist + 1
    for i, c in enumerate(centers):
        d = abs(x - c)
        if d < best_d:
            best_d, best_i = d, i
    return best_i if best_d <= max_dist else None


def _build_columns(header_words, data_centers, max_dist=ASSIGN_MAX_DIST):
    """Rattache chaque mot d'en-tête à une colonne (centres déduits des
    données), reconstitue le libellé de chaque colonne, réinsère les
    colonnes sans aucune donnée (mot d'en-tête non assigné) à leur position
    réelle. Renvoie [(x_centre, libelle), ...] trié de gauche à droite."""
    from collections import defaultdict
    assigned = defaultdict(list)
    unassigned = []
    for w in header_words:
        idx = _nearest_index(w["x0"], data_centers, max_dist)
        if idx is not None:
            assigned[idx].append(w)
        else:
            unassigned.append(w)

    columns = []
    for i, c in enumerate(data_centers):
        ws = sorted(assigned.get(i, []), key=lambda w: (w["top"], w["x0"]))
        label = _normalizer.clean(" ".join(w["text"] for w in ws)) if ws else f"(colonne {i + 1})"
        columns.append((c, label))
    for w in unassigned:
        columns.append((w["x0"], _normalizer.clean(w["text"])))
    columns.sort(key=lambda t: t[0])
    return columns


def extract_full_table(page, min_data_clusters=MIN_DATA_CLUSTERS):
    """Extrait la grille complète (toutes lignes × toutes colonnes) d'une
    page de tableau annexe. Renvoie {"colonnes": [labels...], "lignes":
    {libelle_ligne: {colonne: valeur, ...}, ...}} ou None si la page ne
    ressemble pas à ce gabarit (aucune ligne multi-colonnes trouvée)."""
    words = page.extract_words()
    if not words:
        return None
    lines = _cluster_lines(words)

    first_data_idx = None
    for idx, line in enumerate(lines):
        if len(_extract_numeric_clusters(line)) >= min_data_clusters:
            first_data_idx = idx
            break
    if first_data_idx is None or first_data_idx == 0:
        return None

    # Bloc d'en-tête = les lignes juste avant la première ligne de données,
    # en excluant le préambule fixe (société/date, "Annexe N°X", titre,
    # unité) — sans quoi ses mots ("Annexe", "13", "exprime", "dinars"...)
    # se mêlent aux vraies colonnes. Ce préambule se termine de façon très
    # régulière par la ligne d'unité "(exprimé en dinars tunisiens)",
    # identique sur tous les gabarits Annexe/Bilan/Etat de résultat déjà
    # rencontrés — ancre bien plus fiable qu'une heuristique positionnelle
    # (la ligne société/date contient elle-même 2 nombres — jour + année —
    # qu'un simple "recule tant qu'il n'y a pas de nombre" confond avec une
    # frontière de tableau). Repli sur l'ancienne heuristique positionnelle
    # si ce marqueur, jamais garanti à 100%, est absent d'un gabarit non
    # encore rencontré.
    header_start = None
    for idx in range(min(first_data_idx, 6)):
        norm = _normalizer.clean(" ".join(w["text"] for w in lines[idx]))
        if "exprime en dinars" in norm:
            header_start = idx + 1
            break
    if header_start is None:
        header_start = 0
        for idx in range(first_data_idx - 1, -1, -1):
            if _extract_numeric_clusters(lines[idx]):
                header_start = idx + 1
                break
    header_words = [w for line in lines[header_start:first_data_idx] for w in line]

    data_centers = _find_column_centers(lines, first_data_idx)
    if not data_centers:
        return None
    columns = _build_columns(header_words, data_centers)
    col_names = [name for _x, name in columns]
    col_centers_final = [x for x, _name in columns]

    rows = {}
    for line in lines[first_data_idx:]:
        clusters = _extract_numeric_clusters(line)
        if not clusters:
            continue
        label = _label_text(line)
        if not label:
            continue
        row_values = {}
        for val, x0 in clusters:
            idx = _nearest_index(x0, col_centers_final, ASSIGN_MAX_DIST)
            if idx is not None:
                row_values[col_names[idx]] = val
        if row_values:
            # Deux lignes de libellé identique (rare, ex. sous-totaux
            # répétés) : la seconde écraserait la première — suffixée pour
            # ne perdre aucune ligne réelle du document.
            key = label
            n = 2
            while key in rows:
                key = f"{label} ({n})"
                n += 1
            rows[key] = row_values

    return {"colonnes": [c for c in col_names if c.strip()], "lignes": rows}
