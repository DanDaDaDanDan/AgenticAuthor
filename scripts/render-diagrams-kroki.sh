#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="docs/diagrams"
SVG_DIR="$SRC_DIR/svg"
PNG_DIR="$SRC_DIR/png"

mkdir -p "$SVG_DIR" "$PNG_DIR"

for f in "$SRC_DIR"/*.mmd; do
  base="$(basename "$f" .mmd)"
  echo "Rendering $base to SVG via Kroki..."
  curl -s -X POST \
    -H 'Content-Type: text/plain' \
    --data-binary @"$f" \
    https://kroki.io/mermaid/svg > "$SVG_DIR/$base.svg"

  echo "Rendering $base to PNG via Kroki..."
  curl -s -X POST \
    -H 'Content-Type: text/plain' \
    --data-binary @"$f" \
    https://kroki.io/mermaid/png > "$PNG_DIR/$base.png"
done

echo "Done. Outputs in $SVG_DIR and $PNG_DIR"

