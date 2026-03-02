# Ingestion CLI

Job CLI one-shot qui collecte les **prix retail des VM Azure** depuis l'[Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) (publique, sans authentification) et les insère dans PostgreSQL.

## Architecture

```
Azure Retail Prices API         Ingestion CLI              PostgreSQL (:5432)
  (public, no auth)              (one-shot)
┌───────────────────┐  GET     ┌──────────────────┐ INSERT ┌────────────────┐
│ prices.azure.com  │ ◂─────  │  python main.py  │ ─────▸ │ retail_prices  │
│ /api/retail/      │  OData   │                  │        │ job_runs       │
│   prices          │  $filter │ AzurePricingColl │        │ job_logs       │
└───────────────────┘          └──────────────────┘        └────────────────┘
```

## Prérequis

- **Docker** et **Docker Compose** installés ([installer Docker](https://docs.docker.com/get-docker/))
- Aucun compte Azure nécessaire — l'API de prix est publique et gratuite
- ~500 Mo d'espace disque pour l'image Docker et les données PostgreSQL

Vérifier que Docker fonctionne :

```bash
docker --version          # Docker version 24+ attendu
docker compose version    # Docker Compose version v2+ attendu
```

## Guide pas-à-pas

### Étape 1 — Démarrer PostgreSQL

PostgreSQL reçoit les données collectées. Un fichier `docker-compose.yml` est fourni dans le dossier `postgresql/` pour le lancer en un clic.

```bash
# Depuis la racine du projet az-scout-plugin-bdd-sku
cd postgresql/
docker compose up -d
```

Cela crée automatiquement :
- Un conteneur PostgreSQL 17 sur le port **5432**
- Une base de données `azscout` (user: `azscout`, password: `azscout`)
- Les 3 tables nécessaires (`retail_prices_vm`, `job_runs`, `job_logs`) via `sql/schema.sql`
- Un réseau Docker nommé `postgresql_default` (utilisé ensuite par l'ingestion)

**Vérifier que PostgreSQL est prêt :**

```bash
docker compose ps
```

Vous devez voir :

```
NAME       IMAGE         STATUS
postgres   postgres:17   Up X seconds (healthy)
```

> **Dépannage :** Si le statut est `(health: starting)`, attendre quelques secondes et relancer `docker compose ps`. Si le port 5432 est déjà utilisé, arrêter l'autre service ou modifier le port dans `docker-compose.yml`.

### Étape 2 — Construire l'image d'ingestion

```bash
# Revenir à la racine du projet puis aller dans ingestion/
cd ../ingestion/
docker build -t bdd-sku-ingestion .
```

Le build installe Python 3.12, les dépendances (`requests`, `psycopg2`) et copie le code. Cela prend environ 30 secondes la première fois.

### Étape 3 — Lancer l'ingestion

```bash
docker run --rm \
  --network postgresql_default \
  -e POSTGRES_HOST=postgres \
  -e ENABLE_AZURE_PRICING_COLLECTOR=true \
  bdd-sku-ingestion
```

**Explication des paramètres :**

| Paramètre | Rôle |
|---|---|
| `--rm` | Supprime le conteneur après exécution (c'est un job one-shot) |
| `--network postgresql_default` | Connecte le conteneur au même réseau que PostgreSQL |
| `-e POSTGRES_HOST=postgres` | Indique l'adresse de PostgreSQL (`postgres` est le nom du service dans docker-compose) |
| `-e ENABLE_AZURE_PRICING_COLLECTOR=true` | Active la collecte (désactivée par défaut par sécurité) |

Le job démarre, affiche les logs de progression (pages collectées, items insérés), puis se termine automatiquement.

> **Note :** Sans filtre, l'ingestion collecte **tous** les prix Azure (plusieurs centaines de milliers d'items). Utiliser `AZURE_PRICING_MAX_ITEMS` pour limiter lors des tests — voir la section [Exemples](#exemples) ci-dessous.

### Étape 4 — Vérifier les données

```bash
# Se connecter à PostgreSQL
docker exec -it postgresql-postgres-1 psql -U azscout -d azscout

# Compter les prix collectés
SELECT COUNT(*) FROM retail_prices_vm;

# Voir le dernier run d'ingestion
SELECT run_id, status, items_written, started_at_utc FROM job_runs ORDER BY started_at_utc DESC LIMIT 1;

# Quitter psql
\q
```

### Étape 5 — Arrêter l'environnement

Quand vous avez fini :

```bash
cd ../postgresql/
docker compose down        # Arrête PostgreSQL (les données sont conservées dans le volume)
docker compose down -v     # Arrête ET supprime les données PostgreSQL
```

## Alternative : sans Docker

Si vous ne souhaitez pas utiliser Docker pour l'ingestion (PostgreSQL reste nécessaire) :

```bash
cd ingestion/
pip install -e .

POSTGRES_HOST=localhost \
POSTGRES_PORT=5432 \
POSTGRES_DB=azscout \
POSTGRES_USER=azscout \
POSTGRES_PASSWORD=azscout \
ENABLE_AZURE_PRICING_COLLECTOR=true \
  python app/main.py
```

> Ici `POSTGRES_HOST=localhost` car le script tourne directement sur la machine hôte, pas dans un conteneur Docker.

## Exemples

### Test rapide (1000 items seulement)

```bash
docker run --rm \
  --network postgresql_default \
  -e POSTGRES_HOST=postgres \
  -e ENABLE_AZURE_PRICING_COLLECTOR=true \
  -e AZURE_PRICING_MAX_ITEMS=1000 \
  bdd-sku-ingestion
```

### Collecter uniquement les VM

```bash
docker run --rm \
  --network postgresql_default \
  -e POSTGRES_HOST=postgres \
  -e ENABLE_AZURE_PRICING_COLLECTOR=true \
  -e 'AZURE_PRICING_FILTERS={"serviceName": "Virtual Machines"}' \
  bdd-sku-ingestion
```

### Mode verbose (debug)

```bash
docker run --rm \
  --network postgresql_default \
  -e POSTGRES_HOST=postgres \
  -e ENABLE_AZURE_PRICING_COLLECTOR=true \
  -e AZURE_PRICING_MAX_ITEMS=100 \
  -e LOG_LEVEL=DEBUG \
  bdd-sku-ingestion
```

## Variables d'environnement

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_HOST` | `localhost` | Adresse du serveur PostgreSQL. Utiliser `postgres` si le conteneur est dans le réseau Docker, `localhost` si le script tourne en local |
| `POSTGRES_PORT` | `5432` | Port PostgreSQL |
| `POSTGRES_DB` | `azscout` | Nom de la base de données |
| `POSTGRES_USER` | `azscout` | Utilisateur PostgreSQL |
| `POSTGRES_PASSWORD` | `azscout` | Mot de passe PostgreSQL |
| `POSTGRES_SSLMODE` | `disable` | Mode SSL (`disable` en local, `require` sur Azure) |
| `ENABLE_AZURE_PRICING_COLLECTOR` | `false` | **Doit être `true`** pour lancer la collecte. Sécurité pour éviter les exécutions accidentelles |
| `AZURE_PRICING_MAX_ITEMS` | `-1` | Nombre max d'items à collecter. `-1` = illimité. Utiliser `1000` pour tester |
| `AZURE_PRICING_FILTERS` | `{}` | Filtres OData en JSON. Exemple : `{"serviceName": "Virtual Machines"}` |
| `AZURE_PRICING_API_RETRY_ATTEMPTS` | `3` | Nombre de tentatives en cas d'erreur API (429, 5xx) |
| `AZURE_PRICING_API_RETRY_DELAY` | `2.0` | Délai en secondes entre les retries |
| `LOG_LEVEL` | `INFO` | Niveau de log : `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `JOB_TYPE` | `manual` | Metadata du job (descriptif libre) |

## Dépannage

| Problème | Cause | Solution |
|---|---|---|
| `network postgresql_default not found` | PostgreSQL n'est pas démarré | Lancer `cd postgresql/ && docker compose up -d` d'abord |
| `connection refused` sur port 5432 | PostgreSQL pas encore prêt | Attendre quelques secondes, vérifier `docker compose ps` |
| `POSTGRES_HOST=postgres` ne fonctionne pas | Le script tourne en dehors de Docker | Utiliser `POSTGRES_HOST=localhost` à la place |
| `ENABLE_AZURE_PRICING_COLLECTOR` oublié | La collecte n'est pas activée | Ajouter `-e ENABLE_AZURE_PRICING_COLLECTOR=true` |
| Ingestion très lente | Collecte de tout le catalogue sans filtre | Ajouter `-e AZURE_PRICING_MAX_ITEMS=1000` pour tester |
