# Contributing to Kozquloq

Thanks for your interest. All contributions are licensed under
**GPL-3.0-or-later** - see `LICENSE`.

## Local setup

```bash
uv sync --dev          # install runtime + dev dependencies
uv run pytest          # run the test suite
uv run mypy src tests  # strict type checking (0 errors required)
uv run ruff check .    # lint
uv run ruff format .   # format
uv run kozquloq demo --no-browser   # headless end-to-end smoke test
```

## Workflow

- **Branches:** `feat/<topic>`, `fix/<issue-id>`, `docs/<topic>`.
- **Commits:** Conventional Commits - `feat:`, `fix:`, `refactor:`,
  `test:`, `docs:`, `chore:`. Example: `fix: swap w/l bounds in points_in_box`.
- **Pull requests:** fill in the PR template; CI must be green (ruff, mypy
  strict, pytest with ≥85% coverage, headless demo smoke test).

## Non-negotiables for changes to `src/kozquloq/`

- See `AGENTS.md` - coordinate-system invariants, hermetic tests, frozen
  data contracts. These apply to human contributors equally.
- All transforms LiDAR↔Camera must route through the ego-pose intermediate
  frame with explicit timestamp alignment.
- Tests must never hit the network or require the nuScenes dataset -
  synthetic fixtures in `tests/conftest.py` only.
- DuckDB schema changes require a migration story; the tables in
  `storage/schema.sql` are a public contract for downstream tooling.
