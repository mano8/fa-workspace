# Espacio de trabajo M8 FastAPI

Configuración compartida para el ecosistema de microservicios M8 FastAPI. Este repositorio es el plano de control del espacio de trabajo: ofrece arquitectura, políticas, perfiles de entorno, herramientas de desarrollo y Dev Container compartidos; no ejecuta los servicios de la aplicación.

[English](README.md) | [Español](README.es.md) | [Français](README.fr.md)

## Índice

- [Propósito y fuente de verdad](#proposito-y-fuente-de-verdad)
- [Estructura del espacio de trabajo](#estructura-del-espacio-de-trabajo)
- [Guía de configuración](#guia-de-configuracion)
  - [Configuración compartida](#configuracion-compartida)
  - [Configuración específica de herramientas](#configuracion-especifica-de-herramientas)
  - [Perfiles de entorno](#perfiles-de-entorno)
  - [Hooks de seguridad Git](#hooks-de-seguridad-git)
  - [Dev Container y Headroom](#dev-container-y-headroom)
- [Configuración inicial](#configuracion-inicial)
- [Uso diario](#uso-diario)
- [Solución de problemas](#solucion-de-problemas)

<a id="proposito-y-fuente-de-verdad"></a>

## Propósito y fuente de verdad

La presentación completa del espacio de trabajo compartido, su modelo de propiedad y sus directorios está en [`.workspace/README.md`](.workspace/README.md). Léelo antes de modificar una configuración de nivel de espacio de trabajo.

`.workspace/` es la fuente de verdad neutral respecto a herramientas. Contiene arquitectura compartida, clasificación de repositorios, políticas, contratos, planes, análisis y estado. Este README sirve para orientación e incorporación: enlaza la fuente canónica en vez de duplicar sus políticas.

<a id="estructura-del-espacio-de-trabajo"></a>

## Estructura del espacio de trabajo

```text
fa-workspace/                # Este repositorio: raíz y plano de control del espacio de trabajo
├── .workspace/              # Contexto compartido canónico
├── .agents/ .claude/ .codex/ .devcontainer/ .githooks/ scripts/
├── auth-sdk-m8/ fastapi-m8/ imgtools_m8/ media-sdk-m8/ security-tests-m8/
├── fa-auth-m8/ media-service-m8/ media-worker-m8/ prompt-engine-m8/
├── reparto-docente-m8/
├── astro-auth-m8/ astro-media-m8/ astro-prompt-m8/ astro-reparto-m8/
└── astro-ui-m8/ fa-ui-m8/
```

Los directorios anteriores son hijos directos de `fa-workspace`; no son repositorios hermanos. El Dev Container monta la raíz de este repositorio como `/workspace`. La configuración inicial lee requisitos de desarrollo de los hijos directos `fa-auth-m8`, `imgtools_m8` y `media-service-m8`.

| Ruta | Función |
| --- | --- |
| [`.workspace/`](.workspace/README.md) | Arquitectura, políticas, contratos, planes, análisis y estado compartidos canónicos. |
| [`AGENTS.md`](AGENTS.md) | Punto de entrada y reglas de Codex. |
| [`CLAUDE.md`](CLAUDE.md) | Punto de entrada y reglas de Claude Code. |
| [`.codex/`](.codex/README.md) | Solo configuración específica de Codex. |
| [`.claude/`](.claude/README.md) | Solo configuración específica de Claude Code. |
| [`.agents/`](.agents/) | Habilidades compartibles para agentes. |
| [`.devcontainer/`](.devcontainer/devcontainer.json) | Entorno reproducible basado en Docker Compose. |
| [`scripts/`](scripts/) | Cargadores multiplataforma de perfiles de entorno. |
| [`.githooks/`](.githooks/) | Hooks locales opcionales de seguridad. |

<a id="guia-de-configuracion"></a>

## Guía de configuración

<a id="configuracion-compartida"></a>

### Configuración compartida

Usa [`.workspace/README.md`](.workspace/README.md) como punto de entrada. Los archivos principales son [`architecture.md`](.workspace/architecture.md), [`repo-types.json`](.workspace/repo-types.json), [`policy.index.json`](.workspace/policy.index.json), [`context/`](.workspace/context/) y [`contracts/`](.workspace/contracts/).

Antes de trabajar en un repositorio, lee también su propio `AGENTS.md`. Mientras esté activo el modo transitorio, resuelve su selector `migration.v1_bundle` con `repo-types.json` y carga solamente el paquete de compatibilidad ordenado correspondiente. La política de entorno tiene prioridad sobre la política de lenguaje, la arquitectura y los contratos de validación. Los planes, análisis y estados pertenecen a `.workspace/`; no los dupliques en `.codex/` ni `.claude/`.

<a id="configuracion-especifica-de-herramientas"></a>

### Configuración específica de herramientas

Codex usa [`AGENTS.md`](AGENTS.md) y [`.codex/README.md`](.codex/README.md); Claude Code usa [`CLAUDE.md`](CLAUDE.md) y [`.claude/README.md`](.claude/README.md). Esas ubicaciones pueden contener flujos de trabajo y estado local propios de cada herramienta, pero no deben redefinir información compartida.

El Dev Container instala Codex CLI y la característica de Claude Code. Inicia sesión dentro del contenedor cuando quieras usar cada herramienta. Sus configuraciones se guardan en volúmenes Docker y no se copian de las carpetas de tu equipo anfitrión.

<a id="perfiles-de-entorno"></a>

### Perfiles de entorno

Las rutas y comandos propios de cada equipo son locales. Parte de las plantillas seguras y no confirmes los archivos resultantes:

```bash
cp .env.local.example .env.local
cp .env.devcontainer.example .env.devcontainer
source scripts/import-workspace-env.sh devcontainer
source scripts/import-workspace-env.sh devcontainer --validate-only
```

Usa `local` en un equipo Linux o macOS. En Windows PowerShell, permite el cargador solo para el proceso actual y cárgalo con punto:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\scripts\Import-WorkspaceEnv.ps1 -Profile local
. .\scripts\Import-WorkspaceEnv.ps1 -Profile local -ValidateOnly
```

Los perfiles indican las herramientas y rutas disponibles; los lockfiles y metadatos de cada repositorio siguen decidiendo su gestor de paquetes. Mantén las credenciales de servicio en su repositorio de servicio correspondiente, nunca en perfiles raíz.

<a id="hooks-de-seguridad-git"></a>

### Hooks de seguridad Git

Los hooks incluidos rechazan commits y pushes que contienen archivos bajo un directorio `todo/`. Actívalos una vez por clon:

```bash
git config core.hooksPath .githooks
```

Son una protección local, no sustituyen la revisión. Consulta `git status` antes de confirmar y no hagas push directo a `main`.

<a id="dev-container-y-headroom"></a>

### Dev Container y Headroom

La configuración activa está en [`.devcontainer/devcontainer.json`](.devcontainer/devcontainer.json) y [`.devcontainer/docker-compose.devcontainer.yml`](.devcontainer/docker-compose.devcontainer.yml). Proporciona Ubuntu, Node.js 24, Python 3.12, acceso a Docker, extensiones recomendadas, un entorno Python compartido, Codex CLI y Claude Code.

[Headroom](https://github.com/headroomlabs-ai/headroom) es una ayuda MCP de código abierto que comprime salidas grandes y no sensibles antes de que lleguen a un modelo de IA. Compose ejecuta `headroom-proxy` en la red privada de Docker, en `http://headroom-proxy:8787`, sin exponer un puerto del equipo anfitrión. Al iniciar el contenedor, queda registrado para Codex y, cuando está disponible, Claude Code.

Úsalo para logs, resultados de pruebas, JSON, trazas y extractos largos. No envíes archivos `.env`, credenciales, tokens, claves privadas, archivos OAuth, claves SSH ni material de firma de producción. El proxy desactiva telemetría y seguimiento de suscripciones.

> Los archivos de `.devcontainer/.headroom/` son material de referencia. La configuración activa usa el proxy/stdio descrito aquí.

<a id="configuracion-inicial"></a>

## Configuración inicial

1. Instala e inicia [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Instala [Visual Studio Code](https://code.visualstudio.com/) y la extensión **Dev Containers**.
3. Mantén `fa-auth-m8`, `imgtools_m8` y `media-service-m8` como hijos directos de la raíz de este espacio de trabajo. La configuración inicial instala sus requisitos de desarrollo.
4. Abre `fa-workspace` en VS Code.
5. Desde la paleta de comandos (`F1` o `Ctrl+Shift+P`), selecciona **Dev Containers: Reopen in Container**.
6. Espera la primera compilación y verifica en una terminal nueva:

   ```bash
   python3 --version
   node --version
   docker --version
   headroom --help
   ```

`setup.sh` se ejecuta al crear el contenedor y `configure-mcp.sh` en cada inicio. Después de cambiar archivos de Dev Container o Compose, usa **Dev Containers: Rebuild and Reopen in Container**.

<a id="uso-diario"></a>

## Uso diario

- Consulta `.workspace/` antes de una decisión compartida de arquitectura o política.
- Lee el `AGENTS.md` de cada repositorio antes de modificarlo.
- Carga el perfil local o del Dev Container correspondiente en vez de usar rutas específicas de una máquina.
- Usa `headroom_compress` solo con salidas grandes no secretas y recupera el original solo cuando sea necesario.
- Guarda planes, análisis y estado en `.workspace/` y secretos fuera de Git.

Para comprobar Headroom o reparar su registro MCP dentro del contenedor:

```bash
docker compose -f .devcontainer/docker-compose.devcontainer.yml ps
docker logs --tail 200 headroom-proxy-server
bash .devcontainer/configure-mcp.sh
```

<a id="solucion-de-problemas"></a>

## Solución de problemas

| Problema | Qué hacer |
| --- | --- |
| Docker no está disponible | Inicia Docker Desktop y reconstruye el Dev Container. |
| Falla la instalación inicial de requisitos Python | Comprueba que los tres repositorios hermanos existen y reconstruye. |
| Headroom no está disponible | Consulta el estado y los logs de Compose; después reinicia o reconstruye el contenedor. |
| Faltan herramientas MCP de Headroom | Ejecuta `bash .devcontainer/configure-mcp.sh` y vuelve a abrir el contenedor. |
| Falta una extensión de VS Code | Reconstruye el Dev Container para reaplicar las extensiones. |
| Una política no está clara | Empieza en [`.workspace/README.md`](.workspace/README.md) y después lee el contexto seleccionado por `repo-types.json` y `policy.index.json`. |
