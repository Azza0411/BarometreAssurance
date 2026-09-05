# Résumé fonctions

> Document de référence : une explication par fonction, regroupée par fichier source. Alimenté au fil des sessions, sert de matière pour les schémas de la présentation.

## config/company_registry.py

### `_normalize_name(name)`

```python
def _normalize_name(name):
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    return name.strip().upper()
```

**Rôle** : nettoyer un nom de société pour que les comparaisons ne soient pas cassées par des accents ou de la casse différente.

**Ligne par ligne** :
- `unicodedata.normalize("NFKD", name)` — sépare chaque lettre accentuée en deux caractères : la lettre de base + l'accent (ex. "é" → "e" + accent séparé).
- `"".join(c for c in name if not unicodedata.combining(c))` — relit chaque caractère un par un et ne garde que ceux qui ne sont pas des accents ; recolle le tout sans rien garder des accents.
- `.strip().upper()` — retire les espaces en trop, met en majuscules.

**Exemple** : `"Générale"` → `"Genera´le"` (décomposé) → `"Generale"` (accents retirés) → `"GENERALE"`.

**D'où vient `name`** (vérifié dans le vrai code, 2 appelants réels) :
- `scraping/bvmt_scraper.py` — un nom de société affiché sur le site de la BVMT, avant recherche du code interne correspondant.
- `extraction/cga_kpi_extractor.py` — un libellé lu à l'intérieur d'un PDF du CGA (ex. une ligne "Nombre d'agences par assureur - STAR"), pendant l'extraction.

Jamais un texte fixe écrit dans le code — toujours un texte trouvé dynamiquement (site scrapé ou PDF en cours de lecture).
