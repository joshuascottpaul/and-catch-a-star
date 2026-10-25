#!/usr/bin/env python3
"""
text_portrait.py - render an image as ASCII art built from the words of a text file.

The text is laid down in reading order, so the poem can still be read
left-to-right, top-to-bottom through the picture.

Outputs:
  <out>.txt  plain ASCII art. Blank = light, lowercase = mid, UPPERCASE = dark.
  <out>.png  typographic portrait: every letter inked (and optionally sized,
             weighted and font-picked) by the image underneath. Best likeness.
  <out>.docx Word export of the PNG layout (--docx): live, editable text where
             every letter keeps its own colour, size and font. Always coloured.

Basic:
  python3 text_portrait.py donne.jpg poem.txt

Word export (input may also be a .docx; its largest embedded picture is used):
  python3 text_portrait.py donne.docx poem.txt --face-crop --remove-bg \
      --variable-size --fonts "Inter.ttf,PlayfairDisplay.ttf" --font-mix word

Everything on:
  python3 text_portrait.py donne.jpg poem.txt --face-crop --remove-bg \
      --variable-size --fonts "Inter.ttf,PlayfairDisplay.ttf" --font-mix word

Requires:  pip install pillow numpy
Optional:  pip install opencv-python-headless   (--face-crop)
           pip install rembg onnxruntime          (--remove-bg, downloads a model on first use)
"""
import argparse
import random
import re
import unicodedata
import zipfile
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

MONO_FONTS = [
    ("/System/Library/Fonts/Menlo.ttc", 1),                        # macOS (bold face)
    ("/System/Library/Fonts/SFNSMono.ttf", 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 0),    # Linux
    ("/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf", 0),
    ("C:/Windows/Fonts/consolab.ttf", 0),                          # Windows
    ("C:/Windows/Fonts/consola.ttf", 0),
]
SMART = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
         "\u2013": "-", "\u2014": "-", "\u2026": "..."}
TXT_ASPECT = 0.5  # text editors/terminals: a character is ~2x taller than wide


# ---------------------------------------------------------------- text

def load_text(path, unicode_ok):
    raw = Path(path).read_text(encoding="utf-8", errors="ignore")
    if not unicode_ok:
        raw = "".join(SMART.get(c, c) for c in raw)
        raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    text = re.sub(r"\s+", " ", raw).strip()   # spaces kept internally to know word boundaries
    if not text.replace(" ", ""):
        raise SystemExit("Text file has no usable characters.")
    return text


def text_stream(text, keep_spaces):
    """Yields (char, word_index) forever, in reading order."""
    word = 0
    while True:
        for c in text + " ":
            if c == " ":
                word += 1
                if not keep_spaces:
                    continue
            yield c, word


# ---------------------------------------------------------------- image

