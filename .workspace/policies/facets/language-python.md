# Python language policy

## Code rules

- Use strict typing; do not use `Any`.
- Require type hints for all code and docstrings for public APIs.
- Keep functions focused and small; follow existing patterns.
- Use PEP 8 names: `snake_case` for functions and variables, `PascalCase` for
  classes, and `UPPER_SNAKE_CASE` for constants.
- Use f-strings for formatting.

## Implementation guidance

- Prefer simple, readable, maintainable, testable, reusable code with a small
  footprint.
- Use early returns to avoid nested conditions; choose descriptive names;
  prefer constants where appropriate; avoid duplication; prefer functional,
  immutable approaches when they are not verbose; and make only task-related
  changes.
- Define composing functions before their components and mark existing issues
  with a `TODO:` prefix.
- Build iteratively, beginning with minimal working functionality.
- Keep boundaries clean and organize files in proportion to the application.
