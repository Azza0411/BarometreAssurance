"""
RAG — Retrieval-Augmented Generation sur textes réglementaires tunisiens.

Corpus statique : Code des assurances, circulaires CGA, normes FTUSA.
Retrieval : TF-IDF cosine similarity (sklearn) avec fallback keyword.
"""

from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Corpus réglementaire ─────────────────────────────────────────────────────
# Chaque entrée : { "id", "titre", "source", "date", "texte" }

CORPUS: list[dict] = [
    {
        "id": "code_assurances_art1",
        "titre": "Code des assurances — Champ d'application",
        "source": "Décret-loi n°92-24 du 9 mars 1992",
        "date": "1992",
        "texte": (
            "Le code des assurances tunisien (décret-loi 92-24) régit l'ensemble "
            "des opérations d'assurance et de réassurance en Tunisie. Il établit "
            "les conditions d'agrément des compagnies, les règles de tarification, "
            "les obligations de couverture minimale et les sanctions applicables. "
            "Les compagnies doivent obtenir un agrément de la CGA (Comité Général "
            "des Assurances) pour exercer. Le code distingue les assurances de "
            "dommages (Non-Vie) et les assurances de personnes (Vie)."
        ),
    },
    {
        "id": "provisions_techniques",
        "titre": "Provisions techniques réglementaires",
        "source": "Circulaire CGA n°2006-01",
        "date": "2006",
        "texte": (
            "Les compagnies d'assurance tunisiennes sont tenues de constituer des "
            "provisions techniques suffisantes pour honorer leurs engagements. Les "
            "principales provisions sont : la provision pour primes non acquises "
            "(PPNA), calculée prorata temporis sur les primes émises ; la provision "
            "pour sinistres à payer (PSAP), estimée dossier par dossier ; la "
            "provision mathématique (PM) pour les contrats Vie, calculée actuariellement. "
            "La CGA effectue des contrôles annuels de l'adéquation des provisions. "
            "Toute insuffisance de provisionnement entraîne une mise en demeure "
            "avec délai de régularisation de 3 mois."
        ),
    },
    {
        "id": "solvabilite",
        "titre": "Marge de solvabilité et fonds propres minimaux",
        "source": "Arrêté du Ministère des Finances 2008",
        "date": "2008",
        "texte": (
            "La réglementation tunisienne impose une marge de solvabilité minimale "
            "aux compagnies d'assurance. Pour les assurances Non-Vie, la marge est "
            "calculée comme le maximum de 18% des primes brutes et 26% de la "
            "charge moyenne de sinistres des 3 dernières années. Pour les assurances "
            "Vie, elle correspond à 4% des provisions mathématiques. Le capital "
            "minimum réglementaire est fixé à 10 MDT pour les compagnies Non-Vie "
            "et 5 MDT pour les compagnies Vie. Les compagnies qui ne respectent pas "
            "la marge de solvabilité sont soumises à un plan de redressement imposé "
            "par la CGA."
        ),
    },
    {
        "id": "assurance_auto_obligatoire",
        "titre": "Assurance automobile obligatoire — RC civile",
        "source": "Loi n°2005-86 du 15 août 2005",
        "date": "2005",
        "texte": (
            "L'assurance responsabilité civile automobile est obligatoire en Tunisie "
            "pour tout véhicule motorisé. La loi de 2005 a renforcé les garanties "
            "minimales : indemnisation illimitée pour les dommages corporels aux tiers, "
            "garantie matérielle minimale de 20 000 DT. La tarification de la RC auto "
            "est partiellement réglementée par le Ministère des Finances. Le bureau "
            "CONATUS gère le fonds de garantie pour les victimes de véhicules non "
            "assurés. L'assurance auto représente environ 40% des primes Non-Vie en "
            "Tunisie, ce qui en fait la branche dominante."
        ),
    },
    {
        "id": "ratio_combine_norme",
        "titre": "Ratio combiné — Normes et interprétation",
        "source": "FTUSA — Guide méthodologique",
        "date": "2020",
        "texte": (
            "Le ratio combiné est l'indicateur de performance technique fondamental "
            "en assurance Non-Vie. Il est défini comme la somme du ratio de sinistralité "
            "(charge de sinistres / primes acquises) et du ratio de frais de gestion "
            "(frais généraux / primes émises). Un ratio combiné inférieur à 100% indique "
            "un bénéfice technique. En Tunisie, la moyenne sectorielle oscille entre "
            "95% et 105%. Les compagnies avec un ratio supérieur à 110% sont considérées "
            "comme en difficulté technique. La CGA surveille cet indicateur et peut "
            "imposer des plans d'action correctifs."
        ),
    },
    {
        "id": "controle_cga",
        "titre": "Contrôle et supervision — Rôle de la CGA",
        "source": "Code des assurances — Titre IV",
        "date": "1992",
        "texte": (
            "Le Comité Général des Assurances (CGA) est l'autorité de supervision "
            "du secteur des assurances en Tunisie, placée sous la tutelle du Ministère "
            "des Finances. Ses missions principales : délivrer et retirer les agréments, "
            "contrôler la solvabilité des compagnies, approuver les conditions générales "
            "des contrats pour certaines branches, publier les statistiques annuelles "
            "du secteur. La CGA peut prononcer des sanctions allant de l'avertissement "
            "au retrait d'agrément. Depuis 2015, la CGA publie un rapport annuel "
            "détaillant les indicateurs financiers de chaque compagnie."
        ),
    },
    {
        "id": "takaful",
        "titre": "Assurance Takaful — Cadre réglementaire",
        "source": "Loi n°2014-47 du 24 juillet 2014",
        "date": "2014",
        "texte": (
            "La loi de 2014 a introduit en Tunisie le cadre légal pour l'assurance "
            "Takaful (assurance islamique). Les compagnies Takaful opèrent selon le "
            "principe de mutualité et de partage des risques (Ta'awun), sans intérêt "
            "(Riba). Les acteurs actuels incluent Zitouna Takaful, At-Takafulia et "
            "Al Amanah Takaful. La CGA supervise ces compagnies avec des exigences "
            "spécifiques : comité de conformité charia, séparation des fonds "
            "participants et fonds actionnaires. Le Takaful représente encore une "
            "part marginale du marché (moins de 3% des primes totales en 2023)."
        ),
    },
    {
        "id": "reassurance",
        "titre": "Réassurance — Obligations légales",
        "source": "Code des assurances — Article 72",
        "date": "1992",
        "texte": (
            "Les compagnies d'assurance tunisiennes sont légalement tenues de céder "
            "une quote-part de leurs risques à TUNISRE (Société Tunisienne de "
            "Réassurance), la réassurance publique nationale. Cette cession obligatoire "
            "varie selon les branches : 5% à 25% des primes selon le type de risque. "
            "Au-delà de la cession obligatoire, les compagnies peuvent recourir à des "
            "réassureurs internationaux. TUNISRE garantit également la réassurance des "
            "grands risques industriels et des catastrophes naturelles. Cette obligation "
            "vise à maintenir des primes en Tunisie et à limiter les sorties de devises."
        ),
    },
    {
        "id": "ftusa_statistiques",
        "titre": "FTUSA — Production des statistiques sectorielles",
        "source": "FTUSA — Rapport annuel méthodologique",
        "date": "2023",
        "texte": (
            "La Fédération Tunisienne des Sociétés d'Assurances (FTUSA) regroupe "
            "l'ensemble des compagnies agréées en Tunisie. Elle publie chaque année "
            "les statistiques officielles du secteur : primes émises par branche, "
            "taux de pénétration (primes/PIB), densité (primes par habitant), "
            "sinistres payés et provisions. Les données sont collectées auprès des "
            "compagnies membres et vérifiées par la CGA. Le taux de pénétration en "
            "Tunisie est d'environ 2% du PIB, inférieur à la moyenne africaine (3%) "
            "et très inférieur à la moyenne européenne (7-8%). Le potentiel de "
            "croissance est donc significatif."
        ),
    },
    {
        "id": "ifrs17",
        "titre": "IFRS 17 — Impact sur le secteur tunisien",
        "source": "Note CGA — Veille réglementaire internationale",
        "date": "2023",
        "texte": (
            "La norme IFRS 17 (applicable depuis 2023 dans les pays qui l'adoptent) "
            "révolutionne la comptabilité des contrats d'assurance en imposant une "
            "évaluation à la juste valeur des engagements. La Tunisie n'a pas encore "
            "adopté IFRS 17, mais la CGA surveille son impact sur les filiales de "
            "groupes internationaux présents en Tunisie. Les compagnies concernées "
            "devront retraiter leurs provisions mathématiques Vie selon le modèle BBA "
            "(Building Block Approach). L'adoption éventuelle nécessiterait une révision "
            "du plan comptable des assurances tunisien (PCAAT)."
        ),
    },
    {
        "id": "digitalisation",
        "titre": "Digitalisation et InsurTech en Tunisie",
        "source": "CGA — Rapport stratégique 2022",
        "date": "2022",
        "texte": (
            "La CGA a lancé en 2022 une feuille de route pour la digitalisation du "
            "secteur des assurances. Les axes principaux : e-assurance (vente en ligne "
            "de contrats), traitement électronique des sinistres, télématique auto "
            "(Pay-as-you-drive), et micro-assurance pour les populations non bancarisées. "
            "Plusieurs compagnies tunisiennes ont investi dans des applications mobiles "
            "de déclaration de sinistres. La réglementation sur la signature électronique "
            "et le commerce électronique (loi de 2000) encadre ces initiatives. "
            "L'objectif est d'atteindre 20% de contrats souscrits en ligne d'ici 2025."
        ),
    },
]


