# General

- Do not wrap the lines of md files. Use one line per paragraph.
- Names and code must be self-documenting.
- Match existing patterns exactly.
- Prefer functions over classes.
- Do not write comments explaining "what" code does. Explain "why" only when needed.

## Backend

- Never add a package manually into pyproject.toml. Use `uv add` (never pip).
- Write Google-style docstrings for all production code. Do not write docstrings for tests.
- Test file structure must mirror source file structure.
- Test __init__.py files must be empty. Other __init__.py files must contain a short docstring unless more context is needed.
- Do not use from `__future__ import annotations` unless required and only use `if TYPE_CHECKING` to handle circular imports. Do not manually stringize annotations.
- Always place imports at the top of files.
- If you think you need `type: ignore` comments - you probably don't. Figure out the actual problem and fix it.
- Use `__init__.py` files as a public API. Modules (except test modules) should only import from public APIs when importing from another package in the repo.

## Logging

- Create module-level loggers with `logger = logging.getLogger(__name__)`.
- Never log an exception that will propagate; FastAPI and Uvicorn will report it. Only log when retrying, falling back, or handling an exception without propagating it.
- Use a stable `snake_case` event name and include useful structured context in `extra`.
