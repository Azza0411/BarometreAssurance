"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         CHATBOT ASSURANCE TUNISIEN — FICHIER STANDALONE COMPLET             ║
║         Version consolidée — tous les modules en un seul fichier            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  DÉPENDANCES REQUISES :                                                     ║
║    pip install flask groq rapidfuzz                                         ║
║                                                                             ║
║  DÉPENDANCES OPTIONNELLES (prévisions) :                                   ║
║    pip install prophet xgboost shap pandas numpy                            ║
║                                                                             ║
║  VARIABLES D'ENVIRONNEMENT :                                                ║
║    GROQ_API_KEY=gsk_...    (obligatoire pour le LLM)                        ║
║    DB_PATH=/chemin/vers/MarketInsurance.db  (défaut: ./MarketInsurance.db)  ║
║                                                                             ║
║  LANCEMENT :                                                                ║
║    python chatbot_standalone.py                                             ║
║    → API disponible sur http://localhost:5001/api/chatbot                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

# ── Imports standard ──────────────────────────────────────────────────────────
import json
import logging
import os
import re
import sqlite3
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

# ── Flask ─────────────────────────────────────────────────────────────────────
from flask import Blueprint, Flask, jsonify, request

# ── Fuzzy matching (optionnel) ────────────────────────────────────────────────
try:
    from rapidfuzz import fuzz, process as rfprocess
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("chatbot")

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION BASE DE DONNÉES
# ─────────────────────────────────────────────────────────────────────────────

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("DB_PATH", os.path.join(_BASE_DIR, "MarketInsurance.db"))


def get_connection() -> sqlite3.Connection:
    """Connexion SQLite avec WAL et foreign keys."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def _db():
    """Context manager pour connexion SQLite auto-fermée."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def get_kpi_values_for_document(conn, document_id: int) -> dict:
    rows = conn.execute(
        "SELECT kpi, valeur_nombre, valeur_texte FROM kpi_values WHERE document_id = ?",
        (document_id,)
    ).fetchall()
    result = {}
    for kpi, val_num, val_txt in rows:
        result[kpi] = val_num if val_num is not None else val_txt
    return result


def list_documents_by_source(conn, source_nom: str):
    return conn.execute("""
        SELECT d.id, d.cmf_id, c.code, d.annee
        FROM documents d
        JOIN sources s ON s.id = d.source_id
        LEFT JOIN cmf c ON c.id = d.cmf_id
        WHERE s.nom = ?
        ORDER BY d.annee DESC
    """, (source_nom,)).fetchall()


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 1 — SPELL CORRECTOR + SYNONYMES
# ─────────────────────────────────────────────────────────────────────────────

KPI_SYNONYMS: dict[str, str] = {
    "pib": "Produit Interieur Brut (PIB)",
    "p.i.b": "Produit Interieur Brut (PIB)",
    "produit interieur brut": "Produit Interieur Brut (PIB)",
    "produit intérieur brut": "Produit Interieur Brut (PIB)",
    "gdp": "Produit Interieur Brut (PIB)",
    "population": "Population Totale",
    "population totale": "Population Totale",
    "habitants": "Population Totale",
    "taux de penetration": "Taux de pénétration",
    "taux de pénétration": "Taux de pénétration",
    "penetration": "Taux de pénétration",
    "pénétration": "Taux de pénétration",
    "taux penetration": "Taux de pénétration",
    "densite": "Densité de l'assurance",
    "densité": "Densité de l'assurance",
    "densite assurance": "Densité de l'assurance",
    "densité assurance": "Densité de l'assurance",
    "prime par habitant": "Densité de l'assurance",
    "primes emises": "Total Primes émises",
    "primes émises": "Total Primes émises",
    "total primes": "Total Primes émises",
    "total primes emises": "Total Primes émises",
    "total primes émises": "Total Primes émises",
    "primes": "Total Primes émises",
    "prime": "Total Primes émises",
    "production": "Total Primes émises",
    "automobile": "Primes émises par branche (FTUSA) - Automobile",
    "auto": "Primes émises par branche (FTUSA) - Automobile",
    "primes automobile": "Primes émises par branche (FTUSA) - Automobile",
    "groupe maladie": "Primes émises par branche (FTUSA) - Groupe Maladie",
    "maladie": "Primes émises par branche (FTUSA) - Groupe Maladie",
    "sante": "Primes émises par branche (FTUSA) - Groupe Maladie",
    "santé": "Primes émises par branche (FTUSA) - Groupe Maladie",
    "incendie": "Primes émises par branche (FTUSA) - Incendie",
    "transport": "Primes émises par branche (FTUSA) - Transport",
    "accidents travail": "Primes émises par branche (FTUSA) - Accidents du Travail",
    "accidents du travail": "Primes émises par branche (FTUSA) - Accidents du Travail",
    "risques agricoles": "Primes émises par branche (FTUSA) - Risques Agricoles",
    "agricole": "Primes émises par branche (FTUSA) - Risques Agricoles",
    "primes vie": "Primes émises Vie",
    "primes émises vie": "Primes émises Vie",
    "assurance vie": "Primes émises Vie",
    "vie": "Primes émises Vie",
    "primes non vie": "Primes émises Non-Vie",
    "primes non-vie": "Primes émises Non-Vie",
    "non vie": "Primes émises Non-Vie",
    "non-vie": "Primes émises Non-Vie",
    "ratio sp": "Ratio S/P",
    "ratio s/p": "Ratio S/P",
    "sinistralite": "Ratio S/P",
    "sinistralité": "Ratio S/P",
    "s/p": "Ratio S/P",
    "ratio combine": "Ratio combiné",
    "ratio combiné": "Ratio combiné",
    "combined ratio": "Ratio combiné",
    "ratio frais": "Ratio de frais",
    "ratio de frais": "Ratio de frais",
    "frais gestion": "Ratio de frais",
    "nombre assureurs": "Nombre d'assureurs",
    "nb assureurs": "Nombre d'assureurs",
    "assureurs": "Nombre d'assureurs",
    "nombre de compagnies": "Nombre d'assureurs",
    "compagnies": "Nombre d'assureurs",
    "agences": "Total agences",
    "total agences": "Total agences",
    "nombre agences": "Total agences",
    "reseau": "Total agences",
    "réseau": "Total agences",
    "part de marche": "Part de marché (%)",
    "part de marché": "Part de marché (%)",
    "pdm": "Part de marché (%)",
    "part marche": "Part de marché (%)",
    "part marché": "Part de marché (%)",
    "market share": "Part de marché (%)",
    "roe": "ROE (%)",
    "return on equity": "ROE (%)",
    "rentabilite fonds propres": "ROE (%)",
    "roa": "ROA (%)",
    "return on assets": "ROA (%)",
    "rentabilite actifs": "ROA (%)",
    "resultat net": "Résultat Net",
    "résultat net": "Résultat Net",
    "benefice": "Résultat Net",
    "bénéfice": "Résultat Net",
    "profit": "Résultat Net",
    "resultat": "Résultat Net",
    "résultat": "Résultat Net",
    "total actif": "Total actif",
    "actif total": "Total actif",
    "bilan": "Total actif",
    "capitaux propres": "Capitaux propres",
    "fonds propres": "Capitaux propres",
    "capital": "Capitaux propres",
    "charge sinistres": "Charge de sinistres",
    "sinistres": "Charge de sinistres",
    "indemnisations": "Charge de sinistres",
    "primes emises par assurance": "Primes émises par assurance",
    "primes émises par assurance": "Primes émises par assurance",
    "primes compagnie": "Primes émises par assurance",
    "primes emises compagnie": "Primes émises par assurance",
    "cours action": "Cours de l'action",
    "action": "Cours de l'action",
    "capitalisation": "Capitalisation Boursière",
    "capitalisation boursiere": "Capitalisation Boursière",
    "market cap": "Capitalisation Boursière",
}

