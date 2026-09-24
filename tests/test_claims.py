"""Jede Zahl, die README und Hilfetexte nennen, ist hier belegt (Standardeinstellungen, feste Netze, Seeds ab 100000).
Slope Scaling ist deterministisch (fester Zufallsstrom für die Störung); das Optimum kommt aus HiGHS (MIP). Anteile, Lücken und Iterationen werden mit Bändern geprüft, Sekunden nur als grobes Verhältnis."""

import pytest

import ss_constants as C
import ss_evaluation as ev

P = ev.DEFAULT_PARAMS
GRID = P._replace(net="grid", k=3, fix=10)
PURE = ev.Opts("cap", "off", "off", "off", 0.0, 30, "normal")
PLAIN = ev.Opts("cap", "off", "off", "on", 0.0, 30, "normal")


def test_teaching_nets_by_hand():
    """Big-M-Falle: das erste LP wählt die breite Kante (Kosten 31), das Optimum 15 folgt (Standardoptionen: Iteration 5, ohne Dämpfung und Störung Iteration 2). Rundungs-Falle: das erste LP trifft 23, 8 Iterationen. Bündelung ohne Dämpfung und Störung: 11 im ersten LP, Zyklus nach 3 Iterationen."""
    big = ev.verdict(ev.analyse(P._replace(net="bigm")))[2]
    assert big["opt"] == 15.0 and big["polished"] == 15.0 and big["first"] == 31.0 and big["best_iteration"] == 5 and big["stop"] == "fixed"
    assert ev.verdict(ev.analyse(P._replace(net="bigm"), PLAIN))[2]["best_iteration"] == 2
    rnd = ev.verdict(ev.analyse(P._replace(net="rounding")))[2]
    assert rnd["opt"] == 23.0 and rnd["first"] == 23.0 and rnd["best_iteration"] == 1 and rnd["iterations"] == 8
    bun = ev.verdict(ev.analyse(P._replace(net="bundle"), PLAIN))[2]
    assert bun["opt"] == 11.0 and bun["polished"] == 11.0 and bun["first"] == 11.0 and bun["iterations"] == 3 and bun["stop"] == "cycle"


def test_seed_155_numbers():
    """Zufallsnetz Seed 155, Standardoptionen: 19 Iterationen, beste Lösung (Iteration 9) 1 797 = 0,7 % über dem Optimum 1 784; die letzte Iteration 4,5 % darüber, das erste LP 6,8 %, das Aufrunden aus Stück 10 2,4 %.
    Reines Slope Scaling: 5 Iterationen, 1 870 = 4,8 %. Nur ein LP: 1 906 = 6,8 %, mit Politur 3,4 %."""
    d = ev.verdict(ev.analyse(P))[2]
    assert d["opt"] == 1784.0 and d["groups"] == 27 and d["stop"] == "fixed" and 14 <= d["iterations"] <= 26 and 5 <= d["best_iteration"] <= 14
    assert 1785 <= d["polished"] <= 1815 and 0.0 <= d["gap"] <= 0.017 and d["gap_first"] == pytest.approx(0.068, abs=0.003) and d["gap_upper"] == pytest.approx(0.0235, abs=0.003) and 0.02 <= d["gap_last"] <= 0.08
    pure = ev.verdict(ev.analyse(P, PURE))[2]
    assert pure["iterations"] == 5 and pure["polished"] == pytest.approx(1870.0) and pure["gap"] == pytest.approx(0.048, abs=0.003)
    once = ev.verdict(ev.analyse(P, ev.Opts("cap", "off", "on", "on", 0.5, 30, "once")))[2]
    assert once["iterations"] == 1 and once["best"] == pytest.approx(1906.0) and once["gap_best"] == pytest.approx(0.068, abs=0.003) and 0.028 <= once["gap"] <= 0.04


def test_last_iteration_can_be_far_worse_than_the_best():
    """Seed 38 (Optimum 1 549), reines Verfahren: das erste LP trifft 1 554 (0,3 %), nach 9 Iterationen liegt der Fixpunkt bei 1 909 (23 % darüber); mit der letzten statt der besten Iteration bleiben nur diese 23 %."""
    best = ev.verdict(ev.analyse(P._replace(seed=38), PURE))[2]
    assert best["opt"] == 1549.0 and best["best"] == pytest.approx(1554.0) and best["best_iteration"] == 1 and best["iterations"] == 9 and best["last"] == pytest.approx(1909.0) and best["gap_last"] == pytest.approx(0.232, abs=0.005)
    last = ev.verdict(ev.analyse(P._replace(seed=38), ev.Opts("cap", "off", "off", "off", 0.0, 30, "last")))[2]
    assert last["polished"] == pytest.approx(1909.0) and last["gap"] == pytest.approx(0.232, abs=0.005)


def test_grid_preset():
    """Streckennetz (4 x 3, Seed 6, Fixkosten 10): das erste LP trifft das Optimum 245, 8 Iterationen; das Aufrunden aus Stück 10 liegt 12 % darüber."""
    d = ev.verdict(ev.analyse(GRID))[2]
    assert d["opt"] == 245.0 and d["polished"] == 245.0 and d["first"] == 245.0 and 6 <= d["iterations"] <= 11 and d["gap_upper"] == pytest.approx(0.122, abs=0.005)


@pytest.fixture(scope="module")
def dist():
    return ev.distribution(P)


