-- Schéma pour le stockage des états financiers/rapports de plusieurs sources.
-- `sources`     : une ligne par source de données (CMF, FTUSA, et d'autres à venir).
-- `societes`    : une ligne par société suivie (pertinent pour les sources qui
--                 publient par société, comme CMF ; NULL pour les sources
--                 sectorielles comme FTUSA). Nommée `societes` (et non `cmf`,
--                 son ancien nom historique de l'époque où seul le portail CMF
--                 était scrapé) pour ne pas la confondre avec la source "CMF"
--                 de la table `sources` — elle sert à toutes les sources, pas
--                 seulement à CMF. La colonne `cmf_id` (FK vers cette table)
--                 garde son nom : c'est un identifiant de colonne courant,
--                 sans ambiguïté avec la source CMF.
-- `documents`   : une ligne par document (état financier annuel, rapport
--                 sectoriel...) trouvé pour une source.
-- `kpi_values`  : une ligne par KPI extrait d'un document (Bilan, Annexe 12, Annexe 13...).

CREATE TABLE IF NOT EXISTS sources (
    id   INT AUTO_INCREMENT PRIMARY KEY,
    nom  VARCHAR(50)  NOT NULL UNIQUE,   -- ex: CMF, FTUSA, CGA
    lien VARCHAR(500) NOT NULL           -- URL de base du site source
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS societes (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    code           VARCHAR(50)  NOT NULL UNIQUE,   -- code court (ex: STAR, COMAR)
    nom_entreprise VARCHAR(255) NOT NULL            -- nom exact tel qu'affiché sur le portail CMF
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- cmf_id est NULL pour les documents d'une source sectorielle (ex: FTUSA), qui
-- n'est pas rattachée à une société individuelle. source_id identifie
-- toujours l'origine du document, quelle que soit la source.
CREATE TABLE IF NOT EXISTS documents (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    source_id    INT NOT NULL,
    cmf_id       INT NULL,
    nom_pdf      VARCHAR(255) NOT NULL,             -- ex: STAR_2020.pdf
    annee        SMALLINT NOT NULL,
    lien         VARCHAR(500) NOT NULL,             -- URL du PDF sur le site source
    date_ajout   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_document_source_cmf_annee (source_id, cmf_id, annee),
    CONSTRAINT fk_documents_source FOREIGN KEY (source_id) REFERENCES sources(id),
    CONSTRAINT fk_documents_cmf FOREIGN KEY (cmf_id) REFERENCES societes(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- valeur_nombre / valeur_texte : un seul des deux est renseigné par KPI.
-- Les KPI numériques (Total actif, Effectif...) utilisent valeur_nombre.
-- Les KPI textuels (Date de création, Siège social...) utilisent valeur_texte.
CREATE TABLE IF NOT EXISTS kpi_values (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    document_id   INT NOT NULL,
    tableau       VARCHAR(255) NOT NULL,   -- ex: "Bilan au 31-12-2022", "Annexe 12 - Resultat technique Vie"
    kpi           VARCHAR(255) NOT NULL,   -- ex: "Total actif", "Résultat technique Vie"
    valeur_nombre DOUBLE NULL,
    valeur_texte  VARCHAR(500) NULL,
    date_ajout    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- tableau fait partie de la cle : deux tableaux differents produisant
    -- par erreur le meme nom de KPI ne doivent jamais s'ecraser en silence.
    UNIQUE KEY uq_document_tableau_kpi (document_id, tableau, kpi),
    CONSTRAINT fk_kpi_document FOREIGN KEY (document_id) REFERENCES documents(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Anomalies detectees au moment de l'extraction/nettoyage (desequilibre
-- Actif/Passif, variation annee sur annee implausible...) : jusqu'ici
-- seulement journalisees en JSON Lines dans logs/pipeline.log, invisibles
-- depuis les pages Qualite/Anomalies (api/services/quality.py,
-- pipeline_audit.py, anomalies_service.py), qui recalculent leurs propres
-- constats a chaque requete sans jamais lire ce log. Cette table les rend
-- interrogeables par l'API, et fournit par la meme occasion un historique
-- reel (detected_at) pour le suivi de tendance qualite dans le temps.
CREATE TABLE IF NOT EXISTS anomalies_detectees (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source      VARCHAR(50)  NOT NULL,   -- ex: 'extraction_balance', 'extraction_yoy'
    code        VARCHAR(50)  NULL,       -- societe concernee (NULL si sectoriel)
    annee       SMALLINT     NULL,
    kpi         VARCHAR(255) NULL,
    gravite     VARCHAR(20)  NOT NULL,   -- 'critique' | 'erreur' | 'avertissement' | 'info'
    details     TEXT         NULL,       -- JSON libre (valeurs, ecart, annee precedente...)
    INDEX idx_anomalies_annee (annee),
    INDEX idx_anomalies_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Notifications in-app (cloche dans la barre de navigation) : evenements
-- generes par pipelines/run_pipeline.py (nouveau document CMF, anomalie
-- qualite critique, echec d'une source) et affiches a l'utilisateur sans
-- necessiter de config email/webhook.
CREATE TABLE IF NOT EXISTS notifications (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    type        VARCHAR(50)  NOT NULL,   -- 'nouveau_document' | 'anomalie_critique' | 'echec_pipeline' | 'nouvelle_actualite' | 'nouvelle_reglementation'
    titre       VARCHAR(255) NOT NULL,
    message     TEXT         NULL,
    gravite     VARCHAR(20)  NOT NULL DEFAULT 'info',  -- 'critique' | 'avertissement' | 'info'
    lien        VARCHAR(255) NULL,       -- route frontend a ouvrir au clic (ex: /qualite-donnees)
    lu          TINYINT(1)   NOT NULL DEFAULT 0,
    INDEX idx_notifications_lu (lu),
    INDEX idx_notifications_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Actualites/reglementation deja vues (api/routes/veille.py) : ces 2
-- sections n'avaient jusque-la aucune persistance (scrape live + cache
-- memoire 1h a chaque requete), rendant impossible de detecter un
-- "nouvel article/texte depuis la derniere visite". Ces 2 tables servent
-- UNIQUEMENT a ce diff (cle naturelle = url/id de la source), alimente par
-- pipelines/run_pipeline.py::_run_veille() a chaque execution planifiee -
-- jamais ecrites depuis une route HTTP (les endpoints /api/actualites et
-- /api/veille-reglementaire restent des scrapes live, inchanges).
CREATE TABLE IF NOT EXISTS actualites_vues (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    url               VARCHAR(500) NOT NULL,
    titre             VARCHAR(500) NOT NULL,
    src               VARCHAR(50)  NOT NULL,
    date_publication  VARCHAR(20)  NULL,
    date_ajout        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_actualites_vues_url (url),
    INDEX idx_actualites_vues_date (date_ajout)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reglementation_vues (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    doc_key     VARCHAR(64)  NOT NULL,  -- id (hash) ou url du texte source
    titre       VARCHAR(500) NOT NULL,
    src         VARCHAR(50)  NOT NULL,
    url         VARCHAR(500) NULL,
    date_ajout  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_reglementation_vues_key (doc_key),
    INDEX idx_reglementation_vues_date (date_ajout)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
