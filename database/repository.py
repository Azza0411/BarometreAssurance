"""
Accès MySQL : création du schéma et opérations sur les tables `sources`
(origines des documents : CMF, FTUSA...), `societes` (les compagnies suivies,
toutes sources confondues — ex-nommée `cmf`, renommée pour ne pas la
confondre avec la source "CMF" de la table `sources`), `documents`
(métadonnées des documents, toutes sources confondues) et `kpi_values`.

Aucun contenu binaire n'est stocké : seuls le nom du PDF, l'année et le lien
d'origine sont conservés.
"""

import json
import os
import re

import pymysql

from config.db_config import DB_CONFIG

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def ensure_database():
    """Crée la base de données si elle n'existe pas déjà."""
    conn = pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        conn.close()


def get_connection():
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset="utf8mb4",
        autocommit=True,
    )


def _migrate_kpi_values_schema(conn):
    """Fait évoluer une table `kpi_values` déjà existante (ancienne colonne
    unique `valeur` DOUBLE NOT NULL) vers `valeur_nombre` / `valeur_texte`,
    pour que les KPI textuels (Date de création, Siège social...) puissent
    cohabiter avec les KPI numériques sans perdre les valeurs déjà stockées."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COLUMN_NAME FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'kpi_values'
            """
        )
        columns = {row[0] for row in cur.fetchall()}
        if not columns:
            return
        if "valeur" in columns and "valeur_nombre" not in columns:
            cur.execute("ALTER TABLE kpi_values CHANGE COLUMN valeur valeur_nombre DOUBLE NULL")
        if "valeur_texte" not in columns:
            cur.execute("ALTER TABLE kpi_values ADD COLUMN valeur_texte VARCHAR(500) NULL AFTER valeur_nombre")


def _migrate_documents_schema(conn):
    """Fait évoluer une table `documents` déjà existante (ancien schéma
    100% CMF : `cmf_id NOT NULL`, sans notion de source) vers un schéma
    multi-source : ajoute `source_id`, rend `cmf_id` nullable (pour les
    sources sectorielles comme FTUSA, sans société associée), rattache les
    documents déjà en base à la source CMF, et met à jour la clé unique en
    conséquence. Chaque étape est vérifiée indépendamment via
    information_schema, pour pouvoir reprendre en toute sécurité une
    migration interrompue en cours de route, et n'avoir aucun effet une fois
    le schéma à jour (y compris sur une base fraîchement créée)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COLUMN_NAME FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'documents'
            """
        )
        columns = {row[0] for row in cur.fetchall()}
        if not columns:
            return

        if "source_id" not in columns:
            cur.execute(
                "INSERT INTO sources (nom, lien) VALUES ('CMF', 'https://www.cmf.tn') "
                "ON DUPLICATE KEY UPDATE nom = nom"
            )
            cur.execute("SELECT id FROM sources WHERE nom = 'CMF'")
            cmf_source_id = cur.fetchone()[0]
            cur.execute("ALTER TABLE documents ADD COLUMN source_id INT NULL AFTER id")
            cur.execute("UPDATE documents SET source_id = %s", (cmf_source_id,))
            cur.execute("ALTER TABLE documents MODIFY source_id INT NOT NULL")

        cur.execute(
            """
            SELECT IS_NULLABLE FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = 'documents' AND column_name = 'cmf_id'
            """
        )
        if cur.fetchone()[0] == "NO":
            cur.execute("ALTER TABLE documents MODIFY cmf_id INT NULL")

        cur.execute("SHOW INDEX FROM documents")
        indexes = {row[2] for row in cur.fetchall()}
        if "uq_document_cmf_annee" in indexes:
            # Cet ancien index unique (cmf_id, annee) sert aussi de support à
            # la FK cmf_id -> societes(id) : il faut retirer la FK avant de
            # pouvoir le supprimer, puis lui fournir un nouvel index dédié.
            cur.execute(
                """
                SELECT CONSTRAINT_NAME FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'documents'
                  AND constraint_type = 'FOREIGN KEY' AND constraint_name = 'fk_documents_cmf'
                """
            )
            if cur.fetchone():
                cur.execute("ALTER TABLE documents DROP FOREIGN KEY fk_documents_cmf")
            cur.execute("ALTER TABLE documents DROP INDEX uq_document_cmf_annee")
            cur.execute("ALTER TABLE documents ADD INDEX idx_documents_cmf_id (cmf_id)")
            cur.execute(
                "ALTER TABLE documents ADD CONSTRAINT fk_documents_cmf "
                "FOREIGN KEY (cmf_id) REFERENCES societes(id)"
            )

        cur.execute("SHOW INDEX FROM documents")
        indexes = {row[2] for row in cur.fetchall()}
        if "uq_document_source_cmf_annee" not in indexes:
            cur.execute(
                "ALTER TABLE documents ADD UNIQUE KEY uq_document_source_cmf_annee (source_id, cmf_id, annee)"
            )

        cur.execute(
            """
            SELECT CONSTRAINT_NAME FROM information_schema.table_constraints
            WHERE table_schema = DATABASE() AND table_name = 'documents'
              AND constraint_type = 'FOREIGN KEY' AND constraint_name = 'fk_documents_source'
            """
        )
        if not cur.fetchone():
            cur.execute(
                "ALTER TABLE documents ADD CONSTRAINT fk_documents_source "
                "FOREIGN KEY (source_id) REFERENCES sources(id)"
            )


