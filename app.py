"""Slope Scaling – Fixkosten linearisieren, LP lösen, Steigung anpassen – interaktive Konzept-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Anders als die Fall-Demos im Portfolio (ein Anwendungsfall, mehrere Verfahren im Vergleich) zeigt diese Demo EIN Verfahren - die Matheuristik Slope Scaling für das Fixkosten-Netzdesign - und lässt stattdessen das Beispiel wachsen.
Zwölftes Stück der Hauptlinie der Netzwerkfluss-Linie der "Konzepte"-Reihe, drittes im Netzwerkdesign-Ast: dasselbe Modell wie die beiden Vorgänger, aber ohne Schranke und ohne Beweis - schnell und ungefähr. Siehe README.

Lauffähig mit: streamlit run app.py
"""

import time

import streamlit as st

import ss_constants as C
import ss_evaluation as ev
from ss_presets import (
    KEPT,
    apply_preset,
    bounds,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_seed,
    seed_widget,
    sync_query_params,
)
from ss_visualization import (
    build_costs,
    build_dist,
    build_sizes,
    build_slope_map,
    build_variants,
)

st.set_page_config(page_title="Slope Scaling – Sebastian Hanisch", layout="wide")


def _pct(x, digits=1):
    return "–" if x is None or x != x else f"{100 * x:.{digits}f} %".replace(".", ",")


def _f(x, digits=1):
    return "–" if x is None or x != x else f"{x:.{digits}f}".replace(".", ",")


def _n(x):
    return f"{int(round(x)):,}".replace(",", " ")


def _sec(x):
    return f"{x:.2f}".replace(".", ",") if x >= 0.1 else f"{x:.3f}".replace(".", ",")


@st.cache_resource(show_spinner=False, max_entries=48)
def _analysis(params, opts):
    return ev.analyse(params, opts)


@st.cache_resource(show_spinner=False, max_entries=8)
def _distribution(params, opts):
    return ev.distribution(params, opts)


st.title("📈 Slope Scaling – Fixkosten linearisieren")
st.markdown(
    """
Die beiden Vorgänger sind **exakt**: das Fixkosten-Netzdesign wird mit Schranke und Schnitten bzw. mit Benders-Zerlegung bis zum bewiesenen Optimum gelöst. **Slope Scaling** verzichtet auf jeden Beweis und tauscht ihn gegen Geschwindigkeit: die Fixkosten $f_g$ einer Kante werden als **Stückkosten** auf ihren Fluss umgelegt,
$c^k_e+f_g/s_g$, wobei die **Steigung** $s_g$ die Menge ist, die man über die Kante erwartet. Das ist ein gewöhnliches LP ohne Entscheidungsvariablen. Ist die Erwartung richtig, kostet der Fluss genau die Fixkosten; also wird die Steigung nach jedem LP durch den gerade gefundenen Fluss ersetzt und das LP erneut gelöst - bis sich nichts mehr ändert.
Das sind oft nur ein Dutzend LPs. Kanten ohne Fluss werden **nie** bezahlt: der Entwurf ergibt sich von selbst. Diese Demo lässt die Iterationen einzeln durchlaufen, zeigt, wo das Verfahren zyklt oder sich verschlechtert, und misst gegen das exakte Optimum - und ab welcher Größe es sich lohnt.
"""
)
st.caption(
    "Anders als die Fall-Demos im Portfolio, die an einem Anwendungsfall mehrere Verfahren vergleichen, zeigt diese Demo - zwölftes Stück der Hauptlinie der Netzwerkfluss-Linie der \"Konzepte\"-Reihe, drittes im Netzwerkdesign-Ast - **ein** Verfahren an einem wachsenden Beispiel. "
    "Die Vorgänger: [fixkosten-netzdesign-demo](https://github.com/sebastian-hanisch/fixkosten-netzdesign-demo) (Schranke und Schnitte) und [benders-demo](https://github.com/sebastian-hanisch/benders-demo) (Zerlegung); hier kommt das Verfahren ohne Beweis. "
    "MIP-basierte Nachbarschaftssuchen (Local Branching, RINS) sind bewusst nicht Teil: sie gehören zur LNS-Linie (alns-demo)."
)

