#!/usr/bin/env bash
# Download + unpack the CC0 cast assets for the narrative cinematic:
#   Quaternius Universal Base Characters  (rigged bodies)
#   Quaternius Universal Animation Library (clips, same 65-bone rig)
# Both are free CC0 packs on itch.io; no account is needed -- the flow below is
# the same "No thanks, just take me to the downloads" path the browser takes.
# Run once; narrative_cinematic.py expects the packs under assets/quaternius/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/assets/quaternius"
mkdir -p "$DEST"

fetch_itch() { # <project-url> <out.zip>
    local page=$1 out=$2 jar csrf dl id url
    jar=$(mktemp)
    csrf=$(curl -sc "$jar" "$page" | grep -o 'csrf_token" value="[^"]*"' \
        | head -1 | sed 's/csrf_token" value="//;s/"$//')
    dl=$(curl -sb "$jar" -X POST "$page/download_url" \
        --data-urlencode "csrf_token=$csrf" | python3 -c 'import json,sys;print(json.load(sys.stdin)["url"])')
    id=$(curl -sb "$jar" "$dl" | grep -o 'data-upload_id="[0-9]*"' | head -1 | grep -o '[0-9]*')
    url=$(curl -sb "$jar" -X POST "$page/file/$id?source=game_download" \
        --data-urlencode "csrf_token=$csrf" | python3 -c 'import json,sys;print(json.load(sys.stdin)["url"])')
    curl -L "$url" -o "$out"
    rm -f "$jar"
}

[ -f "$DEST/UniversalBaseCharacters_Standard.zip" ] || \
    fetch_itch https://quaternius.itch.io/universal-base-characters \
               "$DEST/UniversalBaseCharacters_Standard.zip"
[ -f "$DEST/UniversalAnimationLibrary_Standard.zip" ] || \
    fetch_itch https://quaternius.itch.io/universal-animation-library \
               "$DEST/UniversalAnimationLibrary_Standard.zip"
unzip -oq "$DEST/UniversalBaseCharacters_Standard.zip" -d "$DEST"
unzip -oq "$DEST/UniversalAnimationLibrary_Standard.zip" -d "$DEST"
echo "cast assets ready in $DEST"
