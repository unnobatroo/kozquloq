#!/usr/bin/env python3
"""Write a synthetic fixture dataset to disk (auditable via `kozquloq audit`)."""

import argparse

from kozquloq.synthetic import build_synthetic_scene, dump_fixture_dataset


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="data/fixture")
    p.add_argument("--samples", type=int, default=8)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    scene, frames = build_synthetic_scene(n_samples=args.samples, seed=args.seed)
    dump_fixture_dataset(scene, frames, args.out)
    print(f"fixture written to {args.out} — audit it with:")
    print(f"  kozquloq audit --dataroot {args.out}")


if __name__ == "__main__":
    main()