def face_crop(img, pad):
    try:
        import cv2
    except ImportError:
        raise SystemExit("--face-crop needs:  pip install opencv-python-headless")
    gray = np.asarray(ImageOps.grayscale(img))
    m = min(gray.shape)
    faces = []
    for name in ("haarcascade_frontalface_default.xml", "haarcascade_frontalface_alt2.xml",
                 "haarcascade_profileface.xml"):
        det = cv2.CascadeClassifier(cv2.data.haarcascades + name)
        faces = det.detectMultiScale(gray, 1.1, 5, minSize=(m // 12, m // 12))
        if len(faces):
            break
    if not len(faces):
        print("Face crop: no face found (common with stylised engravings) - using full image.")
        return img
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    cx, cy = x + w / 2, y + h / 2
    cw, ch = w * (1 + 1.8 * pad), h * (1 + 2.4 * pad)   # room for hair, ears, shoulders
    left, top = cx - cw / 2, cy - ch * 0.42             # face sits a little above centre
    W, H = img.size
    box = (int(max(0, left)), int(max(0, top)), int(min(W, left + cw)), int(min(H, top + ch)))
    print(f"Face crop: face at {x},{y} {w}x{h} -> cropped to {box}")
    return img.crop(box)


def remove_bg(img, model, bg_color):
    try:
        from rembg import new_session, remove
    except ImportError:
        raise SystemExit("--remove-bg needs:  pip install rembg onnxruntime")
    cut = remove(img, session=new_session(model)).convert("RGBA")
    base = Image.new("RGBA", cut.size, bg_color + (255,))
    return Image.alpha_composite(base, cut).convert("RGB")


IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp")


def open_source_image(path):
    """Open an image file. A .docx is accepted too: its largest embedded picture is used.
    If the .docx does not exist, a sibling image with the same name stem is used instead."""
    p = Path(path)
    if p.suffix.lower() != ".docx":
        return Image.open(p)
    if p.exists():
        with zipfile.ZipFile(p) as z:
            media = [i for i in z.infolist()
                     if i.filename.startswith("word/media/")
                     and i.filename.lower().endswith(IMAGE_EXTS)]
            if not media:
                raise SystemExit(f"{p} has no embedded picture to use as the source image.")
            best = max(media, key=lambda i: i.file_size)
            img = Image.open(BytesIO(z.read(best)))
            img.load()
            return img
    for ext in IMAGE_EXTS:
        sib = p.with_suffix(ext)
        if sib.exists():
            print(f"{p} not found - using {sib} as the source image.")
            return Image.open(sib)
    raise SystemExit(f"Source image not found: {p} (looked for a .docx, then {p.stem}.jpg/.png/...)")


def load_image(args):
    img = ImageOps.exif_transpose(open_source_image(args.image))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        img = Image.alpha_composite(Image.new("RGBA", img.size, (255, 255, 255, 255)), img)
    img = img.convert("RGB")
    if args.face_crop:
        img = face_crop(img, args.crop_pad)
    if args.remove_bg:
        img = remove_bg(img, args.bg_model, (0, 0, 0) if (args.dark and not args.invert)
                        else (255, 255, 255))
    img = ImageOps.autocontrast(img, cutoff=1)
    if args.equalize > 0:
        img = Image.blend(img, ImageOps.equalize(img), args.equalize)
    if not args.no_sharpen:
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=2))
    return ImageEnhance.Contrast(img).enhance(args.contrast)


def to_gray(img, size, invert):
    small = img.resize(size, Image.LANCZOS)
    g = np.asarray(ImageOps.grayscale(small), dtype=np.float32) / 255.0
    return small, (1.0 - g if invert else g)


def otsu(gray):
    if gray.max() - gray.min() < 1e-3:
        return 0.5
    hist, edges = np.histogram(gray, bins=256, range=(0, 1))
    p = hist / hist.sum()
    omega, mu = np.cumsum(p), np.cumsum(p * edges[:-1])
    with np.errstate(divide="ignore", invalid="ignore"):
        sigma = (mu[-1] * omega - mu) ** 2 / (omega * (1 - omega))
    return float(edges[np.nanargmax(sigma)])


# ---------------------------------------------------------------- txt

def make_txt(gray, text, threshold, use_case, dither, keep_spaces):
    levels = [1.0, 0.62, 0.40] if use_case else [1.0, 0.45]
    g = np.clip(gray + ((levels[0] + levels[1]) / 2 - threshold), 0, 1)
    rows, cols = g.shape
    stream = text_stream(text, keep_spaces)
    lines = []
    for y in range(rows):
        line = []
        for x in range(cols):
            v = g[y, x]
            k = int(np.argmin([abs(v - L) for L in levels]))
            if dither:
                err = v - levels[k]
                if x + 1 < cols: g[y, x + 1] += err * 7 / 16
                if y + 1 < rows:
                    if x > 0: g[y + 1, x - 1] += err * 3 / 16
                    g[y + 1, x] += err * 5 / 16
                    if x + 1 < cols: g[y + 1, x + 1] += err / 16
            if k == 0:
                line.append(" ")
            else:
                c, _ = next(stream)
                line.append(c.upper() if k == 2 else (c.lower() if use_case else c))
        lines.append("".join(line).rstrip())
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- fonts

