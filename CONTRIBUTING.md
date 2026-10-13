# Contributing to Kozquloq

All contributions land under **GPL-3.0-or-later** - see `LICENSE`.

## Setup

```bash
uv sync --dev          # runtime + dev dependencies
uv run pytest          # the suite - 37 tests, no network, no real dataset
uv run mypy src tests  # strict typing, zero errors required
uv run ruff check .    # lint
uv run ruff format .   # format
uv run kozquloq demo --no-viz   # headless end-to-end smoke test
```

## Workflow

- **Branches:** `feat/<topic>`, `fix/<issue-id>`, `docs/<topic>`.
- **Commits:** Conventional Commits - `feat:`, `fix:`, `refactor:`,
  `test:`, `docs:`, `chore:`.
- **PRs:** fill in the template, keep CI green (ruff, mypy strict, pytest
  with at least 85% coverage, headless demo). CodeRabbit reviews every PR.

## The rules that do not bend

`AGENTS.md` lists these formally; the short version:

- **Sensor math routes through the ego frame.** LiDAR and camera timestamps
  differ and the car moved in between - never transform lidar to camera
  directly.
- **nuScenes box axes: x = length, y = width.** Use the devkit `Box` for
  occupancy and corners; hand-rolled math here has caused real bugs.
- **Road points are not box evidence.** Ground returns (lidar z < -2.0 m)
  get filtered before occupancy is counted.
- **Tests stay hermetic.** Synthetic fixtures only - no network, no nuScenes
  download. If a test needs real data, it is a script, not a test.
- **`storage/schema.sql` is a public contract.** Downstream tooling reads
  those tables; changes need a migration story, not a silent rename.
