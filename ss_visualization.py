"""Plotly-Abbildungen: Netz mit Steigungen und Fluss, Kosten je Iteration, Varianten, Verteilung der Lücke und Größe.
Achsen sind gesperrt (fixedrange), damit Touch-Geräte beim Scrollen nicht zoomen. Kanten haben über unsichtbare Marker einen Hover-Text
(Plotly-Linien reagieren nur an ihren Stützpunkten)."""

from math import atan2, degrees, hypot

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import ss_constants as C


def lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _base(fig, height):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.08), plot_bgcolor="rgba(0,0,0,0)")
    return lock_axes(fig)


def _layout(fig, net, height, skip=()):
    xs = [p[0] for v, p in enumerate(net.pos) if v not in skip]
    ys = [p[1] for v, p in enumerate(net.pos) if v not in skip]
    pad = 9
    fig.update_xaxes(visible=False, range=[min(xs) - pad, max(xs) + pad], scaleanchor="y", scaleratio=1)
    fig.update_yaxes(visible=False, range=[min(ys) - pad, max(ys) + pad])
    return _base(fig, height)


def _curve(p0, p1, bulge, steps=8):
    """Punkte von p0 nach p1; mit `bulge` > 0 als flacher Bogen nach rechts (so trennen sich Vorwärts- und Rückkante). Dazu der Pfeilwinkel bei 65 %."""
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    length = hypot(dx, dy) or 1.0
    cx, cy = (x0 + x1) / 2 + bulge * length * dy / length, (y0 + y1) / 2 - bulge * length * dx / length
    ts = [k / steps for k in range(steps + 1)]
    xs = [(1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1 for t in ts]
    ys = [(1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1 for t in ts]
    t = 0.65
    tx = 2 * (1 - t) * (cx - x0) + 2 * t * (x1 - cx)
    ty = 2 * (1 - t) * (cy - y0) + 2 * t * (y1 - cy)
    ax = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t * t * x1
    ay = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t * t * y1
    return xs, ys, (ax, ay, degrees(atan2(tx, ty))), (xs[steps // 2], ys[steps // 2])


def _segments(curves):
    x, y = [], []
    for xs, ys, _, _ in curves:
        x += xs + [None]
        y += ys + [None]
    return x, y


def _lines(fig, curves, color, width, name, dash=None, showlegend=True):
    if not curves:
        return
    x, y = _segments(curves)
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color=color, width=width, dash=dash), hoverinfo="skip", name=name, showlegend=showlegend))


def _arrows(fig, curves, color, size=9):
    if not curves:
        return
    fig.add_trace(go.Scatter(x=[c[2][0] for c in curves], y=[c[2][1] for c in curves], mode="markers", hoverinfo="skip", showlegend=False,
                             marker=dict(symbol="arrow", size=size, color=color, angle=[c[2][2] for c in curves])))


def _hover_points(fig, net, entries):
    """Unsichtbare Marker entlang jeder Kante, damit der Hover-Text überall auf der Kante erscheint. entries: [(Kurve, Text)]"""
    x, y, text = [], [], []
    for curve, label in entries:
        xs, ys = curve[0], curve[1]
        for k in range(1, len(xs) - 1):
            x.append(xs[k]); y.append(ys[k]); text.append(label)
    if x:
        fig.add_trace(go.Scatter(x=x, y=y, mode="markers", marker=dict(size=9, opacity=0), hovertext=text, hoverinfo="text", showlegend=False))


def _labels(fig, points):
    """points: [(x, y, Text)] - als Annotationen mit heller Hinterlegung, damit sie Kanten, Pfeile und Knotenbeschriftungen nicht unlesbar machen."""
    for x, y, text in points:
        fig.add_annotation(x=x, y=y, text=text, showarrow=False, xanchor="left", font=dict(size=11, color="#111"), bgcolor="rgba(255,255,255,0.88)", borderpad=1)


def _arc_name(net, i):
    u, v = net.arcs[i][0], net.arcs[i][1]
    return f"{net.names[u]} → {net.names[v]}"


def _wscale(net):
    return max(c for _, _, c, _, _ in net.arcs)


def _width(amount, top, lo=1.0, hi=6.0):
    return lo + (hi - lo) * amount / top if top else lo


def _node_text_positions(net, idx):
    if net.logistic:
        return ["top center" if (v == 0 or net.names[v].startswith("Werk")) else "bottom center" if (v == 1 or net.names[v].startswith("Filiale")) else "middle left" for v in idx]
    return ["top center" if v == net.s else "bottom center" if v == net.t else "middle left" for v in idx]


TOL = 1e-6


def _shift(curve, dx, dy):
    xs, ys, (ax, ay, ang), (mx, my) = curve
    return [x + dx for x in xs], [y + dy for y in ys], (ax + dx, ay + dy, ang), (mx + dx, my + dy)


def _fmt(x):
    return f"{x:.1f}".replace(".", ",") if abs(x - round(x)) > TOL else f"{round(x)}"


def _is_terminal(net, e):
    return net.arcs[e][0] == net.s or net.arcs[e][1] == net.t


def _num(x, digits=2):
    return f"{x:.{digits}f}".replace(".", ",")


def _pct(x, digits=1):
    return f"{100 * x:.{digits}f} %".replace(".", ",")


def build_slope_map(design, frame, previous=None, opt_open=None, height=480):
    """Netz in einer Iteration: Blau = Kante mit Fluss (Dicke ~ Fluss / Kapazität, Beschriftung: Steigung, mit der die Fixkosten umgelegt wurden), grau = ohne Fluss; orange Unterlage = Kante, die gegenüber der
    vorigen Iteration neu geöffnet oder geschlossen wurde, rote Unterlage = im ganzzahligen Optimum offen. Im Streckennetz sind die Kanten von S und zu T ausgeblendet."""
    net = design.net
    grid = design.mcf.layout == "grid"
    fig = go.Figure()
    bulge = 0.0 if net.logistic else 0.12
    K, m = design.K, design.m
    flows = np.asarray(frame.x, dtype=float).reshape(K, m).sum(axis=0)
    prev = previous.design if previous is not None else None
    curves = {"open": [], "closed": [], "opt": [], "changed": [], "fixed": []}
    used, hover, labels = [], [], []
    seen, drawn = set(), {}
    for e, (u, v, cap, cost, kind) in enumerate(net.arcs):
        if grid and _is_terminal(net, e):
            continue
        g = design.group[e]
        if grid and g in seen:
            continue
        par = drawn.get((u, v), 0)
        drawn[(u, v)] = par + 1
        base = _curve(net.pos[u], net.pos[v], 0.0 if grid else bulge + 0.2 * par)
        load = float(flows[e])
        if g < 0:
            curves["fixed"].append(base)
            hover.append((base, f"{_arc_name(net, e)} (Kapazität {cap}, immer offen): Fluss {_fmt(load)}"))
            continue
        seen.add(g)
        is_used = g in frame.design
        curves["open" if is_used else "closed"].append(base)
        if opt_open is not None and g in opt_open:
            curves["opt"].append(base)
        if prev is not None and (g in frame.design) != (g in prev):
            curves["changed"].append(base)
        if is_used:
            used.append((base, 1.5 + 4.5 * min(1.0, load / cap)))
            if design.m <= 60 and load > TOL:
                labels.append((load, base[0][3] + 1.5, base[1][3], f"s={_fmt(frame.slope[g])}"))
        unit = design.fixed[g] / frame.slope[g]
        hover.append((base, f"{_arc_name(net, e)}: {'Fluss ' + _fmt(load) if is_used else 'kein Fluss'}, Fixkosten {design.fixed[g]}, Steigung {_fmt(frame.slope[g])} (umgelegt {_num(unit, 2)} je Einheit), Kapazität {cap}"))
    _lines(fig, curves["opt"], "rgba(214,39,40,0.35)", 12, "Optimum (ganzzahlig)")
    _lines(fig, curves["changed"], "rgba(255,127,14,0.5)", 10, "gegenüber vorher geändert")
    _lines(fig, curves["fixed"], C.COLORS["closed"], 1.0, "Werks-/Nachfragekanten", showlegend=False)
    _lines(fig, curves["closed"], C.COLORS["closed"], 1.0, "ohne Fluss")
    for c, w in used:
        _lines(fig, [c], C.COLORS["open"], w, "mit Fluss", showlegend=False)
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line=dict(color=C.COLORS["open"], width=3.5), name="mit Fluss"))
    if net.m <= 80:
        _arrows(fig, curves["open"], "rgba(60,60,60,0.55)", 7)
    _hover_points(fig, net, hover)
    _labels(fig, [(x, y, t) for _, x, y, t in sorted(labels, key=lambda l: -l[0])[:10]])          # nur die zehn Kanten mit dem meisten Fluss beschriften
    idx = [v for v in range(net.n) if not (grid and v in (net.s, net.t))]
    fig.add_trace(go.Scatter(x=[net.pos[v][0] for v in idx], y=[net.pos[v][1] for v in idx], mode="markers+text", showlegend=False, text=[net.labels[v] for v in idx],
                             textposition=_node_text_positions(net, idx), hovertext=[net.names[v] for v in idx], hoverinfo="text",
                             marker=dict(symbol=["square" if v in (net.s, net.t) else "circle" for v in idx], size=[13 if v in (net.s, net.t) else 10 for v in idx], color=C.COLORS["node"], line=dict(width=1.5, color="#333"))))
    return _layout(fig, net, height, skip=(net.s, net.t) if grid else ())


