"""Rauchtests der Streamlit-Oberfläche per AppTest: Standard, jedes Preset, alle Optionen, Randgrößen, Iterations-Regler, ausgeblendete Regler, Permalink, Experimente auf Abruf, Schlüssel und Achsensperre."""

import itertools
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import ss_constants as C
import ss_evaluation as ev
from ss_presets import PRESET_KEYS

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app.py"

EXPECTED = {
    "🚚 Zufallsnetz": "Kosten 1797,0, **0,7 % über dem Optimum**",
    "🗺️ Streckennetz": "Das Optimum getroffen: 245,0 nach ",
    "💸 Big-M-Falle": "Das Optimum getroffen: 15,0 nach ",
    "🔁 Rundungs-Falle": "Das Optimum getroffen: 23,0 nach ",
    "📦 Bündelung (Zyklus)": "Das Optimum getroffen: 11,0 nach 3 Iterationen (Zyklus",
    "🧱 Reines Slope Scaling": "Kosten 1870,0, **4,8 % über dem Optimum**",
    "🚫 Nur ein LP": "Nur ein LP (die Steigung bleibt der Startwert)",
    "⏮️ Letzte statt beste": "Kosten 1909,0, **23,2 % über dem Optimum**",
}
OPTION_LABELS = {"Startsteigung", "Dämpfung", "Gedächtnis", "Störung", "Politur", "Iterationsgrenze", "Kontrolle"}


def _run(setup=None, timeout=900):
    at = AppTest.from_file(str(APP), default_timeout=timeout)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    if setup is not None:
        setup(at)
        at.run()
        assert not at.exception, [e.value for e in at.exception]
    return at


def _apply(at, p):
    for key, state_key in PRESET_KEYS.items():
        at.session_state[state_key] = p[key]


def _labels(at):
    return {w.label for w in list(at.sidebar.slider) + list(at.sidebar.selectbox) + list(at.sidebar.number_input) + list(at.sidebar.radio)}


def _texts(at):
    return [e.value for e in list(at.success) + list(at.warning) + list(at.info) + list(at.error)]


def _has(at, prefix):
    return any(t.startswith(prefix) for t in _texts(at))


def _metric(at, label):
    return [m.value for m in at.metric if m.label == label]


def _frame_slider(at):
    found = [s for s in at.slider if s.key == "ss_frame"]
    return found[0] if found else None


def test_default_renders_without_exception():
    at = _run()
    assert any("Iteration für Iteration" in m.value for m in at.markdown)
    assert _has(at, EXPECTED["🚚 Zufallsnetz"]) and not at.error
    assert _metric(at, "Optimum (HiGHS)")[0] == "1784,0" and _metric(at, "Beste Iteration")[0] == "1797,0" and _metric(at, "Lücke (Mittel)")[0].endswith("%")
    assert _frame_slider(at).value == _frame_slider(at).max >= 10


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_every_preset_renders_with_its_verdicts(name):
    at = _run(lambda a: _apply(a, C.PRESETS[name]))
    assert _has(at, EXPECTED[name]), _texts(at)
    if C.PRESETS[name]["net"] in C.FIXED_NETS:
        assert any(t.startswith("Festes Netz") for t in _texts(at))


@pytest.mark.parametrize("K", range(C.K_MIN, C.K_MAX + 1))
@pytest.mark.parametrize("net", ["random", "grid"])
def test_every_number_of_goods_renders(net, K):
    def setup(at):
        at.session_state["net_select"] = net
        at.session_state["k_slider"] = K
    at = _run(setup)
    assert not at.error and (_has(at, "Kosten") or _has(at, "Das Optimum") or _has(at, "Dieses Netz kann"))


@pytest.mark.parametrize("start,memory,perturb,polish,damping", list(itertools.product(C.STARTS, C.ONOFF, C.ONOFF, C.ONOFF, C.DAMPINGS)))
def test_every_option_combination_renders(start, memory, perturb, polish, damping):
    def setup(at):
        at.session_state["start_radio"] = start
        at.session_state["memory_radio"] = memory
        at.session_state["perturb_radio"] = perturb
        at.session_state["polish_radio"] = polish
        at.session_state["damping_radio"] = damping
    at = _run(setup)
    assert (_has(at, "Kosten") or _has(at, "Das Optimum")) and not at.error


@pytest.mark.parametrize("control", list(C.CONTROLS))
@pytest.mark.parametrize("iters", C.ITERS)
def test_every_control_and_iteration_limit_renders(control, iters):
    at = _run(lambda a: (a.session_state.__setitem__("control_radio", control), a.session_state.__setitem__("iter_radio", iters)))
    assert not at.exception and len(_texts(at)) >= 1


