# Cas particuliers — extraction des KPI de l'Annexe N°12 (Résultat technique par catégorie d'assurance Vie)

Même principe que extraction/CAS_PARTICULIERS.md (Bilan) et
extraction/CAS_PARTICULIERS_ANNEXE13.md (Annexe 13, Non-Vie) : ce fichier
recense les variantes de mise en page/formulation rencontrées pour ce
tableau, résolues ou non.

## Contexte du tableau

Pendant "Assurance Vie" de l'Annexe 13 (Non-Vie) : même structure générale
(catégories en colonnes + une colonne d'agrégat à la fin), mais catégorisé
par TYPE DE CONTRAT (Mixte, Décès, TDI, Épargne, Unité de compte) plutôt que
par branche d'assurance. La colonne d'agrégat n'est pas toujours nommée
"Total" littéralement (ex: "Montant" chez GAT) — on prend systématiquement
la DERNIÈRE colonne, quel que soit son intitulé exact.

## Point d'attention métier (pas un bug)

**COMAR n'a pas d'activité Vie propre : sa filiale dédiée à l'assurance Vie
est HAYETT** (déjà dans notre registre de sociétés). C'est pourquoi
l'Annexe 12 de COMAR est très réduite/simplifiée par rapport à GAT (qui a
une activité Vie directe plus détaillée) — plusieurs KPI absents chez COMAR
ne sont donc pas une anomalie d'extraction, mais un reflet de la réalité de
l'activité de la société. Pour une vision complète de l'activité Vie liée à
COMAR, se référer aux données de HAYETT plutôt qu'à celles de COMAR.

## Cas résolus

| Société / document | Problème rencontré | Solution appliquée |
|---|---|---|
| GAT | Colonne d'agrégat nommée "Montant" au lieu de "Total" | Toujours la dernière colonne de la ligne, indépendamment de l'intitulé de l'en-tête |
| COMAR | Ligne "Charges des provisions d'assurance vie et des autres provisions techniques" absente (COMAR n'a pas d'activité Vie propre, voir ci-dessus) ; "Primes acquises" et "Charges de prestations" ne sont que des titres de section sans total explicite | Comportement attendu, pas de correction nécessaire — ces KPI restent légitimement absents pour cette société |

## Cas non résolus (à reprendre plus tard)

| Société / document | Problème | Piste envisageable |
|---|---|---|
| STAR | Aucune page correspondant à cette annexe trouvée dans le document (2017) | Vérifier si l'annexe existe sous un autre numéro/titre, ou si elle est simplement absente de ce rapport |
