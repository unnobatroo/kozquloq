# Kozquloq

**A linter for self-driving car labels.** Think eslint, but for AV datasets.

Self-driving datasets like nuScenes contain millions of 3D boxes that human
annotators drew around cars, pedestrians, and barriers. Some of those labels
are wrong in ways that quietly poison a model: a box drawn where the LiDAR
recorded nothing, a "car" that accelerates at 32 m/s² between frames, a rigid
object that shrinks 30% overnight in the data. Kozquloq reads the dataset,
checks every label against what the sensors actually saw, and hands you a list
of annotation tokens to drop from training - plus images showing exactly what
was flagged and why.

The name is Uzbek: *köz quloq* - eye and ear. One tool that watches both the
camera and the point cloud.

## Quickstart

```bash
uv sync
uv run kozquloq demo          # synthetic scene, full audit, ~1 second
```

On real data:

```bash
python scripts/download_nuscenes_mini.py --out data/nuscenes
uv run kozquloq scan --dataroot data/nuscenes --viz-dir viz_out
uv run kozquloq export --output invalid_tokens.parquet
uv run kozquloq viz <sample_token> --dataroot data/nuscenes
```

No dataset handy? Generate a fixture dir:

```bash
python scripts/seed_synthetic_fixtures.py --out data/fixture
uv run kozquloq scan --dataroot data/fixture
```

## What it catches

- **Ghost labels** - a box where LiDAR recorded zero points. Either the
  annotator hallucinated or the sensor dropped data; either way it teaches
  the model to see objects that are not there. On nuScenes v1.0-mini this is
  6% of all labels.
- **Teleporting objects** - per-instance velocity and acceleration tracked
  across frames. Non-physical motion means the annotation jittered or the
  tracking ID hopped.
- **Shapeshifting boxes** - rigid objects whose volume changes more than 15%
  between frames.
- **Sensor health** - underexposed camera frames and LiDAR/camera alignment
  drift, per frame.

Everything flagged gets a severity score. Anything at or above 0.5 lands in
the exported mask.

## The four commands

- `scan` - the main event: audits everything, prints a health grade and a
  failure-rate table per weather/category slice, optionally writes overlays
  for every flagged frame (`--viz-dir`).
- `viz <sample_token>` - the overlay for one frame, for eyeballing a specific
  case.
- `export` - the actual product: a Parquet or JSON file of `annotation_token`
  plus a human-readable `reason`, filtered by `--min-severity`.
- `demo` - synthetic scene, in-memory database, summary in about a second.

## Live report

[kozquloq.vercel.app](https://kozquloq.vercel.app) shows a real audit of
nuScenes v1.0-mini as an interactive report - sortable slices, a searchable
mask table with one-click JSON/CSV export, and overlay galleries. It is a
static snapshot, not a service. Rebuild it after your own scan:

```bash
uv run python scripts/build_site.py --db data/kozquloq.duckdb \
    --dataroot data/nuscenes --out site_out
cd site_out && vercel deploy --prod
```

## Honest caveats

Zero LiDAR points is a strong signal, not a verdict - nuScenes legitimately
annotates occluded objects, so the mask is a review list, not ground truth.
And there is no recall number on real data: we know it catches faults we
deliberately inject (the test suite plants ghosts, teleports and volume jumps
and asserts they get caught), but how many real mislabels it misses is
unmeasurable without hand-verified labels.

## For training pipelines

`kozquloq.pytorch.QualityAuditDataset` loads audits straight into tensors:
each item carries engineered features, a corruption label, and a loss weight
that downweights suspicious labels to 0 instead of deleting them.

## Docs

All documentation lives in the
[wiki](https://github.com/unnobatroo/kozquloq/wiki):

- [Architecture](https://github.com/unnobatroo/kozquloq/wiki/Architecture) -
  how the pieces fit, with diagrams.
- [CLI Reference](https://github.com/unnobatroo/kozquloq/wiki/CLI-Reference) -
  the four commands and their outputs.
- [Deployment](https://github.com/unnobatroo/kozquloq/wiki/Deployment) -
  report site, Azure batch job, Docker.
- [Contributing](https://github.com/unnobatroo/kozquloq/wiki/Contributing) -
  dev setup and CI gates.
- [Security](https://github.com/unnobatroo/kozquloq/wiki/Security) - threat
  model and reporting.
- [AGENTS.md](AGENTS.md) - the invariants that must never break (kept in-repo:
  agents load it automatically).

## Test

```bash
uv run pytest -v
uv run mypy src tests
```

GPL-3.0-or-later. Sensor-fusion math is delegated to the nuScenes devkit and
pyquaternion; persistence is a local DuckDB file; nothing in the core needs
a network connection.
