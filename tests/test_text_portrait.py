import subprocess
import sys
import tempfile
import unittest
import zipfile
import xml.dom.minidom
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont  # noqa: F401
    import numpy  # noqa: F401
    HAVE = True
except ImportError:
    HAVE = False

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "text_portrait.py"
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/georgia.ttf",
]


def two_fonts():
    found = [p for p in FONT_CANDIDATES if Path(p).exists()]
    return found[:2] if len(found) >= 2 else None


def run(cwd, *args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd,
                          capture_output=True, text=True)


@unittest.skipUnless(HAVE, "needs pillow and numpy")
class DocxExport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        im = Image.new("RGB", (120, 150), (240, 230, 200))
        ImageDraw.Draw(im).ellipse((30, 20, 90, 100), fill=(200, 30, 30))
        im.save(self.d / "pic.png")
        (self.d / "poem.txt").write_text("No man is an island entire of itself " * 30)

    def tearDown(self):
        self.tmp.cleanup()

    def test_docx_flag_writes_valid_coloured_package(self):
        fonts = two_fonts()
        args = ["pic.png", "poem.txt", "--docx", "--width", "40"]
        if fonts:
            args += ["--fonts", ",".join(fonts), "--font-mix", "word", "--variable-size"]
        r = run(self.d, *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = self.d / "pic_portrait.docx"
        self.assertTrue(out.exists())
        with zipfile.ZipFile(out) as z:
            for n in z.namelist():
                xml.dom.minidom.parseString(z.read(n))
            doc = z.read("word/document.xml").decode()
        self.assertIn("<w:color w:val=", doc)
        self.assertGreater(doc.count("<w:p>"), 5)
        if fonts:
            self.assertGreaterEqual(doc.count("<w:rFonts"), 2)

    def test_out_name_docx_turns_on_docx(self):
        r = run(self.d, "pic.png", "poem.txt", "--out", "x.docx", "--width", "30")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.d / "x.docx").exists())
        self.assertTrue((self.d / "x.png").exists())

    def test_docx_input_uses_embedded_picture(self):
        src = self.d / "src.docx"
        with zipfile.ZipFile(src, "w") as z:
            z.write(self.d / "pic.png", "word/media/image1.png")
        r = run(self.d, "src.docx", "poem.txt", "--width", "30")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.d / "src_portrait.docx").exists())

    def test_missing_docx_falls_back_to_sibling_image(self):
        r = run(self.d, "pic.docx", "poem.txt", "--width", "30")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("using", r.stdout)
        self.assertTrue((self.d / "pic_portrait.docx").exists())

    def test_missing_source_fails_clearly(self):
        r = run(self.d, "nothing.docx", "poem.txt")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Source image not found", r.stderr)

    def test_rows_never_wrap_and_line_rule_option(self):
        for mode, rule in (("exact", "exact"), ("atleast", "atLeast")):
            r = run(self.d, "pic.png", "poem.txt", "--docx", "--width", "30",
                    "--docx-lines", mode, "--out", "m_" + mode)
            self.assertEqual(r.returncode, 0, r.stderr)
            with zipfile.ZipFile(self.d / ("m_" + mode + ".docx")) as z:
                doc = z.read("word/document.xml").decode()
            self.assertIn('w:lineRule="%s"' % rule, doc)
            self.assertIn('<w:ind w:right="-', doc)

    def test_proofing_and_compat_settings(self):
        r = run(self.d, "pic.png", "poem.txt", "--docx", "--width", "30", "--dark", "--out", "p")
        self.assertEqual(r.returncode, 0, r.stderr)
        with zipfile.ZipFile(self.d / "p.docx") as z:
            doc, st = z.read("word/document.xml").decode(), z.read("word/settings.xml").decode()
        self.assertIn("<w:noProof/>", doc)
        self.assertIn('<w:background w:color="000000"/>', doc)
        for tag in ("hideSpellingErrors", "hideGrammaticalErrors", 'w:val="15"'):
            self.assertIn(tag, st)

    def test_default_run_writes_no_docx(self):
        r = run(self.d, "pic.png", "poem.txt", "--width", "30")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.d / "pic_portrait.docx").exists())


if __name__ == "__main__":
    unittest.main()
