# Sociétés exclues des filtres de la plateforme

Ces sociétés sont retirées de tous les sélecteurs de compagnies en raison de problèmes dans le traitement de leurs PDFs. Elles sont définies dans `api/services/quality.py` (`PROBLEMATIC_CODES`), réutilisées dans `api/routes/comparative.py` et `api/routes/vue_assurance.py`.

| Société | Raison |
|---|---|
| **AL_AMANAH_TAKAFUL** | PDFs rédigés en arabe — extraction texte non fiable |
| **AMI** | PDFs quasi entièrement scannés (la quasi-totalité des années) |
| **CARTE_VIE** | PDFs scannés — OCR insuffisant pour extraire les KPIs |
| **UIB** | PDFs scannés — OCR insuffisant pour extraire les KPIs |
| **HAYETT** | PDFs scannés — OCR insuffisant pour extraire les KPIs |
| **COTUNACE** | Corruption OCR chronique — données extraites non fiables |

## Sociétés avec problèmes partiels (non exclues)

Ces sociétés ont des problèmes sur certaines années seulement et restent disponibles dans les filtres. Voir `extraction/CAS_PARTICULIERS.md` pour le détail année par année.

| Société | Années concernées | Nature du problème |
|---|---|---|
| **TUNIS_RE** | 2023, 2024 | Problèmes d'extraction sur ces années spécifiques |
| **ZITOUNA_TAKAFUL** | 2018 | PDF scanné, aucun texte extractible (besoin d'OCR) |
| **ZITOUNA_TAKAFUL** | 2020 | Encodage de police corrompu à la source (besoin d'OCR) |

## Modifier la liste

Pour réintégrer ou exclure une société, éditer le set `PROBLEMATIC_COMPANIES` dans `api/app.py` et redémarrer le serveur Flask.
