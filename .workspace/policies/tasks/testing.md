# Testing and quality task

Use repository-owned manifests, lockfiles, and quality configuration to choose
the actual runner and gates. Test changed behavior with realistic inputs; new
features require tests and bug fixes require regression tests. Build an
isolated test environment when a component cannot be validated directly.

## Python repositories

When the child configuration exposes these tools, run formatting, linting,
type checking, tests/coverage, and security scanning through the configured
interpreter. Typical commands are `ruff format .`, `ruff check .`,
`mypy . --ignore-missing-imports`, the configured `pytest` coverage command,
and `bandit -r . --severity-level medium`; the child's configuration owns the
exact gate.

Resolve failures in this order: formatting, typing, then linting. Read full
line context before changing a typing failure; use the exact structured type,
narrow with `isinstance` or `cast`, and keep a targeted ignore on the same line
as the error. After extracting a typed helper, rerun the type checker and
formatter, then coverage. Prefer one final helper return when multiple early
returns would create artificial coverage gaps.

## TypeScript and Astro repositories

Detect the package manager from `packageManager` and lockfiles before invoking
repository scripts. Resolve formatting, typing, then linting failures, and run
the child-owned test/build/typecheck commands. Astro package checks may include
build, registry, pack, and installed-tarball fixtures only when the selected
task or child configuration requires them.