with st.expander("So funktioniert Slope Scaling", expanded=True):
    st.markdown(
        r"""
1. **Steigungs-LP:** $\min\sum_{k,e}\big(c^k_e+f_{g(e)}/s_{g(e)}\big)x^k_e$ mit Flusserhaltung je Gut, Kapazität $\sum_k x^k_e\le u_e$ und voller Nachfrage - ein LP, ohne $y$.
2. **Anpassen:** nach dem LP ist $F_g$ der Fluss auf der Gruppe $g$. Ist $F_g>0$, wird $s_g\leftarrow F_g$ (bei Fluss 0 bleibt die Steigung stehen). Im Punkt $s_g=F_g$ ist die Linearisierung exakt: der Fluss zahlt genau $f_g$.
3. **Entwurf und wahre Kosten:** der Entwurf sind die Gruppen mit Fluss; die wahren Kosten sind ihre Fixkosten plus die Stückkosten. **Beste merken:** die Kosten schwanken von Iteration zu Iteration, die letzte ist nicht die beste.
4. **Start:** die Anfangssteigung ist die Kapazität (jede Kante wird als ausgelastet gedacht: Fixkosten sehen billig aus) oder die halbe Gesamtnachfrage (höchstens die Kapazität).
5. **Bausteine (Crainic/Gendron/Hernu 2004):** **Dämpfung** (die Steigung wandert nur halb zum Fluss), **Gedächtnis** (Mittel der Flüsse über alle Iterationen), **Störung** (bei einem Zyklus die Steigungen zufällig auslenken, mit festem Zufallsstrom), **Politur** (Entwurf festhalten, Fluss neu wählen, Kanten einzeln schließen, solange es billiger wird).
6. **Keine Garantie:** es gibt keine Schranke; das exakte Optimum (HiGHS) dient nur der Bewertung.
        """
    )

st.caption("🎯 Schnellstart – ein Beispielnetz laden:")
names = list(C.PRESETS.keys())
for row in range(0, len(names), 4):
    preset_cols = st.columns(4)
    for col, name in zip(preset_cols, names[row:row + 4]):
        with col:
            st.button(name, width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP[name])

st.caption(
    "🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, "
    "um ein Szenario zu teilen."
)

load_permalink_settings()
init_session_state_defaults()


def _kept(key, default):
    return int(st.session_state.get(KEPT[key], default))


def _slider(label, key, help, step=None):
    kw = {"step": step} if step else {}
    seed_widget(key)
    value = st.slider(label, *bounds(key), key=key, help=help, **kw)
    st.session_state[KEPT[key]] = value
    return value