def _migrate_kpi_values_unique_key(conn):
    """Élargit la clé unique de `kpi_values` de (document_id, kpi) à
    (document_id, tableau, kpi). L'ancienne clé permettait à deux tableaux
    différents produisant par erreur le même nom de KPI de s'écraser
    silencieusement l'un l'autre (aucune erreur, aucun log) — seule la
    convention KPI_TABLE_LABEL (chaque nom de KPI mappé à un seul tableau)
    l'empêchait en pratique. La nouvelle clé le rend impossible au niveau du
    schéma plutôt que par convention seule.

    `uq_document_kpi` sert aussi de support à la FK fk_kpi_document
    (document_id -> documents.id) : comme pour l'ancien index
    (cmf_id, annee) de `documents` (voir _migrate_documents_schema), il faut
    retirer la FK avant de pouvoir le supprimer, puis la recréer une fois le
    nouvel index en place. Bug trouvé en production (juillet 2026) : la
    première version de cette migration ne le faisait pas et échouait avec
    "Cannot drop index ... needed in a foreign key constraint"."""
    with conn.cursor() as cur:
        cur.execute("SHOW INDEX FROM kpi_values")
        indexes = {row[2] for row in cur.fetchall()}
        if "uq_document_kpi" in indexes and "uq_document_tableau_kpi" not in indexes:
            cur.execute(
                """
                SELECT CONSTRAINT_NAME FROM information_schema.table_constraints
                WHERE table_schema = DATABASE() AND table_name = 'kpi_values'
                  AND constraint_type = 'FOREIGN KEY' AND constraint_name = 'fk_kpi_document'
                """
            )
            has_fk = cur.fetchone() is not None
            if has_fk:
                cur.execute("ALTER TABLE kpi_values DROP FOREIGN KEY fk_kpi_document")
            cur.execute("ALTER TABLE kpi_values DROP INDEX uq_document_kpi")
            cur.execute(
                "ALTER TABLE kpi_values ADD UNIQUE KEY uq_document_tableau_kpi (document_id, tableau, kpi)"
            )
            if has_fk:
                cur.execute(
                    "ALTER TABLE kpi_values ADD CONSTRAINT fk_kpi_document "
                    "FOREIGN KEY (document_id) REFERENCES documents(id)"
                )


