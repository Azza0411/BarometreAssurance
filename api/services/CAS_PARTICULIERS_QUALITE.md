# Cas particuliers — Qualité & anomalies (api/services/quality.py, pipeline_audit.py, anomalies_service.py)

Ce fichier suit le même principe que `extraction/CAS_PARTICULIERS*.md` : recense
les limitations connues et les décisions de conception pour cette phase,
mise à jour au fil de l'eau.

## Résolu (juillet 2026 — audit phase Qualité & anomalies)

- **Deux systèmes d'anomalies déconnectés** : `extraction/kpi_extraction_pipeline.py`
  et `extraction/data_cleaning.py` journalisaient `balance_check_failed`/`yoy_anomaly`
  uniquement dans `logs/pipeline.log` (JSON Lines) — invisibles depuis les
  pages Qualité/Anomalies, qui recalculaient leurs propres constats à chaque
  requête sans jamais lire ce log. **Fixé** : nouvelle table `anomalies_detectees`
  (voir `database/schema.sql`, fonctions `save_anomaly`/`get_anomalies` dans
  `database/repository.py`) — persistées à l'extraction, relues par
  `pipeline_audit.py` (étape 7 du rapport) et `quality.py` (type "extraction").
- **Seuils contradictoires** : `quality.py` utilisait `[2 %, 1 000 %]`
  (quasi permissif, RC/RSP/RF seulement) tandis que `pipeline_audit.py`
  utilisait des plages différentes et plus étroites (`_PLAGES`) pour les
  mêmes KPI. **Fixé** : source de vérité unique,
  `extraction.kpi_definitions.KPI_PLAGES_PLAUSIBLES`, importée par les deux
  fichiers.
- **Historique fabriqué** : `anomalies_service.py` ne pouvait publier qu'un
  seul point (aujourd'hui), aucune tendance possible, faute de persistance.
  **Fixé** : `pipelines/run_pipeline.py::_check_quality()` persiste
  désormais un instantané de score à chaque exécution planifiée
  (`source="quality_score_snapshot"`) ; `database/repository.py::get_quality_score_history`
  les relit pour un historique réel. Repli sur le point du jour tant
  qu'aucune exécution planifiée n'a encore eu lieu après cette mise à jour.
- **`PROBLEMATIC_CODES` non documenté par société** : les 8 sociétés
  exclues (`AL_AMANAH_TAKAFUL`, `AT_TAKAFULIA`, `ZITOUNA_TAKAFUL`, `AMI`,
  `CARTE_VIE`, `UIB`, `HAYETT`, `COTUNACE`) partageaient une seule raison
  générique. **Fixé** : raison individuelle par société (voir
  `extraction/CAS_PARTICULIERS.md` pour le détail de chaque cas source).
- **Aucune comparaison sectorielle** : `check_yoy_consistency` compare une
  société à elle-même dans le temps, les garde-fous de plausibilité
  comparent à une plage absolue fixe — aucun contrôle ne comparait une
  société à ses pairs la même année. **Nouvelle capacité** :
  `quality._sector_peer_anomalies` signale une société dont RC/RSP/RF
  s'écarte de plus de ×2 (dans un sens ou l'autre) de la moyenne du secteur,
  à condition qu'au moins 5 sociétés aient une valeur cette année-là (sinon
  la moyenne elle-même n'est pas significative).
- **Zéro test** pour `quality.py`/`pipeline_audit.py`/`anomalies_service.py`.
  **Fixé** : `api/tests/` créé (19 tests) — logique pure testée directement,
  fonctions dépendant de la connexion DB testées via monkeypatch.

## Non résolu / limitations connues

- **`_PLAGES`/`KPI_PLAGES_PLAUSIBLES` sans base empirique citée** —
  contrairement au plancher/plafond de `bilan_kpi_extractor.py`
  (`MIN_PLAUSIBLE_VALUE`/`MAX_PLAUSIBLE_VALUE`), validé sur 186 PDF réels,
  ces plages métier (Ratio combiné 30–500 %, ROE ±200 %...) sont
  raisonnables mais n'ont pas été confrontées aux 186 documents un par un.
  À revisiter si un cas documenté (comme BIAT ou ASTREE en Modélisation)
  révèle une plage trop étroite ou trop large.
- **Seuil de comparaison sectorielle (×2) arbitraire** — choisi pour sa
  simplicité et symétrie (même logique que le contrôle YoY), pas calibré
  empiriquement contre l'historique des 24 sociétés. À ajuster si les
  premiers signalements réels s'avèrent trop bruyants ou trop rares.
- **Table `anomalies_detectees` non bornée dans le temps** — chaque
  exécution planifiée où un déséquilibre/une variation persiste ajoute une
  nouvelle ligne (comportement voulu pour l'historique), mais aucune
  purge/archivage n'est en place si le volume devient important à long terme.