with st.sidebar:
    st.header("⚙️ Einstellungen")
    net_key = st.selectbox(
        "Netz", list(C.NETS), key="net_select", format_func=lambda k: C.NETS[k],
        help="Das Distributionsnetz der Vorgänger (dreistufig: Werke, Verteilzentren, Filialen), ein Streckennetz (Gitter mit Start-Ziel-Aufträgen) oder eines von drei festen Lehrnetzen, an denen sich je ein Effekt von Hand nachrechnen lässt.",
    )
    show_dist, show_grid = net_key == "random", net_key == "grid"
    if show_dist or show_grid:
        K = _slider("Zahl der Güter", "k_slider", "Frische, Trocken, Kühl, Getränke, Tiefkühl (in dieser Reihenfolge). Im Distributionsnetz stellt jedes Werk jedes Gut her; im Streckennetz hat jedes Gut einen eigenen Start und ein eigenes Ziel.")
        fix = _slider("Fixkosten je Lane (Basis)", "fix_slider", "Jede Lane (im Streckennetz jede Strecke) kostet die Basis mal 1 bis 3, ein Verteilzentrum das Doppelte. Zum Vergleich: die Stückkosten je Einheit liegen bei 1 bis 9.", step=5)
    else:
        K = _kept("k_slider", C.DEFAULT_K)
        fix = _kept("fix_slider", C.DEFAULT_FIX)
    if show_dist:
        p = _slider("Werke", "p_slider", "Anzahl der Werke (oben im Netz).")
        d = _slider("Verteilzentren", "d_slider", "Anzahl der Verteilzentren; Durchsatz gemeinsam für alle Güter.")
        s = _slider("Filialen", "s_slider", "Anzahl der Filialen (unten im Netz). Für große Netze ist das Verfahren gedacht; das exakte Optimum zum Vergleich braucht dann länger.")
        density = _slider("Netzdichte [%]", "density_slider", "Anteil der möglichen Lanes, die es gibt.", step=10)
        spread = _slider("Streuung der Lane-Breiten [%]", "spread_slider", "0 = alle Lanes einer Stufe gleich breit, 100 = Kapazitäten gleichverteilt von 1 bis zum Doppelten der Grundbreite.", step=25)
        load = _slider("Auslastung [% der Werkskapazität]", "load_slider", "Gesamtnachfrage der Filialen (alle Güter zusammen) in Prozent der Werkskapazität.", step=10)
        seed_widget("seed_input")
        seed = st.number_input("Zufalls-Seed", *bounds("seed_input"), key="seed_input", step=1)
        st.session_state[KEPT["seed_input"]] = seed
        st.button("🎲 Neues Netz generieren", width="stretch", on_click=randomize_seed, args=("seed_input",), help="Würfelt einen neuen Zufalls-Seed. Die Verteilung über feste Netze weiter unten ändert sich dabei nicht - nur die Marke „Ihre Ziehung“.")
    else:
        p, d, s = _kept("p_slider", C.DEFAULT_P), _kept("d_slider", C.DEFAULT_D), _kept("s_slider", C.DEFAULT_S)
        density, spread, load, seed = _kept("density_slider", C.DEFAULT_DENSITY), _kept("spread_slider", C.DEFAULT_SPREAD), _kept("load_slider", C.DEFAULT_LOAD), _kept("seed_input", C.DEFAULT_SEED)
    if show_grid:
        gw = _slider("Breite des Gitters", "gw_slider", "Knoten je Zeile.")
        gh = _slider("Höhe des Gitters", "gh_slider", "Knoten je Spalte.")
        gdensity = _slider("Anteil der Gitterkanten [%]", "gdensity_slider", "Ein zufälliger Spannbaum hält das Netz zusammenhängend; jede weitere Gitterkante gibt es mit diesem Anteil. 100 % = volles Gitter.", step=10)
        gcap = _slider("Größte Kapazität je Kante", "gcap_slider", "Jede Kante trägt in beide Richtungen 1 bis zu diesem Wert, gemeinsam für alle Güter.")
        gdem = _slider("Größte Menge je Gut", "gdem_slider", "Jedes Gut fährt 1 bis zu diesem Wert von seinem Start zu seinem Ziel.")
        seed_widget("gseed_input")
        gseed = st.number_input("Zufalls-Seed (Streckennetz)", *bounds("gseed_input"), key="gseed_input", step=1)
        st.session_state[KEPT["gseed_input"]] = gseed
        st.button("🎲 Neues Netz generieren", width="stretch", on_click=randomize_seed, args=("gseed_input",), key="rand_grid", help="Würfelt einen neuen Zufalls-Seed für das Streckennetz.")
    else:
        gw, gh, gdensity = _kept("gw_slider", C.DEFAULT_GW), _kept("gh_slider", C.DEFAULT_GH), _kept("gdensity_slider", C.DEFAULT_GDENSITY)
        gcap, gdem, gseed = _kept("gcap_slider", C.DEFAULT_GCAP), _kept("gdem_slider", C.DEFAULT_GDEM), _kept("gseed_input", C.DEFAULT_GSEED)
    if not (show_dist or show_grid):
        st.caption("Dieses Netz ist fest - es gibt nichts zu erzeugen. Die Regler für Güter, Größe, Fixkosten und Seed gehören zu den zufälligen Netzen.")
    st.subheader("Verfahren")
    start = st.radio("Startsteigung", list(C.STARTS), key="start_radio", format_func=lambda k: C.STARTS[k], help="Womit die Steigung beginnt: mit der Kapazität jeder Kante (Fixkosten sehen billig aus, breite Kanten werden bevorzugt) oder mit der halben Gesamtnachfrage (vorsichtiger).")
    damping = st.radio("Dämpfung", list(C.DAMPINGS), key="damping_radio", format_func=lambda v: "keine" if v == 0 else f"{v:g}".replace(".", ","), help="Wie stark die Steigung dem neuen Fluss folgt: 0 = ganz (die Steigung wird durch den Fluss ersetzt), 0,5 = nur zur Hälfte. Dämpfung nimmt den Zickzack aus dem Verlauf.")
    memory = st.radio("Gedächtnis", list(C.ONOFF), key="memory_radio", format_func=lambda k: C.ONOFF[k], help="Die Steigung ist das Mittel der Flüsse über alle Iterationen, in denen die Kante Fluss hatte (nach Crainic/Gendron/Hernu).")
    perturb = st.radio("Störung", list(C.ONOFF), key="perturb_radio", format_func=lambda k: C.ONOFF[k], help="Wiederholt sich ein Entwurf (Zyklus), werden die Steigungen zufällig ausgelenkt (höchstens dreimal, fester Zufallsstrom), statt zu stoppen.")
    polish = st.radio("Politur", list(C.ONOFF), key="polish_radio", format_func=lambda k: C.ONOFF[k], help="Am Ende: den besten Entwurf festhalten, den Fluss per LP neu wählen und Kanten einzeln schließen, solange es billiger wird.")
    iters = st.radio("Iterationsgrenze", list(C.ITERS), key="iter_radio", help="Obergrenze der Steigungs-LPs. Meist endet das Verfahren vorher (Fixpunkt oder Zyklus).")
    control = st.radio("Kontrolle", list(C.CONTROLS), key="control_radio", format_func=lambda k: C.CONTROLS[k], help="Die Negativkontrollen zeigen, warum jede Zutat nötig ist: mit nur einem LP (Steigung bleibt der Startwert) fehlt der ganze Sinn; mit der letzten statt der besten Iteration geht eine schon gefundene gute Lösung verloren.")