COMPANY_SYNONYMS: dict[str, str] = {
    "star": "STAR",
    "société tunisienne d'assurances et de réassurances": "STAR",
    "comar": "COMAR",
    "compagnie méditerranéenne d'assurances et de réassurances": "COMAR",
    "astree": "ASTREE",
    "astrée": "ASTREE",
    "gat": "GAT",
    "gat assurances": "GAT",
    "ami": "AMI",
    "assurances mutuelles immobilières": "AMI",
    "maghrebia": "MAGHREBIA",
    "carte": "CARTE",
    "lloyd": "LLOYD",
    "bh assurance": "BH",
    "bh": "BH",
    "bna": "BNA",
    "bna assurances": "BNA",
    "mae": "MAE",
    "ctama": "CTAMA",
    "cotunace": "COTUNACE",
    "uib": "UIB",
    "attijari": "ATTIJARI",
    "attijari assurance": "ATTIJARI",
    "hayett": "HAYETT",
    "zitouna": "ZITOUNA_TAKAFUL",
    "zitouna takaful": "ZITOUNA_TAKAFUL",
    "takafulia": "AT_TAKAFULIA",
    "at takafulia": "AT_TAKAFULIA",
    "al amanah": "AL_AMANAH_TAKAFUL",
    "al amanah takaful": "AL_AMANAH_TAKAFUL",
    "gat vie": "GAT_VIE",
    "maghrebia vie": "MAGHREBIA_VIE",
    "carte vie": "CARTE_VIE",
    "lloyd vie": "LLOYD_VIE",
    "tunisre": "TUNISRE",
    "tunis re": "TUNISRE",
    "biat": "BIAT",
}

COMPANY_DISPLAY: dict[str, str] = {
    "STAR": "STAR", "COMAR": "COMAR", "ASTREE": "Astrée", "GAT": "GAT Assurances",
    "AMI": "AMI", "MAGHREBIA": "Maghrebia", "CARTE": "Carte", "LLOYD": "Lloyd",
    "BH": "BH Assurance", "BNA": "BNA Assurances", "MAE": "MAE", "CTAMA": "CTAMA",
    "COTUNACE": "COTUNACE", "UIB": "UIB Assurances", "ATTIJARI": "Attijari Assurance",
    "HAYETT": "Hayett", "ZITOUNA_TAKAFUL": "Zitouna Takaful", "AT_TAKAFULIA": "At-Takafulia",
    "AL_AMANAH_TAKAFUL": "Al Amanah Takaful", "GAT_VIE": "GAT Vie",
    "MAGHREBIA_VIE": "Maghrebia Vie", "CARTE_VIE": "Carte Vie",
    "LLOYD_VIE": "Lloyd Vie", "TUNISRE": "Tunis Re", "BIAT": "BIAT",
}

_COMPANY_GENERIC_WORDS = {
    "assurance", "assurances", "assureur", "assureurs", "compagnie",
    "compagnies", "marche", "marché", "secteur", "meilleur", "meilleure",
    "premier", "premiere", "leader", "top", "non", "oui",
}


def normalize(text: str) -> str:
    t = text.lower().strip()
    for src, dst in [("é","e"),("è","e"),("ê","e"),("ë","e"),("à","a"),("â","a"),
                     ("ä","a"),("ô","o"),("ö","o"),("î","i"),("ï","i"),("û","u"),
                     ("ù","u"),("ç","c"),("'","'"),("'","'")]:
        t = t.replace(src, dst)
    return t


def match_kpi(user_input: str, threshold: int = 75) -> str | None:
    norm = normalize(user_input)
    if norm in KPI_SYNONYMS:
        return KPI_SYNONYMS[norm]
    if threshold >= 100:
        return None
    if len(norm) >= 4:
        for alias, canonical in KPI_SYNONYMS.items():
            if alias in norm or (len(norm) >= 5 and norm in alias):
                return canonical
    if _HAS_RAPIDFUZZ:
        best = rfprocess.extractOne(norm, list(KPI_SYNONYMS.keys()), scorer=fuzz.token_set_ratio)
        if best and best[1] >= threshold:
            return KPI_SYNONYMS[best[0]]
    return None


def match_company(user_input: str, threshold: int = 82) -> str | None:
    norm = normalize(user_input)
    words = set(norm.split())
    meaningful = {w for w in words - _COMPANY_GENERIC_WORDS if not w.isdigit()}
    if not meaningful:
        return None
    if norm in COMPANY_SYNONYMS:
        return COMPANY_SYNONYMS[norm]
    for alias, code in COMPANY_SYNONYMS.items():
        if alias in norm and len(alias.split()) >= 2:
            return code
        if norm in alias and len(norm.split()) >= 2:
            return code
    if _HAS_RAPIDFUZZ:
        best = rfprocess.extractOne(norm, list(COMPANY_SYNONYMS.keys()), scorer=fuzz.token_set_ratio)
        if best and best[1] >= threshold:
            alias_meaningful = set(best[0].split()) - _COMPANY_GENERIC_WORDS
            if alias_meaningful:
                return COMPANY_SYNONYMS[best[0]]
    return None


def display_company(code: str) -> str:
    return COMPANY_DISPLAY.get(code, code)


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 2 — ENTITY EXTRACTOR
# ─────────────────────────────────────────────────────────────────────────────

_YEAR_PATTERN = re.compile(r"\b(201[5-9]|202[0-9])\b")
_GENERIC_ENTITY_WORDS = {
    "assurance", "assurances", "assureur", "assureurs", "compagnie",
    "compagnies", "marche", "marché", "secteur", "tunisie", "tunisien",
    "meilleur", "meilleure", "premier", "premiere", "leader", "top",
    "non", "oui", "parle", "parler", "on", "je", "tu", "il", "nous",
}


def extract_years(text: str) -> list[int]:
    return sorted({int(y) for y in _YEAR_PATTERN.findall(text)})


def extract_company(text: str) -> str | None:
    norm = normalize(text)
    if re.search(r"\bnon\b", norm):
        return None
    norm_words = set(norm.split())
    if norm_words and norm_words.issubset(_GENERIC_ENTITY_WORDS):
        return None
    words = text.upper().split()
    for word in words:
        clean = re.sub(r"[^A-Z_]", "", word)
        if clean in {c.upper() for c in COMPANY_SYNONYMS.values()}:
            for code in COMPANY_SYNONYMS.values():
                if code.upper() == clean:
                    return code
    company = match_company(norm)
    if company:
        matched_word = norm.strip()
        if matched_word in _GENERIC_ENTITY_WORDS:
            return None
    return company


def extract_kpis(text: str) -> list[str]:
    norm = normalize(text)
    found: list[str] = []
    seen: set[str] = set()
    words = norm.split()
    n = len(words)
    for size in range(min(n, 7), 0, -1):
        for start in range(n - size + 1):
            segment = " ".join(words[start:start + size])
            kpi = match_kpi(segment, threshold=100)
            if kpi and kpi not in seen:
                found.append(kpi)
                seen.add(kpi)
    if not found:
        for size in range(min(n, 7), 1, -1):
            for start in range(n - size + 1):
                segment = " ".join(words[start:start + size])
                kpi = match_kpi(segment, threshold=82)
                if kpi and kpi not in seen:
                    found.append(kpi)
                    seen.add(kpi)
                    break
    return found[:3]


