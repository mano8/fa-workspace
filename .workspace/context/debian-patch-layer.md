# Debian Patch-Layer Policy

Canonical owner of the one Debian patch-layer form every service image in the
fleet carries, and of the rule that their base digests move together. Ratified
by `B23-converge-patch-layer` (Wave 6) of
`.workspace/plans/stack/todo/consumer-alignment-closure-remediation-plan-2026-08-16.md`
(gitignored; not the authority — this file is), closing that plan's `G18`
and, with it, `G17` and the residual of `G16`.

Workspace invariant: [`CFG-SINGLE-WORKSPACE-OWNER`](../architecture.md#cfg-single-workspace-owner)
— this file is the sole canonical owner of the form and of the base-digest
rule; no child repository or agent-specific directory may keep a competing
copy of either. The Dockerfiles carry the form; they do not define it.

## Scope

The five service images and the files that build them:

| Repository | Dockerfile(s) |
| --- | --- |
| `fa-auth-m8` | `auth_user_service/Dockerfile`, `auth_user_service/Dockerfile.local`, `examples/fastapi_full/Dockerfile` |
| `prompt-engine-m8` | `promt_engine_service/Dockerfile` |
| `reparto-docente-m8` | `reparto_service/Dockerfile` |
| `media-service-m8` | `media_service/Dockerfile` |
| `media-worker-m8` | `worker/Dockerfile` |

`fa-auth-m8`'s two extra files are the same block in the same repository —
its `curl` hand-raise (`83e5b1d`) touched all three at once — and are held to
the form for that reason; the published image is built from the first.

## Decision 1 — the one form

The runtime stage's Debian layer is exactly this, byte-for-byte, in every
file above (comment included; the comment names this file as owner):

```dockerfile
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*
```

- **`apt-get upgrade -y`, always.** Every Debian package the base ships is
  raised to the current candidate on every build, so an advisory in any
  package is fixed on the next build in every repository, with no commit.
- **No exact `=` pins, ever.** An exact pin is the only thing `upgrade -y`
  cannot raise, so it freezes the image on the pinned version until a human
  edits the Dockerfile — that is `G16` (`openssl`, twice) and `G17` (`curl`,
  three identical commits for one advisory). The `>=` form does not exist in
  `apt-get` (`E: Unable to locate package curl>`), so there is no cheap
  variant of a pin to reach for.
- **Nothing installed that the base does not already ship.** The only
  package the fleet ever installed was `curl`, in three images, and nothing
  in any of them used it (no `HEALTHCHECK`; the Compose healthchecks use
  `python -c "import urllib.request…"`, `pg_isready` and `redis-cli ping`;
  the `curl` calls in workflows run on the Actions runner or inside the
  `minio` container). It is gone.
- **If a package must ever lead the pinned base** — an advisory fixed in
  Debian but not yet in any published `python:3.14-slim` digest — the
  recorded form is an unpinned install (or the plain upgrade) followed by a
  floor assertion **in the same `RUN`**, verified under `G17` against a
  pinned base (install and assertion exit 0; an impossible floor exits 1):

  ```dockerfile
  RUN apt-get update \
      && apt-get upgrade -y \
      && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libssl3t64)" ge "3.5.7-1~deb13u2" \
      && rm -rf /var/lib/apt/lists/*
  ```

  It self-heals per advisory and fails the build closed if Debian — or a
  base digest pinned backwards — ever regresses below the vetted floor. The
  assertion is temporary by construction: it is removed at the next
  fleet-wide digest raise (Decision 2), which is what makes the base ship
  the floor. At ratification the floor list is empty: the ratified digest
  ships every package the fleet had ever pinned at or above the pinned
  version (measured below).

The options weighed and why this one: **(a)** drop `curl` and replace the
media pair's seven pins with `upgrade -y`; **(b)** `upgrade -y` everywhere
plus the floor assertion for any package that must lead the base; **(c)**
leave the three forms and hand-raise per advisory per repository. (c) is
what `G17` measured being executed by default — three identical commits per
advisory on a package nobody used — and is refused. (a)+(b) together are the
form above; (b)'s assertion is recorded here rather than carried in the
Dockerfiles because, on a shared current digest, no package leads the base.

## Decision 2 — base digests move together

All five images pin **the same** `python:3.14-slim` digest, raised in one
change across the five repositories:

- **on advisory** — whenever a `trivy-image` gate (`CRITICAL,HIGH`,
  `ignore-unfixed: true`, the fleet's settings) goes red on a base-image
  package in any one of the five, the fix is a fleet digest raise, not a
  pin in the repository that happened to build first; and
- **on cadence** — otherwise at each service's next release, taking the
  other four along, so the fleet never carries more than one digest for
  longer than one release window.

Never one repository alone: the measured state at ratification was four
distinct digests across five images (`c845af…` Debian 13.5, `cad9a2…` 13.6,
`cea0e6…` 13.6, `83ff1d…` 13.6 ×2), raised per repository on no schedule,
so one advisory produced three outcomes. The read command:

```bash
for f in fa-auth-m8/auth_user_service/Dockerfile prompt-engine-m8/promt_engine_service/Dockerfile \
         reparto-docente-m8/reparto_service/Dockerfile media-service-m8/media_service/Dockerfile \
         media-worker-m8/worker/Dockerfile; do
  grep -o 'python:3.14-slim@sha256:[0-9a-f]\{12\}' "$f" | sort -u | tr '\n' ' '; echo "$f"
done
# one digest, one line each; and the RUN blocks are identical:
for f in …same list…; do sed -n '/^# Debian patch layer/,/apt\/lists/p' "$f" | md5sum; done
```

## Ratified digest (2026-09-20)

`python:3.14-slim@sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2`
— Debian 13.7, Python 3.14.7, image created 2026-09-19. Measured inside
that digest against the packages the fleet had ever pinned (installed ==
`apt-cache policy` candidate for all eight, so `upgrade -y` is a no-op on
the day of ratification and the seven media pins were already satisfied by
the base):

| Package | Was pinned by | Pinned version | Ships in `caaf35…` |
| --- | --- | --- | --- |
| `curl` | three repos (`G17`) | `8.14.1-2+deb13u5` | not installed; candidate `8.14.1-2+deb13u5` |
| `openssl` / `libssl3t64` / `openssl-provider-legacy` | media pair (`G16`) | `3.5.7-1~deb13u2` | `3.5.7-1~deb13u2` |
| `gzip` | media pair | `1.13-1+deb13u1` | `1.13-1+deb13u1` |
| `libpcre2-8-0` | media pair | `10.46-1~deb13u2` | `10.46-1~deb13u2` |
| `libsqlite3-0` | media pair | `3.46.1-7+deb13u2` | `3.46.1-7+deb13u2` |
| `perl-base` | media pair | `5.40.1-6+deb13u1` | `5.40.1-6+deb13u1` |

The previous digests, for the record, shipped `openssl` at `3.5.6-1~deb13u1`
(`c845af…`) or `3.5.6-1~deb13u2` (`cea0e6…`, `83ff1d…`) and every other row
one Debian revision behind — which is exactly why the media pair had grown
seven pins.
