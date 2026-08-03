"""
Scanne un PDF CMF local et retourne les numéros de page (1-indexed)
de chaque grande section (Annexe 12, Annexe 13, Bilan, État de résultat).

Stratégie robuste :
  - Chaque pattern a un POIDS (pas juste 1).
  - Les patterns à fort poids identifient la page du TABLEAU réel
    (en-têtes de colonnes, libellés de lignes spécifiques).
  - Les mentions dans une TOC ("Annexe N°12") ont un poids faible.
  - Score net = score_section − score_section_concurrente (évite
    qu'une page TOC mentionnant les deux annexes batte le vrai tableau).
  - Contrainte d'ordre : annexe12 doit précéder annexe13 dans le PDF.
"""

import os
import re
import unicodedata
import pdfplumber

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "cmf"
)

# (poids, pattern) — le poids reflète à quel point le pattern est discriminant.
# Les patterns à fort poids (3-5) n'apparaissent QUE dans le vrai tableau,
# jamais dans une TOC ou dans la section concurrente.
_WEIGHTED_PATTERNS: dict[str, list[tuple[int, str]]] = {
    "annexe12": [
        # Titre de la section — "Annexe n°12", "Annexe n12", "(annexe 12)"...
        # (le "n" et le séparateur "°"/"." sont optionnels : la ponctuation
        # varie beaucoup d'une compagnie/vintage à l'autre dans les PDF CMF
        # réels — voir CAS_PARTICULIERS_PDF_SECTIONS.md). Poids fort : ce
        # texte n'apparaît en pratique que sur la page-titre du tableau lui-
        # même ou dans une mention isolée ("voir annexe n°12"), jamais de
        # façon répétée — c'est la combinaison avec les patterns ci-dessous
        # (vocabulaire du tableau) qui départage les deux cas.
        (5, r"annexe\s*n?\.?\s*12(?!\d)"),
        # Sous-titre de section — discriminant
        (4, r"categorie d.assurance vie"),
        (3, r"resultat technique.*vie|vie.*resultat technique"),
        # En-têtes de colonnes du tableau Vie — table only
        (5, r"vie individuelle"),
        (5, r"vie collective"),
        (3, r"capitalisation"),
        # Libellés de lignes spécifiques Vie
        (3, r"primes emises.*vie|vie.*primes emises"),
        (2, r"charges de prestations vie|prestations vie"),
    ],
    "annexe13": [
        (5, r"annexe\s*n?\.?\s*13(?!\d)"),
        (4, r"categorie d.assurance non.?vie"),
        (3, r"resultat technique.*non.?vie|non.?vie.*resultat technique"),
        # En-têtes de colonnes Non-Vie — table only
        (5, r"\bautomobile\b"),
        (5, r"\bincendie\b"),
        (4, r"responsabilite civile|\brc\s+general\b"),
        (4, r"\btransport\b"),
        (3, r"accidents de travail|accidents corporels"),
        # Libellés lignes Non-Vie
        (3, r"primes acquises"),
        (2, r"sinistres payes|charges de sinistres"),
    ],
    "bilan": [
        (3, r"bilan au 31"),
        (3, r"bilan arrete au"),
        (3, r"actif du bilan"),
        (4, r"total de l.actif"),
        (4, r"capitaux propres"),
        (2, r"immobilisations"),
    ],
    # Page Passif du Bilan : sur les PDF CMF, le Bilan est presque toujours
    # scinde en 2 pages (Actif, puis Capitaux propres + Passif) - une seule
    # page ne suffit pas pour localiser "Capitaux propres", "Total du
    # Passif", "Autres passifs", "Provisions techniques brutes"...
    "bilan_passif": [
        (4, r"capitaux propres et le passif"),
        (3, r"total du passif"),
        (3, r"total des capitaux propres et du passif"),
        (2, r"provisions techniques brutes"),
    ],
    "etat_resultat": [
        (3, r"etat de resultat arrete|l.etat de resultat arrete"),
        (3, r"compte de resultat"),
        (3, r"resultat net de l.exercice"),
        (2, r"rtnv resultat technique"),
        (2, r"produits des placements"),
    ],
}

