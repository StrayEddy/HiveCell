#!/usr/bin/env bash
# Prepare the licensed KitBash3D city assets for the "One Night" real-look render
# (HC_REAL=1). These are NOT redistributable and are gitignored (assets/envato/),
# so this script rebuilds them from the Envato Elements .zip downloads.
#
#   1. On elements.envato.com (logged in), download the items listed in
#      docs/envato_assets.md as .zip into ~/Downloads (or pass a dir as $1).
#   2. ./blender/prepare_envato.sh [downloads_dir]
#
# It extracts each kitbash-*.zip into assets/envato/<slug>/ and repoints every
# texture: KitBash blends reference a shared //../../../KB3DTextures/4k/ library
# the Elements download omits (it flattens the textures beside the blend), so
# without this fixup every asset renders magenta.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DL="${1:-$HOME/Downloads}"
ENV="$ROOT/assets/envato"
mkdir -p "$ENV"

shopt -s nullglob
zips=("$DL"/kitbash-*.zip)
[ ${#zips[@]} -gt 0 ] || { echo "no kitbash-*.zip in $DL"; exit 1; }

for z in "${zips[@]}"; do
    slug="$(basename "$z")"; slug="${slug%%-2026-*}"; slug="${slug%.zip}"
    echo "extract: $slug"
    mkdir -p "$ENV/$slug"
    unzip -oq "$z" -d "$ENV/$slug"
done

# repoint textures, per blend, in place
find "$ENV" -maxdepth 3 -name "*.blend" | sort | while read -r b; do
    flatpak run --filesystem="$ROOT" org.blender.Blender \
        --background "$b" --python "$ROOT/blender/envato_fix_textures.py" 2>/dev/null \
        | grep "FIX|" || true
done
echo "envato assets ready in $ENV"