def test_extreme_sizes_render():
    for net, vals in (("random", (("p_slider", C.P_MIN), ("d_slider", C.D_MIN), ("s_slider", C.S_MIN), ("density_slider", C.DENSITY_MIN), ("spread_slider", C.SPREAD_MIN), ("load_slider", C.LOAD_MIN), ("k_slider", C.K_MIN), ("fix_slider", C.FIX_MIN))),
                      ("random", (("p_slider", C.P_MAX), ("d_slider", C.D_MAX), ("s_slider", C.S_MAX), ("density_slider", C.DENSITY_MAX), ("spread_slider", C.SPREAD_MAX), ("load_slider", C.LOAD_MAX), ("k_slider", C.K_MAX), ("fix_slider", C.FIX_MAX))),
                      ("grid", (("gw_slider", C.GW_MIN), ("gh_slider", C.GH_MIN), ("gdensity_slider", C.GDENSITY_MIN), ("gcap_slider", C.GCAP_MIN), ("gdem_slider", C.GDEM_MIN), ("k_slider", C.K_MIN))),
                      ("grid", (("gw_slider", C.GW_MAX), ("gh_slider", C.GH_MAX), ("gdensity_slider", C.GDENSITY_MAX), ("gcap_slider", C.GCAP_MAX), ("gdem_slider", C.GDEM_MAX), ("k_slider", C.K_MAX)))):
        def setup(at, net=net, vals=vals):
            at.session_state["net_select"] = net
            for key, value in vals:
                at.session_state[key] = value
        at = _run(setup)
        assert not at.error


def test_a_net_that_cannot_deliver_renders_and_says_so():
    """Seed 13 im Standardnetz: die Nachfrage lässt sich auch mit allen Kanten offen nicht decken - Hinweis, kein Absturz."""
    at = _run(lambda a: a.session_state.__setitem__("seed_input", 13))
    assert any("kann die Nachfrage nicht decken" in t for t in _texts(at))


def test_iteration_slider_moves_through_all_frames():
    at = _run(lambda a: _apply(a, C.PRESETS["📦 Bündelung (Zyklus)"]))
    top = int(_frame_slider(at).max)
    assert top == 3
    for value in range(1, top + 1):
        _frame_slider(at).set_value(value)
        at.run()
        assert not at.exception and _frame_slider(at).value == value


def test_a_single_iteration_has_no_slider():
    at = _run(lambda a: a.session_state.__setitem__("control_radio", "once"))
    assert _frame_slider(at) is None and any("Es gibt nur eine Iteration" in c.value for c in at.caption)


def test_hidden_controls_keep_their_values_across_a_net_switch():
    at = _run()
    at.sidebar.slider(key="fix_slider").set_value(80)
    at.run()
    at.sidebar.selectbox(key="net_select").set_value("bigm")
    at.run()
    assert not at.exception and not [w for w in at.sidebar.slider if w.key == "fix_slider"]
    at.sidebar.selectbox(key="net_select").set_value("random")
    at.run()
    assert at.sidebar.slider(key="fix_slider").value == 80 and not at.exception


def test_permalink_settings_are_loaded_and_clamped():
    at = AppTest.from_file(str(APP), default_timeout=900)
    at.query_params["net"] = "grid"
    at.query_params["k"] = "9"
    at.query_params["fix"] = "12"
    at.query_params["start"] = "demand"
    at.query_params["perturb"] = "off"
    at.query_params["damping"] = "0.0"
    at.query_params["iters"] = "10"
    at.run()
    assert not at.exception
    assert at.sidebar.selectbox(key="net_select").value == "grid" and at.sidebar.slider(key="k_slider").value == C.K_MAX and at.sidebar.slider(key="fix_slider").value == 10
    assert at.sidebar.radio(key="start_radio").value == "demand" and at.sidebar.radio(key="perturb_radio").value == "off" and at.sidebar.radio(key="damping_radio").value == 0.0 and at.sidebar.radio(key="iter_radio").value == 10


def test_option_controls_exist():
    assert OPTION_LABELS <= _labels(_run())


def test_experiments_run_on_demand(monkeypatch):
    v_orig, s_orig = ev.variant_table, ev.size_table
    monkeypatch.setattr(ev, "variant_table", lambda params: v_orig(params, seeds=C.VARIANT_SEEDS[:6]))
    monkeypatch.setattr(ev, "size_table", lambda params: s_orig(params, sizes=((2, 2, 4), (5, 5, 16)), seeds=C.SIZE_SEEDS, limit=5.0, per_size=1))
    at = _run()
    next(b for b in at.button if b.key == "variants_start").click().run()
    assert not at.exception and any("Keine Zutat ist ein Durchbruch" in c.value for c in at.caption)
    next(b for b in at.button if b.key == "controls_start").click().run()
    assert not at.exception and any("Ein einziges LP mit der Startsteigung" in c.value for c in at.caption)
    next(b for b in at.button if b.key == "sizes_start").click().run()
    assert not at.exception and any("Die Lücke ist gegen die beste Lösung" in c.value for c in at.caption)


def test_experiments_need_a_random_net():
    at = _run(lambda a: a.session_state.__setitem__("net_select", "bundle"))
    assert not [b for b in at.button if b.key in ("variants_start", "controls_start", "sizes_start")] and sum(1 for t in _texts(at) if t.startswith("Für dieses Experiment")) == 3


def test_source_has_explicit_chart_keys_and_locked_axes():
    app = APP.read_text(encoding="utf-8")
    assert all(re.search(r"plotly_chart\(.*key=", line) for line in app.splitlines() if "st.plotly_chart(" in line)
    viz = (ROOT / "ss_visualization.py").read_text(encoding="utf-8")
    assert viz.count("return lock_axes(fig)") >= 5 and "def lock_axes" in viz
