# Déploiement Docker — Scénario 1 (VPS)

> Après ce déploiement, tout collaborateur accède à la plateforme via navigateur
> (ex : `http://votre-vps-ip`) sans rien installer.

## Pré-requis sur le VPS

| Logiciel | Version minimale | Commande de vérification |
|----------|-----------------|--------------------------|
| Docker   | 24+             | `docker --version`       |
| Docker Compose | v2+     | `docker compose version` |

Système recommandé : Ubuntu 22.04 LTS, 2 vCPU, 4 Go RAM, 40 Go disque.

---

## 1. Transférer le projet sur le VPS

```bash
# Depuis votre machine locale
scp -r "FS Market Intelligence/" user@VPS_IP:/opt/fsmarket/
```

ou cloner depuis GitHub :

```bash
git clone -b ThirdVersion https://github.com/Azza0411/SCRAPING.git /opt/fsmarket
```

---

## 2. Configurer les variables d'environnement

```bash
cd /opt/fsmarket
cp .env.example .env
nano .env          # remplir DB_PASSWORD, SECRET_KEY, GROQ_API_KEY
```

---

## 3. Lancer la plateforme

```bash
docker compose up -d --build
```

La première fois, Docker :
1. Télécharge Python 3.12, Node 20, MySQL 8, nginx
2. Installe Tesseract + Ghostscript + toutes les dépendances Python
3. Compile le frontend React

Durée estimée : 5–10 minutes selon la bande passante.

---

## 4. Vérifier que tout fonctionne

```bash
docker compose ps          # tous les services doivent être "Up"
docker compose logs backend --tail=30
```

Ouvrir dans le navigateur : `http://VPS_IP`

---

## 5. Commandes utiles

| Action | Commande |
|--------|----------|
| Arrêter | `docker compose down` |
| Redémarrer | `docker compose restart` |
| Voir les logs en direct | `docker compose logs -f` |
| Mettre à jour le code | `git pull && docker compose up -d --build` |

---

## Ports exposés

| Port | Service |
|------|---------|
| 80   | Frontend (React via nginx) + proxy `/api/` |
| 5000 | Backend Flask (accès direct optionnel) |

---

## Accès collaborateurs

Partager simplement l'URL : `http://VPS_IP`  
Aucune installation requise côté client.