sync_query_params({"net_select": net_key, "k_slider": int(K), "p_slider": int(p), "d_slider": int(d), "s_slider": int(s), "density_slider": int(density), "spread_slider": int(spread),
                   "load_slider": int(load), "fix_slider": int(fix), "seed_input": int(seed), "gw_slider": int(gw), "gh_slider": int(gh), "gdensity_slider": int(gdensity), "gcap_slider": int(gcap),
                   "gdem_slider": int(gdem), "gseed_input": int(gseed), "start_radio": start, "memory_radio": memory, "perturb_radio": perturb, "polish_radio": polish, "damping_radio": damping,
                   "iter_radio": iters, "control_radio": control})

params = ev.normalise(ev.NetParams(net_key, int(K), int(p), int(d), int(s), int(density), int(spread), int(load), int(fix), int(seed), int(gw), int(gh), int(gdensity), int(gcap), int(gdem), int(gseed)))
opts = ev.Opts(start, memory, perturb, polish, float(damping), int(iters), control)
with st.spinner("Rechne..."):
    a = _analysis(params, opts)
design = a.design
level, code, dat = ev.verdict(a)
is_fixed = net_key in C.FIXED_NETS

# --- Iterationen ---------------------------------------------------------------------------------------------------------------------

st.markdown("## 📈 Iteration für Iteration")
if not a.feasible:
    st.warning("⚠️ Dieses Netz kann die Nachfrage nicht decken, auch wenn alle Kanten offen sind - es gibt nichts zu entwerfen. Weniger Auslastung, mehr Lanes oder ein anderer Seed hilft.")
    st.stop()

res = a.result
opt = dat["opt"]
speed = dat["highs_seconds"] / dat["seconds"] if dat["seconds"] else float("nan")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Optimum (HiGHS)", _f(opt, 1), delta=f"{dat['opt_open']} von {design.G} Kanten offen", delta_color="off", help="Das ganzzahlige Optimum aus dem direkten MIP von HiGHS - nur die Vergleichsgröße, das Verfahren kennt es nicht.")
m2.metric("Beste Iteration", _f(dat["best"], 1), delta=f"Lücke {_pct(dat['gap_best'])}", delta_color="off", help=f"Die beste wahre Kostensumme aller {dat['iterations']} Iterationen (Iteration {dat['best_iteration']}).")
m3.metric("Mit Politur", _f(dat["polished"], 1), delta=f"Lücke {_pct(dat['gap'])}", delta_color="off", help="Nach der Politur (Fluss neu wählen, Kanten schließen). Ohne Politur ist es die beste Iteration." if polish == "on" else "Politur ist aus: dieselbe Zahl wie die beste Iteration.")
m4.metric("Sekunden", _sec(dat["seconds"]), delta=f"HiGHS {_sec(dat['highs_seconds'])} s", delta_color="off", help="Rechenzeit des Verfahrens einschließlich Politur (nur zur Information).")

