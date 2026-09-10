"""Generate the microsite's favicon and app icons.

Brand basis (sampled from nbctrustco.com, DECISIONS.md D-022/D-023):
  logo blue  #1260A8  -- sampled from their actual logo PNG
  deep navy  #003D68  -- from their stylesheet, used for the site's ink
  wordmark   heavy high-contrast serif ("NBC") over letterspaced serif caps

Their own favicon is the full stacked logo squeezed into 32x32, which is
illegible at that size. This uses the "NBC" monogram alone, sized to nearly
fill the tile, which is what actually reads in a browser tab.

PIL is required to REGENERATE the icons and nothing else -- the site itself
is stdlib-only (D-005) and the generated PNGs are committed, so building or
serving the microsite never needs this script or PIL.

Usage:  python3 microsite/assets/make_icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent

BLUE = (18, 96, 168)        # #1260A8, sampled from their logo
WHITE = (255, 255, 255)

# Rendered large then downsampled -- Lanczos on a 4x render gives far cleaner
# serif edges at 32px than rasterising the font at 32px directly.
SUPERSAMPLE = 4

SERIF_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Bodoni 72.ttc",
    "/System/Library/Fonts/Supplemental/Didot.ttc",
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
]

SIZES = {
    "icon-32.png": 32,      # browser tab
    "icon-180.png": 180,    # apple-touch-icon
    "icon-512.png": 512,    # PWA / high-DPI / social
}

# Size-specific marks, which is ordinary icon practice rather than a compromise.
# At 32px three high-contrast serif letters go muddy -- Bodoni's thin strokes
# simply do not survive being 1px wide -- so the tab icon is the "N" alone,
# rendered in a sturdier serif whose thins hold up. Larger tiles carry the full
# "NBC" in Bodoni, matching their wordmark.
SMALL_MAX = 48
SMALL_FONTS = [
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
]


def load_serif(px, candidates=None):
    """Heaviest available high-contrast serif, to match their wordmark."""
    for path in (candidates or SERIF_CANDIDATES):
        if not Path(path).exists():
            continue
        # .ttc files hold several faces; try the later (bolder) indices first.
        for index in (1, 2, 0):
            try:
                f = ImageFont.truetype(path, px, index=index)
                if "bold" in (f.getname()[1] or "").lower() or path.endswith(".ttf"):
                    return f, "%s [%s]" % (Path(path).name, f.getname()[1])
            except Exception:
                continue
    for path in (candidates or SERIF_CANDIDATES):
        if Path(path).exists():
            return ImageFont.truetype(path, px), Path(path).name
    raise SystemExit("No serif font found; adjust SERIF_CANDIDATES.")


def render(size):
    S = size * SUPERSAMPLE
    img = Image.new("RGBA", (S, S), BLUE + (255,))
    d = ImageDraw.Draw(img)

    small = size <= SMALL_MAX
    text = "N" if small else "NBC"
    fonts = SMALL_FONTS if small else SERIF_CANDIDATES
    # A single letter can fill more of the tile than three can.
    target_w = S * (0.52 if small else 0.74)

    px = int(S * 0.4)
    font, name = load_serif(px, fonts)
    for _ in range(60):
        b = d.textbbox((0, 0), text, font=font)
        if (b[2] - b[0]) >= target_w or px > S:
            break
        px += max(1, int(px * 0.04))
        font, name = load_serif(px, fonts)

    box = d.textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    # Centre on the glyphs' own ink box, not the font's line box, or the
    # optical centre sits low because of descender metrics.
    d.text(((S - w) / 2 - box[0], (S - h) / 2 - box[1]), text, font=font, fill=WHITE)

    # Gentle rounding: a square tile reads harsh next to platform icons, and
    # iOS masks apple-touch-icon itself, so keep the radius subtle.
    radius = int(S * 0.16)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=255)
    img.putalpha(mask)

    return img.resize((size, size), Image.LANCZOS), name


def main():
    used = None
    for filename, size in SIZES.items():
        img, used = render(size)
        img.save(OUT / filename)
        print("wrote %-14s %3dx%-3d  %s" % (filename, size, size,
                                            "N" if size <= SMALL_MAX else "NBC"))
    print("font: %s" % used)


if __name__ == "__main__":
    main()