class FontSet:
    """One or more font families (ordered light -> heavy for tone mixing).
    Variable fonts with a Weight axis get their weight driven by darkness."""

    def __init__(self, specs, mix, vary_weight, seed=7):
        self.specs = specs              # list of (path, index)
        self.mix = mix
        self.vary_weight = vary_weight
        self.cache = {}
        self.rng = random.Random(seed)
        self.word_pick = {}
        self.last = (0, -1)             # (font index, weight step) of the latest get()
        self.axes = []
        for p, i in specs:
            try:
                ax = ImageFont.truetype(p, 12, index=i).get_variation_axes()
            except Exception:
                ax = []
            self.axes.append(ax)
        names = [Path(p).stem + (" (variable weight)" if self._wght(a) is not None else "")
                 for (p, _), a in zip(specs, self.axes)]
        print("Fonts:", ", ".join(names))

    @staticmethod
    def _wght(axes):
        for n, a in enumerate(axes):
            nm = a["name"].decode() if isinstance(a["name"], bytes) else a["name"]
            if nm.lower().startswith("weight"):
                return n
        return None

    def pick(self, ink, word):
        n = len(self.specs)
        if n == 1 or self.mix == "tone":
            return min(n - 1, int(ink * n))
        if self.mix == "word":
            return word % n
        if word not in self.word_pick:          # random, but stable per word
            self.word_pick = {word: self.rng.randrange(n)}
        return self.word_pick[word]

    def get(self, ink, word, size):
        idx = self.pick(ink, word)
        axes = self.axes[idx]
        wi = self._wght(axes) if self.vary_weight else None
        wb = int(round(ink * 8)) if wi is not None else -1     # 9 weight steps
        key = (idx, size, wb)
        self.last = (idx, wb)
        if key not in self.cache:
            p, i = self.specs[idx]
            f = ImageFont.truetype(p, size, index=i)
            if wi is not None:
                vals = []
                for n, a in enumerate(axes):
                    if n == wi:
                        vals.append(a["minimum"] + (a["maximum"] - a["minimum"]) * wb / 8)
                    else:
                        vals.append(a.get("default", a["minimum"]))
                f.set_variation_by_axes(vals)
            self.cache[key] = f
        return self.cache[key]

    def has_weight_axis(self):
        return self.vary_weight and any(self._wght(a) is not None for a in self.axes)


def resolve_fonts(arg):
    if arg:
        specs = []
        for p in [s.strip() for s in arg.split(",") if s.strip()]:
            if not Path(p).exists():
                raise SystemExit(f"Font not found: {p}")
            specs.append((p, 0))
        return specs
    for p, i in MONO_FONTS:
        if Path(p).exists():
            return [(p, i)]
    raise SystemExit("No monospace font found - pass one with --fonts path/to/font.ttf")


# ---------------------------------------------------------------- png

def ink_and_fill(g, px, args):
    tone = g * args.ghost if not args.dark else 1 - (1 - g) * args.ghost
    ink = (1 - g) if not args.dark else g
    if args.color:
        fill = tuple(int(v) for v in px)
    else:
        lvl = int(255 * tone)
        fill = (lvl, lvl, lvl)
    return ink, fill


def stroke_for(ink, args, fonts, ss):
    if not args.bold:
        return 0
    b = args.bold
    return int(round(ink ** 1.5 * b * ss))


