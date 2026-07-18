# Cas particuliers — extraction des KPI du Bilan (CMF)

Ce fichier recense les variantes de mise en page/formulation déjà rencontrées
lors de l'extraction des KPI depuis les PDF du portail CMF, qu'elles soient
résolues ou non. À mettre à jour à chaque nouveau cas découvert, pour ne pas
perdre le travail d'investigation déjà fait.

## Cas résolus

| Société / document | Problème rencontré | Solution appliquée |
|---|---|---|
| ASTREE | Libellé "Total capitaux propres avant résultat :" (sans "de l'exercice") | Motif tronqué à "avant resultat" (préfixe, pas de correspondance exacte) |
| GAT | "Total des capitaux propres avant résultat..." (article "des" en plus) ; nombres avec virgule décimale ("113,026") | Motif tolère l'article optionnel "des"/"de l'" ; parsing des décimales |
| ATTIJARI | Ligne totale de l'Actif libellée juste "Total" (pas "Total de l'actif") | Repli : dernière ligne libellée "Total" sur la page Actif |
| ATTIJARI | Tableau Actif à 6 colonnes (brut/amort/net répétés pour les deux années, pas seulement l'année en cours) | Au-delà de 4 colonnes numériques, résolution par position de l'en-tête "Net" le plus à gauche plutôt que par position fixe |
| BH, BNA | Ligne totale de l'Actif sans aucun libellé (juste des chiffres) | Repli : dernière ligne entièrement numérique de la page Actif |
| LLOYD_TUNISIEN | "Total CP Av Résultat Exercice" (très abrégé) ; titre de page "Annexe 1 : ACTIF" (le mot "actif" n'est pas en tout début de ligne) | Motif tolère l'abréviation "CP"/"Av" ; détection de la page Actif élargie (mot "actif" dans les 5 premières lignes, pas seulement en préfixe) |
| TUNIS_RE (2017) | Écart entre deux colonnes voisines aussi faible que ~8pt, proche de l'écart interne à un même nombre → fusion incorrecte de deux valeurs | Seuil de regroupement des chiffres resserré (4pt) |
| ATTIJARI (2021) | pdfplumber fusionne certains groupes de chiffres en un seul "mot" dès l'extraction brute, pour ce document précis | Garde-fou : rejet de toute valeur > 50 milliards de dinars (évite de renvoyer un chiffre faux, mais ne retrouve pas la vraie valeur) |
| COMAR | Le code de section (ex: "AC1") réapparaît seul, sans texte, sur la ligne de total de la section → pris à tort pour le début d'une NOUVELLE section, coupant la plage trop tôt | Un code de section n'est retenu comme titre que s'il est suivi d'un texte descriptif ; un code seul est ignoré |
| Toutes sociétés (sections AC1-AC7/PA3/PA7) | La dernière section d'une page (ex: AC7, PA7) n'a pas de section suivante pour délimiter sa plage → engloberait la ligne de total général qui suit | Bornes de fin supplémentaires : toute ligne "Total..." détectée, et par défaut la toute dernière ligne de la page |
| GAT | Le total d'une section est inscrit directement sur sa ligne de titre (pas sur une ligne séparée comme STAR/COMAR) ; les sous-éléments qui suivent (même à 0) ne doivent pas l'écraser | Si la ligne de titre porte déjà ≥2 colonnes de chiffres, on la garde telle quelle sans chercher plus loin |
| BH | Un renvoi de note isolé ("1", "2"...) collé au libellé d'une section est pris pour une valeur, notamment quand il s'agit en réalité de la ligne de titre de la section SUIVANTE incluse par erreur en bord de plage | On exige au moins 2 colonnes de chiffres pour qu'une ligne soit retenue comme un total valide (un chiffre isolé est presque toujours un renvoi de note) |
| ASTREE, BH | Le code de section (AC1..AC7, PA1..PA7) n'est pas détectable tel quel : chiffre absent (BH: "ac creances") ou collé sans espace au libellé (ASTREE: "ac3placements", "acactifs incorporels") | Repli par reconnaissance du texte de la section quand aucun code n'est détecté sur toute la page ; en cas de collision avec un sous-élément contenant le même mot (ex: "AC34 Créances pour espèces déposées..." vs "AC6 Créances"), on retient le libellé le plus court comme vrai titre de section |
| ASTREE | Même problème de collage sans espace pour les lignes de détail directes (ex: "ac33autres placements financiers" pour le KPI OPCVM) | Motifs de lignes de détail non ancrés en début de chaîne (recherche de sous-chaîne au lieu de préfixe strict) |
| ASTREE, BH, LLOYD_TUNISIEN | Pas de ligne "Total du Passif" séparée : seul le total combiné "Total des capitaux propres et du passif" est affiché | Non résolu — voir section suivante |

## Cas non résolus (à reprendre plus tard)

| Société / document | Problème | Piste envisageable |
|---|---|---|
| AMI (quasi toutes années), CARTE_VIE, UIB, HAYETT, COMAR (2018), BNA (2024), STAR (certaines années) | Pages scannées en image, aucun texte extractible | OCR (ex: pytesseract) |
| AL_AMANAH_TAKAFUL | Document entièrement rédigé en arabe | Ajout de motifs de recherche en arabe |
| AT_TAKAFULIA, ZITOUNA_TAKAFUL | "Bilan combiné" Takaful : colonnes séparées "Fonds des Adhérents" / "Entreprise", structure comptable différente | Logique d'extraction dédiée au modèle Takaful |
| COTUNACE | Texte corrompu par un OCR de mauvaise qualité à la source (fautes de caractères aléatoires) | Correspondance floue tolérante aux fautes, ou nouvel OCR du PDF |
| COTUNACE (ratios, 2024) | Ratios combiné/frais extraits à ~54 millions % (numéros de page ou de montant capturés à la place) | Filtrés côté API (`app.py` : ratio > 1 000 % → `None`) ; extraction sous-jacente non corrigée |
| ATTIJARI (2021) | "Total actif" non retrouvé après rejet de la valeur aberrante (cf. garde-fou ci-dessus) | Reconstruction au niveau caractère plutôt qu'au niveau mot |
| TUNIS_RE (2024) | "Total actif" extrait comme 2.0 (numéro de page ou de rangée capturé à la place de la valeur financière) | Filtré côté API (`app.py` : `total_actif < 10 000` → remplacé par `None`) ; extraction sous-jacente non corrigée |
| ASTREE, BH, LLOYD_TUNISIEN (et probablement d'autres) | Pas de ligne "Total du Passif" séparée dans le document source — seul le total combiné "Total des capitaux propres et du passif" existe | Dérivable par calcul (Total combiné − Capitaux propres), mais risqué : nécessiterait la variante "avant affectation" des capitaux propres (incluant le résultat de l'exercice), différente du KPI "Capitaux propres" retenu ("avant résultat") — pas implémenté pour éviter un chiffre subtilement faux |
| Plusieurs sociétés | KPI "Placements représentant des provisions techniques" (section AC4, contrats en unités de compte) souvent absent (33/186 documents testés) | Probablement une absence légitime pour la majorité des assureurs non-vie (pas de produits en unités de compte), à confirmer au cas par cas si le taux surprend |

## Corrections apportées à la spécification KPI fournie par l'utilisateur

| KPI | Référence fournie initialement | Référence corrigée | Raison |
|---|---|---|---|
| Placements représentant des provisions techniques | Ligne "Part des réassureurs dans les provisions techniques" | Ligne "Placements représentant les provisions techniques afférentes aux contrats en unités de compte" (AC4) | Doublon avec le KPI "Part des réassureurs..." — ce sont deux concepts différents en assurance (voir ci-dessus) |
| Autres passifs | Sous-colonne "Net" | Pas de sous-colonne : colonne de la date la plus récente uniquement | Les tableaux Passif n'ont pas de ventilation Brut/Amortissement/Net (confirmé par l'utilisateur) |
