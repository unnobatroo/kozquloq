# Kozquloq

Autonomous vehicle sensor data quality & diagnostics pipeline for nuScenes.
Audits geometric calibration (LiDAR→camera reprojection), annotation integrity
(ghost labels), kinematic consistency (impossible velocities/accelerations,
volume drift), and sensor health (underexposure, return counts) — then persists
metrics to DuckDB for slicing, masking in PyTorch training, agentic diagnosis,
and standalone HTML inspection reports.

## Quickstart

```bash
uv sync
uv run kozquloq demo          # zero-setup: synthetic scene -> audit -> report
```

Real data:

```bash
python scripts/download_nuscenes_mini.py --out data/nuscenes
uv run kozquloq audit --dataroot data/nuscenes --version v1.0-mini
uv run kozquloq report --serve
uv run kozquloq diagnose "which slices degrade most and why?"
uv run kozquloq chat
```

Fixture data (no nuScenes needed):

```bash
python scripts/seed_synthetic_fixtures.py --out data/fixture
uv run kozquloq audit --dataroot data/fixture
```

## Test

```bash
uv run pytest -v
```

## Layout

See `src/kozquloq/` — `auditors/` (geometry, kinematics, sensor health),
`storage/` (DuckDB schema + views), `pytorch/` (quality-masked Dataset),
`agent/` (tool-calling diagnostics, `mock` and `openai` providers),
`visualization/` (OpenCV overlays + Jinja2 HTML report), `cli/` (Typer app,
Rich REPL).
