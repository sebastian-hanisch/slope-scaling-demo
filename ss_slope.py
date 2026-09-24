"""Slope Scaling für das Fixkosten-Netzdesign: Fixkosten in Stückkosten umrechnen, LP lösen, Steigung anpassen, wiederholen.

Statt die Entscheidung y (offen/zu) zu suchen, wird jede Fixkostengruppe g mit einer **Steigung** s_g als Stückkosten auf ihren Fluss umgelegt:
    LP:  min  sum_{k,e} (c^k_e + f_g / s_g) x^k_e   u.d.N. Flusserhaltung je Gut, Kapazität sum_k x^k_e <= u_e, volle Nachfrage
Es gibt keine Entscheidungsvariablen und keine Ganzzahligkeit. Ist s_g die Menge, die später wirklich über die Gruppe fließt, dann kostet der Fluss genau die Fixkosten - die Linearisierung ist im Punkt s_g exakt.
Also wird s_g nach jedem LP durch den gerade gefundenen Fluss auf der Gruppe ersetzt (Kim/Pardalos 1999). Der Entwurf einer Lösung sind die Gruppen mit Fluss; seine **wahren Kosten** sind Fixkosten der genutzten Gruppen + Stückkosten.
Bausteine nach Crainic/Gendron/Hernu (2004): **Gedächtnis** (Steigung als Mittel über die Iterationen), **Störung** (bei einem Zyklus die Steigungen zufällig auslenken), dazu eine **Politur** (Entwurf festhalten, Fluss per LP neu wählen, Gruppen einzeln schließen, solange es billiger wird).
Es gibt keine Optimalitätsgarantie und keine Schranke; gemerkt wird die beste gefundene Lösung.
"""

from dataclasses import dataclass
from time import perf_counter

import numpy as np
from scipy.optimize import linprog

import ss_formulation as fm
from ss_scenario import SplitMix64

TOL = 1e-6
STARTS = ("cap", "demand")


@dataclass(frozen=True)
class Frame:
    iteration: int
    slope: np.ndarray          # Steigung je Gruppe, mit der dieses LP gerechnet wurde
    x: np.ndarray              # (K, m) Fluss
    design: frozenset          # genutzte Gruppen
    true_cost: float           # Fixkosten der genutzten Gruppen + Stückkosten
    linear_cost: float         # Zielwert des Steigungs-LP
    best_cost: float           # beste wahre Kosten bis hier
    improved: bool
    event: str                 # "start", "update", "perturb" oder "cycle" (Anlass für diese Steigung)


@dataclass(frozen=True)
class SlopeResult:
    frames: tuple
    best_cost: float
    best_design: frozenset
    best_x: np.ndarray
    best_iteration: int
    stop: str                  # "fixed" (Fixpunkt), "cycle", "limit"
    polished_cost: float
    polished_design: frozenset
    seconds: float
    lp_seconds: float

    @property
    def iterations(self):
        return len(self.frames)

    @property
    def last_cost(self):
        return self.frames[-1].true_cost


class Problem:
    """Netz mit Steigungs-LP: Matrizen einmal aufgebaut, je Iteration ändert sich nur der Kostenvektor."""

    def __init__(self, design):
        self.design = design
        c, a_eq, b_eq, a_ub, b_ub, lo, hi = fm._build(design, fm.WEAK)
        nx = design.K * design.m
        self.nx = nx
        self.c = c[:nx].copy()
        self.a_eq, self.b_eq = a_eq[:, :nx], b_eq
        a_y = a_ub[:, nx:].toarray()
        self.a_x = a_ub[:, :nx]
        self.b = np.asarray(b_ub, dtype=float) - a_y @ np.ones(design.G)        # alle Gruppen offen: Kapazität u_e
        self.lo, self.hi = lo[:nx].copy(), hi[:nx].copy()
        self.fixed = np.asarray(design.fixed, dtype=float)
        K, m = design.K, design.m
        self.group_of_col = np.array([design.group[e] for k in range(K) for e in range(m)])
        self.cap_of_group = np.array([sum(design.cap(e) for e in design.arcs_of(g)) for g in range(design.G)], dtype=float)
        self.bounds = list(zip(self.lo, np.where(np.isinf(self.hi), None, self.hi)))

    def group_flow(self, x):
        flat = np.asarray(x, dtype=float).ravel()
        out = np.zeros(self.design.G)
        mask = self.group_of_col >= 0
        np.add.at(out, self.group_of_col[mask], flat[mask])
        return out

    def true_cost(self, x):
        flow = self.group_flow(x)
        used = flow > TOL
        return float(self.c @ np.asarray(x, dtype=float).ravel() + self.fixed[used].sum()), frozenset(int(g) for g in np.nonzero(used)[0])

    def solve(self, slope):
        """Steigungs-LP: Stückkosten + f_g / s_g auf jeder Kante der Gruppe g."""
        add = np.zeros(self.nx)
        mask = self.group_of_col >= 0
        add[mask] = (self.fixed / slope)[self.group_of_col[mask]]
        res = linprog(self.c + add, A_ub=self.a_x, b_ub=self.b, A_eq=self.a_eq, b_eq=self.b_eq, bounds=self.bounds, method="highs")
        if res.status == 2:
            raise fm.Infeasible("keine Lieferung möglich")
        if res.status != 0:
            raise RuntimeError(res.message)
        return res.x.reshape(self.design.K, self.design.m), float(res.fun)