# ─── Retrieval TF-IDF ─────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    text = text.lower()
    for c in "éèêëàâäôöîïûùç":
        text = text.replace(c, {"é":"e","è":"e","ê":"e","ë":"e","à":"a","â":"a",
                                  "ä":"a","ô":"o","ö":"o","î":"i","ï":"i","û":"u",
                                  "ù":"u","ç":"c"}.get(c, c))
    tokens = re.findall(r"\b[a-z]{3,}\b", text)
    stopwords = {"les","des","une","pour","par","sur","dans","avec","que","qui",
                 "est","sont","ont","aux","ses","leur","leurs","cette","cet",
                 "ils","elles","nous","vous","mais","donc","comme","plus","tout",
                 "aussi","bien","peut","doit","fait","sans","sous","entre","vers"}
    return [t for t in tokens if t not in stopwords]


def _tfidf_score(query_tokens: list[str], doc_tokens: list[str],
                 all_doc_token_sets: list[list[str]]) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0
    doc_freq = {}
    for dt in set(doc_tokens):
        for dts in all_doc_token_sets:
            if dt in dts:
                doc_freq[dt] = doc_freq.get(dt, 0) + 1
    n_docs = len(all_doc_token_sets)
    score = 0.0
    doc_set = set(doc_tokens)
    for qt in query_tokens:
        if qt in doc_set:
            tf = doc_tokens.count(qt) / len(doc_tokens)
            idf = math.log((n_docs + 1) / (doc_freq.get(qt, 0) + 1)) + 1
            score += tf * idf
    return score


