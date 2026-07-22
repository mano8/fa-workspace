# Root CI supply-chain refresh

The root workflow is the only workflow owned by `fa-workspace`. Every GitHub
Action in it is pinned to a full commit SHA and carries the reviewed release
tag as a comment. Python tooling is installed only from
`workflows/root-tooling.requirements.lock` with pip hash checking enabled.
The lock currently targets the workflow's `ubuntu-latest` CPython 3.12 x86_64
runtime; platform expansion requires a separate reviewed hash set.

## Controlled refresh

1. Review the upstream release notes and the exact GitHub Action release/tag.
2. Resolve the Action tag to a full commit SHA and update the `uses:` line and
   version comment together.
3. Resolve the Python packages from PyPI, select the wheel supported by the
   workflow runner, and record its SHA-256 in
   `root-tooling.requirements.lock`. Keep all runtime dependencies in the
   lock, even when they are transitive.
4. Run the supply-chain validator, the root unit suite, Ruff, and the root
   workspace validators from a clean checkout. Review the resulting diff and
   the upstream hashes before merging the refresh.

The refresh is intentionally manual and review-gated. Do not replace a SHA
with a tag, add an un-hashed install, or use an installer script in this
workflow. The CLI-owned feature manifest lock is
`.devcontainer/devcontainer-lock.json`; the broader reviewed bootstrap, image,
and feature-option identities are maintained separately in
`.devcontainer/bootstrap-lock.json` by Step 10.5's bootstrap procedure. CPython
comes from the digest-pinned official runtime image in
`.devcontainer/Dockerfile`; refreshing it requires updating the image digest,
the verified executable digest, the lock, the supply-chain fixtures, and the
SBOM together. Claude Code and Codex are installed at exact npm versions and
their executable hashes are verified during post-create. Optional floating
Node pnpm, standalone Docker Compose, and buildx installers are disabled. The
Docker feature's unavoidable apt-provided Compose plugin is exact-version
installed and verified during post-create. Any reviewed bootstrap refresh must
finish with two independent no-cache Dev Container builds and matching
post-create identity/capability probes.

Feature keys use the portable major-tag syntax required by Dev Container
clients. Their exact OCI manifest digests are enforced by the canonical
`.devcontainer/devcontainer-lock.json`; exact options are independently bound
by `.devcontainer/bootstrap-lock.json`. Verification builds use
`--frozen-lockfile`, so the tags cannot silently update the reviewed features.

## Root-tooling SBOM

`../sbom/root-tooling.cdx.json` is the deterministic CycloneDX 1.6 inventory
for the root-owned tooling boundary. It covers the pinned devcontainer base,
features, prebuilt Python runtime image, Node, Codex, Claude Code, Headroom, lock-file Python
dependencies, root CI Actions, and the bootstrap/configuration source hashes.
Regenerate it only when a reviewed input changes:

```text
python scripts/agent_context/generate_root_sbom.py --workspace . --write
python scripts/agent_context/generate_root_sbom.py --workspace . --check
```

The second command is enforced in root-only CI and rejects a stale or
nondeterministic inventory. It does not inspect or execute child repositories.