def init_schema(conn):
    """Crée les tables `sources`, `societes`, `documents` et `kpi_values` si
    elles n'existent pas, et fait évoluer le schéma existant si besoin."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        # Retire les commentaires "-- ..." avant de découper sur ";" : un ";"
        # dans un commentaire (ex: une énumération en français) ne doit pas
        # être pris pour une fin d'instruction SQL.
        sql = re.sub(r"--[^\n]*", "", f.read())
    with conn.cursor() as cur:
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                cur.execute(statement)
    _migrate_kpi_values_schema(conn)
    _migrate_documents_schema(conn)
    _migrate_kpi_values_unique_key(conn)


def get_or_create_source(conn, nom, lien):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM sources WHERE nom = %s", (nom,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("INSERT INTO sources (nom, lien) VALUES (%s, %s)", (nom, lien))
        return cur.lastrowid


def get_or_create_company(conn, code, nom_entreprise):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM societes WHERE code = %s", (code,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "INSERT INTO societes (code, nom_entreprise) VALUES (%s, %s)",
            (code, nom_entreprise),
        )
        return cur.lastrowid


def document_exists(conn, source_id, cmf_id, annee):
    with conn.cursor() as cur:
        if cmf_id is None:
            cur.execute(
                "SELECT id FROM documents WHERE source_id = %s AND cmf_id IS NULL AND annee = %s",
                (source_id, annee),
            )
        else:
            cur.execute(
                "SELECT id FROM documents WHERE source_id = %s AND cmf_id = %s AND annee = %s",
                (source_id, cmf_id, annee),
            )
        return cur.fetchone() is not None


def save_document(conn, source_id, cmf_id, nom_pdf, annee, lien):
    """Insère ou met à jour un document. Un SELECT explicite (plutôt qu'un
    ON DUPLICATE KEY) est utilisé car MySQL n'applique pas l'unicité entre
    plusieurs `cmf_id` NULL (cas des sources sectorielles comme FTUSA)."""
    with conn.cursor() as cur:
        if cmf_id is None:
            cur.execute(
                "SELECT id FROM documents WHERE source_id = %s AND cmf_id IS NULL AND annee = %s",
                (source_id, annee),
            )
        else:
            cur.execute(
                "SELECT id FROM documents WHERE source_id = %s AND cmf_id = %s AND annee = %s",
                (source_id, cmf_id, annee),
            )
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE documents SET nom_pdf = %s, lien = %s WHERE id = %s",
                (nom_pdf, lien, row[0]),
            )
            return row[0]
        cur.execute(
            "INSERT INTO documents (source_id, cmf_id, nom_pdf, annee, lien) VALUES (%s, %s, %s, %s, %s)",
            (source_id, cmf_id, nom_pdf, annee, lien),
        )
        return cur.lastrowid


def count_documents(conn, cmf_id):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documents WHERE cmf_id = %s", (cmf_id,))
        return cur.fetchone()[0]


def list_all_documents(conn):
    """Renvoie tous les documents en base, jointés à leur source et (le cas
    échéant) à leur société :
    [(document_id, source_nom, code, nom_entreprise, nom_pdf, annee, lien), ...].
    `code`/`nom_entreprise` sont NULL pour les documents d'une source
    sectorielle sans société associée (ex: FTUSA)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, s.nom, c.code, c.nom_entreprise, d.nom_pdf, d.annee, d.lien
            FROM documents d
            JOIN sources s ON s.id = d.source_id
            LEFT JOIN societes c ON c.id = d.cmf_id
            ORDER BY s.nom, c.code, d.annee
            """
        )
        return cur.fetchall()


def save_kpi_value(conn, document_id, tableau, kpi, valeur_nombre=None, valeur_texte=None):
    """Enregistre un KPI numérique (valeur_nombre) ou textuel (valeur_texte) —
    un seul des deux doit être fourni."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO kpi_values (document_id, tableau, kpi, valeur_nombre, valeur_texte)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE tableau = VALUES(tableau),
                                    valeur_nombre = VALUES(valeur_nombre),
                                    valeur_texte = VALUES(valeur_texte)
            """,
            (document_id, tableau, kpi, valeur_nombre, valeur_texte),
        )


def delete_kpi_value(conn, document_id, tableau, kpi):
    """Supprime un KPI calculé en base (utilisé pour invalider un ratio dont les données sources sont incomplètes)."""
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM kpi_values WHERE document_id = %s AND tableau = %s AND kpi = %s",
            (document_id, tableau, kpi),
        )


def count_kpi_values(conn, document_id):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM kpi_values WHERE document_id = %s", (document_id,))
        return cur.fetchone()[0]


def save_anomaly(conn, source, gravite, code=None, annee=None, kpi=None, details=None):
    """Enregistre une anomalie détectée pendant l'extraction/le nettoyage
    (déséquilibre Bilan, variation YoY implausible...) pour qu'elle soit
    interrogeable par les pages Qualité/Anomalies (voir anomalies_detectees
    dans schema.sql). `details`, si fourni, est sérialisé en JSON."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO anomalies_detectees (source, code, annee, kpi, gravite, details)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (source, code, annee, kpi, gravite, json.dumps(details, ensure_ascii=False) if details else None),
        )


