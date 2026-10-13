# Agent Operating Standards — Kozquloq

Non-negotiable rules for AI agents (and humans) modifying this repository.

## Non-negotiable invariants

1. **Coordinate System Invariant.** All LiDAR↔Camera transformations must
   route through the ego-vehicle intermediate frame with explicit timestamp
   alignment: `lidar → ego(t_lidar) → global → ego(t_cam) → camera`
   (see `auditors/geometry.py::_lidar_to_camera_matrix`). Never shortcut
   lidar→camera directly; ego motion between sensor timestamps is real.
2. **nuScenes box local frame: x = length, y = width.** `AnnBox.size` is
   `(w, l, h)`; bounds test and corner generation must use
   `size[[1,0,2]] / 2` as half-extents (see `geometry._half_extents`).
   Deviating silently corrupts lidar point counts and produces false ghosts.
3. **Ground Plane Isolation.** Synthetic fixtures must place ground returns
   at lidar z ≤ −2.0 so they cannot leak inside box z-ranges. Point-in-box
   occupancy counts must only count real interior points — any heuristic
   that lets ground hits count as box support is a bug.
4. **Hermetic Testing.** Zero external network calls in `tests/`. All tests
   run on synthetic fixtures in `tests/conftest.py`; the nuScenes dataset
   must never be required. Tests run offline or they don't merge.
5. **Typing and Immutability.** Internal data contracts in
   `src/kozquloq/types.py` (`AnnBox`, `FrameBundle`, `SceneMeta`) are frozen
   dataclasses. Mutate only audit outputs (`BoxAuditResult`), never inputs.
   `mypy --strict` must pass on `src` and `tests`.

## Verification contract

Before claiming done: `uv run pytest` (≥85% coverage), `uv run mypy src tests`
(0 errors), `uv run ruff check .` + `uv run ruff format --check .` clean,
`uv run kozquloq demo --no-browser` exits 0.

## Design conventions

- Auditors implement `auditors/base.py::BaseAuditor` (`audit_sample` writes
  into `FrameFindings`; `reset()` clears per-scene state).
- Storage implements `storage/base.py::AuditStore`; `DuckDBAuditStore` is the
  reference implementation. Pipeline code depends on the abstraction only.
- `storage/schema.sql` is a public contract — schema changes need a
  documented migration path.
- Keep it boring: vectorized NumPy, parameterized SQL, no unrequested
  abstraction.
