# Kozquloq

An annotation linter for autonomous vehicle datasets (nuScenes).
It audits 3D annotations for spatial failures (ghost labels: boxes where the
LiDAR saw nothing), kinematic failures (non-physical velocities/accelerations,
volume drift), and sensor health (underexposure, geometric drift) - then
exports invalid token lists for training pipelines as Parquet or JSON masks,
plus annotated camera-frame overlays for visual inspection.

## Quickstart

```bash
uv sync
uv run kozquloq demo          # zero-setup: synthetic scene -> audit -> summary
```

Real data:

```bash
python scripts/download_nuscenes_mini.py --out data/nuscenes
uv run kozquloq scan --dataroot data/nuscenes --viz-dir viz_out
uv run kozquloq export --output invalid_tokens.parquet
uv run kozquloq viz <sample_token> --dataroot data/nuscenes --output-dir viz_out
```

Fixture data (no nuScenes needed):

```bash
python scripts/seed_synthetic_fixtures.py --out data/fixture
uv run kozquloq scan --dataroot data/fixture
```

## Live report

A static audit report on nuScenes v1.0-mini is hosted at
[kozquloq.vercel.app](https://kozquloq.vercel.app). Rebuild it after a scan:

```bash
uv run python scripts/build_site.py --db data/kozquloq.duckdb \
    --dataroot data/nuscenes --out site_out
cd site_out && vercel deploy --prod
```

## Commands

- `scan` - run the audit, print a Rich summary + slice failure table; with
  `--viz-dir` also writes annotated JPEG overlays for every flagged frame.
- `viz <sample_token>` - render the overlay for one keyframe (needs `--dataroot`).
- `export` - write the invalid-token mask (`annotation_token` + `reason`) as
  `.parquet` (DuckDB COPY) or `.json`.
- `demo` - in-memory synthetic audit; writes preview overlays to `./viz_out/`
  unless `--no-viz`. Runs in under a second.

## Compute on Azure

`Dockerfile` builds the audit pipeline as a container; `infra/azure/` shows
running it as an Azure Container Apps job that writes the Parquet mask to
Blob Storage.

## Test

```bash
uv run pytest -v
uv run mypy src tests
```

## Layout

See `src/kozquloq/` - `auditors/` (geometry, kinematics, sensor health),
`storage/` (DuckDB schema + views), `pytorch/` (quality-masked Dataset),
`visualization/` (static overlay renderer), `cli/` (Typer app).

Architecture and data-flow diagrams: `docs/architecture.md`.
