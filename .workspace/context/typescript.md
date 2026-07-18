# TypeScript Policy

## Stack
- Next.js / Vite + Preact
- strict mode enabled
- Zod validation required

## Runtime And Package Manager

- Detect the repository's required package manager from `packageManager` and
  lockfiles before running commands.
- Use `M8_PACKAGE_MANAGER` only as the configured default/fallback when the repo
  does not declare one.
- npm, pnpm, Yarn, Bun, and other configured managers are valid. Do not create
  or replace a lockfile merely to match the local default.
- Use `M8_JS_RUNTIME` for direct runtime commands and
  `M8_PACKAGE_EXECUTOR` only when the selected manager needs an executor.

## Rules
- no any
- UI must be stateless
- API calls must be isolated in hooks/services

## Extension Architecture
- background worker handles privileged logic
- content scripts = UI only

## Safety
- all external inputs must be validated

## Testing
- Vitest required
- **Coverage: 100% required - no exceptions**
- New features require tests
- Bug fixes require regression tests

## Error Resolution
- Fix order: formatting -> type errors -> linting
- Run `tsc --noEmit` before committing
- ESLint must report zero issues

