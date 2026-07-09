"""Render the code-owned Translation Bridge mark into PNG assets.

The SVG files are the source of truth for the mark. This helper keeps the PNG
application icon and social banner aligned without relying on generated imagery.
"""

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
INK = "#101512"
PAPER = "#F3F0E8"
LEAF = "#9CCF78"


def _curve(draw, origin, scale, fill, width):
    """Draw a smooth bridge arch with a deliberately simple profile."""
    ox, oy = origin
    draw.arc(
        (ox + 46 * scale, oy + 94 * scale, ox + 210 * scale, oy + 232 * scale),
        start=180, end=360, fill=fill, width=width,
    )


def draw_mark(size: int) -> Image.Image:
    # Render large then downsample. The icon is shown at very small sizes in the
    # Windows shell, so anti-aliased bridge edges matter more than fine detail.
    resolution = size * 4
    image = Image.new("RGB", (resolution, resolution), INK)
    draw = ImageDraw.Draw(image)
    scale = resolution / 256
    inset = round(24 * scale)
    draw.rounded_rectangle(
        (inset, inset, resolution - inset, resolution - inset),
        radius=round(42 * scale), fill=INK,
    )
    _curve(draw, (0, 0), scale, LEAF, round(14 * scale))
    draw.line(
        [(48 * scale, 163 * scale), (208 * scale, 163 * scale)],
        fill=PAPER, width=round(14 * scale),
    )
    for x in (78, 128, 178):
        draw.line(
            [(x * scale, 163 * scale), (x * scale, 186 * scale)],
            fill=LEAF, width=round(12 * scale),
        )
    radius = round(9 * scale)
    cx, cy = round(128 * scale), round(67 * scale)
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=LEAF)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def draw_banner() -> Image.Image:
    width, height = 1280, 640
    s = 4
    image = Image.new("RGB", (width * s, height * s), PAPER)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width * s, 14 * s), fill=LEAF)
    draw.rounded_rectangle(
        (84 * s, 104 * s, 1196 * s, 538 * s), radius=30 * s,
        outline="#D3D9CF", width=3 * s,
    )

    # A cropped bridge arch gives the banner a recognisable but restrained shape.
    _curve(draw, (660 * s, 82 * s), 2.15 * s, INK, 26 * s)
    draw.line([(760 * s, 432 * s), (1135 * s, 432 * s)], fill=LEAF, width=26 * s)
    for x in (830, 948, 1066):
        draw.line([(x * s, 432 * s), (x * s, 483 * s)], fill=INK, width=20 * s)
    draw.ellipse((922 * s, 190 * s, 956 * s, 224 * s), fill=LEAF)
    mark = draw_mark(152 * s)
    image.paste(mark, (150 * s, 244 * s))
    return image.resize((width, height), Image.Resampling.LANCZOS)


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    draw_mark(512).save(ASSETS / "logo.png", "PNG")
    draw_banner().save(ASSETS / "banner.png", "PNG")
