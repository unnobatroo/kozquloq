import { Charts } from "@/components/Charts";
import { Gallery } from "@/components/Gallery";
import { Gauge } from "@/components/Gauge";
import { SliceTable } from "@/components/SliceTable";
import { loadReport } from "@/lib/data";

export default async function Page() {
  const report = await loadReport();
  const { health: h } = report;
  const generated = new Date(report.generated_at).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  });

  return (
    <div className="wrap">
      <header className="top">
        <div>
          <div className="logo">
            Kozquloq<span>.</span>
          </div>
          <div className="tagline">A health check for your self-driving training data</div>
        </div>
        <div className="stamp">audited {generated}</div>
      </header>

      <section className="hero">
        <Gauge failurePct={h.failure_pct} grade={h.grade} />
        <div>
          <p className="verdict">{report.verdict}</p>
          <div className="stats">
            <div className="stat">
              <div className="n">{h.frames.toLocaleString()}</div>
              <div className="l">frames checked</div>
            </div>
            <div className="stat">
              <div className="n">{h.annotations.toLocaleString()}</div>
              <div className="l">labels inspected</div>
            </div>
            <div className="stat">
              <div className="n" style={{ color: "var(--bad)" }}>
                {h.flagged.toLocaleString()}
              </div>
              <div className="l">look broken ({h.failure_pct}%)</div>
            </div>
          </div>
        </div>
      </section>

      <h2>What&apos;s wrong</h2>
      <p className="hint">The problems we found, in plain terms.</p>
      <div className="findings">
        {report.findings.map((f) => (
          <div key={f.kind} className={`finding ${f.count < 50 ? "warn" : ""}`}>
            <h3>{f.title}</h3>
            <div className="count">{f.count.toLocaleString()}</div>
            <div className="detail">{f.detail}</div>
            <div className="why">
              <b>Why it matters:</b> {f.why}
            </div>
          </div>
        ))}
        {report.findings.length === 0 && (
          <div className="finding" style={{ borderLeftColor: "var(--good)" }}>
            <h3>All clear</h3>
            <div className="detail">Nothing flagged — this dataset looks good to train on.</div>
          </div>
        )}
      </div>

      <h2>Where the problems are</h2>
      <p className="hint">Hover the bars for exact numbers.</p>
      <Charts charts={report.charts} />

      <h2>By the numbers</h2>
      <p className="hint">Every breakdown of the data — weather, time of day, object type.</p>
      <SliceTable rows={report.slices} />

      {report.gallery.length > 0 && (
        <>
          <h2>See for yourself</h2>
          <p className="hint">
            The worst frames, straight from the dataset. Switch views, click to zoom.
          </p>
          <Gallery items={report.gallery} />
        </>
      )}

      <h2>Reading the pictures</h2>
      <div className="legend">
        <span>
          <i style={{ background: "#00ff00" }} /> label checks out
        </span>
        <span>
          <i style={{ background: "#ff0000" }} /> phantom — lidar saw nothing there
        </span>
        <span>
          <i style={{ background: "#ffa500" }} /> moved too fast to be real
        </span>
        <span>
          <i style={{ background: "#0080ff" }} /> changed size between frames
        </span>
      </div>

      {report.diagnostics && (
        <>
          <h2>Diagnostics</h2>
          <div className="diag">{report.diagnostics}</div>
        </>
      )}

      <footer>
        Kozquloq audits lidar boxes, motion, and camera frames before they reach your
        training pipeline. Rebuilt every audit.
      </footer>
    </div>
  );
}
