"""
Regroupement des 24 gouvernorats de Tunisie en 7 grandes régions
économiques (découpage standard utilisé par l'INS), pour les KPI dérivés
de la répartition géographique des agences d'assurance (source CGA).
"""

GOVERNORATE_TO_REGION = {
    "Tunis": "Grand Tunis",
    "Ariana": "Grand Tunis",
    "Ben Arous": "Grand Tunis",
    "Manouba": "Grand Tunis",
    "Nabeul": "Nord Est",
    "Zaghouan": "Nord Est",
    "Bizerte": "Nord Est",
    "Béja": "Nord Ouest",
    "Jendouba": "Nord Ouest",
    "Le Kef": "Nord Ouest",
    "Siliana": "Nord Ouest",
    "Sousse": "Centre Est",
    "Monastir": "Centre Est",
    "Mahdia": "Centre Est",
    "Sfax": "Centre Est",
    "Kairouan": "Centre Ouest",
    "Kasserine": "Centre Ouest",
    "Sidi Bouzid": "Centre Ouest",
    "Gabès": "Sud Est",
    "Médenine": "Sud Est",
    "Tataouine": "Sud Est",
    "Gafsa": "Sud Ouest",
    "Tozeur": "Sud Ouest",
    "Kébili": "Sud Ouest",
}

REGIONS = sorted(set(GOVERNORATE_TO_REGION.values()))