def get_anomalies(conn, annee=None, code=None, source=None):
    """Renvoie les anomalies persistées (les plus récentes d'abord), filtrées
    par année/société/source si fourni. Chaque ligne : {id, detected_at,
    source, code, annee, kpi, gravite, details (dict ou None)}."""
    query = "SELECT id, detected_at, source, code, annee, kpi, gravite, details FROM anomalies_detectees"
    conds, params = [], []
    if annee is not None:
        conds.append("annee = %s")
        params.append(annee)
    if code is not None:
        conds.append("code = %s")
        params.append(code)
    if source is not None:
        conds.append("source = %s")
        params.append(source)
    if conds:
        query += " WHERE " + " AND ".join(conds)
    query += " ORDER BY detected_at DESC"
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return [
        {
            "id": r[0], "detected_at": r[1].isoformat() if r[1] else None,
            "source": r[2], "code": r[3], "annee": r[4], "kpi": r[5],
            "gravite": r[6], "details": json.loads(r[7]) if r[7] else None,
        }
        for r in rows
    ]


def get_quality_score_history(conn, annee=None, limit=90):
    """Renvoie les instantanés de score qualité persistés par
    pipelines/run_pipeline.py::_check_quality() à chaque exécution planifiée
    (source="quality_score_snapshot", un point par exécution — pas par jour :
    plusieurs exécutions le même jour restent des points distincts), pour
    alimenter un historique réel de tendance (voir
    api/services/anomalies_service.py::build_anomalies_systeme). Avant
    juillet 2026, rien n'était persisté : seul le point du jour courant
    pouvait être affiché, jamais de tendance. Renvoie [{date, score,
    n_anomalies}, ...] du plus ancien au plus récent, `limit` points max."""
    query = "SELECT detected_at, details FROM anomalies_detectees WHERE source = %s"
    params = ["quality_score_snapshot"]
    if annee is not None:
        query += " AND annee = %s"
        params.append(annee)
    query += " ORDER BY detected_at DESC LIMIT %s"
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    history = []
    for detected_at, details_json in rows:
        details = json.loads(details_json) if details_json else {}
        history.append({
            "date": detected_at.isoformat(),
            "score": details.get("score"),
            "n_anomalies": details.get("n_anomalies"),
        })
    return list(reversed(history))