def test_distribution_default_net(dist):
    """34 lieferbare Distributionsnetze (40 feste, Standardoptionen): Lücke im Mittel 0,7 % (Median 0,1 %, schlechtestes Netz 6,7 %), in 65 % das Optimum getroffen (Lücke unter 0,5 %); das erste LP allein 7,6 %, die beste Iteration 1,1 %,
    die letzte 3,2 % - die letzte ist in 62 % der Netze schlechter als die beste; Aufrunden (Stück 10) 5,1 %, Slope Scaling ist in 29 von 34 Netzen billiger; im Mittel 14,7 Iterationen, 33 mal Fixpunkt, 1 mal Zyklus."""
    assert dist["n_seeds"] == 40 and 33 <= dist["n_feasible"] <= 35
    assert 0.004 <= dist["gap_mean"] <= 0.012 and dist["gap_median"] <= 0.005 and 0.04 <= dist["gap_max"] <= 0.10 and 0.55 <= dist["exact_share"] <= 0.75
    assert 0.065 <= dist["gap_first_mean"] <= 0.09 and 0.006 <= dist["gap_best_mean"] <= 0.016 and 0.02 <= dist["gap_last_mean"] <= 0.045 and 0.5 <= dist["last_worse_share"] <= 0.72
    assert 0.045 <= dist["gap_upper_mean"] <= 0.058 and 26 <= dist["better_than_upper"] <= 32 and 12 <= dist["iterations_mean"] <= 18 and dist["stops"]["limit"] == 0 and dist["stops"]["fixed"] >= 30 and dist["stops"]["cycle"] <= 4


def test_slope_scaling_is_not_faster_on_small_nets(dist):
    """Auf Netzen dieser Größe (27 Entwurfskanten) ist HiGHS schneller als Slope Scaling (etwa 0,02 gegen 0,05 Sekunden)."""
    assert dist["seconds_mean"] > dist["highs_mean"]


def test_grid_distribution():
    """30 lieferbare Streckennetze (Gitter 4 x 3, drei Güter, Fixkosten 10): Lücke im Mittel 1,6 % (Median 0), in 80 % das Optimum; das Aufrunden liegt hier bei 2,5 %, das erste LP bei 5,9 %."""
    g = ev.distribution(GRID)
    assert 28 <= g["n_feasible"] <= 32 and 0.008 <= g["gap_mean"] <= 0.026 and g["gap_median"] <= 0.005 and 0.72 <= g["exact_share"] <= 0.88 and 0.015 <= g["gap_upper_mean"] <= 0.035 and 0.04 <= g["gap_first_mean"] <= 0.08


def test_variant_matrix():
    """21 lieferbare Netze, Lücke im Mittel: reines Slope Scaling 2,25 %, mit Politur 1,8 %, Gedächtnis 1,55 %, Störung 1,4 %, Dämpfung 0,5 allein 1,7 % (aber 9 Zyklen), Startsteigung Nachfrage 1,15 %, Dämpfung + Störung 0,74 % (Optimum in 15 von 21)."""
    t = ev.variant_table(P)
    by = {r["name"]: r for r in t["rows"]}
    assert t["n"] == 21
    pure, polish, memory, perturb, damp, demand, both = (by[n] for n in ("Reines Slope Scaling", "+ Politur", "+ Gedächtnis", "+ Störung", "+ Dämpfung 0,5", "Startsteigung Nachfrage", "Dämpfung + Störung (Standard)"))
    assert 0.015 <= pure["gap"] <= 0.03 and polish["gap"] <= pure["gap"] + 1e-9 and 0.010 <= memory["gap"] <= 0.022 and 0.009 <= perturb["gap"] <= 0.02 and 0.010 <= damp["gap"] <= 0.024
    assert 0.006 <= demand["gap"] <= 0.017 and 0.004 <= both["gap"] <= 0.011 and both["gap"] < pure["gap"] / 2 and 13 <= both["exact"] <= 18 and both["gap_max"] <= 0.10
    assert damp["cycle"] >= 6 and both["cycle"] <= 2 and 2 <= pure["cycle"] <= 5 and perturb["cycle"] <= 2 and perturb["cycle"] <= pure["cycle"] and 3 <= pure["iterations"] <= 8 and 12 <= both["iterations"] <= 19


def test_negative_controls():
    """Nur ein LP: Lücke im Mittel 7,6 % (Optimum in 2 von 21 Netzen), letzte statt beste Iteration 3,0 % gegen 2,25 % (jeweils ohne Politur und Störung)."""
    c = ev.control_table(P)
    assert c["normal"]["n"] == 21 and 0.015 <= c["normal"]["gap"] <= 0.03 and 0.06 <= c["once"]["gap"] <= 0.09 and 1 <= c["once"]["exact"] <= 4 and 0.02 <= c["last"]["gap"] <= 0.04 and c["last"]["gap"] > c["normal"]["gap"]


def test_sizes():
    """Netze mit 68 / 464 / 1 200 Entwurfskanten (je zwei feste, HiGHS mit Zeitlimit 20 s): Lücke 7 / 10 / 14 % (gegen die beste HiGHS-Lösung), Slope Scaling 0,1 / 1,5 / 2,9 Sekunden gegen HiGHS 0,3 / 3,5 / 18: der Zeitgewinn wächst, die Lücke auch."""
    rows = ev.size_table(P)
    small, mid, big = rows
    assert [round(r["groups"]) for r in rows] == pytest.approx([68, 464, 1200], abs=45) or (60 <= small["groups"] <= 80 and 400 <= mid["groups"] <= 520 and 1000 <= big["groups"] <= 1400)
    assert small["gap"] < mid["gap"] + 0.03 and 0.04 <= small["gap"] <= 0.11 and 0.05 <= mid["gap"] <= 0.15 and 0.08 <= big["gap"] <= 0.20 and big["gap"] > small["gap"]
    assert big["highs"] > 3 * big["seconds"] and mid["highs"] > mid["seconds"]
