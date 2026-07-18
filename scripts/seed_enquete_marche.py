"""
Insère les données de l'enquête de marché STAR dans la base MySQL.
Lancer une seule fois (idempotent grâce aux upserts).

Usage : python scripts/seed_enquete_marche.py
"""

import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.repository import (
    get_connection,
    get_or_create_company,
    get_or_create_source,
    save_document,
    save_kpi_value,
)

# ── Données de l'enquête STAR 2024 ────────────────────────────────────────────
ENQUETE_DATA = {
    # Comptages totaux
    "counts": {
        "Particuliers": 473,
        "Professionnels": 208,
        "TRE": 99,
        "Étudiants": 85,
        "Retraités": 68,
    },
    # Données par segment (clé = identifiant segment)
    "segments": {
        "all": {
            "genre":    [67, 33],
            "age":      [14, 16, 27, 22, 13, 8],
            "typePro":  [
                {"x": "Profession libérale", "y": 38},
                {"x": "Secteur privé",       "y": 26},
                {"x": "Secteur public",      "y": 20},
                {"x": "Retraité",            "y": 12},
                {"x": "Étudiants",           "y": 3},
                {"x": "Sans emploi",         "y": 1},
            ],
            "vehicule":   78,
            "proprio":    52,
            "professions": [
                ["Commerçant", 23], ["Avocat", 23], ["Médecin", 23], ["Taxiste", 23],
                ["Kiné", 23], ["Expert-comptable", 23], ["Consultant", 23],
            ],
            "revFam": {
                "labs": ["Refus", "≥4690 TND/Mois", "[2050,4695] TND/Mois", "[1150,2046] TND/Mois", "<1150 TND/Mois"],
                "vals": [3, 18, 34, 42, 3],
            },
            "revInd": {
                "labs": ["Refus", "≥10000 TND/Mois", "[5000,10000] TND/Mois", "[800,5000] TND/Mois", "<800 TND/Mois"],
                "vals": [5, 16, 34, 40, 5],
            },
        },
        "particuliers": {
            "genre":    [55, 45],
            "age":      [10, 20, 30, 25, 12, 3],
            "typePro":  [
                {"x": "Secteur privé", "y": 45}, {"x": "Secteur public", "y": 30},
                {"x": "Sans emploi",  "y": 15},  {"x": "Profession libérale", "y": 10},
            ],
            "vehicule": 75, "proprio": 45,
            "professions": [["Employé privé", 45], ["Fonctionnaire", 30], ["Sans emploi", 15], ["Autre", 10]],
            "revFam": {"labs": ["Refus","≥4690 TND/Mois","[2050,4695] TND/Mois","[1150,2046] TND/Mois","<1150 TND/Mois"], "vals": [3,15,30,45,7]},
            "revInd": {"labs": ["Refus","≥10000 TND/Mois","[5000,10000] TND/Mois","[800,5000] TND/Mois","<800 TND/Mois"], "vals": [5,10,25,50,10]},
        },
        "professionnels": {
            "genre":    [72, 28],
            "age":      [3, 15, 35, 30, 14, 3],
            "typePro":  [
                {"x": "Profession libérale", "y": 55},
                {"x": "Secteur privé",       "y": 30},
                {"x": "Secteur public",      "y": 15},
            ],
            "vehicule": 90, "proprio": 65,
            "professions": [["Commerçant",23],["Avocat",23],["Médecin",23],["Taxiste",23],["Kiné",23],["Expert-comptable",23],["Consultant",23]],
            "revFam": {"labs": ["Refus","≥4690 TND/Mois","[2050,4695] TND/Mois","[1150,2046] TND/Mois","<1150 TND/Mois"], "vals": [2,30,45,20,3]},
            "revInd": {"labs": ["Refus","≥10000 TND/Mois","[5000,10000] TND/Mois","[800,5000] TND/Mois","<800 TND/Mois"], "vals": [3,25,45,25,2]},
        },
        "etudiants": {
            "genre":    [48, 52],
            "age":      [65, 30, 5, 0, 0, 0],
            "typePro":  [{"x": "Étudiants", "y": 100}],
            "vehicule": 40, "proprio": 10,
            "professions": [["Lycée / Université", 65], ["Master / Ingénieur", 30], ["Doctorat", 5]],
            "revFam": {"labs": ["Refus","≥4690 TND/Mois","[2050,4695] TND/Mois","[1150,2046] TND/Mois","<1150 TND/Mois"], "vals": [5,5,15,40,35]},
            "revInd": {"labs": ["Refus","≥10000 TND/Mois","[5000,10000] TND/Mois","[800,5000] TND/Mois","<800 TND/Mois"], "vals": [10,2,8,30,50]},
        },
        "tre": {
            "genre":    [60, 40],
            "age":      [8, 25, 35, 22, 8, 2],
            "typePro":  [
                {"x": "Secteur privé", "y": 50},
                {"x": "Profession libérale", "y": 30},
                {"x": "Secteur public", "y": 20},
            ],
            "vehicule": 85, "proprio": 70,
            "professions": [["Ingénieur", 35], ["Médecin", 25], ["Informatique", 20], ["Autre", 20]],
            "revFam": {"labs": ["Refus","≥4690 TND/Mois","[2050,4695] TND/Mois","[1150,2046] TND/Mois","<1150 TND/Mois"], "vals": [5,40,35,15,5]},
            "revInd": {"labs": ["Refus","≥10000 TND/Mois","[5000,10000] TND/Mois","[800,5000] TND/Mois","<800 TND/Mois"], "vals": [5,35,40,18,2]},
        },
        "retraites": {
            "genre":    [70, 30],
            "age":      [0, 0, 2, 18, 45, 35],
            "typePro":  [{"x": "Retraité", "y": 100}],
            "vehicule": 65, "proprio": 75,
            "professions": [["Ex-fonctionnaire", 55], ["Ex-secteur privé", 30], ["Ex-prof. libérale", 15]],
            "revFam": {"labs": ["Refus","≥4690 TND/Mois","[2050,4695] TND/Mois","[1150,2046] TND/Mois","<1150 TND/Mois"], "vals": [5,20,35,30,10]},
            "revInd": {"labs": ["Refus","≥10000 TND/Mois","[5000,10000] TND/Mois","[800,5000] TND/Mois","<800 TND/Mois"], "vals": [5,15,30,35,15]},
        },
    },
    "entreprises": {
        "secteurs": [
            {"x": "Commerce",           "y": 32}, {"x": "Industrie",          "y": 32},
            {"x": "Santé",              "y": 9},  {"x": "Sociétés de services","y": 8},
            {"x": "Enseignement",       "y": 7},  {"x": "Autre",              "y": 6},
            {"x": "Transport",          "y": 2},
        ],
        "employes": {
            "labs": ["entre 5 et 19", "entre 20 et 99", "100 et plus"],
            "vals": [39, 36, 25],
        },
        "ca": {
            "labs": ["Refus", ">10 000 000", "[5 000 000, 10 000 000[", "[500 000, 5 000 000[", "<500 000"],
            "vals": [20, 13, 12, 26, 29],
        },
    },
}


