#!/usr/bin/env python3
"""Download nuScenes v1.0-mini.

The mini split is distributed from nuscenes.org behind a login form; this
script tries a direct URL and prints manual instructions on failure.
"""

import argparse
import tarfile
import urllib.request
from pathlib import Path

URL = "https://d36yt3mvayqw5m.cloudfront.net/public/v1.0/v1.0-mini.tgz"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="data/nuscenes", help="dataset root")
    p.add_argument("--url", default=URL)
    args = p.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tgz = out / "v1.0-mini.tgz"

    if not (out / "v1.0-mini").exists():
        try:
            print(f"downloading {args.url} -> {tgz}")
            urllib.request.urlretrieve(args.url, tgz)
        except Exception as e:
            print(f"download failed: {e}")
            print(
                "nuScenes requires a free account: register at "
                "https://www.nuscenes.org/download, download 'v1.0-mini', "
                f"and extract it into {out}"
            )
            raise SystemExit(1) from e
        print("extracting...")
        with tarfile.open(tgz) as tar:
            tar.extractall(out, filter="data")
        tgz.unlink()
    print(f"done — use: kozquloq audit --dataroot {out} --version v1.0-mini")


if __name__ == "__main__":
    main()
