# Standalone child instruction rollout contract

**Contract ID:** `m8-child-repository-rollout-v1`

**Frozen:** 2026-07-20

**Status:** APPROVED FOR INDEPENDENT `C01`--`C16` ROLLOUT

**Machine record:** `child-repository-rollout-v1.boundaries.json`

## Scope and ownership

This root-owned contract freezes Phase 8 Step 8.1. It defines the shape and
verification gate for later independent child changes; it does not edit a
child, authorize a child commit, or combine child delivery with a parent
commit. Each `C01`--`C16` boundary remains child-owned and requires fresh human
execution authorization.

The machine record is the exact classification decision and file boundary. It
records the current byte count and SHA-256 of every classified child
`AGENTS.md`/`CLAUDE.md` pair, the required neutral owner, and the only three
paths allowed at each rollout boundary. No `.claude` rule/skill or child-local
`.codex` source was observed, so none is allowed. A newly discovered source or
any input drift invalidates that boundary until it is reviewed and the root
record is deliberately revised before the child edit.

The Step 5.1 hashes were reproduced for 31 of 32 child inputs. The current
`fa-auth-m8/CLAUDE.md` is 728 bytes with SHA-256
`a978ab15a7e6f2bef16554f29d0afabcbb49abadc1d6ad4112f646479a3d1ae5`,
not the prior 726-byte input. Re-reading the current prose shows the same
neutral, asymmetric classification and the same portability defect: its
example/version-alignment rule is repository-specific but uses hard-coded
workspace paths. `C06` therefore records the current identity and requires
that rule to be preserved in repository-relative form under auth-sensitive
review.

## Frozen child template

Every child rollout uses exactly these owners:

- `REPOSITORY_CONTEXT.md` is the single neutral, local owner for repository
  identity, purpose, owned paths/contracts, repository-specific architecture,
  portable commands, and implications of workspace invariants. It contains no
  agent-specific behavior, mandatory parent lookup, task authorization,
  sibling authority, or copied workspace policy rationale.
- `AGENTS.md` is the compact Codex entrypoint. It tells Codex to use
  `REPOSITORY_CONTEXT.md` as the repository-local source and states that a
  verified nearest workspace may provide optional launcher-selected
  enhancement. It does not invoke a resolver, import Claude configuration, or
  make the parent a prerequisite.
- `CLAUDE.md` is the compact Claude entrypoint with the same local neutral
  owner and optional-parent semantics through Claude-supported integration. It
  does not import `AGENTS.md`, claim a currently unsupported canonical Claude
  transport, or make the parent a prerequisite.

All three files must be strict UTF-8 without BOM, LF-only, final-newline
terminated, repository-relative, and independently meaningful in a child-only
clone. Neutral facts appear once in `REPOSITORY_CONTEXT.md`; the two agent
entrypoints may repeat only the minimum integration instruction needed by
their own client.

## Classification and extraction decision

The 16 pairs contain neutral repository information. Eight are semantic
duplicates and eight are asymmetric neutral overlaps. None contains a rule
that becomes agent-specific merely because it currently appears in one
entrypoint. The frozen decision for every boundary is
`extract-neutral-local-context`: merge neutral meaning into
`REPOSITORY_CONTEXT.md`, retain only agent integration mechanics in the
corresponding entrypoint, and apply the boundary-specific reconciliation gates
from the machine record.

Workspace-wide definitions remain owned by `.workspace/`. A child may state
the repository-local implication needed to remain safe and standalone, but it
must not redefine workspace authority, facet selection, cross-repository
scope, task authorization, or shared invariants. Absolute `/.workspace`,
`/workspace/...`, root-entrypoint, drive/user-profile, or mandatory-parent
references are removed rather than translated to another host-specific path.

## Parent-absent standalone fallback

Parent discovery is never required. In a standalone clone:

1. the active agent loads its local entrypoint and
   `REPOSITORY_CONTEXT.md` from the child root;
2. no parent path is assumed, fetched, or synthesized;
3. workspace policy units, tasks, siblings, and cross-repository authority are
   unavailable; and
4. parent absence is a successful local native/limited outcome, not an error.

A request that explicitly requires unavailable workspace or sibling scope
fails with `E_SCOPE_UNAVAILABLE`. Standalone operation must not be described as
canonical unless a future capability row separately proves its native
inspection, delivery, and lifecycle requirements.

## Nearest-workspace enhancement

When a launcher or supported integration is explicitly used, it may walk
ancestors for the nearest regular `.m8-workspace-root` whose exact content is
`m8-workspace-v2\n`. The candidate is accepted only when its strict v2 registry
maps the child identifier to that exact direct-child path. Symlink aliases,
internal paths, a more distant workspace after an invalid nearer marker, and
unregistered children fail closed.

The verified parent may then resolve `always` plus ordered facets and explicitly
authorized tasks for that one repository. Enhancement never changes the local
owner, lets the child self-authorize a task, injects sibling context, or makes
the nested child unusable when the parent is later absent.

## Canonical delivery and receipt expectation

For parent-found canonical checks, resolver selection alone is insufficient.
The launcher/hook must produce the exact manifest and JCS envelope and a
matching `HANDED_OFF` receipt under the W2a contract. Native local sources must
have current path/hash evidence and must not also appear in the injected
envelope. The receipt must match repository, mode, generation, source,
manifest, envelope, capability, configuration, native-evidence, task, and
authorization identities, with one handoff per launcher-controlled generation.

The current canonical obligation remains only Codex devcontainer
non-interactive mode. Current Claude modes and unwrapped native Codex modes are
reported as limited/noncanonical and never promoted by model acknowledgement
or printed context. A parent-absent smoke test requires no receipt because it
does not claim canonical workspace delivery.

## Allowed static smoke tests

Each C boundary may perform only instruction/context checks:

- re-read and hash the two frozen inputs before editing;
- prove the actual edit set is a subset of the exact three-path allowlist;
- validate strict UTF-8, LF, final newline, portable relative paths, and one
  neutral owner;
- inspect Codex and Claude native instruction discovery without executing the
  child project;
- exercise synthetic or installed-client-supported parent-found and
  parent-absent instruction selection and context-budget accounting; and
- for a claimed canonical mode, compare manifest/envelope/receipt/native
  evidence byte-for-byte with resolver output.

The boundary must not run, parse, emulate, or interpret child CI, tests,
workflows, branches, remotes, releases, or delivery state. It must not install
dependencies or execute repository commands merely because they remain as
neutral documentation.

## Rollback checklist

Rollback is per child and never spans repositories:

1. stop if pre-edit hashes or the discovered agent-source set differ from the
   machine record;
2. preserve the exact original two-file bytes/hashes in the boundary evidence;
3. confirm only the three allowlisted paths changed and no child CI/workflow or
   source file changed;
4. restore the original `AGENTS.md` and `CLAUDE.md` bytes and remove only the
   boundary-created `REPOSITORY_CONTEXT.md` when reverting an uncommitted
   rollout;
5. re-run both parent-found and parent-absent static instruction fixtures for
   Codex and Claude;
6. confirm the parent workspace registry/policies and every sibling remain
   untouched; and
7. record the rollback result in the child boundary without creating a parent
   commit for child-owned changes.

No cleanup command may infer its targets from a glob, unresolved variable, or
workspace root. A committed child rollout is reverted through that child's
normal, separately authorized Git workflow.
