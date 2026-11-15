#!/bin/sh
# Builds index.html and site/index.html from code-racer.html (the artifact-format source).
set -e
cd "$(dirname "$0")"
node tests/verify_tracks.mjs --no-run
{
  printf '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
  printf '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
  printf '<meta name="description" content="Code Racer: type Python, C or Java line by line to drive your car. 30 tracks in 3 worlds, real compilers, combos and a ghost car.">\n'
  printf '<meta name="theme-color" content="#0A0E13">\n'
  printf '<link rel="icon" href="data:image/svg+xml,%%3Csvg xmlns=%%27http://www.w3.org/2000/svg%%27 viewBox=%%270 0 64 64%%27%%3E%%3Crect width=%%2764%%27 height=%%2764%%27 rx=%%2714%%27 fill=%%27%%230A0E13%%27/%%3E%%3Cpath d=%%27M8 40 L12 30 Q20 18 34 18 Q44 18 50 28 L58 32 L58 42 Z%%27 fill=%%27%%23FF9F35%%27/%%3E%%3Ccircle cx=%%2720%%27 cy=%%2742%%27 r=%%276%%27 fill=%%27%%23fff%%27/%%3E%%3Ccircle cx=%%2746%%27 cy=%%2742%%27 r=%%276%%27 fill=%%27%%23fff%%27/%%3E%%3C/svg%%3E">\n'
  awk '/<\/style>/{print; print "</head>"; print "<body>"; next} {print}' code-racer.html
  printf '</body>\n</html>\n'
} > index.html
mkdir -p site && cp index.html site/index.html
echo "built index.html ($(wc -c < index.html) bytes)"