def get_kpi_values_for_document(conn, document_id, exclude_tableaux=None):
    """Renvoie {kpi: valeur_nombre|valeur_texte} pour un document (les KPI
    numériques et textuels sont fusionnés dans le même dict, chaque KPI
    n'ayant jamais les deux à la fois).

    Un KPI absent du dict signifie qu'aucune valeur n'a été extraite pour ce
    document — c'est une décision délibérée, pas un oubli : nulle part dans
    le pipeline (extraction, nettoyage, API) une valeur manquante n'est
    reconstituée par interpolation, report de l'année précédente ou moyenne
    sectorielle. Un KPI manquant reste NULL/absent jusqu'aux dashboards
    plutôt que de risquer d'afficher une donnée inventée comme si elle était
    extraite. Voir extraction/data_cleaning.py pour le même principe côté
    contrôle de cohérence (une valeur suspecte est signalée, jamais corrigée
    automatiquement).

    `exclude_tableaux` : tableaux à exclure du dict renvoyé (ex: "Calcul
    interne" pour un appelant qui va lui-même RECALCULER des KPI portant le
    même nom qu'un KPI brut — voir extraction/calculated_kpi_extractor.py::
    compute_cmf_derived_kpis). Un même nom de KPI peut légitimement exister
    sous deux tableaux différents (ex: "Primes acquises" brut, extrait de
    l'Annexe 13 Non-Vie seule ; "Primes acquises" calculé, somme Vie+Non-Vie
    dans "Calcul interne") — la clé UNIQUE en base est (document_id, tableau,
    kpi), pas (document_id, kpi). Sans ce filtre, le dict fusionné ne garde
    qu'UNE des deux valeurs selon l'ordre de retour SQL (non déterministe),
    et un appelant qui recalcule risque de relire sa PROPRE valeur calculée
    au tour précédent comme si c'était la donnée brute — corruption
    auto-référentielle découverte le 2026-08-16 sur ASTREE 2025 ("Primes
    acquises" calculé à 2,86 milliards TND au lieu de ~148M, la valeur
    "Calcul interne" d'un run précédent ayant été relue comme valeur brute)."""
    with conn.cursor() as cur:
        if exclude_tableaux:
            placeholders = ", ".join(["%s"] * len(exclude_tableaux))
            cur.execute(
                f"SELECT kpi, valeur_nombre, valeur_texte FROM kpi_values "
                f"WHERE document_id = %s AND tableau NOT IN ({placeholders})",
                (document_id, *exclude_tableaux),
            )
        else:
            cur.execute(
                "SELECT kpi, valeur_nombre, valeur_texte FROM kpi_values WHERE document_id = %s",
                (document_id,),
            )
        return {kpi: (nombre if nombre is not None else texte) for kpi, nombre, texte in cur.fetchall()}


def get_document_meta(conn, code, annee):
    """Retourne (nom_pdf, lien) pour un document CMF (code, annee), ou (None, None)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.nom_pdf, d.lien
            FROM documents d
            JOIN sources s ON s.id = d.source_id
            JOIN societes c ON c.id = d.cmf_id
            WHERE s.nom = 'CMF' AND c.code = %s AND d.annee = %s
            LIMIT 1
            """,
            (code, annee),
        )
        row = cur.fetchone()
        return row if row else (None, None)


def get_document_id(conn, code, annee):
    """Retourne l'id du document CMF (code, annee), ou None s'il n'existe
    pas encore en base (utilisé pour retrouver le document de l'année
    précédente d'une société, voir extraction/data_cleaning.py)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id
            FROM documents d
            JOIN sources s ON s.id = d.source_id
            JOIN societes c ON c.id = d.cmf_id
            WHERE s.nom = 'CMF' AND c.code = %s AND d.annee = %s
            LIMIT 1
            """,
            (code, annee),
        )
        row = cur.fetchone()
        return row[0] if row else None


def list_documents_by_source(conn, source_nom):
    """Renvoie [(document_id, cmf_id, code, annee), ...] pour tous les
    documents d'une source donnée (ex: "FTUSA", "CGA", "INS")."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.cmf_id, c.code, d.annee
            FROM documents d
            JOIN sources s ON s.id = d.source_id
            LEFT JOIN societes c ON c.id = d.cmf_id
            WHERE s.nom = %s
            ORDER BY d.annee
            """,
            (source_nom,),
        )
        return cur.fetchall()


def get_available_years(conn, source_nom: str) -> list[int]:
    """Renvoie les années distinctes (ordre décroissant) pour lesquelles au
    moins un document de la source donnée existe en base — utilisé pour les
    sélecteurs d'année (Qualité Data, Anomalies Système) afin qu'ils
    reflètent la vraie plage disponible plutôt qu'une liste d'années codée
    en dur."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT d.annee
            FROM documents d
            JOIN sources s ON s.id = d.source_id
            WHERE s.nom = %s
            ORDER BY d.annee DESC
            """,
            (source_nom,),
        )
        return [row[0] for row in cur.fetchall()]


