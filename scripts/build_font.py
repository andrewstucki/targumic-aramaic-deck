#!/usr/bin/env python3
"""Build `Onqelos` — a Hebrew font that renders Babylonian supralinear vocalization.

Scope is deliberately narrow: the 27 consonants plus the seven simple-system
supralinear vowel signs. No dagesh, rafe, shin/sin marks, meteg or accents —
those codepoints render as nothing so that pasted Tiberian text degrades
quietly instead of showing tofu.

The seven signs are dual-mapped, so either input route produces the same glyph:

  sign  proposed (L2/26-038)          Tiberian aliases
  a     U+05C8 BABYLONIAN PATAH       patah, segol, hataf patah, hataf segol
  a:    U+05C9 BABYLONIAN QAMATS      qamats
  e     U+05CA BABYLONIAN TSERE       tsere
  i     U+05CB BABYLONIAN HIRIQ       hiriq
  o     U+05CC BABYLONIAN HOLAM       holam, holam haser, qamats qatan,
                                      hataf qamats
  u     U+05CD BABYLONIAN QUBUTS      qubuts
  @     U+05CE BABYLONIAN HITFA       sheva

`a` and `a:` have narrow variants used over skinny letters, selected
contextually.

Base: Ezra SIL 2.51 (OFL, Reserved Font Names "SIL" and "Ezra" — hence the
different name here). Design constants below are expressed per 1000 units and
scaled to the base font's own em, so a base at any upem works.
"""

import hashlib
import io
import math
import os
import urllib.request
import zipfile
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.misc.transform import Transform
from fontTools.subset import Subsetter, Options
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

# The script lives in scripts/; everything it reads and writes lands in the
# project root.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "SILEOT.ttf")
BASE_URL = "https://software.sil.org/downloads/r/ezra/EzraSIL-2.51.zip"
BASE_SHA256 = "f16bcb3ec4473ac6a9f138ee0dbde7cc2f835e93a90cbe8649b3f32677760cc1"
# Taken out of the archive: the font, and the license that has to travel with
# anything derived from it. The license is renamed on the way out — dropped in
# the root as "Licenses.txt" it reads like this project's own.
BASE_FILES = {"SILEOT.ttf": "SILEOT.ttf",
              "Licenses.txt": "EzraSIL-Licenses.txt"}

FAMILY = "Onqelos"
VERSION = "1.000"

OUT = os.path.join(ROOT, f"{FAMILY}-Regular.ttf")
FEA_OUT = os.path.join(ROOT, f"{FAMILY.lower()}.fea")
SHEET_OUT = os.path.join(ROOT, f"{FAMILY.lower()}-sheet.svg")

# Every measurement below is per 1000 em units and multiplied by `scale`
# (the base font's upem / 1000) before use.
UPEM_REF = 1000
# Gap between the top of the letter and the bottom of the mark.
CLEARANCE = 55
# Letters whose ink is narrower than this get the short vowel variants.
# The consonants split cleanly: 222-308 units, then 485 and up.
NARROW_MAX = 400

# The slash is the one that matters: variant spellings are written a/b, and
# without it that character comes out .notdef.
PUNCTUATION = [("slash", 0x002F), ("space", 0x0020), ("maqaf", 0x05BE)]

CONSONANTS = [
    ("alef", 0x05D0), ("bet", 0x05D1), ("gimel", 0x05D2), ("dalet", 0x05D3),
    ("he", 0x05D4), ("vav", 0x05D5), ("zayin", 0x05D6), ("het", 0x05D7),
    ("tet", 0x05D8), ("yod", 0x05D9), ("finalkaf", 0x05DA), ("kaf", 0x05DB),
    ("lamed", 0x05DC), ("finalmem", 0x05DD), ("mem", 0x05DE),
    ("finalnun", 0x05DF), ("nun", 0x05E0), ("samekh", 0x05E1),
    ("ayin", 0x05E2), ("finalpe", 0x05E3), ("pe", 0x05E4),
    ("finaltsadi", 0x05E5), ("tsadi", 0x05E6), ("qof", 0x05E7),
    ("resh", 0x05E8), ("shin", 0x05E9), ("tav", 0x05EA),
]