def extract_entities(text: str, context: dict) -> dict:
    norm_text = normalize(text)
    years = extract_years(text)
    company = extract_company(text)
    kpis = extract_kpis(text)

    if not company and context.get("last_company"):
        pronouns = {"son", "sa", "ses", "leur", "leurs", "il", "elle", "lui",
                    "cette", "cet", "ce", "la compagnie", "l'assureur", "cette compagnie"}
        if any(p in norm_text.split() for p in pronouns):
            company = context["last_company"]

    if not kpis and context.get("last_kpis"):
        ref_words = {"et", "aussi", "egalement", "pareil", "meme", "idem"}
        if any(w in norm_text.split() for w in ref_words) or (not kpis and years):
            kpis = context["last_kpis"]

    is_comparison = any(w in norm_text for w in
                        ["comparer", "comparaison", "versus", "vs", "par rapport", "difference", "ecart"])
    is_evolution = any(w in norm_text for w in
                       ["evolution", "évolution", "tendance", "historique", "serie", "depuis",
                        "croissance", "progression", "baisse", "hausse", "toutes les annees"])
    is_ranking = any(w in norm_text for w in
                     ["meilleur", "premier", "top", "classement", "rang", "leader",
                      "plus grand", "le plus", "la plus", "maximum", "minimum", "pire"])
    return {
        "years": years, "company": company, "kpis": kpis,
        "is_comparison": is_comparison, "is_evolution": is_evolution, "is_ranking": is_ranking,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 3 — INTENT DETECTOR
# ─────────────────────────────────────────────────────────────────────────────

INTENT_GREETING       = "greeting"
INTENT_KPI_QUERY      = "kpi_query"
INTENT_COMPANY_PROFILE = "company_profile"
INTENT_RANKING        = "ranking"
INTENT_EVOLUTION      = "evolution"
INTENT_COMPARISON     = "comparison"
INTENT_DEFINITION     = "definition"
INTENT_MARKET_OVERVIEW = "market_overview"
INTENT_FORECAST       = "forecast"
INTENT_REGULATORY     = "regulatory"
INTENT_UNKNOWN        = "unknown"

_INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    (INTENT_REGULATORY, [
        r"r[eé]glementation", r"r[eé]glementaire", r"circulaire", r"d[eé]cret",
        r"loi\s+n[°o]", r"code des assurances", r"cga", r"provision technique",
        r"marge de solvabilit[eé]", r"solvabilit[eé]", r"agr[eé]ment",
        r"obligation l[eé]gale", r"capital minimum", r"r[eé]assurance obligatoire",
        r"takaful", r"ifrs", r"provision math[eé]matique", r"ratio combin[eé].*norme",
        r"que dit la loi", r"quelle est la r[eé]gle", r"est.ce obligatoire",
        r"digitalisation.*assurance", r"insurtech", r"ftusa.*statistique",
    ]),
    (INTENT_FORECAST, [
        r"pr[eé]vision", r"pr[eé]voir", r"estim(er|ation)",
        r"projection", r"anticip(er|ation)",
        r"sera (en|pour|à)", r"seront (en|pour|à)",
        r"(en|pour|à) 20(2[5-9]|3[0-9])",
        r"dans \d+ an", r"d'ici \d+ an",
        r"quel(le)? sera", r"quel(le)? seront",
        r"(combien|quel) (sera|seront|pourrait|pourraient)",
        r"forecast", r"pr[eé]dire", r"pr[eé]dit", r"pr[eé]dis",
    ]),
    (INTENT_GREETING, [
        r"\bbonjour\b", r"\bsalut\b", r"\bhello\b", r"\bhi\b", r"\bbonsoir\b",
        r"^(ok|okay|d'accord|merci|super|parfait|bien)$",
    ]),
    (INTENT_RANKING, [
        r"meilleur", r"premier", r"top\s*\d", r"classement", r"\brang\b",
        r"leader", r"plus grand", r"le plus (eleve|haut|fort|important|performant)",
        r"plus faible", r"pire", r"minimum", r"maximum",
        r"quelle compagnie (a|possede|affiche|realise)",
    ]),
    (INTENT_EVOLUTION, [
        r"evolution", r"évolution", r"tendance", r"historique",
        r"depuis\s+\d{4}", r"toutes les annees", r"serie (temporelle|historique)",
        r"progression", r"croissance", r"baisse", r"hausse",
        r"(comment|comment a) (evolue|évolué)", r"d'une annee (a|à) l'autre",
    ]),
    (INTENT_COMPARISON, [
        r"comparer", r"comparaison", r"versus", r"\bvs\b", r"par rapport",
        r"difference (entre|avec)", r"ecart (entre|avec)",
        r"(entre|parmi) (les|des) compagnies",
    ]),
    (INTENT_DEFINITION, [
        r"qu'est.ce que", r"c'est quoi", r"definir", r"definition",
        r"signifie", r"que veut dire", r"expliquer",
    ]),
    (INTENT_MARKET_OVERVIEW, [
        r"apercu", r"aperçu", r"vue d'ensemble", r"marche global",
        r"secteur assurance", r"tableau de bord",
        r"statistiques (globales|generales|du marche)",
        r"combien (de compagnies|d'assureurs)",
        r"autres (donnees|données|stats|kpi)",
    ]),
    (INTENT_COMPANY_PROFILE, [
        r"profil (de|d'|du)", r"fiche (de|d'|du)",
        r"presentation (de|d'|du)", r"informations? sur",
    ]),
]

_COMPILED_PATTERNS = [
    (intent, [re.compile(p, re.IGNORECASE) for p in patterns])
    for intent, patterns in _INTENT_PATTERNS
]


def detect_intent(text: str, entities: dict) -> str:
    norm = normalize(text)
    for intent, compiled in _COMPILED_PATTERNS:
        for pat in compiled:
            if pat.search(norm):
                return intent
    # Année future (> données historiques) = prévision implicite
    if any(y > 2024 for y in entities.get("years", [])):
        return INTENT_FORECAST
    if entities.get("is_ranking"):
        return INTENT_RANKING
    if entities.get("is_evolution"):
        return INTENT_EVOLUTION
    if entities.get("is_comparison"):
        return INTENT_COMPARISON
    if entities.get("kpis"):
        return INTENT_KPI_QUERY
    if entities.get("company") and not entities.get("kpis"):
        return INTENT_COMPANY_PROFILE
    return INTENT_UNKNOWN


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 4 — CONVERSATION MEMORY
# ─────────────────────────────────────────────────────────────────────────────

_SESSIONS: dict[str, "Session"] = {}
_SESSION_TTL = 3600


@dataclass
class Message:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    data: dict = field(default_factory=dict)


@dataclass
class Session:
    session_id: str
    messages: list[Message] = field(default_factory=list)
    context: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    def add_message(self, role: str, content: str, data: dict | None = None):
        self.messages.append(Message(role=role, content=content, data=data or {}))
        self.last_activity = time.time()

    def update_context(self, entities: dict, intent: str | None = None):
        if entities.get("company"):
            self.context["last_company"] = entities["company"]
        if entities.get("years"):
            self.context["last_year"] = entities["years"][-1]
        if entities.get("kpis"):
            self.context["last_kpis"] = entities["kpis"]
        if intent:
            self.context["last_intent"] = intent

    def get_history_for_llm(self, max_turns: int = 6) -> list[dict]:
        recent = self.messages[-max_turns * 2:]
        return [{"role": m.role, "content": m.content} for m in recent]

    def reset(self):
        self.messages.clear()
        self.context.clear()
        self.last_activity = time.time()


def get_session(session_id: str) -> Session:
    _cleanup_old_sessions()
    if session_id not in _SESSIONS:
        _SESSIONS[session_id] = Session(session_id=session_id)
    return _SESSIONS[session_id]


def _cleanup_old_sessions():
    now = time.time()
    for sid in [s for s, sess in _SESSIONS.items() if now - sess.last_activity > _SESSION_TTL]:
        del _SESSIONS[sid]


def session_to_dict(session: Session) -> list[dict]:
    return [{"role": m.role, "content": m.content, "timestamp": m.timestamp}
            for m in session.messages]


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 5 — QUERY BUILDER (SQL)
# ─────────────────────────────────────────────────────────────────────────────

PRIMES_DIVISOR = 1_000_000

_TND_TO_MDT_KPIS = {
    "Total Primes émises", "Primes émises Vie", "Primes émises Non-Vie",
    "Primes émises par assurance", "Primes émises Vie par assurance",
    "Primes émises Non-Vie par assurance", "Résultat Net", "Total actif",
    "Total Passif", "Capitaux propres", "Résultat technique (TND)",
    "Charge de sinistres",
    "Primes émises par branche (FTUSA) - Automobile",
    "Primes émises par branche (FTUSA) - Groupe Maladie",
    "Primes émises par branche (FTUSA) - Incendie",
    "Primes émises par branche (FTUSA) - Transport",
    "Primes émises par branche (FTUSA) - Accidents du Travail",
    "Primes émises par branche (FTUSA) - Risques Agricoles",
    "Primes émises par branche (FTUSA) - Risques Divers",
}

