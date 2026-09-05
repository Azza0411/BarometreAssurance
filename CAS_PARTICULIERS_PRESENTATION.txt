# Cas particuliers — Extraction "Présentation de la société"

Module : `extraction/presentation_kpi_extractor.py`
KPI : Date de création, Nombre d'actions, Siège social, Effectif.

Contrairement aux autres tableaux (Bilan, Annexe 12/13, États de résultat),
cette source est un **paragraphe narratif**, pas un tableau. La détection
repose sur des lignes à puce "Libellé : Valeur" — on ne retient une
correspondance que si le texte AVANT le premier ":" correspond au motif
attendu (ex: "Date de constitution"), ce qui évite les faux positifs quand un
mot comme "effectif" apparaît ailleurs dans une phrase.

"Cours de l'action" est volontairement exclu du périmètre : à cet endroit du
document, la seule valeur disponible est la **valeur nominale** de l'action
(ex: "10D chacune"), pas un cours de bourse réel. À traiter plus tard via une
source boursière (BVMT), sur décision de l'utilisateur.

## Résolu

- **Libellé variable pour la date** : "Date de constitution" (STAR, BH,
  ASTREE) vs "Date de création" (COMAR) → les deux motifs sont acceptés.
- **Séparateurs de milliers mixtes dans le nombre d'actions** : ex. BH écrit
  "2 660.000 actions" (espace ET point comme séparateurs dans le même
  nombre) → tous les espaces/points/virgules sont supprimés avant conversion,
  quel que soit le séparateur utilisé.
- **"Siège social" quasi-universel** : présent en page de garde
  ("AVIS DES SOCIÉTÉS") pour toutes les sociétés testées, en plus de la
  section "Présentation de la société" — couverture proche de 100% sur
  l'échantillon testé (STAR, BH, ASTREE, COMAR, GAT, TUNIS_RE, ATTIJARI,
  LLOYD_TUNISIEN, MAGHREBIA).

## Non résolu / limitations connues

- **Capital social écrit en toutes lettres (COMAR)** : "Soixante-quinze
  millions de dinars entièrement libérés" — aucun chiffre, donc aucun nombre
  d'actions extractible sur cette ligne pour COMAR.
- **Nombre d'actions absent de la ligne "Capital social" (ASTREE,
  MAGHREBIA)** : la ligne ne mentionne que le montant total du capital, pas
  le nombre d'actions ni leur valeur nominale → KPI non disponible pour ces
  sociétés à cet endroit du document (l'info existe parfois ailleurs, ex.
  dans les notes sur les capitaux propres — non exploré pour l'instant, cf.
  ci-dessous).
- **Effectif rarement présent dans ce paragraphe** : sur l'échantillon
  testé, seul STAR l'y mentionne directement ("Effectif : 512"). Chez COMAR,
  la ligne "Effectif au 31/12/2023 :" n'a pas de nombre inline — le détail
  est donné juste après sous forme de tableau par catégorie professionnelle
  (Cadres/Employés/Personnel contractuel) : non sommé automatiquement pour
  l'instant (nécessiterait une règle générale de somme des lignes suivantes,
  pas encore implémentée faute de récurrence confirmée sur d'autres
  sociétés). Chez BH, ASTREE, GAT, TUNIS_RE, ATTIJARI, LLOYD_TUNISIEN et
  MAGHREBIA, "Effectif" n'apparaît pas du tout dans le bloc de présentation.
- **Format narratif sans puces "Libellé : Valeur" (LLOYD_TUNISIEN,
  TUNIS_RE)** : la présentation est un paragraphe en prose ("La société ...
  est une société anonyme au capital de 45 000 000DT, divisé en 9 000 000
  actions..." / "...a été créée en 1981 à l'initiative des pouvoirs
  publics..."). Date de création et Nombre d'actions non extraits pour ces
  deux sociétés avec l'approche actuelle (ciblée sur le format à puces, qui
  est le plus courant et le plus fiable à généraliser).
- **Date de création absente du format à puces (GAT, MAGHREBIA)** : GAT ne
  semble pas avoir de ligne "Date de constitution/création" repérée dans les
  25 premières pages ; MAGHREBIA l'exprime en prose ("Fondée en 1973") sans
  ":" exploitable.
- **Section "Présentation de la société" non localisée (ATTIJARI)** :
  aucune ligne "Date de constitution/création" trouvée dans les 25 premières
  pages du document testé — à ré-examiner si le document a une structure
  différente d'une année sur l'autre.

Chiffres de couverture sur l'échantillon de 9 sociétés testé manuellement
(STAR, BH, ASTREE, COMAR, GAT, TUNIS_RE, ATTIJARI, LLOYD_TUNISIEN,
MAGHREBIA) : Siège social 9/9, Date de création 4/9, Nombre d'actions 2/9,
Effectif 1/9.

**Chiffres réels sur les 222 documents en base** (pipeline complet du
2026-07-04) : Siège social 199/222 (~90%, fiable), Date de création 39/222
(~18%), Nombre d'actions 8/222 (~4%), **Effectif 1/222 (quasiment jamais
trouvé)**. "Effectif" tel que positionné dans ce module (uniquement dans le
paragraphe de présentation) n'est donc pas une source fiable pour ce KPI sur
l'ensemble du corpus — la plupart des sociétés ne le mentionnent pas à cet
endroit précis du document (voir "Non résolu" ci-dessus : COMAR le détaille
par catégorie professionnelle plutôt qu'en un total direct, BH/ASTREE/GAT/
TUNIS_RE/ATTIJARI/LLOYD_TUNISIEN/MAGHREBIA ne l'y mentionnent pas du tout).
Il faudrait chercher ce KPI ailleurs dans le document (piste non explorée :
une note sur les charges de personnel, présente plus loin dans les états
financiers) si une meilleure couverture est souhaitée.