# Marks reused from the base font's Tiberian outlines: the textbook's e/i/o/@
# are the same shapes as tsere/hiriq/sheva/patah, only supralinear.
REUSED = {
    "babTsere": ("tsere", Transform()),
    "babHiriq": ("hiriq", Transform()),
    "babHolam": ("sheva", Transform()),
    # the hitfa bar is wider than a patah; u is the same bar stood upright
    "babHitfa": ("patah", Transform().scale(1.35, 1.0)),
    "babQubuts": ("patah", Transform().rotate(math.radians(90))),
}

DRAWN = ["babPatah", "babPatah.short", "babQamats", "babQamats.short"]
MARKS = list(REUSED) + DRAWN
# Marks that centring would crowd against lamed's ascender get a second
# anchor there; the set is derived at build time. Other bases anchor both
# classes identically.
LAMED_GAP = 12      # clear space to leave between the ascender and a wide mark
# Over a narrow letter, o and u sit at its left edge rather than centered, as
# the textbook has them — measured there to within a few units.
OU = ["babHolam", "babQubuts"]
OU_INSET = 10       # how far inside the left edge the mark's center sits

# sign -> (proposed codepoint, [Tiberian aliases])
CMAP_PLAN = {
    "babPatah":  (0x05C8, [0x05B7, 0x05B6, 0x05B2, 0x05B1]),
    "babQamats": (0x05C9, [0x05B8]),
    "babTsere":  (0x05CA, [0x05B5]),
    "babHiriq":  (0x05CB, [0x05B4]),
    "babHolam":  (0x05CC, [0x05B9, 0x05BA, 0x05C7, 0x05B3]),
    "babQubuts": (0x05CD, [0x05BB]),
    "babHitfa":  (0x05CE, [0x05B0]),
}

# Columns of the coverage sheet: the textbook's label, and what you type.
VOWELS = [
    ("a", 0x05B7), ("ā", 0x05B8), ("e", 0x05B5), ("i", 0x05B4),
    ("o", 0x05B9), ("u", 0x05BB), ("ǝ", 0x05B0),
]
SHEET_EM = 52          # px per em on the sheet
SHEET_GUTTER = 104     # px reserved for the consonant names
SHEET_HEADER = 30

# Tiberian marks this font deliberately drops: mapped to an empty glyph so
# pasted pointed text loses them silently rather than showing .notdef boxes.
DROPPED = (
    [0x05BC, 0x05BD, 0x05BF, 0x05C1, 0x05C2, 0x05C4, 0x05C5]  # dagesh..dots
    + list(range(0x0591, 0x05AF))                             # accents
)


def stroke(pen, p0, p1, width, extend=0.0):
    """A thick line segment, as one clockwise quad.

    Everything here is wound clockwise, so TrueType's nonzero fill unions
    overlapping contours and the joins need no boolean geometry.
    """
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    x0 -= ux * extend
    y0 -= uy * extend
    x1 += ux * extend
    y1 += uy * extend
    nx, ny = -uy * width / 2, ux * width / 2
    pen.moveTo((round(x0 + nx), round(y0 + ny)))
    pen.lineTo((round(x1 + nx), round(y1 + ny)))
    pen.lineTo((round(x1 - nx), round(y1 - ny)))
    pen.lineTo((round(x0 - nx), round(y0 - ny)))
    pen.closePath()


def rect(pen, x0, y0, x1, y1):
    pen.moveTo((round(x0), round(y1)))
    pen.lineTo((round(x1), round(y1)))
    pen.lineTo((round(x1), round(y0)))
    pen.lineTo((round(x0), round(y0)))
    pen.closePath()


