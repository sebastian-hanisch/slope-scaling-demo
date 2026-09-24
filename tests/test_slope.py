"""Slope Scaling: Handrechnung auf den Lehrnetzen, jede Iteration zulässig, Kosten nie unter dem Optimum, beste gemerkt, Politur nie schlechter, Fixpunkt exakt linearisiert, Negativkontrollen."""

import itertools

import numpy as np
import pytest

import ss_formulation as fm
import ss_model as md
import ss_slope as sl


def tiny_nets(count=3, groups=(6, 11)):
    """Kleine lieferbare Distributionsnetze (wenige Entwurfsgruppen), damit das Aufzählen aller 2^G Entwürfe reicht."""
    out = []
    for seed in range(100000, 100200):
        d = md.generate_design(2, 2, 2, 60, 50, 40, seed, 2, 30)
        if groups[0] <= d.G <= groups[1]:
            try:
                fm.solve_lp(d, fm.WEAK)
            except fm.Infeasible:
                continue
            out.append(d)
            if len(out) == count:
                return out
    raise AssertionError("keine passenden Kleinstnetze")


TEACHING = (md.bigm_net(), md.rounding_net(), md.bundle_net())
NETS = list(TEACHING) + tiny_nets()
OPTIONS = [dict(), dict(memory=True), dict(perturb=True), dict(memory=True, perturb=True), dict(damping=0.5), dict(start="demand")]


def _feasible(design, x, tol=1e-6):
    net, K = design.net, design.K
    for k in range(K):
        for v in range(net.n):
            if v in (net.s, net.t):
                continue
            inflow = sum(x[k, e] for e in range(design.m) if net.arcs[e][1] == v)
            outflow = sum(x[k, e] for e in range(design.m) if net.arcs[e][0] == v)
            if abs(inflow - outflow) > tol:
                return False
        if abs(sum(x[k, e] for e in design.demand_arcs()) - design.mcf.demand(k)) > tol:
            return False
    return all(x[:, e].sum() <= design.cap(e) + tol for e in range(design.m) if design.group[e] >= 0 or design.mcf.joint[e])


def test_teaching_nets_by_hand():
    """Big-M-Falle: 3 Iterationen, Fixpunkt, Optimum 15 in Iteration 2. Rundungs-Falle: 2 Iterationen, Optimum 23 gleich in Iteration 1. Bündelung: Zyklus nach 3 Iterationen, das Optimum 11 steht schon in Iteration 1."""
    big = sl.slope_scaling(md.bigm_net())
    assert (big.iterations, big.stop, big.best_cost, big.best_iteration) == (3, "fixed", 15.0, 2)
    rnd = sl.slope_scaling(md.rounding_net())
    assert (rnd.iterations, rnd.stop, rnd.best_cost, rnd.best_iteration) == (2, "fixed", 23.0, 1)
    bun = sl.slope_scaling(md.bundle_net())
    assert (bun.iterations, bun.stop, bun.best_cost, bun.best_iteration) == (3, "cycle", 11.0, 1)


def test_the_first_lp_of_the_big_m_net_prefers_the_wide_edge():
    """Anfangssteigung = Kapazität: die breite Kante (10, Fixkosten 30) kostet 3 je Einheit + 1, die schmale (1, Fixkosten 12) 12 + 3: der erste Entwurf ist die (teure) breite Kante, erst das Anpassen der Steigung an den Fluss 1 macht sie 30 + 1 gegen 12 + 3."""
    r = sl.slope_scaling(md.bigm_net())
    assert r.frames[0].design == frozenset({0}) and r.frames[0].true_cost == pytest.approx(31.0) and r.frames[1].design == frozenset({1}) and r.frames[1].true_cost == pytest.approx(15.0)
    assert r.frames[0].linear_cost == pytest.approx(4.0)                # 1 Einheit · (1 + 30/10)


