"use client";

import { useCallback, useEffect, useState } from "react";
import type { GalleryItem } from "@/lib/report";

type Variant = "full" | "boxes" | "flagged";

const VARIANT_LABEL: Record<Variant, string> = {
  full: "lidar overlay",
  boxes: "labels only",
  flagged: "just the problems",
};

function src(item: GalleryItem, v: Variant) {
  const val = item.images[v] ?? item.images.full ?? item.images.boxes ?? "";
  if (!val) return "";
  // Values are either asset paths ("assets/x.jpg") or inline base64.
  if (val.startsWith("data:") || val.startsWith("http")) return val;
  if (val.startsWith("assets/")) return `/${val}`;
  return `data:image/jpeg;base64,${val}`;
}

export function Gallery({ items }: { items: GalleryItem[] }) {
  const [variant, setVariant] = useState<Variant>("full");
  const [open, setOpen] = useState<number | null>(null);

  const move = useCallback(
    (d: number) =>
      setOpen((i) => (i === null ? null : (i + d + items.length) % items.length)),
    [items.length],
  );

  useEffect(() => {
    if (open === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(null);
      if (e.key === "ArrowRight") move(1);
      if (e.key === "ArrowLeft") move(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, move]);

  return (
    <>
      <div className="gal-tools">
        {(Object.keys(VARIANT_LABEL) as Variant[]).map((v) => (
          <button
            key={v}
            className={variant === v ? "on" : ""}
            onClick={() => setVariant(v)}
          >
            {VARIANT_LABEL[v]}
          </button>
        ))}
      </div>

      <div className="gallery">
        {items.map((g, i) => (
          <figure key={g.sample_token}>
            <img
              src={src(g, variant)}
              alt={`Frame ${g.sample_token} — ${VARIANT_LABEL[variant]}`}
              loading="lazy"
              onClick={() => setOpen(i)}
            />
            <figcaption>
              <div className="plain">{g.plain}</div>
              <div className="meta">{g.caption}</div>
            </figcaption>
          </figure>
        ))}
      </div>

      {open !== null && items[open] && (
        <div className="lightbox" onClick={() => setOpen(null)}>
          <span className="x">×</span>
          <img
            src={src(items[open], variant)}
            alt={items[open].sample_token}
            onClick={(e) => e.stopPropagation()}
          />
          <div className="cap" onClick={(e) => e.stopPropagation()}>
            {items[open].plain}
          </div>
          <div className="lb-row" onClick={(e) => e.stopPropagation()}>
            <button className="lb-btn" onClick={() => move(-1)}>← prev</button>
            <span className="kbd">
              {open + 1} / {items.length} · esc to close
            </span>
            <button className="lb-btn" onClick={() => move(1)}>next →</button>
          </div>
        </div>
      )}
    </>
  );
}
