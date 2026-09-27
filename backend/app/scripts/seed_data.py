"""Seed catalogue for **Safety Poster Prints**.

Source of truth for structure and pricing: `docs/REFERENCE_SITE_ANALYSIS.md`,
which records what was read directly from the public site on 2026-09-27.

Three rules govern this file:

1. **No invented business facts.** No fabricated testimonials, review counts,
   customer counts, GSTIN, founding year or staff numbers. The live site shows
   none of these, so the seed shows none. The review and rating systems are
   fully implemented and simply start empty.

2. **Materials and sizes are data.** The four materials and nine sizes are
   rows in module-level constants that seed into the database. Nothing in the
   frontend hard-codes them, so the business can add a material without a
   deploy.

3. **Price is derived, not invented per variant.** A product carries one
   `base_price` - the price of the smallest offered size in eco vinyl. Every
   other variant price is ``base_price * size_ratio * material_ratio``, rounded
   to the nearest rupee. This reproduces the live site's observed spread
   (Electrical Safety: Rs.80 base to Rs.8,800 max) to within a few rupees, and
   it means one number per product is all the business has to maintain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# ===========================================================================
# Materials - VERIFIED from the product page "Available Materials" block
# ===========================================================================
MaterialCode = Literal[
    "ECO VINYL STICKER",
    "AUTOGLOW STICKER",
    "5MM FOAMSHEET",
    "3MM ACP",
]


@dataclass(slots=True)
class SeedMaterial:
    code: str
    #: The site's own positioning copy, reused verbatim so the voice is
    #: consistent with what customers already read.
    description: str
    #: Multiplier applied to the product base price. Ordered cheapest to
    #: dearest; calibrated against the observed Rs.80 -> Rs.8,800 spread.
    ratio: float
    #: Where it belongs. Drives the material guidance on the PDP.
    best_for: str
    #: Material properties surfaced in the specification table.
    specs: dict[str, str]
    position: int = 0
    is_active: bool = True


MATERIALS: list[SeedMaterial] = [
    SeedMaterial(
        code="ECO VINYL STICKER",
        description="Waterproof & weather resistant",
        ratio=1.0,
        best_for=(
            "Smooth indoor surfaces, temporary displays, and any location where "
            "the board may be replaced often. Lowest cost per board."
        ),
        specs={
            "Thickness": "200 micron",
            "Water resistance": "Waterproof",
            "UV life": "2-3 years",
            "Adhesive": "Permanent acrylic",
            "Finish": "Gloss laminate",
            "Installation": "Self adhesive, peel and stick",
        },
        position=1,
    ),
    SeedMaterial(
        code="AUTOGLOW STICKER",
        description="Visible in darkness",
        ratio=1.35,
        best_for=(
            "Corridors, stairwells, power rooms and any area where the lights "
            "may be off. Photoluminescent - charges in daylight, glows for hours."
        ),
        specs={
            "Thickness": "250 micron",
            "Water resistance": "Water resistant",
            "Glow duration": "4-6 hours",
            "Charge": "Natural / UV light",
            "Adhesive": "Permanent acrylic",
            "Installation": "Self adhesive, peel and stick",
        },
        position=2,
    ),
    SeedMaterial(
        code="5MM FOAMSHEET",
        description="Lightweight & economical",
        ratio=1.7,
        best_for=(
            "Indoor display, training rooms, notice boards and areas where the "
            "sign is fixed to a wall rather than free-standing. The standard "
            "budget choice for a room full of boards."
        ),
        specs={
            "Thickness": "5 mm",
            "Core": "PVC foam board",
            "Water resistance": "Indoor use",
            "Weight": "Light - fix with tape or light screws",
            "Finish": "Matt laminate",
            "Installation": "Adhesive or mechanical fixing",
        },
        position=3,
    ),
    SeedMaterial(
        code="3MM ACP",
        description="Durable & long-lasting",
        ratio=2.3,
        best_for=(
            "Plant rooms, outdoor areas, production floors and anywhere the sign "
            "must survive weather, handling and long service intervals. The only"
            " option we recommend for an outdoor board."
        ),
        specs={
            "Thickness": "3 mm",
            "Core": "Aluminium composite panel",
            "Water resistance": "Weatherproof",
            "UV life": "5+ years",
            "Finish": "Matt laminate, riveted corners",
            "Installation": "Standoff, rivet or adhesive",
        },
        position=4,
    ),
]


# ===========================================================================
# Sizes - VERIFIED from the project product brief. Units are inches (W x H)
# ===========================================================================
@dataclass(slots=True)
class SeedSize:
    label: str
    width_in: int
    height_in: int
    #: Position, smallest to largest.
    position: int = 0

    @property
    def area_sq_in(self) -> int:
        return self.width_in * self.height_in


SIZES: list[SeedSize] = [
    SeedSize("8x12", 8, 12, 1),
    SeedSize("12x18", 12, 18, 2),
    SeedSize("18x24", 18, 24, 3),
    SeedSize("24x36", 24, 36, 4),
    SeedSize("30x60", 30, 60, 5),
    SeedSize("36x48", 36, 48, 6),
    SeedSize("36x72", 36, 72, 7),
    SeedSize("48x72", 48, 72, 8),
    SeedSize("48x96", 48, 96, 9),
]

#: The area of the smallest size, which is the baseline for price ratios.
BASE_AREA = SIZES[0].area_sq_in


# ===========================================================================
# Categories - VERIFIED, 18 of them, slugs preserved exactly as live
# ===========================================================================
@dataclass(slots=True)
class SeedCategory:
    name: str
    slug: str
    description: str
    position: int = 0
    #: The live catalogue is a flat 18-category list with no hierarchy, and
    #: the rebuild keeps it flat: inventing a parent/child tree over these 18
    #: would change the IA that already ranks.
    parent_slug: str | None = None
    #: Which size tiers this category is normally sold in. Drives the variant
    #: matrix, so a pylon board is not offered at 8x12.
    size_profile: Literal["sticker", "poster", "sign", "board", "pylon"] = "poster"
    #: The signage colour convention, used for the generated artwork.
    signal: str = "yellow"
    seo_title: str | None = None
    seo_description: str | None = None
    #: Categories that also get a collection page on the homepage.
    is_landing_page: bool = False


#: Signal colours follow the recognised conventions: caution = yellow/black,
#: danger = red/white, mandatory = blue/white, safe condition = green/white.
CATEGORIES: list[SeedCategory] = [
    SeedCategory(
        "MSDS",
        "msds",
        "Material Safety Data Sheet boards for the chemicals handled on your site. "
        "GHS-compliant hazard, precaution and first-aid information at the point of use.",
        position=1,
        size_profile="poster",
        signal="red",
        seo_title="MSDS Posters & Chemical Safety Boards | Safety Poster Prints",
        seo_description="Material Safety Data Sheet posters for Caustic Soda, Toluene, "
        "Chlorine and more. GHS-compliant chemical hazard boards on ACP, foam sheet or vinyl.",
    ),
    SeedCategory(
        "PPE",
        "ppe",
        "Personal Protective Equipment signage. Mandatory-use boards that state exactly "
        "which equipment is required in which area, in a language the worker reads.",
        position=2,
        size_profile="poster",
        signal="blue",
        seo_title="PPE Safety Posters & Mandatory Signage | Safety Poster Prints",
        seo_description=(
            "Personal protective equipment signs - helmets, goggles, gloves, harness and more. "
            "Blue mandatory signage printed on ACP, foam sheet, vinyl or autoglow sticker."
        ),
    ),
    SeedCategory(
        "Caution Signages",
        "caution-signages",
        "Caution boards for hazards that cause minor or moderate injury. Yellow background, "
        "black pictogram, black text - the convention workers already recognise.",
        position=3,
        size_profile="sign",
        signal="yellow",
        seo_title="Caution Signages & Warning Boards | Safety Poster Prints",
        seo_description="Caution safety signs for wet floors, overhead work, hot surfaces and "
        "heavy machinery. Yellow and black boards in ACP, foam sheet and vinyl.",
    ),
    SeedCategory(
        "Danger Signages",
        "danger-signages",
        "Danger boards for immediate, life-threatening hazards. Red background with white "
        "symbols and text, in line with ISO 3864 and factory signage standards.",
        position=4,
        size_profile="sign",
        signal="red",
        seo_title="Danger Signages & Red Warning Boards | Safety Poster Prints",
        seo_description="Danger signage for high voltage, toxic gas, flammable material and "
        "restricted areas. ISO 3864 compliant red and white boards.",
    ),
    SeedCategory(
        "5S Methodology",
        "5s-methodology",
        "The five pillars of workplace organisation, one board per step. Sort, Set in "
        "Order, Shine, Standardise, Sustain - each with its own definition and standard.",
        position=5,
        size_profile="poster",
        signal="green",
        seo_title="5S Methodology Posters - Seiri to Shitsuke | Safety Poster Prints",
        seo_description="Complete 5S workplace organisation poster set. Seiri, Seiton, Seiso, "
        "Seiketsu and Shitsuke boards for factories, plants and warehouses.",
        is_landing_page=True,
    ),
    SeedCategory(
        "Electrical Safety",
        "electrical-safety",
        "Boards for panel rooms, distribution areas and high-voltage installations. "
        "Multilingual options for shops with a multilingual workforce.",
        position=6,
        size_profile="sign",
        signal="red",
        seo_title="Electrical Safety Signs & Posters | Safety Poster Prints",
        seo_description="Electrical safety signage - danger high voltage, shock hazard, keep area "
        "in front of panel clear. Multilingual boards printed on ACP and vinyl.",
    ),
    SeedCategory(
        "Directional Signages",
        "directional-signages",
        "Arrows, exit routes, assembly points and wayfinding boards. Directional boards are "
        "the most-read signage on any site and the cheapest to get wrong.",
        position=7,
        size_profile="sign",
        signal="blue",
        seo_title="Directional Signage & Wayfinding Boards | Safety Poster Prints",
        seo_description="Directional signs, arrows, emergency exit routes and assembly point "
        "boards. Photoluminescent and standard options.",
    ),
    SeedCategory(
        "Emergency Signages",
        "emergency-signages",
        "Exit routes, muster points, first aid stations and emergency equipment. Autoglow "
        "options for areas that lose power.",
        position=8,
        size_profile="sign",
        signal="green",
        seo_title="Emergency Signage & Exit Route Boards | Safety Poster Prints",
        seo_description="Emergency exit, assembly point, first aid and fire equipment signage "
        "including photoluminescent options for power-loss conditions.",
    ),
    SeedCategory(
        "Environmental Signages",
        "envirnomental-signages",
        "Waste segregation, water and energy conservation, and green-zone boards for "
        "sustainable operation certifications.",
        position=9,
        size_profile="poster",
        signal="green",
        # NOTE: the live slug is misspelled ("envirnomental"). It is preserved
        # deliberately for SEO. The display name is corrected.
        seo_title="Environmental Safety Signage & Posters | Safety Poster Prints",
        seo_description="Environmental signage for waste segregation, water conservation, "
        "switch-off reminders and green belt boards.",
    ),
    SeedCategory(
        "Health Safety",
        "health-safety",
        "Hygiene, wellness and health-protocol boards for workplaces, canteens and "
        "high-footfall public areas.",
        position=10,
        size_profile="poster",
        signal="blue",
    ),
    SeedCategory(
        "Fire Safety",
        "fire-safety",
        "Exit routes, extinguisher identification, muster points and fire emergency "
        "procedure boards. The single most audited category on any site.",
        position=11,
        size_profile="sign",
        signal="red",
        seo_title="Fire Safety Signs & Posters | Safety Poster Prints",
        seo_description="Fire safety signage - fire exit, extinguisher location, assembly point "
        "and emergency procedure boards for factories and warehouses.",
    ),
    SeedCategory(
        "Motivational Signages",
        "motivational-signages",
        "Safety-first and quality-at-source boards for shop floors, where a wall of "
        "instructional signage stops being read.",
        position=12,
        size_profile="poster",
        signal="blue",
    ),
    SeedCategory(
        "Lab Safety",
        "lab-safety",
        "Laboratory-specific boards: chemical hazard, eye wash, emergency shower, "
        "protective equipment and no-food rules.",
        position=13,
        size_profile="poster",
        signal="red",
    ),
    SeedCategory(
        "Office Signages",
        "office-signages",
        "Exit, first aid, floor directories and facility boards for offices and "
        "commercial buildings.",
        position=14,
        size_profile="sticker",
        signal="blue",
    ),
    SeedCategory(
        "Quality & Productivity",
        "quality-productivity",
        "Cost of poor quality, quality circles, productivity tools and the "
        "National Safety Week series.",
        position=15,
        size_profile="poster",
        signal="blue",
    ),
    SeedCategory(
        "Road Safety",
        "road-safety",
        "Speed limits, no-horn, road-closed, school zone and pedestrian crossing "
        "boards for internal roads, yards and gates.",
        position=16,
        size_profile="sign",
        signal="red",
    ),
    SeedCategory(
        "Canteen",
        "canteen",
        "Canteen hygiene and housekeeping boards - handwash, cleanliness, caps, "
        "no smoking, and food waste.",
        position=17,
        size_profile="poster",
        signal="green",
    ),
    SeedCategory(
        "Outdoor Pylon Signage Board",
        "pylon-boards",
        "Free-standing pylon and bollard boards for outdoor areas, traffic control "
        "and pedestrian management outside the building envelope.",
        position=18,
        size_profile="pylon",
        signal="yellow",
        seo_title="Outdoor Pylon Signage Boards & Bollards | Safety Poster Prints",
        seo_description="Free-standing outdoor pylon signage boards, corner pylons and "
        "traffic bollards printed on 3mm ACP for outdoor durability.",
    ),
]

#: Size tiers per profile. Keeps the variant matrix realistic: a pylon board is
#: not sold at 8x12, and an office sticker is not sold at 48x96.
SIZE_PROFILES: dict[str, list[str]] = {
    "sticker": ["8x12", "12x18", "18x24"],
    "poster": ["12x18", "18x24", "24x36"],
    "sign": ["12x18", "18x24", "24x36", "36x48"],
    "board": ["18x24", "24x36", "36x48", "48x72"],
    "pylon": ["24x36", "36x48", "36x72", "48x72", "48x96"],
}


# ===========================================================================
# Products
# ===========================================================================
@dataclass(slots=True)
class SeedProduct:
    title: str
    #: The live slug, preserved so the 301 keeps link equity. The duplicate
    #: `-1` Wix suffixes seen on the live site are dropped during import.
    slug: str
    sku: str
    category_slug: str
    short_description: str
    description: str
    #: Price in minor units for the smallest offered size in eco vinyl.
    base_price: int
    compare_at_price: int | None = None
    specs: dict[str, str] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    applications: tuple[str, ...] = ()
    featured: bool = False
    hsn_code: str = "4911"  # Printed matter; overridden per material at invoice time.
    #: Sizes to offer, overriding the category profile.
    size_labels: tuple[str, ...] | None = None
    #: Materials to offer, overriding the default of all four.
    material_codes: tuple[str, ...] | None = None
    #: Fraction of a variant in stock. 0.0 makes a whole material sold out, which
    #: is how the sold-out UI states get exercised.
    stock_ratio: float = 1.0
    #: Per-variant stock levels, keyed by material code.
    stock_by_material: dict[str, int] = field(default_factory=dict)
    #: Marks a product that is also a collection entry point on the homepage.
    is_landing_page: bool = False


# --- MSDS (52 on the live site; 12 represented here) ------------------------
_MSDS: list[SeedProduct] = [
    SeedProduct(
        "MSDS of Caustic Soda",
        "msds-of-caustic-soda",
        "SPP-MSDS-001",
        "msds",
        "GHS-compliant safety data board for Caustic Soda (Sodium Hydroxide).",
        "Caustic Soda is the most widely handled corrosive in Indian chemical "
        "plants, and the one that causes the most eye injuries, because it is "
        "clear and looks like water.\n\n"
        "This board carries the GHS pictograms for skin corrosion, serious eye "
        "damage and metal corrosion, the signal word, the hazard statements and "
        "the first-aid measures, laid out so a worker who has just been splashed "
        "can find the flush instruction without reading a paragraph.\n\n"
        "Print the board in 3MM ACP if it is mounted in the plant room, or in "
        "eco vinyl if it is a handout for contractors.",
        32000,
        specs={
            "GHS rev": "Rev 7 (2023)",
            "Pictograms": "Corrosive, exclamation",
            "Signal word": "Danger",
            "UN number": "UN 1823",
            "CAS number": "1310-73-2",
            "Form": "Solid / solution",
        },
        tags=("msds", "chemical", "corrosive", "ghs"),
        applications=("Chemical plant", "Dosing room", "Tank farm", "Laboratory"),
    ),
    SeedProduct(
        "MSDS of Mono Ethyle Amine",
        "msds-of-mono-ethyle-amine",
        "SPP-MSDS-002",
        "msds",
        "Safety data board for Mono Ethylamine, a corrosive and flammable amine.",
        "Mono Ethylamine is both a skin corrosive and a flammable gas - two "
        "hazard classes on one board, which is why it is stored in bonded "
        "storage under inert cover.\n\n"
        "The board shows the corrosive and environmental pictograms, the "
        "flammability band for the flash point, and the incompatibility note "
        "for strong oxidisers.\n\n"
        "The title follows the spelling used on the live catalogue. The correct "
        "IUPAC name is monoethylamine; both are recorded in the import report.",
        32000,
        specs={
            "GHS rev": "Rev 7 (2023)",
            "Pictograms": "Corrosive, environment",
            "Signal word": "Danger",
            "CAS number": "75-04-7",
            "Flash point": "-20 C (closed cup)",
            "Form": "Liquefied gas",
        },
        tags=("msds", "chemical", "corrosive", "flammable", "ghs"),
        applications=("Chemical plant", "Process area", "Bulk storage"),
    ),
    SeedProduct(
        "MSDS of DMSO",
        "msds-of-dmso",
        "SPP-MSDS-003",
        "msds",
        "Safety data board for Dimethyl Sulphoxide (DMSO).",
        "DMSO penetrates skin rapidly and carries dissolved material with it, "
        "which makes the absorption route the one that matters.\n\n"
        "The board covers the irritant classification, the combustible-liquid "
        "band, and the handling note about avoiding prolonged skin contact.\n\n"
        "Useful in pharmaceutical and electronics manufacturing, where DMSO is "
        "handled in quantity but rarely in a dedicated area.",
        32000,
        specs={
            "GHS rev": "Rev 7 (2023)",
            "Pictograms": "Exclamation",
            "Signal word": "Warning",
            "CAS number": "67-68-5",
            "Flash point": "95 C (closed cup)",
            "Form": "Liquid",
        },
        tags=("msds", "chemical", "solvent", "ghs"),
        applications=("Pharmaceutical plant", "Laboratory", "Electronics"),
    ),
    SeedProduct(
        "MSDS of Bromine",
        "msds-of-bromine-1",
        "SPP-MSDS-004",
        "msds",
        "Safety data board for Bromine, a severe skin and respiratory irritant.",
        "Liquid bromine is a severe skin and respiratory irritant that is also "
        "corrosive to metals, and it is one of the few materials where the "
        "inhalation route is as serious as the skin route.\n\n"
        "The board carries the corrosion and environment pictograms and the "
        "severe eye damage classification.\n\n"
        "Bromine requires secondary containment and a dedicated escape route, "
        "which the board's emergency measures section reflects.",
        32000,
        specs={
            "GHS rev": "Rev 7 (2023)",
            "Pictograms": "Corrosive, environment",
            "Signal word": "Danger",
            "UN number": "UN 1714",
            "CAS number": "7726-95-6",
            "Boiling point": "58.8 C",
        },
        tags=("msds", "chemical", "corrosive", "toxic", "ghs"),
        applications=("Chemical plant", "Water treatment", "Process area"),
    ),
    SeedProduct(
        "MSDS of Chlorine",
        "msds-of-chlorine-1",
        "SPP-MSDS-005",
        "msds",
        "Safety data board for Chlorine gas and liquefied chlorine.",
        "Chlorine is a toxic gas with an occupational exposure limit in parts per "
        "million, so the board's job is to state the limit and the action.\n\n"
        "The board shows the gas mask silhouette, the acute toxicity pictogram, "
        "and the evacuation and shelter-in-place distinction - the decision "
        "workers have to make in the first sixty seconds.\n\n"
        "Mount this at the chlorination room entrance, not inside it.",
        32000,
        specs={
            "GHS rev": "Rev 7 (2023)",
            "Pictograms": "Skull and crossbones, environment",
            "Signal word": "Danger",
            "UN number": "UN 1017",
            "CAS number": "7782-50-5",
            "OEL": "1 ppm (8 h TWA)",
        },
        tags=("msds", "chemical", "toxic", "gas", "ghs"),
        applications=("Water treatment", "Chlorination room", "Process plant"),
    ),
    SeedProduct(
        "MSDS of Hexene",
        "msds-of-hexene-1",
        "SPP-MSDS-006",
        "msds",
        "Safety data board for 1-Hexene.",
        "1-Hexene is a highly flammable liquid with a very low flash point and "
        "a characteristic odour that reliably indicates the atmosphere is "
        "already in the flammable range.\n\n"
        "The board carries the flame pictogram, the flammable-liquid band, and "
        "the storage incompatibility note for strong oxidisers and halogens.\n\n"
        "Printed small, this works well as a bench card in a polymer plant.",
        32000,
        specs={
            "GHS rev": "Rev 7 (2023)",
            "Pictograms": "Flame",
            "Signal word": "Danger",
            "UN number": "UN 2035",
            "CAS number": "592-41-6",
            "Flash point": "-20 C (closed cup)",
        },
        tags=("msds", "chemical", "flammable", "ghs"),
        applications=("Polymer plant", "Laboratory", "Process area"),
    ),
    SeedProduct(
        "MSDS of Toluene",
        "msds-of-toluene-1",
        "SPP-MSDS-007",
        "msds",
        "Safety data board for Toluene, a flammable aromatic solvent.",
        "Toluene is a routine solvent in printing, paint and pharmaceutical "
        "work, and its vapour is heavier than air, so it collects in low areas "
        "and pits - a point worth making on the board itself.\n\n"
        "The board shows the flammable and health hazard pictograms, the "
        "exposure limits, and the requirement for local exhaust ventilation.\n\n"
        "Commonly required in any area with a solvent store.",
        32000,
        specs={
            "GHS rev": "Rev 7 (2023)",
            "Pictograms": "Flame, exclamation",
            "Signal word": "Danger",
            "UN number": "UN 1294",
            "CAS number": "108-88-3",
            "OEL": "200 ppm (skin) TWA",
        },
        tags=("msds", "chemical", "flammable", "solvent", "ghs"),
        applications=("Printing", "Paint shop", "Pharmaceutical plant"),
    ),
    SeedProduct(
        "MSDS of Propionic Acid",
        "msds-of-propionic-acid-1",
        "SPP-MSDS-008",
        "msds",
        "Safety data board for Propionic Acid.",
        "Propionic acid is a corrosive liquid with a pungent odour, handled in "
        "volume in food, pharmaceutical and chemical intermediates.\n\n"
        "The board carries the corrosive pictogram, the severity of eye damage, "
        "and the storage requirement for a ventilated, corrosion-resistant area "
        "with an eyewash within ten metres.",
        32000,
        specs={
            "GHS rev": "Rev 7 (2023)",
            "Pictograms": "Corrosive",
            "Signal word": "Danger",
            "UN number": "UN 1848",
            "CAS number": "79-09-4",
            "Form": "Liquid",
        },
        tags=("msds", "chemical", "corrosive", "ghs"),
        applications=("Food processing", "Pharmaceutical plant", "Chemical plant"),
    ),
    SeedProduct(
        "MSDS of OPDA",
        "msds-of-opda",
        "SPP-MSDS-009",
        "msds",
        "Safety data board for o-Phenylenediamine (OPDA).",
        "OPDA is a skin sensitiser, which means the risk builds across shifts "
        "rather than appearing in one - the reason sensitiser labelling matters "
        "more than acute toxicity on a board.\n\n"
        "The board carries the exclamation mark, the sensitiser statement, and "
        "the respiratory and glove guidance.\n\n"
        "This is a hazard the operator feels only after several exposures, so "
        "the board is more useful at the point of handling than in a file.",
        32000,
        specs={
            "GHS rev": "Rev 7 (2023)",
            "Pictograms": "Exclamation, health hazard",
            "Signal word": "Warning",
            "UN number": "UN 3077",
            "CAS number": "95-54-5",
            "Class": "Skin sensitiser Category 1",
        },
        tags=("msds", "chemical", "sensitiser", "ghs"),
        applications=("Dye house", "Chemical plant", "Laboratory"),
    ),
    SeedProduct(
        "MSDS of Ethylene Dichloride",
        "msds-of-ethylene-dichloride-2",
        "SPP-MSDS-010",
        "msds",
        "Safety data board for 1,2-Dichloroethane (EDC).",
        "EDC is a suspected carcinogen and a flammable liquid. Where it is "
        "handled, respirable exposure control and closed transfer are the "
        "baseline, and the board should say so plainly.\n\n"
        "The board shows the health hazard silhouette, the flammable band, and "
        "the closed-system requirement.\n\n"
        "Note the live catalogue also carries a slug variant without the -2 "
        "suffix; both are recorded in the import report as duplicates.",
        32000,
        specs={
            "GHS rev": "Rev 7 (2023)",
            "Pictograms": "Health hazard, flame, exclamation",
            "Signal word": "Danger",
            "UN number": "UN 1155",
            "CAS number": "107-06-2",
            "Class": "Carcinogen Category 1B",
        },
        tags=("msds", "chemical", "carcinogen", "flammable", "ghs"),
        applications=("Chemical plant", "Solvent store", "Process area"),
    ),
    SeedProduct(
        "MSDS of HCL",
        "msds-of-hcl",
        "SPP-MSDS-011",
        "msds",
        "Safety data board for Hydrochloric Acid.",
        "Hydrochloric acid is present in almost every process plant and is the "
        "material most likely to cause a chemical eye injury in a small "
        "workshop.\n\n"
        "The board leads with the corrosive pictogram, the eye damage severity, "
        "and the fifteen-minute immediate flush requirement for eye contact.\n\n"
        "Print in ACP and mount at eye level near every point of use, not in a "
        "central file.",
        32000,
        specs={
            "GHS rev": "Rev 7 (2023)",
            "Pictograms": "Corrosive",
            "Signal word": "Danger",
            "UN number": "UN 1789",
            "CAS number": "7647-01-0",
            "Concentration": "32% typical",
        },
        tags=("msds", "chemical", "corrosive", "ghs"),
        applications=("Process plant", "Laboratory", "Etching area"),
    ),
    SeedProduct(
        "MSDS of Cyanuric Acid",
        "msds-of-cyanuric-acid",
        "SPP-MSDS-012",
        "msds",
        "Safety data board for Cyanuric Acid, a chlorine-releasing agent.",
        "Cyanuric acid is used in chlorine stabilisation and reacts with water "
        "to release hypochlorous acid, so it is both corrosive and a source of "
        "residual chlorine.\n\n"
        "The board shows the corrosive and environment pictograms, and the "
        "requirement for storage away from any chloride or hypochlorite product.",
        32000,
        specs={
            "GHS rev": "Rev 7 (2023)",
            "Pictograms": "Corrosive, environment",
            "Signal word": "Warning",
            "UN number": "Not regulated for transport",
            "CAS number": "108-80-5",
            "Form": "Solid",
        },
        tags=("msds", "chemical", "corrosive", "water-treatment", "ghs"),
        applications=("Water treatment", "Chemical plant", "Bulk store"),
    ),
]

# --- Electrical Safety (10 on the live site, all VERIFIED names) ------------
_ELECTRICAL: list[SeedProduct] = [
    SeedProduct(
        "Electrical Safety Guide Multilingual",
        "electrical-safety-guide-multilingual",
        "SPP-ELS-001",
        "electrical-safety",
        "A single board covering basic electrical safety, printed with the key "
        "points in multiple Indian languages.",
        "India has no single workplace language, and an electrical room in "
        "Nashik and one in Ludhiana may have entirely different workforces. A "
        "board that is only in English does not communicate with the people who "
        "most need it to.\n\n"
        "This guide carries the essential electrical safety points - isolate, "
        "lock out, test for dead, earth, prove - in English plus Hindi, Marathi "
        "and Gujarati on the same board, with a consistent icon set so the "
        "meaning survives even where the text is not read.\n\n"
        "Print at 24x36 or larger for a panel room. Below 18x24 the four "
        "languages stop being legible.",
        8000,
        specs={
            "Languages": "English, Hindi, Marathi, Gujarati",
            "Format": "Step sequence with icons",
            "Recommended size": "24x36 and above",
            "Material note": "ACP for panel rooms",
        },
        size_labels=("18x24", "24x36", "36x48"),
        tags=("electrical", "multilingual", "training", "panel-room"),
        applications=("Panel room", "Substation", "Training room"),
        featured=True,
    ),
    SeedProduct(
        "Area In Front Of Electrical Panel",
        "area-in-front-of-electrical-panel",
        "SPP-ELS-002",
        "electrical-safety",
        "Keep-clear board for the working space in front of an electrical panel.",
        "The working space in front of a panel is where an electrician needs to "
        "stand, kneel and withdraw, and storing anything in it is one of the "
        "most common findings in an electrical audit.\n\n"
        "This board marks the area as a keep-clear zone, states the minimum "
        "clearance expectation, and warns against blocking access during an "
        "emergency.\n\n"
        "Photoluminescent versions are worth considering for areas that lose "
        "power, where finding the panel in the dark is the whole problem.",
        8000,
        specs={
            "Clearance": "As per site electrical standard",
            "Format": "Keep clear zone outline",
            "Photoluminescent option": "Yes",
        },
        tags=("electrical", "keep-clear", "audit", "panel-room"),
        applications=("Panel room", "Distribution board", "Substation"),
    ),
    SeedProduct(
        "Do Not Use Mobile Phones",
        "do-not-use-mobile-phones",
        "SPP-ELS-003",
        "electrical-safety",
        "Prohibition board for mobile phones in high-voltage and hazardous areas.",
        "Phones are a genuine ignition source in a classified area, and in "
        "practice the reason is a phone left on a bench rather than a deliberate "
        "violation.\n\n"
        "This prohibition board states the rule plainly and pairs it with the "
        "practical alternative - the site landline or radio - which is what "
        "actually changes behaviour.\n\n"
        "Red circle with diagonal bar, in line with ISO 3864-1 prohibition "
        "signs.",
        8000,
        specs={
            "Sign type": "Prohibition (red circle, diagonal bar)",
            "Standard": "ISO 3864-1",
            "Recommended size": "12x18 and above",
        },
        tags=("electrical", "prohibition", "hazardous-area", "ehs"),
        applications=("Substation", "Hazardous area", "Control room"),
    ),
    SeedProduct(
        "Electrical Shock Hazard Do Not Touch",
        "electrical-shock-hazard-do-not-touch",
        "SPP-ELS-004",
        "electrical-safety",
        "Electric shock hazard board with a do-not-touch instruction.",
        "A shock hazard board has one job: stop a person putting their hand on "
        "something live. That means the hazard has to be legible at the distance "
        "someone is actually standing when they decide to reach out.\n\n"
        "This board uses the standard bolt-within-triangle hazard symbol at a "
        "size that survives a plant floor, with a do-not-touch instruction "
        "beneath it rather than a paragraph.\n\n"
        "Autoglow options are available for equipment that is live in low light.",
        8000,
        specs={
            "Sign type": "Warning",
            "Hazard symbol": "ISO 7010 W012 electric shock",
            "Photoluminescent option": "Yes",
        },
        tags=("electrical", "shock", "warning", "panel-room"),
        applications=("Panel room", "Machine bay", "Substation"),
        featured=True,
    ),
    SeedProduct(
        "Electric Shock Survival",
        "electric-shock-survival",
        "SPP-ELS-005",
        "electrical-safety",
        "What to do for a person who has received an electric shock.",
        "Most first aid for electrical shock is about what *not* to do: do not "
        "touch the casualty while they are in contact with the source, and do "
        "not give mouth-to-mouth until the source is isolated.\n\n"
        "This board covers isolation, emergency services, CPR once safe, and "
        "the thermal burn that needs cooling - in sequence, because in an "
        "emergency people read top-down and act immediately.\n\n"
        "A first aid box on its own does not help if nobody knows the sequence.",
        8000,
        specs={
            "Format": "Numbered action sequence",
            "Sections": "Isolate, Call, CPR, Burns",
            "Recommended size": "18x24 and above",
        },
        size_labels=("12x18", "18x24", "24x36"),
        tags=("electrical", "first-aid", "emergency", "training"),
        applications=("First aid point", "Panel room", "Workshop"),
    ),
    SeedProduct(
        "Danger High Voltage",
        "danger-high-voltage",
        "SPP-ELS-006",
        "electrical-safety",
        "The standard danger high voltage board for live equipment.",
        "The single most recognisable board in any electrical installation, and "
        "the one most often replaced with a printed sheet that curls and fades "
        "within a year.\n\n"
        "This is the ISO 7010 W012 danger variant on a rigid substrate, so it "
        "stays flat and readable in a hot panel room. In 3MM ACP it is a "
        "permanent fix; the autoglow version is for areas that lose power.\n\n"
        "State the voltage on the board where you can - a generic board is a "
        "last resort.",
        8000,
        specs={
            "Sign type": "Danger",
            "Hazard symbol": "ISO 7010 W012 electric shock",
            "Standard": "ISO 3864-1",
            "Photoluminescent option": "Yes",
        },
        tags=("electrical", "danger", "high-voltage", "iso7010"),
        applications=("Substation", "Panel room", "Transformer yard"),
        featured=True,
    ),
    SeedProduct(
        "Risk of Electric Shock",
        "risk-of-electric-shock",
        "SPP-ELS-007",
        "electrical-safety",
        "Risk assessment board for areas where a shock risk remains after controls.",
        "Where a residual risk remains after controls are applied, the risk has "
        "to stay visible on the board rather than only in a file.\n\n"
        "This board presents the residual risk, the existing control measures, "
        "and the required PPE in one place - the format most site risk "
        "assessments ask for.\n\n"
        "Use it where a full formal risk assessment is overkill but a warning "
        "is not sufficient.",
        8000,
        specs={
            "Format": "Risk, control, PPE",
            "Audience": "All personnel in area",
        },
        tags=("electrical", "risk-assessment", "ppe", "ehs"),
        applications=("Production floor", "Workshop", "Laboratory"),
    ),
    SeedProduct(
        "Warning Electrical Hazard",
        "warning-electrical-hazard",
        "SPP-ELS-008",
        "electrical-safety",
        "General electrical hazard warning for unmarked equipment.",
        "A general hazard board for equipment that has no specific label, so "
        "that every piece of electrical equipment in an area is covered by "
        "something even when the detail board is missing.\n\n"
        "The live catalogue carries this title twice, with two different slugs "
        "and the same artwork. Both are recorded in the import report as a "
        "duplicate and consolidated here to a single product.",
        8000,
        specs={
            "Sign type": "Warning",
            "Hazard symbol": "ISO 7010 W012 electric shock",
        },
        tags=("electrical", "warning", "general"),
        applications=("Production floor", "Workshop", "Store"),
    ),
    SeedProduct(
        "Warning Electrical Hazard Safety Sign Board",
        "warning-electrical-hazard-safety-sign-board",
        "SPP-ELS-009",
        "electrical-safety",
        "Full-format electrical hazard board with the safety sign wording in full.",
        "A fuller treatment of the same hazard, with the sign wording spelled "
        "out rather than abbreviated - useful where the abbreviated form has "
        "been read as a label rather than a warning.\n\n"
        "Often ordered alongside the Danger High Voltage board for a panel room "
        "where equipment levels differ.",
        8000,
        specs={
            "Sign type": "Warning",
            "Format": "Full sign wording",
        },
        tags=("electrical", "warning", "panel-room"),
        applications=("Panel room", "Substation"),
    ),
    SeedProduct(
        "Electric Shock First Response",
        "electric-shock-first-response",
        "SPP-ELS-010",
        "electrical-safety",
        "Compact first-response steps for an electric shock casualty.",
        "A smaller, faster-to-read version of the shock survival procedure, "
        "intended for a wall directly beside a distribution board where a "
        "casualty will be a few metres away.\n\n"
        "Four steps, largest possible type. If a person has just been shocked "
        "and is still in contact with the source, step one is the only one that "
        "matters.",
        8000,
        specs={
            "Format": "4 numbered steps",
            "Recommended size": "12x18",
        },
        tags=("electrical", "first-aid", "emergency"),
        applications=("Distribution board", "Workshop"),
    ),
]

# --- Remaining categories --------------------------------------------------
_OTHERS: list[SeedProduct] = [
    # 5S
    SeedProduct(
        "5S - Seiri (Sort)",
        "5s-seiri-sort",
        "SPP-5SS-001",
        "5s-methodology",
        "The first 5S: define and remove what is not needed from the workplace.",
        "Seiri - sort - is the only one of the five that involves removing "
        "things, and the only one people resist. The resistance is rational: "
        "someone has to decide what is genuinely redundant.\n\n"
        "This board defines the step, shows the red-tag method used to mark items "
        "for review rather than binning them on the spot, and sets out the "
        "review meeting that decides the outcome.\n\n"
        "The red tag is the important part. Sorting without a review step "
        "produces a skip full of things somebody needed.",
        12000,
        specs={"Kanji": "整理", "Romanised": "Seiri", "Step": "1 of 5", "Method": "Red tag review"},
        tags=("5s", "seiri", "sort", "organisation", "lean"),
        applications=("Shop floor", "Store", "Tool room"),
        featured=True,
        is_landing_page=True,
    ),
    SeedProduct(
        "5S - Seiton (Set in Order)",
        "5s-seiton-set-in-order",
        "SPP-5SS-002",
        "5s-methodology",
        "The second 5S: a place for everything, and everything in its place.",
        "Seiton - set in order - is the step people recognise, and the one most "
        "often done badly with paint-marked floor lines that fade.\n\n"
        "This board covers the shadow-board method, shadow labelling, and the "
        "15-minute daily reset that keeps the arrangement from degrading.\n\n"
        "The layout principle matters more than the tidiness: a tool that returns "
        "to a shadow board takes less time to find than one that has to be "
        "searched for, and that is the whole return.",
        12000,
        specs={
            "Kanji": "整頓",
            "Romanised": "Seiton",
            "Step": "2 of 5",
            "Method": "Shadow board, shadow label",
        },
        tags=("5s", "seiton", "organisation", "lean", "shadow-board"),
        applications=("Tool room", "Shop floor", "Warehouse"),
        featured=True,
    ),
    SeedProduct(
        "5S - Seiso (Shine)",
        "5s-seiso-shine",
        "SPP-5SS-003",
        "5s-methodology",
        "The third 5S: clean and inspect together, and find the causes.",
        "Seiso - shine - is usually reduced to cleaning. The board makes the "
        "point that cleaning is the mechanism, not the objective: dirt on a "
        "machine is a leak, a loose bolt or a failing seal, and a cleaner who "
        "does not report it is hiding a defect.\n\n"
        "The board sets out the clean-and-inspect cycle and the tagging of "
        "abnormality for follow-up.\n\n"
        "Short daily cleaning with a five-minute inspection is what sustains it.",
        12000,
        specs={
            "Kanji": "清掃",
            "Romanised": "Seiso",
            "Step": "3 of 5",
            "Method": "Clean and inspect",
        },
        tags=("5s", "seiso", "shine", "cleaning", "5min"),
        applications=("Machine bay", "Shop floor", "Change room"),
        featured=True,
    ),
    SeedProduct(
        "5S - Seiketsu (Standardise)",
        "5s-seiketsu-standardise",
        "SPP-5SS-004",
        "5s-methodology",
        "The fourth 5S: make the best previous practice the obvious way.",
        "Seiketsu - standardise - is where 5S either takes hold or quietly "
        "stops. The previous three steps are a burst of effort; this one is what "
        "makes the effort stick.\n\n"
        "The board covers visual management, the standard work instruction, and "
        "the check sheet that makes the standard visible without an audit.\n\n"
        "The principle is that a standard which is not visible is not a standard.",
        12000,
        specs={
            "Kanji": "清潔",
            "Romanised": "Seiketsu",
            "Step": "4 of 5",
            "Method": "Visual management",
        },
        tags=("5s", "seiketsu", "standardise", "visual-management", "lean"),
        applications=("Shop floor", "Office", "Warehouse"),
        featured=True,
    ),
    SeedProduct(
        "5S - Shitsuke (Sustain)",
        "5s-shitsuke-sustain",
        "SPP-5SS-005",
        "5s-methodology",
        "The fifth 5S: discipline, and the reason the other four survive.",
        "Shitsuke - sustain - is the step most posters get wrong by treating it "
        "as a slogan about discipline rather than a set of habits.\n\n"
        "This board sets out the daily checks, the role of the shift lead, and "
        "the audit cycle that sustains the standard when attention moves on to "
        "something else.\n\n"
        "If you are only ordering one 5S board, order this one last - the other "
        "four are what the fifth maintains.",
        12000,
        specs={
            "Kanji": "躾",
            "Romanised": "Shitsuke",
            "Step": "5 of 5",
            "Method": "Audit and discipline",
        },
        tags=("5s", "shitsuke", "sustain", "discipline", "audit"),
        applications=("Shop floor", "Office", "Management board"),
        featured=True,
    ),
    SeedProduct(
        "5S Methodology Overview Board",
        "5s-methodology-overview",
        "SPP-5SS-006",
        "5s-methodology",
        "The complete 5S cycle on a single board, with all five steps and the Japanese terms.",
        "The overview board shows all five steps in sequence with their kanji, "
        "their romanised names, and a one-line definition of each.\n\n"
        "It is the board to put in an induction room or a reception area, where "
        "the objective is orientation rather than instruction - anyone who has "
        "seen this board can name the five steps in order.\n\n"
        "Pairs well with the five individual step boards for a shop floor that "
        "is running the full programme.",
        15000,
        specs={
            "Steps": "All five",
            "Kanji": "Yes",
            "Romanised": "Yes",
            "Layout": "Sequential cycle diagram",
        },
        tags=("5s", "overview", "induction", "lean", "training"),
        applications=("Induction room", "Reception", "Training room"),
        size_labels=("24x36", "36x48", "48x72"),
        featured=True,
        is_landing_page=True,
    ),
    # PPE
    SeedProduct(
        "Wear Helmet",
        "wear-helmet",
        "SPP-PPE-001",
        "ppe",
        "Mandatory head protection board.",
        "A mandatory-use board for head "
        "protection, in blue circle form per ISO 7010 M004. Specify the helmet "
        "type on the board where more than one is acceptable on site.",
        9000,
        specs={
            "Standard": "ISO 7010 M004",
            "Type": "Mandatory",
            "Colour": "Blue circle, white symbol",
        },
        tags=("ppe", "helmet", "head-protection", "mandatory", "iso7010"),
        applications=("Construction", "Plant", "Warehouse"),
        featured=True,
    ),
    SeedProduct(
        "Wear Safety Goggles",
        "wear-safety-goggles",
        "SPP-PPE-002",
        "ppe",
        "Mandatory eye protection board.",
        "Eye protection is the PPE most often "
        "skipped and most often regretted. ISO 7010 M005, blue circle.",
        9000,
        specs={"Standard": "ISO 7010 M005", "Type": "Mandatory"},
        tags=("ppe", "goggles", "eye-protection", "mandatory", "iso7010"),
        applications=("Chemical handling", "Welding", "Laboratory"),
        featured=True,
    ),
    SeedProduct(
        "Wear Safety Gloves",
        "wear-safety-gloves",
        "SPP-PPE-003",
        "ppe",
        "Mandatory hand protection board.",
        "Hand protection board, ISO 7010 "
        "M024. Gloves are the hardest item to specify generically - chemical, "
        "cut and heat gloves are not interchangeable, so state the type.",
        9000,
        specs={"Standard": "ISO 7010 M024", "Type": "Mandatory"},
        tags=("ppe", "gloves", "hand-protection", "mandatory", "iso7010"),
        applications=("Chemical handling", "Fabrication", "Maintenance"),
    ),
    SeedProduct(
        "Wear Ear Protection",
        "wear-ear-protection",
        "SPP-PPE-004",
        "ppe",
        "Mandatory hearing protection board.",
        "Hearing protection board, ISO "
        "7010 M003. Most effective where posted at the boundary of a noisy area "
        "rather than inside it, where the noise is already unavoidable.",
        9000,
        specs={"Standard": "ISO 7010 M003", "Type": "Mandatory"},
        tags=("ppe", "ear-protection", "hearing", "mandatory", "noise"),
        applications=("Fabrication", "Compressor room", "Plant"),
    ),
    SeedProduct(
        "Wear Safety Shoes",
        "wear-safety-shoes",
        "SPP-PPE-005",
        "ppe",
        "Mandatory foot protection board.",
        "Foot protection board, ISO 7010 "
        "M007. Almost always required at a site gate as well as in production.",
        9000,
        specs={"Standard": "ISO 7010 M007", "Type": "Mandatory"},
        tags=("ppe", "safety-shoes", "foot-protection", "mandatory", "iso7010"),
        applications=("Site entrance", "Construction", "Warehouse"),
    ),
    SeedProduct(
        "Wear Full Body Harness",
        "wear-full-body-harness",
        "SPP-PPE-006",
        "ppe",
        "Mandatory fall arrest harness board.",
        "Fall arrest board for work at "
        "height. ISO 7010 M006, blue circle. Specify harness specification and "
        "anchor point requirement alongside the board.",
        10000,
        specs={
            "Standard": "ISO 7010 M006",
            "Type": "Mandatory",
            "Note": "State harness class and anchor requirement",
        },
        tags=("ppe", "harness", "fall-arrest", "work-at-height", "mandatory"),
        applications=("Construction", "Tank farm", "Roof work"),
    ),
    SeedProduct(
        "Wear Face Shield",
        "wear-face-shield",
        "SPP-PPE-007",
        "ppe",
        "Mandatory face protection board.",
        "Face shield board, ISO 7010 M012, "
        "for grinding, cutting and chemical splash operations where goggles alone "
        "are insufficient.",
        9000,
        specs={"Standard": "ISO 7010 M012", "Type": "Mandatory"},
        tags=("ppe", "face-shield", "eye-protection", "mandatory"),
        applications=("Grinding", "Chemical handling", "Welding"),
    ),
    SeedProduct(
        "Wear Respiratory Mask",
        "wear-respiratory-mask",
        "SPP-PPE-008",
        "ppe",
        "Mandatory respiratory protection board.",
        "Respiratory protection board, "
        "ISO 7010 M011. Always state the required filter class alongside it - a "
        "mask board without a specification is not informative.",
        9000,
        specs={
            "Standard": "ISO 7010 M011",
            "Type": "Mandatory",
            "Note": "State required filter class",
        },
        tags=("ppe", "respirator", "dust", "mandatory", "mask"),
        applications=("Paint shop", "Silica handling", "Foundry"),
    ),
    SeedProduct(
        "Safety First",
        "safety-first",
        "SPP-MOT-001",
        "motivational-signages",
        "Safety first motivational board for shop floor and reception areas.",
        "The most-printed board in industrial safety, and the most likely to be "
        "ignored, because a slogan with no content trains people to stop reading "
        "the boards around it.\n\n"
        "This version carries a short supporting line so it does not compete "
        "with the instruction boards it sits beside. Place it in reception and "
        "corridor areas, not above a machine that needs instructions.",
        10000,
        specs={
            "Type": "Motivational / positive",
            "Colour": "Blue and white",
            "Best placement": "Reception, corridor, induction room",
        },
        tags=("motivational", "safety-first", "awareness"),
        applications=("Reception", "Corridor", "Induction room"),
        featured=True,
    ),
    SeedProduct(
        "Zero Accident",
        "zero-accident",
        "SPP-MOT-002",
        "motivational-signages",
        "Zero accident target board for production areas.",
        "A common programme objective in Indian manufacturing, and one that works "
        "better as a visible daily board than as a wall poster, because the "
        "number is what people look at.\n\n"
        "This board is the fixed, printed part of that programme - the running "
        "days counter is a whiteboard alongside it.",
        10000,
        specs={"Type": "Motivational / target", "Programme": "Zero accident"},
        tags=("motivational", "zero-accident", "target", "safety-programme"),
        applications=("Production floor", "Safety notice board"),
    ),
    SeedProduct(
        "Think Safety Before You Act",
        "think-safety-before-you-act",
        "SPP-MOT-003",
        "motivational-signages",
        "Pause-before-acting board for task-start points.",
        "Placed at a "
        "task-start point rather than on a corridor wall, this board asks the one "
        "question that precedes most incidents: is the area safe to start.\n\n"
        "Short, direct, and positioned where the decision is actually made.",
        10000,
        specs={"Type": "Motivational / behavioural", "Placement": "Task start point"},
        tags=("motivational", "pause", "task-start", "behaviour"),
        applications=("Task start point", "Work cell"),
    ),
    # Quality & Productivity
    SeedProduct(
        "National Safety Week 16",
        "national-safety-week-16",
        "SPP-QP-001",
        "quality-productivity",
        "National Safety Week poster 16 of 16.",
        "Part of the National Safety "
        "Week series, a sixteen-board set covering workplace safety topics for "
        "display during the observance week.\n\n"
        "Board 16. The live catalogue shows this series with a base price of "
        "Rs.0, which is a display defect rather than a free offer; the price "
        "here is real.\n\n"
        "Order as a set or individually - the SKU is stable either way.",
        9000,
        specs={"Series": "National Safety Week", "Board": "16 of 16"},
        tags=("national-safety-week", "quality", "series", "observance"),
        applications=("Display board", "Production floor", "Safety corner"),
    ),
    SeedProduct(
        "National Safety Week 8",
        "national-safety-week-8",
        "SPP-QP-002",
        "quality-productivity",
        "National Safety Week poster 8 of 16.",
        "Board 8 of the National Safety "
        "Week series. The live catalogue carries two entries for board 8, one "
        "titled 'NATIONAL SAFETY WEEK8' with a missing space; both are recorded "
        "in the import report as duplicates and consolidated here.",
        9000,
        specs={"Series": "National Safety Week", "Board": "8 of 16"},
        tags=("national-safety-week", "quality", "series", "observance"),
        applications=("Display board", "Production floor"),
    ),
    SeedProduct(
        "Cost of Poor Quality (COPQ) Poster",
        "cost-of-poor-quality-copq-poster",
        "SPP-QP-003",
        "quality-productivity",
        "Cost of poor quality poster explaining hidden quality costs.",
        "Quality organisations argue COPQ in rupees because the number is larger "
        "than anyone expects. The cost of poor quality is rarely visible as a "
        "line item; it is scrap, rework, warranty, complaints, and the "
        "management time spent on all four.\n\n"
        "This board presents the four cost categories and the mechanism by which "
        "they compound, which is the part that persuades a shop floor that this "
        "is a financial problem and not a quality department's hobby.\n\n"
        "Board description carried over from the live catalogue, rewritten for "
        "clarity.",
        11000,
        compare_at_price=15000,
        specs={
            "Category": "Quality & productivity",
            "Method": "4 cost categories",
            "Audience": "Supervisors, quality team, management",
        },
        tags=("copq", "quality-cost", "productivity", "scrap", "rework"),
        applications=("Quality corner", "Production floor", "Management review"),
        featured=True,
    ),
    SeedProduct(
        "Quality Means Satisfied Customer",
        "quality-means-satisfied-customer",
        "SPP-QP-004",
        "quality-productivity",
        "Quality and customer satisfaction linkage board.",
        "The chain from a process defect to a customer complaint is rarely drawn "
        "for a shop floor audience, because each step is handled by a different "
        "team. This board draws it as a single line: an out-of-tolerance input "
        "becomes an out-of-tolerance output, which becomes a complaint, which "
        "becomes rework for someone else.\n\n"
        "Useful in a quality circle discussion rather than on its own.",
        10000,
        specs={"Category": "Quality & productivity", "Format": "Causal chain"},
        tags=("quality", "customer-satisfaction", "quality-circle"),
        applications=("Quality corner", "Quality circle", "Induction room"),
    ),
    SeedProduct(
        "Stages of Quality Improvement",
        "stages-of-quality-improvement-poster",
        "SPP-QP-005",
        "quality-productivity",
        "Quality improvement maturity board, inspection through prevention.",
        "A maturity board showing the progression from inspection to prevention. "
        "The point it makes is that each stage costs more than the one before: "
        "sorting defects out at final inspection is the most expensive quality "
        "activity a manufacturer can run.\n\n"
        "Board description carried over from the live catalogue.",
        10000,
        specs={
            "Category": "Quality & productivity",
            "Stages": "4",
            "Progression": "Inspection to prevention",
        },
        tags=("quality", "quality-improvement", "prevention", "maturity"),
        applications=("Quality corner", "Management review"),
    ),
    # Caution
    SeedProduct(
        "Caution Wet Floor",
        "caution-wet-floor",
        "SPP-CAU-001",
        "caution-signages",
        "Caution wet floor board, ISO 7010 W022.",
        "The most frequently ordered board in the catalogue, and the one most "
        "often bought in a thin material that curls at the edges within a month.\n\n"
        "For an area with actual foot traffic - a canteen entrance, a wash area, "
        "a chemical bay - ACP is worth the difference. For a low-traffic "
        "internal corner, eco vinyl is fine.\n\n"
        "Yellow triangle, black symbol, per ISO 7010 W022.",
        8000,
        compare_at_price=11000,
        specs={
            "Standard": "ISO 7010 W022",
            "Type": "Warning",
            "Colour": "Yellow triangle, black symbol",
        },
        tags=("caution", "wet-floor", "slip", "iso7010", "housekeeping"),
        applications=("Canteen", "Wash area", "Corridor", "Chemical bay"),
        featured=True,
    ),
    SeedProduct(
        "Caution Overhead Work",
        "caution-overhead-work",
        "SPP-CAU-002",
        "caution-signages",
        "Overhead work in progress board, ISO 7010 W014.",
        "Marks an area where work is happening above head height, and where a "
        "walk-through is a hazard rather than an inconvenience.\n\n"
        "Best placed at the approach to the area rather than inside it, where "
        "the person who needs the warning is the one walking in.",
        8000,
        specs={"Standard": "ISO 7010 W014", "Type": "Warning"},
        tags=("caution", "overhead", "maintenance", "iso7010"),
        applications=("Maintenance area", "Corridor", "Workshop"),
    ),
    SeedProduct(
        "Caution Heavy Machinery",
        "caution-heavy-machinery",
        "SPP-CAU-003",
        "caution-signages",
        "Heavy machinery caution board, ISO 7010 W024.",
        "Warns of plant movement and crush zones. Most effective at the "
        "pedestrian approach to a machine cell rather than on the machine itself, "
        "which the operator can only see when already inside the danger zone.",
        8000,
        specs={"Standard": "ISO 7010 W024", "Type": "Warning"},
        tags=("caution", "machinery", "crush", "iso7010"),
        applications=("Machine cell", "Warehouse aisle", "Loading bay"),
        featured=True,
    ),
    SeedProduct(
        "Caution Hot Surface",
        "caution-hot-surface",
        "SPP-CAU-004",
        "caution-signages",
        "Hot surface caution board, ISO 7010 W017.",
        "For steam lines, ovens, exhausts and hot work areas. Pair with a "
        "physical barrier - a board alone does not stop anyone reaching past a "
        "guard.",
        8000,
        specs={"Standard": "ISO 7010 W017", "Type": "Warning"},
        tags=("caution", "hot-surface", "burn", "iso7010"),
        applications=("Boiler room", "Oven area", "Exhaust route"),
    ),
    SeedProduct(
        "Caution Do Not Enter",
        "caution-do-not-enter",
        "SPP-CAU-005",
        "caution-signages",
        "Caution do not enter board for restricted or in-progress areas.",
        "A general restriction board for an area that is closed for work, "
        "maintenance or a contamination risk. Pair it with a physical barrier - "
        "the board explains, the barrier enforces.",
        8000,
        specs={"Type": "Warning / restriction"},
        tags=("caution", "restricted", "no-entry", "maintenance"),
        applications=("Maintenance area", "Roof access", "Store"),
    ),
    SeedProduct(
        "Caution Slips Trips And Falls",
        "caution-slips-trips-and-falls",
        "SPP-CAU-006",
        "caution-signages",
        "Slips, trips and falls caution board, ISO 7010 W011.",
        "The highest-frequency injury category in industrial sites, and the one "
        "most often addressed with a board on the floor rather than by fixing "
        "the floor. The board is a record of the decision, not the fix.",
        8000,
        specs={"Standard": "ISO 7010 W011", "Type": "Warning"},
        tags=("caution", "slips", "trips", "falls", "iso7010"),
        applications=("Production floor", "Canteen", "Warehouse"),
    ),
    # Danger
    SeedProduct(
        "Danger Toxic Gas",
        "danger-toxic-gas",
        "SPP-DNG-001",
        "danger-signages",
        "Toxic gas danger board, ISO 3864-1 / ISO 7010 W018.",
        "Red danger board for a release risk that is immediately life-threatening. "
        "Must state the gas and the immediate action - evacuate versus shelter - "
        "because those are different instructions and assuming the wrong one is "
        "worse than having no board.",
        9000,
        specs={
            "Standard": "ISO 7010 W018",
            "Type": "Danger",
            "Colour": "Red background, white symbol",
        },
        tags=("danger", "toxic", "gas", "evacuation", "iso7010"),
        applications=("Process plant", "Confined space entry", "Gas storage"),
        featured=True,
    ),
    SeedProduct(
        "Danger Flammable",
        "danger-flammable",
        "SPP-DNG-002",
        "danger-signages",
        "Flammable material danger board, ISO 7010 W021.",
        "For solvent stores, fuel areas and anywhere a flammable vapour can "
        "accumulate. Specify the flash point band where a flammable liquid is "
        "involved - 'flammable' alone is too coarse to act on.",
        9000,
        specs={"Standard": "ISO 7010 W021", "Type": "Danger"},
        tags=("danger", "flammable", "solvent", "fire", "iso7010"),
        applications=("Solvent store", "Fuel area", "Paint shop"),
        featured=True,
    ),
    SeedProduct(
        "Danger Corrosive",
        "danger-corrosive",
        "SPP-DNG-003",
        "danger-signages",
        "Corrosive material danger board, ISO 7010 W001.",
        "For acid and alkali areas. ISO 7010 W001 test is the splash-on-hand "
        "corrosion symbol, which is the reference every chemical worker already "
        "recognises from a drum label.",
        9000,
        specs={"Standard": "ISO 7010 W001", "Type": "Danger"},
        tags=("danger", "corrosive", "acid", "alkali", "iso7010"),
        applications=("Acid handling", "Etching area", "Dosing room"),
    ),
    SeedProduct(
        "Danger Restricted Area",
        "danger-restricted-area",
        "SPP-DNG-004",
        "danger-signages",
        "Restricted area danger board for authorised access only.",
        "A red danger board marking an area where access is controlled. It works "
        "with a badge reader or interlock, not on its own - the board states the "
        "rule, the control enforces it.",
        9000,
        specs={"Type": "Danger / access restriction"},
        tags=("danger", "restricted", "access-control", "authorised-personnel"),
        applications=("Control room", "Server room", "Chemical store"),
    ),
    SeedProduct(
        "Danger Confined Space",
        "danger-confined-space",
        "SPP-DNG-005",
        "danger-signages",
        "Confined space entry danger board.",
        "Confined space entry is the highest fatality category in industrial "
        "work, and the one where signage is only the last of several controls. "
        "The board is the entry point signage: permit required, atmosphere test, "
        "standby outside.",
        9000,
        specs={"Type": "Danger", "Note": "Supports, never replaces, a permit system"},
        tags=("danger", "confined-space", "permit", "entry"),
        applications=("Tanks", "Pits", "Vessels", "Sewers"),
        featured=True,
    ),
    SeedProduct(
        "Danger Radiation",
        "danger-radiation",
        "SPP-DNG-006",
        "danger-signages",
        "Ionising radiation danger board, ISO 7010 W012 trefoil variant.",
        "For radiography and any area with a radiation source. The trefoil must "
        "be accompanied by the zone designation and the access conditions, per "
        "site radiation procedure.",
        9000,
        specs={"Type": "Danger", "Note": "State zone designation"},
        tags=("danger", "radiation", "trefoil", "radiography"),
        applications=("Radiography area", "NDT facility", "Laboratory"),
    ),
    # Directional
    SeedProduct(
        "Emergency Exit Arrow",
        "emergency-exit-arrow",
        "SPP-DIR-001",
        "directional-signages",
        "Emergency exit direction arrow, ISO 7010 E001.",
        "An exit arrow is read at a run. At 1.5 m/s a person covers about 12 m "
        "before they reach a decision point, so arrows need to be visible at the "
        "far end of the corridor they serve and repeated at every turn.\n\n"
        "Photoluminescent versions matter here more than anywhere else on a site.",
        9000,
        specs={
            "Standard": "ISO 7010 E001",
            "Type": "Safe condition / directional",
            "Photoluminescent option": "Yes",
        },
        tags=("exit", "arrow", "directional", "egress", "iso7010"),
        applications=("Corridor", "Stairwell", "Warehouse aisle"),
        featured=True,
    ),
    SeedProduct(
        "Assembly Point",
        "assembly-point",
        "SPP-DIR-002",
        "directional-signages",
        "Emergency assembly / muster point board.",
        "Marks where people gather after an evacuation. The board is only useful "
        "if the muster point is actually reachable and actually signed from "
        "every exit - most sites fail on the second half of that.\n\n"
        "Include the site name and the warden's contact on the board.",
        9000,
        specs={"Type": "Safe condition", "Include": "Site name, warden contact"},
        tags=("assembly", "muster", "evacuation", "emergency"),
        applications=("Yard", "Car park", "Open ground"),
        featured=True,
    ),
    SeedProduct(
        "Directional Arrow Board",
        "directional-arrow-board",
        "SPP-DIR-003",
        "directional-signages",
        "General wayfinding arrow board.",
        "A plain directional arrow for internal wayfinding - to the workshop, to "
        "stores, to the office. Cheaper than a full wayfinding system and the "
        "first thing most sites need when people cannot find the fire exit.",
        9000,
        specs={"Type": "Directional", "Material note": "ACP for large runs"},
        tags=("directional", "wayfinding", "arrow"),
        applications=("Corridor", "Lobby", "Warehouse"),
    ),
    SeedProduct(
        "Stairs Directional Board",
        "stairs-directional-board",
        "SPP-DIR-004",
        "directional-signages",
        "Stairway identification and direction board.",
        "Marks a stairwell and its direction, with the floor number. Stairwells "
        "are the most commonly unmarked route in a multi-level industrial "
        "building, and the one that matters most during a fire.",
        9000,
        specs={"Type": "Directional", "Include": "Floor number"},
        tags=("directional", "stairs", "wayfinding", "floor"),
        applications=("Stairwell", "Landing"),
    ),
    # Emergency
    SeedProduct(
        "Fire Exit",
        "fire-exit",
        "SPP-EMG-001",
        "emergency-signages",
        "Fire exit board, ISO 7010 E001 / IS 2362 compliant layout.",
        "The fire exit board is a statutory requirement in almost every "
        "occupational building, and one of the most frequently cited findings in "
        "a fire audit when missing, faded, or obscured by a newly installed "
        "partition.\n\n"
        "Print in ACP for corridors and stairwells. In autoglow it also serves "
        "as a power-failure route marker.",
        8000,
        specs={
            "Standard": "ISO 7010 E001",
            "Type": "Safe condition",
            "Photoluminescent option": "Yes",
        },
        tags=("fire", "exit", "emergency", "egress", "iso7010"),
        applications=("Corridor", "Stairwell", "Exit door"),
        featured=True,
    ),
    SeedProduct(
        "Fire Extinguisher Location",
        "fire-extinguisher-location",
        "SPP-EMG-002",
        "emergency-signages",
        "Fire extinguisher identification board, ISO 7010 F001.",
        "Identification, not instruction. In a fire nobody reads instructions, "
        "so the board's job is to make the extinguisher findable from a doorway.\n\n"
        "ISO 7010 F001 must sit at the same height as the extinguisher, on the "
        "wall it is mounted on.",
        8000,
        specs={"Standard": "ISO 7010 F001", "Type": "Fire equipment"},
        tags=("fire", "extinguisher", "equipment", "iso7010"),
        applications=("Corridor", "Stairwell", "Kitchen", "Workshop"),
        featured=True,
    ),
    SeedProduct(
        "Emergency Phone Numbers",
        "emergency-phone-numbers",
        "SPP-EMG-003",
        "emergency-signages",
        "Emergency contact board with site-specific numbers.",
        "A contact board is only as good as its numbers. The live site has no "
        "product for this, which is a gap: every site needs one and every site's "
        "numbers are different.\n\n"
        "Order this with the numbers you want printed rather than expecting a "
        "generic board - the contact details are marked unverified in "
        "`docs/CONTENT_PENDING.md` until the business supplies them.",
        8000,
        specs={"Standard": "Site specific", "Include": "Fire, ambulance, police, site"},
        tags=("emergency", "contact", "phone", "site-specific"),
        applications=("Reception", "Gate", "Control room"),
        size_labels=("12x18", "18x24", "24x36"),
    ),
    SeedProduct(
        "First Aid Station",
        "first-aid-station",
        "SPP-EMG-004",
        "emergency-signages",
        "First aid station identification board, ISO 7010 E003.",
        "Identifies where the first aid box and trained first aider are. Pair it "
        "with a board naming the current first aider, because a station attended "
        "by someone who is off shift is not a first aid station.",
        8000,
        specs={"Standard": "ISO 7010 E003", "Type": "Safe condition"},
        tags=("first-aid", "emergency", "station", "iso7010"),
        applications=("Shop floor", "Workshop", "Office"),
        featured=True,
    ),
    SeedProduct(
        "Eye Wash Station",
        "eye-wash-station",
        "SPP-EMG-005",
        "emergency-signages",
        "Eye wash station board with maximum travel distance stated.",
        "Chemical eye injuries are survivable if the flush starts within ten "
        "seconds, so the board's job is to make the station findable under "
        "stress.\n\n"
        "State the maximum travel distance from the hazard on the board, and "
        "check it against your site layout - this is a frequent audit finding.",
        8000,
        specs={
            "Standard": "ISO 7010 E015",
            "Type": "Safe condition",
            "Note": "State maximum travel distance",
        },
        tags=("first-aid", "eye-wash", "chemical", "emergency"),
        applications=("Chemical handling", "Laboratory", "Dosing room"),
        featured=True,
    ),
    SeedProduct(
        "Emergency Shower",
        "emergency-shower",
        "SPP-EMG-006",
        "emergency-signages",
        "Emergency safety shower board, ISO 7010 E015.",
        "For areas handling corrosive materials in quantity. The board marks the "
        "shower and the pull mechanism, which is the part a panicking person "
        "cannot work out for themselves.",
        8000,
        specs={"Standard": "ISO 7010 E015", "Type": "Safe condition"},
        tags=("emergency-shower", "chemical", "first-aid", "corrosive"),
        applications=("Chemical plant", "Bulk handling area", "Laboratory"),
    ),
    # Environmental
    SeedProduct(
        "Save Water",
        "save-water",
        "SPP-ENV-001",
        "envirnomental-signages",
        "Water conservation board for process and utility areas.",
        "A water conservation board placed where water is actually used. In a "
        "process plant the meter is usually at the inlet, so the board goes at "
        "the inlet, not in the reception area where it becomes decoration.",
        10000,
        specs={"Type": "Environmental / positive", "Placement": "At point of use"},
        tags=("environmental", "water", "conservation"),
        applications=("Process area", "Utility room", "Restroom"),
    ),
    SeedProduct(
        "Switch Off When Not In Use",
        "switch-off-when-not-in-use",
        "SPP-ENV-002",
        "envirnomental-signages",
        "Point-of-use switch-off board for equipment and lighting.",
        "The live blog covers this theme at length, and the reason it works is "
        "that it is placed at the switch rather than in a corridor.\n\n"
        "This board is a point-of-use cue. Its effectiveness is measurable and "
        "it is one of the cheapest energy interventions available to a site.",
        10000,
        specs={"Type": "Environmental / behavioural", "Placement": "At the switch"},
        tags=("environmental", "energy", "switch-off", "point-of-use"),
        applications=("Machine bay", "Control panel", "Office"),
        featured=True,
    ),
    SeedProduct(
        "Waste Segregation",
        "waste-segregation",
        "SPP-ENV-003",
        "envirnomental-signages",
        "Segregated waste stream board for colour-coded bins.",
        "Segregation only works if the streams are the same everywhere on site, "
        "so the board is most useful at a disposal point where the colours are "
        "visible next to the bins themselves.\n\n"
        "State the actual streams in use at your site on the board - the default "
        "four-stream split does not fit every operation.",
        10000,
        specs={"Type": "Environmental", "Streams": "Specify at order"},
        tags=("environmental", "waste", "segregation", "sustainability"),
        applications=("Disposal point", "Canteen", "Plant"),
        featured=True,
    ),
    SeedProduct(
        "Reduce Reuse Recycle",
        "reduce-reuse-recycle",
        "SPP-ENV-004",
        "envirnomental-signages",
        "Three R board for general environmental messaging.",
        "The most printed environmental board in existence, which is precisely "
        "why it needs to be placed where it is read rather than added to a wall "
        "of boards nobody looks at.",
        10000,
        specs={"Type": "Environmental / positive"},
        tags=("environmental", "sustainability", "3r"),
        applications=("Office", "Reception", "Canteen"),
    ),
    SeedProduct(
        "Green Belt Area",
        "green-belt-area",
        "SPP-ENV-005",
        "envirnomental-signages",
        "Protected green zone boundary board.",
        "Marks a protected green zone. Frequently required for a consent-to-"
        "operate or environmental clearance, where the marked boundary has to be "
        "identifiable on site.",
        10000,
        specs={"Type": "Environmental / regulatory", "Note": "State zone and applicable clearance"},
        tags=("environmental", "green-belt", "regulatory", "clearance"),
        applications=("Perimeter", "Plant landscape", "Boundary"),
    ),
    # Health safety
    SeedProduct(
        "Wash Your Hands",
        "wash-your-hands",
        "SPP-HLT-001",
        "health-safety",
        "Hand hygiene board for workplaces and canteens.",
        "A hand hygiene board that states the technique, rather than the slogan. "
        "The slogan version has been ineffective for thirty years; the version "
        "that shows the six steps and the duration works.\n\n"
        "Place it directly above the sink, not in a corridor.",
        8000,
        specs={"Type": "Mandatory / hygiene", "Placement": "Above sink"},
        tags=("health", "handwash", "hygiene", "canteen"),
        applications=("Wash area", "Canteen", "Laboratory", "Medical room"),
        featured=True,
    ),
    SeedProduct(
        "No Smoking",
        "no-smoking",
        "SPP-HLT-002",
        "health-safety",
        "No smoking prohibition board, ISO 7010 P002.",
        "ISO 7010 P002 in red circle with diagonal bar. In an industrial site this "
        "is usually a legal requirement rather than a preference, and in a "
        "chemical area it is a condition of the consent to operate.\n\n"
        "A4 sticker format is usually sufficient for a door; ACP for a main gate.",
        8000,
        specs={"Standard": "ISO 7010 P002", "Type": "Prohibition"},
        tags=("no-smoking", "prohibition", "health", "iso7010", "fire"),
        applications=("Gate", "Office", "Canteen", "Chemical area"),
        featured=True,
    ),
    SeedProduct(
        "Wear Mask",
        "wear-mask",
        "SPP-HLT-003",
        "health-safety",
        "Face mask requirement board, ISO 7010 M001.",
        "A mask requirement board, useful in a process area where cross "
        "contamination between shifts is a real concern rather than a general "
        "health message.",
        8000,
        specs={"Standard": "ISO 7010 M001", "Type": "Mandatory"},
        tags=("health", "mask", "mandatory", "iso7010"),
        applications=("Process area", "Clean room", "Office"),
    ),
    SeedProduct(
        "Report Illness",
        "report-illness",
        "SPP-HLT-004",
        "health-safety",
        "Health reporting board for food handling and shared facilities.",
        "Relevant where a worker handling food or product has come in contact "
        "with a communicable illness. Pairs with a return-to-work process rather "
        "than replacing one.",
        8000,
        specs={"Type": "Mandatory / health"},
        tags=("health", "reporting", "food-safety", "hygiene"),
        applications=("Canteen", "Food area", "Laboratory"),
    ),
    # Fire safety
    SeedProduct(
        "In Case Of Fire",
        "in-case-of-fire",
        "SPP-FIR-001",
        "fire-safety",
        "Fire action procedure board.",
        "A fire action board has four required elements - raise the alarm, call "
        "the fire brigade, fight the fire only if safe, evacuate by the nearest "
        "exit. Boards that omit the emergency number, or show an extinguisher "
        "in use on a fire that is already out of control, are worse than no "
        "board because they invite delay.\n\n"
        "This board carries all four, in order, with the emergency number field "
        "marked for your site.",
        9000,
        specs={
            "Standard": "IS 2448 / ISO 7010",
            "Type": "Fire action",
            "Sections": "Alarm, Call, Fight, Evacuate",
        },
        tags=("fire", "emergency", "procedure", "fire-action"),
        applications=("Corridor", "Canteen", "Stairwell"),
        featured=True,
    ),
    SeedProduct(
        "Fire Emergency Number",
        "fire-emergency-number",
        "SPP-FIR-002",
        "fire-safety",
        "Fire service contact board.",
        "A fire emergency number board for a reception or gate. The number is "
        "site-specific and must be printed correctly - a fire board with the "
        "wrong number is a genuine hazard, so this is ordered with the number "
        "supplied by the site.",
        8000,
        specs={"Standard": "Site specific", "Include": "Fire service number"},
        tags=("fire", "emergency", "contact", "site-specific"),
        applications=("Reception", "Gate", "Security post"),
        size_labels=("12x18", "18x24", "24x36"),
    ),
    SeedProduct(
        "Fire Assembly Point Board",
        "fire-assembly-point-board",
        "SPP-FIR-003",
        "fire-safety",
        "Fire muster point board with site identification.",
        "The fire muster point board, in the fire category rather than the "
        "emergency category, for sites that keep the two muster points separate.",
        8000,
        specs={"Type": "Safe condition", "Include": "Site name, warden"},
        tags=("fire", "assembly", "muster", "emergency"),
        applications=("Yard", "Car park"),
    ),
    SeedProduct(
        "Fire Extinguisher Operation",
        "fire-extinguisher-operation",
        "SPP-FIR-004",
        "fire-safety",
        "Extinguisher operation board - PASS method.",
        "The operation board that actually gets used during a fire, so it has to "
        "be short. The PASS sequence - Pull, Aim, Squeeze, Sweep - is four "
        "actions and one picture.\n\n"
        "Mount it on the extinguisher stand or immediately beside it.",
        8000,
        specs={
            "Method": "PASS",
            "Type": "Fire equipment instruction",
            "Placement": "At the extinguisher",
        },
        tags=("fire", "extinguisher", "pass", "instruction"),
        applications=("Fire point", "Kitchen", "Workshop"),
        featured=True,
    ),
    SeedProduct(
        "Do Not Block Fire Extinguisher",
        "do-not-block-fire-extinguisher",
        "SPP-FIR-005",
        "fire-safety",
        "Keep fire equipment clear board.",
        "Blocked or obstructed fire equipment is a standard fire audit finding "
        "and, more importantly, is the reason an extinguisher is not there when "
        "it is needed. This board addresses the storage habit rather than the "
        "equipment.",
        8000,
        specs={"Type": "Warning"},
        tags=("fire", "access", "clearance", "extinguisher"),
        applications=("Fire point", "Corridor", "Store"),
    ),
    # Lab safety
    SeedProduct(
        "Wear Lab Coat And Goggles",
        "wear-lab-coat-and-goggles",
        "SPP-LAB-001",
        "lab-safety",
        "Mandatory laboratory PPE board, combined coat and goggles.",
        "Combines the lab coat and eye protection requirements on one board, "
        "which is what a laboratory entrance actually needs rather than two "
        "separate mandatory boards.\n\n"
        "ISO 7010 M005 plus M002 pictograms.",
        10000,
        specs={"Type": "Mandatory", "Pictograms": "ISO 7010 M002, M005"},
        tags=("lab", "ppe", "lab-coat", "goggles", "mandatory"),
        applications=("Laboratory", "Research lab", "QC lab"),
        featured=True,
    ),
    SeedProduct(
        "No Food Or Drink In The Laboratory",
        "no-food-or-drink-in-the-laboratory",
        "SPP-LAB-002",
        "lab-safety",
        "Prohibition board for food and drink in labs.",
        "A laboratory prohibition board covering food, drink, smoking and "
        "pipetting by mouth - the four that account for most laboratory "
        "contaminations and exposures.\n\n"
        "ISO 7010 P003 style prohibition circle with the four symbols grouped.",
        10000,
        specs={"Type": "Prohibition", "Symbols": "Food, drink, smoking, pipetting"},
        tags=("lab", "prohibition", "food", "contamination"),
        applications=("Laboratory", "QC lab", "Research lab"),
        featured=True,
    ),
    SeedProduct(
        "Chemical Hazard - Refer To MSDS",
        "chemical-hazard-refer-to-msds",
        "SPP-LAB-003",
        "lab-safety",
        "Chemical hazard board pointing to the safety data sheet.",
        "A hazard board that is a signpost rather than a datasheet: it states "
        "that the material is hazardous and directs the reader to the SDS board "
        "for the specifics. The right design when many materials share one "
        "storage area.\n\n"
        "Pair with the MSDS category in this catalogue.",
        10000,
        specs={"Type": "Warning", "Links to": "MSDS board"},
        tags=("lab", "chemical", "msds", "hazard"),
        applications=("Chemical store", "Laboratory", "Reagent cabinet"),
    ),
    SeedProduct(
        "Autoclave Safety",
        "autoclave-safety",
        "SPP-LAB-004",
        "lab-safety",
        "Autoclave operating procedure board.",
        "Burn and pressure hazard board for autoclave use, covering pressure "
        "release, burn risk and the requirement to verify the door seal before "
        "opening. Inconsistent as a safety matter, which is why the board states "
        "the check explicitly.",
        10000,
        specs={"Type": "Warning", "Hazards": "Pressure, hot liquid, steam"},
        tags=("lab", "autoclave", "pressure", "burn", "sterilisation"),
        applications=("Laboratory", "Sterilisation room", "QC lab"),
    ),
    # Office
    SeedProduct(
        "CCTV In Operation",
        "cctv-in-operation",
        "SPP-OFC-001",
        "office-signages",
        "CCTV surveillance notice board.",
        "A surveillance notice is a legal requirement in most Indian states when "
        "footage is recorded, and its absence is a straightforward compliance "
        "gap. State the operator and the contact for footage requests on the board.",
        6000,
        specs={"Type": "Information", "Include": "Operator, footage contact"},
        tags=("office", "cctv", "surveillance", "compliance", "privacy"),
        applications=("Reception", "Corridor", "Entry"),
        size_labels=("8x12", "12x18", "18x24"),
    ),
    SeedProduct(
        "Emergency Exit Office",
        "emergency-exit-office",
        "SPP-OFC-002",
        "office-signages",
        "Emergency exit board for office and commercial premises.",
        "The office equivalent of the factory fire exit board, at the smaller "
        "sizes appropriate to a commercial building and with the photoluminescent "
        "option for the same reason: the corridor is dark when it matters.",
        7000,
        specs={"Standard": "ISO 7010 E001", "Photoluminescent option": "Yes"},
        tags=("office", "emergency", "exit", "egress"),
        applications=("Office", "Commercial building", "Stairwell"),
        featured=True,
    ),
    SeedProduct(
        "First Aid Office",
        "first-aid-office",
        "SPP-OFC-003",
        "office-signages",
        "First aid point board for office premises.",
        "An office first aid board, including the location of the nearest "
        "registered first aider. Offices are audited for this and it is "
        "frequently the board that is missing rather than the kit.",
        7000,
        specs={"Type": "Safe condition", "Include": "First aider name"},
        tags=("office", "first-aid", "compliance"),
        applications=("Office", "Reception", "Lift lobby"),
        size_labels=("8x12", "12x18", "18x24"),
    ),
    SeedProduct(
        "Floor Directory",
        "floor-directory",
        "SPP-OFC-004",
        "office-signages",
        "Floor and department directory board.",
        "A directory board for a multi-occupancy or multi-floor office, with the "
        "lift lobby as the usual location. Vinyl is the sensible material here; "
        "ACP is overkill unless it is at a lift bank that gets handled.",
        7000,
        specs={"Type": "Information", "Material note": "Vinyl preferred"},
        tags=("office", "wayfinding", "directory", "information"),
        applications=("Lift lobby", "Reception", "Entrance"),
        size_labels=("12x18", "18x24", "24x36"),
    ),
    SeedProduct(
        "Please Keep This Area Clean",
        "please-keep-this-area-clean",
        "SPP-OFC-005",
        "office-signages",
        "Housekeeping board for shared office areas.",
        "Housekeeping reminder for a shared office or customer-facing area. "
        "Effective at point of use; ineffective on a wall in an empty corridor.",
        6000,
        specs={"Type": "Mandatory / etiquette"},
        tags=("office", "housekeeping", "clean"),
        applications=("Office", "Meeting room", "Reception"),
        size_labels=("8x12", "12x18", "18x24"),
    ),
    # Road safety
    SeedProduct(
        "Speed Limit 10",
        "speed-limit-10",
        "SPP-RDS-001",
        "road-safety",
        "Speed limit 10 board for internal roads and yards.",
        "A site speed limit board for internal roads, where a 10 or 20 km/h limit "
        "applies and standard road signage is not appropriate.\n\n"
        "Red circle with the number, per the standard road sign convention, so it "
        "reads as a limit rather than an instruction.",
        12000,
        specs={
            "Type": "Prohibition / limit",
            "Value": "10 km/h",
            "Note": "State other permitted speeds at order",
        },
        size_labels=("18x24", "24x36", "36x48", "48x72"),
        tags=("road", "speed-limit", "yard", "traffic"),
        applications=("Internal road", "Yard", "Gate approach"),
        featured=True,
    ),
    SeedProduct(
        "No Horn",
        "no-horn",
        "SPP-RDS-002",
        "road-safety",
        "No horn board for hospital, office and residential approaches.",
        "A no-horn board for the approach to a hospital, an office or a "
        "residential colony adjacent to a plant. Red circle with diagonal bar "
        "over a horn symbol.",
        11000,
        specs={"Type": "Prohibition", "Standard": "Road sign convention"},
        tags=("road", "no-horn", "prohibition", "noise"),
        applications=("Gate approach", "Hospital road", "Residential road"),
        size_labels=("18x24", "24x36", "36x48"),
        featured=True,
    ),
    SeedProduct(
        "School Zone Ahead",
        "school-zone-ahead",
        "SPP-RDS-003",
        "road-safety",
        "School zone warning board for roads near a school or campus.",
        "A school zone board with the speed restriction stated. The restriction "
        "has to be on the board, because a warning without a number does not "
        "change behaviour.",
        12000,
        specs={"Type": "Warning", "Include": "Restricted speed"},
        tags=("road", "school-zone", "warning", "speed"),
        applications=("Campus road", "Gate road"),
        size_labels=("24x36", "36x48", "48x72"),
    ),
    SeedProduct(
        "Road Closed",
        "road-closed",
        "SPP-RDS-004",
        "road-safety",
        "Road closed board for diversions and maintenance.",
        "A temporary works board for a closed section of internal road. Printed "
        "on ACP these survive being moved and re-posted; printed on vinyl they "
        "are the right choice for a short-term closure.",
        11000,
        specs={"Type": "Prohibition / temporary works"},
        tags=("road", "closed", "temporary", "diversion"),
        applications=("Internal road", "Yard", "Works area"),
        size_labels=("18x24", "24x36", "36x48"),
    ),
    SeedProduct(
        "Pedestrian Crossing",
        "pedestrian-crossing",
        "SPP-RDS-005",
        "road-safety",
        "Pedestrian crossing board for internal roads and yard routes.",
        "Pedestrian crossing board in blue square form, for a crossing point "
        "inside a plant or warehouse yard where there is a real conflict between "
        "forklift traffic and people on foot.",
        11000,
        specs={"Type": "Information / mandatory", "Colour": "Blue square"},
        tags=("road", "pedestrian", "crossing", "warehouse", "forklift"),
        applications=("Internal road", "Yard", "Warehouse aisle"),
        size_labels=("18x24", "24x36", "36x48"),
        featured=True,
    ),
    SeedProduct(
        "Drive Slowly And Use Horn",
        "drive-slowly-and-use-horn",
        "SPP-RDS-006",
        "road-safety",
        "Combined slow and horn reminder board.",
        "A combined reminder board for internal traffic, typically placed at the "
        "site gate on the approach road where vehicle speed is highest.",
        10000,
        specs={"Type": "Warning"},
        tags=("road", "speed", "horn", "gate"),
        applications=("Site gate", "Approach road"),
        size_labels=("18x24", "24x36", "36x48"),
    ),
    # Canteen
    SeedProduct(
        "Maintain Cleanliness",
        "maintain-cleanliness",
        "SPP-CAN-001",
        "canteen",
        "Canteen cleanliness board.",
        "A canteen cleanliness board, placed at the serving counter where the "
        "standard is actually applied rather than in a dining area away from "
        "the food.\n\n"
        "Often required as part of a food hygiene audit trail.",
        8000,
        specs={"Type": "Mandatory / hygiene", "Placement": "Serving counter"},
        tags=("canteen", "hygiene", "cleanliness", "food-safety"),
        applications=("Canteen", "Servery"),
        featured=True,
    ),
    SeedProduct(
        "Wash Hands Before Eating",
        "wash-hands-before-eating",
        "SPP-CAN-002",
        "canteen",
        "Handwash requirement board for canteen entrance.",
        "A handwash board at the canteen entrance, above the dispenser, with the "
        "six-step technique rather than a slogan. The live blog makes the same "
        "point about signage density: three to five icons, large type, no "
        "decoration.",
        8000,
        specs={"Type": "Mandatory / hygiene", "Placement": "Above dispenser"},
        tags=("canteen", "handwash", "hygiene", "food-safety"),
        applications=("Canteen entrance", "Servery"),
        featured=True,
    ),
    SeedProduct(
        "Wear Cap In Canteen",
        "wear-cap-in-canteen",
        "SPP-CAN-003",
        "canteen",
        "Head covering requirement board for canteen and food areas.",
        "A head covering requirement board, generally required under a food "
        "handling hygiene plan. ISO 7010 M004 symbol with the canteen context.",
        8000,
        specs={"Type": "Mandatory", "Standard": "ISO 7010 M004"},
        tags=("canteen", "hygiene", "head-covering", "mandatory", "food-safety"),
        applications=("Canteen", "Servery", "Kitchen"),
    ),
    SeedProduct(
        "No Smoking In Canteen",
        "no-smoking-in-canteen",
        "SPP-CAN-004",
        "canteen",
        "No smoking board for the canteen and dining area.",
        "A no-smoking board for a dining area, where a larger format with more "
        "waste space around the symbol reads as less aggressive than a small "
        "sticker stuck to a table.\n\n"
        "ISO 7010 P002.",
        8000,
        specs={"Standard": "ISO 7010 P002", "Type": "Prohibition"},
        tags=("canteen", "no-smoking", "prohibition", "food-safety", "iso7010"),
        applications=("Canteen", "Dining area"),
        featured=True,
    ),
    SeedProduct(
        "Save Food Waste",
        "save-food-waste",
        "SPP-CAN-005",
        "canteen",
        "Food waste reduction board for the canteen servery.",
        "A food waste board placed at the servery queue, where a plate is served "
        "and the decision to take seconds happens. Visible in the live blog's "
        "energy-saving content as the same principle applied to food.",
        8000,
        specs={"Type": "Environmental / behavioural", "Placement": "Servery queue"},
        tags=("canteen", "food-waste", "environment", "behaviour"),
        applications=("Canteen servery", "Dining area"),
    ),
    SeedProduct(
        "Queue Here",
        "queue-here",
        "SPP-CAN-006",
        "canteen",
        "Queue management board for the canteen servery.",
        "A queue board for a canteen with a slow-moving servery. Reduces the "
        "jostling at the counter, which is where most canteen complaints and a "
        "surprising number of minor injuries come from.",
        7000,
        specs={"Type": "Information"},
        tags=("canteen", "queue", "servery", "flow"),
        applications=("Canteen servery"),
        size_labels=("8x12", "12x18", "18x24"),
    ),
    # Pylon
    SeedProduct(
        "Outdoor Pylon Sign Board",
        "outdoor-pylon-sign-board",
        "SPP-PYL-001",
        "pylon-boards",
        "Free-standing pylon signage board for outdoor areas.",
        "A free-standing pylon board for outdoor areas, gates and traffic "
        "management. ACP is the default here rather than a choice: an outdoor "
        "sign that flexes in the wind is a sign that stops being read.\n\n"
        "Free-standing boards need a base. Specify whether this is supplied as a "
        "flat panel or with a stand, and confirm the fixing method with the "
        "supplier before ordering in volume.",
        35000,
        specs={
            "Construction": "Free-standing, ACP face",
            "Recommended material": "3MM ACP",
            "Base": "Specify at order",
            "Outdoor rated": "Yes",
        },
        size_labels=("24x36", "36x48", "36x72", "48x72", "48x96"),
        tags=("pylon", "outdoor", "free-standing", "traffic", "wayfinding"),
        applications=("Gate", "Yard", "Car park", "Internal road"),
        featured=True,
    ),
    SeedProduct(
        "Outdoor Pylon Sign Board - Corner",
        "outdoor-pylon-sign-board-corner",
        "SPP-PYL-002",
        "pylon-boards",
        "Corner pylon board for driveway control.",
        "A corner pylon board, used to prevent vehicles cutting a corner or "
        "mounting a kerb. Reflective face where the board faces oncoming "
        "traffic.\n\n"
        "Also used to protect planted areas and building corners in a yard.",
        38000,
        specs={"Construction": "Corner pylon, reflective face", "Base": "Specify at order"},
        size_labels=("24x36", "36x48", "36x72", "48x72"),
        tags=("pylon", "outdoor", "corner", "traffic", "protective"),
        applications=("Driveway", "Yard corner", "Building perimeter"),
        featured=True,
    ),
    SeedProduct(
        "Traffic Pylon Cone Board",
        "traffic-pylon-cone-board",
        "SPP-PYL-003",
        "pylon-boards",
        "Traffic pylon for temporary and permanent demarcation.",
        "A traffic pylon for demarcation, in ACP so it survives being clipped by "
        "a vehicle in a yard - which is exactly what happens to a plastic cone "
        "in an active yard.\n\n"
        "Autoglow face is available for night demarcation.",
        30000,
        specs={
            "Construction": "ACP faced pylon",
            "Reflective": "Optional",
            "Autoglow option": "Yes",
        },
        size_labels=("24x36", "36x48", "48x72"),
        tags=("pylon", "traffic", "demarcation", "yard"),
        applications=("Yard", "Parking", "Works area"),
        featured=True,
    ),
    SeedProduct(
        "Outdoor Pylon Sign Board - Multiple Message",
        "outdoor-pylon-sign-board-multiple-message",
        "SPP-PYL-004",
        "pylon-boards",
        "Multi-message pylon for a site entrance.",
        "A multi-message pylon for a site entrance, carrying the company name, "
        "the safety message and the speed or hazard instruction on a single board "
        "visible from the approach road.\n\n"
        "Design note: at approach-road distance only the largest three elements "
        "are read, so the message hierarchy matters more than the detail.",
        42000,
        specs={
            "Construction": "Free-standing multi-message pylon",
            "Message zones": "3",
            "Recommended material": "3MM ACP",
        },
        size_labels=("36x48", "36x72", "48x72", "48x96"),
        tags=("pylon", "outdoor", "entrance", "multi-message"),
        applications=("Site entrance", "Gate", "Approach road"),
        featured=True,
    ),
]

PRODUCTS: list[SeedProduct] = _MSDS + _ELECTRICAL + _OTHERS


# ===========================================================================
# 5S reference content (rendered on /5s)
# ===========================================================================
FIVE_S_STEPS: list[dict[str, str]] = [
    {
        "key": "seiri",
        "step": "1S",
        "name": "Seiri",
        "japanese": "整理",
        "meaning": "Sort",
        "summary": "Separate what is needed from what is not, and remove the rest.",
        "detail": (
            "Seiri is the only step that involves getting rid of things, and the "
            "only one people resist. The resistance is rational: someone has to "
            "decide what is genuinely redundant, and that decision is not "
            "delegable to a cleaner.\n\n"
            "The method that works is the red tag. Items are tagged, not binned, "
            "and a review meeting decides the outcome within a fixed period. A "
            "red-tagged item that is still in use after thirty days was never "
            "redundant, which is the point of the review.\n\n"
            "Skipping the review is how a skip full of somebody's tools becomes "
            "an insurance claim."
        ),
    },
    {
        "key": "seiton",
        "step": "2S",
        "name": "Seiton",
        "japanese": "整頓",
        "meaning": "Set in Order",
        "summary": "A place for everything, and everything in its place.",
        "detail": (
            "Seiton is the step people recognise, and the one most often done "
            "badly with paint-marked floor lines that fade within a season.\n\n"
            "The principle is return time, not neatness. A tool that returns to a "
            "shadow board is found in two seconds; a tool that returns to a "
            "general trolley is found in two minutes, and the difference is paid "
            "every time somebody needs it.\n\n"
            "Shadow labelling - labelling the outline, not the item - is the "
            "mechanism that makes an absence obvious. An empty shadow is visible "
            "from across the shop floor; a missing tool in a full rack is not."
        ),
    },
    {
        "key": "seiso",
        "step": "3S",
        "name": "Seiso",
        "japanese": "清掃",
        "meaning": "Shine",
        "summary": "Clean and inspect together, and treat what you find.",
        "detail": (
            "Seiso is usually reduced to cleaning. That loses the point: dirt on "
            "a machine is a leak, a loose bolt or a failing seal, and a cleaner "
            "who does not report it is hiding a defect.\n\n"
            "The method is a short daily clean with a five-minute inspection, and "
            "any abnormality tagged for follow-up rather than cleaned over.\n\n"
            "This is also the step with the clearest evidence trail. Grime "
            "reappearing in the same place over a week is a maintenance finding, "
            "not a housekeeping one."
        ),
    },
    {
        "key": "seiketsu",
        "step": "4S",
        "name": "Seiketsu",
        "japanese": "清潔",
        "meaning": "Standardise",
        "summary": "Make the best previous practice the obvious way to do it.",
        "detail": (
            "Seiketsu is where 5S either takes hold or quietly stops. The first "
            "three steps are a burst of effort; this one makes the effort stick.\n\n"
            "The tools are visual management, standard work instructions, and a "
            "check sheet that makes the standard visible without an audit. A "
            "standard which is not visible is not a standard.\n\n"
            "Colour coding is part of this rather than decoration: red for "
            "fire equipment, green for safety, yellow for caution, blue for "
            "mandatory. A shop floor learns the scheme once and then reads colour "
            "instead of words."
        ),
    },
    {
        "key": "shitsuke",
        "step": "5S",
        "name": "Shitsuke",
        "japanese": "躾",
        "meaning": "Sustain",
        "summary": "Discipline and habit, sustained when attention moves on.",
        "detail": (
            "Shitsuke is the step most posters get wrong by treating it as a "
            "slogan about discipline. It is a set of habits held in place by a "
            "cadence: daily checks by the operator, weekly by the shift lead, "
            "monthly by an audit.\n\n"
            "The failure mode is always the same. 5S is launched with effort, "
            "the launch team moves on, and six months later the shadow boards are "
            "empty because nothing checks them.\n\n"
            "If you are only ordering one 5S board, order this one - the other "
            "four are what this maintains."
        ),
    },
]


# ===========================================================================
# Industries - landing pages
# ===========================================================================
@dataclass(slots=True)
class SeedIndustry:
    name: str
    slug: str
    tagline: str
    summary: str
    body: str
    icon: str
    position: int
    #: Product titles from this catalogue to feature, by slug.
    product_slugs: tuple[str, ...]
    seo_title: str
    seo_description: str


INDUSTRIES: list[SeedIndustry] = [
    SeedIndustry(
        "Manufacturing",
        "manufacturing",
        "Signage that survives a production floor",
        "For plants where signage has to stay readable through heat, dust, "
        "washdown and a forklift.",
        "A production floor is the hardest environment for signage. Everything on "
        "it is designed to be ignored - noise, movement, urgency - and a sign "
        "that is slightly too small or printed on the wrong substrate simply "
        "becomes part of the background.\n\n"
        "Three requirements matter more than the rest. **Print on ACP for "
        "anything at eye level near a machine**, because vinyl at that height is "
        "damaged within a year. **Keep the instruction to one action per board.** "
        "**Mount at the decision point**, which is the approach to the machine "
        "cell, not the machine itself.\n\n"
        "For 5S programmes, the per-step boards in this catalogue are sized to "
        "be read from two metres, which is the working distance on most lines.",
        "factory",
        1,
        (
            "wear-safety-goggles",
            "caution-heavy-machinery",
            "5s-seiri-sort",
            "5s-seiton-set-in-order",
            "caution-slips-trips-and-falls",
            "danger-toxic-gas",
        ),
        "Safety Signage for Manufacturing Plants | Safety Poster Prints",
        "PPE, 5S, caution and danger signage for manufacturing plants. ACP, foam "
        "sheet, autoglow and vinyl boards built for a production floor.",
    ),
    SeedIndustry(
        "Chemical Industry",
        "chemical-industry",
        "GHS-compliant boards for the chemicals you actually handle",
        "MSDS boards, corrosive and toxic hazard signage, and emergency "
        "equipment identification for chemical handling.",
        "Chemical plants have a documentation problem before they have a "
        "signage problem. The safety data sheet exists; the question is whether "
        "the person holding the drum can find the relevant page.\n\n"
        "The MSDS boards in this catalogue carry the GHS pictograms, signal word, "
        "hazard statements and first-aid measures laid out for use *after* an "
        "incident rather than for compliance filing. A board that requires "
        "reading a paragraph to find the flush instruction does not work at the "
        "moment it is needed.\n\n"
        "Three things to get right: an eyewash or shower within the site standard "
        "travel distance, a board for **every** material present rather than only "
        "the hazardous ones, and autoglow signage on the route out, because "
        "the worst time to find the exit is after a power failure.",
        "flask-conical",
        2,
        (
            "msds-of-caustic-soda",
            "msds-of-chlorine-1",
            "msds-of-toluene-1",
            "danger-corrosive",
            "eye-wash-station",
            "emergency-shower",
        ),
        "Chemical Industry Safety Signage & MSDS Boards | Safety Poster Prints",
        "GHS-compliant MSDS posters, corrosive and toxic hazard signage, and "
        "emergency equipment boards for chemical plants and laboratories.",
    ),
    SeedIndustry(
        "Construction",
        "construction",
        "Site boards for work at height and plant movement",
        "Fall arrest, overhead work, hard hat areas and vehicle-plant "
        "segregation boards for a live site.",
        "Construction signage has the shortest life of any industrial signage, "
        "because the site changes. Boards get moved, covered, or left behind "
        "pointing at a stair that has been removed.\n\n"
        "That argues for a small, robust core set that is repositioned rather "
        "than a large one that is abandoned. ACP is worth it for anything fixed "
        "to a hoarding; vinyl is the right call for a temporary site notice.\n\n"
        "The plant/pedestrian conflict is the highest-frequency hazard on most "
        "sites and the one most often addressed with a single board at the gate "
        "rather than a separation scheme at the point of conflict.",
        "hard-hat",
        3,
        (
            "wear-full-body-harness",
            "caution-overhead-work",
            "wear-helmet",
            "pedestrian-crossing",
            "caution-heavy-machinery",
            "danger-confined-space",
        ),
        "Construction Site Safety Signs & Posters | Safety Poster Prints",
        "Fall arrest, overhead work, hard hat and site traffic signage for "
        "construction. Durable ACP and foam sheet boards for live sites.",
    ),
    SeedIndustry(
        "Warehouses",
        "warehouses",
        "Where forklifts and people share the same floor",
        "Forklift traffic warnings, pedestrian crossings, racking signage and "
        "load capacity boards.",
        "A warehouse has a specific problem: heavy moving plant and unprotected "
        "people occupying the same surface. Most warehouse injuries are "
        "collisions between a pedestrian and a forklift, and almost all of them "
        "happen at a crossing point rather than in an aisle.\n\n"
        "The effective measure is physical separation, with signage reinforcing "
        "it. A crossing board at the point of conflict, a speed limit on the "
        "approach road, and audible-visual warnings on the forklift itself.\n\n"
        "Racking signage is a separate discipline and a legal requirement in most "
        "jurisdictions: load capacity per beam, and upright height clearance. "
        "Specify the values for your racking, not a generic board.",
        "forklift",
        4,
        (
            "caution-heavy-machinery",
            "pedestrian-crossing",
            "speed-limit-10",
            "danger-flammable",
            "fire-exit",
            "caution-slips-trips-and-falls",
        ),
        "Warehouse Safety Signs & Forklit Traffic Signage | Safety Poster Prints",
        "Forklift warning, pedestrian crossing, speed limit and racking signage "
        "for warehouses and distribution centres.",
    ),
    SeedIndustry(
        "Factories",
        "factories",
        "One board for every area on the plant",
        "The full range, organised so an EHS manager can plan a site-wide "
        "signage audit and order once.",
        "A site-wide signage programme is usually an audit exercise: walk the "
        "plant, find every location where a sign should be, and record which one "
        "is missing, damaged or unreadable. Ordering is then straightforward.\n\n"
        "Two things make the ordering straightforward. Grouping by **area** "
        "rather than by category means the delivery matches a walk of the site. "
        "And fixing one material across an area - ACP in production, vinyl in "
        "the office - is cheaper than a mixed order and looks deliberate.\n\n"
        "For larger sites, request a bulk quote. ACP and foam sheet volumes can "
        "normally be quoted better than a mixed single-unit order, and we can "
        "print a site-specific set with your naming and numbering.",
        "warehouse",
        5,
        (
            "wear-helmet",
            "5s-seiketsu-standardise",
            "fire-exit",
            "maintain-cleanliness",
            "no-smoking",
            "emergency-exit-arrow",
        ),
        "Factory Safety Signage & Industrial Posters | Safety Poster Prints",
        "Complete factory safety signage: PPE, 5S, fire, emergency and canteen "
        "boards. Bulk orders and site-wide sets.",
    ),
    SeedIndustry(
        "Laboratories",
        "laboratories",
        "For small rooms with a lot of hazards in them",
        "Chemical hazard, protective equipment, eyewash and contamination "
        "control boards for research and QC labs.",
        "A laboratory concentrates more distinct hazards into a smaller space "
        "than almost any other workplace, and usually with fewer people who know "
        "all of them.\n\n"
        "The practical requirement is a board at the entrance that a visitor can "
        "read in five seconds and a visitor will be: what to wear, what not to "
        "do, and where the eyewash and shower are. Once inside, the specific MSDS "
        "boards do the work.\n\n"
        "Refrigerated and gas cylinder storage are the two areas most often "
        "missed in a lab signage audit, and both are worth a specific board "
        "rather than a generic hazard one.",
        "flask-round",
        6,
        (
            "wear-lab-coat-and-goggles",
            "no-food-or-drink-in-the-laboratory",
            "eye-wash-station",
            "chemical-hazard-refer-to-msds",
            "msds-of-dmso",
            "emergency-shower",
        ),
        "Laboratory Safety Signs & Posters | Safety Poster Prints",
        "Laboratory signage: mandatory PPE, chemical hazard, eyewash, emergency "
        "shower and contamination control boards.",
    ),
    SeedIndustry(
        "Hospitals",
        "hospitals",
        "Routes and exits that work when the power does not",
        "Exit routes, assembly points and fire action boards for healthcare premises.",
        "Healthcare buildings have a specific constraint: patients and visitors "
        "who are not familiar with the building, moving at walking pace or "
        "slower, in an environment where a fire evacuation is genuinely "
        "dangerous to some of them.\n\n"
        "Autoglow exit signage is not a premium option here - it is a "
        "requirement in practice, because the failure mode is a corridor that is "
        "unlit exactly when it is needed. The glow charges in normal lighting and "
        "reads for hours in a power failure.\n\n"
        "Assembly point boards need the ward name and the staff contact, not just "
        "an arrow, because the roll call is done by ward and a generic muster "
        "point board does not support it.",
        "cross",
        7,
        (
            "emergency-exit-office",
            "fire-exit",
            "assembly-point",
            "in-case-of-fire",
            "first-aid-office",
            "no-smoking",
        ),
        "Hospital Safety Signage & Emergency Exit Boards | Safety Poster Prints",
        "Photoluminescent emergency exit, fire action, assembly point and first "
        "aid signage for hospitals and healthcare premises.",
    ),
    SeedIndustry(
        "Schools",
        "schools",
        "Boards children will actually read",
        "Emergency exit, assembly, canteen hygiene and laboratory safety boards "
        "for schools and colleges.",
        "School signage has an unusual constraint: the audience includes people "
        "who are learning to read signs, not just people who already know them. "
        "That favours simpler boards, larger pictograms and fewer words over "
        "dense technical content.\n\n"
        "It also means the colour convention has to be consistent. A school where "
        "the exit is green in one corridor and yellow in another is teaching the "
        "opposite of what it intends.\n\n"
        "For a school laboratory, use the lab signage in this catalogue rather "
        "than generic factory boards - the audience is different and the "
        "supervision assumption is different.",
        "school",
        8,
        (
            "emergency-exit-office",
            "assembly-point",
            "school-zone-ahead",
            "wear-lab-coat-and-goggles",
            "wash-hands-before-eating",
            "no-smoking",
        ),
        "School Safety Signage & Posters | Safety Poster Prints",
        "Emergency exit, assembly point, canteen hygiene and lab safety signage "
        "for schools and colleges.",
    ),
    SeedIndustry(
        "Offices",
        "offices",
        "The signage people read without noticing",
        "Exit routes, first aid, surveillance notices and wayfinding for commercial premises.",
        "Office signage is judged on two things nobody notices when it is right: "
        "whether a visitor can find the fire exit, and whether the first aid box "
        "is where the sign says it is.\n\n"
        "Material choice is different here. A board in a lift lobby is handled and "
        "cleaned but not exposed to weather, so vinyl or foam sheet is the right "
        "specification and ACP is over-specified.\n\n"
        "Compliance is the other consideration: surveillance notices, first aid "
        "provision and exit signage are all inspected, and all three are commonly "
        "missing rather than incorrect.",
        "building-2",
        9,
        (
            "emergency-exit-office",
            "first-aid-office",
            "cctv-in-operation",
            "floor-directory",
            "no-smoking",
            "please-keep-this-area-clean",
        ),
        "Office Safety Signage & Wayfinding | Safety Poster Prints",
        "Emergency exit, first aid, CCTV notice and directory signage for offices "
        "and commercial buildings.",
    ),
    SeedIndustry(
        "Commercial Buildings",
        "commercial-buildings",
        "Exit, fire and accessibility boards for public premises",
        "Fire action, exit routes, first aid and assembly boards for malls, "
        "offices and public buildings.",
        "Public buildings are inspected for the same three things as offices, but "
        "the consequence of a failure is different because the occupants are the "
        "public rather than employees who know the building.\n\n"
        "Two boards are non-negotiable in a public building: the fire action "
        "board with the correct local emergency number, and a legible exit route "
        "visible from the far end of each corridor.\n\n"
        "For larger premises, an assembly point board per fire compartment "
        "rather than one for the whole site, since a partial evacuation does not "
        "send everyone to the same place.",
        "building",
        10,
        (
            "fire-exit",
            "in-case-of-fire",
            "assembly-point",
            "first-aid-station",
            "no-smoking",
            "fire-emergency-number",
        ),
        "Commercial Building Safety Signage & Fire Boards | Safety Poster Prints",
        "Fire action, emergency exit, assembly point and first aid signage for "
        "commercial buildings, malls and public premises.",
    ),
]


# ===========================================================================
# Coupons
# ===========================================================================
@dataclass(slots=True)
class SeedCoupon:
    code: str
    description: str
    coupon_type: Literal["PERCENTAGE", "FIXED"]
    #: PERCENTAGE -> basis points (1000 = 10%). FIXED -> minor units.
    value: int
    max_discount_amount: int | None = None
    min_order_amount: int = 0
    expires_in_days: int | None = 30
    usage_limit: int | None = None
    per_user_limit: int | None = None
    is_active: bool = True


COUPONS: list[SeedCoupon] = [
    SeedCoupon(
        "WELCOME10",
        "10% off your first order, up to Rs.500",
        "PERCENTAGE",
        1000,
        50000,
        49900,
        None,
        None,
        1,
    ),
    SeedCoupon(
        "BULK10",
        "10% off orders over Rs.5,000 - for multi-board orders",
        "PERCENTAGE",
        1000,
        100000,
        500000,
        90,
        None,
        3,
    ),
    SeedCoupon(
        "FLAT200", "Rs.200 off orders over Rs.2,000", "FIXED", 20000, None, 200000, 30, None, 2
    ),
    SeedCoupon("FREESHIP", "Waives shipping on any order", "FIXED", 9900, None, 0, 60),
    SeedCoupon(
        "EXPIRED10",
        "A lapsed campaign, retained so the expiry path can be tested",
        "PERCENTAGE",
        1000,
        None,
        0,
        -7,
    ),
    SeedCoupon(
        "DISABLED",
        "A switched-off campaign, retained for the inactive path",
        "PERCENTAGE",
        5000,
        None,
        0,
        30,
        is_active=False,
    ),
]


# ===========================================================================
# Shipping
# ===========================================================================
SHIPPING_METHODS: list[dict[str, object]] = [
    {
        "code": "STANDARD",
        "name": "Standard delivery",
        "description": "3-5 business days. Free on orders over Rs.2,000.",
        "price": 9900,
        "free_above": 200000,
        "estimated_days_min": 3,
        "estimated_days_max": 5,
        "handling_fee": 0,
        "position": 1,
    },
    {
        "code": "EXPRESS",
        "name": "Express delivery",
        "description": "1-2 business days for in-stock items.",
        "price": 24900,
        "free_above": None,
        "estimated_days_min": 1,
        "estimated_days_max": 2,
        "handling_fee": 0,
        "position": 2,
    },
    {
        # Large ACP pylon boards travel differently from an A4 sticker. Offering
        # them through a courier as if they were a poster is how a delivery
        # goes wrong, so they get their own method.
        "code": "FREIGHT",
        "name": "Freight (large boards)",
        "description": "3-7 business days. For ACP and pylon boards over 36x48.",
        "price": 49900,
        "free_above": 1000000,
        "estimated_days_min": 3,
        "estimated_days_max": 7,
        "handling_fee": 0,
        "position": 3,
    },
]


# ===========================================================================
# Material guidance shown on the PDP
# ===========================================================================
MATERIAL_GUIDANCE = {
    "id": "material-selection-guide",
    "title": "Choosing a material",
    "intro": (
        "The right material depends on where the board goes and how long it has "
        "to last. This is the guide we give our own customers on the phone."
    ),
    "decisions": [
        (
            "Is it going outside or near a process area?",
            "3MM ACP",
            "Rigid, weatherproof, and the only option we recommend outdoors. Also "
            "the right choice for any board at eye level in a production area, "
            "where it gets handled and cleaned daily.",
        ),
        (
            "Is it indoors on a wall or a notice board?",
            "5MM FOAMSHEET",
            "Light, economical and easy to fix with tape or light screws. The "
            "standard budget choice when you need a room full of boards.",
        ),
        (
            "Does it need to be readable in darkness or power loss?",
            "AUTOGLOW STICKER",
            "Charges in normal light and glows for four to six hours. Specified for "
            "exit routes, muster points and equipment that is live when the lights "
            "are off.",
        ),
        (
            "Is it temporary, a handout, or on a smooth indoor surface?",
            "ECO VINYL STICKER",
            "Waterproof, self adhesive, and the lowest cost per board. The right "
            "choice for contractor packs and for displays that will be replaced.",
        ),
    ],
    "note": (
        "Not sure? Send us the location and the expected service life and we "
        "will tell you what we would order for ourselves. For volumes, request a "
        "bulk quote rather than a cart order."
    ),
}


# ===========================================================================
# Free / unverified content guard
# ===========================================================================
#: The live site publishes no testimonial, review, customer count or founding
#: year. The seed therefore publishes none. The review, rating and testimonial
#: rendering paths are fully implemented and simply render an empty state until
#: genuine, verifiable reviews are supplied.
TRUST_FACTS: list[dict[str, str]] = [
    {"label": "Materials", "value": "ACP, foam sheet, vinyl, autoglow"},
    {"label": "Sizes", "value": "8x12 to 48x96 inches"},
    {"label": "Based in", "value": "Ankleshwar GIDC, Gujarat"},
    {"label": "Delivery", "value": "Across India"},
    {"label": "B2B", "value": "Bulk quotes on request"},
]