_KPI_SOURCE_HINTS: dict[str, str] = {
    "Produit Interieur Brut (PIB)": "INS", "Population Totale": "INS",
    "Taux de pénétration": "FTUSA", "Densité de l'assurance": "FTUSA",
    "Total Primes émises": "FTUSA", "Primes émises Vie": "FTUSA",
    "Primes émises Non-Vie": "FTUSA", "Ratio S/P": "FTUSA",
    "Ratio de frais": "FTUSA", "Ratio combiné": "FTUSA",
    "Nombre d'assureurs": "CGA", "Total agences": "CGA",
}


def _fmt_number(value, kpi_name: str = "", source: str = "") -> dict:
    if value is None:
        return {"raw": None, "display": "Non disponible", "unit": ""}
    if kpi_name in _TND_TO_MDT_KPIS and source in ("CMF", "FTUSA"):
        mdt = value / PRIMES_DIVISOR
        return {"raw": mdt, "display": f"{mdt:,.1f}", "unit": "MDT"}
    if ("(%)" in kpi_name or kpi_name.startswith("Taux") or kpi_name.startswith("Ratio")
            or kpi_name.startswith("Part") or kpi_name.startswith("ROE") or kpi_name.startswith("ROA")):
        return {"raw": value, "display": f"{value:.1f}", "unit": "%"}
    if kpi_name in ("Nombre d'assureurs", "Total agences", "Population Totale"):
        return {"raw": int(value), "display": f"{int(value):,}", "unit": ""}
    if kpi_name == "Produit Interieur Brut (PIB)":
        return {"raw": value, "display": f"{value:,.0f}", "unit": "MDT"}
    if "Densité" in kpi_name:
        return {"raw": value, "display": f"{value:.1f}", "unit": "DT/habitant"}
    return {"raw": value, "display": f"{value:,.2f}", "unit": ""}


def _kpis_by_year(conn, source_nom: str) -> dict:
    result = {}
    for document_id, _cmf_id, _code, annee in list_documents_by_source(conn, source_nom):
        if annee:
            result[annee] = get_kpi_values_for_document(conn, document_id)
    return result


def fetch_kpi_for_market(conn, kpi_name: str, year: int | None) -> list[dict]:
    source_hint = _KPI_SOURCE_HINTS.get(kpi_name)
    sources_to_try = [source_hint] if source_hint else ["FTUSA", "INS", "CGA"]
    results = []
    for source in sources_to_try:
        q = ("""SELECT d.annee, MAX(CASE WHEN k.valeur_nombre IS NOT NULL THEN k.valeur_nombre END), MAX(k.valeur_texte)
               FROM kpi_values k JOIN documents d ON d.id=k.document_id JOIN sources s ON s.id=d.source_id
               WHERE s.nom=? AND k.kpi=? AND d.annee=? AND d.cmf_id IS NULL GROUP BY d.annee ORDER BY d.annee""",
              (source, kpi_name, year)) if year else (
             """SELECT d.annee, MAX(CASE WHEN k.valeur_nombre IS NOT NULL THEN k.valeur_nombre END), MAX(k.valeur_texte)
               FROM kpi_values k JOIN documents d ON d.id=k.document_id JOIN sources s ON s.id=d.source_id
               WHERE s.nom=? AND k.kpi=? AND d.cmf_id IS NULL GROUP BY d.annee ORDER BY d.annee""",
              (source, kpi_name))
        rows = conn.execute(*q).fetchall()
        if rows:
            seen: set = set()
            for annee, val_num, val_txt in rows:
                if annee in seen:
                    continue
                seen.add(annee)
                fmt = _fmt_number(val_num, kpi_name, source)
                results.append({"annee": annee, "valeur": val_num if val_num is not None else val_txt,
                                 "display": fmt["display"], "unit": fmt["unit"], "source": source, "kpi": kpi_name})
            break
    return results


def fetch_kpi_for_company(conn, kpi_name: str, company_code: str, year: int | None) -> list[dict]:
    params = (company_code, kpi_name, year) if year else (company_code, kpi_name)
    year_clause = "AND d.annee=?" if year else ""
    rows = conn.execute(f"""
        SELECT d.annee, k.valeur_nombre, k.valeur_texte, s.nom
        FROM kpi_values k JOIN documents d ON d.id=k.document_id
        JOIN sources s ON s.id=d.source_id JOIN cmf c ON c.id=d.cmf_id
        WHERE c.code=? AND k.kpi=? {year_clause} ORDER BY d.annee
    """, params).fetchall()
    results = []
    for annee, val_num, val_txt, source in rows:
        fmt = _fmt_number(val_num, kpi_name, source)
        results.append({"annee": annee, "valeur": val_num if val_num is not None else val_txt,
                         "display": fmt["display"], "unit": fmt["unit"], "source": source,
                         "kpi": kpi_name, "company": company_code})
    return results


