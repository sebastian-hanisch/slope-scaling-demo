"""Orakel-Regressionstest: Slope Scaling gegen ein unabhängig aufgebautes Kanten-LP (scipy linprog) und ein MILP (OR-Tools SCIP).

Das Orakel baut Flusserhaltung, Kapazitäten und Kosten selbst aus den Kanten des Netzes (nicht aus `ss_formulation`). Je Netz und Option: Zielwert und Zulässigkeit jedes Steigungs-LP,
wahre Kosten, Steigungsupdate (Dämpfung, Gedächtnis, Störung), Stoppgrund, beste Iteration, Politur und das MIP-Optimum gegen den Brute-Force-Löser. Dazu der Gültigkeitsbereich
der Aussage "im Fixpunkt liegt der LP-Zielwert auf den wahren Kosten" (nur ohne Dämpfung)."""

import re
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("scipy")
pywraplp = pytest.importorskip("ortools.linear_solver.pywraplp")
from scipy.optimize import linprog  # noqa: E402

import ss_formulation as fm  # noqa: E402
import ss_model as md  # noqa: E402
import ss_slope as sl  # noqa: E402

APP = Path(__file__).resolve().parent.parent / "app.py"
BIG = md.BIG


def _cost(design, k, e):
    u, v, cap, c, kind = design.net.arcs[e]
    if v == design.net.t:
        return 0.0
    return design.mcf.factors[k] * c if kind in (1, 3) else float(c)          # Lane Werk -> DC bzw. DC -> Filiale: Gutfaktor


def _lp(design, y_fixed=None, slope=None):
    """Kanten-LP ohne Entscheidungsvariablen: mit `slope` Kosten + f/s (alle Gruppen offen), mit `y_fixed` fester Entwurf. None, wenn unzulässig."""
    K, m, G, net = design.K, design.m, design.G, design.net
    c = np.zeros(K * m)
    for k in range(K):
        for e in range(m):
            c[k * m + e] = _cost(design, k, e)
            g = design.group[e]
            if slope is not None and g >= 0:
                c[k * m + e] += design.fixed[g] / slope[g]
    a_eq, a_ub, b_ub = [], [], []
    for k in range(K):
        for v in range(net.n):
            if v in (net.s, net.t):
                continue
            row = np.zeros(K * m)
            for e, arc in enumerate(net.arcs):
                row[k * m + e] += (arc[1] == v) - (arc[0] == v)
            a_eq.append(row)
    for e, arc in enumerate(net.arcs):
        if arc[1] == net.t:
            continue
        g = design.group[e]
        row = np.zeros(K * m)
        row[[k * m + e for k in range(K)]] = 1
        a_ub.append(row)
        b_ub.append(0.0 if (y_fixed is not None and g >= 0 and g not in y_fixed) else float(arc[2]))
    bounds = []
    for k in range(K):
        for e in range(m):
            hi = None if design.mcf.ub[k][e] >= BIG else design.mcf.ub[k][e]
            bounds.append((hi if net.arcs[e][1] == net.t else 0.0, hi))
    res = linprog(c, A_ub=np.array(a_ub), b_ub=b_ub, A_eq=np.array(a_eq), b_eq=np.zeros(len(a_eq)), bounds=bounds, method="highs")
    if res.status == 2:
        return None
    assert res.status == 0
    fixed = sum(design.fixed[g] for g in y_fixed) if y_fixed is not None else 0.0
    return res.fun + fixed, res.x.reshape(K, m)