stop_text = {"fixed": "Fixpunkt: der Fluss ändert sich nicht mehr", "cycle": "Zyklus: ein früherer Entwurf kehrt wieder", "limit": "Iterationsgrenze erreicht"}[dat["stop"]]
if control == "once":
    st.warning(f"⚠️ Nur ein LP (die Steigung bleibt der Startwert): Kosten {_f(dat['best'], 1)}, Lücke {_pct(dat['gap_best'])} - das ist das erste LP ohne jede Anpassung. Erst das Anpassen der Steigung an den Fluss macht aus der Schätzung eine Lösung.")
elif code == "exact":
    st.success(f"✅ Das Optimum getroffen: {_f(dat['polished'], 1)} nach {dat['iterations']} Iterationen ({stop_text}), in {_sec(dat['seconds'])} Sekunden - HiGHS braucht {_sec(dat['highs_seconds'])}. Der Weg dahin: das erste LP lag {_pct(dat['gap_first'])} über dem Optimum, das Aufrunden aus dem Vorgängerstück {_pct(dat['gap_upper'])}.")
else:
    tail = f" Die Politur gewinnt {_f(dat['polish_gain'], 1)}." if dat["polish_gain"] > 1e-9 else ""
    st.info(f"Kosten {_f(dat['polished'], 1)}, **{_pct(dat['gap'])} über dem Optimum** {_f(opt, 1)} (nach {dat['iterations']} Iterationen, {stop_text}; die beste war Iteration {dat['best_iteration']}, die letzte lag {_pct(dat['gap_last'])} darüber).{tail} Zum Vergleich: das erste LP {_pct(dat['gap_first'])}, das Aufrunden aus Stück 10 {_pct(dat['gap_upper'])}.")

frames = res.frames
opt_open = {g for g in range(design.G) if a.opt.y[g] > 0.5}
owner = (params, opts)
if st.session_state.get("ss_owner") != owner:
    st.session_state["ss_frame"] = len(frames)
    st.session_state["ss_owner"] = owner
step_col, play_col = st.columns([5, 2])
with step_col:
    if len(frames) > 1:
        it_no = st.slider("Iteration", 1, len(frames), key="ss_frame", help="Jede Iteration ist ein Steigungs-LP: welche Kanten der Fluss nutzt, ergibt den Entwurf; die Steigungen der genutzten Kanten werden für die nächste Iteration angepasst.")
    else:
        it_no = 1
        st.caption("Es gibt nur eine Iteration.")
with play_col:
    auto_play = st.button("▶️ Abspielen", width="stretch")
view_slot = st.empty()


def _caption(i):
    f = frames[i]
    prev = frames[i - 1] if i > 0 else None
    label = {"start": "mit der Startsteigung", "update": "mit den angepassten Steigungen", "perturb": "nach einer Störung der Steigungen", "cycle": "nach einem Zyklus"}[f.event]
    text = f"**Iteration {f.iteration}** ({label}): der Fluss nutzt {len(f.design)} von {design.G} Kanten; wahre Kosten {_f(f.true_cost, 1)}, im linearisierten LP {_f(f.linear_cost, 1)}. "
    text += ("Neuer Bestwert! " if f.improved else "") + f"Beste bisher {_f(f.best_cost, 1)} ({_pct(f.best_cost / opt - 1)} über dem Optimum). "
    text += ev.frame_words(design, f, prev) + "."
    return text


def _render(i):
    with view_slot.container():
        f = frames[i]
        c1, c2 = st.columns([3, 2])
        c1.markdown(f"**Iteration {f.iteration}:** der Fluss des Steigungs-LP und seine Steigungen")
        c2.markdown("**Kosten je Iteration**")
        c1.plotly_chart(build_slope_map(design, f, frames[i - 1] if i > 0 else None, opt_open), width="stretch", key=f"slope_map_{i}")
        c2.plotly_chart(build_costs(frames, opt, a.upper, i), width="stretch", key=f"cost_chart_{i}")
        st.caption(_caption(i))


if auto_play:
    for i in range(len(frames)):
        _render(i)
        time.sleep(min(0.6, 6.0 / max(len(frames), 1)))
else:
    _render(it_no - 1)

