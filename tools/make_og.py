"""Generate the 1200x630 social share card (assets/og-card.png), on-brand.

Reproducible: downloads Space Grotesk (OFL) to a temp file if not already
cached. Run from anywhere:  python tools/make_og.py
Requires Pillow (see backend/requirements.txt).
"""
import os
import tempfile
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "og-card.png"
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf"
FONT_PATH = Path(tempfile.gettempdir()) / "SpaceGrotesk-16lab.ttf"

if not FONT_PATH.exists():
    urllib.request.urlretrieve(FONT_URL, FONT_PATH)

INK = (6, 19, 31)
CREAM = (255, 250, 240)
PAPER = (247, 243, 234)
ORANGE = (255, 106, 0)
BLUE = (67, 167, 255)

W, H = 1200, 630
img = Image.new("RGB", (W, H), PAPER)
d = ImageDraw.Draw(img)


def font(size, weight="Bold"):
    f = ImageFont.truetype(str(FONT_PATH), size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


cx0, cy0, cx1, cy1 = 56, 56, W - 56, H - 56
r = 30
d.rounded_rectangle([cx0 + 16, cy0 + 18, cx1 + 16, cy1 + 18], radius=r, fill=INK)
d.rounded_rectangle([cx0, cy0, cx1, cy1], radius=r, fill=CREAM, outline=INK, width=5)

pad = 60
left, top = cx0 + pad, cy0 + pad

# brand
chip = 84
d.rounded_rectangle([left, top, left + chip, top + chip], radius=18, fill=ORANGE, outline=INK, width=4)
bf = font(46)
d.text((left + (chip - d.textlength("16", font=bf)) / 2, top + 16), "16", font=bf, fill=CREAM)
d.text((left + chip + 20, top + 16), "Lab", font=font(50), fill=INK)
d.text((left + 2, top + chip + 22), "R A P   I N T E L L I G E N C E   L A B", font=font(22), fill=INK)

# headline (auto-fit)
inner = (cx1 - pad) - left
parts = [("Decode ", INK), ("every", ORANGE), (" bar.", INK)]
hsize = 116
while hsize > 60:
    hf = font(hsize)
    if sum(d.textlength(t, font=hf) for t, _ in parts) <= inner:
        break
    hsize -= 2
hf = font(hsize)
hy = top + chip + 88
x = left
for text, col in parts:
    d.text((x, hy), text, font=hf, fill=col)
    x += d.textlength(text, font=hf)

# subline (auto-fit, single line)
subtext = "Lyrics, meaning & wordplay + craft and depth scores — even for freestyles."
ssize = 32
while ssize > 22:
    sf = font(ssize, "Medium")
    if d.textlength(subtext, font=sf) <= inner:
        break
    ssize -= 1
d.text((left + 3, hy + hsize + 32), subtext, font=font(ssize, "Medium"), fill=(40, 55, 70))

# footer
wy = cy1 - pad + 10
ff = font(27)
url = "16labs.xyz"
d.text((left + 3, wy - 33), url, font=ff, fill=INK)
tx = left + 6 + d.textlength(url, font=ff) + 22
for i, hh in enumerate([14, 28, 20, 32, 22]):
    d.rounded_rectangle([tx, wy - 10 - hh, tx + 11, wy - 10], radius=4, fill=[ORANGE, INK, BLUE][i % 3])
    tx += 18
pf = font(21, "Medium")
pby = "Powered by Musixmatch  ·  Claude  ·  ElevenLabs"
d.text((cx1 - pad - d.textlength(pby, font=pf), wy - 22), pby, font=pf, fill=(90, 105, 120))

OUT.parent.mkdir(parents=True, exist_ok=True)
img.save(OUT, "PNG")
print("wrote", OUT, img.size)