def make_png_grid(img, cols, text, fonts, args, ss=2, rec=None):
    size = args.font_size * ss
    ref = fonts.get(0.5, 0, size)
    cw = max(1, round(np.mean([fonts.get(0.5, w, size).getlength("n") for w in range(len(fonts.specs))])))
    asc, desc = ref.getmetrics()
    ch = round((asc + desc) * 0.88)
    small, gray = to_gray(img, (cols, max(1, round(img.height / img.width * cols * cw / ch))), args.invert)
    rows = small.size[1]
    canvas = Image.new("RGB", (cols * cw, rows * ch), (0, 0, 0) if args.dark else (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    px = np.asarray(small)
    stream = text_stream(text, args.keep_spaces)
    for y in range(rows):
        row = []
        for x in range(cols):
            c, word = next(stream)
            ink, fill = ink_and_fill(float(gray[y, x]), px[y, x], args)
            f = fonts.get(ink, word, size)
            draw.text((x * cw + cw / 2, y * ch + asc), c, font=f, fill=fill, anchor="ms",
                      stroke_width=stroke_for(ink, args, fonts, ss), stroke_fill=fill)
            row.append((c, fonts.last[0], size, fill, ink, cw - f.getlength(c)))  # pad to the cell
        if rec is not None:
            rec["rows"].append(row)
    if rec is not None:
        rec.update(width=canvas.width, pitch=ch, ss=ss)
    return canvas.resize((canvas.width // ss, canvas.height // ss), Image.LANCZOS)


def make_png_flow(img, cols, text, fonts, args, ss=2, rec=None):
    """Variable size: letters flow along each line like typeset text.
    Each letter's size comes from the darkness under it, so lines stay readable."""
    base = args.font_size * ss
    smin, smax = max(4, round(base * args.min_size)), round(base * args.max_size)
    ref = fonts.get(0.5, 0, base)
    asc, desc = ref.getmetrics()
    row_h = round((asc + desc) * args.line_height)   # big letters may overlap rows: fills darks
    W = round(cols * fonts.get(0.5, 0, base).getlength("n") * 1.15)
    H = round(W * img.height / img.width)
    small, gray = to_gray(img, (W, H), args.invert)
    gray = np.asarray(Image.fromarray((gray * 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(base / 3)), dtype=np.float32) / 255.0
    px = np.asarray(small)
    canvas = Image.new("RGB", (W, H), (0, 0, 0) if args.dark else (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    stream = text_stream(text, args.keep_spaces)
    pending = None
    for top in range(0, H - row_h // 3, row_h):
        baseline = top + round(row_h * 0.78)
        cy = min(H - 1, top + row_h // 2)
        x = 0.0
        row = []
        while x < W:
            c, word = pending or next(stream)
            pending = None
            sx = min(W - 1, int(x + base * 0.3))
            ink, fill = ink_and_fill(float(gray[cy, sx]), px[cy, sx], args)
            size = round(smin + (smax - smin) * ink ** 0.9)
            f = fonts.get(ink, word, size)
            adv = f.getlength(c)
            if x + adv > W and x > 0:
                pending = (c, word)            # carry letter to next line, nothing lost
                break
            draw.text((x, baseline), c, font=f, fill=fill, anchor="ls",
                      stroke_width=stroke_for(ink, args, fonts, ss), stroke_fill=fill)
            x += adv + args.tracking * ss
            row.append((c, fonts.last[0], size, fill, ink, args.tracking * ss))
        if rec is not None:
            rec["rows"].append(row)
    if rec is not None:
        rec.update(width=W, pitch=row_h, ss=ss)
    return canvas.resize((W // ss, H // ss), Image.LANCZOS)


# ---------------------------------------------------------------- docx

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PT_PER_PX = 0.75           # 96 dpi
MAX_PAGE_TWIPS = 31000     # Word's page limit is 31680 twips (22 in)


def family_names(specs):
    """Family name Word should ask for, read from each font file."""
    names = []
    for p, i in specs:
        try:
            fam = ImageFont.truetype(p, 12, index=i).getname()[0]
        except Exception:
            fam = Path(p).stem
        names.append(fam)
    return names


def _run(c, fam, half_pt, fill, bold, spacing):
    rpr = (f'<w:rFonts w:ascii="{fam}" w:hAnsi="{fam}" w:cs="{fam}"/>' + ("<w:b/>" if bold else "")
           + f'<w:color w:val="{fill}"/>'
           + (f'<w:spacing w:val="{spacing}"/>' if spacing else "")
           + f'<w:sz w:val="{half_pt}"/><w:szCs w:val="{half_pt}"/>')
    return f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{escape(c)}</w:t></w:r>'


def write_docx(path, rec, fonts, args):
    """Write the recorded portrait layout as a .docx (stdlib zipfile + hand-built OOXML).
    One paragraph per row, one run per letter (equal neighbours merged). Each run carries
    its colour, font family, size and bold. Fonts must be installed where the file is opened."""
    ss, rows = rec["ss"], rec["rows"]
    fams = [escape(f, {'"': "&quot;"}) for f in family_names(fonts.specs)]
    width_tw = rec["width"] / ss * PT_PER_PX * 20 * 1.04        # 4% slack: Word's metrics differ
    scale = min(1.0, MAX_PAGE_TWIPS / width_tw)
    px_pt = PT_PER_PX * scale / ss                               # recorded px -> points
    margin = 360
    page_w = int(width_tw * scale) + 2 * margin
    page_h = max(1440, int(len(rows) * rec["pitch"] * px_pt * 20) + 2 * margin + 400)
    page_h = min(page_h, 31680)
    line_tw = max(20, int(rec["pitch"] * px_pt * 20))
    paras = []
    for row in rows:
        runs, last, buf = [], None, ""
        for c, idx, size, fill, ink, extra in row:
            hp = max(2, round(size * px_pt * 2))
            key = (fams[idx], hp, "%02X%02X%02X" % tuple(fill[:3]),
                   bool(args.bold and ink >= 0.7), round(extra * px_pt * 20))
            if key == last:
                buf += c
                continue
            if last:
                runs.append(_run(buf, *last))
            last, buf = key, c
        if last:
            runs.append(_run(buf, *last))
        paras.append('<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="%d" '
                     'w:lineRule="exact"/></w:pPr>%s</w:p>' % (line_tw, "".join(runs)))
    bg = "000000" if args.dark else "FFFFFF"
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<w:document xmlns:w="{W_NS}"><w:background w:color="{bg}"/><w:body>'
                + "".join(paras)
                + f'<w:sectPr><w:pgSz w:w="{page_w}" w:h="{page_h}"/>'
                f'<w:pgMar w:top="{margin}" w:right="{margin}" w:bottom="{margin}" w:left="{margin}" '
                'w:header="0" w:footer="0" w:gutter="0"/></w:sectPr></w:body></w:document>')
    settings = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<w:settings xmlns:w="{W_NS}"><w:displayBackgroundShape/></w:settings>')
    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
        '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>')
    doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>'
        '</Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)
        z.writestr("word/settings.xml", settings)
        z.writestr("word/_rels/document.xml.rels", doc_rels)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="ASCII portrait from an image + a text file.")
    ap.add_argument("image")
    ap.add_argument("textfile")
    g = ap.add_argument_group("output")
    g.add_argument("--out", default=None,
                   help="output base name (default: <image>_portrait); a .docx name also turns on --docx")
    g.add_argument("--docx", action="store_true",
                   help="also write <out>.docx: live Word text, per-letter colour/font/size (implies --color). "
                        "Automatic when the input image is a .docx")
    g.add_argument("--width", type=int, default=120, help="TXT columns (default 120)")
    g.add_argument("--png-width", type=int, default=None, help="PNG columns (default 1.5x --width)")
    g = ap.add_argument_group("image prep")
    g.add_argument("--face-crop", action="store_true", help="auto-crop to the face (needs opencv)")
    g.add_argument("--crop-pad", type=float, default=1.0, help="room around face, 0.5 tight - 2 loose")
    g.add_argument("--remove-bg", action="store_true", help="remove background (needs rembg)")
    g.add_argument("--bg-model", default="u2net",
                   help="rembg model: u2net (best), u2netp (small/fast), isnet-general-use")
    g.add_argument("--contrast", type=float, default=1.2)
    g.add_argument("--equalize", type=float, default=0.3, help="0-1, lifts flat engravings")
    g.add_argument("--no-sharpen", action="store_true")
    g.add_argument("--invert", action="store_true", help="swap light/dark")
    g = ap.add_argument_group("text")
    g.add_argument("--keep-spaces", action="store_true", help="keep spaces between words")
    g.add_argument("--unicode", action="store_true", help="keep curly quotes etc.")
    g = ap.add_argument_group("txt output")
    g.add_argument("--threshold", default="auto", help="0-1 or 'auto'")
    g.add_argument("--no-case", action="store_true", help="don't UPPERCASE dark areas")
    g.add_argument("--dither", action="store_true", help="smoother shading, less readable")
    g = ap.add_argument_group("png output")
    g.add_argument("--fonts", default=None,
                   help="comma-separated font files, light->heavy for tone mixing. Can mix families")
    g.add_argument("--font-mix", choices=["tone", "word", "random"], default="tone",
                   help="how to choose between --fonts: by darkness, alternate per word, random per word")
    g.add_argument("--no-weight", action="store_true",
                   help="don't drive variable-font weight by darkness")
    g.add_argument("--font-size", type=int, default=12)
    g.add_argument("--variable-size", action="store_true",
                   help="letters grow in dark areas, shrink in light (flowing lines)")
    g.add_argument("--min-size", type=float, default=0.45, help="smallest letter, x font-size")
    g.add_argument("--max-size", type=float, default=1.6, help="largest letter, x font-size")
    g.add_argument("--line-height", type=float, default=0.85,
                   help="variable size: line spacing x normal (lower = denser)")
    g.add_argument("--tracking", type=float, default=0.0, help="extra px between letters")
    g.add_argument("--bold", type=float, default=1.0, help="extra stroke in darks, 0 = off")
    g.add_argument("--ghost", type=float, default=0.92, help="<1 keeps faint text in highlights")
    g.add_argument("--color", action="store_true", help="colour letters from the photo")
    g.add_argument("--dark", action="store_true", help="light letters on black")
    args = ap.parse_args()

    if args.out and args.out.lower().endswith(".docx"):
        args.out, args.docx = args.out[:-5], True
    if Path(args.image).suffix.lower() == ".docx":
        args.docx = True
    if args.docx and not args.color:
        args.color = True
        print("Word export is always coloured: --color is on.")

    text = load_text(args.textfile, args.unicode)
    img = load_image(args)
    base = args.out or f"{Path(args.image).stem}_portrait"

    tcols = args.width
    _, gray = to_gray(img, (tcols, max(1, round(img.height / img.width * tcols * TXT_ASPECT))), args.invert)
    thr = otsu(gray) if args.threshold == "auto" else float(args.threshold)
    Path(base + ".txt").write_text(
        make_txt(gray, text, thr, not args.no_case, args.dither, args.keep_spaces), encoding="utf-8")

    fonts = FontSet(resolve_fonts(args.fonts), args.font_mix, not args.no_weight)
    pcols = args.png_width or int(args.width * 1.5)
    maker = make_png_flow if args.variable_size else make_png_grid
    rec = {"rows": []} if args.docx else None
    maker(img, pcols, text, fonts, args, rec=rec).save(base + ".png")
    if rec is not None:
        write_docx(base + ".docx", rec, fonts, args)

    print(f"Wrote {base}.txt ({gray.shape[1]}x{gray.shape[0]}) and {base}.png "
          f"({'variable size' if args.variable_size else 'grid'}, {pcols} cols)"
          + (f" and {base}.docx" if rec is not None else ""))


if __name__ == "__main__":
    main()
