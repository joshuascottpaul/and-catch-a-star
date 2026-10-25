# Software Design Document: text_portrait

Status: BUILT (single script, `text_portrait.py`).

## 1. Purpose

Render an image as a portrait made of the words of a text file.
The text keeps reading order, so the poem stays legible through the picture.

## 2. Scope

In scope: one command-line script, three output formats (`.txt`, `.png`, `.docx`).
Out of scope: a GUI, font embedding in Word, any network service.

## 3. Constraints

1. Single file, no package.
2. Required dependencies: Pillow, NumPy.
3. Optional dependencies, imported lazily inside the feature that needs them: OpenCV (`--face-crop`), rembg and onnxruntime (`--remove-bg`).
4. The `.docx` writer uses only the standard library.
5. Every new feature is off by default. The default output must not change.

## 4. Architecture

One pipeline, three renderers.

```
text file --> load_text --> text_stream (char, word_index) forever
image     --> open_source_image --> load_image (face crop, bg removal, tone prep)
                                         |
                    +--------------------+---------------------+
                    v                    v                     v
                make_txt            make_png_grid         make_png_flow
                (.txt)              (.png, fixed cells)   (.png, variable size)
                                         |                     |
                                         +----- rec (layout) --+--> write_docx (.docx)
```

### 4.1 Text (`load_text`, `text_stream`)

Smart punctuation is folded to ASCII unless `--unicode`. Whitespace collapses to single spaces, kept internally to know word boundaries.
`text_stream` yields `(char, word_index)` forever, so the poem repeats to fill any image.

### 4.2 Image prep (`open_source_image`, `face_crop`, `remove_bg`, `load_image`)

1. `open_source_image` opens an image. For a `.docx` it takes the largest picture under `word/media/`. If that `.docx` is missing, it falls back to a same-named sibling image.
2. EXIF orientation is applied. Transparency is flattened onto white.
3. `face_crop` runs Haar cascades (frontal, alt2, profile) and crops head and shoulders. No face means the full image is used.
4. `remove_bg` composites a rembg cut-out onto white, or black with `--dark`.
5. Autocontrast, optional equalise blend, optional unsharp mask, contrast.

### 4.3 TXT renderer (`make_txt`)

Greyscale is thresholded (Otsu by default) into 2 or 3 levels: blank, lowercase, UPPERCASE. Optional Floyd-Steinberg dither.

### 4.4 Fonts (`FontSet`)

Holds one or more font files. `pick` chooses a font by tone (light to heavy), by word (round robin) or randomly per word (stable per word, seeded).
Variable fonts with a Weight axis are detected, and weight is driven by ink in 9 steps. Instances are cached by `(font, size, weight step)`.
`FontSet.last` records `(font index, weight step)` of the latest `get`, so renderers can log what they drew.

### 4.5 PNG renderers

Both draw at 2x supersampling and downscale with Lanczos.

- `make_png_grid`: fixed cell grid. Each cell holds one letter. Letter ink and colour come from the pixel under the cell.
- `make_png_flow` (`--variable-size`): letters flow like typeset text along fixed rows. Each letter's size comes from a blurred darkness map under it. A letter that does not fit is carried to the next row, so nothing is dropped.

### 4.6 Layout record and DOCX export (`rec`, `write_docx`)

Each PNG renderer takes an optional `rec` dict. When given, it appends one list per row of tuples:

```
(char, font_index, size_px, fill_rgb, ink, extra_spacing_px)
```

and sets `width`, `pitch` (row height) and `ss` (supersample factor). Sizes are in supersampled pixels.

`write_docx` turns the record into a minimal OOXML package with `zipfile`:

| Part | Content |
|------|---------|
| `[Content_Types].xml`, `_rels/.rels`, `word/_rels/document.xml.rels` | Package plumbing |
| `word/document.xml` | One `w:p` per row, line height = row pitch (`exact` or `atLeast`), negative right indent so a row never wraps. One `w:r` per run of identically formatted letters. |
| `word/settings.xml` | `displayBackgroundShape` (so the black `--dark` page shows), `hideSpellingErrors`, `hideGrammaticalErrors`, and `compatibilityMode` 15 (no "Compatibility Mode" banner) |

Run properties: `rFonts`, `noProof` (no proofing squiggles) (family from the font file's name table), `b` (when ink >= 0.7 and `--bold` is on), `color` (from the photo), `spacing` (grid cell padding or tracking), `sz`.

Unit mapping: 1 px = 0.75 pt. The page is sized to the portrait, plus 4% width slack and about 4% height slack, because Word's metrics differ from Pillow's and Word rows ran a little taller (the last row spilled to a second page before the height slack). If the portrait would exceed Word's page limit (22 in), all sizes are scaled down together.

Design decisions:

1. **Hand-built OOXML, not python-docx.** Keeps the stdlib-only promise for the writer and adds no dependency.
2. **Record the layout, do not re-derive it.** One source of truth: the PNG and the DOCX cannot drift apart.
3. **DOCX is always coloured.** The format exists for the coloured multi-font output. `--docx` therefore turns on `--color`.
4. **Fonts are referenced, not embedded.** Embedding needs obfuscated font parts and licence checks. Documented as a limit instead.
5. **A `.docx` is accepted as the input argument.** It selects DOCX output and supplies its embedded picture, or falls back to a sibling image.

## 5. CLI

Defined in `main()` with `argparse`, grouped as output, image prep, text, txt output, png output. `--out name.docx` and a `.docx` input both switch on `--docx`. Full table in the README.

## 6. Error handling

Missing optional dependency, missing font, empty text and a missing source image exit with a one-line `SystemExit` message that names the fix.

## 7. Testing

`tests/test_text_portrait.py` (stdlib `unittest`, skipped when Pillow or NumPy is missing):

1. DOCX package is a valid zip with well-formed XML parts.
2. Runs carry the expected colour, font family and size.
3. A `.docx` input yields its embedded picture.
4. A missing `.docx` falls back to the sibling image.
5. `--out x.docx` writes `x.docx`.

Face crop and background removal are checked by hand, because they need heavy optional models.

## 8. Demo

`demo/build_demo.sh` is the reproducible demo build. It downloads the photo (scikit-image `astronaut`, public domain) and two OFL fonts into git-ignored `demo/assets/`, then runs the full command with a `.docx` image argument that resolves through the sibling-image fallback. Committed inputs: `demo/poem.txt`. Committed outputs: `demo/eileen_collins_portrait.*`.

## 9. Known limits and next steps

1. Fonts are not embedded in the DOCX. A reader without the fonts sees substitutes.
2. Exact line spacing (default) keeps the PNG proportions but Word may clip the tops of big letters. LibreOffice does not clip. `--docx-lines atleast` never clips but stretches the portrait taller (rows cannot overlap). Next step: open a variable-size sample in Word; if the clipping is bad, consider per-run `position` offsets instead of overlap.
3. Face detection is weak on engravings.
4. `--face-crop` needs OpenCV below 5: version 5 removed `CascadeClassifier`. The script exits with the install command if it finds 5.x.
