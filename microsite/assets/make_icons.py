"""Generate the microsite's PNG icons and social share image.

The mark (D-025): a round table seen from above -- a solid centre, seven
seats around it, and one seat in copper. That last seat is the reader's: the
whole proposition is "your seat is saved". It is geometric on purpose, so it
stays legible at 32px where a wordmark cannot, and so the SVG favicon
(assets/mark.svg) and these PNGs are drawn from the same coordinates.

PIL is required to REGENERATE these files and nothing else -- the site itself
is stdlib-only (D-005) and the outputs are committed, so building or serving
the microsite never needs this script or PIL.

Usage:  python3 microsite/assets/make_icons.py
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent

DEEP = (16, 32, 27)          # #10201b
FOREST = (26, 58, 48)        # #1a3a30
PAPER = (239, 233, 220)      # #efe9dc
SEAT_DIM = (140, 156, 147)   # paper at ~60% over deep, pre-blended
COPPER = (224, 129, 78)      # #e0814e
WHEAT = (230, 200, 143)

# Rendered large then downsampled -- Lanczos on a 4x render gives far cleaner
# circle edges at 32px than rasterising at 32px directly.
SUPERSAMPLE = 4

SIZES = {
    "icon-32.png": 32,      # browser tab (fallback for the SVG)
    "icon-180.png": 180,    # apple-touch-icon
    "icon-512.png": 512,    # PWA / high-DPI
}


def draw_mark(draw, cx, cy, unit, seat_dim=SEAT_DIM):
    """The mark on a 40-unit grid centred at (cx, cy); ``unit`` px per unit."""
    def dot(x, y, r, fill):
        x, y = cx + (x - 20) * unit, cy + (y - 20) * unit
        draw.ellipse([x - r * unit, y - r * unit, x + r * unit, y + r * unit], fill=fill)

    dot(20, 20, 9, PAPER)
    # Eight seats at 45-degree steps from the top; the bottom one is "yours".
    for k in range(8):
        a = math.radians(-90 + 45 * k)
        x, y = 20 + 15.5 * math.cos(a), 20 + 15.5 * math.sin(a)
        if k == 4:
            dot(x, y, 3.0, COPPER)
        else:
            dot(x, y, 2.6, seat_dim)


def icon(px):
    big = px * SUPERSAMPLE
    img = Image.new("RGB", (big, big), DEEP)
    d = ImageDraw.Draw(img)
    # The mark fills ~80% of the tile; at 32px it needs every pixel.
    scale = 0.9 if px <= 48 else 0.78
    draw_mark(d, big / 2, big / 2, big * scale / 40)
    return img.resize((px, px), Image.LANCZOS)


def load_font(px, italic=False, weight=400, sans=False):
    """The site's own variable fonts, pinned to the instance the CSS uses.
    Fraunces defaults to weight 900 and the "wonky" alternates, so both are
    set explicitly; a fallback font simply ignores the axes."""
    if sans:
        name, axes = "inter-latin-wght-normal.woff2", [weight]
    else:
        name = "fraunces-latin-full-%s.woff2" % ("italic" if italic else "normal")
        axes = [min(144, px / SUPERSAMPLE * 2), weight, 30 if not italic else 100, 0]
    for path in (OUT / "fonts" / name,
                 Path("/System/Library/Fonts/Supplemental/Georgia.ttf")):
        try:
            font = ImageFont.truetype(str(path), px)
        except OSError:
            continue
        try:
            font.set_variation_by_axes(axes)
        except (OSError, ValueError):
            pass
        return font
    return ImageFont.load_default()


def og_image():
    """1200x630 social card: mark, name, and the promise."""
    w, h, s = 1200, 630, 2
    img = Image.new("RGB", (w * s, h * s), DEEP)
    d = ImageDraw.Draw(img)
    # a soft copper glow, top right
    glow = Image.new("L", (w * s, h * s), 0)
    gd = ImageDraw.Draw(glow)
    for i in range(60, 0, -1):
        r = i * 14 * s
        gd.ellipse([w * s - r, -r, w * s + r, r], fill=int(90 * (1 - i / 60)))
    img.paste(Image.new("RGB", img.size, COPPER), (0, 0), glow)
    d = ImageDraw.Draw(img)

    draw_mark(d, 140 * s, 150 * s, 2.4 * s)
    d.text((220 * s, 112 * s), "The Owner’s Table", font=load_font(44 * s, weight=500), fill=PAPER)
    d.text((222 * s, 168 * s), "FROM NBC TRUST", font=load_font(16 * s, weight=600, sans=True), fill=SEAT_DIM)

    d.text((96 * s, 300 * s), "Build a practice that", font=load_font(80 * s, weight=360), fill=PAPER)
    d.text((96 * s, 392 * s), "runs without you.", font=load_font(80 * s, italic=True, weight=360), fill=WHEAT)
    d.text((98 * s, 530 * s), "A free community and library for independent advisors who own their firm.",
           font=load_font(24 * s, sans=True), fill=SEAT_DIM)
    return img.resize((w, h), Image.LANCZOS)


def main():
    for name, px in SIZES.items():
        icon(px).save(OUT / name, optimize=True)
        print("wrote", name)
    og_image().save(OUT / "og.png", optimize=True)
    print("wrote og.png")


if __name__ == "__main__":
    main()
