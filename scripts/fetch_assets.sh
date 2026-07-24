#!/usr/bin/env bash
# Fetch external render assets not committed to the repo (large binaries).
# CC0 HDRIs (Poly Haven) used by blender/build_scene.py + scenario_cinematic.py:
#   - studio HDRI       -> the bright product ("studio") look, stainless reflections
#   - night-street HDRI -> the night look: streetlamp spill + reflections on the
#                          exterior so it isn't dead-black (interior luminaire stays hero)
# Both are optional: the builds fall back to a flat/gradient world if missing, so
# this is recommended-but-not-required for hero renders.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/2k"

fetch() {                                   # $1 = dest path, $2 = Poly Haven slug
  local dest="$1" slug="$2"
  if [[ -f "$dest" ]]; then
    echo "fetch_assets: present ($dest)"
    return
  fi
  mkdir -p "$(dirname "$dest")"
  echo "fetch_assets: downloading $slug (CC0, Poly Haven)..."
  curl -sSL -o "$dest" "$BASE/${slug}_2k.hdr"
  echo "fetch_assets: saved $dest"
}

fetch "$ROOT/blender/hdri/studio.hdr"       "brown_photostudio_02"
fetch "$ROOT/blender/hdri/night_street.hdr" "dresden_station_night"