# Score brut minimum pour être candidat (filtre les mentions isolées dans TOC)
_MIN_RAW_SCORE = {
    "annexe12":      6,   # au moins un pattern fort (vie individuelle=5) + mention
    "annexe13":      6,
    "bilan":         3,
    "bilan_passif":  3,
    "etat_resultat": 3,
}

# Sections concurrentes — on soustrait leur score pour obtenir le score NET
_RIVALS: dict[str, str] = {
    "annexe12": "annexe13",
    "annexe13": "annexe12",
}

_cache: dict = {}


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_str.lower())


def _raw_score(text_norm: str, section: str) -> int:
    return sum(w for w, p in _WEIGHTED_PATTERNS[section] if re.search(p, text_norm))


def get_pdf_sections(code: str, annee: int) -> dict:
    """
    Retourne {section: page_number (1-indexed)} pour un PDF CMF.
    Sections possibles : annexe12, annexe13, bilan (Actif), bilan_passif
    (Capitaux propres + Passif), etat_resultat.
    """
    key = (code.upper(), int(annee))
    if key in _cache:
        return _cache[key]

    path = os.path.join(DATA_DIR, code.upper(), f"{code.upper()}_{annee}.pdf")
    if not os.path.isfile(path):
        _cache[key] = {}
        return {}

    # best[section] = (net_score, raw_score, page_1indexed)
    best: dict[str, tuple[int, int, int]] = {}
    pages_text: list[str] = []

    # Patterns REQUIS : une page doit contenir au moins un de ces patterns
    # pour être candidate. Ces termes n'apparaissent QUE dans le corps du tableau,
    # jamais dans une TOC ou une page titre. Pre-filtre fort anti-faux positifs.
    _REQUIRED: dict[str, list[str]] = {
        # "vie individuelle"/"vie collective" (catégorisation attendue à l'origine)
        # n'apparaît en fait dans AUCUN PDF CMF réel observé (24 sociétés,
        # 2017-2025) : la vraie catégorisation varie par compagnie/vintage
        # ("Vie Décès Mixte Acceptation", "Vie Décès Mixte Capitalisation"...).
        # Le vrai invariant est le TITRE de la page ("Annexe n°12" / "(annexe 12)"),
        # qui lui apparaît systématiquement — voir CAS_PARTICULIERS_PDF_SECTIONS.md.
        "annexe12": [r"annexe\s*n?\.?\s*12(?!\d)"],
        "annexe13": [r"annexe\s*n?\.?\s*13(?!\d)", r"\bautomobile\b", r"\bincendie\b", r"responsabilite civile", r"\btransport\b"],
        # Une page de TOC/commentaire peut mentionner "Bilan" ou citer
        # "Total de l'actif" en passant sans être le vrai tableau — ces termes
        # de ligne/total ci-dessous n'apparaissent en pratique QUE sur la page
        # du tableau lui-meme, jamais dans une table des matieres.
        "bilan":         [r"total de l.actif", r"actif du bilan"],
        "bilan_passif":  [r"capitaux propres et le passif", r"total du passif", r"total des capitaux propres et du passif", r"provisions techniques brutes"],
        "etat_resultat": [r"produits des placements", r"rtnv resultat technique", r"resultat net de l.exercice"],
    }

    def _passes_required(text_norm: str, section: str) -> bool:
        reqs = _REQUIRED.get(section)
        if not reqs:
            return True
        return any(re.search(p, text_norm) for p in reqs)

    try:
        with pdfplumber.open(path) as pdf:
            # Passe 1 : extraire le texte de toutes les pages
            for page in pdf.pages:
                raw = page.extract_text() or ""
                pages_text.append(_normalize(raw))

        # Passe 2 : scorer chaque page pour chaque section
        # On a besoin des scores bruts de TOUTES les sections pour calculer le score net
        for i, text in enumerate(pages_text):
            if not text.strip():
                continue
            page_num = i + 1

            raw_scores = {sec: _raw_score(text, sec) for sec in _WEIGHTED_PATTERNS}

            for section in _WEIGHTED_PATTERNS:
                # Pré-filtre : les annexes exigent les colonnes-clés dans la page
                if section in _REQUIRED and not _passes_required(text, section):
                    continue

                raw = raw_scores[section]
                min_raw = _MIN_RAW_SCORE.get(section, 3)
                if raw < min_raw:
                    continue

                rival = _RIVALS.get(section)
                rival_score = raw_scores.get(rival, 0) if rival else 0
                net = raw - rival_score

                prev_net, prev_raw, _ = best.get(section, (-999, 0, 0))
                # Préférer le score net le plus élevé ; à égalité, le score brut le plus élevé
                if net > prev_net or (net == prev_net and raw > prev_raw):
                    best[section] = (net, raw, page_num)

        # Fallback : si le pré-filtre n'a trouvé aucune page, relâcher et scorer toutes
        import sys
        for section in _REQUIRED:
            if section not in best:
                print(f"[pdf_sections] {section} required-pattern filter found nothing for {code} {annee} — fallback to full scoring", file=sys.stderr)
                for i, text in enumerate(pages_text):
                    if not text.strip():
                        continue
                    raw = _raw_score(text, section)
                    min_raw = _MIN_RAW_SCORE.get(section, 3)
                    if raw < min_raw:
                        continue
                    rival = _RIVALS.get(section)
                    rival_raw = _raw_score(text, rival) if rival else 0
                    net = raw - rival_raw
                    prev_net, prev_raw, _ = best.get(section, (-999, 0, 0))
                    if net > prev_net or (net == prev_net and raw > prev_raw):
                        best[section] = (net, raw, i + 1)

    except Exception as exc:
        import sys
        print(f"[pdf_sections] ERROR {code} {annee}: {exc}", file=sys.stderr)
        _cache[key] = {}
        return {}

    result = {sec: page for sec, (_, _, page) in best.items()}

    # Contrainte d'ordre : annexe12 doit précéder annexe13
    a12 = result.get("annexe12")
    a13 = result.get("annexe13")
    if a12 and a13 and a12 >= a13:
        # Anomalie : on a probablement inversé les deux.
        # Chercher la meilleure page pour chaque en imposant l'ordre.
        import sys
        print(f"[pdf_sections] WARN {code} {annee}: annexe12(p{a12}) >= annexe13(p{a13}), correcting", file=sys.stderr)

        best12 = sorted(
            [(i, pages_text[i]) for i in range(len(pages_text))
             if _raw_score(pages_text[i], "annexe12") >= _MIN_RAW_SCORE["annexe12"]],
            key=lambda x: _raw_score(x[1], "annexe12") - _raw_score(x[1], "annexe13"),
            reverse=True,
        )
        best13 = sorted(
            [(i, pages_text[i]) for i in range(len(pages_text))
             if _raw_score(pages_text[i], "annexe13") >= _MIN_RAW_SCORE["annexe13"]],
            key=lambda x: _raw_score(x[1], "annexe13") - _raw_score(x[1], "annexe12"),
            reverse=True,
        )

        # Trouver la meilleure paire (p12 < p13)
        fixed = False
        for p12_i, _ in best12:
            for p13_i, _ in best13:
                if p12_i < p13_i:
                    result["annexe12"] = p12_i + 1
                    result["annexe13"] = p13_i + 1
                    fixed = True
                    break
            if fixed:
                break

        if not fixed:
            # Dernier recours : retirer annexe12 (moins fiable) — journalisé
            # clairement pour que ce soit diagnosticable plutôt que silencieux :
            # sans page annexe12, toute traçabilité PDF des KPI Vie du document
            # {code} {annee} échouera avec reason="page_invalide"/"page_vide".
            print(
                f"[pdf_sections] WARN {code} {annee}: no valid (p12 < p13) pair found — "
                f"dropping annexe12 entirely (was p{a12}). "
                f"Traçabilité PDF des KPI Vie indisponible pour ce document.",
                file=sys.stderr,
            )
            result.pop("annexe12", None)

    _cache[key] = result
    return result


def clear_cache():
    _cache.clear()