def fetch_ranking(conn, kpi_name: str, year: int, limit: int = 10) -> list[dict]:
    is_pct = "(%)" in kpi_name or any(kpi_name.startswith(x) for x in ("ROE", "ROA", "Ratio", "Part", "Taux"))
    max_val = 500 if is_pct else None
    if max_val:
        rows = conn.execute("""
            SELECT c.code, c.nom_entreprise, k.valeur_nombre, k.valeur_texte, s.nom
            FROM kpi_values k JOIN documents d ON d.id=k.document_id
            JOIN sources s ON s.id=d.source_id JOIN cmf c ON c.id=d.cmf_id
            WHERE k.kpi=? AND d.annee=? AND k.valeur_nombre IS NOT NULL
              AND k.valeur_nombre BETWEEN -500 AND ?
            ORDER BY k.valeur_nombre DESC LIMIT ?
        """, (kpi_name, year, max_val, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT c.code, c.nom_entreprise, k.valeur_nombre, k.valeur_texte, s.nom
            FROM kpi_values k JOIN documents d ON d.id=k.document_id
            JOIN sources s ON s.id=d.source_id JOIN cmf c ON c.id=d.cmf_id
            WHERE k.kpi=? AND d.annee=? AND k.valeur_nombre IS NOT NULL
            ORDER BY k.valeur_nombre DESC LIMIT ?
        """, (kpi_name, year, limit)).fetchall()
    results = []
    for i, (code, nom, val_num, val_txt, source) in enumerate(rows, 1):
        fmt = _fmt_number(val_num, kpi_name, source)
        results.append({"rang": i, "code": code, "nom": nom or code,
                         "valeur": val_num, "display": fmt["display"], "unit": fmt["unit"]})
    return results


def fetch_company_profile(conn, company_code: str, year: int) -> dict:
    _KEY_KPIS = {"Primes émises par assurance", "Résultat Net", "Total actif", "ROA (%)", "ROE (%)"}
    kpis = {}
    actual_year = year
    for doc_id, _, c, doc_annee in sorted(list_documents_by_source(conn, "CMF"),
                                           key=lambda x: x[3] or 0, reverse=True):
        if c != company_code:
            continue
        if doc_annee != year and doc_annee != actual_year:
            if kpis:
                break
        candidate = get_kpi_values_for_document(conn, doc_id)
        if any(candidate.get(k) is not None for k in _KEY_KPIS) or doc_annee == year:
            kpis = candidate
            actual_year = doc_annee
            if doc_annee == year:
                break

    def fmt_mdt(k):
        v = kpis.get(k)
        return round(v / PRIMES_DIVISOR, 1) if (v is not None and abs(v) >= 1000) else None

    def fmt_pct(k):
        v = kpis.get(k)
        return round(v, 1) if v is not None else None

    rc = kpis.get("Ratio combiné (%)")
    rf = kpis.get("Ratio de frais de gestion (%)")
    if rc is not None and rf is not None and abs(rc - rf) < 0.5:
        rc = None

    def _valid_ratio(v):
        return round(v, 1) if (v is not None and 2 <= v <= 1000) else None

    return {
        "code": company_code, "annee": actual_year,
        "primes_emises_mdt": fmt_mdt("Primes émises par assurance"),
        "resultat_net_mdt": fmt_mdt("Résultat Net"),
        "total_actif_mdt": fmt_mdt("Total actif"),
        "capitaux_propres_mdt": fmt_mdt("Capitaux propres"),
        "pdm_pct": fmt_pct("Part de marché (%)"),
        "roe_pct": fmt_pct("ROE (%)"),
        "roa_pct": fmt_pct("ROA (%)"),
        "ratio_combine_pct": _valid_ratio(rc),
        "ratio_sp_pct": _valid_ratio(kpis.get("Ratio de sinistralité (%)")),
        "ratio_frais_pct": _valid_ratio(rf),
        "raw": kpis,
    }


def fetch_market_overview(conn, year: int) -> dict:
    ftusa = _kpis_by_year(conn, "FTUSA").get(year, {})
    ins = _kpis_by_year(conn, "INS").get(year, {})
    cga = _kpis_by_year(conn, "CGA").get(year, {})
    total = ftusa.get("Total Primes émises")
    population = ins.get("Population Totale")
    densite = ftusa.get("Densité de l'assurance")
    if densite is None and total is not None and population:
        densite = total / population
    nb_assureurs = cga.get("Nombre d'assureurs")
    if nb_assureurs is None:
        cmf_docs = list_documents_by_source(conn, "CMF")
        nb_assureurs = len({code for _, _, code, y in cmf_docs if y == year and code}) or None
    return {
        "annee": year,
        "pib_mdt": ins.get("Produit Interieur Brut (PIB)"),
        "population": population,
        "total_primes_mdt": total / PRIMES_DIVISOR if total else None,
        "primes_vie_mdt": (ftusa.get("Primes émises Vie") or 0) / PRIMES_DIVISOR or None,
        "primes_non_vie_mdt": (ftusa.get("Primes émises Non-Vie") or 0) / PRIMES_DIVISOR or None,
        "taux_penetration": ftusa.get("Taux de pénétration"),
        "densite": densite,
        "nb_assureurs": nb_assureurs,
        "total_agences": cga.get("Total agences"),
    }


def fetch_available_years(conn) -> list[int]:
    ftusa_years = set(_kpis_by_year(conn, "FTUSA").keys())
    ins_years = set(_kpis_by_year(conn, "INS").keys())
    return [y for y in sorted(ftusa_years | ins_years, reverse=True) if 2014 <= y <= 2024]


def fetch_available_companies(conn) -> list[str]:
    rows = conn.execute("""
        SELECT DISTINCT c.code FROM cmf c JOIN documents d ON d.cmf_id=c.id ORDER BY c.code
    """).fetchall()
    return [r[0] for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 6 — TEXT-TO-SQL (LLM Groq)
# ─────────────────────────────────────────────────────────────────────────────

_DB_SCHEMA_PROMPT = """
BASE DE DONNÉES SQLite — marché des assurances en Tunisie

TABLES :
  sources(id, nom)           -- nom ∈ {'CMF','FTUSA','INS','CGA'}
  cmf(id, code, nom_entreprise)  -- compagnies d'assurance
  documents(id, source_id, cmf_id, annee)
  kpi_values(id, document_id, kpi, valeur_nombre, valeur_texte)

COMPAGNIES : STAR, AMI, COMAR, GAT, MAGHREBIA, ASTREE, BH, CARTE, CTAMA,
  ATTIJARI, BNA, AL_AMANAH_TAKAFUL, AT_TAKAFULIA, BIAT, CARTE_VIE,
  GAT_VIE, HAYETT, LLOYD_TUNISIEN, LLOYD_VIE, MAGHREBIA_VIE,
  TUNIS_RE, UIB, ZITOUNA_TAKAFUL, COTUNACE

ANNÉES : 2015-2024 (CMF), 2000-2024 (FTUSA/INS)

KPIs COMPAGNIES (CMF) : 'Part de marché (%)', 'Primes émises par assurance',
  'Résultat Net', 'Total actif', 'Capitaux propres', 'ROE (%)', 'ROA (%)',
  'Ratio combiné (%)', 'Ratio de sinistralité (%)', 'Ratio de frais de gestion (%)',
  'Charge de sinistres'

KPIs MARCHÉ (FTUSA) : 'Total Primes émises', 'Taux de pénétration',
  "Densité de l'assurance", 'Primes émises Vie', 'Primes émises Non-Vie'

KPIs MACRO (INS) : 'Produit Interieur Brut (PIB)', 'Population Totale'

RÈGLES SQL :
  1. Primes/actifs CMF : diviser valeur_nombre par 1000000 pour MDT
  2. Classements : filtrer valeur_nombre BETWEEN 0.1 AND 500 pour '%'
  3. TOUJOURS utiliser d.annee = <année> dans le WHERE
  4. Données compagnie : JOIN cmf c ON c.id = d.cmf_id AND c.code = '<CODE>'
  5. Données marché : WHERE s.nom = 'FTUSA' AND d.cmf_id IS NULL
"""

_SQL_SYSTEM_PROMPT = (
    "Tu es un expert SQLite spécialisé dans le marché des assurances tunisien. "
    "Génère une requête SQL SQLite précise pour répondre à la question.\n\n"
    + _DB_SCHEMA_PROMPT +
    "\nRéponds UNIQUEMENT avec un objet JSON valide :\n"
    '{"sql": "SELECT ...", "description": "...", "unit": "MDT|%|nombre|", "format": "ranking|single|timeseries|profile"}\n'
    "Ne génère JAMAIS de requêtes INSERT/UPDATE/DELETE."
)


def _call_groq(messages: list[dict]) -> str | None:
    try:
        from groq import Groq
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=messages,
            max_tokens=600, temperature=0.1,
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq error: {e}")
        return None


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def _safe_execute(conn: sqlite3.Connection, sql: str):
    sql_clean = sql.strip()
    if not re.match(r'^SELECT\b', sql_clean, re.IGNORECASE):
        logger.warning(f"Rejected non-SELECT SQL: {sql_clean[:50]}")
        return None
    try:
        cursor = conn.execute(sql_clean)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description] if cursor.description else []
        return rows, cols
    except Exception as e:
        logger.error(f"SQL error: {e}")
        return None


def _format_sql_answer(rows, cols, meta, question) -> str:
    if not rows:
        return "Je n'ai pas trouvé de données pour cette question dans la base."
    unit = meta.get("unit", "")
    fmt = meta.get("format", "single")
    desc = meta.get("description", "")
    rows = [tuple(r) for r in rows]
    if fmt == "ranking":
        lines = [f"**Classement** ({desc}) :"]
        for i, row in enumerate(rows, 1):
            vals = [f"{v:,.1f} {unit}".strip() if isinstance(v, float) else str(v)
                    for v in row if v is not None]
            lines.append(f"{i}. {' — '.join(vals)}")
        return "\n".join(lines)
    elif fmt == "timeseries":
        lines = [f"**Évolution** ({desc}) :"]
        for row in rows:
            parts = [f"{v:,.1f} {unit}".strip() if isinstance(v, float) else str(v)
                     for v in row if v is not None]
            lines.append(" — ".join(parts))
        return "\n".join(lines)
    elif fmt == "profile":
        # Deux formes possibles selon la requête générée par le LLM :
        # - pivotée (1 ligne, 1 colonne par KPI) -> unit global cohérent
        # - dépivotée (1 ligne par KPI, colonnes kpi/valeur) -> pas d'unit
        #   global sensé (chaque KPI a sa propre unité), donc pas d'unit affiché
        if len(rows) == 1 and len(rows[0]) > 2:
            lines = []
            for col, val in zip(cols, rows[0]):
                if val is not None:
                    lines.append(f"**{col}** : {val:,.2f} {unit}".strip() if isinstance(val, float) else f"**{col}** : {val}")
            return "\n".join(lines) if lines else "Profil non disponible."
        lines = []
        for row in rows:
            row_map = dict(zip(cols, row))
            label = row_map.get("kpi") or row[0]
            value = next((v for v in row[1:] if v is not None), None)
            if label is None or value is None:
                continue
            lines.append(f"**{label}** : {value:,.2f}" if isinstance(value, float) else f"**{label}** : {value}")
        return "\n".join(lines) if lines else "Profil non disponible."
    else:
        if len(rows) == 1 and len(rows[0]) == 1:
            v = rows[0][0]
            return f"{desc} : **{v:,.2f} {unit}**".strip() if isinstance(v, float) else f"{desc} : **{v}**"
        lines = []
        for row in rows:
            parts = [f"{v:,.2f} {unit}".strip() if isinstance(v, float) else str(v)
                     for v in row if v is not None]
            lines.append(" — ".join(parts))
        return "\n".join(lines)


def answer_with_sql(conn: sqlite3.Connection, question: str, history: list[dict]) -> dict:
    messages = [{"role": "system", "content": _SQL_SYSTEM_PROMPT}]
    for msg in history[-4:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": f"Question: {question}\n\nGénère le SQL SQLite."})
    raw = _call_groq(messages)
    meta = _extract_json(raw) if raw else None
    if not meta or not meta.get("sql"):
        return {"text": "Je n'ai pas pu générer une requête. Essayez de reformuler.",
                "sql": None, "rows": [], "error": "LLM did not return valid SQL"}
    result = _safe_execute(conn, meta["sql"])
    if result is None:
        return {"text": "Erreur lors de l'exécution de la requête.",
                "sql": meta["sql"], "rows": [], "error": "SQL execution failed"}
    rows, cols = result
    return {
        "text": _format_sql_answer(rows, cols, meta, question),
        "sql": meta["sql"],
        "rows": [dict(zip(cols, tuple(r))) for r in rows],
        "meta": meta, "error": None,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 7 — RESPONSE GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

RENDER_TEXT      = "text"
RENDER_TABLE     = "table"
RENDER_KPI_CARDS = "kpi_cards"
RENDER_RANKING   = "ranking"
RENDER_EVOLUTION = "evolution"


def build_response(user_question: str, intent: str, entities: dict,
                   query_results: dict, history: list[dict]) -> dict:
    results = query_results.get("results", [])
    error = query_results.get("error")
    if error:
        return {"text": f"⚠️ {error}", "render": RENDER_TEXT, "data": {},
                "suggestions": _default_suggestions(), "error": error}
    if not results and intent not in ("greeting", "definition", "market_overview"):
        company = entities.get("company")
        years = entities.get("years", [])
        year_str = f" en {years[0]}" if years else ""
        company_str = f" pour **{display_company(company)}**" if company else ""
        return {"text": f"Je n'ai pas trouvé de données{company_str}{year_str} dans la base.",
                "render": RENDER_TEXT, "data": {}, "suggestions": _default_suggestions(), "error": None}
    if intent == "greeting":
        return build_greeting()
    render_type = _choose_render(intent, results, entities)
    text = _generate_text(user_question, intent, entities, query_results, history, render_type)
    return {"text": text, "render": render_type, "data": query_results,
            "suggestions": _contextual_suggestions(intent, entities), "error": None}


def _generate_text(user_question, intent, entities, query_results, history, render_type) -> str:
    """Génère une analyse narrative via LLM — commentaire d'analyste, pas juste reformulation."""
    results = query_results.get("results", [])
    kpis = entities.get("kpis") or [query_results.get("kpi", "")]
    company = entities.get("company")
    years = entities.get("years", [])

    # Construire un résumé structuré des données pour le LLM
    data_summary = json.dumps(results[:15], ensure_ascii=False, indent=2)

    intent_guidance = {
        INTENT_RANKING: (
            "Commente le classement. Identifie le leader, les challengers et les retardataires. "
            "Souligne les écarts notables et ce qu'ils révèlent sur la compétitivité du marché."
        ),
        INTENT_EVOLUTION: (
            "Analyse la tendance sur la période. Identifie les années de rupture, "
            "les phases de croissance et de recul. Propose une interprétation des causes "
            "(contexte macro, réforme réglementaire, dynamique concurrentielle)."
        ),
        INTENT_COMPANY_PROFILE: (
            "Réalise un diagnostic financier de la compagnie. Points forts, points de vigilance, "
            "positionnement par rapport au marché. Sois factuel et précis."
        ),
        INTENT_COMPARISON: (
            "Compare les entités sur les indicateurs disponibles. Identifie les avantages "
            "compétitifs et les faiblesses relatives. Conclue sur le positionnement global."
        ),
        INTENT_KPI_QUERY: (
            "Explique ce que signifie ce chiffre dans le contexte du marché tunisien. "
            "Est-il au-dessus ou en dessous de la moyenne ? Quelle est sa signification pratique ?"
        ),
        INTENT_MARKET_OVERVIEW: (
            "Dresse un tableau synthétique du marché. Souligne les dynamiques clés, "
            "le niveau de maturité et les opportunités de développement."
        ),
    }.get(intent, "Commente les données de façon professionnelle et précise.")

    system_prompt = (
        "Tu es un analyste senior en assurances pour EY Tunisie, spécialisé dans le "
        "marché des assurances tunisien (2015-2024). Tu rédiges des analyses concises, "
        "factuelless et professionnelles destinées à des experts du secteur.\n\n"
        "RÈGLES ABSOLUES :\n"
        "- Cite UNIQUEMENT les chiffres présents dans les données fournies\n"
        "- N'invente aucun chiffre, aucune tendance, aucun fait\n"
        "- Si les données sont insuffisantes, dis-le clairement\n"
        "- Réponds en français, max 150 mots, structuré et percutant\n\n"
        f"DONNÉES :\n{data_summary}\n\n"
        f"CONSIGNE D'ANALYSE : {intent_guidance}"
    )
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-4:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_question})

    raw = _call_groq(messages)
    if raw and len(raw.strip()) > 20:
        return raw.strip()
    return _fallback_text(intent, entities, query_results)


