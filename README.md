# az-scout-plugin-bdd-sku

Plugin [az-scout](https://github.com/lrivallain/az-scout) qui met en cache les **prix retail des VM Azure** dans une base PostgreSQL locale. Permet des requêtes rapides et hors-ligne sur les prix, sans appeler l'API Azure à chaque fois.

## Architecture

```
┌────────────────────┐         ┌──────────────────┐         ┌──────────────┐
│     az-scout       │  GET    │   Plugin routes   │  async  │  PostgreSQL  │
│  (FastAPI :5001)   │ ──────▸ │  /plugins/bdd-sku │ ──────▸ │   (:5432)    │
│                    │         │    /status         │         │              │
│  MCP server        │         │                   │         │ retail_prices│
│  cache_status tool │         └───────────────────┘         │ job_runs     │
└────────────────────┘                                       │ job_logs     │
                                                             └──────┬───────┘
┌────────────────────┐                                              │
│  Ingestion CLI     │  INSERT (psycopg2)                           │
│  (one-shot Docker) │ ─────────────────────────────────────────────┘
│                    │  ◂── Azure Retail Prices API (public, no auth)
└────────────────────┘
```

**Deux composants indépendants :**

| Composant | Rôle | Technologie |
|---|---|---|
| **Plugin** (`src/az_scout_bdd_sku/`) | Tab UI + routes API + outil MCP, lecture seule depuis Postgres | FastAPI, psycopg (async), psycopg_pool |
| **Ingestion** (`ingestion/`) | Job CLI one-shot qui collecte les prix et les insère dans Postgres | requests, psycopg2-binary |

---

## Prérequis

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (gestionnaire de paquets)
- Docker & Docker Compose
- [az-scout](https://github.com/lrivallain/az-scout) installé (`uv pip install az-scout` ou en mode dev)

---

## Lancement local

### 1. Démarrer PostgreSQL

```bash
cd postgresql/
docker compose up -d
```

Cela démarre un conteneur PostgreSQL 17 avec :
- **Base** : `azscout`, **user** : `azscout`, **password** : `azscout`
- **Port** : `localhost:5432`
- Le schéma (`sql/schema.sql`) est appliqué automatiquement au premier démarrage

Vérifier que Postgres est prêt :

```bash
docker compose ps           # State: running (healthy)
docker compose logs postgres  # ... database system is ready to accept connections
```

### 2. Installer le plugin en mode développement

```bash
# Depuis la racine du repo
uv pip install -e ".[dev]"
```

Le plugin est découvert automatiquement par az-scout grâce à l'entry point `az_scout.plugins` dans `pyproject.toml`.

### 3. (Optionnel) Configurer la connexion PostgreSQL

Par défaut, le plugin se connecte à `localhost:5432/azscout` (user/pass: `azscout`). Pour personnaliser :

Créer `~/.config/az-scout/bdd-sku.toml` :

```toml
[database]
host = "localhost"
port = 5432
dbname = "azscout"
user = "azscout"
password = "azscout"
sslmode = "disable"
```

Ou pointer vers un fichier custom :

```bash
export AZ_SCOUT_BDD_SKU_CONFIG=/chemin/vers/mon/config.toml
```

### 4. Lancer az-scout

```bash
uv run az-scout web --host 0.0.0.0 --port 5001 --reload --no-open -v
```

Ouvrir http://localhost:5001 — l'onglet **SKU DB Cache** apparaît dans la barre de navigation.

### 5. Alimenter la base (ingestion)

L'ingestion est un **job Docker one-shot** séparé :

```bash
cd ingestion/

# Construire l'image
docker build -t bdd-sku-ingestion .

# Lancer l'ingestion
docker run --rm \
  --network postgresql_default \
  -e POSTGRES_HOST=postgres \
  -e ENABLE_AZURE_PRICING_COLLECTOR=true \
  bdd-sku-ingestion
```

> **Note :** `--network postgresql_default` permet au container d'atteindre le Postgres du `docker compose`. Le nom du réseau peut varier — vérifier avec `docker network ls`.

#### Variables d'environnement de l'ingestion

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_HOST` | `localhost` | Hôte PostgreSQL |
| `POSTGRES_PORT` | `5432` | Port PostgreSQL |
| `POSTGRES_DB` | `azscout` | Nom de la base |
| `POSTGRES_USER` | `azscout` | Utilisateur |
| `POSTGRES_PASSWORD` | `azscout` | Mot de passe |
| `POSTGRES_SSLMODE` | `disable` | Mode SSL (`disable`, `require`, `verify-full`) |
| `ENABLE_AZURE_PRICING_COLLECTOR` | `false` | **Doit être `true`** pour lancer la collecte |
| `AZURE_PRICING_MAX_ITEMS` | `-1` | Limite d'items (-1 = illimité) |
| `AZURE_PRICING_API_RETRY_ATTEMPTS` | `3` | Nombre de tentatives en cas d'erreur API |
| `AZURE_PRICING_API_RETRY_DELAY` | `2.0` | Délai entre retries (secondes) |
| `AZURE_PRICING_FILTERS` | `{}` | Filtres OData JSON (ex: `{"serviceName": "Virtual Machines"}`) |
| `LOG_LEVEL` | `INFO` | Niveau de log (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `JOB_TYPE` | `manual` | Type de job (metadata) |

#### Exemple avec filtres

```bash
docker run --rm \
  --network postgresql_default \
  -e POSTGRES_HOST=postgres \
  -e ENABLE_AZURE_PRICING_COLLECTOR=true \
  -e 'AZURE_PRICING_FILTERS={"serviceName": "Virtual Machines"}' \
  -e AZURE_PRICING_MAX_ITEMS=1000 \
  -e LOG_LEVEL=DEBUG \
  bdd-sku-ingestion
```

### 6. Vérifier le statut

- **UI** : Onglet SKU DB Cache → cliquer "Refresh Status"
- **API** : `curl http://localhost:5001/plugins/bdd-sku/status`
- **MCP** : L'outil `cache_status` est exposé automatiquement sur le serveur MCP

La réponse `/status` :

```json
{
  "db_connected": true,
  "retail_prices_count": 42000,
  "last_run": {
    "run_id": "a1b2c3...",
    "status": "ok",
    "started_at_utc": "2026-01-15T10:00:00+00:00",
    "finished_at_utc": "2026-01-15T10:05:00+00:00",
    "items_read": 45000,
    "items_written": 42000,
    "error_message": null
  }
}
```

---

## Déploiement sur Azure (Terraform)

L'infrastructure Azure est définie dans le dossier `infra/` et se déploie avec Terraform. Elle crée :

- **Azure Database for PostgreSQL – Flexible Server** (Burstable, PostgreSQL 17)
- **Azure Container Registry** (Basic) pour stocker l'image d'ingestion
- **Azure Container Apps Environment** avec Log Analytics
- **2 Container Apps Jobs** :
  - `pricing-scheduler` — cron quotidien (02:00 UTC)
  - `pricing-manual` — déclenchement manuel à la demande

### 1. Prérequis

- [Terraform](https://developer.hashicorp.com/terraform/install) ≥ 1.5
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) connecté (`az login`)
- Un abonnement Azure avec les droits suffisants

### 2. Configuration

```bash
cd infra/

# Copier le fichier d'exemple et remplir vos valeurs
cp terraform.tfvars.example terraform.tfvars
```

Éditer `terraform.tfvars` — au minimum renseigner :

| Variable | Description |
|---|---|
| `subscription_id` | ID de votre abonnement Azure |
| `postgres_admin_password` | Mot de passe fort pour le serveur PostgreSQL |

### 3. Déployer

```bash
terraform init
terraform plan        # Vérifier les ressources qui seront créées
terraform apply       # Confirmer avec 'yes'
```

### 4. Construire et pousser l'image d'ingestion

Après le déploiement, construire l'image dans l'ACR :

```bash
# Récupérer le nom du registre
ACR_NAME=$(terraform output -raw container_registry_login_server)

# Construire directement dans l'ACR
az acr build --registry ${ACR_NAME%%.*} --image bdd-sku-ingestion:latest ../ingestion/
```

### 5. Appliquer le schéma PostgreSQL

```bash
PG_FQDN=$(terraform output -raw postgresql_fqdn)

psql "host=$PG_FQDN port=5432 dbname=azscout user=azscout sslmode=require" \
  -f ../sql/schema.sql
```

### 6. Déclencher un job manuel (optionnel)

```bash
az containerapp job start \
  --resource-group $(terraform output -raw resource_group_name) \
  --name $(terraform output -raw pricing_manual_job_name)
```

### 7. Détruire l'infrastructure

```bash
terraform destroy     # Confirmer avec 'yes'
```

> **Note :** `terraform.tfvars` contient des secrets (mot de passe PostgreSQL). Ce fichier est ignoré par `.gitignore` et ne doit **jamais** être committé.

---

## Intégration du plugin dans az-scout

### Installation depuis PyPI (ou un registre privé)

```bash
uv pip install az-scout-bdd-sku
```

### Installation depuis Git

```bash
uv pip install "az-scout-bdd-sku @ git+https://github.com/rsabile/az-scout-plugin-bdd-sku.git"
```

### Installation en mode développement

```bash
git clone https://github.com/rsabile/az-scout-plugin-bdd-sku.git
cd az-scout-plugin-bdd-sku
uv pip install -e ".[dev]"
```

### Via le gestionnaire de plugins az-scout

Dans l'interface az-scout : **Settings → Plugins → Install** et renseigner l'URL Git du repo.

### Vérifier que le plugin est chargé

Au démarrage d'az-scout, les logs affichent :

```
INFO: Discovered plugin: bdd-sku v0.1.0
INFO: Mounted plugin routes at /plugins/bdd-sku/
INFO: Registered MCP tool: cache_status
INFO: Loaded plugin tab: SKU DB Cache
```

Le plugin ajoute :

| Élément | Description |
|---|---|
| **Onglet UI** `SKU DB Cache` | Affiche le nombre de prix en cache et le dernier run d'ingestion |
| **Route API** `GET /plugins/bdd-sku/status` | Statut de la base (connectivité, comptage, dernier run) |
| **Outil MCP** `cache_status` | Même info que la route, accessible via le serveur MCP |

---

## Structure du projet

```
az-scout-plugin-bdd-sku/
├── pyproject.toml                  # Package config, entry point, dépendances
├── README.md
├── LICENSE.txt
├── sql/
│   └── schema.sql                  # Schéma PostgreSQL (3 tables)
├── postgresql/
│   └── docker-compose.yml          # Postgres 17 pour le développement local
├── infra/
│   ├── main.tf                     # Provider + Resource Group + PostgreSQL Flexible Server
│   ├── container-apps.tf           # ACR + Container Apps Environment + Jobs (cron + manuel)
│   ├── variables.tf                # Variables Terraform
│   ├── outputs.tf                  # Outputs (FQDN, noms de ressources, etc.)
│   └── terraform.tfvars.example    # Exemple de fichier de variables
├── ingestion/
│   ├── Dockerfile                  # Image Docker pour le job CLI
│   ├── pyproject.toml              # Dépendances ingestion (psycopg2, requests)
│   └── app/
│       ├── main.py                 # Point d'entrée CLI
│       ├── core/
│       │   ├── base_collector.py   # Classe abstraite BaseCollector
│       │   └── orchestrator.py     # Orchestrateur de jobs
│       ├── collectors/
│       │   └── azure_pricing_collector.py  # Collecteur Azure Retail Prices API
│       └── shared/
│           ├── config.py           # Gestion des variables d'environnement
│           └── pg_client.py        # Client PostgreSQL (sync)
├── src/
│   └── az_scout_bdd_sku/
│       ├── __init__.py             # Classe plugin + entry point
│       ├── plugin_config.py        # Configuration TOML du plugin
│       ├── db.py                   # Pool de connexions async (psycopg)
│       ├── routes.py               # Routes FastAPI (GET /status)
│       ├── tools.py                # Outil MCP cache_status
│       └── static/
│           ├── css/bdd-sku.css
│           ├── html/bdd-sku-tab.html
│           └── js/bdd-sku-tab.js
└── tests/
    └── test_bdd_sku.py             # Tests pytest (routes + outil MCP)
```

## Base de données

3 tables PostgreSQL :

| Table | Description |
|---|---|
| `job_runs` | Suivi des exécutions d'ingestion (status, durée, items lus/écrits) |
| `job_logs` | Logs détaillés par run |
| `retail_prices_vm` | Prix retail des VM Azure (25 colonnes, UPSERT via contrainte UNIQUE) |

---

## Quality checks

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest
```

## License

[MIT](LICENSE.txt)

## Disclaimer

> **This tool is not affiliated with Microsoft.** All capacity, pricing, and latency information are indicative and not a guarantee of deployment success. Pricing values are dynamic and may change between ingestion and actual deployment.