@pytest.mark.parametrize("kw", OPTIONS)
def test_every_iteration_is_feasible_and_never_below_the_optimum(kw):
    for d in NETS:
        opt = fm.brute_force(d)[0].objective
        r = sl.slope_scaling(d, **kw)
        for f in r.frames:
            assert _feasible(d, f.x) and f.true_cost >= opt - 1e-6
            assert f.best_cost <= f.true_cost + 1e-9 and f.design == frozenset(int(g) for g in np.nonzero(sl.Problem(d).group_flow(f.x) > sl.TOL)[0])
        assert r.best_cost == pytest.approx(min(f.true_cost for f in r.frames)) and r.best_cost >= opt - 1e-6
        assert r.frames[r.best_iteration - 1].true_cost == pytest.approx(r.best_cost)


@pytest.mark.parametrize("kw", OPTIONS)
def test_polish_is_never_worse_and_its_cost_is_real(kw):
    for d in NETS:
        opt = fm.brute_force(d)[0].objective
        r = sl.slope_scaling(d, **kw)
        assert opt - 1e-6 <= r.polished_cost <= r.best_cost + 1e-9
        s = fm.solve_fixed_design(d, set(r.polished_design))
        assert s is not None and s.flow_cost + sum(d.fixed[g] for g in r.polished_design) == pytest.approx(r.polished_cost, abs=1e-6)


def test_fixed_point_is_exactly_linearised():
    """Im Fixpunkt ist die Steigung gleich dem Fluss: der Zielwert des Steigungs-LP ist dann die wahren Kosten."""
    for d in NETS:
        r = sl.slope_scaling(d)
        if r.stop == "fixed" and r.iterations > 1:
            last = r.frames[-1]
            assert last.linear_cost == pytest.approx(last.true_cost, abs=1e-5)


def test_polish_closes_a_useless_group():
    d = md.bigm_net()
    cost, design = sl.polish(d, {0, 1})
    assert (cost, design) == (pytest.approx(15.0), frozenset({1}))


def test_result_is_deterministic_and_seed_dependent_only_with_perturbation():
    d = md.generate_design(3, 3, 8, 60, 50, 50, 155, 3, 30)
    a, b = sl.slope_scaling(d, perturb=True, seed=1), sl.slope_scaling(d, perturb=True, seed=1)
    assert a.best_cost == b.best_cost and [f.true_cost for f in a.frames] == [f.true_cost for f in b.frames]
    p1, p2 = sl.slope_scaling(d, seed=1), sl.slope_scaling(d, seed=2)
    assert [f.true_cost for f in p1.frames] == [f.true_cost for f in p2.frames]


def test_negative_controls():
    d = md.generate_design(3, 3, 8, 60, 50, 50, 155, 3, 30)
    plain = sl.slope_scaling(d)
    once = sl.slope_scaling(d, adapt=False)
    assert once.iterations == 1 and once.best_cost >= plain.best_cost - 1e-9
    last = sl.slope_scaling(d, keep_best=False)
    assert last.best_cost == pytest.approx(last.frames[-1].true_cost) and last.best_cost >= plain.best_cost - 1e-9


def test_slope_is_never_below_one_and_memory_averages():
    d = md.generate_design(3, 3, 8, 60, 50, 50, 155, 3, 30)
    r = sl.slope_scaling(d, memory=True, perturb=True)
    assert all(f.slope.min() >= 1.0 for f in r.frames) and all(f.event in ("start", "update", "perturb") for f in r.frames) and r.frames[0].event == "start"


def test_group_flow_and_true_cost():
    d = md.rounding_net()
    p = sl.Problem(d)
    x = np.zeros((1, d.m))
    x[0, 0], x[0, 1] = 2.0, 1.0
    x[0, d.demand_arcs()[0]] = 3.0
    assert list(p.group_flow(x)) == [2.0, 1.0] and p.true_cost(x)[0] == pytest.approx(3.0 + 20.0) and p.true_cost(x)[1] == frozenset({0, 1})