def _fallback_text(intent, entities, query_results) -> str:
    kpis = entities.get("kpis") or query_results.get("kpis", [])
    kpi = kpis[0] if kpis else query_results.get("kpi", "")
    return f"Voici les données pour **{kpi}** :" if kpi else "Voici un aperçu des données disponibles :"


def _choose_render(intent, results, entities) -> str:
    if intent == "ranking":
        return RENDER_RANKING
    if intent == "evolution" or (not entities.get("company") and len(results) > 3):
        return RENDER_EVOLUTION
    if intent == "company_profile":
        return RENDER_KPI_CARDS
    if len(results) > 1 and all(r.get("annee") for r in results):
        return RENDER_TABLE
    return RENDER_TEXT


def _default_suggestions() -> list[str]:
    return [
        "Quelle est l'évolution des primes émises depuis 2019 ?",
        "Quel est le taux de pénétration de l'assurance en 2023 ?",
        "Quelle compagnie possède la plus grande part de marché ?",
    ]


def _contextual_suggestions(intent, entities) -> list[str]:
    company = entities.get("company")
    years = entities.get("years", [])
    year = years[0] if years else 2023
    if company:
        name = display_company(company)
        return [f"Quelle est l'évolution du ROE de {name} ?",
                f"Comparer {name} avec les autres compagnies en {year} ?",
                f"Quel est le profil complet de {name} en {year} ?"]
    return _default_suggestions()


def build_greeting() -> dict:
    text = (
        "Bonjour ! Je suis votre assistant IA spécialisé dans le marché des assurances tunisien.\n\n"
        "Je peux répondre à vos questions sur :\n"
        "• Les KPIs financiers — primes, ratios, résultats\n"
        "• Les profils de compagnies — STAR, COMAR, GAT, AMI...\n"
        "• Les tendances et évolutions historiques\n"
        "• Les comparaisons entre compagnies\n"
        "• Les prévisions pour les années futures (2025-2029)\n\n"
        "Comment puis-je vous aider aujourd'hui ?"
    )
    return {"text": text, "render": RENDER_TEXT, "data": {},
            "suggestions": ["Quel est le leader du marché en 2023 ?",
                            "Quelle sera la part de marché de STAR en 2026 ?",
                            "Évolution des primes depuis 2019 ?"], "error": None}


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 8 — CHATBOT ORCHESTRATEUR
# ─────────────────────────────────────────────────────────────────────────────

_MARKET_KPIS = {
    "Produit Interieur Brut (PIB)", "Population Totale",
    "Taux de pénétration", "Densité de l'assurance",
    "Total Primes émises", "Primes émises Vie", "Primes émises Non-Vie",
    "Ratio S/P", "Ratio de frais", "Ratio combiné",
    "Nombre d'assureurs", "Total agences",
}