st.caption("Links: blau = Kante mit Fluss (Beschriftung s = Steigung, mit der ihre Fixkosten umgelegt wurden), grau = ohne Fluss, orange Unterlage = gegenüber der vorigen Iteration neu geöffnet oder geschlossen, rote Unterlage = im ganzzahligen Optimum offen. "
           "Rechts: die wahren Kosten je Iteration (sie schwanken), die beste bis dahin (grün gestrichelt), das Optimum (rot) und das Aufrunden aus dem Vorgängerstück (gepunktet).")

st.markdown("---")

# --- Verteilung ------------------------------------------------------------------------------------------------------------------------

st.markdown("## 📊 Nicht nur dieses eine Netz")
if is_fixed:
    st.info("Festes Netz: es gibt nur diese eine Ziehung. Für die Verteilung über viele Netze ein zufälliges Netz wählen.")
else:
    kind = "Streckennetze" if net_key == "grid" else "Distributionsnetze"
    with st.spinner("Rechne die 40 festen Netze..."):
        dist = _distribution(params, opts)
    st.markdown(f"**{dist['n_seeds']} feste {kind}** mit denselben Einstellungen (Güter {K}, Fixkosten {fix}), getrennt vom Seed oben; {dist['n_infeasible']} davon sind nicht lieferbar und zählen nicht.")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Lücke (Mittel)", _pct(dist["gap_mean"]), delta=f"Median {_pct(dist['gap_median'])}", delta_color="off", help="Kosten der Lösung mit den gewählten Optionen gegen das Optimum, Mittel über die lieferbaren Netze.")
    p2.metric("Optimum getroffen", _pct(dist["exact_share"], 0), delta=f"schlechtestes Netz {_pct(dist['gap_max'])}", delta_color="off", help="Anteil der Netze mit Lücke unter 0,5 %.")
    p3.metric("Iterationen", _f(dist["iterations_mean"], 1), delta=f"Fixpunkt in {dist['stops']['fixed']}, Zyklus in {dist['stops']['cycle']}", delta_color="off", help="Mittel über die Netze; Stoppgrund je Netz.")
    p4.metric("Besser als Aufrunden", f"{dist['better_than_upper']} von {dist['n_feasible']}", delta=f"Aufrunden {_pct(dist['gap_upper_mean'])}", delta_color="off", help="In wie vielen Netzen die Lösung billiger ist als das Aufrunden aus Stück 10 (im Mittel 5 % über dem Optimum).")
    mine = {"gap_first": dat["gap_first"], "gap_best": dat["gap_best"], "gap": dat["gap"], "gap_upper": dat["gap_upper"]}
    st.plotly_chart(build_dist(dist, mine), width="stretch", key="dist_chart")
    st.caption(f"Das erste LP allein liegt im Mittel {_pct(dist['gap_first_mean'])} über dem Optimum, die beste Iteration {_pct(dist['gap_best_mean'])}, mit den gewählten Optionen {_pct(dist['gap_mean'])}; in {_pct(dist['last_worse_share'], 0)} der Netze ist die letzte Iteration schlechter als die beste. Raute = die Ziehung oben.")

st.markdown("---")

# --- Experimente -----------------------------------------------------------------------------------------------------------------------

st.subheader("🔬 Was jede Zutat leistet")
st.caption("Sieben Varianten auf festen Netzen (Standardgröße, 24 Seeds mit den Einstellungen oben, die lieferbaren zählen): das reine Verfahren, dann Politur, Gedächtnis, Störung, Dämpfung und deren Kombinationen.")
if is_fixed:
    st.info("Für dieses Experiment ein zufälliges Netz wählen.")
else:
    if st.button("Varianten durchrechnen", key="variants_start"):
        st.session_state["variants_on"] = True
    if st.session_state.get("variants_on"):
        with st.spinner("Rechne..."):
            vt = ev.variant_table(params)
        st.plotly_chart(build_variants(vt), width="stretch", key="variants_chart")
        st.table({"Variante": [r["name"] for r in vt["rows"]], "Lücke (Mittel)": [_pct(r["gap"]) for r in vt["rows"]], "Optimum getroffen": [f"{r['exact']} von {r['n']}" for r in vt["rows"]],
                  "schlechtestes Netz": [_pct(r["gap_max"]) for r in vt["rows"]], "Iterationen": [_f(r["iterations"], 1) for r in vt["rows"]], "Zyklen": [str(r["cycle"]) for r in vt["rows"]]})
        st.caption(f"{vt['n']} lieferbare Netze. Keine Zutat ist ein Durchbruch: die Lücke liegt zwischen den Varianten nah beieinander; die Dämpfung zusammen mit der Störung hilft am meisten, das Gedächtnis wenig. Die Unterschiede sind auf {vt['n']} Netzen klein - die Rangfolge ist mit Vorsicht zu lesen.")

