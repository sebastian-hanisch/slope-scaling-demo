"""Konstanten, Regler-Grenzen, Presets und feste Seed-Mengen der Demo "Slope Scaling: Fixkosten linearisieren"."""

# --- Regler Distributionsnetz -----------------------------------------------------------------------------------------------------
P_MIN, P_MAX, DEFAULT_P = 2, 6, 3            # Werke
D_MIN, D_MAX, DEFAULT_D = 2, 6, 3            # Verteilzentren
S_MIN, S_MAX, DEFAULT_S = 3, 12, 8           # Filialen
DENSITY_MIN, DENSITY_MAX, DEFAULT_DENSITY = 20, 100, 60   # Anteil vorhandener Lanes in ganzen Prozent, Schritt 10
SPREAD_MIN, SPREAD_MAX, DEFAULT_SPREAD = 0, 100, 50       # Streuung der Lane-Breiten in ganzen Prozent, Schritt 25
LOAD_MIN, LOAD_MAX, DEFAULT_LOAD = 30, 90, 50             # Gesamtnachfrage in Prozent der Werkskapazität, Schritt 10
FIX_MIN, FIX_MAX, DEFAULT_FIX = 5, 150, 30                # Fixkosten-Basis je Lane (mal 1 bis 3; Verteilzentrum doppelt), Schritt 5
DEFAULT_SEED = 155
SEED_MAX = 2_000_000_000

# --- Regler Streckennetz ------------------------------------------------------------------------------------------------------------
GW_MIN, GW_MAX, DEFAULT_GW = 3, 6, 4                      # Breite des Gitters
GH_MIN, GH_MAX, DEFAULT_GH = 3, 5, 3                      # Höhe des Gitters
GDENSITY_MIN, GDENSITY_MAX, DEFAULT_GDENSITY = 40, 100, 60   # Anteil der Gitterkanten (über den Spannbaum hinaus), Schritt 10
GCAP_MIN, GCAP_MAX, DEFAULT_GCAP = 1, 4, 4                # größte Kapazität je Kante und Richtung
GDEM_MIN, GDEM_MAX, DEFAULT_GDEM = 1, 5, 2                # größte Menge je Gut
DEFAULT_GSEED = 6

K_MIN, K_MAX, DEFAULT_K = 1, 5, 3            # Zahl der Güter

NETS = {
    "random": "Distributionsnetz (wie im Vorgänger)",
    "grid": "Streckennetz (Gitter mit Start-Ziel-Aufträgen)",
    "bigm": "Big-M-Falle: eine Menge von 1, eine Kante mit Kapazität 10",
    "rounding": "Rundungs-Falle: 3 Einheiten über zwei Kanten der Kapazität 2",
    "bundle": "Bündelung: zwei Güter teilen eine Stammstrecke",
}
DEFAULT_NET = "random"
FIXED_NETS = ("bigm", "rounding", "bundle")

STARTS = {"cap": "Kapazität (ausgelastet gedacht)", "demand": "halbe Gesamtnachfrage (vorsichtiger)"}
DEFAULT_START = "cap"
ONOFF = {"off": "aus", "on": "an"}
DEFAULT_MEMORY = "off"
DEFAULT_PERTURB = "on"
DEFAULT_POLISH = "on"
DAMPINGS = (0.0, 0.5)
DEFAULT_DAMPING = 0.5
ITERS = (10, 30, 60)
DEFAULT_ITER = 30
CONTROLS = {"normal": "wie beschrieben", "once": "Negativkontrolle: nur ein LP (Steigung nie angepasst)", "last": "Negativkontrolle: letzte statt beste Iteration"}
DEFAULT_CONTROL = "normal"

# --- feste Seed-Mengen (dieselben wie in den Vorgänger-Demos; unabhängig vom Nutzer-Seed) ------------------------------------------
DIST_SEEDS = tuple(range(100000, 100100))
QUALITY_SEEDS = DIST_SEEDS[:40]                     # Verteilung der Lücke
VARIANT_SEEDS = DIST_SEEDS[:24]                     # Varianten-Matrix
SIZE_SEEDS = DIST_SEEDS[:6]
SIZES = ((5, 5, 16), (12, 12, 50), (20, 20, 80))     # Werke, Verteilzentren, Filialen
HIGHS_LIMIT = 20.0
COLORS = {"open": "#1f77b4", "closed": "rgba(150,150,150,0.45)", "slope": "#ff7f0e", "opt": "#d62728", "node": "#111111", "best": "#2ca02c", "cost": "#1f77b4"}

