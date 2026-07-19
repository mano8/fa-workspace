# Git commit task

- Inspect the selected repository's status before committing.
- Do not add attribution footers or identify the tool that produced commit or
  pull-request text.
- Validation remains repository-owned. For a Python child whose configuration
  exposes the historical checks, run format, lint, type check, tests/coverage,
  and security scan in that order; do not commit when a required check fails.
  For a TypeScript child, run its required typecheck before committing.
- This overlay authorizes only the recorded commit operation. It does not
  authorize branch creation, pushing, opening a pull request, or releasing.
