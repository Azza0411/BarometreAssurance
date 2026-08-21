# -*- coding: utf-8 -*-
"""
Rafraîchit la copie SQLite locale du chatbot (MarketInsurance.db) à partir
de la base MySQL principale (database/repository.py), qui est la seule
source de vérité pour toutes les données de l'application.

Le chatbot (chatbot_portable/) est un service Flask autonome qui lit sa
propre copie SQLite plutôt que MySQL directement (portabilité/déploiement
Docker sans dépendance MySQL). Sans rafraîchissement régulier, cette copie
dérive silencieusement de la base principale — découvert le 2026-08-18 :
la copie datait du 26 juillet, ne contenait même pas certains documents
recalculés depuis (ex: ZITOUNA_TAKAFUL 2025), ce qui aurait faussé toute
prévision ML bâtie dessus.

Stratégie : reconstruction complète (DELETE puis ré-INSERT avec les IDs
MySQL préservés tels quels) plutôt qu'une synchronisation incrémentale —
la base ne fait que ~300 documents / ~14000 valeurs de KPI, le coût d'un
refresh complet est négligeable et évite toute logique de diff fragile.

Le schéma SQLite est aligné sur la contrainte MySQL exacte
UNIQUE(document_id, tableau, kpi) — la contrainte SQLite d'origine,
UNIQUE(document_id, kpi), est plus stricte que MySQL et aurait rejeté ~300
lignes légitimes où un même nom de KPI existe sous deux tableaux différents
(ex: "Résultat technique Vie" journalisé à la fois sous "Annexe 12/13" et
sous son libellé précis "Annexe 12 - Resultat technique Vie" — même
valeur, deux lignes).

Usage : python chatbot_portable/sync_db.py [--db-path CHEMIN]
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.repository import get_connection as get_mysql_connection

SCHEMA = """
CREATE TABLE sources (
    id   INTEGER PRIMARY KEY,
    nom  TEXT NOT NULL UNIQUE,
    lien TEXT NOT NULL
);

CREATE TABLE cmf (
    id             INTEGER PRIMARY KEY,
    code           TEXT NOT NULL UNIQUE,
    nom_entreprise TEXT NOT NULL
);

CREATE TABLE documents (
    id         INTEGER PRIMARY KEY,
    source_id  INTEGER NOT NULL,
    cmf_id     INTEGER NULL,
    nom_pdf    TEXT NOT NULL,
    annee      INTEGER NOT NULL,
    lien       TEXT NOT NULL,
    date_ajout TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (source_id) REFERENCES sources(id),
    FOREIGN KEY (cmf_id) REFERENCES cmf(id)
);

CREATE TABLE kpi_values (
    id            INTEGER PRIMARY KEY,
    document_id   INTEGER NOT NULL,
    tableau       TEXT NOT NULL,
    kpi           TEXT NOT NULL,
    valeur_nombre REAL NULL,
    valeur_texte  TEXT NULL,
    date_ajout    TEXT DEFAULT (datetime('now')),
    UNIQUE (document_id, tableau, kpi),
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

CREATE INDEX idx_kpi_values_document ON kpi_values(document_id);
CREATE INDEX idx_kpi_values_kpi ON kpi_values(kpi);
CREATE INDEX idx_documents_cmf ON documents(cmf_id);
CREATE INDEX idx_documents_source ON documents(source_id);
"""


def _rebuild_sqlite(sqlite_path: str) -> dict:
    if os.path.exists(sqlite_path):
        os.remove(sqlite_path)
    # WAL sidecar files, si presents d'une session precedente
    for ext in ("-wal", "-shm"):
        sidecar = sqlite_path + ext
        if os.path.exists(sidecar):
            os.remove(sidecar)

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.executescript(SCHEMA)

    mysql_conn = get_mysql_connection()
    counts = {}
    try:
        with mysql_conn.cursor() as cur:
            cur.execute("SELECT id, nom, lien FROM sources")
            rows = cur.fetchall()
            sqlite_conn.executemany("INSERT INTO sources (id, nom, lien) VALUES (?, ?, ?)", rows)
            counts["sources"] = len(rows)

            cur.execute("SELECT id, code, nom_entreprise FROM cmf")
            rows = cur.fetchall()
            sqlite_conn.executemany("INSERT INTO cmf (id, code, nom_entreprise) VALUES (?, ?, ?)", rows)
            counts["cmf"] = len(rows)

            cur.execute("SELECT id, source_id, cmf_id, nom_pdf, annee, lien FROM documents")
            rows = cur.fetchall()
            sqlite_conn.executemany(
                "INSERT INTO documents (id, source_id, cmf_id, nom_pdf, annee, lien) VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
            counts["documents"] = len(rows)

            cur.execute(
                "SELECT id, document_id, tableau, kpi, valeur_nombre, valeur_texte FROM kpi_values"
            )
            rows = cur.fetchall()
            sqlite_conn.executemany(
                "INSERT INTO kpi_values (id, document_id, tableau, kpi, valeur_nombre, valeur_texte) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
            counts["kpi_values"] = len(rows)
    finally:
        mysql_conn.close()

    sqlite_conn.commit()
    sqlite_conn.execute("PRAGMA journal_mode=WAL")
    sqlite_conn.close()
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MarketInsurance.db")
    parser.add_argument("--db-path", default=default_path)
    args = parser.parse_args()

    print(f"Reconstruction de {args.db_path} a partir de MySQL...")
    counts = _rebuild_sqlite(args.db_path)
    for table, n in counts.items():
        print(f"  {table}: {n} lignes")
    print("Termine.")


if __name__ == "__main__":
    main()
