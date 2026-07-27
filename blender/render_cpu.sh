#!/usr/bin/env bash
# Render the "One Night" cinematic on CPU with texture-limit + persistent-data
# speedups baked in (see _render_cpu.py), then assemble a real-time-paced mp4.
#   ./render_cpu.sh                1fps    (HC_FSTEP=24, default)
#   HC_FSTEP=12 ./render_cpu.sh    2fps
#   HC_FSTEP=96 ./render_cpu.sh    0.25fps
#   HC_TEXLIMIT=2048 ./render_cpu.sh   softer texture clamp for 2K+ output
#   HC_TEXLIMIT=OFF  ./render_cpu.sh   no clamp (slow, full RAM)
#   HC_SAMPLES=64 ./render_cpu.sh      override the blend's spp (it is often
#                                      saved low, ~4, for viewport speed)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${HC_FSTEP:=24}"
: "${HC_TEXLIMIT:=1024}"
FPS=24
OUT="$ROOT/renders/narrative"

HC_FSTEP="$HC_FSTEP" HC_TEXLIMIT="$HC_TEXLIMIT" \
HC_PCT="${HC_PCT:-100}" HC_SAMPLES="${HC_SAMPLES:-}" \
    blender --background --factory-startup --python "$ROOT/blender/_render_cpu.py"

# pace playback: each rendered frame fills its HC_FSTEP-frame slot => real-time.
IN_FPS=$(awk "BEGIN{printf \"%.6f\", $FPS/$HC_FSTEP}")
DUR=$(awk "BEGIN{printf \"%.2f\", $(ls "$OUT"/f_*.png | wc -l)/$IN_FPS}")
CARD="scale=trunc(iw/2)*2:trunc(ih/2)*2,tpad=stop_mode=clone:stop_duration=3,drawtext=text='a good night. a clean start.':fontcolor=white@0.9:fontsize=34:x=(w-text_w)/2:y=(h-text_h)/2:enable='gte(t,$DUR)'"

ffmpeg -y -framerate "$IN_FPS" -pattern_type glob -i "$OUT/f_*.png" \
    -r $FPS -vf "$CARD" -c:v libx264 -pix_fmt yuv420p -crf 16 \
    "$ROOT/renders/narrative_cpu.mp4"
echo "assembled: renders/narrative_cpu.mp4  (step=${HC_FSTEP}, texlimit=${HC_TEXLIMIT})"
