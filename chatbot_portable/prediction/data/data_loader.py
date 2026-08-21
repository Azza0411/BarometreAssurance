"""
Chargement des séries temporelles depuis SQLite.
Responsabilité unique : récupérer les données brutes.
Aucune logique métier ici.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TimeSeriesResult:
    """Résultat brut d'un chargement de série temporelle."""
    kpi: str
    company: str | None          # None = donnée sectorielle (FTUSA/INS)
    source: str                  # CMF | FTUSA | INS | CGA
    data: pd.DataFrame           # colonnes: annee, valeur
    n_points: int
    years: list[int]
    unit: str                    # MDT | % | TND | nombre


# KPIs provenant de sources sectorielles (pas d'une compagnie spécifique)
_MARKET_KPIS: set[str] = {
    "Total Primes émises",
    "Taux de pénétration",
    "Densité de l'assurance",
    "Primes émises Vie",
    "Primes émises Non-Vie",
    "Ratio S/P",
    "Ratio de frais",
    "Ratio combiné",
}

_KPI_UNITS: dict[str, str] = {
    "Primes émises par assurance": "MDT",
    "Total Primes émises": "MDT",
    "Primes émises Vie": "MDT",
    "Primes émises Non-Vie": "MDT",
    "Charge de sinistres": "MDT",
    "Résultat Net": "MDT",
    "Total actif": "MDT",
    "Capitaux propres": "MDT",
    "Part de marché (%)": "%",
    "Ratio combiné (%)": "%",
    "Ratio de sinistralité (%)": "%",
    "Ratio de frais de gestion (%)": "%",
    "ROE (%)": "%",
    "ROA (%)": "%",
    "Taux de pénétration": "%",
    "Densité de l'assurance": "TND/hab",
    "Population Totale": "habitants",
    "Produit Interieur Brut (PIB)": "MDT",
}

_TND_TO_MDT: set[str] = {
    "Primes émises par assurance",
    "Total Primes émises",
    "Primes émises Vie",
    "Primes émises Non-Vie",
    "Charge de sinistres",
    "Résultat Net",
    "Total actif",
    "Capitaux propres",
}


