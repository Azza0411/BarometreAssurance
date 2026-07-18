# Cas particuliers — extraction des KPI "Charge de sinistres" et "Résultat Net"

Trois KPI répartis sur 3 tableaux résumés (pas les annexes par catégorie
déjà traitées dans CAS_PARTICULIERS_ANNEXE12.md / _ANNEXE13.md) :
  - "L'état de résultat technique de l'assurance vie" -> Charge de sinistres Vie
  - "L'état de résultat technique de l'assurance non-vie" -> Charge de sinistres Non-Vie
  - "L'état de résultat arrêté au [date]" -> Résultat Net

## Cas résolus

| Société / document | Problème rencontré | Solution appliquée |
|---|---|---|
| STAR | Code de ligne collé sans espace au libellé (ex: "chnv1charge de sinistres") | Motifs non ancrés en début de chaîne (recherche de sous-chaîne, comme pour les autres tableaux) |
| STAR, COMAR | Le total de "Charges de sinistres" est parfois sur une ligne séparée après les sous-éléments (STAR : ligne non libellée ; COMAR : code répété seul "CHV1") | Balayage vers l'avant borné par le préfixe de code de ligne (ex: "chnv1" englobe "chnv11"/"chnv12" mais pas "chnv2") — même principe que les sections du Bilan |
| GAT | Faute de frappe dans le document source : "sinsitres" au lieu de "sinistres" (lettres transposées) | Motif tolérant les deux orthographes |
| GAT | Titre de page "annexe n 3 etat de resultat technique..." réparti sur plus de lignes que prévu | Fenêtre de lignes vérifiées pour le titre de page augmentée (3 -> 8) |
| COMAR | Tableau Vie sans le mot "technique" dans son titre ("ETAT DE RESULTAT DE L'ASSURANCE VIE") ; ce même titre "sans technique" faisait à tort matcher le résultat GLOBAL (qui exclut seulement les titres contenant "technique"/"catégorie") | Motif de détection du résultat global élargi pour exclure aussi "assurance vie"/"assurance non vie" ; recherche qui continue sur les pages suivantes si la ligne n'est pas trouvée sur la première page correspondant au titre (au lieu d'abandonner) |
| ASTREE | Ligne "Résultat net" nommée "Résultat net après modifications comptables" (sans "de l'exercice") | Motif réduit à la racine commune "resultat net" |
| BH | Titre de page avec texte inséré entre "assurance" et "vie/non-vie" ("assurance et/ou de la réassurance non Vie") | Motif de titre capturant le texte intermédiaire, puis vérification de la présence de "non" dans ce texte capturé plutôt qu'un enchaînement direct exigé |
| BH | Code de ligne avec espace ("CHNV 2" au lieu de "CHNV2" chez GAT/COMAR) | Motif de détection de code tolérant l'espace optionnel |

## Cas non résolus (à reprendre plus tard)

| Société / document | Problème | Piste envisageable |
|---|---|---|
| BH | KPI "Charge de sinistres Non-Vie" incorrect : quand le code de la section suivante a un chiffre séparé par un espace ("CHNV 2"), ce chiffre est absorbé comme donnée numérique par l'extracteur de nombres plutôt que reconnu comme faisant partie d'un code de ligne — ceci casse à la fois la détection de la frontière de section ET le comptage de colonnes de la ligne concernée | Reconstruire les codes de ligne au niveau des mots bruts (avant filtrage numérique/texte) plutôt qu'après coup sur le libellé déjà séparé des nombres — chantier plus large touchant potentiellement bilan_kpi_extractor et annexe12/13_kpi_extractor aussi |
| STAR | KPI "Charge de sinistres Vie" introuvable (page correspondante scannée en image pour ce document) | OCR |
| GAT | Valeurs "Charge de sinistres" (Vie et Non-Vie) non vérifiées indépendamment (seulement 2 colonnes trouvées sur la ligne d'en-tête au lieu des 4 attendues — possible fusion de chiffres à valider) | Vérifier manuellement contre le PDF source |
