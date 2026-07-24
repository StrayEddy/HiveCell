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

# Per-beat HUD text laid out as a vertical panel on the RIGHT of the frame, so the
# centre of the render (the cell, full height) stays clear. Lines are pre-wrapped
# with '|' since ffmpeg drawtext does not wrap; each field is one panel line.
# (No ':' or ',' — they are ffmpeg drawtext metacharacters.)
declare -A TITLE STAT BODY TCOL
TITLE[clear]="CLEARING SWEEP|pod proven empty"
STAT[clear]="SF1 life detection  ·  clear"
BODY[clear]="the piston sweeps loose|items out the mouth —|they fall clear"
TCOL[clear]="0x8CE0A0"                        # green: safe / ready
TITLE[locked]="SOMEONE INSIDE|motion LOCKED"
STAT[locked]="SF1 life detection  ·  DETECTED"
BODY[locked]="the machine holds still|and alerts a human —|it never pushes"
TCOL[locked]="0xFF7A6E"                        # red: life present
TITLE[intrude]="INTRUSION MID-SWEEP|STOP & REVERSE"
STAT[intrude]="SF2 force cap + SF1 trip|sweep aborted"
BODY[intrude]="the piston backs out|to the safe deployed pose"
TCOL[intrude]="0xFF7A6E"

encode_beat () {                              # $1 = beat name
  local b="$1" frames="$ROOT/renders/beats/$1" seg="$ROOT/renders/beats/$1.mp4"
  local pw=356                                # right-panel width (px)
  local tx="W-$((pw-28))"                     # text left edge (28px panel padding)
  local y=132                                 # top padding of the text block
  local line
  # upscale the half-res Cycles frames to the 960x540 output, then draw the HUD at full
  # size so the burned-in text stays crisp; a translucent right panel + accent rule.
  local vf="scale=960:540:flags=lanczos"
  vf+=",drawbox=x=iw-${pw}:y=0:w=${pw}:h=ih:color=black@0.55:t=fill"
  vf+=",drawbox=x=iw-${pw}:y=0:w=3:h=ih:color=${TCOL[$b]}@0.85:t=fill"
  local IFS='|'
  for line in ${TITLE[$b]}; do               # title block — bold, beat colour
    vf+=",drawtext=fontfile=${FONTB}:text='${line}':x=${tx}:y=${y}:fontsize=24:fontcolor=${TCOL[$b]}"
    y=$((y+35))
  done
  y=$((y+18))
  for line in ${STAT[$b]}; do                 # status block — bright grey
    vf+=",drawtext=fontfile=${FONT}:text='${line}':x=${tx}:y=${y}:fontsize=18:fontcolor=0xD2DAE4"
    y=$((y+27))
  done
  y=$((y+14))
  for line in ${BODY[$b]}; do                 # explanatory body — dim grey
    vf+=",drawtext=fontfile=${FONT}:text='${line}':x=${tx}:y=${y}:fontsize=18:fontcolor=0xAEB8C4"
    y=$((y+27))
  done
  ffmpeg -y -framerate $FPS -i "$frames/f_%04d.png" -vf "$vf" \
      -c:v libx264 -pix_fmt yuv420p -crf 18 "$seg" >/dev/null 2>&1
  echo "  encoded $seg"
}

for b in "${BEATS[@]}"; do
  if [ "${SKIP_RENDER:-0}" != "1" ]; then
    echo "rendering beat: $b"
    rm -f "$ROOT/renders/beats/$b"/*.png
    HC_BEAT="$b" HC_DRAFT="$DRAFT" HC_LOWRES="${HC_LOWRES:-1}" HC_SAMPLES="${HC_SAMPLES:-24}" \
        HC_NIGHT="${HC_NIGHT:-1}" \
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