def _mip(design):
    """Optimum per MILP in SCIP: y_g binär, sum_k x <= u · y_g."""
    K, m, G, net = design.K, design.m, design.G, design.net
    s = pywraplp.Solver.CreateSolver("SCIP")
    x = [[s.NumVar(0, s.infinity() if design.mcf.ub[k][e] >= BIG else design.mcf.ub[k][e], "") for e in range(m)] for k in range(K)]
    for k in range(K):
        for e, arc in enumerate(net.arcs):
            if arc[1] == net.t:
                s.Add(x[k][e] == design.mcf.ub[k][e])
    y = [s.BoolVar("") for _ in range(G)]
    for k in range(K):
        for v in range(net.n):
            if v not in (net.s, net.t):
                s.Add(sum(x[k][e] for e, a in enumerate(net.arcs) if a[1] == v) == sum(x[k][e] for e, a in enumerate(net.arcs) if a[0] == v))
    for e, arc in enumerate(net.arcs):
        if arc[1] != net.t:
            g = design.group[e]
            s.Add(sum(x[k][e] for k in range(K)) <= (arc[2] * y[g] if g >= 0 else arc[2]))
    s.Minimize(sum(_cost(design, k, e) * x[k][e] for k in range(K) for e in range(m)) + sum(design.fixed[g] * y[g] for g in range(G)))
    return s.Objective().Value() if s.Solve() == pywraplp.Solver.OPTIMAL else None


def _true_cost(design, x):
    gf = np.zeros(design.G)
    for e in range(design.m):
        if design.group[e] >= 0:
            gf[design.group[e]] += x[:, e].sum()
    used = frozenset(int(g) for g in np.nonzero(gf > 1e-6)[0])
    return sum(_cost(design, k, e) * x[k, e] for k in range(design.K) for e in range(design.m)) + sum(design.fixed[g] for g in used), used, gf


class _SplitMix:
    """SplitMix64 nach Vigna (Referenz), unabhängig von ss_scenario."""

    def __init__(self, seed):
        self.s = seed % 2 ** 64

    def below(self, n):
        self.s = (self.s + 0x9E3779B97F4A7C15) % 2 ** 64
        z = ((self.s ^ (self.s >> 30)) * 0xBF58476D1CE4E5B9) % 2 ** 64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) % 2 ** 64
        return (z ^ (z >> 31)) % n


def _designs(count=14):
    out = [md.bigm_net(), md.rounding_net(), md.bundle_net()]
    for seed in range(100000, 100400):
        d = md.generate_design(2, 2, 3, 60, 50, 50, seed, 2, 30) if seed % 2 else md.generate_design_grid(3, 2, 60, 3, 2, 2, seed, 10)
        if d.G <= 13 and _lp(d) is not None:
            out.append(d)
        if len(out) == count:
            return out
    raise AssertionError("zu wenige lieferbare Kleinstnetze")


DESIGNS = _designs()
OPTIONS = [dict(), dict(memory=True), dict(perturb=True), dict(damping=0.5, perturb=True), dict(start="demand", perturb=True), dict(adapt=False)]


def test_mip_optimum_equals_scip_and_brute_force():
    for d in DESIGNS:
        opt = _mip(d)
        assert fm.solve_mip(d).objective == pytest.approx(opt, abs=1e-6) == pytest.approx(fm.brute_force(d)[0].objective, abs=1e-6)
        assert fm.solve_lp(d, fm.WEAK).objective <= fm.solve_lp(d, fm.STRONG).objective + 1e-6 <= opt + 1e-5