_EXTRA_CORPUS_PATH = Path(__file__).parent / "rag_corpus_extra.json"


def _load_extra_corpus() -> list[dict]:
    """Charge les extraits ingérés automatiquement (voir rag_ingest.py),
    s'ils existent. Absence de fichier = corpus statique seul, pas une erreur."""
    if not _EXTRA_CORPUS_PATH.exists():
        return []
    try:
        with open(_EXTRA_CORPUS_PATH, encoding="utf-8") as f:
            extra = json.load(f)
        logger.info("RAG : %d extrait(s) supplémentaire(s) chargés depuis %s", len(extra), _EXTRA_CORPUS_PATH.name)
        return extra
    except Exception:
        logger.exception("RAG : échec du chargement de %s, corpus statique seul utilisé", _EXTRA_CORPUS_PATH.name)
        return []


class RegulationRAG:
    """Retrieval-Augmented Generation sur le corpus réglementaire."""

    def __init__(self):
        self._corpus = CORPUS + _load_extra_corpus()
        self._doc_tokens = [_tokenize(d["texte"] + " " + d["titre"]) for d in self._corpus]

    def retrieve(self, question: str, top_k: int = 3) -> list[dict]:
        """Retourne les top_k documents les plus pertinents."""
        q_tokens = _tokenize(question)
        scores = [
            (i, _tfidf_score(q_tokens, dt, self._doc_tokens))
            for i, dt in enumerate(self._doc_tokens)
        ]
        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for i, score in scores[:top_k]:
            if score > 0:
                doc = dict(self._corpus[i])
                doc["score"] = round(score, 4)
                results.append(doc)
        return results

    def build_context(self, retrieved: list[dict]) -> str:
        """Formate les documents récupérés en contexte pour le LLM."""
        if not retrieved:
            return "Aucun document réglementaire pertinent trouvé."
        parts = []
        for doc in retrieved:
            parts.append(
                f"[{doc['source']} — {doc['date']}]\n"
                f"**{doc['titre']}**\n{doc['texte']}"
            )
        return "\n\n---\n\n".join(parts)

    def answer(self, question: str, call_groq_fn, history: list[dict]) -> str:
        """
        Répond à une question réglementaire via RAG + LLM.
        call_groq_fn: la fonction _call_groq du chatbot
        """
        retrieved = self.retrieve(question, top_k=3)
        context = self.build_context(retrieved)

        system_prompt = (
            "Tu es un expert juridique et réglementaire spécialisé dans le secteur "
            "des assurances en Tunisie. Réponds uniquement à partir des documents "
            "réglementaires fournis ci-dessous. Si la réponse n'est pas dans les "
            "documents, dis-le clairement. Cite toujours la source (décret, circulaire, "
            "loi) avec l'année. Réponds en français, de façon structurée et précise.\n\n"
            "DOCUMENTS RÉGLEMENTAIRES :\n\n" + context
        )
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history[-4:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": question})

        raw = call_groq_fn(messages)
        if raw:
            sources = [f"{d['source']} ({d['date']})" for d in retrieved]
            return raw + f"\n\n*Sources : {' · '.join(sources)}*"
        # Fallback sans LLM
        return (
            "D'après la réglementation tunisienne :\n\n" + context +
            "\n\n*Sources consultées : " +
            ", ".join(f"{d['source']}" for d in retrieved) + "*"
        )


# Singleton
_rag_instance: RegulationRAG | None = None

def get_rag() -> RegulationRAG:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RegulationRAG()
    return _rag_instance