# Préfixes des KPI CGA éclatés par compagnie (voir extraction/cga_kpi_extractor.py
# et extraction/calculated_kpi_extractor.py) : le segment qui suit
# immédiatement le préfixe est un code société, à comparer à `code`. Se fier
# à "ce segment est un code société reconnu dans le registre" (plutôt que ce
# préfixe explicite) serait fragile : des sociétés réelles du CGA (ex: "MAE")
# n'ont pas de code dans config.company_registry et fuiteraient vers toutes
# les autres sociétés.
_PER_COMPANY_KPI_PREFIXES = (
    "Nombre d'agences par assureur - ",
    "Nombre d'agences par compagnie - ",
    "Part de marché réseau (%) - ",
    "Nombre d'agences de la compagnie par région - ",
    "Répartition des agences de la compagnie par gouvernorat - ",
    "Cours de l'action - ",
)


def _belongs_to_company_or_global(kpi_name, code):
    """True si `kpi_name` est soit un KPI global (aucun des préfixes
    éclatés par compagnie), soit spécifique à `code`. Sert à filtrer les
    KPI CGA par compagnie, qui vivent tous sous des documents sectoriels
    (cmf_id NULL) et ne peuvent donc pas être filtrés par société via une
    jointure SQL."""
    for prefix in _PER_COMPANY_KPI_PREFIXES:
        if kpi_name.startswith(prefix):
            company_segment = kpi_name[len(prefix):].split(" - ", 1)[0]
            return company_segment == code
    return True


def get_kpi_values_by_use_case(conn, use_case, annee=None, code=None):
    """Renvoie les valeurs de KPI d'un use case (voir
    config.kpi_registry.KPI_REGISTRY), sous forme de
    [(source, code, annee, kpi, valeur_nombre, valeur_texte), ...].

    `kpi_values` reste la seule source stockée : ceci ne fait qu'un filtre
    au moment de la requête, pas une duplication par use case. Un nom de
    KPI du registre sans suffixe (ex: "Nombre d'agences par assureur")
    retrouve aussi ses variantes éclatées par entité (ex: "... - STAR"),
    via une recherche par préfixe en plus de l'égalité exacte.

    `code` filtre sur la société. Les documents sectoriels (cmf_id NULL,
    ex: FTUSA/INS/CGA) restent inclus pour leurs KPI globaux (ex: Total
    Primes émises), mais leurs KPI éclatés par compagnie (ex: CGA "Nombre
    d'agences par assureur - COMAR") sont exclus s'ils ne correspondent pas
    à `code` — voir _belongs_to_company_or_global (un filtre SQL simple sur
    cmf_id ne suffit pas, ces KPI vivent sous des documents sectoriels)."""
    from config.kpi_registry import KPI_REGISTRY

    names = KPI_REGISTRY[use_case]
    name_clauses = []
    params = []
    for name in names:
        name_clauses.append("(k.kpi = %s OR k.kpi LIKE %s)")
        params.extend([name, f"{name} - %"])

    query = f"""
        SELECT s.nom, c.code, d.annee, k.kpi, k.valeur_nombre, k.valeur_texte
        FROM kpi_values k
        JOIN documents d ON d.id = k.document_id
        JOIN sources s ON s.id = d.source_id
        LEFT JOIN societes c ON c.id = d.cmf_id
        WHERE ({" OR ".join(name_clauses)})
    """
    if annee is not None:
        query += " AND d.annee = %s"
        params.append(annee)
    if code is not None:
        query += " AND (c.code = %s OR d.cmf_id IS NULL)"
        params.append(code)
    query += " ORDER BY d.annee, c.code, k.kpi"

    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    if code is not None:
        rows = [row for row in rows if _belongs_to_company_or_global(row[3], code)]
    return rows


