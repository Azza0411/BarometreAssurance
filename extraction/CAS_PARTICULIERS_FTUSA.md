# Cas particuliers — Source FTUSA (annexe "Compte d'exploitation par branche & par entreprise")

Module : `extraction/ftusa_kpi_extractor.py`
KPI (9) : Total / Vie / Non-Vie pour Primes émises, Charges de prestations,
Charges d'acquisition et de gestion nettes.

## Résolu

- **Texte tourné à 90° (pas une rotation de page)** : la page contenant ce
  tableau a `page.rotation == 0`, mais chaque caractère du tableau porte une
  matrice de police tournée (`a=d=0`), ce qui fait ressortir le texte brut
  de pdfplumber lettre par lettre à l'envers (ex: "ENTREPRISE" ->
  "ESIRPERTNE"). Confirmé identique sur 2015, 2019, 2022 et 2024 : c'est
  structurel à cette annexe, pas un accident d'un seul document. Résolu en
  recalculant les coordonnées de chaque caractère selon la rotation inverse
  puis en reconstruisant les mots/lignes normalement (voir
  `_derotate_page_words`) — texte vectoriel réel, donc pas besoin d'OCR.
- **Deux annexes au titre quasi identique** : chaque rapport contient aussi
  une annexe voisine "... PAR BRANCHE EN [année] (NON VIE ET VIE)" avec des
  colonnes différentes (TOTAL NON VIE / TOTAL NON VIE & VIE, sans
  ACCEPTATIONS ni AFF. DIRECTES distincts). Le motif de titre exige
  désormais la présence de "affaires directes" pour cibler spécifiquement
  la bonne annexe.
- **Colonnes manquantes selon la ligne** (ex: "primes émises" n'a pas de
  valeur "Accidents du Travail" en 2024, alors que "charges de
  prestations" l'a) : les valeurs sont retrouvées par correspondance de
  position (x) avec une ligne de référence complète, pas par comptage
  d'index dans la ligne — une colonne absente est ignorée (non comptée
  comme 0) plutôt que de décaler les colonnes suivantes.
- **Nombres négatifs consécutifs collés sans espace** (ex: "104-1" = fin de
  "...350 104" suivi du début de "-1 144..."), qui cassaient le tokenizer
  numérique standard (le signe n'est pas en tête du mot) : fonction générale
  `_split_glued_negative` ajoutée dans `bilan_kpi_extractor.py` (partagée
  par tous les extracteurs), qui sépare ce genre de mot en deux nombres
  avant le regroupement en clusters.
- **En-tête de colonnes trop resserré pour un regroupement par proximité
  horizontale** : l'écart entre deux colonnes voisines (~10-14pt) chevauche
  celui entre deux mots d'une même colonne (ex: "ASS." / "VIE", ~1.5pt) et
  un simple seuil de proximité fusionnait plusieurs colonnes ensemble.
  Résolu en abandonnant le regroupement des mots d'en-tête : chaque colonne
  de donnée est identifiée par sa position dans une ligne de référence
  complète, dans l'ordre sémantique connu et fixe du tableau (8 branches,
  puis Vie), plutôt que par correspondance avec le texte d'en-tête
  (le texte d'en-tête, plus court que les nombres, n'est pas fiablement
  aligné en x avec sa colonne de données).
- **Faute de frappe "EXPLOIATATION"** (lettre en trop) dans le titre de
  cette annexe, présente de façon récurrente sur plusieurs années : motif
  de titre tolérant (`exploia?tation`).

## Non résolu / limitations connues

- **Rapport 2018 : annexe purement et simplement absente du PDF (pas juste
  sous une autre forme).** Vérifié en détail (2026-07-08) : la page 116 (
  sommaire des annexes) annonce bien "IV- Le compte d'exploitation par
  branche (affaires directes, acceptations)", mais le document ne la
  contient jamais — les pages 117 à 129 (dernière page du PDF, 130 pages au
  total) enchaînent directement sur des infographies de synthèse en anglais
  ("TUNISIAN INSURANCE MARKET IN 2018") puis la liste des entreprises,
  sans jamais revenir au tableau détaillé. Ce n'est donc pas un problème de
  format alternatif à gérer côté extracteur : la donnée n'existe tout
  simplement pas dans ce PDF (upload/scan FTUSA incomplet pour cette
  année-là). Le rapport 2018 dispose bien de pages à texte tourné (indices
  63-68), mais leur contenu ("2016 2017 2018", suites de nombres) correspond
  à des graphiques comparatifs annexes, pas au tableau cible.
  Les 9 KPI + 8 KPI de ventilation par branche sont donc introuvables pour
  2018 uniquement ; les autres années testées (2015 à 2017, 2019 à 2024,
  soit 9/10) sont toutes complètes ou quasi-complètes (16-17/17 KPI, la
  colonne "Accidents du Travail" étant parfois absente de la seule ligne
  "primes émises" — voir plus haut).
- **Colonnes "TOTAL (AFF. DIRECTES)" et "ACCEPTATIONS" non exploitées** :
  seules les 8 colonnes de branches, la colonne Vie et la colonne finale
  "TOTAL (AFF. DIR+ACC)" sont utilisées (correspondant exactement aux 9 KPI
  demandés) ; ces 2 colonnes intermédiaires existent dans le tableau mais
  ne sont pas nécessaires pour les KPI actuels.

