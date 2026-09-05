"""
Insère les données de l'enquête de marché STAR dans la base MySQL.
Lancer une seule fois (idempotent grâce aux upserts).

Usage : python scripts/seed_enquete_marche.py

Différence avec les scrapers web (CMF, FTUSA...) : il n'y a ici aucune
collecte automatisée (pas de Selenium, pas de requests HTTP). Les chiffres
ci-dessous (ENQUETE_DATA) sont des statistiques déjà calculées / transcrites
à la main à partir du fichier Excel de l'enquête terrain STAR ; ce script se
contente de les écrire en base via les fonctions de database/repository.py.
Le calcul des mêmes statistiques *à la volée* depuis le fichier Excel
(pour l'API/dashboard live) est fait ailleurs, dans extraction/enquete_extractor.py.
"""

import json  # JSON pour la colonne texte
import os  # chemin racine
import sys  # chemin des modules

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # racine du repo

from database.repository import (
    get_connection,  # connexion MySQL
    get_or_create_company,  # id de la société
    get_or_create_source,  # id source ENQUETE
    save_document,  # document de l'enquête
    save_kpi_value,  # insère un KPI
)

# ------------------------------------------------------------------ #
# Données de l'enquête (dict codé en dur, pas lu depuis un fichier)
# ------------------------------------------------------------------ #
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
        "all": {  # toutes catégories confondues
            "genre":    [67, 33],  # % Homme, % Femme
            "age":      [14, 16, 27, 22, 13, 8],  # % par tranche d'âge
            "typePro":  [  # par catégorie socio-pro
                {"x": "Profession libérale", "y": 38},
                {"x": "Secteur privé",       "y": 26},
                {"x": "Secteur public",      "y": 20},
                {"x": "Retraité",            "y": 12},
                {"x": "Étudiants",           "y": 3},
                {"x": "Sans emploi",         "y": 1},
            ],
            "vehicule":   78,  # % avec véhicule
            "proprio":    52,  # % propriétaires
            "professions": [  # professions les plus citées
                ["Commerçant", 23], ["Avocat", 23], ["Médecin", 23], ["Taxiste", 23],
                ["Kiné", 23], ["Expert-comptable", 23], ["Consultant", 23],
            ],
            "revFam": {  # revenu familial : tranches/%
                "labs": ["Refus", "≥4690 TND/Mois", "[2050,4695] TND/Mois", "[1150,2046] TND/Mois", "<1150 TND/Mois"],
                "vals": [3, 18, 34, 42, 3],
            },
            "revInd": {  # revenu individuel : tranches/%
                "labs": ["Refus", "≥10000 TND/Mois", "[5000,10000] TND/Mois", "[800,5000] TND/Mois", "<800 TND/Mois"],
                "vals": [5, 16, 34, 40, 5],
            },
        },
        "particuliers": {  # segment Particuliers
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
        "professionnels": {  # segment Professionnels
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
        "etudiants": {  # segment Étudiants
            "genre":    [48, 52],
            "age":      [65, 30, 5, 0, 0, 0],
            "typePro":  [{"x": "Étudiants", "y": 100}],
            "vehicule": 40, "proprio": 10,
            "professions": [["Lycée / Université", 65], ["Master / Ingénieur", 30], ["Doctorat", 5]],
            "revFam": {"labs": ["Refus","≥4690 TND/Mois","[2050,4695] TND/Mois","[1150,2046] TND/Mois","<1150 TND/Mois"], "vals": [5,5,15,40,35]},
            "revInd": {"labs": ["Refus","≥10000 TND/Mois","[5000,10000] TND/Mois","[800,5000] TND/Mois","<800 TND/Mois"], "vals": [10,2,8,30,50]},
        },
        "tre": {  # segment TRE (résidents à l'étranger)
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
        "retraites": {  # segment Retraités
            "genre":    [70, 30],
            "age":      [0, 0, 2, 18, 45, 35],
            "typePro":  [{"x": "Retraité", "y": 100}],
            "vehicule": 65, "proprio": 75,
            "professions": [["Ex-fonctionnaire", 55], ["Ex-secteur privé", 30], ["Ex-prof. libérale", 15]],
            "revFam": {"labs": ["Refus","≥4690 TND/Mois","[2050,4695] TND/Mois","[1150,2046] TND/Mois","<1150 TND/Mois"], "vals": [5,20,35,30,10]},
            "revInd": {"labs": ["Refus","≥10000 TND/Mois","[5000,10000] TND/Mois","[800,5000] TND/Mois","<800 TND/Mois"], "vals": [5,15,30,35,15]},
        },
    },
    "entreprises": {  # volet Entreprises (BDD Corporate)
        "secteurs": [  # par secteur d'activité
            {"x": "Commerce",           "y": 32}, {"x": "Industrie",          "y": 32},
            {"x": "Santé",              "y": 9},  {"x": "Sociétés de services","y": 8},
            {"x": "Enseignement",       "y": 7},  {"x": "Autre",              "y": 6},
            {"x": "Transport",          "y": 2},
        ],
        "employes": {  # par tranche d'effectif
            "labs": ["entre 5 et 19", "entre 20 et 99", "100 et plus"],
            "vals": [39, 36, 25],
        },
        "ca": {  # par tranche de CA
            "labs": ["Refus", ">10 000 000", "[5 000 000, 10 000 000[", "[500 000, 5 000 000[", "<500 000"],
            "vals": [20, 13, 12, 26, 29],
        },
    },
}


# ------------------------------------------------------------------ #
# Écriture en base
# ------------------------------------------------------------------ #

# Utilité : point d'entrée unique — crée le référentiel puis insère tous les KPI
def seed(conn):  # insère tout ENQUETE_DATA
    source_id = get_or_create_source(conn, "ENQUETE", "Enquête de marché")  # source ENQUETE
    cmf_id    = get_or_create_company(conn, "STAR", "Société Tunisienne d'Assurances et de Réassurance")  # rattache à STAR
    doc_id    = save_document(conn, source_id, cmf_id, "Enquête de marché STAR 2024", 2024, "")  # document = l'enquête
    conn.commit()  # valide avant les KPI

    TAB = "Enquête"  # onglet des KPI

    # Comptages
    for nom, val in ENQUETE_DATA["counts"].items():  # un KPI par segment compté
        save_kpi_value(conn, doc_id, TAB, f"Comptage - {nom}", valeur_nombre=val)

    # Segments
    for seg_key, seg in ENQUETE_DATA["segments"].items():  # les 6 segments
        p = f"Segment {seg_key}"  # préfixe du nom de KPI
        save_kpi_value(conn, doc_id, TAB, f"{p} - genre",      valeur_texte=json.dumps(seg["genre"]))  # sérialisé en JSON
        save_kpi_value(conn, doc_id, TAB, f"{p} - age",        valeur_texte=json.dumps(seg["age"]))
        save_kpi_value(conn, doc_id, TAB, f"{p} - typePro",    valeur_texte=json.dumps(seg["typePro"]))
        save_kpi_value(conn, doc_id, TAB, f"{p} - vehicule",   valeur_nombre=seg["vehicule"])  # valeur numérique directe
        save_kpi_value(conn, doc_id, TAB, f"{p} - proprio",    valeur_nombre=seg["proprio"])
        save_kpi_value(conn, doc_id, TAB, f"{p} - professions",valeur_texte=json.dumps(seg["professions"]))
        save_kpi_value(conn, doc_id, TAB, f"{p} - revFam",     valeur_texte=json.dumps(seg["revFam"]))
        save_kpi_value(conn, doc_id, TAB, f"{p} - revInd",     valeur_texte=json.dumps(seg["revInd"]))

    # Entreprises
    e = ENQUETE_DATA["entreprises"]  # sous-bloc entreprises
    save_kpi_value(conn, doc_id, TAB, "Entreprises - secteurs", valeur_texte=json.dumps(e["secteurs"]))
    save_kpi_value(conn, doc_id, TAB, "Entreprises - employes", valeur_texte=json.dumps(e["employes"]))
    save_kpi_value(conn, doc_id, TAB, "Entreprises - ca",       valeur_texte=json.dumps(e["ca"]))

    conn.commit()  # valide tous les KPI
    print(f"OK - Donnees enquete STAR 2024 inserees (doc_id={doc_id})")  # confirmation console


if __name__ == "__main__":  # lancé directement
    conn = get_connection()  # connexion MySQL
    try:
        seed(conn)  # insertion complète
    finally:
        conn.close()  # ferme même en cas d'erreur