def save_notification(conn, type, titre, message=None, gravite="info", lien=None):
    """Enregistre une notification in-app (cloche de la barre de navigation).
    Appelé par pipelines/run_pipeline.py sur trois événements : nouveau
    document CMF, anomalie qualité critique, échec d'une source."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO notifications (type, titre, message, gravite, lien)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (type, titre, message, gravite, lien),
        )


def get_notifications(conn, limit=30, unread_only=False):
    """Renvoie les notifications les plus récentes d'abord."""
    query = "SELECT id, created_at, type, titre, message, gravite, lien, lu FROM notifications"
    if unread_only:
        query += " WHERE lu = 0"
    query += " ORDER BY created_at DESC LIMIT %s"
    with conn.cursor() as cur:
        cur.execute(query, (limit,))
        rows = cur.fetchall()
    return [
        {
            "id": r[0], "created_at": r[1].isoformat() if r[1] else None,
            "type": r[2], "titre": r[3], "message": r[4],
            "gravite": r[5], "lien": r[6], "lu": bool(r[7]),
        }
        for r in rows
    ]


def count_unread_notifications(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM notifications WHERE lu = 0")
        return cur.fetchone()[0]


def mark_notification_read(conn, notif_id):
    with conn.cursor() as cur:
        cur.execute("UPDATE notifications SET lu = 1 WHERE id = %s", (notif_id,))


def mark_all_notifications_read(conn):
    with conn.cursor() as cur:
        cur.execute("UPDATE notifications SET lu = 1 WHERE lu = 0")


def diff_and_mark_actualites(conn, items):
    """Reçoit la liste d'actualités fraîchement scrapée (dicts avec 'url',
    'titre', 'src', 'date'), renvoie le sous-ensemble jamais vu auparavant
    (clé = url), et persiste TOUS les items (nouveaux et déjà connus) dans
    actualites_vues. Appelé uniquement par pipelines/run_pipeline.py -
    /api/actualites reste un scrape live inchangé, cette table ne sert qu'à
    détecter les nouveautés pour la cloche de notification.

    Premier passage (table vide) : peuple la table SANS rien renvoyer comme
    "nouveau" - tout serait nouveau par définition faute de ligne de base,
    ce qui noierait l'utilisateur sous une notification "50 actualités"
    dès le premier lancement du pipeline après ce déploiement."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM actualites_vues")
        first_run = cur.fetchone()[0] == 0

    nouveaux = []
    with conn.cursor() as cur:
        for it in items:
            url = it.get("url")
            if not url:
                continue
            cur.execute("SELECT id FROM actualites_vues WHERE url = %s", (url,))
            if cur.fetchone() is None and not first_run:
                nouveaux.append(it)
            cur.execute(
                """
                INSERT IGNORE INTO actualites_vues (url, titre, src, date_publication)
                VALUES (%s, %s, %s, %s)
                """,
                (url, (it.get("titre") or "")[:500], it.get("src") or "?", it.get("date")),
            )
    return nouveaux


def diff_and_mark_reglementation(conn, items):
    """Équivalent de diff_and_mark_actualites pour la veille réglementaire
    (table reglementation_vues, clé = id/url du texte source). Même garde
    contre l'avalanche de notifications au premier passage."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM reglementation_vues")
        first_run = cur.fetchone()[0] == 0

    nouveaux = []
    with conn.cursor() as cur:
        for it in items:
            doc_key = it.get("id") or it.get("url")
            if not doc_key:
                continue
            cur.execute("SELECT id FROM reglementation_vues WHERE doc_key = %s", (doc_key,))
            if cur.fetchone() is None and not first_run:
                nouveaux.append(it)
            cur.execute(
                """
                INSERT IGNORE INTO reglementation_vues (doc_key, titre, src, url)
                VALUES (%s, %s, %s, %s)
                """,
                (doc_key, (it.get("titre") or "")[:500], it.get("src") or "?", it.get("url")),
            )
    return nouveaux
