"""Bildvorverarbeitung fuer OCR - bewusst nur Pillow (portabel, klein)."""

from __future__ import annotations

from PIL import Image, ImageFilter, ImageOps

# Spike-Ergebnis (Dev-Benchmark): Die gebuendelten RapidOCR-Mobilmodelle
# liefern bei ~1900 px Kantenlaenge vollstaendige, sauber getrennte Zeilen;
# groessere Bilder verschlechtern Detektion und Worttrennung.
MAX_SIDE = 1920
MIN_SIDE = 900


def prepare(image: Image.Image) -> Image.Image:
    """EXIF-Orientierung, Graustufen, sanfte Skalierung/Kontrast."""
    img = ImageOps.exif_transpose(image)
    if img.mode not in ("L", "RGB"):
        img = img.convert("RGB")
    w, h = img.size
    longest = max(w, h)
    if longest > MAX_SIDE:
        scale = MAX_SIDE / longest
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    elif longest < MIN_SIDE:
        scale = MIN_SIDE / longest
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    gray = img.convert("L")
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = gray.filter(ImageFilter.MedianFilter(size=3))
    return gray
