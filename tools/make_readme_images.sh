#!/usr/bin/env bash
# Build the web-sized README images in docs/images/ from the drawn art
# assets in art/build/assets/. Requires ImageMagick (`convert`).
# Run from the repository root after you re-render the art.
set -euo pipefail

A=art/build/assets
OUT=docs/images
mkdir -p "$OUT"

board() {
  # Both boards share one 4567 x 3197 canvas; drop the empty strip below the frame.
  convert "$A/$1.png" -gravity north -crop 4567x3070+0+0 +repage \
    -resize 1600x -strip -quality 85 "$OUT/$1.jpg"
}

strip() {
  local out=$1; shift
  local files=()
  for name in "$@"; do files+=("$A/$name.png"); done
  convert "${files[@]}" -resize x360 -bordercolor white -border 8 +append \
    -strip -quality 85 "$OUT/$out.jpg"
}

board palace-board
board succession-map
strip equipment-cards card-1-dagger card-2-pilum card-3-helmet \
  card-4-scutum card-5-gladius card-6-armor card-back
strip faction-cards faction-army faction-elites faction-officials \
  faction-empty-1 faction-back