class DataLoader:
    """
    Charge les séries temporelles KPI depuis la base SQLite.

    Usage:
        loader = DataLoader(conn)
        result = loader.load(kpi="Primes émises par assurance", company="STAR")
    """

    def __init__(self, conn):
        """
        Args:
            conn: connexion SQLite (sqlite3.Connection compatible context manager)
        """
        self._conn = conn

    def load(self, kpi: str, company: str | None = None) -> TimeSeriesResult:
        """
        Charge la série temporelle complète pour un KPI donné.

        Args:
            kpi: nom exact du KPI (tel que stocké dans kpi_values.kpi)
            company: code compagnie (ex: "STAR") ou None pour données marché

        Returns:
            TimeSeriesResult avec les données historiques triées par année

        Raises:
            ValueError: si la compagnie ou le KPI est introuvable
        """
        is_market = (company is None) or (kpi in _MARKET_KPIS)

        if is_market:
            df, source = self._load_market_kpi(kpi)
        else:
            df, source = self._load_company_kpi(kpi, company)

        if df.empty:
            logger.warning(f"Aucune donnée trouvée: kpi={kpi!r} company={company!r}")
            return TimeSeriesResult(
                kpi=kpi, company=company, source=source,
                data=df, n_points=0, years=[], unit=_KPI_UNITS.get(kpi, "")
            )

        # Conversion TND → MDT pour les KPIs monétaires CMF/FTUSA
        if kpi in _TND_TO_MDT and source in ("CMF", "FTUSA"):
            df["valeur"] = df["valeur"] / 1_000_000

        df = df.sort_values("annee").reset_index(drop=True)

        logger.info(f"Chargé {len(df)} points: kpi={kpi!r} company={company!r} ({source})")

        return TimeSeriesResult(
            kpi=kpi,
            company=company,
            source=source,
            data=df,
            n_points=len(df),
            years=df["annee"].tolist(),
            unit=_KPI_UNITS.get(kpi, ""),
        )

    def _load_company_kpi(self, kpi: str, company: str) -> tuple[pd.DataFrame, str]:
        """Charge un KPI pour une compagnie spécifique (source CMF).

        Exclut le tableau "Calcul interne" : un même nom de KPI peut exister
        à la fois comme valeur brute extraite (ex: "Primes acquises" issu de
        l'Annexe 13 Non-Vie seule) et comme valeur recalculée sous ce
        tableau (ex: somme Vie+Non-Vie) — voir database/repository.py::
        get_kpi_values_for_document pour l'incident déjà rencontré (ASTREE
        2025, "Primes acquises" lu à 2,86 Md TND au lieu de ~148M via ce
        mélange). Sans ce filtre, une série temporelle pourrait mélanger
        silencieusement des années en valeur brute et d'autres en valeur
        recalculée, faussant toute prévision."""
        rows = self._conn.execute(
            """
            SELECT d.annee, k.valeur_nombre
            FROM kpi_values k
            JOIN documents d ON d.id = k.document_id
            JOIN sources s   ON s.id = d.source_id
            JOIN cmf c       ON c.id = d.cmf_id
            WHERE c.code = ?
              AND k.kpi = ?
              AND k.valeur_nombre IS NOT NULL
              AND k.tableau != 'Calcul interne'
              AND d.annee BETWEEN 2000 AND 2025
            ORDER BY d.annee
            """,
            (company, kpi),
        ).fetchall()

        if not rows:
            return pd.DataFrame(columns=["annee", "valeur"]), "CMF"

        df = pd.DataFrame(rows, columns=["annee", "valeur"])
        # Dédoublonner : garder la valeur médiane si plusieurs docs/an
        df = df.groupby("annee")["valeur"].median().reset_index()
        df.columns = ["annee", "valeur"]
        return df, "CMF"

    def _load_market_kpi(self, kpi: str) -> tuple[pd.DataFrame, str]:
        """Charge un KPI sectoriel (FTUSA, INS ou CGA)."""
        for source in ("FTUSA", "INS", "CGA"):
            rows = self._conn.execute(
                """
                SELECT d.annee, k.valeur_nombre
                FROM kpi_values k
                JOIN documents d ON d.id = k.document_id
                JOIN sources s   ON s.id = d.source_id
                WHERE s.nom = ?
                  AND k.kpi = ?
                  AND k.valeur_nombre IS NOT NULL
                  AND k.tableau != 'Calcul interne'
                  AND d.cmf_id IS NULL
                  AND d.annee BETWEEN 2000 AND 2025
                ORDER BY d.annee
                """,
                (source, kpi),
            ).fetchall()

            if rows:
                df = pd.DataFrame(rows, columns=["annee", "valeur"])
                df = df.groupby("annee")["valeur"].median().reset_index()
                df.columns = ["annee", "valeur"]
                return df, source

        return pd.DataFrame(columns=["annee", "valeur"]), "FTUSA"

    def list_available_companies(self) -> list[str]:
        """Retourne tous les codes compagnies ayant des documents CMF."""
        rows = self._conn.execute(
            "SELECT DISTINCT c.code FROM cmf c JOIN documents d ON d.cmf_id = c.id ORDER BY c.code"
        ).fetchall()
        return [r[0] for r in rows]

    def list_available_years(self, company: str | None = None) -> list[int]:
        """Retourne les années disponibles pour une compagnie (ou le marché)."""
        if company:
            rows = self._conn.execute(
                """
                SELECT DISTINCT d.annee FROM documents d
                JOIN cmf c ON c.id = d.cmf_id
                WHERE c.code = ? ORDER BY d.annee
                """,
                (company,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT DISTINCT annee FROM documents WHERE cmf_id IS NULL ORDER BY annee"
            ).fetchall()
        return [r[0] for r in rows if r[0]]