class Chatbot:
    def process(self, session_id: str, user_message: str) -> dict:
        session = get_session(session_id)
        session.add_message("user", user_message)

        # Message de correction court
        _correction = re.match(
            r"^(non|pas|plutot|plutôt|correction|en fait)[,.\s]*(on parle de|je veux dire|je parle de)?\s*(.*)$",
            user_message.strip().lower()
        )
        if _correction and len(user_message.split()) <= 8:
            ctx = session.context
            clarification = _correction.group(3).strip()
            if not clarification:
                resp = {"text": "Je m'excuse. Pouvez-vous préciser votre question ?",
                        "render": RENDER_TEXT, "data": {}, "suggestions": _default_suggestions(), "error": None}
                session.add_message("assistant", resp["text"])
                return resp
            user_message = f"{clarification} {ctx['last_year']}" if ctx.get("last_year") else clarification

        entities = extract_entities(user_message, session.context)
        intent = detect_intent(user_message, entities)

        # Follow-up année uniquement
        _year_only = re.match(
            r"^(et\s+)?(pour\s+|en\s+|de\s+)?(201[5-9]|202[0-9])\s*\??$",
            user_message.strip().lower()
        )
        ctx = session.context
        if _year_only and ctx.get("last_intent") and intent not in (INTENT_GREETING, INTENT_COMPANY_PROFILE):
            intent = ctx["last_intent"]
            if not entities.get("company") and ctx.get("last_company"):
                entities["company"] = ctx["last_company"]
            if not entities.get("kpis") and ctx.get("last_kpis"):
                entities["kpis"] = ctx["last_kpis"]

        session.update_context(entities, intent=intent)
        history = session.get_history_for_llm()

        # Enrichissement question (contexte "même année")
        enriched = self._enrich_question(user_message, session.context)

        # ── RAG Réglementaire ─────────────────────────────────────────────────
        if intent == INTENT_REGULATORY:
            reg_resp = self._handle_regulatory(user_message, history, session)
            if reg_resp:
                return reg_resp

        # ── Prévision (années futures) ────────────────────────────────────────
        if intent == INTENT_FORECAST:
            forecast_resp = self._handle_forecast(entities, user_message, enriched, history, session_id, session)
            if forecast_resp:
                return forecast_resp

        # ── Text-to-SQL ───────────────────────────────────────────────────────
        query_results = self._fetch_with_sql(intent, entities, enriched, history, session_id)
        if not query_results.get("results") and query_results.get("error") is None:
            query_results = self._fetch_data(intent, entities, user_message)

        # Réponse Text-to-SQL directe
        if query_results.get("text_override"):
            response = {"text": query_results["text_override"], "render": RENDER_TEXT,
                        "data": query_results, "suggestions": [], "error": None}
            session.add_message("assistant", response["text"], data=query_results)
            return response

        # ── Couche générative ─────────────────────────────────────────────────
        response = build_response(user_message, intent, entities, query_results, history)
        session.add_message("assistant", response.get("text", ""), data=query_results)
        return response

    def _enrich_question(self, question: str, ctx: dict) -> str:
        q = question.strip()
        lq = q.lower()
        same_year_pat = re.compile(
            r"\b(la\s+m[eê]me\s+ann[ée]e?|cette\s+ann[ée]e?|idem|pareil|m[eê]me\s+ann[ée]e?)\b",
            re.IGNORECASE
        )
        if same_year_pat.search(q) and ctx.get("last_year"):
            q = same_year_pat.sub(str(ctx["last_year"]), q)
        if not re.search(r"\b(201[5-9]|202[0-9])\b", q) and ctx.get("last_year"):
            if any(w in lq for w in ["meme", "même", "pareil", "idem", "aussi", "également"]):
                q = f"{q} en {ctx['last_year']}"
        if ctx.get("last_company") and re.search(r"\b(lui|eux|elle|cette compagnie|cet assureur)\b", lq):
            q = f"{q} pour {ctx['last_company']}"
        return q

    def _fetch_with_sql(self, intent, entities, question, history, session_id) -> dict:
        if intent == INTENT_GREETING:
            return {"results": [], "intent": intent}
        try:
            with _db() as conn:
                result = answer_with_sql(conn, question, history)
            if result.get("error") or not result.get("rows"):
                return {"results": [], "intent": intent}
            return {"results": result["rows"], "text_override": result["text"],
                    "sql": result.get("sql"), "intent": intent}
        except Exception as e:
            logger.error(f"Text-to-SQL error: {e}", exc_info=True)
            return {"results": [], "intent": intent}

    def _fetch_data(self, intent, entities, raw_question) -> dict:
        if intent == INTENT_GREETING:
            return {"results": [], "intent": intent}
        with _db() as conn:
            try:
                company = entities.get("company")
                years = entities.get("years", [])
                kpis = entities.get("kpis", [])
                available_years = fetch_available_years(conn)
                default_year = available_years[0] if available_years else 2023
                year = years[0] if years else default_year

                if intent == INTENT_RANKING:
                    _leader_pat = re.compile(r"\b(leader|num[eé]ro\s*1|n°\s*1|premier[e]?|top\s*1)\b", re.IGNORECASE)
                    limit = 1 if _leader_pat.search(raw_question) else 10
                    kpi = kpis[0] if kpis else "Part de marché (%)"
                    rows = fetch_ranking(conn, kpi, year, limit=limit)
                    if not rows:
                        kpi = "Primes émises par assurance"
                        rows = fetch_ranking(conn, kpi, year, limit=limit)
                    return {"results": rows, "kpi": kpi, "annee": year, "intent": intent}

                if intent == INTENT_COMPANY_PROFILE and company:
                    profile = fetch_company_profile(conn, company, year)
                    return {"results": [profile], "company": company, "annee": year, "intent": intent}

                if intent == INTENT_MARKET_OVERVIEW:
                    overview = fetch_market_overview(conn, year)
                    return {"results": [overview], "annee": year, "intent": intent}

                if intent == INTENT_EVOLUTION:
                    all_results = []
                    for kpi in kpis[:2]:
                        if company and kpi not in _MARKET_KPIS:
                            rows = fetch_kpi_for_company(conn, kpi, company, None)
                        else:
                            rows = fetch_kpi_for_market(conn, kpi, None)
                        all_results.extend(rows)
                    return {"results": all_results, "kpis": kpis, "intent": intent}

                if kpis:
                    all_results = []
                    for kpi in kpis[:2]:
                        if company and kpi not in _MARKET_KPIS:
                            rows = fetch_kpi_for_company(conn, kpi, company, year)
                        else:
                            rows = fetch_kpi_for_market(conn, kpi, year)
                        all_results.extend(rows)
                    return {"results": all_results, "kpis": kpis, "annee": year, "intent": intent}

                if company:
                    profile = fetch_company_profile(conn, company, year)
                    return {"results": [profile], "company": company, "annee": year, "intent": INTENT_COMPANY_PROFILE}

                overview = fetch_market_overview(conn, year)
                return {"results": [overview], "annee": year, "intent": INTENT_MARKET_OVERVIEW}

            except Exception as e:
                logger.error(f"Query error: {e}", exc_info=True)
                return {"results": [], "error": f"Erreur : {e}"}

    def _handle_forecast(self, entities, raw_question, enriched_question,
                         history, session_id, session) -> dict | None:
        company = entities.get("company")
        kpis = entities.get("kpis", [])
        future_years = [int(y) for y in re.findall(r"\b(202[5-9]|203\d)\b", raw_question)]
        horizon = max(max(future_years) - 2024, 1) if future_years else 1
        horizon = min(horizon, 5)
        kpi = kpis[0] if kpis else None
        if not kpi:
            return None

        # ── Tentative Prophet/XGBoost ─────────────────────────────────────────
        narrative = None
        model_used = None
        try:
            from prediction.inference.forecast_service import ForecastService
            with _db() as conn:
                narrative = ForecastService(conn).predict_text(company=company, kpi=kpi, horizon=horizon)
            model_used = "Prophet/XGBoost"
        except Exception as exc:
            logger.warning(f"ForecastService indisponible ({exc}), fallback régression linéaire")

        # ── Fallback : régression linéaire sur données historiques ───────────
        if not narrative:
            narrative = self._linear_forecast(company, kpi, horizon)
            model_used = "Régression linéaire (tendance historique)"

        if not narrative:
            return None

        # Récupérer contexte historique pour l'explication causale (amélioration 3)
        causal_context = ""
        try:
            with _db() as conn:
                if company:
                    hist_rows = fetch_kpi_for_company(conn, kpi, company, year=None)
                else:
                    hist_rows = fetch_kpi_for_market(conn, kpi, year=None)
            hist_rows = sorted(hist_rows, key=lambda r: r.get("annee", 0))[-6:]
            if hist_rows:
                hist_str = ", ".join(
                    f"{r['annee']}: {r.get('valeur', '?')}" for r in hist_rows
                )
                causal_context = f"\nDonnées historiques récentes : {hist_str}"
        except Exception:
            pass

        entity_label = display_company(company) if company else "le marché tunisien"
        system_prompt = (
            "Tu es un analyste senior en assurances chez EY Tunisie. "
            "À partir des données de prévision, rédige une analyse en deux parties :\n"
            "1. **Prévision** : présente les chiffres avec l'intervalle de confiance\n"
            "2. **Explication causale** : identifie les facteurs qui expliquent la tendance "
            "(dynamique concurrentielle, macro-économique, réglementaire). "
            "Cite des éléments concrets du marché tunisien.\n\n"
            "RÈGLES : cite uniquement les chiffres fournis. Max 200 mots. "
            f"Modèle utilisé : {model_used}."
        )
        llm_raw = _call_groq([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": (
                f"Question: {raw_question}\n\n"
                f"Entité analysée : {entity_label}\n"
                f"KPI : {kpi}\n"
                f"Horizon : {horizon} an(s)\n"
                f"{causal_context}\n\n"
                f"Données de prévision :\n{narrative}"
            )},
        ])
        answer_text = llm_raw if llm_raw else narrative
        response = {"text": answer_text, "render": RENDER_TEXT,
                    "data": {"forecast": True, "kpi": kpi, "company": company, "horizon": horizon},
                    "suggestions": [
                        f"Évolution historique de {kpi} ?",
                        f"Comparer les prévisions avec les concurrents ?",
                        "Quel est le taux de pénétration prévu pour 2027 ?",
                    ], "error": None}
        session.add_message("assistant", answer_text)
        return response

    def _linear_forecast(self, company: str | None, kpi: str, horizon: int) -> str | None:
        """Régression linéaire simple sur données historiques — fallback sans dépendances ML."""
        try:
            import numpy as np
            with _db() as conn:
                if company:
                    rows = fetch_kpi_for_company(conn, kpi, company, year=None)
                else:
                    rows = fetch_kpi_for_market(conn, kpi, year=None)
            rows = [r for r in rows if r.get("valeur") is not None
                    and isinstance(r.get("valeur"), (int, float))]
            if len(rows) < 3:
                return None
            rows.sort(key=lambda r: r["annee"])
            years = np.array([r["annee"] for r in rows], dtype=float)
            values = np.array([r["valeur"] for r in rows], dtype=float)
            # Régression polynomiale degré 1
            coeffs = np.polyfit(years, values, 1)
            slope, intercept = coeffs
            last_year = int(years[-1])
            last_val = float(values[-1])
            unit = rows[0].get("unit", "")
            entity_label = (f"la compagnie {display_company(company)}" if company
                            else "le marché tunisien")
            lines = [
                f"Prévision — {kpi} pour {entity_label}",
                f"Données historiques : {int(years[0])}–{last_year} ({len(rows)} points)",
                f"Dernière valeur connue ({last_year}) : {last_val:,.2f} {unit}".strip(),
                f"Tendance annuelle estimée : {slope:+.3f} {unit}/an",
                "",
                "Prévisions :",
            ]
            for h in range(1, horizon + 1):
                target_year = last_year + h
                pred = float(np.polyval(coeffs, target_year))
                # Intervalle ±10% (heuristique)
                ci_low = pred * 0.90
                ci_high = pred * 1.10
                lines.append(
                    f"  {target_year} : {pred:,.2f} {unit} "
                    f"[IC80% : {ci_low:,.2f}–{ci_high:,.2f} {unit}]".strip()
                )
            lines += [
                "",
                "Méthode : régression linéaire (OLS) sur données 2015–2024.",
                "Limites : modèle sans saisonnalité ni effets macro-économiques externes.",
            ]
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Linear forecast error: {e}")
            return None

    def _handle_regulatory(self, question: str, history: list[dict], session) -> dict | None:
        """RAG sur corpus réglementaire tunisien."""
        try:
            from rag_module import get_rag
            rag = get_rag()
            retrieved = rag.retrieve(question, top_k=3)
            if not retrieved:
                return None
            answer_text = rag.answer(question, _call_groq, history)
            response = {
                "text": answer_text,
                "render": RENDER_TEXT,
                "data": {"regulatory": True, "sources": [d["source"] for d in retrieved]},
                "suggestions": [
                    "Quel est le capital minimum requis pour une compagnie ?",
                    "Comment sont calculées les provisions techniques ?",
                    "Quelle est la réglementation sur l'assurance Takaful ?",
                ],
                "error": None,
            }
            session.add_message("assistant", answer_text)
            return response
        except Exception as e:
            logger.error(f"RAG error: {e}", exc_info=True)
            return None

    def greet(self, session_id: str) -> dict:
        session = get_session(session_id)
        response = build_greeting()
        session.add_message("assistant", response["text"])
        return response

    def reset(self, session_id: str) -> dict:
        get_session(session_id).reset()
        return self.greet(session_id)

    def get_history(self, session_id: str) -> list[dict]:
        return session_to_dict(get_session(session_id))