# --- Presets -----------------------------------------------------------------------------------------------------------------
_BASE = dict(net="random", k=DEFAULT_K, p=DEFAULT_P, d=DEFAULT_D, s=DEFAULT_S, density=DEFAULT_DENSITY, spread=DEFAULT_SPREAD, load=DEFAULT_LOAD, fix=DEFAULT_FIX, seed=DEFAULT_SEED,
             gw=DEFAULT_GW, gh=DEFAULT_GH, gdensity=DEFAULT_GDENSITY, gcap=DEFAULT_GCAP, gdem=DEFAULT_GDEM, gseed=DEFAULT_GSEED,
             start=DEFAULT_START, memory=DEFAULT_MEMORY, perturb=DEFAULT_PERTURB, polish=DEFAULT_POLISH, damping=DEFAULT_DAMPING, iters=DEFAULT_ITER, control=DEFAULT_CONTROL)
PRESETS = {
    "🚚 Zufallsnetz": {**_BASE},
    "🗺️ Streckennetz": {**_BASE, "net": "grid", "k": 3, "fix": 10},
    "💸 Big-M-Falle": {**_BASE, "net": "bigm", "k": 1},
    "🔁 Rundungs-Falle": {**_BASE, "net": "rounding", "k": 1},
    "📦 Bündelung (Zyklus)": {**_BASE, "net": "bundle", "k": 2, "perturb": "off", "damping": 0.0},
    "🧱 Reines Slope Scaling": {**_BASE, "perturb": "off", "polish": "off", "damping": 0.0},
    "🚫 Nur ein LP": {**_BASE, "control": "once"},
    "⏮️ Letzte statt beste": {**_BASE, "seed": 38, "control": "last", "perturb": "off", "polish": "off", "damping": 0.0},
}
PRESET_HELP = {
    "🚚 Zufallsnetz": "Das Netz der Vorgänger (Seed 155, drei Güter, Fixkosten 30) mit den Standardoptionen (Dämpfung 0,5, Störung, Politur): 19 Iterationen bis zum Fixpunkt; die beste (Iteration 9) kostet 1 797, 0,7 % über dem Optimum 1 784. Die letzte Iteration liegt 4,5 % darüber, das erste LP 6,8 %, das Aufrunden aus Stück 10 2,4 %.",
    "🗺️ Streckennetz": "Gitter 4 × 3 mit drei Gütern (Seed 6, Fixkosten 10): das erste LP trifft das Optimum 245 schon, danach folgen 8 Iterationen bis zum Fixpunkt. Das Aufrunden aus dem Vorgängerstück liegt hier 12 % darüber.",
    "💸 Big-M-Falle": "Eine Einheit, zwei Wege: das erste LP (Steigung = Kapazität) wählt die breite Kante (Kosten 31), erst das Anpassen der Steigung an den tatsächlichen Fluss 1 macht sie teuer und die schmale billiger: Optimum 15, gefunden in Iteration 5.",
    "🔁 Rundungs-Falle": "Drei Einheiten über zwei gleiche Kanten (Kapazität 2): schon das erste LP liefert das Optimum 23 (beide Kanten offen), danach 8 Iterationen bis zum Fixpunkt. Die Rundungs-Lücke der Schranke aus Stück 10 gibt es hier nicht - Slope Scaling rechnet ohne Schranke.",
    "📦 Bündelung (Zyklus)": "Ohne Dämpfung und ohne Störung: das Optimum 11 steht im ersten LP, nach 3 Iterationen stoppt das Verfahren mit einem Zyklus - ein früherer Entwurf kehrt wieder. Gemerkt wird die beste Lösung, deshalb schadet der Zyklus hier nicht.",
    "🧱 Reines Slope Scaling": "Ohne Dämpfung, Störung und Politur (Seed 155): 5 Iterationen bis zum Fixpunkt, Kosten 1 870, 4,8 % über dem Optimum. Mit Dämpfung und Störung sind es 0,7 %.",
    "🚫 Nur ein LP": "Negativkontrolle: die Steigung bleibt der Startwert (Kapazität), es gibt nur das erste LP: 1 906, 6,8 % über dem Optimum; die Politur holt davon auf 3,4 %. Erst das Anpassen der Steigung an den Fluss macht aus der Schätzung eine Lösung.",
    "⏮️ Letzte statt beste": "Negativkontrolle auf einem Netz mit Seed 38 (Optimum 1 549), reines Verfahren: das erste LP trifft mit 1 554 fast das Optimum (0,3 %), danach wird es schlechter - nach 9 Iterationen liegt der Fixpunkt bei 1 909, 23 % darüber. Zählt die letzte Iteration, geht die beste verloren.",
}
