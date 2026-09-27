# Cas particuliers — extraction état de résultat complet (resultat_full_extractor.py)

## 2026-09-27 — CHNT*/PRNT* non reconnus → concaténation de lignes (ASTREE/STAR/COMAR)

**Symptôme** : plusieurs lignes CHNT/PRNT se retrouvaient fusionnées en un
seul libellé garbled incluant le texte ET les valeurs numériques de la ligne
précédente. Exemple ASTREE 2025 : `PRNT1produits des placements assurance non
vie chnt11charges de gestion...1814...`.

**Cause** : `_ROW_CODE_RE` ne couvrait pas les préfixes CHNT/PRNT (charges et
produits non techniques). Sans la reconnaissance du code, les lignes tombaient
dans le branch `else: key = label`, ce qui concaténait l'étiquette avec le
contenu des `pending_label_words` de la ligne précédente.

**Fix** (commit 5a8dba5) : ajout de `CHNT\d*` et `PRNT\d*` dans `_ROW_CODE_RE`
et `_TOP_SECTION_RE`. Re-extraction des 81 documents CMF → 81 OK, 0 erreurs.

---

## 2026-09-27 — Bruit numérique en fin de libellé (limitation connue)

**Symptôme** : certains libellés stockés contiennent des fragments numériques
en fin de chaîne, ex. `chnt3 autres charges non techniques 2 595 3 455`.
Les VALEURS extraites sont correctes ; seul le libellé affiché est bruité.

**Cause probable** : quand le code de ligne (ex. CHNT3) et ses valeurs
apparaissent sur la MÊME ligne PDF mais que `_cluster_lines` les sépare en
deux "lignes" (différence de y légère), la ligne texte seule (sans valeurs)
passe dans le branch `pending_label_words`. Les fragments de nombres
appartenant en réalité à la valeur de la ligne voisine (ex. "2", "595")
peuvent apparaître comme non-numériques si le token ne correspond pas
exactement au pattern `NUMERIC_TOKEN_RE` (par exemple : séparateurs de
milliers non-ASCII, chiffres isolés considérés comme suffixe de note).

**Impact** : cosmétique uniquement. Les valeurs numériques exportées dans
Excel sont correctes. Limitation à documenter, à corriger dans une prochaine
itération si nécessaire.

---

## 2026-09-27 — Sociétés sans etat_resultat extrait (skips connus)

Lors de la re-extraction du 2026-09-27 : 0 SKIP sur 81 documents. Cependant
certaines sociétés/années n'ont pas de données en base car elles n'ont pas
de page etat_resultat reconnue par `pdf_sections` (ex. sociétés Takaful,
CTAMA années manquantes).