def line_cross(p, u, q, v):
    """Where line p+t*u meets line q+s*v, or None if they are parallel."""
    den = u[0] * v[1] - u[1] * v[0]
    if abs(den) < 1e-9:
        return None
    t = ((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / den
    return (p[0] + t * u[0], p[1] + t * u[1])


def fillet(pen, corner, dir_a, dir_b, r, overlap=0.0):
    """Round a concave corner with one quadratic.

    `dir_a`/`dir_b` point away from the corner along each edge. The control
    point is the corner itself, where the two tangents meet, which is what
    lands the curve tangent to both edges.

    `overlap` sinks the straight legs back into the filled material. Without
    it they abut the neighbouring contour exactly, integer rounding leaves a
    sub-unit gap, and that rasterizes as a hairline seam.
    """
    a = (corner[0] + dir_a[0] * r, corner[1] + dir_a[1] * r)
    b = (corner[0] + dir_b[0] * r, corner[1] + dir_b[1] * r)
    bx, by = dir_a[0] + dir_b[0], dir_a[1] + dir_b[1]
    norm = math.hypot(bx, by) or 1.0
    inner = (corner[0] - bx / norm * overlap,
             corner[1] - by / norm * overlap)
    # keep the winding clockwise, as `stroke` and `disc` are
    if ((inner[0] - a[0]) * (b[1] - inner[1])
            - (inner[1] - a[1]) * (b[0] - inner[0])) > 0:
        a, b = b, a
    rnd = lambda p: (round(p[0]), round(p[1]))
    pen.moveTo(rnd(a))
    pen.lineTo(rnd(inner))
    pen.lineTo(rnd(b))
    pen.qCurveTo(rnd(corner), rnd(a))
    pen.closePath()


def disc(pen, cx, cy, r, segments=8):
    """A circle as quadratic segments, wound clockwise like `stroke`."""
    ctrl_r = r / math.cos(math.pi / segments)
    on = []
    off = []
    for i in range(segments):
        a = -2 * math.pi * i / segments          # negative = clockwise
        b = a - math.pi / segments
        on.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        off.append((cx + ctrl_r * math.cos(b), cy + ctrl_r * math.sin(b)))
    pen.moveTo((round(on[0][0]), round(on[0][1])))
    for i in range(segments):
        nxt = on[(i + 1) % segments]
        pen.qCurveTo((round(off[i][0]), round(off[i][1])),
                     (round(nxt[0]), round(nxt[1])))
    pen.closePath()


# The two signs with no Tiberian counterpart, traced from the textbook's own
# pointing. The images they were traced from are gone, so these numbers are
# the only record of them.
NIB = 50            # the two strokes of each sign
BAR_W = 44          # the horizontal bar
SEAT = 16           # how far a stroke is sunk into the bar, so they join
FILLET = 40         # radius of the curve at each stroke/bar corner
OVERLAP = 10        # how far a fillet is sunk into the material it joins
SWEEP_STEPS = 16    # flattening resolution for the curved short form
SIGNS = {
    # miniature ayin: one swept stroke with a stem standing on it. The short
    # form is the same stroke begun at `short_t0`, which drops the tail.
    "babPatah": {
        "sweep": {
            "cubic": [(0, 0), (0, 0), (250, -38), (420, 115)],
            "stem_t": 0.645,
            "stem": (38, 150),
            "short_t0": 0.605,
        },
    },
    # side arrow: one arm rising right, one falling right
    "babQamats": {
        "arms": [(115, 99), (181, -82)],
        "bar_y": 0,
        "bar_x": {"long": (-275, 22), "short": (-33, 22)},
    },
}


def cubic_at(cubic, t):
    """The point at parameter t on a cubic."""
    p0, p1, p2, p3 = cubic
    m = 1 - t
    return (
        m * m * m * p0[0] + 3 * m * m * t * p1[0]
        + 3 * m * t * t * p2[0] + t * t * t * p3[0],
        m * m * m * p0[1] + 3 * m * m * t * p1[1]
        + 3 * m * t * t * p2[1] + t * t * t * p3[1],
    )


def cubic_points(cubic, steps, t0=0.0):
    """Flatten a cubic to a polyline, optionally starting partway along it."""
    return [cubic_at(cubic, t0 + (1.0 - t0) * i / steps)
            for i in range(steps + 1)]


def polyline(pen, pts, width):
    """Stroke a polyline with round joins at the interior vertices.

    Two traps. A join disc goes in only where it cannot reach past either
    end, or it bulges out and rounds off the flat cap — which happens
    whenever the vertex spacing is finer than the half-width. And segments
    are overlapped slightly so neighbouring quads intersect rather than meet
    edge-to-edge, which can rasterize as a pinhole; the discs are then
    exactly half the stroke, so they round each join without standing proud
    and scalloping the long edge.
    """
    r = width / 2
    bleed = r * 0.06
    run = [0.0]
    for p0, p1 in zip(pts, pts[1:]):
        run.append(run[-1] + math.hypot(p1[0] - p0[0], p1[1] - p0[1]))
        if run[-1] - run[-2] > 0.5:
            stroke(pen, p0, p1, width, extend=bleed)
    for i in range(1, len(pts) - 1):
        if run[i] >= r and run[-1] - run[i] >= r:
            disc(pen, pts[i][0], pts[i][1], r)


def draw_sweep(spec, scale, t0=0.0):
    """One swept stroke with a stem standing on it.

    The sweep is given in its own coordinates; everything is shifted so the
    point at `stem_t` is the origin, which is what keeps the stem's foot on
    the curve rather than floating beside it. `t0` starts the sweep partway
    along, which is how the short form drops its tail: the same stroke, begun
    later, not a different shape.
    """
    pen = TTGlyphPen(None)
    cubic = [(x * scale, y * scale) for x, y in spec["cubic"]]
    ox, oy = cubic_at(cubic, spec["stem_t"])
    cubic = [(x - ox, y - oy) for x, y in cubic]

    # Spacing has to stay wider than the join discs — see `polyline`. The
    # sweep is shallow enough that the chord error here is under a unit.
    radius = NIB * scale / 2
    probe = cubic_points(cubic, 64, t0)
    length = sum(math.hypot(b[0] - a[0], b[1] - a[1])
                 for a, b in zip(probe, probe[1:]))
    steps = max(3, min(SWEEP_STEPS, int(length / (radius * 1.2))))
    polyline(pen, cubic_points(cubic, steps, t0), NIB * scale)
    tip = (spec["stem"][0] * scale, spec["stem"][1] * scale)
    stroke(pen, (0, 0), tip, NIB * scale)
    disc(pen, 0, 0, NIB * scale / 2)
    return pen.glyph()


def draw_sign(name, scale):
    spec = SIGNS[name.split(".")[0]]
    variant = "short" if name.endswith(".short") else "long"
    if "sweep" in spec:
        sweep = spec["sweep"]
        return draw_sweep(sweep, scale,
                          sweep["short_t0"] if variant == "short" else 0.0)
    pen = TTGlyphPen(None)

    half = NIB * scale / 2
    bar_y = spec["bar_y"] * scale
    top = bar_y + BAR_W * scale / 2
    bottom = bar_y - BAR_W * scale / 2
    x0, x1 = (v * scale for v in spec["bar_x"][variant])
    rect(pen, x0, bottom, x1, top)

    for ax, ay in spec["arms"]:
        tip = (ax * scale, ay * scale)
        length = math.hypot(*tip)
        u = (tip[0] / length, tip[1] / length)
        # sink the stroke into the bar so the two shapes merge cleanly
        root = (-u[0] * SEAT * scale, -u[1] * SEAT * scale)
        stroke(pen, root, tip, NIB * scale)

        edge = top if u[1] > 0 else bottom
        for side in (1, -1):
            perp = (-u[1] * side * half, u[0] * side * half)
            corner = line_cross(perp, u, (0, edge), (1, 0))
            if corner is None or not x0 < corner[0] < x1:
                continue
            # Away from the stroke's axis, but no further than the bar runs:
            # the narrow form's bar is shorter than FILLET, and a leg that
            # overshoots its end leaves a spike standing out past the stroke.
            along = (1, 0) if -u[1] * side > 0 else (-1, 0)
            room = (x1 - corner[0]) if along[0] > 0 else (corner[0] - x0)
            r = min(FILLET * scale, room)
            if r < NIB * scale / 8:
                continue
            fillet(pen, corner, u, along, r, overlap=OVERLAP * scale)
    return pen.glyph()


def copy_glyph(glyph_set, source, transform):
    rec = RecordingPen()
    glyph_set[source].draw(rec)
    pen = TTGlyphPen(None)
    rec.replay(TransformPen(pen, transform))
    return pen.glyph()


def normalize_mark(glyph, glyf):
    """Sit the mark on y=0 with xMin=0, and return its anchor point."""
    glyph.recalcBounds(glyf)
    dx, dy = -glyph.xMin, -glyph.yMin
    if glyph.numberOfContours:
        coords, endPts, flags = glyph.getCoordinates(glyf)
        for i in range(len(coords)):
            coords[i] = (coords[i][0] + dx, coords[i][1] + dy)
        glyph.coordinates = coords
    glyph.recalcBounds(glyf)
    return ((glyph.xMin + glyph.xMax) // 2, 0)


def render_sheet(ttf_path, out_path):
    """Every consonant against every vowel, shaped by HarfBuzz.

    Shaped rather than drawn from the anchor values this script just computed,
    so the sheet is an independent check: if a layout rule regresses the way
    the DFLT-only `mark` feature once did, the marks move here too.
    """
    import uharfbuzz as hb
    from fontTools.pens.svgPathPen import SVGPathPen

    tt = TTFont(ttf_path)
    glyph_set = tt.getGlyphSet()
    glyf = tt["glyf"]
    hb_font = hb.Font(hb.Face(hb.Blob.from_file_path(ttf_path)))

    paths = {}

    def path_for(name):
        if name not in paths:
            pen = SVGPathPen(glyph_set)
            glyph_set[name].draw(pen)
            paths[name] = pen.getCommands()
        return paths[name]

    cells = {}
    extent = {}
    widest = 0
    for row, (cname, ccp) in enumerate(CONSONANTS):
        lo = hi = 0
        for col, (_, vcp) in enumerate(VOWELS):
            buf = hb.Buffer()
            buf.add_str(chr(ccp) + chr(vcp))
            buf.guess_segment_properties()
            hb.shape(hb_font, buf)
            x, items = 0, []
            for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
                name = tt.getGlyphName(info.codepoint)
                items.append((name, x + pos.x_offset, pos.y_offset))
                g = glyf[name]
                if g.numberOfContours:
                    lo = min(lo, g.yMin + pos.y_offset)
                    hi = max(hi, g.yMax + pos.y_offset)
                x += pos.x_advance
            widest = max(widest, x)
            cells[(row, col)] = (items, x)
        extent[row] = (lo, hi)

    s = SHEET_EM / tt["head"].unitsPerEm
    cell_w = round(widest * s) + 18
    pad = 12
    width = SHEET_GUTTER + cell_w * len(VOWELS)

    # Rows are sized to their own ink, so only lamed pays for an ascender and
    # only the five descenders pay for a tail.
    geom = {}
    y = SHEET_HEADER
    for row in range(len(CONSONANTS)):
        lo, hi = extent[row]
        h = round((hi - lo) * s) + pad
        geom[row] = (y, h, round(hi * s) + pad // 2)
        y += h
    height = y + 20

    narrow_rows = {
        row for row in range(len(CONSONANTS))
        if any(n.endswith(".short") for n, _, _ in cells[(row, 0)][0])
    }

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        '<style>'
        'text{font-family:ui-sans-serif,system-ui,sans-serif;fill:#111}'
        '.lbl{font-size:13px;fill:#555}'
        '.hdr{font-size:15px;font-weight:600;text-anchor:middle}'
        '.note{font-size:11px;fill:#888}'
        '</style>',
        f'<rect width="{width}" height="{height}" fill="#fff"/>',
    ]
    for row in narrow_rows:
        y, h, _ = geom[row]
        out.append(f'<rect x="0" y="{y}" width="{width}" height="{h}" '
                   f'fill="#f0f4f8"/>')
    for col, (label, _) in enumerate(VOWELS):
        cx = SHEET_GUTTER + col * cell_w + cell_w // 2
        out.append(f'<text class="hdr" x="{cx}" y="20">{label}</text>')
    for row, (cname, _) in enumerate(CONSONANTS):
        y, h, base_y = geom[row]
        out.append(f'<text class="lbl" x="10" y="{y + base_y}">{cname}</text>')
        out.append(f'<line x1="0" y1="{y}" x2="{width}" y2="{y}" '
                   f'stroke="#e5e5e5"/>')
        for col in range(len(VOWELS)):
            items, run = cells[(row, col)]
            ox = SHEET_GUTTER + col * cell_w + (cell_w - run * s) / 2
            out.append(f'<g transform="translate({ox:.2f},{y + base_y}) '
                       f'scale({s:.5f},{-s:.5f})">')
            for name, dx, dy in items:
                d = path_for(name)
                if d:
                    out.append(f'<path transform="translate({dx},{dy})" '
                               f'd="{d}"/>')
            out.append('</g>')
    out.append(f'<text class="note" x="10" y="{height - 6}">'
               f'{FAMILY} {VERSION} — tinted rows take the narrow variants of '
               f'a and ā automatically; nothing different is typed.</text>')
    out.append('</svg>')

    with open(out_path, "w") as fh:
        fh.write("\n".join(out))
    return len(cells), sorted(CONSONANTS[r][0] for r in narrow_rows)


def fetch_base():
    """Download Ezra SIL unless it is already here.

    Entries are written by their own chosen basename into the project root, so
    a hostile archive cannot place a file outside it. Delete SILEOT.ttf to
    re-fetch.
    """
    if os.path.exists(BASE):
        return
    print(f"fetching {BASE_URL}")
    with urllib.request.urlopen(BASE_URL, timeout=120) as response:
        blob = response.read()
    digest = hashlib.sha256(blob).hexdigest()
    if digest != BASE_SHA256:
        raise SystemExit(f"checksum mismatch for {BASE_URL}\n"
                         f"  expected {BASE_SHA256}\n"
                         f"  got      {digest}")
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        wanted = {n: e for e in archive.namelist()
                  for n in BASE_FILES if os.path.basename(e) == n}
        missing = set(BASE_FILES) - set(wanted)
        if missing:
            raise SystemExit(f"{BASE_URL} is missing {sorted(missing)}")
        for name, entry in wanted.items():
            out = BASE_FILES[name]
            with archive.open(entry) as src:
                with open(os.path.join(ROOT, out), "wb") as dst:
                    dst.write(src.read())
            print(f"  extracted {out}")


def main():
    fetch_base()
    font = TTFont(BASE)
    scale = font["head"].unitsPerEm / UPEM_REF
    glyph_set = font.getGlyphSet()
    glyf = font["glyf"]

    # Capture the outlines we reuse before subsetting can discard them.
    reused_glyphs = {
        new: copy_glyph(glyph_set, src, tf) for new, (src, tf) in REUSED.items()
    }

    keep = [n for n, _ in CONSONANTS] + [n for n, _ in PUNCTUATION]
    opts = Options()
    opts.layout_features = []          # drop all of the base's Tiberian logic
    opts.glyph_names = True
    opts.notdef_outline = True
    opts.recalc_bounds = True
    # per-glyph device metrics that would be stale once glyphs are added
    opts.drop_tables += ["hdmx", "VDMX"]
    sub = Subsetter(options=opts)
    sub.populate(glyphs=keep)
    sub.subset(font)

    glyf = font["glyf"]
    hmtx = font["hmtx"]

    # --- add the marks -----------------------------------------------------
    anchors = {}
    for name in MARKS:
        glyph = reused_glyphs[name] if name in reused_glyphs else draw_sign(name, scale)
        glyf.glyphs[name] = glyph
        anchors[name] = normalize_mark(glyph, glyf)
        hmtx.metrics[name] = (0, glyph.xMin if glyph.numberOfContours else 0)

    glyf.glyphs["nullmark"] = TTGlyphPen(None).glyph()
    hmtx.metrics["nullmark"] = (0, 0)

    order = font.getGlyphOrder()
    new = [g for g in MARKS + ["nullmark"] if g not in order]
    font.setGlyphOrder(list(order) + new)
    font["maxp"].numGlyphs = len(font.getGlyphOrder())

    # --- cmap --------------------------------------------------------------
    table = {}
    for name, cp in CONSONANTS:
        table[cp] = name
    for name, cp in PUNCTUATION:
        table[cp] = name
    for name, (proposed, aliases) in CMAP_PLAN.items():
        table[proposed] = name
        for cp in aliases:
            table[cp] = name
    for cp in DROPPED:
        table[cp] = "nullmark"
    for sub_table in font["cmap"].tables:
        sub_table.cmap = dict(table)

    # --- layout ------------------------------------------------------------
    narrow = [
        n for n, _ in CONSONANTS
        if (glyf[n].xMax - glyf[n].xMin) < NARROW_MAX * scale
    ]
    print(f"narrow bases -> short vowels: {' '.join(narrow)}")

    # One height for every letter. Lamed's yMax is no guide: the stroke that
    # reaches it is narrow and sits left of where a mark goes, and lamed's own
    # top line is below the common top, so the ascender just rises beside it.
    ref_top = max(glyf[n].yMax for n, _ in CONSONANTS if n != "lamed")

    lines = []
    # Both matter: HarfBuzz will not fall back from `hebr` to `DFLT` for GPOS,
    # so a mark feature registered only under DFLT is silently ignored and
    # marks land wherever Unicode's combining class says they belong — which
    # for these Tiberian codepoints is under the letter.
    lines.append("languagesystem DFLT dflt;")
    lines.append("languagesystem hebr dflt;")
    lines.append("@narrow = [%s];" % " ".join(narrow))
    lines.append("@bases = [%s];" % " ".join(
        [n for n, _ in CONSONANTS] + [n for n, _ in PUNCTUATION]))
    lines.append("@babMarks = [%s];" % " ".join(MARKS))
    lines.append("table GDEF { GlyphClassDef @bases, , [@babMarks nullmark], ; } GDEF;")

    lines.append("lookup babShorten {")
    lines.append("    sub babPatah by babPatah.short;")
    lines.append("    sub babQamats by babQamats.short;")
    lines.append("} babShorten;")
    lines.append("lookup babNarrowCtx {")
    lines.append("    sub @narrow [babPatah babQamats]' lookup babShorten;")
    lines.append("} babNarrowCtx;")
    for feat in ("calt", "rclt"):
        lines.append(f"feature {feat} {{ lookup babNarrowCtx; }} {feat};")

    # How far right lamed's ascender reaches in the band a mark occupies.
    lam = glyf["lamed"]
    lam_pts, _, _ = lam.getCoordinates(glyf)
    asc_right = max((p[0] for p in lam_pts if p[1] > ref_top), default=0)

    # A class per mark, so the anchor can depend on the (base, mark) pair —
    # what MarkBasePos models anyway. One shared class had to suit its widest
    # member, over-shifting every narrower mark on lamed.
    for name in MARKS:
        ax, ay = anchors[name]
        lines.append(f"markClass {name} <anchor {ax} {ay}> @MC_{name};")

    nudged = []
    lines.append("feature mark {")
    for name, _ in CONSONANTS:
        g = glyf[name]
        # One height for every letter. Lamed's yMax of 2173 is no guide: the
        # stroke reaching it is narrow and off to the left of the mark, and
        # lamed's own top horizontal line is below the common top.
        cy = round(ref_top + CLEARANCE * scale)
        cx = (g.xMin + g.xMax) // 2
        spec = []
        for mark in MARKS:
            mw = glyf[mark].xMax - glyf[mark].xMin
            if name in narrow and mark in OU:
                # over a narrow letter o and u sit on its left edge
                mx = round(g.xMin + OU_INSET * scale)
            elif name == "lamed" and f"{mark}.short" in MARKS:
                # Only a and ā are wide enough to warrant it — they are the
                # two with narrow variants, so that is the test. Everything
                # else stays centered on lamed like any other letter, even
                # where that leaves it close to the ascender.
                mx = max(cx, round(asc_right + LAMED_GAP * scale + mw / 2))
                if mx > cx:
                    nudged.append(f"{mark}+{mx - cx}")
            else:
                mx = cx
            spec.append(f"<anchor {mx} {cy}> mark @MC_{mark}")
        lines.append(f"    pos base {name} " + " ".join(spec) + ";")
    lines.append("} mark;")

    print("nudged right on lamed to clear its ascender: "
          + (" ".join(nudged) or "none"))

    fea = "\n".join(lines)
    with open(FEA_OUT, "w") as fh:
        fh.write(fea + "\n")
    addOpenTypeFeaturesFromString(font, fea)

    # --- names -------------------------------------------------------------
    ps = f"{FAMILY}-Regular"
    names = {
        1: FAMILY,
        2: "Regular",
        3: f"{VERSION};{ps}",
        4: f"{FAMILY} Regular",
        5: f"Version {VERSION}",
        6: ps,
        0: ("Base outlines copyright (c) 1997-2007 SIL International "
            "(https://www.sil.org/), with Reserved Font Names \"SIL\" and "
            "\"Ezra\". Babylonian supralinear vowel signs added in this "
            "derivative, which is not named with either reserved name."),
        # OFL 1.1 §5: a Modified Version of an OFL font must itself be
        # distributed under the OFL, so this cannot carry the project's MIT
        # license. §2 accepts the notice in these metadata fields.
        13: ("Licensed under the SIL Open Font License, Version 1.1. "
             "The full text ships alongside as EzraSIL-Licenses.txt and is "
             "at https://openfontlicense.org/."),
        14: "https://openfontlicense.org/",
    }
    name_table = font["name"]
    name_table.names = []
    for nid, val in names.items():
        name_table.setName(val, nid, 3, 1, 0x409)
        name_table.setName(val, nid, 1, 0, 0)

    font["head"].fontRevision = float(VERSION)
    font["maxp"].recalc(font)
    font.save(OUT)
    font.flavor = "woff2"
    font.save(OUT.replace(".ttf", ".woff2"))
    print(f"wrote {OUT} (+ .woff2)")
    print(f"glyphs: {len(font.getGlyphOrder())}  "
          f"cmap entries: {len(table)}")

    try:
        n, short_rows = render_sheet(OUT, SHEET_OUT)
    except ImportError:
        print("skipped the proof sheet: pip install uharfbuzz")
    else:
        print(f"wrote {SHEET_OUT} ({n} cells; "
              f"narrow variants over {' '.join(short_rows)})")


if __name__ == "__main__":
    main()