def seed(conn):
    source_id = get_or_create_source(conn, "ENQUETE", "Enquête de marché")
    cmf_id    = get_or_create_company(conn, "STAR", "Société Tunisienne d'Assurances et de Réassurance")
    doc_id    = save_document(conn, source_id, cmf_id, "Enquête de marché STAR 2024", 2024, "")
    conn.commit()

    TAB = "Enquête"

    # Comptages
    for nom, val in ENQUETE_DATA["counts"].items():
        save_kpi_value(conn, doc_id, TAB, f"Comptage - {nom}", valeur_nombre=val)

    # Segments
    for seg_key, seg in ENQUETE_DATA["segments"].items():
        p = f"Segment {seg_key}"
        save_kpi_value(conn, doc_id, TAB, f"{p} - genre",      valeur_texte=json.dumps(seg["genre"]))
        save_kpi_value(conn, doc_id, TAB, f"{p} - age",        valeur_texte=json.dumps(seg["age"]))
        save_kpi_value(conn, doc_id, TAB, f"{p} - typePro",    valeur_texte=json.dumps(seg["typePro"]))
        save_kpi_value(conn, doc_id, TAB, f"{p} - vehicule",   valeur_nombre=seg["vehicule"])
        save_kpi_value(conn, doc_id, TAB, f"{p} - proprio",    valeur_nombre=seg["proprio"])
        save_kpi_value(conn, doc_id, TAB, f"{p} - professions",valeur_texte=json.dumps(seg["professions"]))
        save_kpi_value(conn, doc_id, TAB, f"{p} - revFam",     valeur_texte=json.dumps(seg["revFam"]))
        save_kpi_value(conn, doc_id, TAB, f"{p} - revInd",     valeur_texte=json.dumps(seg["revInd"]))

    # Entreprises
    e = ENQUETE_DATA["entreprises"]
    save_kpi_value(conn, doc_id, TAB, "Entreprises - secteurs", valeur_texte=json.dumps(e["secteurs"]))
    save_kpi_value(conn, doc_id, TAB, "Entreprises - employes", valeur_texte=json.dumps(e["employes"]))
    save_kpi_value(conn, doc_id, TAB, "Entreprises - ca",       valeur_texte=json.dumps(e["ca"]))

    conn.commit()
    print(f"OK - Donnees enquete STAR 2024 inserees (doc_id={doc_id})")


if __name__ == "__main__":
    conn = get_connection()
    try:
        seed(conn)
    finally:
        conn.close()
