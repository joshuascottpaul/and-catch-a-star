# and-catch-a-star

Turn a photo and a text file into a portrait made of the text.
The text is laid down in reading order, so a poem can still be read left to right, top to bottom, through the picture.

Named for Donne: *Go and catch a falling star.*

## Outputs

| File | What it is |
|------|------------|
| `<out>.txt` | Plain ASCII art. Blank is light, lowercase is mid, UPPERCASE is dark. |
| `<out>.png` | Typographic portrait. Each letter is inked, and optionally sized, weighted and font-picked, by the image under it. |
| `<out>.docx` | Word export of the PNG layout (`--docx`). Live, editable text. Every letter keeps its own colour, font and size. |

Samples are in [`docs/samples`](docs/samples).

## Install

```
pip install pillow numpy
```

Optional, per feature:

```
pip install "opencv-python-headless<5"  # --face-crop (OpenCV 5 removed the face detector)
pip install rembg onnxruntime         # --remove-bg (downloads a ~176 MB model on first use)
```

Python 3.9 or newer. The `.docx` writer uses only the standard library (`zipfile`), so it adds no dependency.

## Use

Basic:

```
python3 text_portrait.py donne.jpg poem.txt
```

Everything on, with a Word file:

```
python3 text_portrait.py donne.docx poem.txt --face-crop --remove-bg \
    --variable-size --fonts "Inter.ttf,PlayfairDisplay.ttf" --font-mix word
```

### The `.docx` format

The Word export is built for the coloured, multi-font, variable-size output.

- Colour is always on in the Word file. `--docx` turns on `--color` for you.
- Each row is one paragraph. Each letter is a run with its own font family, size, colour and bold.
- Neighbouring letters with identical formatting are merged into one run, to keep the file small.
- In grid mode, letter spacing is padded so every letter sits in its cell.
- Rows use exact line spacing, so the layout matches the PNG. Word may clip the tops of the biggest letters in `--variable-size` portraits. `--docx-lines atleast` never clips, but rows grow and the portrait stretches taller. LibreOffice shows exact spacing unclipped.
- Rows never wrap (negative right indent), even if Word's letter widths differ from Pillow's.
- The page is sized to fit the portrait. With `--dark` the page background is black.
- Fonts are **not embedded**. The reader needs the fonts installed, or Word substitutes them. A variable font shows under its family name (for example `Inter`).

Ways to ask for it:

1. `--docx` writes `<out>.docx` beside the `.txt` and `.png`.
2. `--out name.docx` does the same, with the base name `name`.
3. Give a `.docx` as the image argument. If that file exists, its largest embedded picture is the source. If it does not exist, a sibling image with the same name (`donne.jpg`, `.png`, ...) is used.

### Options

| Group | Option | Meaning |
|-------|--------|---------|
| output | `--out` | Output base name. Default `<image>_portrait`. |
| output | `--docx`, `--docx-lines` | Also write a Word file. Line spacing `exact` (default) or `atleast`. |
| output | `--width` | TXT columns. Default 120. |
| output | `--png-width` | PNG columns. Default 1.5 x `--width`. |
| image | `--face-crop`, `--crop-pad` | Crop to the face. Pad 0.5 tight to 2 loose. |
| image | `--remove-bg`, `--bg-model` | Remove the background. Models: `u2net`, `u2netp`, `isnet-general-use`. |
| image | `--contrast`, `--equalize`, `--no-sharpen`, `--invert` | Tone controls. |
| text | `--keep-spaces`, `--unicode` | Keep spaces or curly quotes. |
| txt | `--threshold`, `--no-case`, `--dither` | ASCII shading controls. |
| png | `--fonts`, `--font-mix` | Font files, comma separated. Mix by `tone`, `word` or `random`. |
| png | `--no-weight` | Do not drive variable-font weight by darkness. |
| png | `--font-size`, `--tracking`, `--bold`, `--ghost` | Type controls. |
| png | `--variable-size`, `--min-size`, `--max-size`, `--line-height` | Letters grow in darks and shrink in lights. |
| png | `--color`, `--dark` | Colour letters from the photo. Light letters on black. |

Run `python3 text_portrait.py --help` for defaults.

## Notes

- The face detector is trained on photos. It may miss an engraving. Crop by hand and skip `--face-crop` if it does.
- Variable fonts with a Weight axis are detected automatically.
- Google Fonts variable fonts work well. Tested: Inter, JetBrains Mono, Playfair Display.

## Tests

```
python3 -m unittest discover -s tests
```

## Design

See [`docs/SDD.md`](docs/SDD.md).

## License

[MIT](LICENSE)