@pytest.mark.parametrize("kw", OPTIONS)
def test_every_iteration_matches_an_independent_lp_and_the_update_rule(kw):
    for d in DESIGNS:
        opt = _mip(d)
        G, m = d.G, d.m
        r = sl.slope_scaling(d, max_iter=30, **kw)
        cap = np.array([sum(d.net.arcs[e][2] for e in range(m) if d.group[e] == g) for g in range(G)], float)
        if kw.get("start") == "demand":
            cap = np.minimum(cap, max(1.0, sum(d.mcf.demand(k) for k in range(d.K)) / 2))
        slope, rng = np.maximum(cap, 1.0), _SplitMix(1)
        hist, counts, seen, pert, event, stop = np.zeros(G), np.zeros(G), {}, 0, "start", None
        for it, f in enumerate(r.frames, 1):
            assert f.event == event and np.allclose(f.slope, slope)
            lp = _lp(d, slope=slope)
            assert f.linear_cost == pytest.approx(lp[0], rel=1e-6)
            assert sum((_cost(d, k, e) + (d.fixed[d.group[e]] / slope[d.group[e]] if d.group[e] >= 0 else 0)) * f.x[k, e] for k in range(d.K) for e in range(m)) == pytest.approx(lp[0], rel=1e-6)
            tc, used, gf = _true_cost(d, f.x)
            assert f.true_cost == pytest.approx(tc, abs=1e-6) and f.design == used and tc >= opt - 1e-6
            if kw.get("adapt") is False:
                stop = "fixed"
                break
            key = (used, tuple(np.round(gf, 6)))
            if key in seen:
                if kw.get("perturb") and pert < 3:
                    pert += 1
                    slope = np.maximum(slope * np.array([0.5 + rng.below(101) / 100.0 for _ in range(G)]), 1.0)
                    event = "perturb"
                    seen.clear()
                    stop = "limit" if it == 30 else None
                    continue
                stop = "fixed" if seen[key] == it - 1 else "cycle"
                break
            seen[key] = it
            pos = gf > 1e-6
            hist[pos] += gf[pos]
            counts[pos] += 1
            target = np.where(counts > 0, hist / np.maximum(counts, 1), slope) if kw.get("memory") else np.where(pos, gf, slope)
            new = kw.get("damping", 0.0) * slope + (1 - kw.get("damping", 0.0)) * target
            slope, event, stop = np.maximum(np.where(pos | bool(kw.get("memory")), new, slope), 1.0), "update", None
        assert r.stop == (stop or "limit") and len(r.frames) == it
        costs = [f.true_cost for f in r.frames]
        assert r.best_cost == pytest.approx(min(costs)) and r.best_iteration == 1 + next(i for i, c in enumerate(costs) if c < min(costs) + 1e-9)


@pytest.mark.parametrize("kw", [dict(), dict(damping=0.5, perturb=True)])
def test_polish_equals_independent_greedy_closing(kw):
    for d in DESIGNS:
        r = sl.slope_scaling(d, **kw)
        opened = set(r.best_design)
        cost = _lp(d, y_fixed=opened)[0]
        improved = True
        while improved:
            improved = False
            for g in sorted(opened, key=lambda g: -d.fixed[g]):
                t = _lp(d, y_fixed=opened - {g})
                if t is not None and t[0] < cost - 1e-9:
                    opened, cost, improved = opened - {g}, t[0], True
                    break
        assert r.polished_cost == pytest.approx(min(cost, r.best_cost), abs=1e-6) and r.polished_cost >= _mip(d) - 1e-6


def test_fixed_point_hits_the_true_cost_only_without_damping():
    """Ohne Dämpfung ist die Steigung im Fixpunkt der Fluss (LP-Zielwert = wahre Kosten); mit Dämpfung stoppt das Verfahren schon, wenn sich der Fluss wiederholt, die Steigung liegt dann noch daneben.
    Der Text der Demo nennt deshalb die Voraussetzung."""
    for d in DESIGNS:
        r = sl.slope_scaling(d)
        if r.stop == "fixed" and r.iterations > 1:
            assert r.frames[-1].linear_cost == pytest.approx(r.frames[-1].true_cost, abs=1e-5)
    d = md.generate_design(3, 3, 8, 60, 50, 50, 155, 3, 30)
    r = sl.slope_scaling(d, damping=0.5, perturb=True)
    last = r.frames[-1]
    flow = sl.Problem(d).group_flow(last.x)
    assert r.stop == "fixed" and np.abs(last.slope[flow > 1e-6] - flow[flow > 1e-6]).max() > 0.1 and abs(last.linear_cost - last.true_cost) > 1.0
    text = APP.read_text(encoding="utf-8")
    assert re.search(r"ohne Dämpfung liegt er im Fixpunkt genau auf ihnen", text)
