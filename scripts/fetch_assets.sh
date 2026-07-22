#!/usr/bin/env bash
# Fetch external render assets not committed to the repo (large binaries).
# Currently: a CC0 studio HDRI (Poly Haven) used by blender/build_scene.py for
# realistic stainless reflections. If it is missing, the build falls back to a
# procedural gradient world, so this is optional but recommended for hero renders.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HDRI="$ROOT/blender/hdri/studio.hdr"
URL="https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/2k/brown_photostudio_02_2k.hdr"

if [[ -f "$HDRI" ]]; then
  echo "fetch_assets: HDRI already present ($HDRI)"
  exit 0
fi
mkdir -p "$(dirname "$HDRI")"
echo "fetch_assets: downloading studio HDRI (CC0, Poly Haven)..."
curl -sSL -o "$HDRI" "$URL"
echo "fetch_assets: saved $HDRI"
