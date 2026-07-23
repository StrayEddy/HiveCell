#!/usr/bin/env bash
# Render the 3-beat HiveCell scenario cinematic and assemble renders/cinematic.mp4.
#
# For each beat it runs scenario_cinematic.py headless (EEVEE quality), encodes the
# PNG sequence to a segment with a burned-in HUD (scenario title + status, echoing
# the Godot twin), then concatenates the segments. This Flatpak Blender has no
# FFmpeg output, so the system ffmpeg does the encode + overlay + concat.
#
#   bash blender/render_cinematic.sh            # render everything, then assemble
#   SKIP_RENDER=1 bash blender/render_cinematic.sh   # re-encode titles only (fast)
#   HC_DRAFT=1 bash blender/render_cinematic.sh  # Workbench draft (motion check)
set -euo pipefail

ROOT="/home/eddy/Projects/HiveCell"
FONT="/usr/share/fonts/TTF/DejaVuSans.ttf"
FONTB="/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
FPS=24
DRAFT="${HC_DRAFT:-0}"
BEATS=(clear locked intrude)

# Per-beat HUD text (no ':' or ',' — they are ffmpeg drawtext metacharacters).
declare -A TITLE STAT1 STAT2 TCOL
TITLE[clear]="CLEARING SWEEP  —  pod proven empty"
STAT1[clear]="SF1 life detection  ·  clear"
STAT2[clear]="the piston sweeps loose items out the mouth — they fall clear"
TCOL[clear]="0x8CE0A0"                       # green: safe / ready
TITLE[locked]="SOMEONE INSIDE  —  motion LOCKED"
STAT1[locked]="SF1 life detection  ·  DETECTED"
STAT2[locked]="the machine holds still and alerts a human — it never pushes"
TCOL[locked]="0xFF7A6E"                       # red: life present
TITLE[intrude]="INTRUSION MID-SWEEP  —  STOP & REVERSE"
STAT1[intrude]="SF2 force cap + SF1 trip  ·  sweep aborted"
STAT2[intrude]="the piston backs out to the safe deployed pose"
TCOL[intrude]="0xFF7A6E"

encode_beat () {                              # $1 = beat name
  local b="$1" frames="$ROOT/renders/beats/$1" seg="$ROOT/renders/beats/$1.mp4"
  local band=118
  local vf="drawbox=x=0:y=0:w=iw:h=${band}:color=black@0.5:t=fill"
  vf+=",drawtext=fontfile=${FONTB}:text='${TITLE[$b]}':x=30:y=24:fontsize=30:fontcolor=${TCOL[$b]}"
  vf+=",drawtext=fontfile=${FONT}:text='${STAT1[$b]}':x=30:y=66:fontsize=19:fontcolor=0xD2DAE4"
  vf+=",drawtext=fontfile=${FONT}:text='${STAT2[$b]}':x=30:y=90:fontsize=19:fontcolor=0xAEB8C4"
  ffmpeg -y -framerate $FPS -i "$frames/f_%04d.png" -vf "$vf" \
      -c:v libx264 -pix_fmt yuv420p -crf 18 "$seg" >/dev/null 2>&1
  echo "  encoded $seg"
}

for b in "${BEATS[@]}"; do
  if [ "${SKIP_RENDER:-0}" != "1" ]; then
    echo "rendering beat: $b"
    rm -f "$ROOT/renders/beats/$b"/*.png
    HC_BEAT="$b" HC_DRAFT="$DRAFT" HC_LOWRES="${HC_LOWRES:-0}" HC_SAMPLES="${HC_SAMPLES:-4}" \
        flatpak run --filesystem="$ROOT" \
        org.blender.Blender --background "$ROOT/blender/hivecell.blend" \
        --python "$ROOT/blender/scenario_cinematic.py" >/dev/null 2>&1
  fi
  echo "encoding beat: $b"
  encode_beat "$b"
done

# concat the segments
LIST="$ROOT/renders/beats/concat.txt"
: > "$LIST"
for b in "${BEATS[@]}"; do echo "file '$ROOT/renders/beats/$b.mp4'" >> "$LIST"; done
ffmpeg -y -f concat -safe 0 -i "$LIST" -c copy "$ROOT/renders/cinematic.mp4" >/dev/null 2>&1
echo "assembled $ROOT/renders/cinematic.mp4"
