# Cas particuliers — extraction des KPI de l'Annexe N°13 (Résultat technique par catégorie d'assurance Non-Vie)

Même principe que extraction/CAS_PARTICULIERS.md (Bilan) : ce fichier
recense les variantes de mise en page/formulation rencontrées pour ce
tableau, résolues ou non.

## Contexte du tableau

Ce tableau détaille le résultat technique de l'assurance Non-Vie **par
branche** (Incendie, Automobile, Transport, Accidents du Travail...), avec
une colonne "Total" à l'extrême droite qui additionne toutes les branches —
c'est cette colonne qui nous intéresse pour les 7 KPI demandés.

Deux présentations différentes rencontrées pour le même contenu :
  - "Résultat technique par catégorie d'assurance Non Vie" (STAR, GAT...) :
    une colonne par branche + colonne "Total".
  - "Tableau de raccordement du résultat technique par catégorie
    d'assurance aux états financiers" (ASTREE...) : présentation à une
    seule colonne, avec les négatifs notés entre chevrons ("<1 234>") au
    lieu d'un signe moins.

## Cas résolus

| Société / document | Problème rencontré | Solution appliquée |
|---|---|---|
| COMAR | Signe négatif rendu avec le caractère Unicode HYPHEN (U+2010, ex: "‐29 700 121") au lieu du tiret ASCII standard | `NUMERIC_TOKEN_RE` et le parsing des nombres (dans bilan_kpi_extractor, réutilisé ici) tolèrent désormais plusieurs variantes de tiret Unicode |
| COMAR | Les lignes "Primes Acquises" et "Charges de prestations" ne sont que des titres de section sans total explicite (contrairement à STAR où le total apparaît directement sur cette ligne, avant le détail) | Pas de balayage vers l'avant par défaut (contrairement au Bilan) : on ne prend que la valeur présente sur la ligne du libellé lui-même, pour ne jamais confondre avec la ligne suivante qui a son propre libellé distinct et significatif (ex: "Primes Emises") |
| STAR | Le libellé "Résultat technique" du KPI correspond aussi au tout début du TITRE de la page ("Résultat technique par catégorie d'assurance Non Vie...") | Motif exigeant qu'aucun des mots "catégorie"/"assurance" n'apparaisse plus loin dans le même libellé, pour exclure le titre de page |
| STAR | Libellé "Charges d'acquisition et de gestion n[ettes]" coupé avant "ettes" en fin de ligne | Motif arrêté avant "nettes" (comme "et caisse" pour le Bilan) |
| ASTREE | Négatifs notés entre chevrons ("< 2 094 225>" ou tout collé "<11 719 512>") plutôt qu'avec un signe moins | Prétraitement générique (bilan_kpi_extractor._words_with_bracket_negatives_resolved) qui détecte un "<" (seul ou collé au premier chiffre) et préfixe le nombre correspondant d'un "-" |
| ASTREE, TUNIS_RE | Titre de page différent ("Tableau de raccordement...") de la présentation standard ("Résultat technique par catégorie...") | Motif de détection de page élargi pour couvrir les deux formulations |
| TUNIS_RE | Cette annexe se trouve très loin dans le document (page 91 sur 101, société de réassurance aux annexes très détaillées) | Limite de pages scannées augmentée de 45 à 120 |

## Cas non résolus (à reprendre plus tard)

| Société / document | Problème | Piste envisageable |
|---|---|---|
| TUNIS_RE | Le titre de la page est détecté mais la page ne contient presque aucun texte (probablement une image/tableau scanné pour cette annexe précise) | OCR |
| ATTIJARI, et probablement d'autres rapports courts (<40 pages) | Cette annexe n'apparaît pas du tout dans le document (rapport possiblement résumé sans le détail par catégorie) | Vérifier si une version plus complète du rapport existe ailleurs sur le portail CMF |
| GAT | KPI "Provisions pour Primes non acquises" introuvable alors que le reste du tableau est bien détecté (seule la ligne "Variation des primes non acquises" a été trouvée, pas la ligne "Provisions...") | Vérifier si GAT omet cette ligne dans les "Informations complémentaires" de cette annexe, ou si elle est formulée différemment |
| Généralement | KPI "Primes acquises" et "Charges de prestations Non-Vie" absents chez les sociétés qui ne montrent pas explicitement le total agrégé de ces sections (ex: COMAR) — valeur techniquement calculable (Primes Émises + Variation ; Prestations payées + Charges des provisions) mais non dérivée pour éviter un chiffre subtilement faux | Envisager le calcul dérivé si le besoin se confirme, en gardant une marque claire que c'est une valeur calculée et non lue directement |