_bot_instance: Chatbot | None = None


def get_chatbot() -> Chatbot:
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = Chatbot()
    return _bot_instance


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 9 — FLASK API
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/api/chatbot")


def _llm_available() -> bool:
    if os.environ.get("GROQ_API_KEY"):
        try:
            import groq  # noqa
            return True
        except ImportError:
            pass
    return False


def _session_id() -> str:
    sid = request.headers.get("X-Session-ID")
    if not sid and request.is_json:
        sid = (request.get_json(silent=True) or {}).get("session_id")
    return sid or str(uuid.uuid4())


@chatbot_bp.post("")
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Paramètre 'message' manquant"}), 400
    session_id = _session_id()
    try:
        response = get_chatbot().process(session_id, message)
        return jsonify({
            "session_id": session_id,
            "text": response.get("text", ""),
            "render": response.get("render"),
            "data": response.get("data"),
            "suggestions": response.get("suggestions", []),
            "error": response.get("error"),
            "llm_available": _llm_available(),
        })
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@chatbot_bp.post("/greet")
def greet():
    session_id = _session_id()
    response = get_chatbot().greet(session_id)
    return jsonify({"session_id": session_id, "text": response.get("text", ""),
                    "render": response.get("render"), "suggestions": response.get("suggestions", []),
                    "llm_available": _llm_available()})


@chatbot_bp.post("/reset")
def reset():
    session_id = _session_id()
    response = get_chatbot().reset(session_id)
    return jsonify({"session_id": session_id, "text": response.get("text", ""),
                    "suggestions": response.get("suggestions", []), "llm_available": _llm_available()})


@chatbot_bp.get("/history")
def history():
    session_id = request.headers.get("X-Session-ID") or request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id requis"}), 400
    return jsonify({"session_id": session_id, "messages": get_chatbot().get_history(session_id)})


@chatbot_bp.get("/status")
def status():
    return jsonify({"status": "ok", "llm_available": _llm_available(), "db_path": DB_PATH})


app.register_blueprint(chatbot_bp)

# CORS (utile si le frontend tourne sur un autre port)
@app.after_request
def _cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Session-ID"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


# ─────────────────────────────────────────────────────────────────────────────
#  POINT D'ENTRÉE
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Console Windows par défaut en cp1252 : les print() avec accents/✓
    # plantent au démarrage sans ce reconfigure (UnicodeEncodeError).
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    # Charger .env si présent
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    port = int(os.environ.get("PORT", 5001))
    print(f"✓ Chatbot Assurance — http://localhost:{port}/api/chatbot")
    print(f"✓ Base de données : {DB_PATH}")
    print(f"✓ LLM disponible  : {_llm_available()}")
    app.run(host="0.0.0.0", port=port, debug=False)