def start_slope(problem, start="cap"):
    """Anfangssteigung: die Kapazität der Gruppe (ausgelastet gedacht) oder höchstens die Gesamtnachfrage."""
    cap = problem.cap_of_group.copy()
    if start == "demand":
        cap = np.minimum(cap, max(1.0, problem.design.mcf.total_demand() / 2))
    return np.maximum(cap, 1.0)


def polish(design, opened):
    """Politur: Entwurf festhalten und den Fluss neu wählen, dann Gruppen einzeln schließen (teuerste Fixkosten zuerst), solange die Gesamtkosten sinken. Rückgabe (Kosten, Entwurf)."""
    opened = set(opened)
    sol = fm.solve_fixed_design(design, opened)
    if sol is None:
        return float("inf"), frozenset(opened)
    cost = sol.flow_cost + float(sum(design.fixed[g] for g in opened))
    improved = True
    while improved:
        improved = False
        for g in sorted(opened, key=lambda g: -design.fixed[g]):
            trial = opened - {g}
            s = fm.solve_fixed_design(design, trial)
            if s is None:
                continue
            c = s.flow_cost + float(sum(design.fixed[h] for h in trial))
            if c < cost - 1e-9:
                opened, cost, improved = trial, c, True
                break
    return cost, frozenset(opened)


def slope_scaling(design, start="cap", memory=False, perturb=False, damping=0.0, max_iter=30, seed=1, keep_best=True, adapt=True, problem=None, do_polish=True):
    """Die Schleife. `memory`: Steigung = Mittel der Flüsse über alle Iterationen mit Fluss; `perturb`: bei einem Zyklus die Steigungen mit festem Zufallsstrom auslenken (statt zu stoppen, höchstens 3 Störungen);
    `damping` in [0, 1): s_neu = damping · s_alt + (1 - damping) · Fluss; `adapt=False`: die Steigung bleibt der Anfangswert (ein einziges LP, Negativkontrolle);
    `keep_best=False`: das Ergebnis ist die LETZTE Iteration statt der besten (Negativkontrolle)."""
    problem = problem or Problem(design)
    rng = SplitMix64(seed)
    t0 = perf_counter()
    slope = start_slope(problem, start)
    history = np.zeros(problem.design.G)
    counts = np.zeros(problem.design.G)
    frames, seen = [], {}
    best = (float("inf"), frozenset(), None, 0)
    lp_seconds, stop, event, perturbations = 0.0, "limit", "start", 0
    for it in range(1, max_iter + 1):
        t = perf_counter()
        x, lin = problem.solve(slope)
        lp_seconds += perf_counter() - t
        cost, used = problem.true_cost(x)
        improved = cost < best[0] - 1e-9
        if improved:
            best = (cost, used, x.copy(), it)
        frames.append(Frame(it, slope.copy(), x, used, cost, lin, best[0], improved, event))
        flow = problem.group_flow(x)
        key = (used, tuple(np.round(flow, 6)))
        if not adapt:
            stop = "fixed"
            break
        if key in seen:
            if perturb and perturbations < 3:
                perturbations += 1
                factors = np.array([0.5 + rng.below(101) / 100.0 for _ in range(problem.design.G)])
                slope = np.maximum(slope * factors, 1.0)
                event = "perturb"
                seen.clear()
                continue
            stop = "fixed" if seen[key] == it - 1 else "cycle"
            break
        seen[key] = it
        pos = flow > TOL
        history[pos] += flow[pos]
        counts[pos] += 1
        target = np.where(counts > 0, history / np.maximum(counts, 1), slope) if memory else np.where(pos, flow, slope)
        new = damping * slope + (1 - damping) * target
        slope = np.maximum(np.where(pos | memory, new, slope), 1.0)
        event = "update"
    final_cost, final_design = (best[0], best[1]) if keep_best else (frames[-1].true_cost, frames[-1].design)
    p_cost, p_design = polish(design, final_design) if do_polish else (final_cost, final_design)
    return SlopeResult(tuple(frames), float(final_cost), final_design, best[2] if keep_best else frames[-1].x, best[3] if keep_best else len(frames), stop, float(min(p_cost, final_cost)) if do_polish else float(final_cost),
                       p_design if p_cost < final_cost else final_design, perf_counter() - t0, lp_seconds)