st.subheader("🔬 Negativkontrollen")
st.caption("Was fehlt, wenn eine Zutat fehlt: die Steigung wird nie angepasst (nur ein LP), oder es zählt die letzte statt der besten Iteration. Jeweils ohne Politur und Störung.")
if is_fixed:
    st.info("Für dieses Experiment ein zufälliges Netz wählen.")
else:
    if st.button("Kontrollen durchrechnen", key="controls_start"):
        st.session_state["controls_on"] = True
    if st.session_state.get("controls_on"):
        with st.spinner("Rechne..."):
            ct = ev.control_table(params)
        labels_ = {"normal": "wie beschrieben (beste Iteration)", "once": "nur ein LP", "last": "letzte statt beste Iteration"}
        st.table({"Variante": [labels_[k] for k in labels_], "Lücke (Mittel)": [_pct(ct[k]["gap"]) for k in labels_], "Optimum getroffen": [f"{ct[k]['exact']} von {ct[k]['n']}" for k in labels_], "schlechtestes Netz": [_pct(ct[k]["worst"]) for k in labels_]})
        st.caption("Ein einziges LP mit der Startsteigung liegt weit vom Optimum; das Anpassen der Steigung ist der Kern. Die letzte statt der besten Iteration kostet etwas Güte, weil der Verlauf schwankt und ein früher Bestwert verloren geht.")

st.subheader("🔬 Ab welcher Größe lohnt es sich?")
st.caption("Slope Scaling (Standardoptionen, 60 Iterationen) gegen das direkte MIP von HiGHS (Zeitlimit 20 Sekunden) über wachsende Netze, zwei feste Netze je Größe.")
if is_fixed:
    st.info("Für dieses Experiment ein zufälliges Netz wählen.")
else:
    if st.button("Größen durchrechnen (etwa eine Minute)", key="sizes_start"):
        st.session_state["sizes_on"] = True
    if st.session_state.get("sizes_on"):
        with st.spinner("Rechne..."):
            sz = ev.size_table(params)
        st.plotly_chart(build_sizes(sz), width="stretch", key="sizes_chart")
        st.table({"Werke/Verteilzentren/Filialen": [f"{r['size'][0]}/{r['size'][1]}/{r['size'][2]}" for r in sz], "Entwurfskanten": [_f(r["groups"], 0) for r in sz], "Lücke Slope Scaling": [_pct(r["gap"]) for r in sz],
                  "Sekunden Slope Scaling": [_sec(r["seconds"]) for r in sz], "Sekunden HiGHS": [_sec(r["highs"]) for r in sz]})
        st.caption("Die Lücke ist gegen die beste Lösung, die HiGHS im Zeitlimit fand, gerechnet (bei Zeitlimit nicht das bewiesene Optimum). Auf kleinen Netzen (wie denen der Vorgänger, 27 Entwurfskanten) ist HiGHS in Hundertstelsekunden fertig und das Verfahren ohne Nutzen; erst bei vielen hundert Entwurfskanten wird der Zeitunterschied groß - zum Preis einer Lücke, die mit der Größe wächst (in der Messreihe der Tests etwa 10 % bei 460 und 14 % bei 1 200 Entwurfskanten; je nach Rechner und Zeitlimit etwas anders).")

st.markdown("---")

# --- Grenzen -----------------------------------------------------------------------------------------------------------------------------

