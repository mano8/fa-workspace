# Python Policy

## Stack
- Python 3.12+
- FastAPI + Pydantic v2
- SQLAlchemy async + Alembic

## Python Environment

- Use the resolved interpreter configured by `M8_PYTHON` on every host OS.
  This is the stable execution contract regardless of how the interpreter was
  created.
- `M8_PYTHON_ENV_KIND` may be `conda`, `venv`, `virtualenv`, `uv`, `poetry`,
  `pipenv`, `pyenv`, `system`, `other`, or `none`.
- `M8_PYTHON_MANAGER` and `M8_PYTHON_ENV_NAME` are optional metadata for
  environment lifecycle operations. Routine linting, testing, and scripts must
  invoke `M8_PYTHON` directly instead of activating or assuming a manager.

PowerShell:

```powershell
& $env:M8_PYTHON --version
& $env:M8_PYTHON -m pytest
```

Bash:

```bash
"${M8_PYTHON}" --version
"${M8_PYTHON}" -m pytest
```

- Never assume conda, `.venv`, a Windows path, or a particular environment
  manager exists on another contributor's machine.
- If `M8_PYTHON_ENV_KIND=none`, Python work is unavailable until the user
  configures a local interpreter; do not silently fall back to another Python.

## Code Rules
- strict typing (no Any)
- Type hints required for all code
- Public APIs must have docstrings
- Functions must be focused and small
- Follow existing patterns exactly
- functions <= 50 lines
- cyclomatic complexity <= 10
- 88 char max line length
- ruff + mypy + bandit required
- **All tools must report zero issues - pre-existing violations must be fixed, not skipped.**

## Code Formatting Commands

- `ruff format .` - format
- `ruff check .` - lint
- `ruff check . --fix` - auto-fix
- `mypy . --ignore-missing-imports` - type check
- `bandit -r . --severity-level medium` - security scan

## Code style
- PEP 8 naming (snake_case for functions/variables)
- Class names in PascalCase
- Constants in UPPER_SNAKE_CASE
- Document with docstrings
- Use f-strings for formatting

## Development Philosophy

- **Simplicity**: Write simple, straightforward code
- **Readability**: Make code easy to understand
- **Performance**: Consider performance without sacrificing readability
- **Maintainability**: Write code that's easy to update
- **Testability**: Ensure code is testable
- **Reusability**: Create reusable components and functions
- **Less Code = Less Debt**: Minimize code footprint

## Coding Best Practices

- **Early Returns**: Use to avoid nested conditions
- **Descriptive Names**: Use clear variable/function names (prefix handlers with "handle")
- **Constants Over Functions**: Use constants where possible
- **DRY Code**: Don't repeat yourself
- **Functional Style**: Prefer functional, immutable approaches when not verbose
- **Minimal Changes**: Only modify code related to the task at hand
- **Function Ordering**: Define composing functions before their components
- **TODO Comments**: Mark issues in existing code with "TODO:" prefix
- **Simplicity**: Prioritize simplicity and readability over clever solutions
- **Build Iteratively** Start with minimal functionality and verify it works before adding complexity
- **Run Tests**: Test your code frequently with realistic inputs and validate outputs
- **Build Test Environments**: Create testing environments for components that are difficult to validate directly
- **Functional Code**: Use functional and stateless approaches where they improve clarity
- **Clean logic**: Keep core logic clean and push implementation details to the edges
- **File Organsiation**: Balance file organization with simplicity - use an appropriate number of files for the project scale
- Secret handling follows
  [`SEC-NO-SECRET-DISCLOSURE`](../architecture.md#sec-no-secret-disclosure);
  resolve suspected scanner false positives without printing the value.

## Migrations

- NEVER hand-write Alembic migration files.
- Do NOT run `alembic revision --autogenerate` yourself either.
- Migrations are generated/applied automatically on `compose up`, run manually
  by the user. Leave migration creation to that step - never author or
  autogenerate version files as part of a task.

## Testing
- pytest + anyio
- **Coverage: 100% required in every repo - no exceptions**
- New features require tests
- Bug fixes require regression tests
- `# pragma: no cover` only for truly unreachable guards (e.g. `if __name__ == "__main__"`)

## Architecture
- business logic isolated from transport layer
- migrations via Alembic only
- Workspace invariant:
  [`ARCH-NO-CROSS-SERVICE-DATA`](../architecture.md#arch-no-cross-service-data).

## Pre-commit Checklist (REQUIRED before every commit)

Run in this exact order - each step must report zero issues:

```bash
ruff format .                          # 1. format first
ruff check .                           # 2. lint
mypy . --ignore-missing-imports        # 3. type check
pytest --cov --cov-fail-under=100      # 4. tests + coverage
bandit -r . --severity-level medium    # 5. security
```

Never commit if any step fails.

## Error Resolution

1. CI Failures
   - Fix order:
     1. Formatting (`ruff format .`)
     2. Type errors (`mypy`)
     3. Linting (`ruff check .`)
   - Type errors:
     - Get full line context before changing anything
     - Use the exact TypedDict / specific type (not plain `dict`) when passing typed dicts
     - `# type: ignore[code]` must be on the **same line** as the error - not on a closing `)` of a multi-line call; split arguments when needed
     - When suppressing multiple mypy codes use `# type: ignore[code1, code2]`
     - Add type narrowing with `isinstance` or `cast` rather than blanket ignores
     - Verify function signatures match all call sites after refactoring

2. Common Issues
   - Line length:
     - Break strings with parentheses
     - Multi-line function calls
     - Split imports
   - Types:
     - Add None checks
     - Use specific types (e.g. `UpscaleModelDict` not `dict`) to avoid mypy arg-type errors
     - Narrow string types
     - Match existing patterns
   - After extracting private helpers:
     - Run `mypy` immediately to catch type mismatches introduced by new signatures
     - Run `ruff format .` since ruff may reformat multi-line calls and displace `# type: ignore` comments
     - Run coverage to ensure new helper lines are exercised by existing tests
     - A single `return` at the end of a helper is safer for line coverage than multiple early returns

3. Best Practices
   - Run formatters before type checks
   - Keep changes minimal
   - Follow existing patterns
   - Document public APIs
   - Test thoroughly
