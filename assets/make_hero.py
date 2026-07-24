"""Generate the README hero image.

Reproducible so the banner can be retweaked without a design tool. Renders at 2x
and downsamples for crisp anti-aliasing. Run: python assets/make_hero.py
"""

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 2  # supersample factor
W, H = 1200 * S, 400 * S
OUT = os.path.join(os.path.dirname(__file__), "hero.png")

CYAN = (34, 211, 238)
VIOLET = (139, 92, 246)
WHITE = (248, 250, 252)
SLATE = (148, 163, 184)
MUTED = (100, 116, 139)

FONT_DIR = "/System/Library/Fonts"


def _font(name, size, variation=None):
    f = ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    if variation:
        try:
            f.set_variation_by_name(variation)
        except Exception:
            pass
    return f


def background():
    yy = np.linspace(0, 1, H)[:, None]
    base = (1 - yy) * np.array([13, 18, 28]) + yy * np.array([8, 11, 18])
    img = np.repeat(base[:, None, :], W, axis=1)

    gx, gy = np.meshgrid(np.arange(W), np.arange(H))

    def glow(cx, cy, color, strength, sigma):
        d2 = (gx - cx) ** 2 + (gy - cy) ** 2
        falloff = np.exp(-d2 / (2 * sigma ** 2))
        for c in range(3):
            img[:, :, c] += color[c] * strength * falloff

    glow(0.74 * W, 0.42 * H, CYAN, 0.30, 0.34 * W)
    glow(0.52 * W, 0.95 * H, VIOLET, 0.16, 0.40 * W)
    glow(0.10 * W, 0.30 * H, (20, 120, 130), 0.12, 0.30 * W)

    return Image.fromarray(np.clip(img, 0, 255).astype("uint8"), "RGB").convert("RGBA")


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def lens_and_graph(base):
    glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    cx, cy = int(0.75 * W), int(0.50 * H)

    # concentric lens rings
    rings = 7
    for i in range(rings):
        r = int((40 + i * 30) * S)
        t = i / (rings - 1)
        color = lerp(CYAN, VIOLET, t)
        alpha = int(230 * (1 - t) + 40)
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color + (alpha,), width=int(2.5 * S))

    # correlation nodes connected to the focus
    rng_pts = [(-0.30, -0.34), (-0.12, -0.40), (0.16, -0.30),
               (0.30, -0.05), (0.22, 0.28), (-0.05, 0.36), (-0.28, 0.22)]
    for fx, fy in rng_pts:
        nx, ny = int(cx + fx * W), int(cy + fy * H)
        gd.line([cx, cy, nx, ny], fill=CYAN + (70,), width=int(1.2 * S))
    node_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    nd = ImageDraw.Draw(node_layer)
    for fx, fy in rng_pts:
        nx, ny = int(cx + fx * W), int(cy + fy * H)
        rr = int(5 * S)
        nd.ellipse([nx - rr, ny - rr, nx + rr, ny + rr], fill=WHITE + (255,))

    # bright focus core
    rr = int(9 * S)
    nd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=WHITE + (255,))

    blurred = glow_layer.filter(ImageFilter.GaussianBlur(int(3 * S)))
    base = Image.alpha_composite(base, blurred)
    base = Image.alpha_composite(base, glow_layer)
    base = Image.alpha_composite(base, node_layer.filter(ImageFilter.GaussianBlur(1)))
    base = Image.alpha_composite(base, node_layer)
    return base


def text(base):
    d = ImageDraw.Draw(base)
    wordmark = _font("SFNS.ttf", int(96 * S), "Bold")
    tagline = _font("SFNS.ttf", int(34 * S), "Regular")
    mono = _font("SFNSMono.ttf", int(21 * S), "Regular")

    x = int(96 * S)
    y = int(120 * S)
    d.text((x, y), "Onion", font=wordmark, fill=WHITE)
    w1 = d.textlength("Onion", font=wordmark)
    d.text((x + w1, y), "Lens", font=wordmark, fill=CYAN)

    d.text((x + int(4 * S), int(238 * S)), "AI correlation over the onion web", font=tagline, fill=SLATE)
    d.text((x + int(4 * S), int(292 * S)),
           "passive OSINT   ·   powered by Ahmia   ·   no Tor required",
           font=mono, fill=MUTED)
    return base


def main():
    img = background()
    img = lens_and_graph(img)
    img = text(img)
    img = img.resize((W // S, H // S), Image.LANCZOS)
    img.convert("RGB").save(OUT, "PNG")
    print(f"wrote {OUT} ({img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    main()
