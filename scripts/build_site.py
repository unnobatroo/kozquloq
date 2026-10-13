"""Build the static audit-report site deployed to kozquloq.vercel.app.

Usage:
    uv run python scripts/build_site.py --db data/kozquloq.duckdb \
        --dataroot v1.0-mini --out site_out

Reads the audit DB for summary/slice/token stats, renders up to --max-images
flagged-frame overlays from the dataset, and writes a single index.html plus
img/*.jpg into --out. Deploy with `vercel deploy --prod` inside the output dir.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path


def render_images(dataroot: str, version: str, img_dir: Path, max_images: int) -> list[str]:
    """Save overlays for the first flagged frames; return jpeg filenames."""
    from kozquloq.auditors import DEFAULT_AUDITORS, audit_frame
    from kozquloq.ingestion import load_frames
    from kozquloq.visualization.overlay import save_annotated_frame

    names: list[str] = []
    for _scene, frames in load_frames(dataroot, version):
        auditors = [cls() for cls in DEFAULT_AUDITORS]
        for bundle in frames:
            _, boxes = audit_frame(bundle, auditors)
            if any(r.flagged for r in boxes):
                names.append(save_annotated_frame(bundle, boxes, str(img_dir)).name)
                if len(names) >= max_images:
                    return names
    return names


def build(db: str, img_names: list[str]) -> str:
    from kozquloq.storage.duckdb_store import Store

    store = Store(db)
    s = store.get_summary()
    slices = store.get_slice_metrics()[:12]
    invalid = store.get_invalid_tokens()[:10]
    esc = lambda v: html.escape(str(v))  # noqa: E731
    fmt = lambda v: f"{v:,}" if isinstance(v, int) else v  # noqa: E731

    slice_rows = "".join(
        f"<tr><td>{esc(r['weather'])}</td><td>{esc(r['time_of_day'])}</td>"
        f"<td>{esc(r['category'])}</td><td>{fmt(r['total_annotations'])}</td>"
        f"<td>{fmt(r['ghost_labels_count'])}</td>"
        f"<td>{fmt(r['kinematic_outliers_count'])}</td>"
        f"<td>{r['failure_rate_pct']}%</td></tr>"
        for r in slices
    )
    inv_rows = "".join(
        f"<tr><td class='mono'>{esc(r['annotation_token'][:12])}...</td>"
        f"<td>{esc(r['category'])}</td><td>{r['severity']:.2f}</td>"
        f"<td>{esc(r['reason'])}</td></tr>"
        for r in invalid
    )
    gallery = "".join(
        f"<figure><img src='img/{esc(n)}' loading='lazy'/>"
        f"<figcaption class='mono'>{esc(n[:8])}</figcaption></figure>"
        for n in img_names
    )
    grade_color = {
        "A": "#22c55e",
        "B": "#84cc16",
        "C": "#eab308",
        "D": "#f97316",
        "F": "#ef4444",
    }[s["grade"]]

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kozquloq - AV annotation lint report</title>
<style>
:root {{ --bg:#0d1117; --card:#161b22; --border:#30363d; --fg:#e6edf3; --dim:#8b949e; }}
* {{ margin:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif; }}
.wrap {{ max-width:1100px; margin:0 auto; padding:32px 20px; }}
h1 {{ font-size:28px; }} .tag {{ color:var(--dim); margin:4px 0 24px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:20px 0; }}
.card {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; }}
.card .v {{ font-size:28px; font-weight:700; }} .card .k {{ color:var(--dim); font-size:12px; text-transform:uppercase; }}
.grade {{ font-size:44px; font-weight:800; color:{grade_color}; }}
table {{ width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--border); border-radius:8px; overflow:hidden; margin:12px 0 32px; }}
th,td {{ padding:8px 12px; text-align:left; border-bottom:1px solid var(--border); font-size:13px; }}
th {{ background:#1c2128; color:var(--dim); text-transform:uppercase; font-size:11px; letter-spacing:.5px; }}
.mono {{ font-family:ui-monospace,Menlo,monospace; font-size:12px; }}
.gal {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:12px; }}
.gal img {{ width:100%; border-radius:8px; border:1px solid var(--border); display:block; }}
figcaption {{ color:var(--dim); padding:4px 0 0; }}
h2 {{ margin:28px 0 8px; font-size:19px; }}
.cmd {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:12px 16px; font-family:ui-monospace,Menlo,monospace; font-size:13px; overflow-x:auto; white-space:pre; }}
a {{ color:#58a6ff; }} .foot {{ color:var(--dim); font-size:12px; margin-top:36px; }}
</style></head><body><div class="wrap">
<h1>Kozquloq</h1>
<p class="tag">Annotation linter for autonomous-driving datasets - eslint for AV data.
Static audit report generated from <b>nuScenes v1.0-mini</b>.
<a href="https://github.com/unnobatroo/kozquloq">github.com/unnobatroo/kozquloq</a></p>
<div class="grid">
<div class="card"><div class="grade">{s["grade"]}</div><div class="k">Health grade</div></div>
<div class="card"><div class="v">{fmt(s["frames"])}</div><div class="k">Frames</div></div>
<div class="card"><div class="v">{fmt(s["annotations"])}</div><div class="k">Annotations</div></div>
<div class="card"><div class="v">{fmt(s["flagged"])}</div><div class="k">Flagged ({s["failure_pct"]}%)</div></div>
<div class="card"><div class="v" style="color:#ef4444">{fmt(s["ghosts"])}</div><div class="k">Ghost labels</div></div>
<div class="card"><div class="v" style="color:#f59e0b">{fmt(s["kinematic_outliers"])}</div><div class="k">Kinematic</div></div>
<div class="card"><div class="v" style="color:#3b82f6">{fmt(s["scale_unstable"])}</div><div class="k">Scale unstable</div></div>
</div>
<h2>Failure rate by slice</h2>
<table><tr><th>Weather</th><th>Time</th><th>Category</th><th>N</th><th>Ghosts</th><th>Kinematic</th><th>Fail %</th></tr>{slice_rows}</table>
<h2>Flagged frames (overlays)</h2>
<div class="gal">{gallery}</div>
<h2>Sample invalid tokens</h2>
<table><tr><th>Token</th><th>Category</th><th>Severity</th><th>Reason</th></tr>{inv_rows}</table>
<h2>Reproduce</h2>
<div class="cmd">pip install kozquloq
kozquloq scan --dataroot &lt;nuScenes-root&gt; --db audit.duckdb
kozquloq export --db audit.duckdb --output mask.parquet
kozquloq viz &lt;sample_token&gt; --dataroot &lt;nuScenes-root&gt;</div>
<p class="foot">Static snapshot. Colors: green = verified, red = ghost (zero LiDAR returns),
amber = kinematic outlier, blue = scale unstable. GPL-3.0.</p>
</div></body></html>"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="data/kozquloq.duckdb")
    p.add_argument("--dataroot", default=None, help="dataset root for overlays")
    p.add_argument("--version", default="v1.0-mini")
    p.add_argument("--out", default="site_out")
    p.add_argument("--max-images", type=int, default=8)
    args = p.parse_args()

    out = Path(args.out)
    img_dir = out / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    names = (
        render_images(args.dataroot, args.version, img_dir, args.max_images)
        if args.dataroot
        else []
    )
    (out / "index.html").write_text(build(args.db, names))
    print(f"site written to {out} ({len(names)} images)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
