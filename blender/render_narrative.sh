#!/usr/bin/env bash
# Render the "One Night" narrative cinematic and assemble the review mp4s.
#   ./render_narrative.sh              regenerate greybox (Workbench, HC_DRAFT=1)
#   HC_DRAFT=0 ./render_narrative.sh   regenerate for Cycles
#   HC_REAL=1 ./render_narrative.sh    real look: licensed KitBash city, Cycles
#                                      night (needs blender/prepare_envato.sh first).
#                                      HC_STILL=120,700 renders just those frames;
#                                      HC_SAMPLES=N sets Cycles samples.
#   HC_BLEND=narrative.blend ./render_narrative.sh
#                                      render a HAND-EDITED baked blend as-is
#                                      (no regeneration -- manual edits survive)
# Produces renders/narrative_greybox.mp4 (clean, warm end card burned in) and
# renders/narrative_greybox_labeled.mp4 (shot names burned in, for review).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FPS=24
: "${HC_DRAFT:=1}"
: "${HC_REAL:=0}"
: "${HC_STILL:=}"
: "${HC_SAMPLES:=48}"
: "${HC_BLEND:=}"

rm -f "$ROOT"/renders/narrative/f_*.png
if [ -n "$HC_BLEND" ]; then
    # baked blend already holds the whole scene + frame range + output path
    flatpak run --filesystem="$ROOT" org.blender.Blender \
        --background "$ROOT/blender/$HC_BLEND" --render-anim
else
    HC_DRAFT="$HC_DRAFT" HC_REAL="$HC_REAL" HC_STILL="$HC_STILL" HC_SAMPLES="$HC_SAMPLES" \
        flatpak run --filesystem="$ROOT" org.blender.Blender \
        --background "$ROOT/blender/hivecell.blend" \
        --python "$ROOT/blender/narrative_cinematic.py"
fi

# still-only look-check: the python wrote just those frames, nothing to assemble
if [ -n "$HC_STILL" ]; then
    echo "stills: renders/narrative/f_*.png ($HC_STILL)"
    exit 0
fi

# the one warm end card: clone the last frame for 3s and set the line over it
DUR=$(awk "BEGIN{printf \"%.2f\", $(ls "$ROOT"/renders/narrative/f_*.png | wc -l)/$FPS}")
CARD="tpad=stop_mode=clone:stop_duration=3,drawtext=text='a good night. a clean start.':fontcolor=white@0.9:fontsize=30:x=(w-text_w)/2:y=(h-text_h)/2:enable='gte(t,$DUR)'"

ffmpeg -y -framerate $FPS -i "$ROOT/renders/narrative/f_%04d.png" \
    -vf "$CARD" -c:v libx264 -pix_fmt yuv420p -crf 18 \
    "$ROOT/renders/narrative_greybox.mp4"

# review cut: the two shot names burned in (S1 ends at frame 480 = n 479)
ffmpeg -y -framerate $FPS -i "$ROOT/renders/narrative/f_%04d.png" -vf "\
drawtext=text='S1 the living wall':x=16:y=16:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5:enable='lt(n,480)',\
drawtext=text='S2 the pass':x=16:y=16:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5:enable='gte(n,480)',\
$CARD" \
    -c:v libx264 -pix_fmt yuv420p -crf 18 \
    "$ROOT/renders/narrative_greybox_labeled.mp4"
echo "assembled: renders/narrative_greybox.mp4 (+ labeled)"
