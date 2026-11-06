"""Kotiza logo geometry (100-unit grid). Run from this folder: python3 generate_logo.py -> writes SVGs into ./out"""
import math, os
os.makedirs("out", exist_ok=True)

INK = "#0E2E2B"          # obra-900  deep formwork green
CINTA = "#E0336E"        # survey flagging tape pink
CONCRETE = "#F2F4F0"     # concreto-50
CINTA_DARK = "#FF6F9C"   # cinta on dark grounds
GAP = 3
TOP, BOT, RIGHT = 12, 88, 88

def P(pts):  # polygon points string
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)

# ---------------------------------------------------------------- the mark
STEM_X, STEM_W = 12, 24
def stem_courses(heights):
    out, y = [], BOT
    for h in heights:
        out.append((STEM_X, y - h, STEM_W, h)); y -= h + GAP
    return out
COURSES = stem_courses((25, 19, 14, 9))            # labor, materials, equipment, indirects
COURSES_SMALL = stem_courses((40, 33))              # simplified for <= 24px

def arms(T=27):
    x0 = STEM_X + STEM_W + GAP
    x1 = RIGHT - T
    y0 = TOP + (x1 - x0)                            # 45 degrees
    upper = [(x0, y0), (x1, TOP), (RIGHT, TOP), (x0, y0 + T)]
    c = y0 + T + x0 + GAP * math.sqrt(2)            # upper arm's underside, pushed out by GAP: y = -x + c
    k_r, k_l = BOT - RIGHT, BOT - (RIGHT - T)       # lower arm edges: y = x + k
    xa = (c - k_r) / 2; xb = (c - k_l) / 2
    lower = [(xa, xa + k_r), (RIGHT, BOT), (RIGHT - T, BOT), (xb, xb + k_l)]
    return upper, lower
UPPER, LOWER = arms()

def mark(stem, arm, low, courses=COURSES):
    return ("".join(f'<rect fill="{stem}" x="{x}" y="{y}" width="{w}" height="{h}"/>' for x, y, w, h in courses)
            + f'<polygon fill="{arm}" points="{P(UPPER)}"/><polygon fill="{low}" points="{P(LOWER)}"/>')

# ---------------------------------------------------------------- the wordmark
CAP, S = 56, 11.5                                  # cap height, stroke

def slant(xt, xb, y0, y1, s=S):
    """Bar from top-centre xt to bottom-centre xb with perpendicular thickness s, flat cuts."""
    dx, dy = xb - xt, y1 - y0
    hw = s * math.hypot(dx, dy) / dy / 2           # half horizontal width
    return [(xt - hw, y0), (xt + hw, y0), (xb + hw, y1), (xb - hw, y1)]

def rect_pts(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]

def rrect_path(x, y, w, h, r):
    return (f"M{x+r},{y}H{x+w-r}A{r},{r} 0 0 1 {x+w},{y+r}V{y+h-r}A{r},{r} 0 0 1 {x+w-r},{y+h}"
            f"H{x+r}A{r},{r} 0 0 1 {x},{y+h-r}V{y+r}A{r},{r} 0 0 1 {x+r},{y}Z")

def L_K(x):
    w = 39
    upper = slant(x + w - S * 0.78, x + S + 2.0, 0, CAP * 0.62)     # rises from the stem to the top-right
    lower = slant(x + S + 7.5, x + w - S * 0.78, CAP * 0.40, CAP)    # drops from the upper arm to the foot
    return [("poly", rect_pts(x, 0, S, CAP)), ("poly", upper), ("poly", lower)], w

def L_O(x):
    w = 40
    return [("path", rrect_path(x, 0, w, CAP, 15) + rrect_path(x + S, S, w - 2 * S, CAP - 2 * S, 5))], w

def L_T(x):
    w = 38
    return [("poly", rect_pts(x, 0, w, S)), ("poly", rect_pts(x + (w - S) / 2, 0, S, CAP))], w

def L_I(x):
    return [("poly", rect_pts(x, 0, S, CAP))], S

def L_Z(x):
    w = 38
    return [("poly", rect_pts(x, 0, w, S)), ("poly", rect_pts(x, CAP - S, w, S)),
            ("poly", slant(x + w - S * 0.75, x + S * 0.75, S - 0.5, CAP - S + 0.5))], w

def L_A(x):
    w = 43
    cx = x + w / 2
    left = slant(cx - 3.2, x + S * 0.62, 0, CAP)
    right = slant(cx + 3.2, x + w - S * 0.62, 0, CAP)
    bar = rect_pts(x + 9, CAP - 21, w - 18, 9.5)
    return [("poly", left), ("poly", right), ("poly", bar)], w

def wordmark(color, track=7.5):
    out, x = [], 0
    for fn in (L_K, L_O, L_T, L_I, L_Z, L_A):
        shapes, w = fn(x)
        for kind, s in shapes:
            out.append(f'<polygon fill="{color}" points="{P(s)}"/>' if kind == "poly"
                       else f'<path fill="{color}" fill-rule="evenodd" d="{s}"/>')
        x += w + track
    return "".join(out), x - track

# ---------------------------------------------------------------- files
def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}" width="{w:g}" height="{h:g}" '
            f'role="img" aria-label="{title}"><title>{title}</title>{body}</svg>\n')

def write(name, w, h, body, title="Kotiza"):
    open(f"out/{name}", "w").write(svg(w, h, body, title))

write("kotiza-mark.svg", 100, 100, mark(INK, CINTA, INK), "Kotiza")
write("kotiza-mark-reverse.svg", 100, 100, mark(CONCRETE, CINTA_DARK, CONCRETE), "Kotiza")
write("kotiza-mark-ink.svg", 100, 100, mark(INK, INK, INK), "Kotiza")
write("kotiza-mark-white.svg", 100, 100, mark("#FFFFFF", "#FFFFFF", "#FFFFFF"), "Kotiza")
write("kotiza-mark-small.svg", 100, 100, mark(INK, CINTA, INK, COURSES_SMALL), "Kotiza")
tile = f'<rect width="100" height="100" rx="22" fill="{INK}"/><g transform="translate(17 17) scale(0.66)">'
write("kotiza-app-icon.svg", 100, 100, tile + mark(CONCRETE, CINTA_DARK, CONCRETE) + "</g>", "Kotiza")
write("kotiza-favicon.svg", 100, 100, tile + mark(CONCRETE, CINTA_DARK, CONCRETE, COURSES_SMALL) + "</g>", "Kotiza")

def lockup(name, stem, arm, low, word):
    wm, ww = wordmark(word)
    gap = 24
    W = 100 + gap + ww
    body = mark(stem, arm, low) + f'<g transform="translate({100 + gap} {(TOP + BOT) / 2 - CAP / 2:g})">{wm}</g>'
    write(name, round(W, 1), 100, body)
lockup("kotiza-lockup.svg", INK, CINTA, INK, INK)
lockup("kotiza-lockup-reverse.svg", CONCRETE, CINTA_DARK, CONCRETE, CONCRETE)
wm, ww = wordmark(INK); write("kotiza-wordmark.svg", round(ww, 1), CAP, wm)
wm, ww = wordmark(CONCRETE); write("kotiza-wordmark-reverse.svg", round(ww, 1), CAP, wm)
print("courses", COURSES); print("upper", [tuple(round(v, 2) for v in p) for p in UPPER]); print("lower", [tuple(round(v, 2) for v in p) for p in LOWER])
