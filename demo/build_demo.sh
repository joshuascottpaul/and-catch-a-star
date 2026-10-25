#!/usr/bin/env bash
# Build the demo: Eileen Collins (NASA astronaut, scikit-image's public-domain "astronaut" photo)
# rendered in the words of Donne, as .txt, .png and a coloured multi-font .docx,
# in a white-page and a black-page version.
#
#   bash demo/build_demo.sh
#
# Needs: python3 with pillow numpy "opencv-python-headless<5" rembg onnxruntime, and curl.
# Override the interpreter with PYTHON=/path/to/python. First run downloads the fonts, the photo
# and the rembg model (~176 MB). Downloads are cached in demo/assets/ (git-ignored).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
ASSETS="$HERE/assets"
GF="https://github.com/google/fonts/raw/main/ofl"
mkdir -p "$ASSETS"

fetch() {  # fetch <url> <dest>
  [ -s "$2" ] || { echo "Downloading $(basename "$2")"; curl -fsSL -o "$2" "$1"; }
}

fetch "$GF/inter/Inter%5Bopsz%2Cwght%5D.ttf" "$ASSETS/Inter.ttf"
fetch "$GF/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf" "$ASSETS/PlayfairDisplay.ttf"
fetch "https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.0/skimage/data/astronaut.png" \
      "$ASSETS/eileen_collins.png"

cd "$HERE"
# The .docx argument does not exist: the script falls back to assets/eileen_collins.png beside it.
COMMON=(--face-crop --remove-bg --variable-size
        --fonts "assets/Inter.ttf,assets/PlayfairDisplay.ttf" --font-mix word)

# White page.
"$PYTHON" ../text_portrait.py assets/eileen_collins.docx poem.txt "${COMMON[@]}" \
    --out eileen_collins_portrait
# Black page: light letters on black (--dark), background removed to black.
"$PYTHON" ../text_portrait.py assets/eileen_collins.docx poem.txt "${COMMON[@]}" --dark \
    --out eileen_collins_portrait_dark

echo
echo "Done. Open demo/eileen_collins_portrait.docx and demo/eileen_collins_portrait_dark.docx"
echo "(install Inter and Playfair Display first)."
