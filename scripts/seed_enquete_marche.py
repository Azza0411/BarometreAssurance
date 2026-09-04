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

import json  # sérialiser les listes/dicts en texte JSON pour les stocker en colonne texte
import os  # construire le chemin racine du projet
import sys  # modifier le chemin de recherche des modules Python

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # ajoute la racine du repo pour importer "database"

from database.repository import (
    get_connection,  # ouvre la connexion MySQL
    get_or_create_company,  # récupère ou crée l'id de la société (table societes)
    get_or_create_source,  # récupère ou crée l'id de la source "ENQUETE" (table sources)
    save_document,  # enregistre le "document" représentant l'enquête (upsert)
    save_kpi_value,  # insère/actualise un KPI numérique ou texte (upsert)
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
        "all": {  # segment agrégé : toutes les catégories de répondants confondues
            "genre":    [67, 33],  # % Homme, % Femme
            "age":      [14, 16, 27, 22, 13, 8],  # % de répondants par tranche d'âge
            "typePro":  [  # répartition par catégorie socio-professionnelle
                {"x": "Profession libérale", "y": 38},
                {"x": "Secteur privé",       "y": 26},
                {"x": "Secteur public",      "y": 20},
                {"x": "Retraité",            "y": 12},
                {"x": "Étudiants",           "y": 3},
                {"x": "Sans emploi",         "y": 1},
            ],
            "vehicule":   78,  # % des répondants possédant un véhicule
            "proprio":    52,  # % des répondants propriétaires de leur logement
            "professions": [  # professions les plus citées (nom, % de citations)
                ["Commerçant", 23], ["Avocat", 23], ["Médecin", 23], ["Taxiste", 23],
                ["Kiné", 23], ["Expert-comptable", 23], ["Consultant", 23],
            ],
            "revFam": {  # revenu familial : tranches (labs) + % de répondants (vals)
                "labs": ["Refus", "≥4690 TND/Mois", "[2050,4695] TND/Mois", "[1150,2046] TND/Mois", "<1150 TND/Mois"],
                "vals": [3, 18, 34, 42, 3],
            },
            "revInd": {  # revenu individuel : tranches (labs) + % de répondants (vals)
                "labs": ["Refus", "≥10000 TND/Mois", "[5000,10000] TND/Mois", "[800,5000] TND/Mois", "<800 TND/Mois"],
                "vals": [5, 16, 34, 40, 5],
            },
        },
        "particuliers": {  # segment "Particuliers" (mêmes champs que "all", cf. ci-dessus)
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
        "professionnels": {  # segment "Professionnels"
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
        "etudiants": {  # segment "Étudiants"
            "genre":    [48, 52],
            "age":      [65, 30, 5, 0, 0, 0],
            "typePro":  [{"x": "Étudiants", "y": 100}],
            "vehicule": 40, "proprio": 10,
            "professions": [["Lycée / Université", 65], ["Master / Ingénieur", 30], ["Doctorat", 5]],
            "revFam": {"labs": ["Refus","≥4690 TND/Mois","[2050,4695] TND/Mois","[1150,2046] TND/Mois","<1150 TND/Mois"], "vals": [5,5,15,40,35]},
            "revInd": {"labs": ["Refus","≥10000 TND/Mois","[5000,10000] TND/Mois","[800,5000] TND/Mois","<800 TND/Mois"], "vals": [10,2,8,30,50]},
        },
        "tre": {  # segment "TRE" (Tunisiens Résidents à l'Étranger)
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
        "retraites": {  # segment "Retraités"
            "genre":    [70, 30],
            "age":      [0, 0, 2, 18, 45, 35],
            "typePro":  [{"x": "Retraité", "y": 100}],
            "vehicule": 65, "proprio": 75,
            "professions": [["Ex-fonctionnaire", 55], ["Ex-secteur privé", 30], ["Ex-prof. libérale", 15]],
            "revFam": {"labs": ["Refus","≥4690 TND/Mois","[2050,4695] TND/Mois","[1150,2046] TND/Mois","<1150 TND/Mois"], "vals": [5,20,35,30,10]},
            "revInd": {"labs": ["Refus","≥10000 TND/Mois","[5000,10000] TND/Mois","[800,5000] TND/Mois","<800 TND/Mois"], "vals": [5,15,30,35,15]},
        },
    },
    "entreprises": {  # bloc séparé : volet "Entreprises" de l'enquête (BDD Corporate)
        "secteurs": [  # répartition par secteur d'activité
            {"x": "Commerce",           "y": 32}, {"x": "Industrie",          "y": 32},
            {"x": "Santé",              "y": 9},  {"x": "Sociétés de services","y": 8},
            {"x": "Enseignement",       "y": 7},  {"x": "Autre",              "y": 6},
            {"x": "Transport",          "y": 2},
        ],
        "employes": {  # répartition par tranche d'effectif salarié
            "labs": ["entre 5 et 19", "entre 20 et 99", "100 et plus"],
            "vals": [39, 36, 25],
        },
        "ca": {  # répartition par tranche de chiffre d'affaires annuel
            "labs": ["Refus", ">10 000 000", "[5 000 000, 10 000 000[", "[500 000, 5 000 000[", "<500 000"],
            "vals": [20, 13, 12, 26, 29],
        },
    },
}


# ------------------------------------------------------------------ #
# Écriture en base
# ------------------------------------------------------------------ #

# Utilité : point d'entrée unique — crée le référentiel puis insère tous les KPI
def seed(conn):  # insère tout ENQUETE_DATA en base via une seule connexion
    source_id = get_or_create_source(conn, "ENQUETE", "Enquête de marché")  # source "ENQUETE" (pas une URL, juste un libellé)
    cmf_id    = get_or_create_company(conn, "STAR", "Société Tunisienne d'Assurances et de Réassurance")  # rattache l'enquête à la société STAR
    doc_id    = save_document(conn, source_id, cmf_id, "Enquête de marché STAR 2024", 2024, "")  # "document" = l'enquête elle-même (pas de lien PDF)
    conn.commit()  # valide la création de source/société/document avant d'insérer les KPI

    TAB = "Enquête"  # nom d'onglet utilisé pour tous les KPI insérés par ce script

    # Comptages
    for nom, val in ENQUETE_DATA["counts"].items():  # une ligne de KPI numérique par segment compté
        save_kpi_value(conn, doc_id, TAB, f"Comptage - {nom}", valeur_nombre=val)

    # Segments
    for seg_key, seg in ENQUETE_DATA["segments"].items():  # parcourt les 6 segments (all + 5 catégories)
        p = f"Segment {seg_key}"  # préfixe commun du nom de KPI pour ce segment
        save_kpi_value(conn, doc_id, TAB, f"{p} - genre",      valeur_texte=json.dumps(seg["genre"]))  # liste sérialisée en JSON texte
        save_kpi_value(conn, doc_id, TAB, f"{p} - age",        valeur_texte=json.dumps(seg["age"]))
        save_kpi_value(conn, doc_id, TAB, f"{p} - typePro",    valeur_texte=json.dumps(seg["typePro"]))
        save_kpi_value(conn, doc_id, TAB, f"{p} - vehicule",   valeur_nombre=seg["vehicule"])  # valeur numérique directe (pas de JSON)
        save_kpi_value(conn, doc_id, TAB, f"{p} - proprio",    valeur_nombre=seg["proprio"])
        save_kpi_value(conn, doc_id, TAB, f"{p} - professions",valeur_texte=json.dumps(seg["professions"]))
        save_kpi_value(conn, doc_id, TAB, f"{p} - revFam",     valeur_texte=json.dumps(seg["revFam"]))
        save_kpi_value(conn, doc_id, TAB, f"{p} - revInd",     valeur_texte=json.dumps(seg["revInd"]))

    # Entreprises
    e = ENQUETE_DATA["entreprises"]  # raccourci vers le sous-bloc entreprises
    save_kpi_value(conn, doc_id, TAB, "Entreprises - secteurs", valeur_texte=json.dumps(e["secteurs"]))
    save_kpi_value(conn, doc_id, TAB, "Entreprises - employes", valeur_texte=json.dumps(e["employes"]))
    save_kpi_value(conn, doc_id, TAB, "Entreprises - ca",       valeur_texte=json.dumps(e["ca"]))

    conn.commit()  # valide l'insertion de tous les KPI
    print(f"OK - Donnees enquete STAR 2024 inserees (doc_id={doc_id})")  # confirmation console


if __name__ == "__main__":  # ne s'exécute que si le script est lancé directement
    conn = get_connection()  # ouvre la connexion MySQL
    try:
        seed(conn)  # lance l'insertion complète (idempotente)
    finally:
        conn.close()  # ferme la connexion, même si une erreur est survenue