def build_costs(frames, opt, upper, i, height=340):
    """Wahre Kosten je Iteration (Linie), die beste bis dahin (grün), das Optimum (rot) und das Aufrunden aus dem Vorgängerstück (gepunktet); Ring = gezeigte Iteration."""
    xs = [f.iteration for f in frames]
    fig = go.Figure()
    fig.add_hline(y=opt, line=dict(color=C.COLORS["opt"], width=2))
    fig.add_hline(y=upper, line=dict(color="#555", width=1.5, dash="dot"))
    fig.add_trace(go.Scatter(x=xs, y=[f.true_cost for f in frames], mode="lines+markers", line=dict(color=C.COLORS["cost"], width=2), marker=dict(size=7), name="wahre Kosten",
                             hovertext=[f"Iteration {f.iteration}: {_num(f.true_cost, 1)} ({len(f.design)} Kanten, {f.event})" for f in frames], hoverinfo="text"))
    fig.add_trace(go.Scatter(x=xs, y=[f.best_cost for f in frames], mode="lines", line=dict(color=C.COLORS["best"], width=2, dash="dash"), name="beste bis hier", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line=dict(color=C.COLORS["opt"], width=2), name="Optimum"))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line=dict(color="#555", width=1.5, dash="dot"), name="Aufrunden (Stück 10)"))
    f = frames[i]
    fig.add_trace(go.Scatter(x=[f.iteration], y=[f.true_cost], mode="markers", marker=dict(size=15, color="rgba(0,0,0,0)", line=dict(width=3, color="#9467bd")), name="gezeigte Iteration", hoverinfo="skip"))
    hi = max(max(f.true_cost for f in frames), upper)
    fig.update_xaxes(title="Iteration", dtick=1 if len(frames) <= 20 else None)
    fig.update_yaxes(title="Kosten", range=[opt * 0.97, hi * 1.03])
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.35), plot_bgcolor="rgba(0,0,0,0)")
    return lock_axes(fig)


