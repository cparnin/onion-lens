"""Generate the README hero image.

Reproducible so the banner can be retweaked without a design tool. Renders at 2x
and downsamples for crisp anti-aliasing. Run: python assets/make_hero.py
"""

import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 2  # supersample factor
W, H = 1200 * S, 400 * S
OUT = os.path.join(os.path.dirname(__file__), "hero.png")

GREEN = (52, 255, 150)
DIM_GREEN = (24, 120, 78)
RED = (255, 64, 64)
WHITE = (236, 244, 240)
SLATE = (120, 140, 132)
MUTED = (82, 98, 92)

FONT_DIR = "/System/Library/Fonts"

CX, CY = int(0.75 * W), int(0.50 * H)
SWEEP_ANGLE = math.radians(-35)  # where the radar beam currently points
MAX_R = int(230 * S)


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
    base = (1 - yy) * np.array([5, 8, 9]) + yy * np.array([2, 3, 4])
    img = np.repeat(base[:, None, :], W, axis=1)

    gx, gy = np.meshgrid(np.arange(W), np.arange(H))

    def glow(cx, cy, color, strength, sigma):
        d2 = (gx - cx) ** 2 + (gy - cy) ** 2
        falloff = np.exp(-d2 / (2 * sigma ** 2))
        for c in range(3):
            img[:, :, c] += color[c] * strength * falloff

    glow(CX, CY, (10, 60, 40), 0.55, 0.26 * W)
    glow(0.08 * W, 0.85 * H, (30, 10, 12), 0.35, 0.30 * W)

    # vignette: pull the edges down into black
    dx = (gx - W / 2) / (W / 2)
    dy = (gy - H / 2) / (H / 2)
    vig = 1 - 0.55 * np.clip(dx ** 2 + dy ** 2, 0, 1)
    img *= vig[:, :, None]

    return Image.fromarray(np.clip(img, 0, 255).astype("uint8"), "RGB").convert("RGBA")


def glyph_field(base):
    """Faint drifting onion-address fragments, the haystack being searched."""
    rng = random.Random(7)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    mono = _font("SFNSMono.ttf", int(13 * S))
    chars = "abcdefghijklmnopqrstuvwxyz234567"
    for _ in range(46):
        frag = "".join(rng.choice(chars) for _ in range(rng.randint(6, 14)))
        if rng.random() < 0.45:
            frag += ".onion"
        x = rng.randint(0, W)
        y = rng.randint(0, H)
        # brighter near the lens, nearly invisible elsewhere
        dist = math.hypot(x - CX, y - CY) / (0.5 * W)
        a = int(max(8, 46 * (1 - dist)))
        d.text((x, y), frag, font=mono, fill=DIM_GREEN + (a,))
    return Image.alpha_composite(base, layer)


def radar_sweep(base):
    """A bright beam with a decaying phosphor trail inside the lens."""
    gx, gy = np.meshgrid(np.arange(W), np.arange(H))
    ang = np.arctan2(gy - CY, gx - CX)
    dist = np.hypot(gx - CX, gy - CY)
    # angular distance behind the beam, in [0, 2pi)
    trail = np.mod(ang - SWEEP_ANGLE, 2 * math.pi)
    fade = np.exp(-trail / 0.9)
    radial = np.clip(1 - dist / MAX_R, 0, 1) ** 0.5
    alpha = (fade * radial * 110).astype("uint8")

    sweep = np.zeros((H, W, 4), dtype="uint8")
    sweep[:, :, 0], sweep[:, :, 1], sweep[:, :, 2] = 24, 160, 96
    sweep[:, :, 3] = alpha
    base = Image.alpha_composite(base, Image.fromarray(sweep, "RGBA"))

    # the beam edge itself
    beam = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(beam)
    ex = CX + int(MAX_R * math.cos(SWEEP_ANGLE))
    ey = CY + int(MAX_R * math.sin(SWEEP_ANGLE))
    bd.line([CX, CY, ex, ey], fill=GREEN + (235,), width=int(2.2 * S))
    base = Image.alpha_composite(base, beam.filter(ImageFilter.GaussianBlur(int(2 * S))))
    base = Image.alpha_composite(base, beam)
    return base