st.subheader("🚧 Wo die Annahmen enden")
st.markdown(
    """
| Annahme | Was passiert, wenn sie verletzt ist - und wer setzt an |
|---|---|
| **Eine gute Lösung genügt** | Es gibt keine Schranke und keinen Beweis: ob die Lösung 1 % oder 10 % über dem Optimum liegt, weiß man nur mit einem exakten Vergleich (Stück 10 und 11). |
| **Die Steigung findet den Entwurf** | Ist der Fixpunkt ein lokales Optimum oder ein Zyklus, bleibt das Verfahren stecken; Dämpfung, Gedächtnis und Störung mildern das, beheben es nicht. |
| **Ein LP je Iteration ist billig** | Für sehr große Netze trägt das LP selbst nicht mehr; dann braucht es Spaltenerzeugung (mcf-column-generation-demo) oder die Näherung ohne LP-Löser (garg-koenemann-demo). |
| **Nur Entwurfskanten kosten fix** | Mengenrabatte, Fahrzeugtypen oder Fahrpläne verlangen andere Linearisierungen (leercontainer-demo, linehaul-demo). |
| **Nachbarschaftssuche** | MIP-basierte Verbesserungen (Local Branching, RINS) setzen auf einer Lösung wie dieser auf und gehören in die LNS-Linie (alns-demo). |
"""
)
st.caption("Die Netzwerkfluss-Linie besteht aus Edmonds-Karp, Dinic, Push-Relabel, Successive Shortest Paths, Cycle-Canceling, Cost Scaling, Netzwerksimplex, Mehrgüterfluss, Column Generation, Garg-Könemann, Fixkosten-Netzwerkdesign, Benders-Zerlegung und Slope Scaling (dieses Stück; die dreizehn Stücke der Hauptlinie) sowie den Erweiterungen Projektauswahl, Graph Cuts, Gomory-Hu-Baum, Frank-Wolfe, Gradient Projection und Fluss über die Zeit; alle sind gebaut.")

st.markdown("---")

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Entwurf.** $\min\ \sum_g f_g y_g+\sum_{k,e}c^k_e x^k_e$ u.d.N. Flusserhaltung je Gut, $\sum_k x^k_e\le u_e y_{g(e)}$, $y\in\{0,1\}^G$, volle Nachfrage.

**Linearisierung.** Fließt über die Gruppe $g$ die Menge $F_g=\sum_{e\in g}\sum_k x^k_e>0$, sind die Fixkosten $f_g=F_g\cdot(f_g/F_g)$: als Stückkosten $f_g/F_g$ auf den Fluss umgelegt. Gilt das für die erwartete Menge $s_g=F_g$, bezahlt das LP
$$\min\ \sum_{k,e}\Big(c^k_e+\frac{f_{g(e)}}{s_{g(e)}}\Big)x^k_e\quad\text{u.d.N. Flusserhaltung, }\sum_k x^k_e\le u_e$$
genau die wahren Kosten. Iteration: $s_g^{t+1}=\alpha\,s_g^t+(1-\alpha)F_g^t$ für Gruppen mit Fluss ($\alpha$ = Dämpfung, ohne Dämpfung $\alpha=0$); mit Gedächtnis ist $s_g^{t+1}$ das Mittel der positiven $F_g$ bisher. Kanten ohne Fluss werden nicht bezahlt.

**Wahre Kosten.** $\text{cost}(x)=\sum_{g:\,F_g>0}f_g+\sum c\,x$; das Verfahren merkt $\min_t\text{cost}(x^t)$. **Politur:** bei festem Entwurf $D$ ist der beste Fluss ein LP; dann werden Gruppen aus $D$ (teuerste Fixkosten zuerst) einzeln entfernt, solange die Gesamtkosten sinken.

**Keine Garantie.** Der Zielwert des Steigungs-LP ist weder obere noch untere Schranke der wahren Kosten (ohne Dämpfung liegt er im Fixpunkt genau auf ihnen; mit Dämpfung stoppt das Verfahren, sobald sich der Fluss wiederholt, die Steigung ist dann noch nicht ganz beim Fluss angekommen, und beide können auseinanderliegen); das Optimum dient nur der Bewertung.

Implementiert in `ss_slope.py` (Steigungs-LP, Schleife, Bausteine, Politur), `ss_formulation.py` (MIP-Optimum, Fluss bei festem Entwurf, Aufrunden; Kopie aus dem Vorgänger), `ss_model.py` und `ss_scenario.py` (Netze), `ss_evaluation.py`, `ss_visualization.py`; das Vergleichs-MIP löst HiGHS über `scipy`.
        """
    )

st.markdown("---")

st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zur Reihe: [Netzwerkfluss: vom Max-Flow zum Netzdesign](https://sebastianhanisch.net/konzepte-netzwerkfluss.html)."
)
