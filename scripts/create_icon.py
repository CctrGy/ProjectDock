"""Genera el icono original: módulos encajados en un dock."""
from pathlib import Path
from PIL import Image, ImageDraw

assets = Path(__file__).resolve().parents[1] / "src/projectdock/assets"
assets.mkdir(parents=True, exist_ok=True)
svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
<rect x="8" y="8" width="240" height="240" rx="56" fill="#101820"/>
<rect x="41" y="76" width="48" height="74" rx="12" fill="#399db5"/>
<rect x="104" y="44" width="48" height="106" rx="12" fill="#68dfbb"/>
<rect x="167" y="91" width="48" height="59" rx="12" fill="#edf5fa"/>
<path d="M42 171v15q0 26 26 26h120q26 0 26-26v-15" fill="none" stroke="#68dfbb" stroke-width="17" stroke-linecap="round"/>
</svg>
"""
(assets / "projectdock.svg").write_text(svg, encoding="utf-8")
scale = 4
image = Image.new("RGBA", (256 * scale, 256 * scale))
draw = ImageDraw.Draw(image)
def box(coords, radius, color):
    draw.rounded_rectangle(tuple(v * scale for v in coords), radius * scale, fill=color)
box((8, 8, 248, 248), 56, "#101820")
box((41, 76, 89, 150), 12, "#399db5")
box((104, 44, 152, 150), 12, "#68dfbb")
box((167, 91, 215, 150), 12, "#edf5fa")
box((34, 163, 222, 220), 27, "#68dfbb")
box((51, 147, 205, 203), 16, "#101820")
image = image.resize((256, 256), Image.Resampling.LANCZOS)
image.save(assets / "projectdock.png")
image.save(assets / "projectdock.ico", sizes=[(s, s) for s in [16, 24, 32, 48, 64, 128, 256]])