def build_variants(table, height=340):
    """Mittlere Lücke zum Optimum je Variante (Beschriftung: Anteil der Netze, in denen das Optimum getroffen wird)."""
    rows = table["rows"]
    fig = go.Figure(go.Bar(x=[r["name"] for r in rows], y=[100 * r["gap"] for r in rows], marker_color="#1f77b4", text=[f"{100 * r['gap']:.1f} %".replace(".", ",") for r in rows], textposition="outside",
                           hovertext=[f"{r['name']}: Lücke {_pct(r['gap'])}, Optimum in {r['exact']} von {r['n']} Netzen, {r['iterations']:.1f} Iterationen, {r['cycle']} Zyklen" for r in rows], hoverinfo="text"))
    fig.update_yaxes(title="Lücke zum Optimum [%]", range=[0, max(100 * r["gap"] for r in rows) * 1.25 + 0.5])
    fig.update_xaxes(tickangle=-25)
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
    return lock_axes(fig)


def build_dist(dist, mine, height=360):
    """Verteilung der Lücke zum Optimum über feste Netze: das erste LP, die beste Iteration, mit Politur (gewählte Optionen) und das Aufrunden aus Stück 10; Raute = die gezeigte Ziehung. `mine`: {Schlüssel: Lücke}."""
    fig = go.Figure()
    names = (("gap_first", "erstes LP", "#c7c7c7"), ("gap_best", "beste Iteration", "#1f77b4"), ("gap", "mit Politur", "#2ca02c"), ("gap_upper", "Aufrunden (Stück 10)", "#7f7f7f"))
    for key, name, color in names:
        fig.add_trace(go.Box(y=[100 * v for v in dist["cols"][key]], name=name, marker_color=color, boxpoints="all", jitter=0.4, pointpos=0, marker_size=4, showlegend=False))
    if mine:
        fig.add_trace(go.Scatter(x=[n for k, n, _ in names if k in mine], y=[100 * mine[k] for k, _, _ in names if k in mine], mode="markers", name="Ihre Ziehung",
                                 marker=dict(symbol="diamond", size=13, color=C.COLORS["opt"], line=dict(width=1.5, color="#111"))))
    fig.update_yaxes(title="Lücke zum Optimum [%]")
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.1), plot_bgcolor="rgba(0,0,0,0)")
    return lock_axes(fig)


def build_sizes(rows, height=320):
    """Sekunden je Netzgröße: Slope Scaling gegen HiGHS (mit Zeitlimit), logarithmisch; Beschriftung der Balken: Sekunden."""
    xs = [f"{r['groups']:.0f} Kanten" for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=xs, y=[r["seconds"] for r in rows], name="Slope Scaling", marker_color="#2ca02c", text=[f"{r['seconds']:.1f}" for r in rows], textposition="outside"))
    fig.add_trace(go.Bar(x=xs, y=[r["highs"] for r in rows], name="HiGHS (direktes MIP)", marker_color="#9467bd", text=[f"{r['highs']:.1f}" for r in rows], textposition="outside"))
    fig.update_xaxes(title="Entwurfskanten im Netz", type="category")
    fig.update_yaxes(type="log", title="Sekunden (log.)")
    fig.update_layout(height=height, barmode="group", margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", y=-0.3), plot_bgcolor="rgba(0,0,0,0)")
    return lock_axes(fig)
