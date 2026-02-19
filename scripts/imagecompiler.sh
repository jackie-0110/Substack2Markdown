#!/bin/bash
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SVG="$ROOT/assets/images/logo.svg"
ICONSET="$ROOT/assets/images/Substack2Markdown.iconset"

  mkdir -p "$ICONSET"

  # macOS iconset — required sizes
  for size in 16 32 128 256 512; do
      rsvg-convert -w $size -h $size "$SVG" -o "$ICONSET/icon_${size}x${size}.png"
      rsvg-convert -w $((size*2)) -h $((size*2)) "$SVG" -o "$ICONSET/icon_${size}x${size}@2x.png"
  done

  # Build .icns
  iconutil -c icns "$ICONSET" -o "$ROOT/assets/images/Substack2Markdown.icns"

  # Build .ico (for Windows builds)
  magick "$SVG" \
      \( -clone 0 -resize 16x16 \) \
      \( -clone 0 -resize 32x32 \) \
      \( -clone 0 -resize 48x48 \) \
      \( -clone 0 -resize 256x256 \) \
      -delete 0 \
      "$ROOT/assets/images/Substack2Markdown.ico"