def lens_and_graph(base):
    glow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)

    # concentric lens rings, dimming outward
    rings = 7
    for i in range(rings):
        r = int((40 + i * 30) * S)
        t = i / (rings - 1)
        alpha = int(190 * (1 - t) + 26)
        gd.ellipse([CX - r, CY - r, CX + r, CY + r],
                   outline=DIM_GREEN + (alpha,), width=int(2 * S))

    # crosshair through the focus, with edge ticks
    ch = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(ch)
    gap = int(14 * S)
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        cd.line([CX + dx * gap, CY + dy * gap, CX + dx * MAX_R, CY + dy * MAX_R],
                fill=GREEN + (60,), width=int(1 * S))
        cd.line([CX + dx * (MAX_R - 10 * S), CY + dy * (MAX_R - 10 * S),
                 CX + dx * MAX_R, CY + dy * MAX_R],
                fill=GREEN + (200,), width=int(2 * S))

    # nodes: blips lit by the sweep, most still dark, two flagged red
    # (angle degrees, radius as a fraction of MAX_R); kept clear of the text zone
    pts = [(205, 0.62), (155, 0.85), (-75, 0.80), (-30, 1.12),
           (8, 0.92), (58, 0.68), (105, 1.02)]
    node_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    nd = ImageDraw.Draw(node_layer)
    for i, (deg, rf) in enumerate(pts):
        a = math.radians(deg)
        nx = int(CX + rf * MAX_R * math.cos(a))
        ny = int(CY + rf * MAX_R * math.sin(a))
        behind = (a - SWEEP_ANGLE) % (2 * math.pi)
        lit = behind < 1.8
        flagged = i in (4, 5)
        if flagged:
            color, a, rr = RED, 255, int(6 * S)
        elif lit:
            color, a, rr = GREEN, 235, int(5 * S)
        else:
            color, a, rr = DIM_GREEN, 90, int(4 * S)
        gd.line([CX, CY, nx, ny], fill=color + (46 if not flagged else 90,),
                width=int(1.2 * S))
        nd.ellipse([nx - rr, ny - rr, nx + rr, ny + rr], fill=color + (a,))
        if flagged:
            # bracket the flagged node like a target lock
            b = int(11 * S)
            k = int(5 * S)
            for sx, sy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                nd.line([nx + sx * b, ny + sy * b, nx + sx * (b - k), ny + sy * b],
                        fill=RED + (220,), width=int(1.4 * S))
                nd.line([nx + sx * b, ny + sy * b, nx + sx * b, ny + sy * (b - k)],
                        fill=RED + (220,), width=int(1.4 * S))

    # bright focus core
    rr = int(8 * S)
    nd.ellipse([CX - rr, CY - rr, CX + rr, CY + rr], fill=WHITE + (255,))

    blurred = glow_layer.filter(ImageFilter.GaussianBlur(int(3 * S)))
    base = Image.alpha_composite(base, blurred)
    base = Image.alpha_composite(base, glow_layer)
    base = Image.alpha_composite(base, ch)
    base = Image.alpha_composite(base, node_layer.filter(ImageFilter.GaussianBlur(int(2 * S))))
    base = Image.alpha_composite(base, node_layer)
    return base


def text(base):
    d = ImageDraw.Draw(base)
    wordmark = _font("SFNS.ttf", int(96 * S), "Bold")
    tagline = _font("SFNS.ttf", int(34 * S), "Regular")
    mono = _font("SFNSMono.ttf", int(21 * S), "Regular")

    x = int(96 * S)
    y = int(112 * S)

    # soft green glow behind the wordmark so it reads against pure black
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.text((x, y), "Onion", font=wordmark, fill=WHITE + (140,))
    w1 = d.textlength("Onion", font=wordmark)
    gd.text((x + w1, y), "Lens", font=wordmark, fill=GREEN + (170,))
    base = Image.alpha_composite(base, glow.filter(ImageFilter.GaussianBlur(int(4 * S))))

    d = ImageDraw.Draw(base)
    d.text((x, y), "Onion", font=wordmark, fill=WHITE)
    d.text((x + w1, y), "Lens", font=wordmark, fill=GREEN)

    d.text((x + int(4 * S), int(230 * S)), "AI correlation over the onion web",
           font=tagline, fill=SLATE)
    d.text((x + int(4 * S), int(286 * S)),
           "> scanning indexed .onion space _",
           font=mono, fill=GREEN)
    d.text((x + int(4 * S), int(324 * S)),
           "passive OSINT   ·   powered by Ahmia   ·   no Tor required",
           font=mono, fill=MUTED)
    return base


def grit(img):
    """Scanlines and film grain over the final RGB frame."""
    arr = np.asarray(img.convert("RGB")).astype("int16")
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 5, arr.shape[:2])
    arr += noise[:, :, None].astype("int16")
    # darken every other output row (2*S rows at supersample scale)
    mask = (np.arange(H) // S) % 2 == 1
    arr[mask] = (arr[mask] * 0.88).astype("int16")
    return Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), "RGB").convert("RGBA")


def main():
    img = background()
    img = glyph_field(img)
    img = radar_sweep(img)
    img = lens_and_graph(img)
    img = grit(img)
    img = text(img)
    img = img.resize((W // S, H // S), Image.LANCZOS)
    img.convert("RGB").save(OUT, "PNG")
    print(f"wrote {OUT} ({img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    main()
