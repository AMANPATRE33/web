"""Deterministic placeholder artwork for the seed catalogue.

Real product artwork cannot be committed and hot-linking the legacy site's CDN
would make the rebuild depend on a third party. So the seed *generates* its own
placeholder: an abstract safety-sign board per product, in the correct signal
colour for its category.

The colours are the real signage convention, not decoration:

    yellow  = caution / warning      ISO 7010 W
    red     = danger / prohibition   ISO 7010 W (danger) / P (prohibition)
    blue    = mandatory / directional ISO 7010 M
    green   = safe condition / first aid ISO 7010 E

That matters even for placeholders: a wall of generated boards still teaches the
correct colour association, so the seed does not accidentally normalise a wrong
one during design review.

Every file lands at ``public/seed/<category>/<sku>.svg`` and the database stores
that path. Replacing placeholders with real photography means uploading to
Supabase Storage and updating ``product_images.url`` - no code change.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

ShapeName = str

#: Signal colour -> (background, border, glyph). Values chosen for contrast
#: against a white glyph at large sizes, which is the actual requirement.
SIGNAL_COLOURS: dict[str, tuple[str, str, str]] = {
    "yellow": ("#F2C200", "#1A1A1A", "#1A1A1A"),
    "red": ("#C8102E", "#8C0A20", "#FFFFFF"),
    "blue": ("#0057B8", "#003E80", "#FFFFFF"),
    "green": ("#0E7A3C", "#0A5528", "#FFFFFF"),
    "white": ("#F5F5F2", "#1A1A1A", "#1A1A1A"),
    "black": ("#1A1A1A", "#000000", "#FFFFFF"),
}

#: Abstract glyphs. Intentionally generic - a triangle, a bolt, a cross, a
#: flame - so nothing here resembles a real sign design or a trademark.
_GLYPHS: dict[str, str] = {
    "triangle": "M300,120 L480,440 L120,440 Z",
    "diamond": "M300,110 L490,300 L300,490 L110,300 Z",
    "circle": "M300,300 m-190,0 a190,190 0 1,0 380,0 a190,190 0 1,0 -380,0",
    "bolt": "M340,120 L200,320 h90 l-40,160 L390,270 h-90 Z",
    "cross": "M270,180 L330,180 L330,270 L420,270 L420,330 L330,330 L330,420 "
    "L270,420 L270,330 L180,330 L180,270 L270,270 Z",
    "flame": "M300,150 c60,80 110,120 110,190 a110,110 0 0,1 -220,0 c0,-50 30,-80 60,-120 "
    "c10,30 30,50 50,50 c0,-40 -10,-80 -0,-120 Z",
    "flask": "M265,120 L265,250 L175,450 a40,40 0 0,0 35,60 L390,510 a40,40 0 0,0 35,-60 "
    "L335,250 L335,120 M250,120 L350,120",
    "arrow": "M170,300 L430,300 M340,210 L430,300 L340,390",
    "person": "M300,180 m-55,0 a55,55 0 1,0 110,0 a55,55 0 1,0 -110,0 "
    "M170,470 C170,370 230,320 300,320 C370,320 430,370 430,470",
    "shield": "M300,110 L450,170 L450,320 C450,400 380,470 300,500 "
    "C220,470 150,400 150,320 L150,170 Z",
    "ear": "M340,180 a110,110 0 1,0 -80,180 l-30,60 a30,30 0 0,0 50,30 M250,360 a90,90 0 0,0 90,90",
    "goggles": "M130,300 a70,70 0 1,0 140,0 a70,70 0 1,0 -140,0 "
    "M330,300 a70,70 0 1,0 140,0 a70,70 0 1,0 -140,0 M270,300 L330,300",
    "helmet": "M160,380 C160,250 220,180 300,180 C380,180 440,250 440,380 L440,410 "
    "L160,410 Z M160,340 L440,340",
    "hand": "M200,470 L200,300 L160,300 a30,30 0 0,1 0,-60 L200,240 L200,170 "
    "a28,28 0 0,1 56,0 L256,240 L256,150 a28,28 0 0,1 56,0 L312,250 "
    "L312,180 a28,28 0 0,1 56,0 L368,300 L430,360 a40,40 0 0,1 -50,60 "
    "L330,470 Z",
    "boot": "M180,180 L280,180 L280,340 L430,400 a40,40 0 0,1 30,40 L180,440 Z",
    "fire": "M300,120 C340,190 400,230 400,320 a100,100 0 0,1 -200,0 "
    "c0,-60 30,-100 60,-150 c10,40 30,60 50,60 c0,-50 -10,-100 0,-110 Z",
    "eye": "M120,300 C180,230 240,210 300,210 C360,210 420,230 480,300 "
    "C420,370 360,390 300,390 C240,390 180,370 120,300 Z "
    "M300,300 m-55,0 a55,55 0 1,0 110,0 a55,55 0 1,0 -110,0",
    "leaf": "M300,120 C420,180 460,280 430,390 C400,500 280,530 210,470 "
    "C140,410 160,290 220,220 C260,170 280,150 300,120 Z "
    "M300,140 L300,470",
}

#: Which glyph a category reads as, so a place full of placeholders still looks
#: like a catalogue rather than a colour swatch test.
_CATEGORY_GLYPH: dict[str, str] = {
    "msds": "flask",
    "ppe": "helmet",
    "caution-signages": "triangle",
    "danger-signages": "diamond",
    "5s-methodology": "shield",
    "electrical-safety": "bolt",
    "directional-signages": "arrow",
    "emergency-signages": "arrow",
    "envirnomental-signages": "leaf",
    "health-safety": "cross",
    "fire-safety": "fire",
    "motivational-signages": "shield",
    "lab-safety": "flask",
    "office-signages": "person",
    "quality-productivity": "shield",
    "road-safety": "triangle",
    "canteen": "hand",
    "pylon-boards": "arrow",
}


def _seed_int(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16)


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


@dataclass(slots=True)
class GeneratedImage:
    path: str  # URL path, e.g. /seed/electrical-safety/SPP-ELS-001.svg
    alt_text: str
    width: int = 800
    height: int = 800


def _sign_frame(
    *,
    signal: str,
    glyph: str,
    label: str,
    sku: str,
    size_label: str,
    material: str,
    variant_index: int,
) -> str:
    """Render one placeholder board.

    The composition is a sign board on a studio backdrop: a bordered rectangle
    in the signal colour with the category glyph, plus a caption strip carrying
    the SKU, size and material. Those three facts are what a shopper chooses on,
    so they appear on the placeholder rather than being hidden in metadata.
    """
    background, border, glyph_fill = SIGNAL_COLOURS.get(signal, SIGNAL_COLOURS["white"])
    path_data = _GLYPHS.get(glyph, _GLYPHS["triangle"])
    glyph_fill = _xml_escape(glyph_fill)

    # Gallery frames differ by camera angle and crop, so a product gallery shows
    # four genuinely different images rather than the same one repeated.
    scale = (1.0, 0.88, 1.08, 0.96)[variant_index % 4]
    rotate = (0, -6, 5, -2)[variant_index % 4]
    backdrop = (0.0, -0.06, 0.06, 0.0)[variant_index % 4]
    show_caption = variant_index % 2 == 0

    caption = ""
    if show_caption:
        caption = f"""
  <rect x="0" y="672" width="800" height="128" fill="{background}" opacity="0.92"/>
  <text x="40" y="722" font-family="ui-monospace, SFMono-Regular, monospace"
        font-size="24" letter-spacing="2.4" fill="{glyph_fill}" opacity="0.95">
    {sku}  ·  {size_label}
  </text>
  <text x="40" y="762" font-family="ui-sans-serif, system-ui, sans-serif"
        font-size="21" letter-spacing="1.6" fill="{glyph_fill}" opacity="0.8">
    {_xml_escape(material)}
  </text>"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800"
     viewBox="0 0 800 800" role="img" aria-label="{_xml_escape(label)}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0.6" y2="1">
      <stop offset="0%" stop-color="#1B1D21"/>
      <stop offset="100%" stop-color="#0E0F12"/>
    </linearGradient>
    <filter id="drop" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="14" stdDeviation="18" flood-color="#000000"
                    flood-opacity="0.45"/>
    </filter>
  </defs>

  <rect width="800" height="800" fill="url(#bg)"/>
  <rect width="800" height="800" fill="#FFFFFF" opacity="{backdrop * 0.5:.3f}"/>

  <g transform="translate(400 330) rotate({rotate}) scale({scale}) translate(-300 -300)"
     filter="url(#drop)">
    <rect x="80" y="60" width="440" height="500" rx="8"
          fill="{background}" stroke="{border}" stroke-width="10"/>
    <rect x="104" y="84" width="392" height="452" rx="4"
          fill="none" stroke="{glyph_fill}" stroke-width="3" opacity="0.35"/>
    <g transform="translate(0 10)" fill="none" stroke="{glyph_fill}"
       stroke-width="20" stroke-linecap="round" stroke-linejoin="round"
       opacity="0.95">
      <path d="{path_data}"/>
    </g>
  </g>
{caption}
  <text x="40" y="60" font-family="ui-sans-serif, system-ui, sans-serif"
        font-size="17" letter-spacing="3.2" fill="#FFFFFF" opacity="0.42">
    PLACEHOLDER ARTWORK
  </text>
  <text x="760" y="60" text-anchor="end"
        font-family="ui-sans-serif, system-ui, sans-serif" font-size="17"
        letter-spacing="2.4" fill="{background}" opacity="0.7">
    {_xml_escape(label[:28].upper())}
  </text>
