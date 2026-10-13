## Summary

<!-- What changed and why - technical motivation, not a file list. -->

## Approach

<!-- Key design decisions, alternatives rejected, anything surprising. -->

## Checklist

- [ ] Tests added/updated; `uv run pytest` passes locally
- [ ] `uv run mypy src tests` - 0 errors
- [ ] `uv run ruff check .` and `uv run ruff format --check .` clean
- [ ] No breaking DuckDB schema migrations (or migration documented)
- [ ] `uv run kozquloq demo --no-viz` runs cleanly
- [ ] Coordinate-transform changes verified against `num_lidar_pts` or synthetic ground truth
- [ ] No new network access in `tests/`

## Related issues

<!-- Closes #... -->
