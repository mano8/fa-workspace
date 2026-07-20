# Espace de travail M8 FastAPI

Configuration partagée de l'écosystème de microservices M8 FastAPI. Ce dépôt est le plan de contrôle de l'espace de travail : il fournit l'architecture, les politiques, les profils d'environnement, les outils de développement et le Dev Container partagés ; il n'exécute pas les services applicatifs.

[English](README.md) | [Español](README.es.md) | [Français](README.fr.md)

## Table des matières

- [Objectif et source de vérité](#objectif-et-source-de-verite)
- [Structure de l'espace de travail](#structure-de-lespace-de-travail)
- [Guide de configuration](#guide-de-configuration)
  - [Configuration partagée](#configuration-partagee)
  - [Configuration propre aux outils](#configuration-propre-aux-outils)
  - [Profils d'environnement](#profils-denvironnement)
  - [Hooks de sécurité Git](#hooks-de-securite-git)
  - [Dev Container et Headroom](#dev-container-et-headroom)
- [Configuration initiale](#configuration-initiale)
- [Utilisation quotidienne](#utilisation-quotidienne)
- [Dépannage](#depannage)

<a id="objectif-et-source-de-verite"></a>

## Objectif et source de vérité

La présentation complète de l'espace de travail partagé, de son modèle de propriété et de ses répertoires est disponible dans [`.workspace/README.md`](.workspace/README.md). Consultez-le avant toute modification de configuration au niveau de l'espace de travail.

`.workspace/` est la source de vérité indépendante des outils. Il contient l'architecture commune, la classification des dépôts, les politiques, les contrats, les plans, les analyses et les états. Ce README sert de guide d'accueil et de navigation : il renvoie vers la source canonique au lieu de dupliquer ses politiques.

<a id="structure-de-lespace-de-travail"></a>

## Structure de l'espace de travail

```text
fa-workspace/                # Ce dépôt : racine et plan de contrôle de l'espace de travail
├── .workspace/              # Contexte partagé canonique
├── .agents/ .claude/ .codex/ .devcontainer/ .githooks/ scripts/
├── auth-sdk-m8/ fastapi-m8/ imgtools_m8/ media-sdk-m8/ security-tests-m8/
├── fa-auth-m8/ media-service-m8/ media-worker-m8/ prompt-engine-m8/
├── reparto-docente-m8/
├── astro-auth-m8/ astro-media-m8/ astro-prompt-m8/ astro-reparto-m8/
└── astro-ui-m8/ fa-ui-m8/
```

Les répertoires ci-dessus sont des enfants directs de `fa-workspace` ; ils ne sont pas des dépôts voisins. Le Dev Container monte la racine de ce dépôt dans `/workspace`. Sa configuration initiale lit les exigences de développement des enfants directs `fa-auth-m8`, `imgtools_m8` et `media-service-m8`.

| Chemin | Rôle |
| --- | --- |
| [`.workspace/`](.workspace/README.md) | Architecture, politiques, contrats, plans, analyses et états partagés canoniques. |
| [`AGENTS.md`](AGENTS.md) | Point d'entrée et règles Codex. |
| [`CLAUDE.md`](CLAUDE.md) | Point d'entrée et règles Claude Code. |
| [`.codex/`](.codex/README.md) | Configuration propre à Codex uniquement. |
| [`.claude/`](.claude/README.md) | Configuration propre à Claude Code uniquement. |
| [`.agents/`](.agents/) | Compétences d'agents partageables. |
| [`.devcontainer/`](.devcontainer/devcontainer.json) | Environnement reproductible fondé sur Docker Compose. |
| [`scripts/`](scripts/) | Chargeurs multiplateformes des profils d'environnement. |
| [`.githooks/`](.githooks/) | Hooks locaux de sécurité facultatifs. |

<a id="guide-de-configuration"></a>

## Guide de configuration

<a id="configuration-partagee"></a>

### Configuration partagée

Utilisez [`.workspace/README.md`](.workspace/README.md) comme point d'entrée. Les fichiers importants sont [`architecture.md`](.workspace/architecture.md), [`repo-types.json`](.workspace/repo-types.json), [`policy.index.json`](.workspace/policy.index.json), [`context/`](.workspace/context/) et [`contracts/`](.workspace/contracts/).

Avant de travailler dans un dépôt, lisez aussi son propre `AGENTS.md`. La résolution sélectionne `always`, les facettes du dépôt dans l'ordre, puis les tâches explicitement demandées. Le format actif est v2 facetté ; l'ancien analyseur et les sélecteurs transitoires ne subsistent que comme preuve historique de rollback. La politique d'environnement est prioritaire sur la politique de langage, l'architecture et les contrats de validation. Les plans, analyses et états appartiennent à `.workspace/` ; ne les dupliquez pas dans `.codex/` ou `.claude/`.

Le guide opérationnel complet se trouve dans [`.workspace/README.md`](.workspace/README.md) : propriété sémantique, périmètre et autorisation des dépôts/tâches, preuves de capacité, livraison native ou injectée, modes standalone, runtime et reçus sécurisés, formule exacte des octets, overrides, budgets, et distinction entre contexte d'instructions, effort de raisonnement, compression de sortie et prix. La livraison canonique actuelle est vérifiée uniquement pour Codex non interactif dans le Dev Container ; les modes interactifs Codex/Claude sont `LIMITED` et Windows/POSIX hôte est `UNSUPPORTED`.

<a id="configuration-propre-aux-outils"></a>

### Configuration propre aux outils

Codex utilise [`AGENTS.md`](AGENTS.md) et [`.codex/README.md`](.codex/README.md) ; Claude Code utilise [`CLAUDE.md`](CLAUDE.md) et [`.claude/README.md`](.claude/README.md). Ces emplacements peuvent contenir des flux de travail et un état local propres à chaque outil, mais ne doivent pas redéfinir les informations partagées.

Le chargement natif et la livraison injectée dépendent de preuves propres au client, à la plateforme et au mode. Le chargement natif exige des hashes correspondants ; l'injection exige que la découverte native soit désactivée et qu'un reçu prouve une livraison exacte unique. Les reçus prouvent la remise par le launcher, pas le comportement du modèle. Le runtime isolé reste sous `.workspace/.runtime/` et les journaux normaux ne contiennent pas de politiques brutes.

Le Dev Container installe Codex CLI et la fonctionnalité Claude Code. Connectez-vous dans le conteneur lorsque vous voulez utiliser ces outils. Leur configuration est conservée dans des volumes Docker et n'est pas copiée depuis les répertoires de votre machine hôte.

<a id="profils-denvironnement"></a>

### Profils d'environnement

Les chemins et commandes propres à chaque machine restent locaux. Partez des modèles sûrs et ne validez jamais les fichiers générés :

```bash
cp .env.local.example .env.local
cp .env.devcontainer.example .env.devcontainer
source scripts/import-workspace-env.sh devcontainer
source scripts/import-workspace-env.sh devcontainer --validate-only
```

Utilisez `local` sur un hôte Linux ou macOS. Sous Windows PowerShell, autorisez le chargeur uniquement pour le processus courant puis chargez-le avec dot-sourcing :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\scripts\Import-WorkspaceEnv.ps1 -Profile local
. .\scripts\Import-WorkspaceEnv.ps1 -Profile local -ValidateOnly
```

Les profils décrivent les outils et chemins disponibles ; les lockfiles et métadonnées de chaque dépôt choisissent toujours son gestionnaire de paquets. Conservez les identifiants de service dans le dépôt de service correspondant, jamais dans les profils racine.

<a id="hooks-de-securite-git"></a>

### Hooks de sécurité Git

Les hooks fournis refusent les commits et pushs contenant des fichiers sous un répertoire `todo/`. Activez-les une fois par clone :

```bash
git config core.hooksPath .githooks
```

Ils constituent une protection locale et ne remplacent pas la revue. Vérifiez `git status` avant un commit et ne poussez jamais directement vers `main`.

<a id="dev-container-et-headroom"></a>

### Dev Container et Headroom

La configuration active est [`.devcontainer/devcontainer.json`](.devcontainer/devcontainer.json) avec [`.devcontainer/docker-compose.devcontainer.yml`](.devcontainer/docker-compose.devcontainer.yml). Elle fournit Ubuntu, Node.js 24, Python 3.12, l'accès à Docker, les extensions recommandées, un environnement Python partagé, Codex CLI et Claude Code.

[Headroom](https://github.com/headroomlabs-ai/headroom) est une aide MCP open source qui compresse les sorties volumineuses non sensibles avant leur envoi à un modèle d'IA. Compose exécute `headroom-proxy` sur le réseau Docker privé, à l'adresse `http://headroom-proxy:8787`, sans exposer de port sur l'hôte. Au démarrage du conteneur, il est enregistré pour Codex et, lorsqu'il est disponible, Claude Code.

Utilisez-le pour les journaux, résultats de tests, JSON, traces et extraits longs. N'envoyez pas de fichiers `.env`, d'identifiants, de jetons, de clés privées, de fichiers OAuth, de clés SSH ou de matériel de signature de production. Le proxy désactive la télémétrie et le suivi d'abonnement.

> Les fichiers `.devcontainer/.headroom/` sont des références. La configuration active utilise le proxy/stdio décrit ici.

<a id="configuration-initiale"></a>

## Configuration initiale

1. Installez et démarrez [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Installez [Visual Studio Code](https://code.visualstudio.com/) et l'extension **Dev Containers**.
3. Conservez `fa-auth-m8`, `imgtools_m8` et `media-service-m8` comme enfants directs de cette racine d'espace de travail. La configuration initiale installe leurs exigences de développement.
4. Ouvrez `fa-workspace` dans VS Code.
5. Dans la palette de commandes (`F1` ou `Ctrl+Shift+P`), choisissez **Dev Containers: Reopen in Container**.
6. Attendez la première construction, puis vérifiez dans un nouveau terminal :

   ```bash
   python3 --version
   node --version
   docker --version
   headroom --help
   ```

`setup.sh` s'exécute lors de la création du conteneur et `configure-mcp.sh` à chaque démarrage. Après une modification d'un fichier Dev Container ou Compose, utilisez **Dev Containers: Rebuild and Reopen in Container**.

<a id="utilisation-quotidienne"></a>

### Utilisation quotidienne

- Consultez `.workspace/` avant toute décision partagée d'architecture ou de politique.
- Lisez le `AGENTS.md` de chaque dépôt avant de le modifier.
- Chargez le profil local ou Dev Container approprié au lieu d'utiliser des chemins propres à une machine.
- Utilisez `headroom_compress` uniquement avec de grandes sorties non secrètes et récupérez l'original seulement si nécessaire.
- Conservez les plans, analyses et états dans `.workspace/` et les secrets hors de Git.

Pour contrôler Headroom ou réparer son enregistrement MCP depuis le conteneur :

```bash
docker compose -f .devcontainer/docker-compose.devcontainer.yml ps
docker logs --tail 200 headroom-proxy-server
bash .devcontainer/configure-mcp.sh
```

<a id="depannage"></a>

## Dépannage

| Problème | Action |
| --- | --- |
| Docker est indisponible | Démarrez Docker Desktop puis reconstruisez le Dev Container. |
| L'installation initiale des exigences Python échoue | Vérifiez les trois dépôts voisins, puis reconstruisez. |
| Headroom est indisponible | Consultez l'état et les journaux Compose, puis redémarrez ou reconstruisez le conteneur. |
| Les outils MCP Headroom sont absents | Exécutez `bash .devcontainer/configure-mcp.sh`, puis rouvrez le conteneur. |
| Une extension VS Code est absente | Reconstruisez le Dev Container pour réappliquer les extensions. |
| Une politique est ambiguë | Commencez par [`.workspace/README.md`](.workspace/README.md), puis lisez le contexte sélectionné par `repo-types.json` et `policy.index.json`. |
