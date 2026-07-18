"""
Accès MySQL : création du schéma et opérations sur les tables `sources`
(origines des documents : CMF, FTUSA...), `cmf` (sociétés suivies par la
source CMF), `documents` (métadonnées des documents, toutes sources
confondues) et `kpi_values`.

Aucun contenu binaire n'est stocké : seuls le nom du PDF, l'année et le lien
d'origine sont conservés.
"""

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
            # la FK cmf_id -> cmf(id) : il faut retirer la FK avant de
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
                "FOREIGN KEY (cmf_id) REFERENCES cmf(id)"
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


def init_schema(conn):
    """Crée les tables `sources`, `cmf`, `documents` et `kpi_values` si elles
    n'existent pas, et fait évoluer le schéma existant si besoin."""
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
        cur.execute("SELECT id FROM cmf WHERE code = %s", (code,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "INSERT INTO cmf (code, nom_entreprise) VALUES (%s, %s)",
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
            LEFT JOIN cmf c ON c.id = d.cmf_id
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


def get_kpi_values_for_document(conn, document_id):
    """Renvoie {kpi: valeur_nombre|valeur_texte} pour un document (les KPI
    numériques et textuels sont fusionnés dans le même dict, chaque KPI
    n'ayant jamais les deux à la fois)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT kpi, valeur_nombre, valeur_texte FROM kpi_values WHERE document_id = %s",
            (document_id,),
        )
        return {kpi: (nombre if nombre is not None else texte) for kpi, nombre, texte in cur.fetchall()}


def list_documents_by_source(conn, source_nom):
    """Renvoie [(document_id, cmf_id, code, annee), ...] pour tous les
    documents d'une source donnée (ex: "FTUSA", "CGA", "INS")."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.cmf_id, c.code, d.annee
            FROM documents d
            JOIN sources s ON s.id = d.source_id
            LEFT JOIN cmf c ON c.id = d.cmf_id
            WHERE s.nom = %s
            ORDER BY d.annee
            """,
            (source_nom,),
        )
        return cur.fetchall()


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
        LEFT JOIN cmf c ON c.id = d.cmf_id
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
