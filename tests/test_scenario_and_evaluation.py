"""Auswertung: Netzbau, Urteil, Verteilung, Experiment-Tabellen, Anzeige-Helfer."""

import pytest

import ss_constants as C
import ss_evaluation as ev
import ss_model as md

P = ev.DEFAULT_PARAMS
GRID = P._replace(net="grid", k=3, fix=10)
PURE = ev.Opts("cap", "off", "off", "off", 0.0, 30, "normal")


def test_build_dispatches_on_the_net_and_ignores_the_random_settings_for_fixed_nets():
    assert ev.build(P) == md.generate_design(3, 3, 8, 60, 50, 50, 155, 3, 30)
    assert ev.build(GRID) == md.generate_design_grid(4, 3, 60, 4, 2, 3, 6, 10)
    assert ev.build(P._replace(net="bigm")) == md.bigm_net() and ev.build(P._replace(net="rounding")) == md.rounding_net() and ev.build(P._replace(net="bundle")) == md.bundle_net()
    assert ev.normalise(P._replace(net="rounding", k=5, seed=9, fix=77)) == ev.normalise(P._replace(net="rounding", fix=5))
    assert ev.normalise(P._replace(net="grid", p=6, seed=9)) == ev.normalise(P._replace(net="grid", p=2, seed=77))
    assert ev.normalise(P._replace(gw=6, gseed=9)) == ev.normalise(P._replace(gw=3, gseed=1))


def test_with_seed_changes_only_the_seed_of_the_shown_net():
    assert ev.with_seed(P, 5).seed == 5 and ev.with_seed(P, 5).gseed == P.gseed
    assert ev.with_seed(GRID, 5).gseed == 5 and ev.with_seed(GRID, 5).seed == P.seed


def test_verdict_codes_and_data():
    lvl, code, d = ev.verdict(ev.analyse(P))
    assert (lvl, code) == ("success", "ok") and d["opt"] == 1784.0 and d["best"] >= d["opt"] and d["polished"] <= d["best"] + 1e-9 and d["gap"] == pytest.approx(d["polished"] / d["opt"] - 1)
    assert d["iterations"] > 1 and d["first"] >= d["best"] and d["last"] >= d["best"] and d["upper"] >= d["opt"] and d["seconds"] > 0 and d["highs_seconds"] > 0
    assert ev.verdict(ev.analyse(P._replace(net="rounding")))[:2] == ("success", "exact")
    assert ev.verdict(ev.analyse(P._replace(seed=13)))[:2] == ("warning", "nothing")


def test_options_change_the_run():
    a, b = ev.analyse(P), ev.analyse(P, PURE)
    assert a.result.iterations != b.result.iterations and b.result.stop == "fixed"
    limit = ev.analyse(P, ev.Opts("cap", "off", "on", "on", 0.5, 10, "normal"))
    assert limit.result.iterations == 10 and limit.result.stop == "limit"
    once = ev.analyse(P, ev.Opts("cap", "off", "off", "off", 0.0, 30, "once")).result
    assert once.iterations == 1 and once.best_cost == once.frames[0].true_cost


def test_distribution_is_consistent_with_single_runs():
    seeds = tuple(range(100000, 100004))
    dist = ev.distribution(P, seeds=seeds)
    feasible = [s for s in seeds if ev.analyse(ev.with_seed(P, s)).feasible]
    assert dist["n_seeds"] == 4 and dist["n_feasible"] == len(feasible) and dist["n_infeasible"] == 4 - len(feasible)
    for i, seed in enumerate(feasible):
        d = ev.verdict(ev.analyse(ev.with_seed(P, seed)))[2]
        assert dist["cols"]["gap"][i] == pytest.approx(d["gap"]) and dist["cols"]["iterations"][i] == d["iterations"] and dist["cols"]["gap_first"][i] == pytest.approx(d["gap_first"])
    assert ev.distribution(GRID, seeds=seeds)["n_seeds"] == 4


def test_variant_and_control_tables_shape():
    t = ev.variant_table(P, seeds=C.VARIANT_SEEDS[:6])
    assert [r["name"] for r in t["rows"]] == [v[0] for v in ev.VARIANTS] and t["n"] >= 4 and all(0 <= r["exact"] <= r["n"] and r["gap"] >= -1e-9 for r in t["rows"])
    c = ev.control_table(P, seeds=C.VARIANT_SEEDS[:6])
    assert set(c) == {"normal", "once", "last"} and c["once"]["gap"] > c["normal"]["gap"]


def test_size_table_shape():
    rows = ev.size_table(P, sizes=((2, 2, 4), (5, 5, 16)), seeds=C.SIZE_SEEDS, limit=5.0, per_size=1)
    assert [r["size"] for r in rows] == [(2, 2, 4), (5, 5, 16)] and rows[0]["groups"] < rows[1]["groups"] and all(r["gap"] >= -1e-6 for r in rows)


def test_frame_words():
    a = ev.analyse(P._replace(net="bigm"), PURE)
    f = a.result.frames
    assert ev.frame_words(a.design, f[0], None).startswith("neu offen:")
    text = ev.frame_words(a.design, f[1], f[0])
    assert "neu offen:" in text and "geschlossen:" in text and "A → B" in text
    assert ev.frame_words(a.design, f[1], f[1]) == "derselbe Entwurf wie zuvor"
    assert ev.arc_name(a.design, 0) == "A → B" and ev.group_name(a.design, 1) == "A → B"
