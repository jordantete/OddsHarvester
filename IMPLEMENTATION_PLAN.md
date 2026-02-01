# Plan d'implémentation — Modernisation du CLI & Structure

Plan incrémental pour intégrer les idées intéressantes de la PR #33 (par @S1M0N38) tout en évitant les breaking changes inutiles.

---

## Phase 1 : Restructuration en package Python

**Objectif** : Transformer `src/` en package installable sans casser l'existant.

**Changements** :
- Renommer `src/` → `src/oddsharvester/`
- Ajouter `src/oddsharvester/__init__.py` et `__main__.py`
- Mettre à jour tous les imports internes (`from src.utils...` → `from oddsharvester.utils...`)
- Mettre à jour `pyproject.toml` :
  - Ajouter `[project.scripts]` pour le point d'entrée CLI
  - Mettre à jour `[tool.setuptools.packages.find]`
  - Mettre à jour `[tool.pytest.ini_options] pythonpath`
- Mettre à jour les imports dans tous les fichiers de tests
- Mettre à jour le Dockerfile et `serverless.yaml`
- Mettre à jour les GitHub Actions workflows

**Choix du nom CLI** : `oddsharvester` (explicite, sans risque de conflit)

---

## Phase 2 : Migration CLI argparse → Click

**Objectif** : Remplacer le layer CLI custom par Click pour plus de composabilité et maintenabilité.

**Changements** :
- Ajouter `click` aux dépendances dans `pyproject.toml`
- Créer la nouvelle structure CLI :
  - `oddsharvester/cli/cli.py` — Groupe de commandes principal
  - `oddsharvester/cli/commands/upcoming.py` — Commande `upcoming`
  - `oddsharvester/cli/commands/historic.py` — Commande `historic`
  - `oddsharvester/cli/options.py` — Options partagées (décorateurs réutilisables)
  - `oddsharvester/cli/validators.py` — Callbacks de validation Click
  - `oddsharvester/cli/types.py` — Types custom Click (Sport, Market, etc.)
- Conserver le format de date `YYYYMMDD` côté utilisateur (cohérent avec les URLs oddsportal)
- Options globales : `--verbose`, `--quiet`, `--version`
- Aliases courts : `-s` (sport), `-l` (league), `-m` (market), `-o` (output), `-f` (format), `-c` (concurrency)
- Supprimer l'ancien CLI layer (`cli_argument_parser.py`, `cli_argument_handler.py`, `cli_argument_validator.py`, `cli_help_message_generator.py`)
- Mettre à jour les tests CLI

---

## Phase 3 : Support des variables d'environnement

**Objectif** : Permettre la configuration via env vars pour les déploiements Docker/Lambda.

**Changements** (intégré naturellement avec Click via le paramètre `envvar`) :

| Variable d'environnement | Option CLI |
|--------------------------|------------|
| `OH_SPORT` | `--sport` |
| `OH_LEAGUES` | `--league` |
| `OH_MARKETS` | `--market` |
| `OH_STORAGE` | `--storage` |
| `OH_FORMAT` | `--format` |
| `OH_FILE_PATH` | `--file-path` |
| `OH_HEADLESS` | `--headless` |
| `OH_CONCURRENCY` | `--concurrency` |
| `OH_PROXY_URL` | `--proxy-url` |
| `OH_PROXY_USER` | `--proxy-user` |
| `OH_PROXY_PASS` | `--proxy-pass` |
| `OH_USER_AGENT` | `--user-agent` |
| `OH_LOCALE` | `--locale` |
| `OH_TIMEZONE` | `--timezone` |

- Mettre à jour `lambda_handler.py` pour utiliser ces env vars
- Documenter les env vars dans le README

---

## Phase 4 : Refactoring des options proxy

**Objectif** : Simplifier la syntaxe proxy.

**Changements** :
- Remplacer `--proxies "http://proxy:8080 user pass"` par trois options distinctes :
  - `--proxy-url` (URL du proxy)
  - `--proxy-user` (username, optionnel)
  - `--proxy-pass` (password, optionnel)
- Mettre à jour `proxy_manager.py` pour accepter le nouveau format
- Support de proxy unique (supprimer la rotation multi-proxy ou la gérer autrement si nécessaire)
- Mettre à jour les tests proxy

---

## Ordre d'exécution

```
Phase 1 (package structure) ─── prérequis pour tout le reste
    │
    ├── Phase 2 (Click CLI) ─── inclut naturellement Phase 3 (env vars)
    │
    └── Phase 4 (proxy options) ─── peut être fait dans Phase 2
```

En pratique, les phases 2, 3 et 4 peuvent être implémentées ensemble dans une seule PR puisque Click rend les env vars et les options proxy triviales à déclarer.

---

## Ce qu'on ne reprend PAS de la PR #33

| Élément | Raison |
|---------|--------|
| Changement format date → `YYYY-MM-DD` | Casse les URLs oddsportal (format `YYYYMMDD`) |
| Nom CLI `oh` | Trop générique, risque de conflit |
| Suppression section Cloud Deployment | Documentation utile à conserver |