</svg>
"""


def generate_product_images(
    *,
    sku: str,
    title: str,
    brand: str,
    shape: ShapeName,
    category_slug: str,
    variant_count: int = 3,
    out_dir: Path,
    signal: str = "yellow",
    size_label: str = "18x24",
    material: str = "ECO VINYL STICKER",
) -> list[GeneratedImage]:
    """Write placeholder frames for one product and return their URL paths."""
    directory = out_dir / category_slug
    directory.mkdir(parents=True, exist_ok=True)

    glyph = _CATEGORY_GLYPH.get(category_slug, shape if shape in _GLYPHS else "triangle")
    label = f"{brand} {title}".strip()[:44]

    images: list[GeneratedImage] = []
    for index in range(max(1, variant_count)):
        filename = f"{sku}.svg" if index == 0 else f"{sku}-{index + 1}.svg"
        (directory / filename).write_text(
            _sign_frame(
                signal=signal,
                glyph=glyph,
                label=label,
                sku=sku,
                size_label=size_label,
                material=material,
                variant_index=index,
            ),
            encoding="utf-8",
        )
        suffix = "" if index == 0 else f" - view {index + 1}"
        images.append(
            GeneratedImage(
                path=f"/seed/{category_slug}/{filename}",
                alt_text=f"{label}{suffix}",
            )
        )
    return images


def generate_category_image(
    *,
    slug: str,
    name: str,
    out_dir: Path,
    signal: str = "yellow",
    width: int = 1200,
    height: int = 800,
) -> str:
    """Write a wide placeholder for a category header."""
    directory = out_dir / slug
    directory.mkdir(parents=True, exist_ok=True)
    background, border, glyph_fill = SIGNAL_COLOURS.get(signal, SIGNAL_COLOURS["white"])
    glyph = _CATEGORY_GLYPH.get(slug, "triangle")
    path_data = _GLYPHS.get(glyph, _GLYPHS["triangle"])

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}" role="img" aria-label="{_xml_escape(name)}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#1B1D21"/>
      <stop offset="100%" stop-color="#0E0F12"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" fill="url(#bg)"/>
  <g transform="translate({width // 2 - 150} {height // 2 - 150}) scale(1.2)">
    <rect x="20" y="20" width="280" height="280" rx="6"
          fill="{background}" stroke="{border}" stroke-width="8"/>
    <g transform="translate(0 20)" fill="none" stroke="{glyph_fill}"
       stroke-width="18" stroke-linecap="round" stroke-linejoin="round">
      <path d="{path_data}"/>
    </g>
  </g>
  <text x="60" y="{height - 70}" font-family="ui-sans-serif, system-ui, sans-serif"
        font-size="40" letter-spacing="3" fill="{background}" opacity="0.85">
    {_xml_escape(name.upper())}
  </text>
  <text x="60" y="{height - 40}" font-family="ui-sans-serif, system-ui, sans-serif"
        font-size="16" letter-spacing="2.6" fill="#FFFFFF" opacity="0.32">
    PLACEHOLDER ARTWORK
  </text>
</svg>
"""
    filename = f"{slug}.svg"
    (directory / filename).write_text(svg, encoding="utf-8")
    return f"/seed/{slug}/{filename}"
